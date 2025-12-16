import streamlit as st
import pandas as pd

# -----------------------------
# Template data (edit as needed)
# -----------------------------
TEMPLATE = [
    ("Project Management / QAQC", "Project kickoff meetings", 10),
    ("Project Management / QAQC", "Schedule development & tracking", 8),
    ("Project Management / QAQC", "Ongoing client coordination", 18),
    ("Project Management / QAQC", "MEP coordination", 14),
    ("Project Management / QAQC", "Fee & scope management", 8),
    ("Project Management / QAQC", "Internal design reviews", 12),
    ("Project Management / QAQC", "Senior QA/QC reviews", 14),
    ("Project Management / QAQC", "Closeout & lessons learned", 8),

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

    ("Design Development (DD)", "Updated load calculations", 14),
    ("Design Development (DD)", "Power plans – typical units", 24),
    ("Design Development (DD)", "Power plans – common areas", 22),
    ("Design Development (DD)", "Lighting layouts & controls", 22),
    ("Design Development (DD)", "Equipment room layouts", 12),
    ("Design Development (DD)", "Metering strategy", 10),
    ("Design Development (DD)", "Panel schedules (DD level)", 14),
    ("Design Development (DD)", "Riser & one-line refinement", 14),
    ("Design Development (DD)", "Arch coordination", 16),
    ("Design Development (DD)", "Mechanical coordination", 12),
    ("Design Development (DD)", "Code compliance review", 8),
    ("Design Development (DD)", "DD review & revisions", 14),

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
    ("Construction Documents (CD)", "Discipline coordination", 20),
    ("Construction Documents (CD)", "Internal QA/QC", 18),
    ("Construction Documents (CD)", "Permit set issuance", 12),

    ("Permitting / AHJ", "Permit support", 6),
    ("Permitting / AHJ", "Plan check review", 10),
    ("Permitting / AHJ", "Comment responses", 14),
    ("Permitting / AHJ", "Drawing revisions", 12),
    ("Permitting / AHJ", "AHJ coordination", 4),

    ("Bidding", "Contractor RFIs", 16),
    ("Bidding", "Addenda", 14),
    ("Bidding", "VE reviews", 8),
    ("Bidding", "Bid evaluation support", 8),

    ("Construction Administration", "Submittal reviews", 34),
    ("Construction Administration", "Shop drawings", 20),
    ("Construction Administration", "RFIs", 28),
    ("Construction Administration", "Site visits", 22),
    ("Construction Administration", "Change order reviews", 12),
    ("Construction Administration", "Punchlist support", 12),
    ("Construction Administration", "As-built review", 10),
]


def money(x: float) -> str:
    return f"${x:,.0f}"


def main():
    st.set_page_config(page_title="Work Plan Generator", layout="wide")
    st.title("Work Plan Generator — Hours & Fees")

    with st.sidebar:
        st.header("Inputs")

        standard_rate = st.number_input("Standard Rate ($/hr)", min_value=0.0, value=150.0, step=5.0)
        multiplier = st.number_input("Multiplier", min_value=0.0, value=1.0, step=0.05, format="%.2f")
        billing_rate = standard_rate * multiplier

        st.caption("Optional: Enter a target fee to auto-scale hours.")
        target_fee = st.number_input("Target Fee ($) (optional)", min_value=0.0, value=0.0, step=1000.0)

        st.divider()
        st.write(f"**Billing Rate Used:** {money(billing_rate)}/hr")

    # Build base dataframe
    df = pd.DataFrame(TEMPLATE, columns=["Phase", "Task", "Base Hours"])
    df["Hours"] = df["Base Hours"].astype(float)

    # If target fee provided, scale hours to match budget
    base_total_hours = df["Hours"].sum()
    base_total_fee = base_total_hours * billing_rate

    if target_fee and billing_rate > 0:
        # Scale hours proportionally to hit the target fee
        scale = target_fee / base_total_fee if base_total_fee > 0 else 0.0
        df["Hours"] = df["Hours"] * scale
    else:
        scale = 1.0

    # Fee calc
    df["Fee ($)"] = df["Hours"] * billing_rate

    # Round hours reasonably (you can change this)
    df["Hours"] = df["Hours"].round(1)
    df["Fee ($)"] = df["Fee ($)"].round(0)

    # Phase subtotals
    subtotals = (
        df.groupby("Phase", as_index=False)[["Hours", "Fee ($)"]]
        .sum()
        .rename(columns={"Hours": "Phase Hours", "Fee ($)": "Phase Fee ($)"})
    )

    total_hours = float(df["Hours"].sum())
    total_fee = float(df["Fee ($)"].sum())

    # Display header info
    st.subheader("Electrical Detailed Task Plan — Hours & Fees")
    st.write(f"**Billing Rate Used:** {money(billing_rate)}/hr")
    if target_fee and billing_rate > 0:
        st.write(
            f"**Target Fee:** {money(target_fee)}  |  "
            f"**Scale Applied to Hours:** {scale:.3f}"
        )

    # Pretty display table with subtotal rows inserted
    display_rows = []
    for phase in df["Phase"].unique():
        phase_rows = df[df["Phase"] == phase].copy()
        for _, r in phase_rows.iterrows():
            display_rows.append(
                {
                    "Phase": r["Phase"],
                    "Task": r["Task"],
                    "Hours": r["Hours"],
                    "Fee ($)": r["Fee ($)"],
                }
            )

        # Add subtotal line
        s = subtotals[subtotals["Phase"] == phase].iloc[0]
        display_rows.append(
            {
                "Phase": f"{phase} Subtotal",
                "Task": "",
                "Hours": round(float(s["Phase Hours"]), 1),
                "Fee ($)": round(float(s["Phase Fee ($)"]), 0),
            }
        )

    out = pd.DataFrame(display_rows)

    # Format money for display (keep numeric separately for downloads)
    out_display = out.copy()
    out_display["Fee ($)"] = out_display["Fee ($)"].apply(lambda v: money(float(v)) if pd.notna(v) else "")
    out_display["Hours"] = out_display["Hours"].apply(lambda v: f"{float(v):,.1f}" if pd.notna(v) and v != "" else "")

    st.dataframe(out_display, use_container_width=True, hide_index=True)

    st.markdown(
        f"### TOTAL LABOR\n"
        f"**{total_hours:,.1f} hrs**  |  **{money(total_fee)}**"
    )

    # Downloads
    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        csv = out.to_csv(index=False)
        st.download_button(
            "Download CSV (with subtotal rows)",
            data=csv,
            file_name="work_plan.csv",
            mime="text/csv",
        )

    with col2:
        # a clean "tasks only" export (no subtotals)
        tasks_only = df[["Phase", "Task", "Hours", "Fee ($)"]].copy()
        tasks_only_csv = tasks_only.to_csv(index=False)
        st.download_button(
            "Download CSV (tasks only)",
            data=tasks_only_csv,
            file_name="work_plan_tasks_only.csv",
            mime="text/csv",
        )

    st.caption("Tip: Edit TEMPLATE in the code to match your typical scope/tasks.")


if __name__ == "__main__":
    main()
