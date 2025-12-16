import re
import streamlit as st
import pandas as pd

# =============================
# Helpers
# =============================
def money(x: float) -> str:
    return f"${x:,.0f}"

def pct(x: float) -> float:
    return x / 100.0

def parse_currency(text: str) -> float:
    digits = re.sub(r"[^\d]", "", text or "")
    if digits == "":
        raise ValueError("No digits found")
    return float(digits)

def normalize(d: dict) -> dict:
    total = sum(max(v, 0.0) for v in d.values())
    if total <= 0:
        n = len(d)
        return {k: 1.0 / n for k in d}
    return {k: max(v, 0.0) / total for k, v in d.items()}

def build_plan(rows, target_fee: float, rate: float, phase_split: dict) -> pd.DataFrame:
    """
    rows: list of tuples (Phase, Task, BaseHours)
    Allocates target_fee into phases using phase_split (normalized to 100%),
    then distributes each phase's hours across tasks proportional to BaseHours.
    """
    phase_split_n = normalize(phase_split)
    df = pd.DataFrame(rows, columns=["Phase", "Task", "Base"])

    out = []
    for phase, frac in phase_split_n.items():
        phase_fee = target_fee * frac
        phase_hours = (phase_fee / rate) if rate > 0 else 0.0

        p = df[df["Phase"] == phase].copy()
        if p.empty:
            p = pd.DataFrame([{"Phase": phase, "Task": f"{phase} - General", "Base": 1.0}])

        base_sum = float(p["Base"].sum())
        p["Hours"] = (p["Base"] / base_sum * phase_hours) if base_sum > 0 else 0.0
        p["Fee ($)"] = p["Hours"] * rate

        out.append(p[["Phase", "Task", "Hours", "Fee ($)"]])

    out_df = pd.concat(out, ignore_index=True)
    out_df["Hours"] = out_df["Hours"].round(1)
    out_df["Fee ($)"] = out_df["Fee ($)"].round(0)
    return out_df

# =============================
# Tasks (Electrical / Plumbing / Mechanical)
# =============================

ELECTRICAL = [
    # SD
    ("SD", "PM: kickoff meetings / coordination", 10),
    ("SD", "PM: schedule tracking", 6),
    ("SD", "PM: client coordination (SD)", 8),
    ("SD", "PM: internal reviews / QA", 6),
    ("SD", "Utility research & service availability", 10),
    ("SD", "Preliminary load calculations", 14),
    ("SD", "Service & distribution concepts", 16),
    ("SD", "Electrical room & shaft planning", 12),
    ("SD", "Preliminary risers / one-lines", 18),
    ("SD", "Typical unit power & lighting concepts", 16),
    ("SD", "Common area electrical concepts", 12),
    ("SD", "EV charging assumptions", 8),
    ("SD", "Life safety & code analysis", 10),
    ("SD", "Basis of Design narrative", 12),
    ("SD", "SD review & revisions", 10),

    # DD
    ("DD", "PM: client coordination (DD)", 8),
    ("DD", "PM: discipline coordination (DD)", 8),
    ("DD", "PM: internal design reviews (DD)", 6),
    ("DD", "Updated load calculations", 14),
    ("DD", "Power plans – typical units", 24),
    ("DD", "Power plans – common areas", 22),
    ("DD", "Lighting layouts & controls", 22),
    ("DD", "Equipment room layouts", 12),
    ("DD", "Metering strategy", 10),
    ("DD", "Panel schedules (DD level)", 14),
    ("DD", "Riser & one-line refinement", 14),
    ("DD", "Arch coordination", 16),
    ("DD", "Mechanical coordination", 12),
    ("DD", "Code compliance review", 8),
    ("DD", "DD review & revisions", 14),

    # CD (+ permitting in CD)
    ("CD", "PM: issue management / meetings (CD)", 10),
    ("CD", "PM: fee & scope tracking (CD)", 6),
    ("CD", "Final unit power plans", 36),
    ("CD", "Final common area power plans", 30),
    ("CD", "Lighting plans & controls", 32),
    ("CD", "Emergency / life safety systems", 20),
    ("CD", "Final risers & one-lines", 26),
    ("CD", "Final load calculations", 12),
    ("CD", "Panel schedules (final)", 28),
    ("CD", "Details & diagrams", 18),
    ("CD", "Grounding & bonding", 10),
    ("CD", "Specs & general notes", 14),
    ("CD", "Discipline coordination", 20),
    ("CD", "Internal QA/QC", 18),
    ("CD", "Permit set issuance", 12),
    ("CD", "Permit support", 6),
    ("CD", "Plan check review", 10),
    ("CD", "Comment responses", 14),
    ("CD", "Drawing revisions (permit comments)", 12),
    ("CD", "AHJ coordination", 4),

    # Bidding
    ("Bidding", "Contractor RFIs", 16),
    ("Bidding", "Addenda", 14),
    ("Bidding", "VE reviews", 8),
    ("Bidding", "Bid evaluation support", 8),

    # CA
    ("CA", "PM: CA coordination & reporting", 12),
    ("CA", "Submittal reviews", 34),
    ("CA", "Shop drawings", 20),
    ("CA", "RFIs", 28),
    ("CA", "Site visits", 22),
    ("CA", "Change order reviews", 12),
    ("CA", "Punchlist support", 12),
    ("CA", "As-built review", 10),
]

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

    # Bidding / CA placeholders
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

        rows.append((phase, task, base_hrs))
    return rows

# Mechanical tasks from your image (base hours)
MECHANICAL = [
    # SD (total 55)
    ("SD", "Meetings", 12),
    ("SD", "Preliminary load calcs", 18),
    ("SD", "Preliminary sizing/routing", 15),
    ("SD", "SD Narrative", 8),
    ("SD", "QA/QC", 2),

    # DD (total 198)
    ("DD", "Meetings", 20),
    ("DD", "Load calcs", 20),
    ("DD", "Coordination", 10),
    ("DD", "Equipment selection", 15),
    ("DD", "Details/Schedules", 10),
    ("DD", "Chase/Shaft/BOH routing", 15),
    ("DD", "Unit modeling", 60),
    ("DD", "Amenity space modeling", 40),
    ("DD", "QA/QC", 8),

    # CD (total 134)
    ("CD", "Meetings", 16),
    ("CD", "Coordination", 10),
    ("CD", "Equipment selection", 10),
    ("CD", "Details/Schedules", 10),
    ("CD", "BOH routing/detailing", 20),
    ("CD", "Unit modeling/detailing", 40),
    ("CD", "Amenity space modeling", 20),
    ("CD", "QA/QC", 8),

    # Bidding/CPS (total 55)
    ("Bidding", "Meetings", 25),
    ("Bidding", "Coordination", 10),
    ("Bidding", "RFI/Submittals", 20),

    # CA (not provided in image; placeholder so fee split can allocate CA)
    ("CA", "CA Support (submittals/RFIs/site)", 60),
]

# =============================
# App UI
# =============================
st.set_page_config(page_title="MEP Work Plan Generator", layout="wide")
st.title("Electrical + Plumbing / Fire + Mechanical Work Plan Generator — Hours & Fees")

# Sidebar: global inputs
with st.sidebar:
    st.header("Construction and % Design Fee Inputs")

    cost_raw = st.text_input("Construction Cost ($)", "10,000,000")
    try:
        construction_cost = parse_currency(cost_raw)
    except ValueError:
        construction_cost = 0.0
        st.error("Construction Cost must contain digits (commas and $ are ok).")

    arch_fee_pct = st.number_input("Architectural Fee (%)", min_value=0.0, value=3.5, step=0.1, format="%.2f")
    mep_fee_pct = st.number_input("MEP Fee (%)", min_value=0.0, value=15.0, step=0.5, format="%.2f")

    st.divider()
    st.header("Rate Inputs")
    base_raw_rate = st.number_input("Base Raw Rate ($/hr)", min_value=0.0, value=56.0, step=1.0)
    multiplier = st.number_input("Multiplier", min_value=0.0, value=3.6, step=0.1, format="%.2f")
    billing_rate = base_raw_rate * multiplier

# Phase split
st.subheader("Design Phase Fee % Split")
c1, c2, c3, c4, c5 = st.columns(5)
sd_pct = c1.number_input("SD (%)", min_value=0.0, value=12.0, step=0.5, format="%.1f")
dd_pct = c2.number_input("DD (%)", min_value=0.0, value=40.0, step=0.5, format="%.1f")
cd_pct = c3.number_input("CD (%)", min_value=0.0, value=28.0, step=0.5, format="%.1f")
bid_pct = c4.number_input("Bidding (%)", min_value=0.0, value=1.5, step=0.1, format="%.1f")
ca_pct = c5.number_input("CA (%)", min_value=0.0, value=18.5, step=0.5, format="%.1f")
phase_split = {"SD": sd_pct, "DD": dd_pct, "CD": cd_pct, "Bidding": bid_pct, "CA": ca_pct}
st.caption("Phase split auto-normalizes to 100% if entries don’t add to 100.")

# Discipline splits (under phase split)
st.subheader("Discipline % of MEP Fee")
d1, d2, d3 = st.columns(3)
with d1:
    electrical_pct = st.number_input("Electrical (%)", min_value=0.0, value=28.0, step=0.5, format="%.1f")
with d2:
    plumbing_fire_pct = st.number_input("Plumbing / Fire (%)", min_value=0.0, value=24.0, step=0.5, format="%.1f")
with d3:
    mechanical_pct = st.number_input("Mechanical (%)", min_value=0.0, value=48.0, step=0.5, format="%.1f")

# Fee cascade
arch_fee = construction_cost * pct(arch_fee_pct)
mep_fee = arch_fee * pct(mep_fee_pct)

electrical_target_fee = mep_fee * pct(electrical_pct)
plumbing_fire_target_fee = mep_fee * pct(plumbing_fire_pct)
mechanical_target_fee = mep_fee * pct(mechanical_pct)

# Plumbing/Fire carveout
fire_fee = plumbing_fire_target_fee * pct(10.0)
plumbing_fee = plumbing_fire_target_fee - fire_fee

# Fee summary (NO st.metric)
st.subheader("Design Fee Summary")
s1, s2, s3, s4, s5, s6 = st.columns(6)
with s1:
    st.markdown("**Construction Cost**"); st.write(money(construction_cost))
with s2:
    st.markdown("**Architectural Fee**"); st.write(money(arch_fee))
with s3:
    st.markdown("**MEP Fee**"); st.write(money(mep_fee))
with s4:
    st.markdown(f"**Electrical ({electrical_pct:.1f}%)**"); st.write(money(electrical_target_fee))
with s5:
    st.markdown(f"**Plumbing/Fire ({plumbing_fire_pct:.1f}%)**"); st.write(money(plumbing_fire_target_fee))
with s6:
    st.markdown(f"**Mechanical ({mechanical_pct:.1f}%)**"); st.write(money(mechanical_target_fee))

st.write(f"**Billing Rate Used:** {money(billing_rate)}/hr (Base {money(base_raw_rate)}/hr × {multiplier:.2f})")

# Build plans
e_df = build_plan(ELECTRICAL, electrical_target_fee, billing_rate, phase_split)
m_df = build_plan(MECHANICAL, mechanical_target_fee, billing_rate, phase_split)

# 3-column layout
col_e, col_pf, col_m = st.columns(3)

# Electrical section
with col_e:
    st.subheader("Electrical")
    for ph in ["SD", "DD", "CD", "Bidding", "CA"]:
        d = e_df[e_df["Phase"] == ph].copy()
        hrs = float(d["Hours"].sum())
        fee = float(d["Fee ($)"].sum())
        with st.expander(f"{ph} — {hrs:,.1f} hrs | {money(fee)}", expanded=False):
            show = d[["Task", "Hours", "Fee ($)"]].copy()
            show["Fee ($)"] = show["Fee ($)"].apply(lambda v: money(float(v)))
            st.dataframe(show, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown(f"### ELECTRICAL TOTAL\n**{float(e_df['Hours'].sum()):,.1f} hrs** | **{money(float(e_df['Fee ($)'].sum()))}**")
    st.download_button("Download Electrical CSV", data=e_df.to_csv(index=False), file_name="electrical_work_plan.csv", mime="text/csv")

# Plumbing/Fire section (with compact inputs)
with col_pf:
    st.subheader("Plumbing / Fire")
    st.caption("Inputs")
    pi1, pi2, pi3, pi4 = st.columns([1.1, 1, 1, 1])

    with pi1:
        podium = st.checkbox("Include Podium", value=True)
    with pi2:
        st.caption("Luxury units")
        lux_units = st.number_input("", min_value=0, value=8, step=1, key="lux_units", label_visibility="collapsed")
    with pi3:
        st.caption("Typical units")
        typ_units = st.number_input("", min_value=0, value=12, step=1, key="typ_units", label_visibility="collapsed")
    with pi4:
        st.caption("Domestic units")
        dom_units = st.number_input("", min_value=0, value=25, step=1, key="dom_units", label_visibility="collapsed")

    p_rows = build_plumbing_rows(podium=podium, lux_units=int(lux_units), typ_units=int(typ_units), dom_units=int(dom_units))
    p_df = build_plan(p_rows, plumbing_fee, billing_rate, phase_split)

    fire_rows = [(ph, "Fire Protection", 1.0) for ph in phase_split.keys()]
    f_df = build_plan(fire_rows, fire_fee, billing_rate, phase_split)

    pf_df = pd.concat([p_df, f_df], ignore_index=True)

    for ph in ["SD", "DD", "CD", "Bidding", "CA"]:
        d = pf_df[pf_df["Phase"] == ph].copy()
        hrs = float(d["Hours"].sum())
        fee = float(d["Fee ($)"].sum())
        with st.expander(f"{ph} — {hrs:,.1f} hrs | {money(fee)}", expanded=False):
            show = d[["Task", "Hours", "Fee ($)"]].copy()
            show["Fee ($)"] = show["Fee ($)"].apply(lambda v: money(float(v)))
            st.dataframe(show, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown(f"### PLUMBING / FIRE TOTAL\n**{float(pf_df['Hours'].sum()):,.1f} hrs** | **{money(float(pf_df['Fee ($)'].sum()))}**")
    st.download_button("Download Plumbing/Fire CSV", data=pf_df.to_csv(index=False), file_name="plumbing_fire_work_plan.csv", mime="text/csv")

# Mechanical section
with col_m:
    st.subheader("Mechanical")
    for ph in ["SD", "DD", "CD", "Bidding", "CA"]:
        d = m_df[m_df["Phase"] == ph].copy()
        hrs = float(d["Hours"].sum())
        fee = float(d["Fee ($)"].sum())
        with st.expander(f"{ph} — {hrs:,.1f} hrs | {money(fee)}", expanded=False):
            show = d[["Task", "Hours", "Fee ($)"]].copy()
            show["Fee ($)"] = show["Fee ($)"].apply(lambda v: money(float(v)))
            st.dataframe(show, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown(f"### MECHANICAL TOTAL\n**{float(m_df['Hours'].sum()):,.1f} hrs** | **{money(float(m_df['Fee ($)'].sum()))}**")
    st.download_button("Download Mechanical CSV", data=m_df.to_csv(index=False), file_name="mechanical_work_plan.csv", mime="text/csv")
