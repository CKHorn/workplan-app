import streamlit as st
import pandas as pd

def money(x: float) -> str:
    return f"${x:,.0f}"

def pct(x: float) -> float:
    return x / 100.0

# -------------------------------------------------------
# Template: PM included inside SD/DD/CD/CA phases
# -------------------------------------------------------
TEMPLATE = [
    # SD (includes PM)
    ("Schematic Design (SD)", "PM: Kickoff & project setup", 6),
    ("Schematic Design (SD)", "PM: Schedule tracking & coordination", 6),
    ("Schematic Design (SD)", "PM: Client coordination (SD)", 6),
    ("Schematic Design (SD)", "Utility research & service availability", 10),
    ("Schematic Design (SD)", "Preliminary load calculations", 14),
    ("Schematic Design (SD)", "Service & distribution concepts", 16),
    ("Schematic Design (SD)", "Electrical room & shaft planning", 12),
    ("Schematic Design (SD)", "Preliminary risers / one-lines", 18),
    ("Schematic Design (SD)", "Typical unit power & lighting concepts", 16),
    ("Schematic Design (SD)", "Common area electrical concepts", 12),
    ("Schematic Design (SD)", "EV charging assumptions", 8),
    ("Schematic Design (SD)", "Life safety & code analysis", 10),
    ("Schematic Design (SD)", "Basis of Design narrative", 12),
    ("Schematic Design (SD)", "SD review & revisions", 10),

    # DD (includes PM)
    ("Design Development (DD)", "PM: Client coordination (DD)", 6),
    ("Design Development (DD)", "PM: MEP/Arch coordination (DD)", 8),
    ("Design Development (DD)", "PM: Internal design reviews (DD)", 6),
    ("Design Development (DD)", "Updated load calculations", 14),
    ("Design Development (DD)", "Power plans – typical units", 24),
    ("Design Development (DD)", "Power plans – common areas", 22),
    ("Design Development (DD)", "Lighting layouts & controls", 22),
    ("Design Development (DD)", "Equipment room layouts", 12),
    ("Design Development (DD)", "Metering strategy", 10),
    ("Design Development (DD)", "Panel schedules (DD level)", 14),
    ("Design Development (DD)", "Riser & one-line refinement", 14),
    ("Design Development (DD)", "Code compliance review", 8),
    ("Design Development (DD)", "DD review & revisions", 14),

    # CD (includes PM)
    ("Construction Documents (CD)", "PM: Coordination & issue management (CD)", 10),
    ("Construction Documents (CD)", "PM: QA/QC planning & tracking (CD)", 6),
    ("Construction Documents (CD)", "PM: Internal QA/QC (CD)", 10),
    ("Construction Documents (CD)", "Final unit power plans", 36),
    ("Construction Documents (CD)", "Final common area power plans", 30),
    ("Construction Documents (CD)", "Lighting plans & controls", 32),
    ("Construction Documents (CD)", "Emergency / life safety systems", 20),
    ("Construction Documents (CD)", "Final risers & one-lines", 26),
    ("Construction Documents (CD)", "Final load calculations", 12),
    ("Construction Documents (CD)", "Panel schedules (final)", 28),
    ("Construction Documents (CD)", "Details & diagrams", 18),
    ("Construction Documents (CD)", "Grounding & bonding", 10),
    ("Construction Documents (CD)", "Specs & general notes", 14),
    ("Construction Documents (CD)", "Permit set issuance", 12),

    # CA (includes PM)
    ("Construction Administration (CA)", "PM: CA coordination & reporting", 8),
    ("Construction Administration (CA)", "Submittal reviews", 34),
    ("Construction Administration (CA)", "Shop drawings", 20),
    ("Construction Administration (CA)", "RFIs", 28),
    ("Construction Administration (CA)", "Site visits", 22),
    ("Construction Administration (CA)", "Change order reviews", 12),
    ("Construction Administration (CA)", "Punchlist support", 12),
    ("Construction Administration (CA)", "As-built review", 10),
]

def main():
    st.set_page_config(page_title="Electrical Work Plan Generator", layout="wide")
    st.title("Electrical Work Plan Generator — Hours & Fees")

    # -----------------------------
    # Sidebar inputs
    # -----------------------------
    with st.sidebar:
        st.header("Construction and % Design Fee Inputs")

construction_cost_str = st.text_input(
    "Construction Cost ($)",
    value="10,000,000",
    help="Enter total construction cost (commas allowed, no decimals)."
)

# Parse input safely
try:
    construction_cost = float(construction_cost_str.replace(",", ""))
except ValueError:
    construction_cost = 0.0
    st.warning("Please enter a valid construction cost (numbers and commas only).")


        arch_fee_pct = st.number_input(
            "Architectural Fee (%)",
            min_value=0.0,
            value=3.5,
            step=0.1,
            format="%.2f",
        )

        mep_fee_pct = st.number_input(
            "Standard MEP Fee (%)",
            min_value=0.0,
            value=15.0,
            step=0.5,
            format="%.2f",
        )

        electrical_fee_pct = st.number_input(
            "Electrical Fee (%)",
            min_value=0.0,
            value=25.0,
            step=0.5,
            format="%.2f",
        )

        st.divider()
        st.header("Rate Inputs")

        base_raw_rate = st.number_input(
            "Base Raw Rate ($/hr)",
            min_value=0.0,
            value=56.0,
            step=1.0,
        )

        multiplier = st.number_input(
            "Multiplier",
            min_value=0.0,
            value=3.6,
            step=0.1,
            format="%.2f",
        )

        billing_rate = base_raw_rate * multiplier

    # -----------------------------
    # Fee cascade calculations
    # -----------------------------
    arch_fee_dollars = construction_cost * pct(arch_fee_pct)
    mep_fee_dollars = arch_fee_dollars * pct(mep_fee_pct)
    electrical_target_fee = mep_fee_dollars * pct(electrical_fee_pct)

    # -----------------------------
    # Summary
    # -----------------------------
    st.subheader("Design Fee Summary")
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown("**Construction Cost**")
        st.write(money(construction_cost))

    with c2:
        st.markdown("**Architectural Fee ($)**")
        st.write(money(arch_fee_dollars))

    with c3:
        st.markdown("**MEP Fee ($)**")
        st.write(money(mep_fee_dollars))

    with c4:
        st.markdown("**Electrical Target Fee ($)**")
        st.write(money(electrical_target_fee))

    st.write(
        f"**Base Raw Rate:** {money(base_raw_rate)}/hr  |  "
        f"**Multiplier:** {multiplier:.2f}  |  "
        f"**Billing Rate Used:** {money(billing_rate)}/hr"
    )

    # -----------------------------
    # Build & scale workplan
    # -----------------------------
    df = pd.DataFrame(TEMPLATE, columns=["Phase", "Task", "Base Hours"])
    df["Hours"] = df["Base Hours"].astype(float)

    base_total_hours = float(df["Hours"].sum())
    base_total_fee = base_total_hours * billing_rate

    scale = 0.0 if billing_rate <= 0 or base_total_fee <= 0 else electrical_target_fee / base_total_fee

    df["Hours"] = (df["Hours"] * scale).round(1)
    df["Fee ($)"] = (df["Hours"] * billing_rate).round(0)

    total_hours = float(df["Hours"].sum())
    total_fee = float(df["Fee ($)"].sum())

    st.write(
        f"**Hours scaling factor applied:** `{scale:.3f}`  "
        f"(Base total fee @ billing rate was {money(base_total_fee)}; "
        f"scaled to {money(electrical_target_fee)})"
    )

    # -----------------------------
    # Phase dropdowns
    # -----------------------------
    st.divider()
    st.subheader("Electrical Detailed Task Plan — Hours & Fees (by Phase)")

    for phase in df["Phase"].unique():
        phase_df = df[df["Phase"] == phase][["Task", "Hours", "Fee ($)"]].copy()
        phase_hours = float(phase_df["Hours"].sum())
        phase_fee = float(phase_df["Fee ($)"].sum())

        with st.expander(f"{phase} — {phase_hours:,.1f} hrs | {money(phase_fee)}", expanded=False):
            pretty = phase_df.copy()
            pretty["Fee ($)"] = pretty["Fee ($)"].apply(lambda v: money(float(v)))
            st.dataframe(pretty, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown(f"### TOTAL LABOR\n**{total_hours:,.1f} hrs**  |  **{money(total_fee)}**")

if __name__ == "__main__":
    main()

