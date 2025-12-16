import json
import re
import streamlit as st
import pandas as pd

PHASES = ["SD", "DD", "CD", "Bidding", "CA"]

# =========================================================
# Helpers
# =========================================================
def money(x: float) -> str:
    return f"${x:,.0f}"

def normalize(weights: dict) -> dict:
    total = sum(max(v, 0.0) for v in weights.values())
    if total <= 0:
        n = len(weights)
        return {k: 1.0 / n for k in weights}
    return {k: max(v, 0.0) / total for k, v in weights.items()}

def safe_num(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

def build_plan_from_library(task_df: pd.DataFrame, target_fee: float, rate: float, phase_split: dict) -> pd.DataFrame:
    phase_split_n = normalize(phase_split)
    df = task_df.copy()
    df = df[df.get("Enabled", True) == True].copy()
    if df.empty:
        df = pd.DataFrame([{"Phase": "SD", "Task": "No tasks enabled", "BaseHours": 1.0, "Enabled": True}])

    df["BaseHours"] = pd.to_numeric(df["BaseHours"], errors="coerce").fillna(0.0)

    out = []
    for ph, frac in phase_split_n.items():
        phase_fee = target_fee * frac
        phase_hours = phase_fee / rate if rate > 0 else 0.0

        p = df[df["Phase"] == ph].copy()
        if p.empty:
            p = pd.DataFrame([{"Phase": ph, "Task": f"{ph} - General", "BaseHours": 1.0, "Enabled": True}])

        base_sum = float(p["BaseHours"].sum())
        p["Hours"] = (p["BaseHours"] / base_sum * phase_hours) if base_sum > 0 else 0.0
        p["Fee ($)"] = p["Hours"] * rate
        out.append(p[["Phase", "Task", "Hours", "Fee ($)"]])

    out_df = pd.concat(out, ignore_index=True)
    out_df["Hours"] = out_df["Hours"].round(1)
    out_df["Fee ($)"] = out_df["Fee ($)"].round(0)
    return out_df

# =========================================================
# $/SF Lookup (Space Type -> $/SF)
# =========================================================
RATE_LOOKUP = {
    "Office (Fitout / Renovation)": 1.50,
    "Office (Core & Shell)": 0.95,
    "Lobby / Reception": 1.50,
    "Conference Rooms": 1.50,
    "Ballrooms": 1.75,
    "Hotel Rooms": 1.50,
    "Retail (dry non-cooking)": 0.85,
    "Retail (Core & Shell Restaurant)": 0.95,
    "Restaurant (Kitchen / Dining Areas)": 2.75,
    "Parking (Open)": 0.35,
    "Parking (Enclosed)": 0.45,
    "Multifamily (Garden Style)": 0.85,
    "Multifamily (High Rise)": 1.01,
    # These need override
    "Site Lighting": None,
    "Site Parking": None,
    "BOH Rooms": 0.75,
    "Classroom": 1.50,
    "Bar / Lounge Areas": 1.25,
    "Amenity Areas": 1.25,
    "Manufacturing Light (Mainly Storage)": 0.95,
    "Manufacturing Complex (Process Equipment Etc.)": 1.50,
}
SPACE_TYPES = list(RATE_LOOKUP.keys())

def new_space_row(space_type=None, space_name="", area=0):
    if space_type is None:
        space_type = SPACE_TYPES[0]
    return {
        "Delete?": False,
        "Override $/SF?": False,
        "Space Name": space_name,
        "Space Type": space_type,
        "Area (SF)": int(area),
        "$/SF": 0.0,
        "Total Cost": 0.0,
        "Notes": "",
    }

def build_default_area_df():
    examples = [
        ("Amenity Areas", "Amenities", 18000),
        ("BOH Rooms", "Back of House", 14000),
        ("Retail (Core & Shell Restaurant)", "Retail", 5000),
        ("Office (Core & Shell)", "Office", 4500),
        ("Parking (Enclosed)", "Parking", 80000),
        ("Multifamily (High Rise)", "Residential", 175000),
        ("Restaurant (Kitchen / Dining Areas)", "Restaurant", 3000),
        ("Site Lighting", "Site Lighting (override)", 0),
    ]
    return pd.DataFrame([new_space_row(t, n, a) for t, n, a in examples])

def recalc_area_df(df_in: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    df = df_in.copy()

    required_cols = ["Delete?", "Override $/SF?", "Space Name", "Space Type", "Area (SF)", "$/SF", "Total Cost", "Notes"]
    for c in required_cols:
        if c not in df.columns:
            df[c] = "" if c in ["Space Name", "Space Type", "Notes"] else 0

    df["Area (SF)"] = pd.to_numeric(df["Area (SF)"], errors="coerce").fillna(0.0)
    df["$/SF"] = pd.to_numeric(df["$/SF"], errors="coerce").fillna(0.0)

    missing_defaults = []
    for i, row in df.iterrows():
        stype = row.get("Space Type", "")
        override = bool(row.get("Override $/SF?", False))
        lookup = RATE_LOOKUP.get(stype)
        if not override:
            if lookup is None:
                df.loc[i, "$/SF"] = 0.0
                if stype:
                    missing_defaults.append(stype)
            else:
                df.loc[i, "$/SF"] = float(lookup)

    df["Total Cost"] = df["Area (SF)"] * df["$/SF"]
    return df, missing_defaults

def style_preview(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    input_cols = ["Space Name", "Space Type", "Area (SF)", "Override $/SF?", "$/SF", "Notes"]
    computed_cols = ["Total Cost"]

    def _cell_base(col):
        if col in computed_cols:
            return "background-color: #F3F4F6;"  # gray
        if col in input_cols:
            return "background-color: #ECFDF5;"  # light green
        return ""

    def _row_style(row):
        styles = []
        stype = str(row.get("Space Type", ""))
        override = bool(row.get("Override $/SF?", False))
        area = float(row.get("Area (SF)", 0.0))
        psf = float(row.get("$/SF", 0.0))

        missing_area = area <= 0
        lookup = RATE_LOOKUP.get(stype)
        needs_override = (lookup is None) and (not override)
        missing_psf = (psf <= 0) and (override or lookup is not None)

        for col in row.index:
            base = _cell_base(col)
            if col == "Area (SF)" and missing_area:
                styles.append(base + "border: 2px solid #EF4444;")
            elif col == "$/SF" and (needs_override or missing_psf):
                styles.append(base + "border: 2px solid #EF4444;")
            else:
                styles.append(base)
        return styles

    preview = df.copy()
    preview["Area (SF)"] = preview["Area (SF)"].map(lambda x: float(x))
    preview["$/SF"] = preview["$/SF"].map(lambda x: float(x))
    preview["Total Cost"] = preview["Total Cost"].map(lambda x: float(x))

    styler = preview.style.apply(_row_style, axis=1).format({
        "Area (SF)": "{:,.0f}",
        "$/SF": "{:,.2f}",
        "Total Cost": "${:,.0f}",
    })
    return styler

# =========================================================
# Default Task Libraries
# =========================================================
def electrical_defaults_df():
    tasks = [
        ("SD","PM: kickoff meetings / coordination",10),
        ("SD","PM: schedule tracking",6),
        ("SD","PM: client coordination (SD)",8),
        ("SD","PM: internal reviews / QA",6),
        ("SD","Utility research & service availability",10),
        ("SD","Preliminary load calculations",14),
        ("SD","Service & distribution concepts",16),
        ("SD","Electrical room & shaft planning",12),
        ("SD","Preliminary risers / one-lines",18),
        ("SD","Typical unit power & lighting concepts",16),
        ("SD","Common area electrical concepts",12),
        ("SD","EV charging assumptions",8),
        ("SD","Life safety & code analysis",10),
        ("SD","Basis of Design narrative",12),
        ("SD","SD review & revisions",10),

        ("DD","PM: client coordination (DD)",8),
        ("DD","PM: discipline coordination (DD)",8),
        ("DD","PM: internal design reviews (DD)",6),
        ("DD","Updated load calculations",14),
        ("DD","Power plans – typical units",24),
        ("DD","Power plans – common areas",22),
        ("DD","Lighting layouts & controls",22),
        ("DD","Equipment room layouts",12),
        ("DD","Metering strategy",10),
        ("DD","Panel schedules (DD level)",14),
        ("DD","Riser & one-line refinement",14),
        ("DD","Arch coordination",16),
        ("DD","Mechanical coordination",12),
        ("DD","Code compliance review",8),
        ("DD","DD review & revisions",14),

        ("CD","PM: issue management / meetings (CD)",10),
        ("CD","PM: fee & scope tracking (CD)",6),
        ("CD","Final unit power plans",36),
        ("CD","Final common area power plans",30),
        ("CD","Lighting plans & controls",32),
        ("CD","Emergency / life safety systems",20),
        ("CD","Final risers & one-lines",26),
        ("CD","Final load calculations",12),
        ("CD","Panel schedules (final)",28),
        ("CD","Details & diagrams",18),
        ("CD","Grounding & bonding",10),
        ("CD","Specs & general notes",14),
        ("CD","Discipline coordination",20),
        ("CD","Internal QA/QC",18),
        ("CD","Permit set issuance",12),
        ("CD","Permit support",6),
        ("CD","Plan check review",10),
        ("CD","Comment responses",14),
        ("CD","Drawing revisions (permit comments)",12),
        ("CD","AHJ coordination",4),

        ("Bidding","Contractor RFIs",16),
        ("Bidding","Addenda",14),
        ("Bidding","VE reviews",8),
        ("Bidding","Bid evaluation support",8),

        ("CA","PM: CA coordination & reporting",12),
        ("CA","Submittal reviews",34),
        ("CA","Shop drawings",20),
        ("CA","RFIs",28),
        ("CA","Site visits",22),
        ("CA","Change order reviews",12),
        ("CA","Punchlist support",12),
        ("CA","As-built review",10),
    ]
    df = pd.DataFrame(tasks, columns=["Phase","Task","BaseHours"])
    df["Enabled"] = True
    return df[["Phase","Task","BaseHours","Enabled"]]

PLUMBING_TAGS = ["", "lux_units_4hr", "typ_units_4hr", "dom_units_2hr", "podium_only"]

def plumbing_defaults_df():
    tasks = [
        ("SD","SAN/VENT - Initial Sizing",3,""),
        ("SD","SAN/VENT - Civil Coordination",9,""),
        ("SD","SAN/VENT - Luxury Amenity",9,""),
        ("SD","SAN/VENT - Luxury Units (hr/unit)",4,"lux_units_4hr"),
        ("SD","SAN/VENT - Typical Units (hr/unit)",4,"typ_units_4hr"),
        ("SD","STORM - Main Roof Sizing",18,""),
        ("SD","STORM - Podium Sizing",9,"podium_only"),
        ("SD","Domestic - Initial Sizing",4,""),
        ("SD","Domestic - Pump Sizing",4,""),

        ("DD","SAN/VENT - Potential Equipment Sizing",18,""),
        ("DD","STORM - Riser Coordination Luxury",5,""),
        ("DD","STORM - Offsets",4,""),
        ("DD","STORM - Riser Coordination Typical",5,""),
        ("DD","STORM - Riser Offsets",4,""),
        ("DD","STORM - Podium",14,"podium_only"),
        ("DD","Domestic - Ground Lvl distribution",10,""),
        ("DD","Domestic - Amenity distribution",10,""),
        ("DD","Domestic - Top Level distribution",10,""),
        ("DD","Domestic - Unit Distribution (hr/unit)",2,"dom_units_2hr"),

        ("CD","SAN/VENT - In building Collections",54,""),
        ("CD","SAN/VENT - Ground Level Collections",9,""),
        ("CD","SAN/VENT - Underground Collections",18,""),
        ("CD","SAN/VENT - Isometrics",40,""),
        ("CD","SAN/VENT - Derm Grease",9,""),
        ("CD","STORM - Ground Level Collections",9,""),
        ("CD","STORM - Underground Collections",18,""),
        ("CD","STORM - Storm Isometrics",18,""),
        ("CD","Domestic - Domestic Isometrics",18,""),
        ("CD","Garage Drainage - Collections",27,""),
        ("CD","Garage Drainage - Equipment Sizing",4,""),
        ("CD","Garage Drainage - Civil Coordination",4,""),
        ("CD","Garage Drainage - Isometric",18,""),
        ("CD","Misc/Details/Schedules",18,""),

        ("Bidding","Bidding support (Plumbing)",10,""),
        ("CA","Submittals / RFIs / site support (Plumbing)",60,""),
    ]
    df = pd.DataFrame(tasks, columns=["Phase","Task","BaseHours","Tag"])
    df["Enabled"] = True
    return df[["Phase","Task","BaseHours","Tag","Enabled"]]

def mechanical_defaults_df():
    tasks = [
        ("SD","Meetings",12),
        ("SD","Preliminary load calcs",18),
        ("SD","Preliminary sizing/routing",15),
        ("SD","SD Narrative",8),
        ("SD","QA/QC",2),

        ("DD","Meetings",20),
        ("DD","Load calcs",20),
        ("DD","Coordination",10),
        ("DD","Equipment selection",15),
        ("DD","Details/Schedules",10),
        ("DD","Chase/Shaft/BOH routing",15),
        ("DD","Unit modeling",60),
        ("DD","Amenity space modeling",40),
        ("DD","QA/QC",8),

        ("CD","Meetings",16),
        ("CD","Coordination",10),
        ("CD","Equipment selection",10),
        ("CD","Details/Schedules",10),
        ("CD","BOH routing/detailing",20),
        ("CD","Unit modeling/detailing",40),
        ("CD","Amenity space modeling",20),
        ("CD","QA/QC",8),

        ("Bidding","Meetings",25),
        ("Bidding","Coordination",10),
        ("Bidding","RFI/Submittals",20),

        ("CA","CA Support (submittals/RFIs/site)",60),
    ]
    df = pd.DataFrame(tasks, columns=["Phase","Task","BaseHours"])
    df["Enabled"] = True
    return df[["Phase","Task","BaseHours","Enabled"]]

def build_plumbing_task_df_from_library(lib_df: pd.DataFrame, podium: bool, lux_units: int, typ_units: int, dom_units: int):
    df = lib_df.copy()
    df = df[df.get("Enabled", True) == True].copy()
    if df.empty:
        return pd.DataFrame([{"Phase":"SD","Task":"No plumbing tasks enabled","BaseHours":1.0,"Enabled":True}])

    df["BaseHours"] = pd.to_numeric(df["BaseHours"], errors="coerce").fillna(0.0)
    df["Tag"] = df.get("Tag", "").fillna("").astype(str)

    rows = []
    for _, r in df.iterrows():
        tag = r["Tag"].strip()
        ph = r["Phase"]
        task = r["Task"]
        base = float(r["BaseHours"])

        if tag == "podium_only":
            if not podium:
                continue
            rows.append({"Phase": ph, "Task": task, "BaseHours": base, "Enabled": True})
        elif tag == "lux_units_4hr":
            rows.append({"Phase": ph, "Task": task, "BaseHours": base * float(lux_units), "Enabled": True})
        elif tag == "typ_units_4hr":
            rows.append({"Phase": ph, "Task": task, "BaseHours": base * float(typ_units), "Enabled": True})
        elif tag == "dom_units_2hr":
            rows.append({"Phase": ph, "Task": task, "BaseHours": base * float(dom_units), "Enabled": True})
        else:
            rows.append({"Phase": ph, "Task": task, "BaseHours": base, "Enabled": True})

    out = pd.DataFrame(rows)
    if out.empty:
        out = pd.DataFrame([{"Phase":"SD","Task":"No plumbing tasks enabled","BaseHours":1.0,"Enabled":True}])
    return out[["Phase","Task","BaseHours","Enabled"]]

# =========================================================
# Presets (JSON)
# =========================================================
def export_preset() -> str:
    preset = {
        "version": 1,
        "rate": {
            "base_raw_rate": st.session_state.get("base_raw_rate", 56.0),
            "multiplier": st.session_state.get("multiplier", 3.6),
        },
        "phase_split": st.session_state.get("phase_split", {"SD":12.0,"DD":40.0,"CD":28.0,"Bidding":1.5,"CA":18.5}),
        "discipline_pct": {
            "electrical": st.session_state.get("electrical_pct", 28.0),
            "plumbing_fire": st.session_state.get("plumbing_fire_pct", 24.0),
            "mechanical": st.session_state.get("mechanical_pct", 48.0),
        },
        "auto_balance": st.session_state.get("auto_balance", True),
        "plumbing_inputs": {
            "podium": st.session_state.get("podium", True),
            "lux_units": st.session_state.get("lux_units", 8),
            "typ_units": st.session_state.get("typ_units", 12),
            "dom_units": st.session_state.get("dom_units", 25),
        },
        "area_df": st.session_state.get("area_df", build_default_area_df()).to_dict(orient="list"),
        "tasks": {
            "electrical": st.session_state.get("electrical_lib", electrical_defaults_df()).to_dict(orient="list"),
            "plumbing": st.session_state.get("plumbing_lib", plumbing_defaults_df()).to_dict(orient="list"),
            "mechanical": st.session_state.get("mechanical_lib", mechanical_defaults_df()).to_dict(orient="list"),
        },
    }
    return json.dumps(preset, indent=2)

def load_preset_from_json(text: str):
    preset = json.loads(text)

    st.session_state["base_raw_rate"] = safe_num(preset.get("rate", {}).get("base_raw_rate", 56.0), 56.0)
    st.session_state["multiplier"] = safe_num(preset.get("rate", {}).get("multiplier", 3.6), 3.6)

    st.session_state["phase_split"] = preset.get("phase_split", {"SD":12.0,"DD":40.0,"CD":28.0,"Bidding":1.5,"CA":18.5})

    disc = preset.get("discipline_pct", {})
    st.session_state["electrical_pct"] = safe_num(disc.get("electrical", 28.0), 28.0)
    st.session_state["plumbing_fire_pct"] = safe_num(disc.get("plumbing_fire", 24.0), 24.0)
    st.session_state["mechanical_pct"] = safe_num(disc.get("mechanical", 48.0), 48.0)

    st.session_state["auto_balance"] = bool(preset.get("auto_balance", True))

    p_in = preset.get("plumbing_inputs", {})
    st.session_state["podium"] = bool(p_in.get("podium", True))
    st.session_state["lux_units"] = int(safe_num(p_in.get("lux_units", 8), 8))
    st.session_state["typ_units"] = int(safe_num(p_in.get("typ_units", 12), 12))
    st.session_state["dom_units"] = int(safe_num(p_in.get("dom_units", 25), 25))

    area_dict = preset.get("area_df", None)
    st.session_state["area_df"] = pd.DataFrame(area_dict) if area_dict else build_default_area_df()

    tasks = preset.get("tasks", {})
    if "electrical" in tasks:
        st.session_state["electrical_lib"] = pd.DataFrame(tasks["electrical"])
    if "plumbing" in tasks:
        st.session_state["plumbing_lib"] = pd.DataFrame(tasks["plumbing"])
    if "mechanical" in tasks:
        st.session_state["mechanical_lib"] = pd.DataFrame(tasks["mechanical"])

# =========================================================
# App
# =========================================================
st.set_page_config(page_title="MEP Fee and Work Plan Generator", layout="wide")
st.title("MEP Fee and Work Plan Generator")

# Initialize state
if "area_df" not in st.session_state:
    st.session_state["area_df"] = build_default_area_df()
if "electrical_lib" not in st.session_state:
    st.session_state["electrical_lib"] = electrical_defaults_df()
if "plumbing_lib" not in st.session_state:
    st.session_state["plumbing_lib"] = plumbing_defaults_df()
if "mechanical_lib" not in st.session_state:
    st.session_state["mechanical_lib"] = mechanical_defaults_df()

if "phase_split" not in st.session_state:
    st.session_state["phase_split"] = {"SD":12.0,"DD":40.0,"CD":28.0,"Bidding":1.5,"CA":18.5}
if "electrical_pct" not in st.session_state:
    st.session_state["electrical_pct"] = 28.0
if "plumbing_fire_pct" not in st.session_state:
    st.session_state["plumbing_fire_pct"] = 24.0
if "mechanical_pct" not in st.session_state:
    st.session_state["mechanical_pct"] = 48.0
if "auto_balance" not in st.session_state:
    st.session_state["auto_balance"] = True

if "base_raw_rate" not in st.session_state:
    st.session_state["base_raw_rate"] = 56.0
if "multiplier" not in st.session_state:
    st.session_state["multiplier"] = 3.6

if "podium" not in st.session_state:
    st.session_state["podium"] = True
if "lux_units" not in st.session_state:
    st.session_state["lux_units"] = 8
if "typ_units" not in st.session_state:
    st.session_state["typ_units"] = 12
if "dom_units" not in st.session_state:
    st.session_state["dom_units"] = 25

# Sidebar
with st.sidebar:
    st.header("Presets")
    up = st.file_uploader("Load preset (JSON)", type=["json"])
    if up is not None:
        try:
            load_preset_from_json(up.read().decode("utf-8"))
            st.success("Preset loaded.")
            st.rerun()
        except Exception as e:
            st.error(f"Could not load preset: {e}")

    st.download_button(
        "Save preset (JSON)",
        data=export_preset(),
        file_name="mep_fee_workplan_preset.json",
        mime="application/json",
    )

    st.divider()
    st.header("Rate Inputs")
    st.session_state["base_raw_rate"] = st.number_input(
        "Base Raw Rate ($/hr)", min_value=0.0, value=float(st.session_state["base_raw_rate"]), step=1.0
    )
    st.session_state["multiplier"] = st.number_input(
        "Multiplier", min_value=0.0, value=float(st.session_state["multiplier"]), step=0.1, format="%.2f"
    )

billing_rate = float(st.session_state["base_raw_rate"]) * float(st.session_state["multiplier"])

# Phase split
st.subheader("Design Phase Fee % Split")
p1, p2, p3, p4, p5 = st.columns(5)
ps = st.session_state["phase_split"]
ps["SD"] = p1.number_input("SD (%)", min_value=0.0, value=float(ps.get("SD", 12.0)), step=0.5, format="%.1f")
ps["DD"] = p2.number_input("DD (%)", min_value=0.0, value=float(ps.get("DD", 40.0)), step=0.5, format="%.1f")
ps["CD"] = p3.number_input("CD (%)", min_value=0.0, value=float(ps.get("CD", 28.0)), step=0.5, format="%.1f")
ps["Bidding"] = p4.number_input("Bidding (%)", min_value=0.0, value=float(ps.get("Bidding", 1.5)), step=0.1, format="%.1f")
ps["CA"] = p5.number_input("CA (%)", min_value=0.0, value=float(ps.get("CA", 18.5)), step=0.5, format="%.1f")
st.session_state["phase_split"] = ps
st.caption("Phase split auto-normalizes to 100% if entries don’t add to 100.")

# Discipline splits
st.subheader("Discipline % of MEP Fee")
d1, d2, d3, d4 = st.columns([1, 1, 1, 1.2])

with d4:
    st.session_state["auto_balance"] = st.checkbox("Auto-balance to 100%", value=bool(st.session_state["auto_balance"]))

with d1:
    st.session_state["electrical_pct"] = st.number_input("Electrical (%)", min_value=0.0, value=float(st.session_state["electrical_pct"]), step=0.5, format="%.1f")
with d2:
    st.session_state["plumbing_fire_pct"] = st.number_input("Plumbing / Fire (%)", min_value=0.0, value=float(st.session_state["plumbing_fire_pct"]), step=0.5, format="%.1f")

if st.session_state["auto_balance"]:
    remainder = max(0.0, 100.0 - float(st.session_state["electrical_pct"]) - float(st.session_state["plumbing_fire_pct"]))
    st.session_state["mechanical_pct"] = remainder
    with d3:
        st.number_input("Mechanical (%)", min_value=0.0, value=float(remainder), step=0.5, format="%.1f", disabled=True)
else:
    with d3:
        st.session_state["mechanical_pct"] = st.number_input("Mechanical (%)", min_value=0.0, value=float(st.session_state["mechanical_pct"]), step=0.5, format="%.1f")

# Fee summary
st.subheader("Design Fee Summary")

# =========================================================
# Area-Based Fee Calculator (Auto-update + styled preview)
# =========================================================
st.markdown("#### Area-Based Fee Calculator (Drives MEP Fee)")
c1, c2, c3 = st.columns([1, 1, 2])

def _area_editor_changed():
    df_cur = st.session_state["area_editor"]
    df_new, _ = recalc_area_df(df_cur)
    st.session_state["area_df"] = df_new

with c1:
    if st.button("➕ Add Row"):
        st.session_state["area_df"] = pd.concat(
            [st.session_state["area_df"], pd.DataFrame([new_space_row(space_type=SPACE_TYPES[0])])],
            ignore_index=True,
        )
        st.session_state["area_df"], _ = recalc_area_df(st.session_state["area_df"])

with c2:
    if st.button("🗑️ Delete Checked Rows"):
        df_del = st.session_state["area_df"].copy()
        df_del = df_del[df_del["Delete?"] != True].reset_index(drop=True)
        st.session_state["area_df"], _ = recalc_area_df(df_del)

with c3:
    st.caption("Inputs are tinted green in the preview below. Calculated cells are gray. Red borders = missing required inputs.")

# Always recalc before rendering editor
st.session_state["area_df"], missing_defaults = recalc_area_df(st.session_state["area_df"])

edited = st.data_editor(
    st.session_state["area_df"],
    use_container_width=True,
    hide_index=True,
    key="area_editor",
    on_change=_area_editor_changed,
    column_config={
        "Delete?": st.column_config.CheckboxColumn(width="small"),
        "Override $/SF?": st.column_config.CheckboxColumn(width="small"),
        "Space Name": st.column_config.TextColumn(width="medium"),
        "Space Type": st.column_config.SelectboxColumn(options=SPACE_TYPES, width="medium"),
        "Area (SF)": st.column_config.NumberColumn(min_value=0, step=1, format="%d", width="small"),
        "$/SF": st.column_config.NumberColumn(min_value=0.0, step=0.05, format="%.2f", width="small"),
        "Total Cost": st.column_config.NumberColumn(format="%.0f", disabled=True, width="small"),
        "Notes": st.column_config.TextColumn(width="large"),
    },
)

# Recalc after edit (ensures immediate consistency)
st.session_state["area_df"], missing_defaults = recalc_area_df(edited)

area_mep_fee = float(st.session_state["area_df"]["Total Cost"].sum())
st.markdown(f"**Area-Based MEP Fee:** {money(area_mep_fee)}")

if missing_defaults:
    st.warning(
        "Some Space Types require override because no default $/SF exists: "
        + ", ".join(sorted(set(missing_defaults)))
    )

st.markdown("##### Styled Preview (Read Only)")
st.dataframe(style_preview(st.session_state["area_df"]), use_container_width=True)

# =========================================================
# Fee split results (uses area_mep_fee)
# =========================================================
electrical_target_fee = area_mep_fee * (float(st.session_state["electrical_pct"]) / 100.0)
plumbing_fire_target_fee = area_mep_fee * (float(st.session_state["plumbing_fire_pct"]) / 100.0)
mechanical_target_fee = area_mep_fee * (float(st.session_state["mechanical_pct"]) / 100.0)

fire_fee = plumbing_fire_target_fee * 0.10
plumbing_fee = plumbing_fire_target_fee - fire_fee

s1, s2, s3, s4, s5 = st.columns(5)
with s1:
    st.markdown("**MEP Fee (Area-Based)**"); st.write(money(area_mep_fee))
with s2:
    st.markdown(f"**Electrical ({st.session_state['electrical_pct']:.1f}%)**"); st.write(money(electrical_target_fee))
with s3:
    st.markdown(f"**Plumbing/Fire ({st.session_state['plumbing_fire_pct']:.1f}%)**"); st.write(money(plumbing_fire_target_fee))
with s4:
    st.markdown("**Fire Protection (10% of P/F)**"); st.write(money(fire_fee))
with s5:
    st.markdown(f"**Mechanical ({st.session_state['mechanical_pct']:.1f}%)**"); st.write(money(mechanical_target_fee))

st.write(f"**Billing Rate Used:** {money(billing_rate)}/hr (Base {money(st.session_state['base_raw_rate'])}/hr × {st.session_state['multiplier']:.2f})")

# =========================================================
# Work Plan Generator
# =========================================================
st.divider()
st.subheader("Work Plan Generator")

e_df = build_plan_from_library(st.session_state["electrical_lib"], electrical_target_fee, billing_rate, st.session_state["phase_split"])
m_df = build_plan_from_library(st.session_state["mechanical_lib"], mechanical_target_fee, billing_rate, st.session_state["phase_split"])

col_e, col_pf, col_m = st.columns(3)

with col_e:
    st.subheader("Electrical")
    for ph in PHASES:
        d = e_df[e_df["Phase"] == ph]
        hrs = float(d["Hours"].sum())
        fee = float(d["Fee ($)"].sum())
        with st.expander(f"{ph} — {hrs:,.1f} hrs | {money(fee)}", expanded=False):
            show = d[["Task", "Hours", "Fee ($)"]].copy()
            show["Fee ($)"] = show["Fee ($)"].apply(lambda v: money(float(v)))
            st.dataframe(show, use_container_width=True, hide_index=True)
    st.divider()
    st.markdown(f"### ELECTRICAL TOTAL\n**{float(e_df['Hours'].sum()):,.1f} hrs** | **{money(float(e_df['Fee ($)'].sum()))}**")

with col_pf:
    st.subheader("Plumbing / Fire")
    st.caption("Inputs")
    pi1, pi2, pi3, pi4 = st.columns([1.1, 1, 1, 1])
    with pi1:
        st.session_state["podium"] = st.checkbox("Include Podium", value=bool(st.session_state["podium"]))
    with pi2:
        st.caption("Luxury units")
        st.session_state["lux_units"] = st.number_input("", min_value=0, value=int(st.session_state["lux_units"]), step=1, label_visibility="collapsed")
    with pi3:
        st.caption("Typical units")
        st.session_state["typ_units"] = st.number_input("", min_value=0, value=int(st.session_state["typ_units"]), step=1, label_visibility="collapsed")
    with pi4:
        st.caption("Domestic units")
        st.session_state["dom_units"] = st.number_input("", min_value=0, value=int(st.session_state["dom_units"]), step=1, label_visibility="collapsed")

    p_base_df = build_plumbing_task_df_from_library(
        st.session_state["plumbing_lib"],
        podium=bool(st.session_state["podium"]),
        lux_units=int(st.session_state["lux_units"]),
        typ_units=int(st.session_state["typ_units"]),
        dom_units=int(st.session_state["dom_units"]),
    )

    p_df = build_plan_from_library(p_base_df, plumbing_fee, billing_rate, st.session_state["phase_split"])
    fire_lib = pd.DataFrame([{"Phase": ph, "Task": "Fire Protection", "BaseHours": 1.0, "Enabled": True} for ph in PHASES])
    f_df = build_plan_from_library(fire_lib, fire_fee, billing_rate, st.session_state["phase_split"])
    pf_df = pd.concat([p_df, f_df], ignore_index=True)

    for ph in PHASES:
        d = pf_df[pf_df["Phase"] == ph]
        hrs = float(d["Hours"].sum())
        fee = float(d["Fee ($)"].sum())
        with st.expander(f"{ph} — {hrs:,.1f} hrs | {money(fee)}", expanded=False):
            show = d[["Task", "Hours", "Fee ($)"]].copy()
            show["Fee ($)"] = show["Fee ($)"].apply(lambda v: money(float(v)))
            st.dataframe(show, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown(f"### PLUMBING / FIRE TOTAL\n**{float(pf_df['Hours'].sum()):,.1f} hrs** | **{money(float(pf_df['Fee ($)'].sum()))}**")

with col_m:
    st.subheader("Mechanical")
    for ph in PHASES:
        d = m_df[m_df["Phase"] == ph]
        hrs = float(d["Hours"].sum())
        fee = float(d["Fee ($)"].sum())
        with st.expander(f"{ph} — {hrs:,.1f} hrs | {money(fee)}", expanded=False):
            show = d[["Task", "Hours", "Fee ($)"]].copy()
            show["Fee ($)"] = show["Fee ($)"].apply(lambda v: money(float(v)))
            st.dataframe(show, use_container_width=True, hide_index=True)
    st.divider()
    st.markdown(f"### MECHANICAL TOTAL\n**{float(m_df['Hours'].sum()):,.1f} hrs** | **{money(float(m_df['Fee ($)'].sum()))}**")
