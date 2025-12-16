import streamlit as st
import pandas as pd

def money(x: float) -> str:
    return f"${x:,.0f}"

def pct(x: float) -> float:
    return x / 100.0

# -------------------------------------------------------
# Template: PM is included INSIDE SD/DD/CD/CA phases
# (Edit tasks/hours anytime)
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

    with st.sidebar:
        st.header("Inputs (cascading)")

        construction_cost = st.number_input(
            "Construction Cost ($)",
            min_value=0.0,
            value=10_000_000.0,
            step=100_000.0,
        )

        arch_fee_pct = st.number_input(
            "Arch Fee (%)",
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
            help="Applied to the MEP fee dollars to calculate Electrical Target Fee.",
        )

        st.divider()
        st.header("Rate inputs (used to scale hours)")

        standard_rate = st.number_input("Standard Rate ($/hr)", min_value=0.0, value=150.0, step=5.0)
        multiplier = st.number_input("Multiplier", min_value=0.0, value=1.0, step=0.05, format="%.2f")
        billing_rate = standard_rate * multiplier

    # Cascading fee calcs
    arch_fee_dollars = construction_cost * pct(arch_fee_pct)
    mep_fee_dollars = arch_fee_dollars * pct(mep_fee_pct)
    electrical_target_fee = mep_fee_dollars * pct(electrical_fee_pct)

    # Header summary
    st.subheader("Fee Cascade Summary")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Construction Cost", money(construction_cost))
    c2.metric("Arch Fee ($)", money(arch_fee_dollars))
    c3.metric("MEP Fee ($)", money(mep_fee_dollars))
    c4.metric("Electrical Target Fee ($)", money(electrical_target_fee))

    st.write(f"**Billing Rate Used:** {money(billing_rate)}/hr")

    # Build base df
    df = pd.DataFrame(TEMPLATE, columns=["Phase", "Task", "Base Hours"])
    df["Hours"] = df["Base Hours"].astype(float)

    # Scale hours to match Electrical Target Fee
    base_total_hours = float(df["Hours"].sum())
    base_total_fee = base_total_hours * billing_rate

    if billing_rate <= 0:
        scale = 0.0
    else:
        scale = (electrical_target_fee / base_total_fee) if base_total_fee > 0 else 0.0

    df["Hours"] = (df["Hours"] * scale).round(1)
    df["Fee ($)"] = (df["Hours"] * billing_rate).round(0)

    # Totals
    total_hours = float(df["Hours"].sum())
    total_fee = float(df["Fee ($)"].sum())

    st.write(
        f"**Hours scaling factor applied:** `{scale:.3f}`  "
        f"(Base total fee @ billing rate was {money(base_total_fee)}; scaled to {money(electrical_target_fee)})"
    )

    st.divider()
    st.subheader("Electrical Detailed Task Plan — Hours & Fees (by Phase)")

    # Show phases as dropdown expanders
    for phase in df["Phase"].unique():
        phase_df = df[df["Phase"] == phase][["Task", "Hours", "Fee ($)"]].copy()

        phase_hours = float(phase_df["Hours"].sum())
        phase_fee = float(phase_df["Fee ($)"].sum())

        with st.expander(f"{phase}  —  {phase_hours:,.1f} hrs  |  {money(phase_fee)}", expanded=False):
            pretty = phase_df.copy()
            pretty["Fee ($)"] = pretty["Fee ($)"].apply(lambda v: money(float(v)))
            st.dataframe(pretty, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown(f"### TOTAL LABOR\n**{total_hours:,.1f} hrs**  |  **{money(total_fee)}**")

    # Downloads
    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        csv = df[["Phase", "Task", "Hours", "Fee ($)"]].to_csv(index=False)
        st.download_button(
            "Download CSV (tasks)",
            data=csv,
            file_name="electrical_work_plan_tasks.csv",
            mime="text/csv",
        )

    with col2:
        # Phase summary export
        phase_summary = (
            df.groupby("Phase", as_index=False)[["Hours", "Fee ($)"]]
              .sum()
              .rename(columns={"Hours": "Phase Hours", "Fee ($)": "Phase Fee ($)"})
        )
        phase_csv = phase_summary.to_csv(index=False)
        st.download_button(
            "Download CSV (phase summary)",
            data=phase_csv,
            file_name="electrical_work_plan_phase_summary.csv",
            mime="text/csv",
        )

if __name__ == "__main__":
    main()
