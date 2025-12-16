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
# Plumbing definition (percents as provided)
# - Some tasks are unit-driven overrides
# - Podium tasks are optional
# ---------------------------
PLUMBING_TASKS = [
    ("SAN/VENT", "Initial Sizing", 0.5, None),
    ("SAN/VENT", "Civil Coordination", 1.6, None),
    ("SAN/VENT", "Luxury Amenity", 1.6, None),
    ("SAN/VENT", "Luxury Units ( @ 4hr/unit)", 5.8, "lux_units_4hr"),
    ("SAN/VENT", "Typical Units ( @ 4hr/unit)", 12.4, "typ_units_4hr"),
    ("SAN/VENT", "In building Collections", 9.8, None),
    ("SAN/VENT", "Ground Level Collections", 1.6, None),
    ("SAN/VENT", "Underground Collections", 3.3, None),
    ("SAN/VENT", "Potential Equipment Sizing", 3.3, None),
    ("SAN/VENT", "Isometrics", 7.3, None),
    ("SAN/VENT", "Derm Grease", 1.6, None),

    ("STORM", "Main Roof Sizing", 3.3, None),
    ("STORM", "Podium Sizing", 1.6, "podium_only"),
    ("STORM", "Riser Coordination Luxury", 0.9, None),
    ("STORM", "Offsets", 0.7, None),
    ("STORM", "Riser Coordination Typical", 0.9, None),
    ("STORM", "Riser Offsets", 0.7, None),
    ("STORM", "Podium", 2.5, "podium_only"),
    ("STORM", "Ground Level Collections", 1.6, None),
    ("STORM", "Underground Collections", 3.3, None),
    ("STORM", "Storm Isometrics", 3.3, None),

    ("Domestic", "Initial Sizing", 0.7, None),
    ("Domestic", "Pump Sizing", 0.7, None),
    ("Domestic", "Ground Lvl distribution", 1.8, None),
    ("Domestic", "Amenity distribution", 1.8, None),
    ("Domestic", "Top Level distribution", 1.8, None),
    ("Domestic", "Unit Distribution ( @ 2 hr/unit)", 9.1, "dom_units_2hr"),
    ("Domestic", "Domestic Isometrics", 3.3, None),

    ("Garage Drainage", "Collections", 4.9, None),
    ("Garage Drainage", "Equipment Sizing", 0.7, None),
    ("Garage Drainage", "Civil Coordination", 0.7, None),
    ("Garage Drainage", "Isometric", 3.3, None),

    ("Misc/Details/Schedules", "Misc/Details/Schedules", 3.3, None),
]

def build_plumbing_plan(total_hours: float, podium: bool, lux_units: int, typ_units: int, dom_units: int) -> pd.DataFrame:
    """
    Returns df with columns: Group, Task, Percent, Hours
    Rules:
      - Podium-only tasks included only if podium=True
      - Unit-driven tasks override hours:
          lux_units*4, typ_units*4, dom_units*2
      - Remaining hours distributed to remaining tasks proportional to their % (after removing excluded tasks)
    """
    rows = []
    for grp, task, p, tag in PLUMBING_TASKS:
        if tag == "podium_only" and not podium:
            continue
        rows.append({"Group": grp, "Task": task, "Percent": p, "Tag": tag})

    df = pd.DataFrame(rows)

    # Compute fixed (unit-driven) hours
    fixed = {}
    for _, r in df.iterrows():
        if r["Tag"] == "lux_units_4hr":
            fixed[r["Task"]] = lux_units * 4.0
        elif r["Tag"] == "typ_units_4hr":
            fixed[r["Task"]] = typ_units * 4.0
        elif r["Tag"] == "dom_units_2hr":
            fixed[r["Task"]] = dom_units * 2.0

    df["FixedHours"] = df["Task"].map(fixed).fillna(0.0)

    fixed_total = float(df["FixedHours"].sum())
    remaining = max(total_hours - fixed_total, 0.0)

    # Allocate remaining hours by percent across NON-fixed tasks
    alloc_df = df[df["FixedHours"] == 0.0].copy()
    pct_sum = float(alloc_df["Percent"].sum())

    if pct_sum > 0 and remaining > 0:
        alloc_df["AllocHours"] = remaining * (alloc_df["Percent"] / pct_sum)
    else:
        alloc_df["AllocHours"] = 0.0

    df = df.merge(alloc_df[["Group", "Task", "AllocHours"]], on=["Group", "Task"], how="left")
    df["AllocHours"] = df["AllocHours"].fillna(0.0)

    df["Hours"] = df["FixedHours"] + df["AllocHours"]
    df["Hours"] = df["Hours"].round(1)

    # Recompute effective percent of total hours (for display)
    if total_hours > 0:
        df["Effective %"] = (df["Hours"] / total_hours * 100.0).round(1)
    else:
        df["Effective %"] = 0.0

    df = df[["Group", "Task", "Percent", "Hours", "Effective %"]]
    return df

def main():
    st.set_page_config(page_title="Electrical + Plumbing Work Plan Generator", layout="wide")
    st.title("Electrical + Plumbing Work Plan Generator — Hours & Fees")

    # -----------------------------
    # Sidebar
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

        st.divider()
        st.header("Rate Inputs")
        base_raw_rate = st.number_input("Base Raw Rate ($/hr)", min_value=0.0, value=56.0, step=1.0)
        multiplier = st.number_input("Multiplier", min_value=0.0, value=3.6, step=0.1, format="%.2f")
        billing_rate = base_raw_rate * multiplier

        st.divider()
        st.header("Plumbing Inputs")
        plumbing_total_hours = st.number_input("Plumbing Total Hours", min_value=0.0, value=550.0, step=10.0)

        podium = st.checkbox("Include Podium (Storm Podium Sizing + Podium)", value=True)

        lux_units = st.number_input("Luxury Units (count) — 4 hr/unit", min_value=0, value=8, step=1)
        typ_units = st.number_input("Typical Units (count) — 4 hr/unit", min_value=0, value=12, step=1)
        dom_units = st.number_input("Domestic Unit Distribution (count) — 2 hr/unit", min_value=0, value=25, step=1)

    # -----------------------------
    # Fee cascade calculations (Electrical target fee)
    # -----------------------------
    arch_fee_dollars = construction_cost * pct(arch_fee_pct)
    mep_fee_dollars = arch_fee_dollars * pct(mep_fee_pct)
    electrical_target_fee = mep_fee_dollars * pct(electrical_fee_pct)

    st.subheader("Design Fee Summary")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown("**Construction Cost**"); st.write(money(construction_cost))
    with c2:
        st.markdown("**Architectural Fee ($)**"); st.write(money(arch_fee_dollars))
    with c3:
        st.markdown("**MEP Fee ($)**"); st.write(money(mep_fee_dollars))
    with c4:
        st.markdown("**Electrical Target Fee ($)**"); st.write(money(electrical_target_fee))

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

    base_total_fee = float(e_df["Hours"].sum()) * billing_rate
    scale = 0.0 if billing_rate <= 0 or base_total_fee <= 0 else (electrical_target_fee / base_total_fee)

    e_df["Hours"] = (e_df["Hours"] * scale).round(1)
    e_df["Fee ($)"] = (e_df["Hours"] * billing_rate).round(0)

    e_total_hours = float(e_df["Hours"].sum())
    e_total_fee = float(e_df["Fee ($)"].sum())

    st.write(
        f"**Electrical hours scaling factor applied:** `{scale:.3f}`  "
        f"(Base total fee @ billing rate was {money(base_total_fee)}; scaled to {money(electrical_target_fee)})"
    )

    # -----------------------------
    # Plumbing plan (percent allocation to Plumbing Total Hours)
    # -----------------------------
    p_df = build_plumbing_plan(
        total_hours=float(plumbing_total_hours),
        podium=bool(podium),
        lux_units=int(lux_units),
        typ_units=int(typ_units),
        dom_units=int(dom_units),
    )
    p_total_hours = float(p_df["Hours"].sum())

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
        st.subheader("Plumbing Work Plan (Hours Allocation)")
        st.caption("Hours are allocated from Plumbing Total Hours using your provided percentages, with unit-based overrides and optional podium items.")

        for grp in p_df["Group"].unique():
            g = p_df[p_df["Group"] == grp].copy()
            g_hours = float(g["Hours"].sum())
            with st.expander(f"{grp} — {g_hours:,.1f} hrs", expanded=False):
                pretty = g[["Task", "Percent", "Hours", "Effective %"]].copy()
                pretty["Percent"] = pretty["Percent"].map(lambda x: f"{x:.1f}%")
                pretty["Effective %"] = pretty["Effective %"].map(lambda x: f"{x:.1f}%")
                st.dataframe(pretty, use_container_width=True, hide_index=True)

        st.markdown(f"### PLUMBING TOTAL\n**{p_total_hours:,.1f} hrs**")

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
