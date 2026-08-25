import streamlit as st
import pandas as pd
import base64
import os
import io
import json
import re
from datetime import datetime
import pytz
import gspread
from google.oauth2.service_account import Credentials
import warnings
warnings.filterwarnings("ignore")
# ==========================================
# ⚙️ PAGE CONFIG & AUTHENTICATION SETUP
# ==========================================
st.set_page_config(page_title="AMC NTEP - Adverse Outcomes", layout="wide", initial_sidebar_state="collapsed")
india_tz = pytz.timezone('Asia/Kolkata')
def img_to_b64(img_path):
    try:
        with open(img_path, "rb") as img_file: return base64.b64encode(img_file.read()).decode('utf-8')
    except: return ""
if "auth" not in st.session_state: 
    st.session_state.auth = False
    st.session_state.current_user = ""
    st.session_state.role = ""
    st.session_state.target = ""
try:
    df_users = pd.read_csv("users.csv")
    df_users['Username'] = df_users['Username'].astype(str).str.strip().str.upper()
except:
    st.error("⚠️ User Database (users.csv) not found in the repository!")
    st.stop()
# ==========================================
# 🔐 ENTERPRISE LOGIN PAGE
# ==========================================
if not st.session_state.auth:
    b64_amc = img_to_b64("amc.png")
    
    st.markdown("""
    <style>
    .left-panel { background: #0A3A6E; color: white; padding: 40px 30px; border-radius: 15px 0 0 15px; text-align: center; height: 100%;}
    .right-panel { padding: 40px; background: white; border-radius: 0 15px 15px 0; border: 1px solid #e2e8f0; height: 100%; }
    .stTextInput>div>div>input { border-radius: 8px; border: 1px solid #cbd5e1; padding: 12px; }
    .stButton>button { background-color: #0A3A6E; color: white; border-radius: 8px; width: 100%; font-weight: 600; padding: 10px; }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    sp1, login_box, sp2 = st.columns([1, 6, 1])
    
    with login_box:
        l_col, r_col = st.columns([4, 5], gap="small")
        with l_col:
            st.markdown(f"""
            <div class="left-panel">
            <img src="data:image/png;base64,{b64_amc}" width="65" style="margin-bottom:20px; background:white; border-radius:50%; padding:5px;">
            <h2 style="font-size: 24px; font-weight: 600;">AMC · NTEP</h2>
            <p style="font-size: 13px; color: #85B7EB;">Adverse Outcomes & Field Entry Module</p>
            </div>
            """, unsafe_allow_html=True)
            
        with r_col:
            st.markdown("<h3 style='color: #1e293b; font-weight: 600;'>Sign in</h3><br>", unsafe_allow_html=True)
            uname = st.text_input("User ID / Zone Code").strip().upper()
            pwd = st.text_input("Password", type="password").strip()
            
            if st.button("Sign In Securely"):
                user_match = df_users[(df_users['Username'] == uname) & (df_users['Password'].astype(str).str.strip() == pwd)]
                if not user_match.empty: 
                    st.session_state.auth = True
                    st.session_state.current_user = uname
                    st.session_state.role = str(user_match.iloc[0]['Role']).strip().upper()
                    st.session_state.target = str(user_match.iloc[0]['Target']).strip().upper()
                    st.rerun()
                else: 
                    st.error("⚠️ Invalid User ID or Password")
    st.stop()
# ==========================================
# 🟢 MAIN APPLICATION & DATABASE CONNECTIONS
# ==========================================
st.markdown(f"<div style='background-color: #d4edda; color: #155724; padding: 10px; border-radius: 5px; font-weight: bold; margin-bottom: 20px;'>👤 Logged in as: {st.session_state.target} ({st.session_state.role})</div>", unsafe_allow_html=True)
@st.cache_resource
def init_gspread():
    creds_dict = json.loads(st.secrets["google_credentials"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)
client = init_gspread()
NEW_SHEET_URL = "https://docs.google.com/spreadsheets/d/11JHb7Zv4KqV_PAY9REGBVdkLwqBSubvgtSrr1ulGRzA/edit"
try:
    new_sheet = client.open_by_url(NEW_SHEET_URL).sheet1
except Exception as e:
    st.error("Could not connect to the New Google Sheet. Check credentials.")
    st.stop()
@st.cache_data(ttl=10, show_spinner="Syncing Live Data Tracker...")
def get_live_tracker():
    try:
        return pd.DataFrame(new_sheet.get_all_records())
    except:
        return pd.DataFrame()
df_live = get_live_tracker()
@st.cache_data(ttl=600, show_spinner="Calculating Executive Metrics...")
def load_kpi_data():
    import urllib.request
    try:
        url = "https://docs.google.com/spreadsheets/d/1Dfvl87uaZZ12_5F4dhHXTP_u8i9NM9TASWN8wyX18nE/export?format=csv&gid=1898426568"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as response:
            return pd.read_csv(io.BytesIO(response.read()), low_memory=False, dtype=str, on_bad_lines='skip')
    except:
        return pd.DataFrame()
df_this_raw = load_kpi_data()
# ---------------------------------------------------------
# 🧮 CALCULATION ENGINE: YEAR-WISE SUCCESS & DEATH RATES
# ---------------------------------------------------------
success_overall_str, success_years_str = "0%", ""
death_overall_str, death_years_str = "0%", ""
init_death_overall_str, init_death_years_str = "0%", ""
if not df_this_raw.empty:
    def cx(col_letter):
        num = 0
        for c in col_letter.upper(): num = num * 26 + (ord(c) - ord('A') + 1)
        return num - 1
    def get_col_series(df, possible_names, fallback_col_letter):
        for p in possible_names:
            p_clean = re.sub(r'[^A-Z0-9]', '', str(p).upper())
            for c in df.columns:
                c_clean = re.sub(r'[^A-Z0-9]', '', str(c).upper())
                if c_clean == p_clean: return df[c]
        idx = cx(fallback_col_letter)
        if idx < len(df.columns): return df.iloc[:, idx]
        return pd.Series([""] * len(df))
    ep_series = get_col_series(df_this_raw, ['EPISODE ID'], 'M').fillna("").astype(str).str.strip()
    regimen_series = get_col_series(df_this_raw, ['TYPE OF TB REGIMEN'], 'BJ').fillna("").astype(str).str.upper()
    outcome_series = get_col_series(df_this_raw, ['TREATMENT OUTCOME'], 'BK').fillna("").astype(str).str.upper().str.strip()
    
    diag_series = get_col_series(df_this_raw, ['DIAGNOSIS DATE'], 'S').fillna("").astype(str).str.strip()
    init_series = get_col_series(df_this_raw, ['INITIATION DATE'], 'BM').fillna("").astype(str).str.strip()
    out_date_series = get_col_series(df_this_raw, ['OUTCOME DATE'], 'CB').fillna("").astype(str).str.strip()
    df_calc = pd.DataFrame({
        'Valid': ~ep_series.isin(["", "NAN", "NONE", "NULL", "N/A"]),
        'Regimen_Eligible': regimen_series.str.contains("2HRZE/4HRE|2HRZES|4HRE|2HRZE", regex=True, na=False),
        'Is_Success': outcome_series.str.contains("COMPLETE|CURED", regex=True, na=False),
        'Is_Death': outcome_series.str.contains("DIED|DEATH", regex=True, na=False),
        'Init_Year': pd.to_datetime(init_series, errors='coerce').dt.year,
        'Diag_Year': pd.to_datetime(diag_series, errors='coerce').dt.year,
        'Has_Diag': diag_series != "",
        'Has_OutDate': out_date_series != "",
        'No_Init': init_series == ""
    })
    df_calc_init = df_calc[df_calc['Valid'] & df_calc['Regimen_Eligible']].copy()
    total_eligible = len(df_calc_init)
    
    if total_eligible > 0:
        success_overall_str = f"{(df_calc_init['Is_Success'].sum() / total_eligible * 100):.1f}%"
        death_overall_str = f"{(df_calc_init['Is_Death'].sum() / total_eligible * 100):.1f}%"
        
        grp_succ = df_calc_init.groupby('Init_Year')['Is_Success'].agg(['sum', 'count'])
        grp_death = df_calc_init.groupby('Init_Year')['Is_Death'].agg(['sum', 'count'])
        success_years_str = " | ".join([f"{int(y)}: {(r['sum']/r['count']*100):.1f}%" for y, r in grp_succ.iterrows() if pd.notna(y) and r['count'] > 0])
        death_years_str = " | ".join([f"{int(y)}: {(r['sum']/r['count']*100):.1f}%" for y, r in grp_death.iterrows() if pd.notna(y) and r['count'] > 0])
    df_calc_diag = df_calc[df_calc['Valid']].copy()
    df_calc_diag['Is_Initial_Death'] = df_calc_diag['Has_Diag'] & df_calc_diag['Has_OutDate'] & df_calc_diag['No_Init'] & df_calc_diag['Is_Death']
    
    total_diag = len(df_calc_diag)
    if total_diag > 0:
        init_death_overall_str = f"{(df_calc_diag['Is_Initial_Death'].sum() / total_diag * 100):.1f}%"
        grp_init = df_calc_diag.groupby('Diag_Year')['Is_Initial_Death'].agg(['sum', 'count'])
        init_death_years_str = " | ".join([f"{int(y)}: {(r['sum']/r['count']*100):.1f}%" for y, r in grp_init.iterrows() if pd.notna(y) and r['count'] > 0])

total_adverse_count = len(df_live)

# ---------------------------------------------------------
# 🧮 AHMEDABAD RESIDENT COUNT (used by KPI + breakdown card)
# ---------------------------------------------------------
ahmedabad_count = 0
ahmedabad_pct_str = "0%"
if total_adverse_count > 0 and 'ZONE' in df_live.columns:
    ahmedabad_mask = df_live['ZONE'].astype(str).str.upper().str.contains("AHMEDABAD|EAST|WEST|NORTH|SOUTH|CENTRAL|AMC", regex=True, na=False)
    ahmedabad_count = int(ahmedabad_mask.sum())
    ahmedabad_pct_str = f"{int((ahmedabad_count / total_adverse_count) * 100)}%"

# ---------------------------------------------------------
# 🧮 REAL FIELD DATA-ENTRY COLUMNS (English headers)
# These must exist as column headers in your Google Sheet.
# ---------------------------------------------------------
COL_MONTHS_RESIDING     = "Months Residing in Ahmedabad (as of Outcome)"
COL_RESIDED_THROUGHOUT  = "Resided in Ahmedabad Throughout Treatment"
COL_PLACE_OF_DEATH      = "Place of Death"
COL_COMORBIDITY         = "Comorbidity"
COL_STATE_NON_AMC       = "State (If Non-AMC)"
COL_DISTRICT_NON_AMC    = "District (If Non-AMC)"
COL_TRANSFER_REASON     = "Transfer Reason (If Non-AMC)"
COL_TRANSFER_OUT_DATE   = "Transfer Out Date"
COL_REJECT_DATE         = "Reject Date (If Rejected)"
COL_REMARKS             = "Remarks"
COL_SUBMITTED_BY        = "Submitted By"
COL_LAST_UPDATED        = "Last Updated"

REQUIRED_ENTRY_COLS = [
    COL_MONTHS_RESIDING, COL_RESIDED_THROUGHOUT, COL_PLACE_OF_DEATH, COL_COMORBIDITY,
    COL_STATE_NON_AMC, COL_DISTRICT_NON_AMC, COL_TRANSFER_REASON,
    COL_TRANSFER_OUT_DATE, COL_REJECT_DATE, COL_REMARKS,
]
META_ENTRY_COLS = [COL_SUBMITTED_BY, COL_LAST_UPDATED]

COMORBIDITY_OPTIONS = [
    "Diabetes", "Cardiovascular disease", "Hypertension", "COPD", "Asthma",
    "Other lung disease", "Chronic liver disease", "Chronic kidney disease", "Cancer",
    "HIV/AIDS", "Occupational lung disease", "Anaemia", "Mental health disorder",
    "Autoimmune disorder", "Severe malnutrition", "Congenital disorder",
    "Chronic alcoholism", "P/H of COVID-19", "Sickle cell trait or anaemia",
    "Other", "Multiple", "NA",
]
PLACE_OF_DEATH_OPTIONS = ["", "Home", "Government Hospital", "Private Hospital", "In Transit / Enroute", "Other"]
TRANSFER_REASON_OPTIONS = ["", "Migration for Work", "Family Relocation", "Better Treatment Facility", "Other"]
INDIAN_STATES_UTS = [
    "", "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat",
    "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra",
    "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim",
    "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Andaman and Nicobar Islands", "Chandigarh", "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
]

def split_multi(val):
    return [x.strip() for x in str(val).split(",") if x.strip()]

def colnum_to_letter(n):
    letters = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters

# ---------------------------------------------------------
# 🧮 BIFURCATED BREAKDOWNS (Comorbidity / Residency / Transfer-Reject)
# ---------------------------------------------------------
comorbidity_breakdown = {}
residency_breakdown = {}
transfer_reject_breakdown = {}
entry_completed_count = 0

if not df_live.empty:
    if COL_RESIDED_THROUGHOUT in df_live.columns:
        resided_series = df_live[COL_RESIDED_THROUGHOUT].fillna("").astype(str).str.strip().str.upper()
        entry_completed_count = int((resided_series != "").sum())
        residency_breakdown = {
            "Resided in Ahmedabad Throughout": int((resided_series == "YES").sum()),
            "Did Not Reside Throughout":       int((resided_series == "NO").sum()),
        }
    if COL_COMORBIDITY in df_live.columns:
        comorb_counts = {label: 0 for label in COMORBIDITY_OPTIONS}
        for val in df_live[COL_COMORBIDITY].fillna(""):
            for token in split_multi(val):
                for label in COMORBIDITY_OPTIONS:
                    if token.lower() == label.lower():
                        comorb_counts[label] += 1
                        break
        comorbidity_breakdown = {k: v for k, v in sorted(comorb_counts.items(), key=lambda x: x[1], reverse=True) if v > 0}
    if COL_TRANSFER_OUT_DATE in df_live.columns and COL_REJECT_DATE in df_live.columns:
        transfer_series = df_live[COL_TRANSFER_OUT_DATE].fillna("").astype(str).str.strip()
        reject_series = df_live[COL_REJECT_DATE].fillna("").astype(str).str.strip()
        transferred_count = int((transfer_series != "").sum())
        rejected_count = int((reject_series != "").sum())
        retained_count = max(total_adverse_count - transferred_count - rejected_count, 0)
        transfer_reject_breakdown = {
            "Retained in AMC":        retained_count,
            "Transferred (Non-AMC)":  transferred_count,
            "Rejected":               rejected_count,
        }

# ==========================================
# 📊 EXECUTIVE SUMMARY (MOH VIEW) — REDESIGNED
# ==========================================
st.markdown("""
<style>
    /* ---- Primary KPI cards: flat, white, accent-bordered ---- */
    .kpi-card-v2 {
        background: #ffffff;
        border-radius: 12px;
        padding: 18px 20px;
        box-shadow: 0 1px 3px rgba(15,23,42,0.06), 0 1px 2px rgba(15,23,42,0.04);
        border-left: 5px solid #0A3A6E;
        height: 100%;
    }
    .kpi-dot { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px; vertical-align:middle; }
    .kpi-label-v2 {
        font-size: 11px; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.4px; color: #64748b;
    }
    .kpi-number-v2 { font-size: 30px; font-weight: 800; color: #0f172a; margin-top: 6px; line-height: 1.1; }
    .kpi-sub-v2 { font-size: 11.5px; color: #64748b; margin-top: 8px; font-weight: 600; }
    .kpi-years-wrap { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
    .kpi-year-chip {
        font-size: 12px; font-weight: 700; color: #0f172a;
        background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 6px;
        padding: 3px 8px;
    }

    /* ---- Secondary breakdown cards ---- */
    .breakdown-card {
        background: #f8fafc;
        border-radius: 10px;
        padding: 14px 16px 16px 16px;
        border: 1px solid #e2e8f0;
        height: 100%;
        max-height: 300px;
        overflow-y: auto;
    }
    .breakdown-title { font-size: 13px; font-weight: 700; color: #334155; margin-bottom: 10px; }
    .breakdown-row { display: flex; justify-content: space-between; font-size: 12px; color: #475569; margin-top: 8px; }
    .breakdown-row b { color: #0f172a; }
    .progress-bg { background: #e2e8f0; border-radius: 4px; height: 6px; margin-top: 4px; overflow: hidden; }
    .progress-fill { height: 100%; border-radius: 4px; }
    .breakdown-empty { font-size: 12px; color: #94a3b8; font-style: italic; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h3 style='color: #0A3A6E; font-weight: 800;'>Executive Summary</h3>", unsafe_allow_html=True)

def render_kpi_card(label, value, sub="", years_str="", accent="#0A3A6E"):
    sub_html = f"<div class='kpi-sub-v2'>{sub}</div>" if sub else ""
    years_html = ""
    if years_str:
        chips = "".join([f"<span class='kpi-year-chip'>{part.strip()}</span>" for part in years_str.split("|")])
        years_html = f"<div class='kpi-years-wrap'>{chips}</div>"
    parts = [
        f'<div class="kpi-card-v2" style="border-left-color:{accent};">',
        f'<span class="kpi-dot" style="background:{accent};"></span><span class="kpi-label-v2">{label}</span>',
        f'<div class="kpi-number-v2">{value}</div>',
        sub_html,
        years_html,
        '</div>',
    ]
    return "".join(parts)

kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
with kpi1:
    st.markdown(render_kpi_card("Total Adverse Outcomes", total_adverse_count,
                                 sub=f"{entry_completed_count} of {total_adverse_count} entries completed",
                                 accent="#0A3A6E"), unsafe_allow_html=True)
with kpi2:
    st.markdown(render_kpi_card("Ahmedabad Residents", ahmedabad_pct_str,
                                 sub=f"{ahmedabad_count} of {total_adverse_count} records",
                                 accent="#2563eb"), unsafe_allow_html=True)
with kpi3:
    st.markdown(render_kpi_card("Success Rate", success_overall_str,
                                 sub="Among eligible regimens", years_str=success_years_str,
                                 accent="#16a34a"), unsafe_allow_html=True)
with kpi4:
    st.markdown(render_kpi_card("Initial Death Rate", init_death_overall_str,
                                 sub="Died before treatment initiation", years_str=init_death_years_str,
                                 accent="#f97316"), unsafe_allow_html=True)
with kpi5:
    st.markdown(render_kpi_card("Normal Death Rate", death_overall_str,
                                 sub="During treatment", years_str=death_years_str,
                                 accent="#dc2626"), unsafe_allow_html=True)

# ---------------------------------------------------------
# 🔍 DETAILED BIFURCATION (Addiction / Comorbidity / Migration)
# ---------------------------------------------------------
st.markdown("<div style='height:22px;'></div>", unsafe_allow_html=True)
st.markdown("<h4 style='color: #334155; font-weight: 700; font-size:16px;'>Detailed Breakdown of Adverse Outcomes</h4>", unsafe_allow_html=True)
st.markdown("<div style='font-size:12px; color:#94a3b8; margin-bottom:14px;'>Based on field entries below. Percentages are calculated out of all records, so they will read 0% until entries are filled in. A record with more than one condition (e.g. Diabetes + HIV) is counted in every matching category, so totals can add up to more than 100%.</div>", unsafe_allow_html=True)

def render_breakdown_card(title, data_dict, total, accent):
    if total > 0 and data_dict:
        row_parts = []
        for label, count in data_dict.items():
            pct = (count / total * 100) if total > 0 else 0
            row_parts.append(
                f'<div class="breakdown-row"><span>{label}</span><span><b>{count}</b>&nbsp;({pct:.0f}%)</span></div>'
                f'<div class="progress-bg"><div class="progress-fill" style="width:{pct:.0f}%; background:{accent};"></div></div>'
            )
        rows_html = "".join(row_parts)
    else:
        rows_html = "<div class='breakdown-empty'>No entries recorded yet</div>"
    title_html = (
        f'<div class="breakdown-title">'
        f'<span class="kpi-dot" style="background:{accent};"></span>{title}'
        f'&nbsp;<span style="color:#94a3b8; font-weight:500;">(out of {total})</span></div>'
    )
    return f'<div class="breakdown-card">{title_html}{rows_html}</div>'

b1, b2, b3 = st.columns(3)
with b1:
    st.markdown(render_breakdown_card("Comorbidity", comorbidity_breakdown, total_adverse_count, accent="#0891b2"), unsafe_allow_html=True)
with b2:
    st.markdown(render_breakdown_card("Ahmedabad Residency (During Treatment)", residency_breakdown, total_adverse_count, accent="#2563eb"), unsafe_allow_html=True)
with b3:
    st.markdown(render_breakdown_card("Transfer & Rejection Overview", transfer_reject_breakdown, total_adverse_count, accent="#ca8a04"), unsafe_allow_html=True)


st.markdown("<hr style='border: 1px solid #cbd5e1; margin: 25px 0;'>", unsafe_allow_html=True)
# ==========================================
# 📝 INLINE SPREADSHEET EDITOR (DIRECT DATA ENTRY)
# ==========================================
st.markdown("<h3 style='color: #0A3A6E; font-weight: 800;'>Interactive Line List & Field Data Entry</h3>", unsafe_allow_html=True)
st.markdown(
    "<div style='font-size: 14px; margin-bottom:15px; color:#555;'>Double-click a cell to edit it, then hit Save. "
    "<b>Comorbidity</b> is view-only here — since a patient can have more than one condition (e.g. both HIV and Diabetes), "
    "edit it using the <b>Comorbidity (Multi-Select) Entry</b> form further below.</div>",
    unsafe_allow_html=True
)

if not df_live.empty:
    df_display = df_live.copy()

    # Check the Google Sheet actually has all the required real columns (English headers)
    missing_cols = [c for c in REQUIRED_ENTRY_COLS if c not in df_display.columns]
    if missing_cols:
        st.error("⚠️ Setup Required: your Google Sheet is missing these column headers. Add them exactly as written, in row 1:")
        st.markdown("<div style='font-size:13px; color:#64748b;'>" + "<br>".join([f"• {c}" for c in missing_cols]) + "</div>", unsafe_allow_html=True)
        st.stop()

    # Ensure no NaN values for clean text editing
    for col in REQUIRED_ENTRY_COLS:
        df_display[col] = df_display[col].fillna("").astype(str)
    # Numeric column needs to actually be numeric for the NumberColumn editor
    df_display[COL_MONTHS_RESIDING] = pd.to_numeric(df_display[COL_MONTHS_RESIDING], errors='coerce')

    # 1. Role-Based Filtering
    if st.session_state.role in ["TB_UNIT", "TU"]:
        df_display = df_display[df_display['TB Unit'].astype(str).str.upper().str.contains(st.session_state.target.strip().upper(), na=False)]
    elif st.session_state.role == "ZONE":
        df_display = df_display[df_display['ZONE'].astype(str).str.upper().str.contains(st.session_state.target.replace("ZONE", "").strip().upper(), na=False)]
    # 2. Top Bar Filters
    f1, f2, f3 = st.columns(3)
    with f1:
        opts_out = sorted([x for x in df_display['Treatment Outcome'].unique() if str(x).strip() != ""]) if 'Treatment Outcome' in df_display.columns else []
        sel_out = st.multiselect("Filter by Treatment Outcome", opts_out)
    with f2:
        opts_zone = sorted([x for x in df_display['ZONE'].unique() if str(x).strip() != ""]) if 'ZONE' in df_display.columns else []
        sel_zone = st.multiselect("Filter by Zone", opts_zone)
    with f3:
        entry_status = st.selectbox("Data Entry Status", ["All", "Pending Entry", "Completed"])
    if sel_out and 'Treatment Outcome' in df_display.columns: df_display = df_display[df_display['Treatment Outcome'].isin(sel_out)]
    if sel_zone and 'ZONE' in df_display.columns: df_display = df_display[df_display['ZONE'].isin(sel_zone)]

    if entry_status == "Pending Entry":
        df_display = df_display[df_display[COL_RESIDED_THROUGHOUT].str.strip() == ""]
    elif entry_status == "Completed":
        df_display = df_display[df_display[COL_RESIDED_THROUGHOUT].str.strip() != ""]
    # 🚨 CRITICAL: reset the index so Streamlit's editor maps perfectly to our filtered dataframe
    df_display = df_display.reset_index(drop=True)

    # 3. Configure the Interactive Table — everything editable EXCEPT Comorbidity (view-only, real
    #    multi-value edits happen in the dedicated form below) and historical/locked columns.
    editable_cols = [c for c in REQUIRED_ENTRY_COLS if c != COL_COMORBIDITY]
    locked_cols = [col for col in df_display.columns if col not in editable_cols]
    column_configuration = {
        COL_MONTHS_RESIDING: st.column_config.NumberColumn(COL_MONTHS_RESIDING, min_value=0, step=1, format="%d"),
        COL_RESIDED_THROUGHOUT: st.column_config.SelectboxColumn(COL_RESIDED_THROUGHOUT, options=["", "YES", "NO"]),
        COL_PLACE_OF_DEATH: st.column_config.SelectboxColumn(
            COL_PLACE_OF_DEATH, options=PLACE_OF_DEATH_OPTIONS,
            help="Only applicable when Treatment Outcome is Died"
        ),
        COL_COMORBIDITY: st.column_config.TextColumn(
            COL_COMORBIDITY, help="View only — edit using the Comorbidity (Multi-Select) form below"
        ),
        COL_STATE_NON_AMC: st.column_config.SelectboxColumn(COL_STATE_NON_AMC, options=INDIAN_STATES_UTS),
        COL_DISTRICT_NON_AMC: st.column_config.TextColumn(COL_DISTRICT_NON_AMC),
        COL_TRANSFER_REASON: st.column_config.SelectboxColumn(COL_TRANSFER_REASON, options=TRANSFER_REASON_OPTIONS),
        COL_TRANSFER_OUT_DATE: st.column_config.DateColumn(COL_TRANSFER_OUT_DATE, format="DD-MMM-YYYY"),
        COL_REJECT_DATE: st.column_config.DateColumn(COL_REJECT_DATE, format="DD-MMM-YYYY", help="Only applicable when the record is Rejected"),
        COL_REMARKS: st.column_config.TextColumn(COL_REMARKS),
    }
    # Render the interactive Data Editor
    edited_df = st.data_editor(
        df_display,
        use_container_width=True,
        hide_index=True,
        disabled=locked_cols,
        column_config=column_configuration,
        key="master_data_editor"
    )

    # 4. Save Changes Engine — looks up real column letters by header name, so it works
    #    regardless of where these columns actually sit in your sheet.
    if "master_data_editor" in st.session_state and st.session_state["master_data_editor"]["edited_rows"]:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("💾 Save All Changes to Master Database", type="primary", use_container_width=True):
            with st.spinner("Writing updates securely to Google Sheets..."):
                try:
                    sheet_headers = new_sheet.row_values(1)
                except Exception:
                    sheet_headers = list(df_live.columns)
                header_to_col = {h: i + 1 for i, h in enumerate(sheet_headers) if h}
                episode_id_col = header_to_col.get('Episode ID', 8)

                edited_rows_dict = st.session_state["master_data_editor"]["edited_rows"]
                warnings_list = []

                for row_idx, changes in edited_rows_dict.items():
                    current_row = df_display.iloc[int(row_idx)]
                    ep_id = current_row['Episode ID']
                    outcome_val = str(current_row.get('Treatment Outcome', '')).upper()

                    try:
                        cell = new_sheet.find(str(ep_id), in_column=episode_id_col)

                        def val_for(col):
                            v = changes.get(col, current_row.get(col, ""))
                            if isinstance(v, (pd.Timestamp,)) or hasattr(v, "strftime"):
                                return v.strftime("%d-%b-%Y") if v else ""
                            return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)

                        field_values = {col: val_for(col) for col in editable_cols}
                        field_values[COL_SUBMITTED_BY] = st.session_state.current_user
                        field_values[COL_LAST_UPDATED] = datetime.now(india_tz).strftime("%d-%b-%Y %H:%M:%S")

                        # Soft validation — conditional fields
                        if field_values.get(COL_PLACE_OF_DEATH, "") and "DIED" not in outcome_val and "DEATH" not in outcome_val:
                            warnings_list.append(f"Episode {ep_id}: Place of Death was filled but Treatment Outcome isn't Died.")
                        if field_values.get(COL_REJECT_DATE, "") and "REJECT" not in outcome_val:
                            warnings_list.append(f"Episode {ep_id}: Reject Date was filled but Treatment Outcome isn't Rejected.")

                        updates = []
                        for col, val in field_values.items():
                            col_idx = header_to_col.get(col)
                            if not col_idx:
                                continue
                            letter = colnum_to_letter(col_idx)
                            updates.append({"range": f"{letter}{cell.row}", "values": [[val]]})
                        if updates:
                            new_sheet.batch_update(updates)

                    except Exception as e:
                        st.error(f"❌ Failed to update Episode ID {ep_id}. Ensure the ID exists in the Episode ID column. Error: {e}")

                st.success("✅ All field data successfully saved to the Master Sheet!")
                for w in warnings_list:
                    st.warning(f"⚠️ {w}")
                get_live_tracker.clear()  # Clears cache to fetch fresh data
                st.rerun()

    # ==========================================
    # 🧷 COMORBIDITY (MULTI-SELECT) ENTRY
    # ==========================================
    st.markdown("<hr style='border: 1px solid #e2e8f0; margin: 30px 0 20px 0;'>", unsafe_allow_html=True)
    st.markdown("<h3 style='color: #0A3A6E; font-weight: 800;'>Comorbidity (Multi-Select) Entry</h3>", unsafe_allow_html=True)
    st.markdown(
        "<div style='font-size: 14px; margin-bottom:15px; color:#555;'>Streamlit's table can't do a checkbox-style "
        "multi-select inside one cell (unlike Google Sheets), so use this form instead when a patient has "
        "<b>more than one</b> comorbidity — for example both <b>HIV/AIDS</b> and <b>Diabetes</b>. Pick the Episode ID, "
        "tick every condition that applies, and save. This updates the same row shown in the table above.</div>",
        unsafe_allow_html=True
    )

    if 'Episode ID' in df_display.columns and len(df_display) > 0:
        ep_options = df_display['Episode ID'].astype(str).tolist()
        sel_ep = st.selectbox("Select Episode ID", ep_options, key="multi_entry_ep")

        sel_row = df_display[df_display['Episode ID'].astype(str) == str(sel_ep)]
        if not sel_row.empty:
            sel_row = sel_row.iloc[0]
            existing_comorbidity = split_multi(sel_row.get(COL_COMORBIDITY, ""))

            sel_comorbidity = st.multiselect(
                "Comorbidity (select all that apply)", COMORBIDITY_OPTIONS,
                default=[c for c in existing_comorbidity if c in COMORBIDITY_OPTIONS],
                key="multi_entry_comorbidity"
            )

            if st.button("💾 Save Comorbidity Entry", type="primary", use_container_width=True, key="multi_entry_save"):
                with st.spinner("Writing updates securely to Google Sheets..."):
                    try:
                        sheet_headers = new_sheet.row_values(1)
                        header_to_col = {h: i + 1 for i, h in enumerate(sheet_headers) if h}
                        episode_id_col = header_to_col.get('Episode ID', 8)
                        cell = new_sheet.find(str(sel_ep), in_column=episode_id_col)

                        field_values = {
                            COL_COMORBIDITY: ", ".join(sel_comorbidity),
                            COL_SUBMITTED_BY: st.session_state.current_user,
                            COL_LAST_UPDATED: datetime.now(india_tz).strftime("%d-%b-%Y %H:%M:%S"),
                        }
                        updates = []
                        for col, val in field_values.items():
                            col_idx = header_to_col.get(col)
                            if not col_idx:
                                continue
                            letter = colnum_to_letter(col_idx)
                            updates.append({"range": f"{letter}{cell.row}", "values": [[val]]})
                        if updates:
                            new_sheet.batch_update(updates)

                        st.success(f"✅ Episode ID {sel_ep} updated successfully!")
                        get_live_tracker.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Failed to update Episode ID {sel_ep}. Ensure the ID exists in the Episode ID column. Error: {e}")
    else:
        st.info("ℹ️ No Episode IDs available for the current filter.")
else:
    st.info("ℹ️ No records found in the New Sheet.")
