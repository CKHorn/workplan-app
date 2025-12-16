import re
import streamlit as st
import pandas as pd

# -----------------------------
# Helpers
# -----------------------------
def money(x: float) -> str:
    return f"${x:,.0f}"

def pct(x: float) -> float:
    return x / 100.0

def parse_currency_int(text: str) -> int:
    digits = re.sub(r"[^\d]", "", text or "")
    if digits == "":
        raise ValueError("No digits")
    return int(digits)

def normalize_phase_split(phase_split: dict) -> dict:
    total = sum(max(v, 0.0) for v in phase_split.values())
    if total <= 0:
        n = len(phase_split)
        return {k: 1.0 / n for k in phase_split}
    return {k: max(v, 0.0) / total for k, v in phase_split.items()}

def build_phase_scaled_plan(template_rows, target_fee, billing_rate, phase_split):
    phases = list(phase_split.keys())
    phase_split_n = normalize_phase_split(phase_split)

    df = pd.DataFrame(template_rows).copy()
    df = df[df["BaseHours"] > 0].copy()

    # ensure each phase has a row
    for p in phases:
        if not (df["Phase"] == p).any():
            df = pd.concat(
                [df, pd.DataFrame([{"Phase": p, "Task": f"{p} - General", "BaseHours": 1.0}])],
                ignore_index=True,
            )

    phase_fee = {p: target_fee * phase_split_n[p] for p in phases}
    phase_hours = {p: (phase_fee[p] / billing_rate) if billing_rate > 0 else 0.0 for p in phases}

    out_rows = []
    for p in phases:
        p_df = df[df["Phase"] == p].copy()
        base_sum = float(p_df["BaseHours"].sum())
        p_df["Hours"] = p_df["BaseHours"] / base_sum * phase_hours[p]
        p_df["Fee ($)"] = p_df["Hours"] * billing_rate
        out_rows.append(p_df[["Phase", "Task", "Hours", "Fee ($)"]])

    out = pd.concat(out_rows, ignore_index=True)
    out["Hours"] = out["Hours"].round(1)
    out["Fee ($)"] = out["Fee ($)"].round(0)
    return out

# -----------------------------
# Discipline splits
# -----------------------------
ELECTRICAL_BASE_PCT = 28.0
PLUMBING_BASE_PCT = 24.0

PLUMBING_CORE_PCT = 90.0   # Plumbing
FIRE_PCT = 10.0            # Fire Protection

# -----------------------------
# ELECTRICAL TASKS (unchanged)
# -----------------------------
ELECTRICAL_ROWS = []
_sd = [
    ("PM: kickoff / coordination", 30),
    ("Load calcs & concepts", 60),
]
for t, h in _sd:
    ELECTRICAL_ROWS.append({"Phase": "SD", "Task": t, "BaseHours": h})

_dd = [
    ("PM / coordination", 40),
    ("Power & lighting plans", 110),
]
for t, h in _dd:
    ELECTRICAL_ROWS.append({"Phase": "DD", "Task": t, "BaseHours": h})

_cd = [
    ("PM / QAQC", 50),
    ("Construction documents", 180),
]
for t, h in _cd:
    ELECTRICAL_ROWS.append({"Phase": "CD", "Task": t, "BaseHours": h})

ELECTRICAL_ROWS.append({"Phase": "Bidding", "Task": "Bidding support", "BaseHours": 10})
ELECTRICAL_ROWS.append({"Phase": "CA", "Task": "Submittals / RFIs / site visits", "BaseHours": 120})

# -----------------------------
# PLUMBING BASE TASKS
# -----------------------------
PLUMBING_BASE = [
    ("SD", "SAN/VENT – Initial sizing", 3),
    ("SD", "SAN/VENT – Civil coordination", 9),
    ("SD", "SAN/VENT – Luxury amenity", 9),

    ("DD", "SAN/VENT – Equipment sizing", 18),
    ("DD", "Domestic – Distribution layouts", 30),

    ("CD", "SAN/VENT – Collections & isometrics", 90),
    ("CD", "Garage drainage", 53),
    ("CD", "Misc / details / schedules", 18),

    ("Bidding", "Bidding support (Plumbing)", 10),
    ("CA", "Submittals / RFIs / site support (Plumbing)", 60),
]

def main():
    st.set_page_config(page_title="MEP Work Plan Generator", layout="wide")
    st.title("Electrical + Plumbing / Fire Work Plan Generator — Hours & Fees")

    # -----------------------------
    # Sidebar
    # -----------------------------
    with st.sidebar:
        st.header("Construction and % Design Fee Inputs")

        cost_raw = st.text_input("Construction Cost ($)", "10,000,000")
        construction_cost = parse_currency_int(cost_raw)

        arch_fee_pct = st.number_input("Architectural Fee (%)", value=3.5)
        mep_fee_pct = st.number_input("Standard MEP Fee (%)", value=15.0)

        st.divider()
        st.header("Rate Inputs")
        base_raw_rate = st.number_input("Base Raw Rate ($/hr)", value=56.0)
        multiplier = st.number_input("Multiplier", value=3.6)
        billing_rate = base_raw_rate * multiplier

    # -----------------------------
    # Phase split (main page)
    # -----------------------------
    st.subheader("Design Phase Fee % Split")
    c1, c2, c3, c4, c5 = st.columns(5)
    sd = c1.number_input("SD", value=12.0)
    dd = c2.number_input("DD", value=40.0)
    cd = c3.number_input("CD", value=28.0)
    bid = c4.number_input("Bidding", value=1.5)
    ca = c5.number_input("CA", value=18.5)

    phase_split = {"SD": sd, "DD": dd, "CD": cd, "Bidding": bid, "CA": ca}

    # -----------------------------
    # Fee cascade
    # -----------------------------
    arch_fee = construction_cost * pct(arch_fee_pct)
    mep_fee = arch_fee * pct(mep_fee_pct)

    electrical_fee = mep_fee * pct(ELECTRICAL_BASE_PCT)
    plumbing_fire_fee = mep_fee * pct(PLUMBING_BASE_PCT)

    plumbing_fee = plumbing_fire_fee * pct(PLUMBING_CORE_PCT)
    fire_fee = plumbing_fire_fee * pct(FIRE_PCT)

    # -----------------------------
    # Build plans
    # -----------------------------
    e_df = build_phase_scaled_plan(ELECTRICAL_ROWS, electrical_fee, billing_rate, phase_split)

    p_df = build_phase_scaled_plan(
        [{"Phase": p, "Task": t, "BaseHours": h} for p, t, h in PLUMBING_BASE],
        plumbing_fee,
        billing_rate,
        phase_split,
    )

    fire_rows = [
        {"Phase": phase, "Task": "Fire Protection", "BaseHours": 1.0}
        for phase in phase_split.keys()
    ]
    f_df = build_phase_scaled_plan(fire_rows, fire_fee, billing_rate, phase_split)

    pf_df = pd.concat([p_df, f_df], ignore_index=True)

    # -----------------------------
    # Summary
    # -----------------------------
st.subheader("Design Fee Summary")
c1, c2, c3, c4, c5 = st.columns(5)

with c1:
    st.markdown("**Construction Cost**")
    st.write(money(construction_cost))

with c2:
    st.markdown("**Architectural Fee**")
    st.write(money(arch_fee))

with c3:
    st.markdown("**MEP Fee**")
    st.write(money(mep_fee))

with c4:
    st.markdown("**Electrical Fee (28% of MEP)**")
    st.write(money(electrical_fee))

with c5:
    st.markdown("**Plumbing / Fire Fee (24% of MEP)**")
    st.write(money(plumbing_fire_fee))


    # -----------------------------
    # Display
    # -----------------------------
    left, right = st.columns(2)

    with left:
        st.subheader("Electrical")
        for ph in phase_split:
            dfp = e_df[e_df["Phase"] == ph]
            with st.expander(f"{ph} — {dfp['Hours'].sum():.1f} hrs | {money(dfp['Fee ($)'].sum())}"):
                st.dataframe(dfp[["Task", "Hours", "Fee ($)"]], hide_index=True)

    with right:
        st.subheader("Plumbing / Fire")
        for ph in phase_split:
            dfp = pf_df[pf_df["Phase"] == ph]
            with st.expander(f"{ph} — {dfp['Hours'].sum():.1f} hrs | {money(dfp['Fee ($)'].sum())}"):
                st.dataframe(dfp[["Task", "Hours", "Fee ($)"]], hide_index=True)

    st.divider()
    st.markdown(
        f"""
### TOTALS
**Electrical:** {e_df['Hours'].sum():.1f} hrs | {money(e_df['Fee ($)'].sum())}  
**Plumbing / Fire:** {pf_df['Hours'].sum():.1f} hrs | {money(pf_df['Fee ($)'].sum())}
"""
    )

if __name__ == "__main__":
    main()

