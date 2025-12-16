import re
import streamlit as st
import pandas as pd

# ---------------------------
# Helpers
# ---------------------------
def money(x: float) -> str:
    return f"${x:,.0f}"

def pct(x: float) -> float:
    return x / 100.0

def parse_currency_int(text: str) -> int:
    """Allows commas/spaces/$; returns integer dollars. Decimals ignored."""
    if text is None:
        return 0
    digits = re.sub(r"[^\d]", "", text.strip())
    if digits == "":
        raise ValueError("No digits found")
    return int(digits)

# ---------------------------
# Electrical template (PM embedded)
# ---------------------------
ELECTRICAL_TEMPLATE = [
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

    ("Construction Administration (CA)", "PM: CA coordination & reporting", 8),
    ("Construction Administration (CA)", "Submittal reviews", 34),
    ("Construction Administration (CA)", "Shop drawings", 20),
    ("Construction Administration (CA)", "RFIs", 28),
    ("Construction Administration (CA)", "Site visits", 22),
    ("Construction Administration (CA)", "Change order reviews", 12),
    ("Construction Administration (CA)", "Punchlist support", 12),
    ("Construction Administration (CA)", "As-built review", 10),
]

# ---------------------------
# Plumbing tasks with Phase assignment + % weights (your provided %)
# Notes:
# - "Tag" controls unit-driven items and podium-only items
# - We allocate remaining hours per phase proportional to these percents within the phase
# ---------------------------
PLUMBING_TASKS = [
    # SD
    ("Schematic Design (SD)", "SAN/VENT", "Initial Sizing", 0.5, None),
    ("Schematic Design (SD)", "SAN/VENT", "Civil Coordination", 1.6, None),
    ("Schematic Design (SD)", "SAN/VENT", "Luxury Amenity", 1.6, None),
    ("Schematic Design (SD)", "SAN/VENT", "Luxury Units ( @ 4hr/unit)", 5.8, "lux_units_4hr"),
    ("Schematic Design (SD)", "SAN/VENT", "Typical Units ( @ 4hr/unit)", 12.4, "typ_units_4hr"),
    ("Schematic Design (SD)", "STORM", "Main Roof Sizing", 3.3, None),
    ("Schematic Design (SD)", "STORM", "Podium Sizing", 1.6, "podium_only"),
    ("Schematic Design (SD)", "Domestic", "Initial Sizing", 0.7, None),
    ("Schematic Design (SD)", "Domestic", "Pump Sizing", 0.7, None),

    # DD
    ("Design Development (DD)", "SAN/VENT", "Potential Equipment Sizing", 3.3, None),
    ("Design Development (DD)", "Domestic", "Ground Lvl distribution", 1.8, None),
    ("Design Development (DD)", "Domestic", "Amenity distribution", 1.8, None),
    ("Design Development (DD)", "Domestic", "Top Level distribution", 1.8, None),
    ("Design Development (DD)", "Domestic", "Unit Distribution ( @ 2 hr/unit)", 9.1, "dom_units_2hr"),
    ("Design Development (DD)", "STORM", "Riser Coordination Luxury", 0.9, None),
    ("Design Development (DD)", "STORM", "Riser Coordination Typical", 0.9, None),
    ("Design Development (DD)", "STORM", "Offsets", 0.7, None),
    ("Design Development (DD)", "STORM", "Riser Offsets", 0.7, None),
    ("Design Development (DD)", "STORM", "Podium", 2.5, "podium_only"),

    # CD
    ("Construction Documents (CD)", "SAN/VENT", "In building Collections", 9.8, None),
    ("Construction Documents (CD)", "SAN/VENT", "Ground Level Collections", 1.6, None),
    ("Construction Documents (CD)", "SAN/VENT", "Underground Collections", 3.3, None),
    ("Construction Documents (CD)", "SAN/VENT", "Isometrics", 7.3, None),
    ("Construction Documents (CD)", "SAN/VENT", "Derm Grease", 1.6, None),
    ("Construction Documents (CD)", "STORM", "Ground Level Collections", 1.6, None),
    ("Construction Documents (CD)", "STORM", "Underground Collections", 3.3, None),
    ("Construction Documents (CD)", "STORM", "Storm Isometrics", 3.3, None),
    ("Construction Documents (CD)", "Domestic", "Domestic Isometrics", 3.3, None),
    ("Construction Documents (CD)", "Garage Drainage", "Collections", 4.9, None),
    ("Construction Documents (CD)", "Garage Drainage", "Equipment Sizing", 0.7, None),
    ("Construction Documents (CD)", "Garage Drainage", "Civil Coordination", 0.7, None),
    ("Construction Documents (CD)", "Garage Drainage", "Isometric", 3.3, None),
    ("Construction Documents (CD)", "Misc/Details/Schedules", "Misc/Details/Schedules", 3.3, None),

    # CA (not in your list, but requested SD/DD/CD/CA breakdown)
    # These are placeholders so CA can carry a standard % of effort.
    ("Construction Administration (CA)", "CA", "Submittals / RFIs / Site Support", 0.0, "ca_bucket"),
]

def build_plumbing_plan(
    total_hours: float,
    podium: bool,
    lux_units: int,
    typ_units: int,
    dom_units: int,
    phase_weights: dict,
) -> pd.DataFrame:
    """
    Returns df: Phase, Group, Task, Base%, Hours
    Process:
      1) Filter podium-only tasks
      2) Compute fixed hours (unit-driven tasks) and assign to their phase
      3) Compute remaining hours = total - fixed_total
      4) Allocate remaining hours to phases by phase_weights (normalized)
      5) Within each phase, distribute that phase's remaining hours across that phase's non-fixed tasks
         proportionally to their Base% (within that phase)
      6) Add fixed hours back to each task
    """
    rows = []
    for phase, group, task, base_pct, tag in PLUMBING_TASKS:
        if tag == "podium_only" and not podium:
            continue
        rows.append({"Phase": phase, "Group": group, "Task": task, "Base%": float(base_pct), "Tag": tag})
    df = pd.DataFrame(rows)

    # Fixed/unit-driven hours
    def fixed_hours_for_row(r):
        if r["Tag"] == "lux_units_4hr":
            return float(lux_units) * 4.0
        if r["Tag"] == "typ_units_4hr":
            return float(typ_units) * 4.0
        if r["Tag"] == "dom_units_2hr":
            return float(dom_units) * 2.0
        return 0.0

    df["FixedHours"] = df.apply(fixed_hours_for_row, axis=1)

    fixed_total = float(df["FixedHours"].sum())
    remaining_total = max(total_hours - fixed_total, 0.0)

    # Normalize phase weights
    # (Allow user to type anything; we normalize to sum=1; if all zero, fallback)
    phases = ["Schematic Design (SD)", "Design Development (DD)", "Construction Documents (CD)", "Construction Administration (CA)"]
    w = {p: max(float(phase_weights.get(p, 0.0)), 0.0) for p in phases}
    w_sum = sum(w.values())
    if w_sum <= 0:
        w = {p: 1.0 for p in phases}
        w_sum = 4.0
    w = {p: w[p] / w_sum for p in phases}

    # Remaining hours allocated to phases
    remaining_by_phase = {p: remaining_total * w[p] for p in phases}

    df["AllocHours"] = 0.0

    for phase in phases:
        phase_mask = df["Phase"] == phase

        # tasks that are NOT fixed and not CA bucket
        phase_alloc_tasks = df[phase_mask & (df["FixedHours"] == 0.0) & (df["Tag"] != "ca_bucket")].copy()

        # Special case: CA bucket row carries all CA remaining if present
        if phase == "Construction Administration (CA)":
            ca_bucket_mask = phase_mask & (df["Tag"] == "ca_bucket")
            if ca_bucket_mask.any():
                df.loc[ca_bucket_mask, "AllocHours"] = remaining_by_phase[phase]
            else:
                # If no CA bucket row, distribute by Base% like other phases
                pass
            continue

        pct_sum = float(phase_alloc_tasks["Base%"].sum())
        if pct_sum > 0 and remaining_by_phase[phase] > 0:
            alloc = remaining_by_phase[phase] * (phase_alloc_tasks["Base%"] / pct_sum)
            df.loc[phase_alloc_tasks.index, "AllocHours"] = alloc.values

    df["Hours"] = (df["FixedHours"] + df["AllocHours"]).round(1)

    # Helpful display: effective % of plumbing total hours
    df["Effective %"] = 0.0
    if total_hours > 0:
        df["Effective %"] = (df["Hours"] / total_hours * 100.0).round(1)

    # Clean up
    df = df[["Phase", "Group", "Task", "Base%", "Hours", "Effective %"]]
    return df

def main():
    st.set_page_config(page_title="Electrical + Plumbing Work Plan Generator", layout="wide")
    st.title("Electrical + Plumbing Work Plan Generator — Hours & Fees")

    # -----------------------------
    # Sidebar inputs
    # -----------------------------
    with st.sidebar:
        st.header("Construction and % Design Fee Inputs")

        construction_cost_raw = st.text_input(
            "Construction Cost ($)",
            value="10,000,000",
            help="Commas allowed. Decimals ignored.",
        )
        try:
            construction_cost = float(parse_currency_int(construction_cost_raw))
        except ValueError:
            construction_cost = 0.0
            st.error("Construction Cost must contain digits (commas and $ are ok).")

        arch_fee_pct = st.number_input("Architectural Fee (%)", min_value=0.0, value=3.5, step=0.1, format="%.2f")
        mep_fee_pct = st.number_input("Standard MEP Fee (%)", min_value=0.0, value=15.0, step=0.5, format="%.2f")

        electrical_fee_pct = st.number_input("Electrical Fee (%)", min_value=0.0, value=25.0, step=0.5, format="%.2f")
        plumbing_fee_pct = st.number_input("Plumbing Fee (%)", min_value=0.0, value=25.0, step=0.5, format="%.2f")

        st.divider()
        st.header("Rate Inputs")
        base_raw_rate = st.number_input("Base Raw Rate ($/hr)", min_value=0.0, value=56.0, step=1.0)
        multiplier = st.number_input("Multiplier", min_value=0.0, value=3.6, step=0.1, format="%.2f")
        billing_rate = base_raw_rate * multiplier

        st.divider()
        st.header("Plumbing Inputs")
        podium = st.checkbox("Include Podium (Storm Podium Sizing + Podium)", value=True)
        lux_units = st.number_input("Luxury Units (count) — 4 hr/unit", min_value=0, value=8, step=1)
        typ_units = st.number_input("Typical Units (count) — 4 hr/unit", min_value=0, value=12, step=1)
        dom_units = st.number_input("Domestic Unit Distribution (count) — 2 hr/unit", min_value=0, value=25, step=1)

        st.divider()
        st.header("Plumbing Phase % Breakdown (editable)")
        # Defaults = a common “standard” split; edit anytime
        p_sd = st.number_input("Plumbing SD (%)", min_value=0.0, value=20.0, step=1.0, format="%.1f")
        p_dd = st.number_input("Plumbing DD (%)", min_value=0.0, value=25.0, step=1.0, format="%.1f")
        p_cd = st.number_input("Plumbing CD (%)", min_value=0.0, value=40.0, step=1.0, format="%.1f")
        p_ca = st.number_input("Plumbing CA (%)", min_value=0.0, value=15.0, step=1.0, format="%.1f")

    # -----------------------------
    # Fee cascade calculations
    # -----------------------------
    arch_fee_dollars = construction_cost * pct(arch_fee_pct)
    mep_fee_dollars = arch_fee_dollars * pct(mep_fee_pct)

    electrical_target_fee = mep_fee_dollars * pct(electrical_fee_pct)
    plumbing_target_fee = mep_fee_dollars * pct(plumbing_fee_pct)

    # Plumbing total hours derived from plumbing target fee and billing rate
    plumbing_total_hours = 0.0 if billing_rate <= 0 else (plumbing_target_fee / billing_rate)

    # -----------------------------
    # Summary
    # -----------------------------
    st.subheader("Design Fee Summary")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown("**Construction Cost**"); st.write(money(construction_cost))
    with c2:
        st.markdown("**Architectural Fee ($)**"); st.write(money(arch_fee_dollars))
    with c3:
        st.markdown("**MEP Fee ($)**"); st.write(money(mep_fee_dollars))
    with c4:
        st.markdown("**Electrical Target Fee ($)**"); st.write(money(electrical_target_fee))
    with c5:
        st.markdown("**Plumbing Target Fee ($)**"); st.write(money(plumbing_target_fee))

    st.write(
        f"**Base Raw Rate:** {money(base_raw_rate)}/hr  |  "
        f"**Multiplier:** {multiplier:.2f}  |  "
        f"**Billing Rate Used:** {money(billing_rate)}/hr"
    )

    # -----------------------------
    # Electrical plan (scaled to Electrical Target Fee)
    # -----------------------------
    e_df = pd.DataFrame(ELECTRICAL_TEMPLATE, columns=["Phase", "Task", "Base Hours"])
    e_df["Hours"] = e_df["Base Hours"].astype(float)

    e_base_total_fee = float(e_df["Hours"].sum()) * billing_rate
    e_scale = 0.0 if billing_rate <= 0 or e_base_total_fee <= 0 else (electrical_target_fee / e_base_total_fee)

    e_df["Hours"] = (e_df["Hours"] * e_scale).round(1)
    e_df["Fee ($)"] = (e_df["Hours"] * billing_rate).round(0)

    e_total_hours = float(e_df["Hours"].sum())
    e_total_fee = float(e_df["Fee ($)"].sum())

    st.write(
        f"**Electrical hours scaling factor applied:** `{e_scale:.3f}`  "
        f"(Base total fee @ billing rate was {money(e_base_total_fee)}; scaled to {money(electrical_target_fee)})"
    )

    # -----------------------------
    # Plumbing plan (organized into SD/DD/CD/CA)
    # -----------------------------
    phase_weights = {
        "Schematic Design (SD)": p_sd,
        "Design Development (DD)": p_dd,
        "Construction Documents (CD)": p_cd,
        "Construction Administration (CA)": p_ca,
    }

    p_df = build_plumbing_plan(
        total_hours=float(plumbing_total_hours),
        podium=bool(podium),
        lux_units=int(lux_units),
        typ_units=int(typ_units),
        dom_units=int(dom_units),
        phase_weights=phase_weights,
    )

    # Add plumbing fees (using same billing rate) so plumbing matches “hours & fees” style
    p_df["Fee ($)"] = (p_df["Hours"] * billing_rate).round(0)

    p_total_hours = float(p_df["Hours"].sum())
    p_total_fee = float(p_df["Fee ($)"].sum())

    # -----------------------------
    # Show side-by-side
    # -----------------------------
    st.divider()
    left, right = st.columns(2)

    with left:
        st.subheader("Electrical Work Plan")
        for phase in e_df["Phase"].unique():
            phase_df = e_df[e_df["Phase"] == phase][["Task", "Hours", "Fee ($)"]].copy()
            phase_hours = float(phase_df["Hours"].sum())
            phase_fee = float(phase_df["Fee ($)"].sum())
            with st.expander(f"{phase} — {phase_hours:,.1f} hrs | {money(phase_fee)}", expanded=False):
                pretty = phase_df.copy()
                pretty["Fee ($)"] = pretty["Fee ($)"].apply(lambda v: money(float(v)))
                st.dataframe(pretty, use_container_width=True, hide_index=True)

        st.markdown(f"### ELECTRICAL TOTAL\n**{e_total_hours:,.1f} hrs**  |  **{money(e_total_fee)}**")

    with right:
        st.subheader("Plumbing Work Plan")
        st.caption("Plumbing total hours are derived from Plumbing Target Fee ÷ Billing Rate, then allocated into SD/DD/CD/CA by your phase % breakdown.")

        for phase in p_df["Phase"].unique():
            phase_df = p_df[p_df["Phase"] == phase].copy()
            phase_hours = float(phase_df["Hours"].sum())
            phase_fee = float(phase_df["Fee ($)"].sum())

            with st.expander(f"{phase} — {phase_hours:,.1f} hrs | {money(phase_fee)}", expanded=False):
                pretty = phase_df[["Group", "Task", "Base%", "Hours", "Fee ($)", "Effective %"]].copy()
                pretty["Base%"] = pretty["Base%"].map(lambda x: f"{x:.1f}%")
                pretty["Effective %"] = pretty["Effective %"].map(lambda x: f"{x:.1f}%")
                pretty["Fee ($)"] = pretty["Fee ($)"].apply(lambda v: money(float(v)))
                st.dataframe(pretty, use_container_width=True, hide_index=True)

        st.markdown(f"### PLUMBING TOTAL\n**{p_total_hours:,.1f} hrs**  |  **{money(p_total_fee)}**")

    # -----------------------------
    # Downloads
    # -----------------------------
    st.divider()
    d1, d2 = st.columns(2)

    with d1:
        csv_e = e_df[["Phase", "Task", "Hours", "Fee ($)"]].to_csv(index=False)
        st.download_button("Download Electrical CSV", data=csv_e, file_name="electrical_work_plan.csv", mime="text/csv")

    with d2:
        csv_p = p_df.to_csv(index=False)
        st.download_button("Download Plumbing CSV", data=csv_p, file_name="plumbing_work_plan.csv", mime="text/csv")


if __name__ == "__main__":
    main()
