import json
import re
import streamlit as st
import pandas as pd

# =========================================================
# Helpers
# =========================================================
PHASES = ["SD", "DD", "CD", "Bidding", "CA"]

def money(x: float) -> str:
    return f"${x:,.0f}"

def normalize(weights: dict) -> dict:
    total = sum(max(v, 0.0) for v in weights.values())
    if total <= 0:
        n = len(weights)
        return {k: 1.0 / n for k in weights}
    return {k: max(v, 0.0) / total for k, v in weights.items()}

def parse_currency(text: str) -> float:
    digits = re.sub(r"[^\d]", "", text or "")
    if digits == "":
        raise ValueError("No digits found")
    return float(digits)

def safe_num(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

def build_plan_from_library(task_df: pd.DataFrame, target_fee: float, rate: float, phase_split: dict) -> pd.DataFrame:
    """
    task_df columns required: Phase, Task, BaseHours, Enabled
    Uses BaseHours as weights within each phase, and scales to match phase fee.
    """
    phase_split_n = normalize(phase_split)
    df = task_df.copy()

    # Filter enabled only
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
# $/SF Lookup + Complexity
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
    # Typically override:
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

COMPLEXITY = {
    "Low": 0.85,
    "Standard": 1.00,
    "High": 1.15,
}

def new_space_row(space_type=None, space_name="", area=0, mult=1.0, complexity="Standard"):
    if space_type is None:
        space_type = SPACE_TYPES[0]
    return {
        "Delete?": False,
        "Override $/SF?": False,
        "Space Name": space_name,
        "Space Type": space_type,
        "Area (SF)": int(area),
        "Complexity": complexity,
        "$/SF": 0.0,
        "Multiplier": float(mult),
        "Total Cost": 0.0,
        "Notes": "",
    }

def build_default_area_df():
    # Different example space types (as requested)
    examples = [
        ("Amenity Areas", "Amenities", 18000, 1.00, "Standard"),
        ("BOH Rooms", "Back of House", 14000, 1.00, "Standard"),
        ("Retail (Core & Shell Restaurant)", "Retail", 5000, 1.00, "High"),
        ("Office (Core & Shell)", "Office", 4500, 1.00, "Standard"),
        ("Parking (Enclosed)", "Parking", 80000, 1.00, "Low"),
        ("Multifamily (High Rise)", "Residential", 175000, 1.00, "Standard"),
        ("Restaurant (Kitchen / Dining Areas)", "Restaurant", 3000, 1.00, "High"),
        ("Site Lighting", "Site Lighting (override)", 0, 1.00, "Standard"),
    ]
    return pd.DataFrame([new_space_row(t, n, a, m, cx) for t, n, a, m, cx in examples])

# =========================================================
# Default Task Libraries (Editable)
# =========================================================
def electrical_defaults_df():
    tasks = [
        # SD
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

        # DD
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

        # CD (+ permitting in CD)
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

        # Bidding
        ("Bidding","Contractor RFIs",16),
        ("Bidding","Addenda",14),
        ("Bidding","VE reviews",8),
        ("Bidding","Bid evaluation support",8),

        # CA
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

# Plumbing is editable too, including Tags for dynamic hours.
PLUMBING_TAGS = ["", "lux_units_4hr", "typ_units_4hr", "dom_units_2hr", "podium_only"]

def plumbing_defaults_df():
    # For tagged rows:
    # - lux_units_4hr / typ_units_4hr: BaseHours = hours per unit (default 4)
    # - dom_units_2hr: BaseHours = hours per unit (default 2)
    # - podium_only: BaseHours = hours used if podium included (default as shown)
    tasks = [
        # SD
        ("SD","SAN/VENT - Initial Sizing",3,""),
        ("SD","SAN/VENT - Civil Coordination",9,""),
        ("SD","SAN/VENT - Luxury Amenity",9,""),
        ("SD","SAN/VENT - Luxury Units (hr/unit)",4,"lux_units_4hr"),
        ("SD","SAN/VENT - Typical Units (hr/unit)",4,"typ_units_4hr"),
        ("SD","STORM - Main Roof Sizing",18,""),
        ("SD","STORM - Podium Sizing",9,"podium_only"),
        ("SD","Domestic - Initial Sizing",4,""),
        ("SD","Domestic - Pump Sizing",4,""),

        # DD
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

        # CD
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

        # Bidding / CA
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

# =========================================================
# Plumbing plan builder (from editable library with tags)
# =========================================================
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
            # base is podium hours
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
# Preset Save/Load
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
        "scope_toggles": st.session_state.get("scope_toggles", {}),
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

    st.session_state["scope_toggles"] = preset.get("scope_toggles", {})

    area_dict = preset.get("area_df", None)
    if area_dict:
        st.session_state["area_df"] = pd.DataFrame(area_dict)
    else:
        st.session_state["area_df"] = build_default_area_df()

    tasks = preset.get("tasks", {})
    if "electrical" in tasks:
        st.session_state["electrical_lib"] = pd.DataFrame(tasks["electrical"])
    if "plumbing" in tasks:
        st.session_state["plumbing_lib"] = pd.DataFrame(tasks["plumbing"])
    if "mechanical" in tasks:
        st.session_state["mechanical_lib"] = pd.DataFrame(tasks["mechanical"])

# =========================================================
# Scope Toggles (quick group switches)
# =========================================================
ELECTRICAL_GROUPS = {
    "Include EV Charging tasks": ["EV charging"],
    "Include Emergency / Life Safety tasks": ["Emergency / life safety", "Life safety"],
    "Include Permitting / AHJ tasks": ["Permit", "Plan check", "AHJ", "Comment responses", "Drawing revisions (permit"],
}

MECH_GROUPS = {
    "Include Unit modeling tasks": ["Unit modeling"],
    "Include Amenity modeling tasks": ["Amenity space modeling"],
    "Include QA/QC tasks": ["QA/QC"],
}

PLUMB_GROUPS = {
    "Include Grease/Derm tasks": ["Derm Grease", "Grease"],
    "Include Garage Drainage tasks": ["Garage Drainage"],
}

def apply_scope_toggles_to_lib(lib_df: pd.DataFrame, groups: dict, toggles_state: dict) -> pd.DataFrame:
    """
    If a toggle is False, disable tasks containing those keywords.
    If True, enable tasks containing those keywords (doesn't override manual disables outside group keywords).
    """
    df = lib_df.copy()
    if "Enabled" not in df.columns:
        df["Enabled"] = True

    for toggle_name, keywords in groups.items():
        on = bool(toggles_state.get(toggle_name, True))
        mask = False
        for kw in keywords:
            mask = mask | df["Task"].astype(str).str.contains(kw, case=False, regex=False)
        if not on:
            df.loc[mask, "Enabled"] = False
        else:
            # only re-enable those tasks if user hasn't explicitly disabled them via editor?
            # We'll re-enable to match toggle intent.
            df.loc[mask, "Enabled"] = True

    return df

# =========================================================
# App
# =========================================================
st.set_page_config(page_title="MEP Fee and Work Plan Generator", layout="wide")
st.title("MEP Fee and Work Plan Generator")

# ---------- Initialize state ----------
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

if "scope_toggles" not in st.session_state:
    # default everything ON
    st.session_state["scope_toggles"] = {
        **{k: True for k in ELECTRICAL_GROUPS.keys()},
        **{k: True for k in PLUMB_GROUPS.keys()},
        **{k: True for k in MECH_GROUPS.keys()},
    }

# ---------- Sidebar: Presets + Rates ----------
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
    st.session_state["base_raw_rate"] = st.number_input("Base Raw Rate ($/hr)", min_value=0.0, value=float(st.session_state["base_raw_rate"]), step=1.0)
    st.session_state["multiplier"] = st.number_input("Multiplier", min_value=0.0, value=float(st.session_state["multiplier"]), step=0.1, format="%.2f")

billing_rate = float(st.session_state["base_raw_rate"]) * float(st.session_state["multiplier"])

# ---------- Phase Split ----------
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

# ---------- Discipline Split + Auto-balance ----------
st.subheader("Discipline % of MEP Fee")
d1, d2, d3, d4 = st.columns([1, 1, 1, 1.2])

with d4:
    st.session_state["auto_balance"] = st.checkbox("Auto-balance to 100%", value=bool(st.session_state["auto_balance"]))

with d1:
    st.session_state["electrical_pct"] = st.number_input("Electrical (%)", min_value=0.0, value=float(st.session_state["electrical_pct"]), step=0.5, format="%.1f")
with d2:
    st.session_state["plumbing_fire_pct"] = st.number_input("Plumbing / Fire (%)", min_value=0.0, value=float(st.session_state["plumbing_fire_pct"]), step=0.5, format="%.1f")

# Mechanical percent is either remainder (auto) or editable
if st.session_state["auto_balance"]:
    remainder = max(0.0, 100.0 - float(st.session_state["electrical_pct"]) - float(st.session_state["plumbing_fire_pct"]))
    st.session_state["mechanical_pct"] = remainder
    with d3:
        st.number_input("Mechanical (%)", min_value=0.0, value=float(remainder), step=0.5, format="%.1f", disabled=True)
else:
    with d3:
        st.session_state["mechanical_pct"] = st.number_input("Mechanical (%)", min_value=0.0, value=float(st.session_state["mechanical_pct"]), step=0.5, format="%.1f")

# ---------- Scope Toggles ----------
with st.expander("Scope Toggles (quick switches)"):
    st.caption("These switch related tasks on/off while keeping your detailed task library intact.")
    tcol1, tcol2, tcol3 = st.columns(3)

    with tcol1:
        st.markdown("**Electrical**")
        for k in ELECTRICAL_GROUPS.keys():
            st.session_state["scope_toggles"][k] = st.checkbox(k, value=bool(st.session_state["scope_toggles"].get(k, True)), key=f"tog_{k}")

    with tcol2:
        st.markdown("**Plumbing / Fire**")
        for k in PLUMB_GROUPS.keys():
            st.session_state["scope_toggles"][k] = st.checkbox(k, value=bool(st.session_state["scope_toggles"].get(k, True)), key=f"tog_{k}")

    with tcol3:
        st.markdown("**Mechanical**")
        for k in MECH_GROUPS.keys():
            st.session_state["scope_toggles"][k] = st.checkbox(k, value=bool(st.session_state["scope_toggles"].get(k, True)), key=f"tog_{k}")

# ---------- Compute area-based MEP fee (later, but we show summary first) ----------
st.subheader("Design Fee Summary")

# We'll compute area fee after area table; placeholder value:
area_mep_fee = 0.0

# ---------- Area Calculator under Fee Summary ----------
st.markdown("#### Area-Based Fee Calculator (Drives MEP Fee)")

c1, c2, c3 = st.columns([1, 1, 2])
with c1:
    if st.button("➕ Add Row"):
        st.session_state["area_df"] = pd.concat([st.session_state["area_df"], pd.DataFrame([new_space_row(space_type=SPACE_TYPES[min(1, len(SPACE_TYPES)-1)])])], ignore_index=True)
with c2:
    if st.button("🗑️ Delete Checked Rows"):
        df_del = st.session_state["area_df"].copy()
        df_del = df_del[df_del["Delete?"] != True].reset_index(drop=True)
        st.session_state["area_df"] = df_del
with c3:
    st.caption("Override $/SF? unchecked = lookup. Complexity multiplies that row’s total.")

# Pre-calc before editor (so it looks right immediately)
df = st.session_state["area_df"].copy()

for col in ["Area (SF)", "$/SF", "Multiplier"]:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

# --- Complexity column (robust for older presets / older session state) ---
if "Complexity" not in df.columns:
    df["Complexity"] = "Standard"
else:
    df["Complexity"] = df["Complexity"].fillna("Standard").astype(str)

df.loc[~df["Complexity"].isin(COMPLEXITY.keys()), "Complexity"] = "Standard"


missing_defaults = []
for i, row in df.iterrows():
    stype = row["Space Type"]
    override = bool(row["Override $/SF?"])
    lookup = RATE_LOOKUP.get(stype)
    if not override:
        if lookup is None:
            df.loc[i, "$/SF"] = 0.0
            missing_defaults.append(stype)
        else:
            df.loc[i, "$/SF"] = float(lookup)

df["Total Cost"] = df["Area (SF)"] * df["$/SF"] * df["Multiplier"] * df["Complexity"].map(COMPLEXITY)
st.session_state["area_df"] = df

edited = st.data_editor(
    st.session_state["area_df"],
    use_container_width=True,
    hide_index=True,
    column_config={
        "Delete?": st.column_config.CheckboxColumn(width="small"),
        "Override $/SF?": st.column_config.CheckboxColumn(width="small"),
        "Space Name": st.column_config.TextColumn(width="medium"),
        "Space Type": st.column_config.SelectboxColumn(options=SPACE_TYPES, width="medium"),
        "Area (SF)": st.column_config.NumberColumn(min_value=0, step=1, format="%d", width="small"),
        "Complexity": st.column_config.SelectboxColumn(options=list(COMPLEXITY.keys()), width="small"),
        "$/SF": st.column_config.NumberColumn(min_value=0.0, step=0.05, format="%.2f", width="small"),
        "Multiplier": st.column_config.NumberColumn(min_value=0.0, step=0.05, format="%.2f", width="small"),
        "Total Cost": st.column_config.NumberColumn(format="%.0f", disabled=True, width="small"),
        "Notes": st.column_config.TextColumn(width="large"),
    },
    key="area_editor",
)

# Re-apply lookup + recalc so overrides behave correctly
df2 = edited.copy()
for col in ["Area (SF)", "$/SF", "Multiplier"]:
    df2[col] = pd.to_numeric(df2[col], errors="coerce").fillna(0.0)

# --- Complexity column (robust for older presets / older session state) ---
if "Complexity" not in df2.columns:
    df2["Complexity"] = "Standard"
else:
    df2["Complexity"] = df2["Complexity"].fillna("Standard").astype(str)

df2.loc[~df2["Complexity"].isin(COMPLEXITY.keys()), "Complexity"] = "Standard"


missing_defaults = []
for i, row in df2.iterrows():
    stype = row["Space Type"]
    override = bool(row["Override $/SF?"])
    lookup = RATE_LOOKUP.get(stype)
    if not override:
        if lookup is None:
            df2.loc[i, "$/SF"] = 0.0
            missing_defaults.append(stype)
        else:
            df2.loc[i, "$/SF"] = float(lookup)

df2["Total Cost"] = df2["Area (SF)"] * df2["$/SF"] * df2["Multiplier"] * df2["Complexity"].map(COMPLEXITY)
st.session_state["area_df"] = df2

area_mep_fee = float(df2["Total Cost"].sum())
st.markdown(f"**Area-Based MEP Fee:** {money(area_mep_fee)}")

if missing_defaults:
    st.warning(
        "Some Space Types require override because no default $/SF exists: "
        + ", ".join(sorted(set(missing_defaults)))
    )

with st.expander("View $/SF Lookup Table"):
    lookup_df = pd.DataFrame([{"Space Type": k, "$/SF": ("" if v is None else v)} for k, v in RATE_LOOKUP.items()])
    st.dataframe(lookup_df, use_container_width=True, hide_index=True)

# ---------- Summary numbers (now that MEP fee is known) ----------
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
# Editable Task Libraries (disable-only)
# =========================================================
with st.expander("Edit Task Libraries (disable-only, detailed)"):
    tabs = st.tabs(["Electrical Tasks", "Plumbing/Fire Tasks", "Mechanical Tasks"])

    # Electrical
    with tabs[0]:
        st.caption("You can disable tasks or adjust BaseHours (weights). Totals will still match fee targets.")
        elec_lib = st.session_state["electrical_lib"].copy()
        # Apply scope toggles to reflect quick switches
        elec_lib = apply_scope_toggles_to_lib(elec_lib, ELECTRICAL_GROUPS, st.session_state["scope_toggles"])

        edited_e = st.data_editor(
            elec_lib,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config={
                "Phase": st.column_config.SelectboxColumn(options=PHASES, width="small"),
                "Task": st.column_config.TextColumn(width="large"),
                "BaseHours": st.column_config.NumberColumn(min_value=0.0, step=1.0, format="%.1f", width="small"),
                "Enabled": st.column_config.CheckboxColumn(width="small"),
            },
            key="edit_electrical_lib",
        )
        st.session_state["electrical_lib"] = edited_e

    # Plumbing
    with tabs[1]:
        st.caption("Plumbing supports tags for dynamic rows (units/podium). Disable tasks or adjust BaseHours.")
        st.caption("Tags: lux_units_4hr, typ_units_4hr, dom_units_2hr, podium_only (leave blank for fixed hours).")

        pl_lib = st.session_state["plumbing_lib"].copy()
        pl_lib = apply_scope_toggles_to_lib(pl_lib, PLUMB_GROUPS, st.session_state["scope_toggles"])

        edited_p = st.data_editor(
            pl_lib,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config={
                "Phase": st.column_config.SelectboxColumn(options=PHASES, width="small"),
                "Task": st.column_config.TextColumn(width="large"),
                "BaseHours": st.column_config.NumberColumn(min_value=0.0, step=1.0, format="%.1f", width="small"),
                "Tag": st.column_config.SelectboxColumn(options=PLUMBING_TAGS, width="small"),
                "Enabled": st.column_config.CheckboxColumn(width="small"),
            },
            key="edit_plumbing_lib",
        )
        st.session_state["plumbing_lib"] = edited_p

    # Mechanical
    with tabs[2]:
        st.caption("Mechanical: disable tasks or adjust BaseHours (weights).")
        mech_lib = st.session_state["mechanical_lib"].copy()
        mech_lib = apply_scope_toggles_to_lib(mech_lib, MECH_GROUPS, st.session_state["scope_toggles"])

        edited_m = st.data_editor(
            mech_lib,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config={
                "Phase": st.column_config.SelectboxColumn(options=PHASES, width="small"),
                "Task": st.column_config.TextColumn(width="large"),
                "BaseHours": st.column_config.NumberColumn(min_value=0.0, step=1.0, format="%.1f", width="small"),
                "Enabled": st.column_config.CheckboxColumn(width="small"),
            },
            key="edit_mechanical_lib",
        )
        st.session_state["mechanical_lib"] = edited_m

# =========================================================
# Work Plans
# =========================================================
st.divider()
st.subheader("Work Plan Generator")

# Plumbing inputs (compact, under section)
col_e, col_pf, col_m = st.columns(3)

# Build Electrical plan
elec_lib_effective = apply_scope_toggles_to_lib(st.session_state["electrical_lib"], ELECTRICAL_GROUPS, st.session_state["scope_toggles"])
e_df = build_plan_from_library(elec_lib_effective, electrical_target_fee, billing_rate, st.session_state["phase_split"])

# Build Mechanical plan
mech_lib_effective = apply_scope_toggles_to_lib(st.session_state["mechanical_lib"], MECH_GROUPS, st.session_state["scope_toggles"])
m_df = build_plan_from_library(mech_lib_effective, mechanical_target_fee, billing_rate, st.session_state["phase_split"])

with col_e:
    st.subheader("Electrical")
    for ph in PHASES:
        d = e_df[e_df["Phase"] == ph].copy()
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

    # Plumbing inputs (persisted for presets)
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

    # Plumbing library -> computed base hours with tags
    pl_lib_effective = apply_scope_toggles_to_lib(st.session_state["plumbing_lib"], PLUMB_GROUPS, st.session_state["scope_toggles"])
    p_base_df = build_plumbing_task_df_from_library(
        pl_lib_effective,
        podium=bool(st.session_state["podium"]),
        lux_units=int(st.session_state["lux_units"]),
        typ_units=int(st.session_state["typ_units"]),
        dom_units=int(st.session_state["dom_units"]),
    )

    # Scale Plumbing (90% of P/F) + Fire (10% of P/F)
    p_df = build_plan_from_library(p_base_df, plumbing_fee, billing_rate, st.session_state["phase_split"])

    fire_lib = pd.DataFrame([{"Phase": ph, "Task": "Fire Protection", "BaseHours": 1.0, "Enabled": True} for ph in PHASES])
    f_df = build_plan_from_library(fire_lib, fire_fee, billing_rate, st.session_state["phase_split"])

    pf_df = pd.concat([p_df, f_df], ignore_index=True)

    for ph in PHASES:
        d = pf_df[pf_df["Phase"] == ph].copy()
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
        d = m_df[m_df["Phase"] == ph].copy()
        hrs = float(d["Hours"].sum())
        fee = float(d["Fee ($)"].sum())
        with st.expander(f"{ph} — {hrs:,.1f} hrs | {money(fee)}", expanded=False):
            show = d[["Task", "Hours", "Fee ($)"]].copy()
            show["Fee ($)"] = show["Fee ($)"].apply(lambda v: money(float(v)))
            st.dataframe(show, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown(f"### MECHANICAL TOTAL\n**{float(m_df['Hours'].sum()):,.1f} hrs** | **{money(float(m_df['Fee ($)'].sum()))}**")

# =========================================================
# Exports + Assumptions
# =========================================================
st.divider()
st.subheader("Exports")

# Combined export
combined = pd.concat([
    e_df.assign(Discipline="Electrical"),
    pf_df.assign(Discipline="Plumbing/Fire"),
    m_df.assign(Discipline="Mechanical"),
], ignore_index=True)[["Discipline", "Phase", "Task", "Hours", "Fee ($)"]]

st.download_button(
    "Download Combined Work Plan CSV",
    data=combined.to_csv(index=False),
    file_name="mep_work_plan_combined.csv",
    mime="text/csv",
)

cA, cB, cC = st.columns(3)
with cA:
    st.download_button("Download Electrical CSV", data=e_df.to_csv(index=False), file_name="electrical_work_plan.csv", mime="text/csv")
with cB:
    st.download_button("Download Plumbing/Fire CSV", data=pf_df.to_csv(index=False), file_name="plumbing_fire_work_plan.csv", mime="text/csv")
with cC:
    st.download_button("Download Mechanical CSV", data=m_df.to_csv(index=False), file_name="mechanical_work_plan.csv", mime="text/csv")

with st.expander("Assumptions Used"):
    st.write(f"- MEP Fee Source: **Area-Based Calculator** = {money(area_mep_fee)}")
    st.write(f"- Billing Rate: **{money(billing_rate)}/hr** (Base {money(st.session_state['base_raw_rate'])}/hr × {st.session_state['multiplier']:.2f})")
    st.write(f"- Phase Split (normalized internally): {st.session_state['phase_split']}")
    st.write(f"- Discipline %: Electrical {st.session_state['electrical_pct']:.1f}%, Plumbing/Fire {st.session_state['plumbing_fire_pct']:.1f}%, Mechanical {st.session_state['mechanical_pct']:.1f}%")
    st.write(f"- Plumbing/Fire carveout: Fire Protection = 10% of Plumbing/Fire fee")
    st.write(f"- Plumbing Inputs: Podium={st.session_state['podium']}, Luxury units={st.session_state['lux_units']}, Typical units={st.session_state['typ_units']}, Domestic units={st.session_state['dom_units']}")

