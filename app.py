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
    """
    template_rows: list of dicts with keys: Phase, Task, BaseHours
    Allocates target_fee into phases using phase_split (normalized).
    Within each phase, distributes phase-hours across tasks proportional to BaseHours.
    Returns df with columns Phase, Task, Hours, Fee ($)
    """
    phases = list(phase_split.keys())
    phase_split_n = normalize_phase_split(phase_split)

    df = pd.DataFrame(template_rows).copy()
    df = df[df["BaseHours"] > 0].copy()

    # Ensure each phase has at least one row so phase fee isn't lost
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
        if base_sum <= 0:
            continue
        p_df["Hours"] = p_df["BaseHours"] / base_sum * phase_hours[p]
        p_df["Fee ($)"] = p_df["Hours"] * billing_rate
        out_rows.append(p_df[["Phase", "Task", "Hours", "Fee ($)"]])

    out = pd.concat(out_rows, ignore_index=True)
    out["Hours"] = out["Hours"].round(1)
    out["Fee ($)"] = out["Fee ($)"].round(0)
    return out

# -----------------------------
# Fixed discipline splits (of MEP fee)
# -----------------------------
ELECTRICAL_BASE_PCT = 28.0
PLUMBING_BASE_PCT = 24.0

# -----------------------------
# Electrical tasks (your detailed list, organized into SD/DD/CD/Bidding/CA)
# -----------------------------
ELECTRICAL_ROWS = []

# SD
_sd = [
    ("Utility research & service availability", 10),
    ("Preliminary load calculations", 14),
    ("Service & distribution concepts", 16),
    ("Electrical room & shaft planning", 12),
    ("Preliminary risers / one-lines", 18),
    ("Typical unit power & lighting concepts", 16),
    ("Common area electrical concepts", 12),
    ("EV charging assumptions", 8),
    ("Life safety & code analysis", 10),
    ("Basis of Design narrative", 12),
    ("SD review & revisions", 10),
]
_sd_pm = [
    ("PM: kickoff meetings / coordination", 10),
    ("PM: schedule tracking", 6),
    ("PM: client coordination (SD)", 8),
    ("PM: internal reviews / QA", 6),
]
for task, hrs in _sd_pm + _sd:
    ELECTRICAL_ROWS.append({"Phase": "SD", "Task": task, "BaseHours": float(hrs)})

# DD
_dd = [
    ("Updated load calculations", 14),
    ("Power plans – typical units", 24),
    ("Power plans – common areas", 22),
    ("Lighting layouts & controls", 22),
    ("Equipment room layouts", 12),
    ("Metering strategy", 10),
    ("Panel schedules (DD level)", 14),
    ("Riser & one-line refinement", 14),
    ("Arch coordination", 16),
    ("Mechanical coordination", 12),
    ("Code compliance review", 8),
    ("DD review & revisions", 14),
]
_dd_pm = [
    ("PM: client coordination (DD)", 8),
    ("PM: discipline coordination (DD)", 8),
    ("PM: internal design reviews (DD)", 6),
]
for task, hrs in _dd_pm + _dd:
    ELECTRICAL_ROWS.append({"Phase": "DD", "Task": task, "BaseHours": float(hrs)})

# CD (+ Permitting/AHJ mapped into CD)
_cd = [
    ("Final unit power plans", 36),
    ("Final common area power plans", 30),
    ("Lighting plans & controls", 32),
    ("Emergency / life safety systems", 20),
    ("Final risers & one-lines", 26),
    ("Final load calculations", 12),
    ("Panel schedules (final)", 28),
    ("Details & diagrams", 18),
    ("Grounding & bonding", 10),
    ("Specs & general notes", 14),
    ("Discipline coordination", 20),
    ("Internal QA/QC", 18),
    ("Permit set issuance", 12),
    ("Permit support", 6),
    ("Plan check review", 10),
    ("Comment responses", 14),
    ("Drawing revisions (permit comments)", 12),
    ("AHJ coordination", 4),
]
_cd_pm = [
    ("PM: issue management / meetings (CD)", 10),
    ("PM: fee & scope tracking (CD)", 6),
]
for task, hrs in _cd_pm + _cd:
    ELECTRICAL_ROWS.append({"Phase": "CD", "Task": task, "BaseHours": float(hrs)})

# Bidding
_bid = [
    ("Contractor RFIs", 16),
    ("Addenda", 14),
    ("VE reviews", 8),
    ("Bid evaluation support", 8),
]
for task, hrs in _bid:
    ELECTRICAL_ROWS.append({"Phase": "Bidding", "Task": task, "BaseHours": float(hrs)})

# CA
_ca = [
    ("Submittal reviews", 34),
    ("Shop drawings", 20),
    ("RFIs", 28),
    ("Site visits", 22),
    ("Change order reviews", 12),
    ("Punchlist support", 12),
    ("As-built review", 10),
]
_ca_pm = [
    ("PM: CA coordination & reporting", 12),
]
for task, hrs in _ca_pm + _ca:
    ELECTRICAL_ROWS.append({"Phase": "CA", "Task": task, "BaseHours": float(hrs)})

# -----------------------------
# Plumbing base tasks (your list), organized into SD/DD/CD + placeholders for Bidding/CA
# Unit-driven tasks override BaseHours:
#   - Luxury Units: lux_units*4
#   - Typical Units: typ_units*4
#   - Unit Distribution: dom_units*2
# Podium checkbox controls:
#   - STORM - Podium Sizing
#   - STORM - Podium
# -----------------------------
PLUMBING_BASE = [
    # SD
    ("SD", "SAN/VENT - Initial Sizing", 3, None),
    ("SD", "SAN/VENT - Civil Coordination", 9, None),
    ("SD", "SAN/VENT - Luxury Amenity", 9, None),
    ("SD", "SAN/VENT - Luxury Units (4 hr/unit)", 32, "lux_units_4hr"),
    ("SD", "SAN/VENT - Typical Units (4 hr/unit)", 68, "typ_units_4hr"),
    ("SD", "STORM - Main Roof Sizing", 18, None),
    ("SD", "STORM - Podium Sizing", 9, "podium_only"),
    ("SD", "Domestic - Initial Sizing", 4, None),
    ("SD", "Domestic - Pump Sizing", 4, None),

    # DD
    ("DD", "SAN/VENT - Potential Equipment Sizing", 18, None),
    ("DD", "STORM - Riser Coordination Luxury", 5, None),
    ("DD", "STORM - Offsets", 4, None),
    ("DD", "STORM - Riser Coordination Typical", 5, None),
    ("DD", "STORM - Riser Offsets", 4, None),
    ("DD", "STORM - Podium", 14, "podium_only"),
    ("DD", "Domestic - Ground Lvl distribution", 10, None),
    ("DD", "Domestic - Amenity distribution", 10, None),
    ("DD", "Domestic - Top Level distribution", 10, None),
    ("DD", "Domestic - Unit Distribution (2 hr/unit)", 50, "dom_units_2hr"),

    # CD
    ("CD", "SAN/VENT - In building Collections", 54, None),
    ("CD", "SAN/VENT - Ground Level Collections", 9, None),
    ("CD", "SAN/VENT - Underground Collections", 18, None),
    ("CD", "SAN/VENT - Isometrics", 40, None),
    ("CD", "SAN/VENT - Derm Grease", 9, None),
    ("CD", "STORM - Ground Level Collections", 9, None),
    ("CD", "STORM - Underground Collections", 18, None),
    ("CD", "STORM - Storm Isometrics", 18, None),
    ("CD", "Domestic - Domestic Isometrics", 18, None),
    ("CD", "Garage Drainage - Collections", 27, None),
    ("CD", "Garage Drainage - Equipment Sizing", 4, None),
    ("CD", "Garage Drainage - Civil Coordination", 4, None),
    ("CD", "Garage Drainage - Isometric", 18, None),
    ("CD", "Misc/Details/Schedules", 18, None),

    # Bidding / CA placeholders so the phase split works cleanly
    ("Bidding", "Bidding support (Plumbing)", 10, None),
    ("CA", "Submittals / RFIs / site support (Plumbing)", 60, None),
]

def build_plumbing_rows(podium: bool, lux_units: int, typ_units: int, dom_units: int):
    rows = []
    for phase, task, hrs, tag in PLUMBING_BASE:
        if tag == "podium_only" and not podium:
            continue

        base_hrs = float(hrs)
        if tag == "lux_units_4hr":
            base_hrs = float(lux_units) * 4.0
        elif tag == "typ_units_4hr":
            base_hrs = float(typ_units) * 4.0
        elif tag == "dom_units_2hr":
            base_hrs = float(dom_units) * 2.0

        rows.append({"Phase": phase, "Task": task, "BaseHours": base_hrs})
    return rows

# -----------------------------
# App
# -----------------------------
def main():
    st.set_page_config(page_title="MEP Work Plan Generator", layout="wide")
    st.title("Electrical + Plumbing Work Plan Generator — Hours & Fees")

    # Sidebar now only has the “global” stuff (as in your markup request)
    with st.sidebar:
        st.header("Construction and % Design Fee Inputs")

        cost_raw = st.text_input("Construction Cost ($)", "10,000,000")
        try:
            construction_cost = float(parse_currency_int(cost_raw))
        except ValueError:
            construction_cost = 0.0
            st.error("Construction Cost must contain digits (commas and $ are ok).")

        arch_fee_pct = st.number_input("Architectural Fee (%)", min_value=0.0, value=3.5, step=0.1, format="%.2f")
        mep_fee_pct = st.number_input("Standard MEP Fee (%)", min_value=0.0, value=15.0, step=0.5, format="%.2f")

        st.divider()
        st.header("Rate Inputs")
        base_raw_rate = st.number_input("Base Raw Rate ($/hr)", min_value=0.0, value=56.0, step=1.0)
        multiplier = st.number_input("Multiplier", min_value=0.0, value=3.6, step=0.1, format="%.2f")
        billing_rate = base_raw_rate * multiplier

    # -----------------------------
    # Main-page: Design Phase Fee % Split (moved out of sidebar, compact)
    # -----------------------------
    st.subheader("Design Phase Fee % Split")
    s1, s2, s3, s4, s5 = st.columns([1, 1, 1, 1, 1])

    with s1:
        st.caption("SD (%)")
        sd_pct = st.number_input("", min_value=0.0, value=12.0, step=0.5, format="%.1f", key="sd_pct_main", label_visibility="collapsed")
    with s2:
        st.caption("DD (%)")
        dd_pct = st.number_input("", min_value=0.0, value=40.0, step=0.5, format="%.1f", key="dd_pct_main", label_visibility="collapsed")
    with s3:
        st.caption("CD (%)")
        cd_pct = st.number_input("", min_value=0.0, value=28.0, step=0.5, format="%.1f", key="cd_pct_main", label_visibility="collapsed")
    with s4:
        st.caption("Bidding (%)")
        bid_pct = st.number_input("", min_value=0.0, value=1.5, step=0.1, format="%.1f", key="bid_pct_main", label_visibility="collapsed")
    with s5:
        st.caption("CA (%)")
        ca_pct = st.number_input("", min_value=0.0, value=18.5, step=0.5, format="%.1f", key="ca_pct_main", label_visibility="collapsed")

    phase_split = {"SD": sd_pct, "DD": dd_pct, "CD": cd_pct, "Bidding": bid_pct, "CA": ca_pct}
    phase_split_n = normalize_phase_split(phase_split)
    normalized_sum = sum(phase_split_n.values()) * 100.0
    st.caption(f"Phase split normalized to 100% (current total after normalization: {normalized_sum:.1f}%).")

    # -----------------------------
    # Fee cascade
    # -----------------------------
    arch_fee = construction_cost * pct(arch_fee_pct)
    mep_fee = arch_fee * pct(mep_fee_pct)

    electrical_target_fee = mep_fee * pct(ELECTRICAL_BASE_PCT)
    plumbing_target_fee = mep_fee * pct(PLUMBING_BASE_PCT)

    # -----------------------------
    # Summary (ordered)
    # -----------------------------
    st.subheader("Design Fee Summary")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown("**Construction Cost**"); st.write(money(construction_cost))
    with c2:
        st.markdown("**Architectural Fee**"); st.write(money(arch_fee))
    with c3:
        st.markdown("**MEP Fee**"); st.write(money(mep_fee))
    with c4:
        st.markdown("**Electrical Fee (28% of MEP)**"); st.write(money(electrical_target_fee))
    with c5:
        st.markdown("**Plumbing Fee (24% of MEP)**"); st.write(money(plumbing_target_fee))

    st.write(
        f"**Billing Rate Used:** {money(billing_rate)}/hr "
        f"(Base {money(base_raw_rate)}/hr × {multiplier:.2f})"
    )

    st.divider()
    left, right = st.columns(2)

    # -----------------------------
    # Plumbing inputs moved next to Plumbing header
    # -----------------------------
    with right:
        st.subheader("Plumbing")

        # Compact plumbing inputs (moved from sidebar)
        st.caption("Plumbing Inputs")
        pi1, pi2, pi3, pi4 = st.columns([1.2, 1, 1, 1])
        with pi1:
            podium = st.checkbox("Include Podium", value=True)
        with pi2:
            st.caption("Luxury units")
            lux_units = st.number_input("", min_value=0, value=8, step=1, key="lux_units_main", label_visibility="collapsed")
        with pi3:
            st.caption("Typical units")
            typ_units = st.number_input("", min_value=0, value=12, step=1, key="typ_units_main", label_visibility="collapsed")
        with pi4:
            st.caption("Domestic units")
            dom_units = st.number_input("", min_value=0, value=25, step=1, key="dom_units_main", label_visibility="collapsed")

        # Build plumbing plan
        p_rows = build_plumbing_rows(podium=podium, lux_units=int(lux_units), typ_units=int(typ_units), dom_units=int(dom_units))
        p_df = build_phase_scaled_plan(p_rows, plumbing_target_fee, billing_rate, phase_split)

        # Display plumbing phases
        for phase in ["SD", "DD", "CD", "Bidding", "CA"]:
            dfp = p_df[p_df["Phase"] == phase].copy()
            if dfp.empty:
                continue
            hrs = float(dfp["Hours"].sum())
            fee = float(dfp["Fee ($)"].sum())
            with st.expander(f"{phase} — {hrs:,.1f} hrs | {money(fee)}", expanded=False):
                pretty = dfp[["Task", "Hours", "Fee ($)"]].copy()
                pretty["Fee ($)"] = pretty["Fee ($)"].apply(lambda v: money(float(v)))
                st.dataframe(pretty, use_container_width=True, hide_index=True)

        st.markdown(
            f"### PLUMBING TOTAL\n"
            f"**{p_df['Hours'].sum():,.1f} hrs**  |  **{money(p_df['Fee ($)'].sum())}**"
        )

        csv_p = p_df.to_csv(index=False)
        st.download_button("Download Plumbing CSV", data=csv_p, file_name="plumbing_work_plan.csv", mime="text/csv")

    # -----------------------------
    # Electrical column (left)
    # -----------------------------
    with left:
        st.subheader("Electrical")

        e_df = build_phase_scaled_plan(ELECTRICAL_ROWS, electrical_target_fee, billing_rate, phase_split)

        for phase in ["SD", "DD", "CD", "Bidding", "CA"]:
            dfp = e_df[e_df["Phase"] == phase].copy()
            if dfp.empty:
                continue
            hrs = float(dfp["Hours"].sum())
            fee = float(dfp["Fee ($)"].sum())
            with st.expander(f"{phase} — {hrs:,.1f} hrs | {money(fee)}", expanded=False):
                pretty = dfp[["Task", "Hours", "Fee ($)"]].copy()
                pretty["Fee ($)"] = pretty["Fee ($)"].apply(lambda v: money(float(v)))
                st.dataframe(pretty, use_container_width=True, hide_index=True)

        st.markdown(
            f"### ELECTRICAL TOTAL\n"
            f"**{e_df['Hours'].sum():,.1f} hrs**  |  **{money(e_df['Fee ($)'].sum())}**"
        )

        csv_e = e_df.to_csv(index=False)
        st.download_button("Download Electrical CSV", data=csv_e, file_name="electrical_work_plan.csv", mime="text/csv")


if __name__ == "__main__":
    main()
