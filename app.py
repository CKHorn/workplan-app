# ============================================================
# MEP Fee and Work Plan Generator
# Original full app + Toggles directly affecting task hours
# (WEIGHTS MODEL: toggles remove tasks from the weight pool)
# ============================================================

import streamlit as st
import pandas as pd

PHASES = ["SD", "DD", "CD", "Bidding", "CA"]

# ============================================================
# Helpers
# ============================================================
def money(x: float) -> str:
    return f"${x:,.0f}"

def pct(x: float) -> str:
    return f"{x*100:,.2f}%"

def normalize_pct_dict(d: dict) -> dict:
    # Input values are percents; output is fractions summing to 1
    vals = {k: max(float(d.get(k, 0.0)), 0.0) for k in d}
    total = sum(vals.values())
    if total <= 0:
        n = len(vals)
        return {k: 1.0 / n for k in vals}
    return {k: v / total for k, v in vals.items()}

def total_pct_badge(total_pct, label="Total %"):
    ok = abs(float(total_pct) - 100.0) < 0.01
    bg = "#16a34a" if ok else "#dc2626"  # green / red
    return f"""
    <div style="
        padding:10px 12px;
        border-radius:10px;
        color:white;
        font-weight:700;
        display:inline-block;
        background:{bg};
        min-width:140px;
        text-align:center;">
        {label}: {total_pct:,.1f}%
    </div>
    """

def parse_tags(tag_str) -> set:
    if tag_str is None:
        return set()
    return {t.strip().lower() for t in str(tag_str).split(",") if t.strip()}

def apply_toggles_to_tasks(task_df: pd.DataFrame, toggle_map: dict) -> pd.DataFrame:
    """
    Toggle model that directly affects hours:
    - Task participates ONLY if Enabled == True AND none of its tags are toggled OFF.
    """
    df = task_df.copy()
    if "Enabled" not in df.columns:
        df["Enabled"] = True
    if "Tags" not in df.columns:
        df["Tags"] = ""

    df["Enabled"] = df["Enabled"].astype(bool)
    df["Tags"] = df["Tags"].fillna("").astype(str)

    def active(row) -> bool:
        if not bool(row["Enabled"]):
            return False
        tags = parse_tags(row["Tags"])
        for tag, is_on in toggle_map.items():
            if tag in tags and (is_on is False):
                return False
        return True

    df["__active__"] = df.apply(active, axis=1)
    df = df[df["__active__"]].drop(columns=["__active__"])
    return df

def build_plan_from_library(task_df: pd.DataFrame, target_fee: float, billing_rate: float, phase_split_pct: dict) -> pd.DataFrame:
    """
    WEIGHTS MODEL:
    - Phase fee fixed by phase split
    - Tasks in phase share hours proportional to BaseHours
    - If toggles remove tasks, weights re-normalize automatically
    """
    phase_frac = normalize_pct_dict(phase_split_pct)

    df = task_df.copy()
    if df.empty:
        return pd.DataFrame([{"Phase": "SD", "Task": "No tasks enabled", "Hours": 0.0, "Fee ($)": 0.0}])

    df["BaseHours"] = pd.to_numeric(df["BaseHours"], errors="coerce").fillna(0.0)

    out_rows = []
    for ph in PHASES:
        frac = phase_frac.get(ph, 0.0)
        phase_fee = float(target_fee) * float(frac)
        phase_hours = (phase_fee / billing_rate) if billing_rate > 0 else 0.0

        p = df[df["Phase"] == ph].copy()
        if p.empty:
            continue

        w_sum = float(p["BaseHours"].sum())
        p["Hours"] = (p["BaseHours"] / w_sum) * phase_hours if w_sum > 0 else 0.0
        p["Fee ($)"] = p["Hours"] * billing_rate
        out_rows.append(p[["Phase", "Task", "Hours", "Fee ($)"]])

    if not out_rows:
        return pd.DataFrame([{"Phase": "SD", "Task": "No tasks enabled", "Hours": 0.0, "Fee ($)": 0.0}])

    out = pd.concat(out_rows, ignore_index=True)
    out["Hours"] = out["Hours"].round(1)
    out["Fee ($)"] = out["Fee ($)"].round(0)
    return out

# ============================================================
# Area $/SF Lookup
# ============================================================
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
    "BOH Rooms": 0.75,
    "Classroom": 1.50,
    "Bar / Lounge Areas": 1.25,
    "Amenity Areas": 1.25,
    "Manufacturing Light (Mainly Storage)": 0.95,
    "Manufacturing Complex (Process Equipment Etc.)": 1.50,
    "Site Lighting": None,
    "Site Parking": None,
}
SPACE_TYPES = list(RATE_LOOKUP.keys())

def new_space_row(space_type=None, name="", area=0):
    if space_type is None:
        space_type = SPACE_TYPES[0]
    return {
        "Delete?": False,
        "Override $/SF?": False,
        "Space Name": name,
        "Space Type": space_type,
        "Area (SF)": int(area),
        "Override $/SF Value": 0.0,
        "$/SF": 0.0,
        "Total Cost": 0.0,
    }

def recalc_area_df(df_in: pd.DataFrame) -> pd.DataFrame:
    df = df_in.copy()
    df["Area (SF)"] = pd.to_numeric(df["Area (SF)"], errors="coerce").fillna(0.0)
    df["Override $/SF Value"] = pd.to_numeric(df["Override $/SF Value"], errors="coerce").fillna(0.0)
    df["Override $/SF?"] = df["Override $/SF?"].astype(bool)

    for i, row in df.iterrows():
        stype = str(row.get("Space Type", ""))
        lookup = RATE_LOOKUP.get(stype)
        if bool(row.get("Override $/SF?", False)):
            df.loc[i, "$/SF"] = float(row.get("Override $/SF Value", 0.0))
        else:
            df.loc[i, "$/SF"] = 0.0 if lookup is None else float(lookup)

    df["Total Cost"] = df["Area (SF)"] * pd.to_numeric(df["$/SF"], errors="coerce").fillna(0.0)
    return df

# ============================================================
# Task Libraries (kept at same detail level as your “final”)
# Now with Tags so toggles can directly control task participation
# ============================================================
def electrical_defaults_df():
    tasks = [
        ("SD", "PM / Coordination", 30, "pm,coordination,meetings"),
        ("SD", "Design / Analysis", 70, "analysis,life_safety,power,lighting,ev,narrative"),
        ("DD", "PM / Coordination", 40, "pm,coordination,meetings"),
        ("DD", "Plans / Schedules", 120, "plans,schedules,power,lighting,panels_risers,ev,life_safety"),
        ("CD", "PM / QAQC", 50, "pm,qaqc,coordination,meetings"),
        ("CD", "Construction Documents", 180, "cd_docs,permitting,power,lighting,panels_risers,life_safety,ev"),
        ("Bidding", "Bidding Support", 10, "bidding"),
        ("CA", "Construction Administration", 120, "ca,coordination,meetings"),
    ]
    df = pd.DataFrame(tasks, columns=["Phase", "Task", "BaseHours", "Tags"])
    df["Enabled"] = True
    return df

def plumbing_defaults_df():
    tasks = [
        ("SD", "Sizing / Coordination", 80, "sanvent,coordination,meetings,podium"),
        ("DD", "Layouts / Coordination", 140, "sanvent,storm,domestic,coordination,meetings,podium"),
        ("CD", "Details / Isometrics", 200, "details,isometrics,sanvent,storm,domestic,garage,grease,permitting"),
        ("Bidding", "Bidding Support", 10, "bidding"),
        ("CA", "Construction Administration", 120, "ca,coordination,meetings"),
    ]
    df = pd.DataFrame(tasks, columns=["Phase", "Task", "BaseHours", "Tags"])
    df["Enabled"] = True
    return df

def mechanical_defaults_df():
    tasks = [
        ("SD", "Preliminary Design", 55, "ductwork,oa_calcs,ies_loads,coordination,meetings,narrative"),
        ("DD", "System Design / Modeling", 198, "ductwork,oa_calcs,ies_loads,chilled_water,condenser_water,refrigerant_piping,coordination,meetings"),
        ("CD", "Detailed Design", 134, "ductwork,chilled_water,condenser_water,refrigerant_piping,smoke_control,coordination,meetings,permitting,qaqc"),
        ("Bidding", "Bidding / CPS", 55, "bidding,coordination"),
        ("CA", "Construction Administration", 60, "ca,coordination,meetings"),
    ]
    df = pd.DataFrame(tasks, columns=["Phase", "Task", "BaseHours", "Tags"])
    df["Enabled"] = True
    return df

# ============================================================
# App Setup
# ============================================================
st.set_page_config(page_title="MEP Fee and Work Plan Generator", layout="wide")
st.title("MEP Fee and Work Plan Generator")

# ---------------- Session State Init ----------------
if "area_df" not in st.session_state:
    st.session_state.area_df = pd.DataFrame([
        new_space_row("Amenity Areas", "Amenities", 18000),
        new_space_row("BOH Rooms", "Back of House", 14000),
        new_space_row("Retail (Core & Shell Restaurant)", "Retail", 5000),
        new_space_row("Office (Core & Shell)", "Office", 4500),
        new_space_row("Parking (Enclosed)", "Parking", 80000),
        new_space_row("Multifamily (High Rise)", "Residential", 175000),
    ])

if "construction_cost_psf" not in st.session_state:
    st.session_state.construction_cost_psf = 300.0
if "arch_fee_pct" not in st.session_state:
    st.session_state.arch_fee_pct = 3.5

if "phase_split" not in st.session_state:
    st.session_state.phase_split = {"SD": 12.0, "DD": 40.0, "CD": 28.0, "Bidding": 1.5, "CA": 18.5}

if "electrical_pct" not in st.session_state:
    st.session_state.electrical_pct = 28.0
if "plumbing_pct" not in st.session_state:
    st.session_state.plumbing_pct = 24.0
if "mechanical_pct" not in st.session_state:
    st.session_state.mechanical_pct = 48.0

if "base_raw_rate" not in st.session_state:
    st.session_state.base_raw_rate = 56.0
if "multiplier" not in st.session_state:
    st.session_state.multiplier = 3.6

if "electrical_lib" not in st.session_state:
    st.session_state.electrical_lib = electrical_defaults_df()
if "plumbing_lib" not in st.session_state:
    st.session_state.plumbing_lib = plumbing_defaults_df()
if "mechanical_lib" not in st.session_state:
    st.session_state.mechanical_lib = mechanical_defaults_df()

# Sidebar rate inputs
with st.sidebar:
    st.header("Rate Inputs")
    st.session_state.base_raw_rate = st.number_input("Base Raw Rate ($/hr)", min_value=0.0, value=float(st.session_state.base_raw_rate), step=1.0)
    st.session_state.multiplier = st.number_input("Multiplier", min_value=0.0, value=float(st.session_state.multiplier), step=0.1, format="%.2f")

billing_rate = float(st.session_state.base_raw_rate) * float(st.session_state.multiplier)

# ============================================================
# Project Cost & Fee Context
# ============================================================
st.subheader("Project Cost & Fee Context")

st.session_state.area_df = recalc_area_df(st.session_state.area_df)
total_area = float(st.session_state.area_df["Area (SF)"].sum())

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(f"**Total Area**  \n{total_area:,.0f} SF")
with c2:
    st.session_state.construction_cost_psf = st.number_input("Construction Cost ($/SF)", value=float(st.session_state.construction_cost_psf), step=5.0)
with c3:
    st.session_state.arch_fee_pct = st.number_input("Arch Fee (%)", value=float(st.session_state.arch_fee_pct), step=0.1, format="%.2f")

construction_cost_total = total_area * float(st.session_state.construction_cost_psf)
arch_fee_total = construction_cost_total * (float(st.session_state.arch_fee_pct) / 100.0)
typical_mep_total = arch_fee_total * 0.15

st.markdown("##### Auto-Calculated Totals")
t1, t2, t3 = st.columns(3)
with t1:
    st.markdown("**Total Construction Cost**")
    st.write(money(construction_cost_total))
with t2:
    st.markdown("**Architectural Fee**")
    st.write(money(arch_fee_total))
with t3:
    st.markdown("**Typical MEP (15% of Arch Fee)**")
    st.write(money(typical_mep_total))

# ============================================================
# Design Phase Fee % Split (with Total % indicator)
# ============================================================
st.subheader("Design Phase Fee % Split")
pcols = st.columns([1, 1, 1, 1, 1, 0.9])
ps = st.session_state.phase_split

ps["SD"] = pcols[0].number_input("SD (%)", min_value=0.0, value=float(ps.get("SD", 0.0)), step=0.5, format="%.1f")
ps["DD"] = pcols[1].number_input("DD (%)", min_value=0.0, value=float(ps.get("DD", 0.0)), step=0.5, format="%.1f")
ps["CD"] = pcols[2].number_input("CD (%)", min_value=0.0, value=float(ps.get("CD", 0.0)), step=0.5, format="%.1f")
ps["Bidding"] = pcols[3].number_input("Bidding (%)", min_value=0.0, value=float(ps.get("Bidding", 0.0)), step=0.1, format="%.1f")
ps["CA"] = pcols[4].number_input("CA (%)", min_value=0.0, value=float(ps.get("CA", 0.0)), step=0.5, format="%.1f")

phase_total = float(ps["SD"] + ps["DD"] + ps["CD"] + ps["Bidding"] + ps["CA"])
with pcols[5]:
    st.markdown(total_pct_badge(phase_total, "Total %"), unsafe_allow_html=True)
st.session_state.phase_split = ps

# ============================================================
# Discipline % of MEP Fee (Total % indicator)
# ============================================================
st.subheader("Discipline % of MEP Fee")
dcols = st.columns([1, 1, 1, 0.9])
st.session_state.electrical_pct = dcols[0].number_input("Electrical (%)", min_value=0.0, value=float(st.session_state.electrical_pct), step=0.5, format="%.1f")
st.session_state.plumbing_pct = dcols[1].number_input("Plumbing / Fire (%)", min_value=0.0, value=float(st.session_state.plumbing_pct), step=0.5, format="%.1f")
st.session_state.mechanical_pct = dcols[2].number_input("Mechanical (%)", min_value=0.0, value=float(st.session_state.mechanical_pct), step=0.5, format="%.1f")

disc_total = float(st.session_state.electrical_pct + st.session_state.plumbing_pct + st.session_state.mechanical_pct)
with dcols[3]:
    st.markdown(total_pct_badge(disc_total, "Total %"), unsafe_allow_html=True)

# ============================================================
# Area-Based Fee Calculator
# ============================================================
st.subheader("Area-Based MEP Fee Calculator")

edited = st.data_editor(
    st.session_state.area_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Delete?": st.column_config.CheckboxColumn(),
        "Space Name": st.column_config.TextColumn(width="medium"),
        "Space Type": st.column_config.SelectboxColumn(options=SPACE_TYPES),
        "Area (SF)": st.column_config.NumberColumn(format="%d"),
        "Override $/SF?": st.column_config.CheckboxColumn(),
        "Override $/SF Value": st.column_config.NumberColumn(format="%.2f"),
        "$/SF": st.column_config.NumberColumn(disabled=True),
        "Total Cost": st.column_config.NumberColumn(disabled=True),
    }
)

edited = edited[edited["Delete?"] != True].reset_index(drop=True)
st.session_state.area_df = recalc_area_df(edited)

mep_fee = float(st.session_state.area_df["Total Cost"].sum())
mep_pct_of_arch = (mep_fee / arch_fee_total) if arch_fee_total > 0 else 0.0

s1, s2 = st.columns(2)
with s1:
    st.markdown("**MEP Fee (Area-Based)**")
    st.write(money(mep_fee))
with s2:
    st.markdown("**MEP % of Arch Fee**")
    st.write(pct(mep_pct_of_arch))

st.caption(f"Billing Rate Used: {money(billing_rate)}/hr (Base {money(st.session_state.base_raw_rate)}/hr × {st.session_state.multiplier:.2f})")

# ============================================================
# Scope Toggles (Directly affects task participation → hours)
# ============================================================
st.divider()
st.subheader("Scope Toggles (directly affects task hour breakdown)")

st.markdown("#### Common Toggles")
ct1, ct2, ct3, ct4, ct5, ct6 = st.columns(6)
include_pm = ct1.checkbox("PM", value=True)
include_qaqc = ct2.checkbox("QA/QC", value=True)
include_coord = ct3.checkbox("Coordination", value=True)
include_meetings = ct4.checkbox("Meetings", value=True)
include_narr = ct5.checkbox("Narrative", value=True)
include_permitting = ct6.checkbox("Permitting", value=True)

common_toggle_map = {
    "pm": include_pm,
    "qaqc": include_qaqc,
    "coordination": include_coord,
    "meetings": include_meetings,
    "narrative": include_narr,
    "permitting": include_permitting,
}

st.markdown("#### Electrical Toggles")
et1, et2, et3, et4, et5 = st.columns(5)
include_power = et1.checkbox("Power", value=True)
include_lighting = et2.checkbox("Lighting", value=True)
include_panels = et3.checkbox("Panels/Risers", value=True)
include_ev = et4.checkbox("EV", value=True)
include_lifesafety = et5.checkbox("Life Safety", value=True)

elec_toggle_map = {
    "power": include_power,
    "lighting": include_lighting,
    "panels_risers": include_panels,
    "ev": include_ev,
    "life_safety": include_lifesafety,
}

st.markdown("#### Plumbing / Fire Toggles")
pt1, pt2, pt3, pt4, pt5, pt6 = st.columns(6)
include_sanvent = pt1.checkbox("San/Vent", value=True)
include_storm = pt2.checkbox("Storm", value=True)
include_domestic = pt3.checkbox("Domestic", value=True)
include_garage = pt4.checkbox("Garage", value=True)
include_grease = pt5.checkbox("Grease", value=True)
include_podium = pt6.checkbox("Podium", value=True)

plumb_toggle_map = {
    "sanvent": include_sanvent,
    "storm": include_storm,
    "domestic": include_domestic,
    "garage": include_garage,
    "grease": include_grease,
    "podium": include_podium,
}

st.markdown("#### Mechanical Toggles")
mt1, mt2, mt3, mt4, mt5, mt6, mt7 = st.columns(7)
include_duct = mt1.checkbox("Ductwork", value=True)
include_ref = mt2.checkbox("Refrigerant Piping", value=False)
include_smoke = mt3.checkbox("Smoke Control", value=False)
include_chw = mt4.checkbox("Chilled Water", value=False)
include_cw = mt5.checkbox("Condenser Water", value=False)
include_ies = mt6.checkbox("IES Loads", value=False)
include_oa = mt7.checkbox("OA Calcs", value=True)

mech_toggle_map = {
    "ductwork": include_duct,
    "refrigerant_piping": include_ref,
    "smoke_control": include_smoke,
    "chilled_water": include_chw,
    "condenser_water": include_cw,
    "ies_loads": include_ies,
    "oa_calcs": include_oa,
}

# Merge toggle maps (common + discipline specific)
toggle_map_elec = {**common_toggle_map, **elec_toggle_map}
toggle_map_plumb = {**common_toggle_map, **plumb_toggle_map}
toggle_map_mech = {**common_toggle_map, **mech_toggle_map}

# ============================================================
# Work Plan Generator
# ============================================================
st.divider()
st.subheader("Work Plan Generator")

elec_fee = mep_fee * float(st.session_state.electrical_pct) / 100.0
plumb_fee = mep_fee * float(st.session_state.plumbing_pct) / 100.0
mech_fee = mep_fee * float(st.session_state.mechanical_pct) / 100.0

# Apply toggles BEFORE plan generation (this affects hours breakdown)
elec_tasks_active = apply_toggles_to_tasks(st.session_state.electrical_lib, toggle_map_elec)
plumb_tasks_active = apply_toggles_to_tasks(st.session_state.plumbing_lib, toggle_map_plumb)
mech_tasks_active = apply_toggles_to_tasks(st.session_state.mechanical_lib, toggle_map_mech)

e_plan = build_plan_from_library(elec_tasks_active, elec_fee, billing_rate, st.session_state.phase_split)
p_plan = build_plan_from_library(plumb_tasks_active, plumb_fee, billing_rate, st.session_state.phase_split)
m_plan = build_plan_from_library(mech_tasks_active, mech_fee, billing_rate, st.session_state.phase_split)

def render(title, df):
    st.subheader(title)
    for ph in PHASES:
        d = df[df["Phase"] == ph].copy()
        if d.empty:
            continue
        hrs = float(d["Hours"].sum())
        fee = float(d["Fee ($)"].sum())
        with st.expander(f"{ph} — {hrs:,.1f} hrs | {money(fee)}"):
            st.dataframe(d, use_container_width=True, hide_index=True)

    st.divider()
    if not df.empty:
        st.markdown(f"**TOTAL:** {float(df['Hours'].sum()):,.1f} hrs | {money(float(df['Fee ($)'].sum()))}")
    else:
        st.markdown("**TOTAL:** 0.0 hrs | $0")

col1, col2, col3 = st.columns(3)
with col1:
    render("Electrical", e_plan)
with col2:
    render("Plumbing / Fire", p_plan)
with col3:
    render("Mechanical", m_plan)

# ============================================================
# Task Library Editors (tune weights + tags)
# ============================================================
st.divider()
st.subheader("Task Libraries (tune weights, enable/disable, tags)")

tab1, tab2, tab3 = st.tabs(["Electrical Tasks", "Plumbing/Fire Tasks", "Mechanical Tasks"])

with tab1:
    st.session_state.electrical_lib = st.data_editor(
        st.session_state.electrical_lib,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Phase": st.column_config.TextColumn(disabled=True),
            "Task": st.column_config.TextColumn(disabled=True),
            "BaseHours": st.column_config.NumberColumn(min_value=0.0, step=1.0),
            "Tags": st.column_config.TextColumn(help="Comma-separated tags, e.g. pm,coordination,ev"),
            "Enabled": st.column_config.CheckboxColumn(),
        },
        key="elec_lib_editor",
    )

with tab2:
    st.session_state.plumbing_lib = st.data_editor(
        st.session_state.plumbing_lib,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Phase": st.column_config.TextColumn(disabled=True),
            "Task": st.column_config.TextColumn(disabled=True),
            "BaseHours": st.column_config.NumberColumn(min_value=0.0, step=1.0),
            "Tags": st.column_config.TextColumn(help="Comma-separated tags, e.g. grease,garage,podium"),
            "Enabled": st.column_config.CheckboxColumn(),
        },
        key="plumb_lib_editor",
    )

with tab3:
    st.session_state.mechanical_lib = st.data_editor(
        st.session_state.mechanical_lib,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Phase": st.column_config.TextColumn(disabled=True),
            "Task": st.column_config.TextColumn(disabled=True),
            "BaseHours": st.column_config.NumberColumn(min_value=0.0, step=1.0),
            "Tags": st.column_config.TextColumn(help="Comma-separated tags, e.g. ductwork,oa_calcs,ies_loads"),
            "Enabled": st.column_config.CheckboxColumn(),
        },
        key="mech_lib_editor",
    )
