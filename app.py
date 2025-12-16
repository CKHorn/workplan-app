# ============================================================
# MEP Fee and Work Plan Generator
# FINAL STABLE VERSION
# ============================================================

import json
import streamlit as st
import pandas as pd

PHASES = ["SD", "DD", "CD", "Bidding", "CA"]

# ============================================================
# Helpers
# ============================================================
def money(x):
    return f"${x:,.0f}"

def pct(x):
    return f"{x*100:,.2f}%"

def normalize_pct_dict(d):
    vals = {k: max(float(d.get(k, 0.0)), 0.0) for k in d}
    total = sum(vals.values())
    if total <= 0:
        return {k: 1/len(vals) for k in vals}
    return {k: v/total for k, v in vals.items()}

def build_plan_from_library(task_df, target_fee, billing_rate, phase_split):
    phase_frac = normalize_pct_dict(phase_split)

    df = task_df.copy()
    df = df[df["Enabled"]].copy()
    if df.empty:
        return pd.DataFrame([{"Phase":"SD","Task":"No tasks enabled","Hours":0,"Fee ($)":0}])

    df["BaseHours"] = pd.to_numeric(df["BaseHours"], errors="coerce").fillna(0)

    rows = []
    for ph in PHASES:
        frac = phase_frac.get(ph, 0)
        phase_fee = target_fee * frac
        phase_hours = phase_fee / billing_rate if billing_rate > 0 else 0

        p = df[df["Phase"] == ph].copy()
        if p.empty:
            continue

        w_sum = p["BaseHours"].sum()
        p["Hours"] = (p["BaseHours"] / w_sum) * phase_hours if w_sum > 0 else 0
        p["Fee ($)"] = p["Hours"] * billing_rate
        rows.append(p[["Phase","Task","Hours","Fee ($)"]])

    out = pd.concat(rows, ignore_index=True)
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

def recalc_area_df(df):
    df = df.copy()
    df["Area (SF)"] = pd.to_numeric(df["Area (SF)"], errors="coerce").fillna(0)
    df["Override $/SF Value"] = pd.to_numeric(df["Override $/SF Value"], errors="coerce").fillna(0)
    df["Override $/SF?"] = df["Override $/SF?"].astype(bool)

    for i, r in df.iterrows():
        lookup = RATE_LOOKUP.get(r["Space Type"])
        if r["Override $/SF?"]:
            df.loc[i, "$/SF"] = r["Override $/SF Value"]
        else:
            df.loc[i, "$/SF"] = 0 if lookup is None else lookup

    df["Total Cost"] = df["Area (SF)"] * df["$/SF"]
    return df

# ============================================================
# Detailed Task Libraries (WEIGHTS)
# ============================================================
def electrical_defaults_df():
    tasks = [
        ("SD","PM / Coordination",30),
        ("SD","Design / Analysis",70),
        ("DD","PM / Coordination",40),
        ("DD","Plans / Schedules",120),
        ("CD","PM / QAQC",50),
        ("CD","Construction Documents",180),
        ("Bidding","Bidding Support",10),
        ("CA","Construction Administration",120),
    ]
    df = pd.DataFrame(tasks, columns=["Phase","Task","BaseHours"])
    df["Enabled"] = True
    return df

def plumbing_defaults_df():
    tasks = [
        ("SD","Sizing / Coordination",80),
        ("DD","Layouts / Coordination",140),
        ("CD","Details / Isometrics",200),
        ("Bidding","Bidding Support",10),
        ("CA","Construction Administration",120),
    ]
    df = pd.DataFrame(tasks, columns=["Phase","Task","BaseHours"])
    df["Enabled"] = True
    return df

def mechanical_defaults_df():
    tasks = [
        ("SD","Preliminary Design",55),
        ("DD","System Design / Modeling",198),
        ("CD","Detailed Design",134),
        ("Bidding","Bidding / CPS",55),
        ("CA","Construction Administration",60),
    ]
    df = pd.DataFrame(tasks, columns=["Phase","Task","BaseHours"])
    df["Enabled"] = True
    return df

# ============================================================
# App Setup
# ============================================================
st.set_page_config(page_title="MEP Fee and Work Plan Generator", layout="wide")
st.title("MEP Fee and Work Plan Generator")

# ---------------- Session State ----------------
if "area_df" not in st.session_state:
    st.session_state.area_df = pd.DataFrame([
        new_space_row("Amenity Areas","Amenities",18000),
        new_space_row("BOH Rooms","Back of House",14000),
        new_space_row("Retail (Core & Shell Restaurant)","Retail",5000),
        new_space_row("Office (Core & Shell)","Office",4500),
        new_space_row("Parking (Enclosed)","Parking",80000),
        new_space_row("Multifamily (High Rise)","Residential",175000),
    ])

if "construction_cost_psf" not in st.session_state:
    st.session_state.construction_cost_psf = 300.0
if "arch_fee_pct" not in st.session_state:
    st.session_state.arch_fee_pct = 3.5

if "phase_split" not in st.session_state:
    st.session_state.phase_split = {"SD":12,"DD":40,"CD":28,"Bidding":1.5,"CA":18.5}

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

billing_rate = st.session_state.base_raw_rate * st.session_state.multiplier

# ============================================================
# Project Cost & Fee Context
# ============================================================
st.subheader("Project Cost & Fee Context")

st.session_state.area_df = recalc_area_df(st.session_state.area_df)
total_area = st.session_state.area_df["Area (SF)"].sum()

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(f"**Total Area**  \n{total_area:,.0f} SF")
with c2:
    st.session_state.construction_cost_psf = st.number_input(
        "Construction Cost ($/SF)", value=st.session_state.construction_cost_psf, step=5.0
    )
with c3:
    st.session_state.arch_fee_pct = st.number_input(
        "Arch Fee (%)", value=st.session_state.arch_fee_pct, step=0.1, format="%.2f"
    )

construction_cost_total = total_area * st.session_state.construction_cost_psf
arch_fee_total = construction_cost_total * (st.session_state.arch_fee_pct / 100)
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
# Area-Based Fee Calculator
# ============================================================
st.subheader("Area-Based MEP Fee Calculator")

edited = st.data_editor(
    st.session_state.area_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Delete?": st.column_config.CheckboxColumn(),
        "Space Type": st.column_config.SelectboxColumn(options=SPACE_TYPES),
        "Area (SF)": st.column_config.NumberColumn(format="%d"),
        "Override $/SF Value": st.column_config.NumberColumn(format="%.2f"),
        "$/SF": st.column_config.NumberColumn(disabled=True),
        "Total Cost": st.column_config.NumberColumn(disabled=True),
    }
)

edited = edited[edited["Delete?"] != True]
st.session_state.area_df = recalc_area_df(edited)

mep_fee = st.session_state.area_df["Total Cost"].sum()
mep_pct_of_arch = mep_fee / arch_fee_total if arch_fee_total > 0 else 0

s1, s2 = st.columns(2)
with s1:
    st.markdown("**MEP Fee (Area-Based)**")
    st.write(money(mep_fee))
with s2:
    st.markdown("**MEP % of Arch Fee**")
    st.write(pct(mep_pct_of_arch))

# ============================================================
# Work Plan Generator
# ============================================================
st.divider()
st.subheader("Work Plan Generator")

elec_fee = mep_fee * st.session_state.electrical_pct / 100
plumb_fee = mep_fee * st.session_state.plumbing_pct / 100
mech_fee = mep_fee * st.session_state.mechanical_pct / 100

e_plan = build_plan_from_library(st.session_state.electrical_lib, elec_fee, billing_rate, st.session_state.phase_split)
p_plan = build_plan_from_library(st.session_state.plumbing_lib, plumb_fee, billing_rate, st.session_state.phase_split)
m_plan = build_plan_from_library(st.session_state.mechanical_lib, mech_fee, billing_rate, st.session_state.phase_split)

def render(title, df):
    st.subheader(title)
    for ph in PHASES:
        d = df[df["Phase"] == ph]
        if d.empty:
            continue
        with st.expander(f"{ph} — {d['Hours'].sum():,.1f} hrs | {money(d['Fee ($)'].sum())}"):
            st.dataframe(d, use_container_width=True, hide_index=True)

col1, col2, col3 = st.columns(3)
with col1:
    render("Electrical", e_plan)
with col2:
    render("Plumbing / Fire", p_plan)
with col3:
    render("Mechanical", m_plan)
