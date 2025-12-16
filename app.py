# ============================================================
# MEP Fee and Work Plan Generator
# Toggles → Tasks → Hours (WEIGHTS MODEL)
# ============================================================

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

def parse_tags(tag_str):
    if tag_str is None:
        return set()
    return {t.strip().lower() for t in str(tag_str).split(",") if t.strip()}

def apply_toggles_to_tasks(task_df, toggle_map):
    """
    CORE LOGIC:
    - A task participates in hour distribution ONLY if:
        - Enabled == True
        - None of its tags are toggled OFF
    """
    df = task_df.copy()
    df["Enabled"] = df["Enabled"].astype(bool)

    def task_active(row):
        if not row["Enabled"]:
            return False
        tags = parse_tags(row.get("Tags", ""))
        for tag, is_on in toggle_map.items():
            if tag in tags and not is_on:
                return False
        return True

    df["__active__"] = df.apply(task_active, axis=1)
    return df[df["__active__"]].drop(columns="__active__")

def build_plan_from_library(task_df, target_fee, billing_rate, phase_split):
    """
    WEIGHTS MODEL:
    - Phase fee fixed by phase_split
    - Tasks in that phase share hours proportional to BaseHours
    """
    phase_frac = normalize_pct_dict(phase_split)

    df = task_df.copy()
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

    out = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    if not out.empty:
        out["Hours"] = out["Hours"].round(1)
        out["Fee ($)"] = out["Fee ($)"].round(0)
    return out

# ============================================================
# Task Libraries (DETAILED + TAGGED)
# ============================================================
def mechanical_tasks():
    tasks = [
        ("SD","Preliminary loads",18,"ies_loads,oa_calcs"),
        ("SD","Preliminary duct routing",15,"ductwork"),
        ("DD","Unit modeling",60,"ies_loads"),
        ("DD","Ductwork layouts",40,"ductwork"),
        ("DD","Refrigerant piping layouts",30,"refrigerant_piping"),
        ("DD","Chilled water layouts",25,"chilled_water"),
        ("DD","Condenser water layouts",20,"condenser_water"),
        ("CD","Ductwork details",35,"ductwork"),
        ("CD","Refrigerant piping details",25,"refrigerant_piping"),
        ("CD","Smoke control diagrams",18,"smoke_control"),
        ("CD","CHW details",22,"chilled_water"),
        ("CD","CW details",18,"condenser_water"),
        ("Bidding","Bidding support",20,"bidding"),
        ("CA","Construction administration",60,"ca"),
    ]
    df = pd.DataFrame(tasks, columns=["Phase","Task","BaseHours","Tags"])
    df["Enabled"] = True
    return df

def electrical_tasks():
    tasks = [
        ("SD","PM / Coordination",30,"pm,coordination"),
        ("SD","Load calcs",40,"analysis"),
        ("SD","Life safety concepts",20,"life_safety"),
        ("DD","Power plans",60,"power"),
        ("DD","EV layouts",20,"ev"),
        ("CD","Construction documents",120,"cd_docs,permitting"),
        ("CA","Construction admin",100,"ca"),
    ]
    df = pd.DataFrame(tasks, columns=["Phase","Task","BaseHours","Tags"])
    df["Enabled"] = True
    return df

def plumbing_tasks():
    tasks = [
        ("SD","System sizing",60,"sanvent"),
        ("DD","Layouts",100,"sanvent"),
        ("CD","Isometrics",160,"isometrics"),
        ("CD","Grease systems",40,"grease"),
        ("CA","Construction admin",120,"ca"),
    ]
    df = pd.DataFrame(tasks, columns=["Phase","Task","BaseHours","Tags"])
    df["Enabled"] = True
    return df

# ============================================================
# App Setup
# ============================================================
st.set_page_config(page_title="MEP Fee and Work Plan Generator", layout="wide")
st.title("MEP Fee and Work Plan Generator")

# ---------------- Session State ----------------
if "phase_split" not in st.session_state:
    st.session_state.phase_split = {"SD":12,"DD":40,"CD":28,"Bidding":1.5,"CA":18.5}

if "billing_rate" not in st.session_state:
    st.session_state.billing_rate = 200.0

if "mech_lib" not in st.session_state:
    st.session_state.mech_lib = mechanical_tasks()
if "elec_lib" not in st.session_state:
    st.session_state.elec_lib = electrical_tasks()
if "plumb_lib" not in st.session_state:
    st.session_state.plumb_lib = plumbing_tasks()

# ============================================================
# Phase Split Inputs
# ============================================================
st.subheader("Design Phase Fee % Split")
pcols = st.columns(5)
for i, ph in enumerate(PHASES):
    st.session_state.phase_split[ph] = pcols[i].number_input(
        f"{ph} (%)", value=float(st.session_state.phase_split.get(ph,0))
    )

# ============================================================
# Mechanical Toggles (DIRECTLY AFFECT HOURS)
# ============================================================
st.subheader("Mechanical Scope Toggles")

tcols = st.columns(7)
toggles_mech = {
    "ductwork": tcols[0].checkbox("Ductwork", value=True),
    "refrigerant_piping": tcols[1].checkbox("Refrigerant Piping", value=False),
    "smoke_control": tcols[2].checkbox("Smoke Control", value=False),
    "chilled_water": tcols[3].checkbox("Chilled Water", value=False),
    "condenser_water": tcols[4].checkbox("Condenser Water", value=False),
    "ies_loads": tcols[5].checkbox("IES Loads", value=False),
    "oa_calcs": tcols[6].checkbox("OA Calcs", value=True),
}

# ============================================================
# Build Mechanical Work Plan (TOGGLES → TASKS → HOURS)
# ============================================================
st.divider()
st.subheader("Mechanical Work Plan")

mech_fee = 500_000  # example fee for demo
mech_active_tasks = apply_toggles_to_tasks(st.session_state.mech_lib, toggles_mech)

mech_plan = build_plan_from_library(
    mech_active_tasks,
    mech_fee,
    st.session_state.billing_rate,
    st.session_state.phase_split
)

for ph in PHASES:
    d = mech_plan[mech_plan["Phase"] == ph]
    if d.empty:
        continue
    with st.expander(f"{ph} — {d['Hours'].sum():,.1f} hrs | {money(d['Fee ($)'].sum())}"):
        st.dataframe(d, use_container_width=True, hide_index=True)

st.markdown(
    f"### TOTAL: {mech_plan['Hours'].sum():,.1f} hrs | {money(mech_plan['Fee ($)'].sum())}"
)
