import re
import streamlit as st
import pandas as pd

# =============================
# Helpers
# =============================
def money(x):
    return f"${x:,.0f}"

def pct(x):
    return x / 100.0

def parse_currency(text):
    digits = re.sub(r"[^\d]", "", text or "")
    if digits == "":
        raise ValueError
    return float(digits)

def normalize(d):
    total = sum(max(v, 0) for v in d.values())
    if total <= 0:
        n = len(d)
        return {k: 1 / n for k in d}
    return {k: max(v, 0) / total for k, v in d.items()}

# =============================
# Fixed discipline splits
# =============================
ELECTRICAL_PCT = 28.0
PLUMBING_FIRE_PCT = 24.0
FIRE_CARVEOUT = 10.0
PLUMBING_CORE = 90.0

# =============================
# Electrical task baseline
# =============================
ELECTRICAL = [
    # SD
    ("SD", "PM: kickoff / coordination", 10),
    ("SD", "PM: schedule tracking", 6),
    ("SD", "PM: client coordination", 8),
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
    ("DD", "PM: coordination & reviews", 22),
    ("DD", "Updated load calculations", 14),
    ("DD", "Power plans – typical units", 24),
    ("DD", "Power plans – common areas", 22),
    ("DD", "Lighting layouts & controls", 22),
    ("DD", "Equipment room layouts", 12),
    ("DD", "Metering strategy", 10),
    ("DD", "Panel schedules (DD)", 14),
    ("DD", "Riser & one-line refinement", 14),
    ("DD", "Code compliance review", 8),
    ("DD", "DD review & revisions", 14),

    # CD
    ("CD", "PM / QAQC", 16),
    ("CD", "Final unit power plans", 36),
    ("CD", "Final common area power plans", 30),
    ("CD", "Lighting plans & controls", 32),
    ("CD", "Emergency / life safety systems", 20),
    ("CD", "Final risers & one-lines", 26),
    ("CD", "Panel schedules (final)", 28),
    ("CD", "Details & diagrams", 18),
    ("CD", "Specs & general notes", 14),
    ("CD", "Permit set & AHJ responses", 42),

    # Bidding
    ("Bidding", "Bid support / addenda / VE", 46),

    # CA
    ("CA", "PM / coordination", 12),
    ("CA", "Submittals / RFIs / site visits", 104),
]

# =============================
# Plumbing baseline (units + podium logic)
# =============================
PLUMBING = [
    ("SD", "SAN/VENT – Initial sizing", 3),
    ("SD", "SAN/VENT – Civil coordination", 9),
    ("SD", "SAN/VENT – Luxury amenity", 9),
    ("SD", "SAN/VENT – Luxury units", "lux"),
    ("SD", "SAN/VENT – Typical units", "typ"),
    ("SD", "STORM – Main roof sizing", 18),
    ("SD", "STORM – Podium sizing", "podium"),
    ("SD", "Domestic – Initial sizing", 4),

    ("DD", "SAN/VENT – Equipment sizing", 18),
    ("DD", "STORM – Riser coordination", 18),
    ("DD", "STORM – Podium", "podium"),
    ("DD", "Domestic – Distribution layouts", "dom"),

    ("CD", "SAN/VENT – Collections & isometrics", 130),
    ("CD", "STORM – Collections & isometrics", 45),
    ("CD", "Garage drainage", 53),
    ("CD", "Misc / details / schedules", 18),

    ("Bidding", "Bidding support (Plumbing)", 10),
    ("CA", "Submittals / RFIs / site support", 60),
]

# =============================
# Phase scaling engine
# =============================
def build_plan(rows, target_fee, rate, phase_split):
    phase_split = normalize(phase_split)
    df = pd.DataFrame(rows, columns=["Phase", "Task", "Base"])
    out = []

    for phase, frac in phase_split.items():
        phase_fee = target_fee * frac
        phase_hours = phase_fee / rate if rate else 0
        p = df[df.Phase == phase].copy()
        base_sum = p.Base.sum()
        p["Hours"] = p.Base / base_sum * phase_hours
        p["Fee ($)"] = p.Hours * rate
        out.append(p[["Phase", "Task", "Hours", "Fee ($)"]])

    out = pd.concat(out)
    out["Hours"] = out["Hours"].round(1)
    out["Fee ($)"] = out["Fee ($)"].round(0)
    return out

# =============================
# APP
# =============================
st.set_page_config(layout="wide")
st.title("Electrical + Plumbing / Fire Work Plan Generator — Hours & Fees")

# ---------- Sidebar ----------
with st.sidebar:
    st.header("Construction and % Design Fee Inputs")
    cost = parse_currency(st.text_input("Construction Cost ($)", "10,000,000"))
    arch_pct = st.number_input("Architectural Fee (%)", value=3.5)
    mep_pct = st.number_input("MEP Fee (%)", value=15.0)

    st.divider()
    st.header("Rate Inputs")
    raw = st.number_input("Base Raw Rate ($/hr)", value=56.0)
    mult = st.number_input("Multiplier", value=3.6)
    rate = raw * mult

# ---------- Phase Split ----------
st.subheader("Design Phase Fee % Split")
c = st.columns(5)
phase_split = {
    "SD": c[0].number_input("SD (%)", value=12.0),
    "DD": c[1].number_input("DD (%)", value=40.0),
    "CD": c[2].number_input("CD (%)", value=28.0),
    "Bidding": c[3].number_input("Bidding (%)", value=1.5),
    "CA": c[4].number_input("CA (%)", value=18.5),
}

# ---------- Fees ----------
arch_fee = cost * pct(arch_pct)
mep_fee = arch_fee * pct(mep_pct)

elec_fee = mep_fee * pct(ELECTRICAL_PCT)
plumb_fire_fee = mep_fee * pct(PLUMBING_FIRE_PCT)
fire_fee = plumb_fire_fee * pct(FIRE_CARVEOUT)
plumb_fee = plumb_fire_fee * pct(PLUMBING_CORE)

# ---------- Summary ----------
st.subheader("Design Fee Summary")
s = st.columns(5)
s[0].markdown("**Construction Cost**"); s[0].write(money(cost))
s[1].markdown("**Architectural Fee**"); s[1].write(money(arch_fee))
s[2].markdown("**MEP Fee**"); s[2].write(money(mep_fee))
s[3].markdown("**Electrical Fee (28%)**"); s[3].write(money(elec_fee))
s[4].markdown("**Plumbing / Fire Fee (24%)**"); s[4].write(money(plumb_fire_fee))

st.write(f"**Billing Rate Used:** {money(rate)}/hr")

# ---------- Build Electrical ----------
e_rows = [(p, t, h) for p, t, h in ELECTRICAL]
e_df = build_plan(e_rows, elec_fee, rate, phase_split)

# ---------- Plumbing Inputs ----------
right, left = st.columns(2)
with right:
    st.subheader("Plumbing / Fire Inputs")
    podium = st.checkbox("Include Podium", True)
    lux = st.number_input("Luxury units (×4 hr)", 0, 100, 8)
    typ = st.number_input("Typical units (×4 hr)", 0, 200, 12)
    dom = st.number_input("Domestic units (×2 hr)", 0, 300, 25)

# ---------- Build Plumbing ----------
p_rows = []
for phase, task, base in PLUMBING:
    if base == "lux":
        p_rows.append((phase, task, lux * 4))
    elif base == "typ":
        p_rows.append((phase, task, typ * 4))
    elif base == "dom":
        p_rows.append((phase, task, dom * 2))
    elif base == "podium":
        if podium:
            p_rows.append((phase, task, 12))
    else:
        p_rows.append((phase, task, base))

p_df = build_plan(p_rows, plumb_fee, rate, phase_split)

# ---------- Fire rows ----------
fire_rows = [(p, "Fire Protection", 1) for p in phase_split]
f_df = build_plan(fire_rows, fire_fee, rate, phase_split)

pf_df = pd.concat([p_df, f_df])

# ---------- Display ----------
left, right = st.columns(2)

with left:
    st.subheader("Electrical")
    for ph in phase_split:
        d = e_df[e_df.Phase == ph]
        with st.expander(f"{ph} — {d.Hours.sum():.1f} hrs | {money(d['Fee ($)'].sum())}"):
            st.dataframe(d[["Task", "Hours", "Fee ($)"]], hide_index=True)

with right:
    st.subheader("Plumbing / Fire")
    for ph in phase_split:
        d = pf_df[pf_df.Phase == ph]
        with st.expander(f"{ph} — {d.Hours.sum():.1f} hrs | {money(d['Fee ($)'].sum())}"):
            st.dataframe(d[["Task", "Hours", "Fee ($)"]], hide_index=True)
