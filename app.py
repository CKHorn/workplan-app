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
        raise ValueError
    return int(digits)

# -----------------------------
# ELECTRICAL TEMPLATE
# -----------------------------
ELECTRICAL_TEMPLATE = [
    ("SD", "PM / Coordination", 30),
    ("SD", "Load calcs & concepts", 60),

    ("DD", "PM / Coordination", 40),
    ("DD", "Power & lighting plans", 110),

    ("CD", "PM / QAQC", 50),
    ("CD", "Construction documents", 180),

    ("Bidding", "Bidding support", 10),

    ("CA", "Submittals / RFIs / Site visits", 120),
]

# -----------------------------
# PLUMBING TEMPLATE
# -----------------------------
PLUMBING_TEMPLATE = [
    ("SD", "Sizing & early coordination", 120),

    ("DD", "System layouts & coordination", 200),

    ("CD", "Detailed plans & isometrics", 160),

    ("Bidding", "Bidding support", 10),

    ("CA", "Submittals / RFIs / site support", 60),
]

# -----------------------------
def build_plan(template, target_fee, billing_rate, phase_split):
    df = pd.DataFrame(template, columns=["Phase", "Task", "Base Hours"])

    # Normalize phase split
    total_pct = sum(phase_split.values())
    phase_split = {k: v / total_pct for k, v in phase_split.items()}

    # Fee per phase
    phase_fee = {p: target_fee * phase_split.get(p, 0) for p in df["Phase"].unique()}

    df["Phase Fee"] = df["Phase"].map(phase_fee)

    # Distribute hours per phase proportionally
    result = []
    for phase in df["Phase"].unique():
        phase_df = df[df["Phase"] == phase].copy()
        base_sum = phase_df["Base Hours"].sum()

        phase_hours = phase_fee[phase] / billing_rate if billing_rate > 0 else 0

        phase_df["Hours"] = phase_df["Base Hours"] / base_sum * phase_hours
        phase_df["Fee ($)"] = phase_df["Hours"] * billing_rate

        result.append(phase_df)

    out = pd.concat(result)
    out["Hours"] = out["Hours"].round(1)
    out["Fee ($)"] = out["Fee ($)"].round(0)
    return out[["Phase", "Task", "Hours", "Fee ($)"]]

# -----------------------------
def main():
    st.set_page_config(page_title="MEP Work Plan Generator", layout="wide")
    st.title("Electrical + Plumbing Work Plan Generator — Hours & Fees")

    # -----------------------------
    # SIDEBAR INPUTS
    # -----------------------------
    with st.sidebar:
        st.header("Construction and % Design Fee Inputs")

        cost_raw = st.text_input("Construction Cost ($)", "10,000,000")
        construction_cost = parse_currency_int(cost_raw)

        arch_fee_pct = st.number_input("Architectural Fee (%)", value=3.5)
        mep_fee_pct = st.number_input("Standard MEP Fee (%)", value=15.0)
        electrical_fee_pct = st.number_input("Electrical Fee (%)", value=25.0)
        plumbing_fee_pct = st.number_input("Plumbing Fee (%)", value=25.0)

        st.divider()
        st.header("Design Phase Fee % Split")

        sd_pct = st.number_input("SD (%)", value=12.0)
        dd_pct = st.number_input("DD (%)", value=40.0)
        cd_pct = st.number_input("CD (%)", value=28.0)
        bid_pct = st.number_input("Bidding (%)", value=1.5)
        ca_pct = st.number_input("CA (%)", value=18.5)

        phase_split = {
            "SD": sd_pct,
            "DD": dd_pct,
            "CD": cd_pct,
            "Bidding": bid_pct,
            "CA": ca_pct,
        }

        st.divider()
        st.header("Rate Inputs")

        base_raw_rate = st.number_input("Base Raw Rate ($/hr)", value=56.0)
        multiplier = st.number_input("Multiplier", value=3.6)
        billing_rate = base_raw_rate * multiplier

    # -----------------------------
    # FEE CASCADE
    # -----------------------------
    arch_fee = construction_cost * pct(arch_fee_pct)
    mep_fee = arch_fee * pct(mep_fee_pct)

    electrical_target_fee = mep_fee * pct(electrical_fee_pct)
    plumbing_target_fee = mep_fee * pct(plumbing_fee_pct)

    # -----------------------------
    # BUILD PLANS
    # -----------------------------
    e_df = build_plan(ELECTRICAL_TEMPLATE, electrical_target_fee, billing_rate, phase_split)
    p_df = build_plan(PLUMBING_TEMPLATE, plumbing_target_fee, billing_rate, phase_split)

    # -----------------------------
    # DISPLAY
    # -----------------------------
    st.subheader("Design Fee Summary")
    st.write(
        f"Construction: {money(construction_cost)} | "
        f"MEP Fee: {money(mep_fee)} | "
        f"Electrical: {money(electrical_target_fee)} | "
        f"Plumbing: {money(plumbing_target_fee)}"
    )

    st.divider()
    left, right = st.columns(2)

    with left:
        st.subheader("Electrical")
        for phase in e_df["Phase"].unique():
            dfp = e_df[e_df["Phase"] == phase]
            hrs = dfp["Hours"].sum()
            fee = dfp["Fee ($)"].sum()
            with st.expander(f"{phase} — {hrs:.1f} hrs | {money(fee)}"):
                st.dataframe(dfp[["Task", "Hours", "Fee ($)"]], hide_index=True)

    with right:
        st.subheader("Plumbing")
        for phase in p_df["Phase"].unique():
            dfp = p_df[p_df["Phase"] == phase]
            hrs = dfp["Hours"].sum()
            fee = dfp["Fee ($)"].sum()
            with st.expander(f"{phase} — {hrs:.1f} hrs | {money(fee)}"):
                st.dataframe(dfp[["Task", "Hours", "Fee ($)"]], hide_index=True)

    st.divider()
    st.markdown(
        f"### TOTALS\n"
        f"**Electrical:** {e_df['Hours'].sum():.1f} hrs | {money(e_df['Fee ($)'].sum())}\n\n"
        f"**Plumbing:** {p_df['Hours'].sum():.1f} hrs | {money(p_df['Fee ($)'].sum())}"
    )

if __name__ == "__main__":
    main()
