import streamlit as st
import pandas as pd
import base64
import os
import io
import json
import re
from datetime import datetime, timedelta
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
        with open(img_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode('utf-8')
    except Exception:
        return ""
def first_existing_b64(candidates):
    for name in candidates:
        b64 = img_to_b64(name)
        if b64:
            return b64
    return ""
JALI_CANDIDATES = [
    "banner_sidi-saiyyad-jali_902.png", "banner_sidi-saiyyad-jali_902.jpg", "banner_sidi-saiyyad-jali_902.jpeg",
    "sidi-saiyyad-jali.png", "sidi-saiyyad-jali.jpg", "sidi_saiyyad_jali.png", "sidi_saiyyad_jali.jpg",
]
RIVERFRONT_CANDIDATES = [
    "ahmedabad_riverfront.png", "ahmedabad_riverfront.jpg", "ahmedabad_riverfront.jpeg",
    "riverfront.png", "riverfront.jpg", "sabarmati_riverfront.png", "sabarmati_riverfront.jpg",
]
b64_jali = first_existing_b64(JALI_CANDIDATES)
b64_riverfront = first_existing_b64(RIVERFRONT_CANDIDATES)
if "auth" not in st.session_state:
    st.session_state.auth = False
    st.session_state.current_user = ""
    st.session_state.role = ""
    st.session_state.target = ""
try:
    df_users = pd.read_csv("users.csv")
    df_users['Username'] = df_users['Username'].astype(str).str.strip().str.upper()
except Exception:
    st.error("⚠️ User Database (users.csv) not found in the repository!")
    st.stop()
# ==========================================
# 🎯 ROLE-BASED SCOPE FILTER
# ==========================================
TU_NAME_CANDIDATES = ["TB Unit", "TB UNIT", "TU NAME", "NAME OF TU", "TB UNIT NAME", "TU"]
ZONE_NAME_CANDIDATES = ["ZONE", "Zone", "ZONE NAME"]
def find_column(df, candidates):
    if df is None or df.empty:
        return None
    cols_clean = {re.sub(r'[^A-Z0-9]', '', str(c).upper()): c for c in df.columns}
    for cand in candidates:
        key = re.sub(r'[^A-Z0-9]', '', cand.upper())
        if key in cols_clean:
            return cols_clean[key]
    return None
def apply_scope_filter(df):
    if df is None or df.empty:
        return df, None
    role = st.session_state.role
    target = st.session_state.target.strip().upper()
    if role in ["TB_UNIT", "TU"]:
        col = find_column(df, TU_NAME_CANDIDATES)
        if col:
            return df[df[col].astype(str).str.upper().str.contains(target, na=False)], col
        return df, "NOT_FOUND"
    if role == "ZONE":
        col = find_column(df, ZONE_NAME_CANDIDATES)
        if col:
            zone_target = target.replace("ZONE", "").strip()
            return df[df[col].astype(str).str.upper().str.contains(zone_target, na=False)], col
        return df, "NOT_FOUND"
    return df, None
# ==========================================
# 🔐 LOGIN PAGE
# ==========================================
if not st.session_state.auth:
    b64_amc = img_to_b64("amc.png")
    riverfront_layer = (
        f"linear-gradient(180deg, rgba(244,247,251,0.85) 0%, rgba(244,247,251,0.97) 100%), "
        f"url('data:image/png;base64,{b64_riverfront}')"
        if b64_riverfront else "none"
    )
    jali_layer = (
        f"linear-gradient(160deg, rgba(10,58,110,0.90) 0%, rgba(18,74,138,0.80) 55%, rgba(10,58,110,0.92) 100%), "
        f"url('data:image/png;base64,{b64_jali}')"
        if b64_jali else "linear-gradient(160deg, #0A3A6E 0%, #124a8a 60%, #1a5aa8 100%)"
    )
    st.markdown(f"""
    <style>
        #MainMenu, footer, header {{visibility: hidden;}}
        html, body, [data-testid="stAppViewContainer"] {{
            background: {riverfront_layer};
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        .gov-topbar {{
            background: #0A3A6E; color: #dbeafe; text-align:center;
            font-size: 12.5px; letter-spacing: 0.6px; font-weight: 600;
            padding: 8px 0; text-transform: uppercase;
            border-bottom: 3px solid #c9a227;
        }}
        div[data-testid="stHorizontalBlock"] {{
            max-width: 900px;
            margin: 5vh auto 0 auto;
            border-radius: 18px;
            overflow: hidden;
            box-shadow: 0 20px 50px rgba(15,23,42,0.18);
            border: 1px solid #e2e8f0;
        }}
        .brand-panel {{
            background: {jali_layer};
            background-size: cover;
            background-position: center;
            filter: saturate(1.02);
            color: #fff;
            padding: 48px 32px;
            text-align: center;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            min-height: 480px;
        }}
        .brand-panel img {{
            background: #fff;
            border-radius: 50%;
            padding: 8px;
            box-shadow: 0 8px 20px rgba(0,0,0,0.3);
            margin-bottom: 22px;
        }}
        .brand-panel h2 {{ font-size: 23px; font-weight: 800; margin: 0 0 6px 0; letter-spacing: 0.5px; }}
        .brand-panel p {{ font-size: 13px; color: #dbe9fb; line-height: 1.5; margin: 0; }}
        .brand-tag {{
            margin-top: 26px; font-size: 11.5px; color: #cfe1f7; border-top: 1px solid rgba(255,255,255,0.35);
            padding-top: 14px; width: 100%;
        }}
        [data-testid="column"]:has(.form-panel-marker) {{
            background: #ffffff;
        }}
        [data-testid="column"]:has(.form-panel-marker) [data-testid="stVerticalBlock"] {{
            padding: 52px 46px;
        }}
        .form-panel-marker {{ display: none; }}
        .form-panel-heading h3 {{ color: #0f172a !important; font-weight: 800; font-size: 24px; margin-bottom: 4px; }}
        .form-panel-heading .sub {{ color: #475569 !important; font-size: 13.5px; margin-bottom: 26px; }}
        [data-testid="stTextInput"] label, [data-testid="stTextInput"] label p {{
            color: #1e293b !important; font-weight: 700 !important; font-size: 13.5px !important;
        }}
        .stTextInput>div>div>input {{
            border-radius: 10px; border: 1.5px solid #cbd5e1; padding: 11px 14px; font-size: 14px;
            color: #0f172a !important; background: #fff !important;
        }}
        .stTextInput>div>div>input:focus {{ border-color: #0A3A6E; box-shadow: 0 0 0 3px rgba(10,58,110,0.12); }}
        .stButton>button {{
            background: linear-gradient(135deg, #0A3A6E 0%, #1a5aa8 100%);
            color: white !important; border: none; border-radius: 10px; width: 100%;
            font-weight: 700; padding: 12px; margin-top: 8px; letter-spacing: 0.3px;
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }}
        .stButton>button:hover {{ transform: translateY(-1px); box-shadow: 0 10px 20px rgba(10,58,110,0.3); }}
    </style>
    <div class="gov-topbar">Government of Gujarat &nbsp;·&nbsp; Ahmedabad Municipal Corporation &nbsp;·&nbsp; National TB Elimination Programme</div>
    """, unsafe_allow_html=True)
    outer_l, outer_r = st.columns([4, 5], gap="small")
    with outer_l:
        st.markdown(f"""
        <div class="brand-panel">
            <img src="data:image/png;base64,{b64_amc}" width="62">
            <h2>AMC · NTEP</h2>
            <p>Adverse Outcomes &amp; Field Entry Module</p>
            <div class="brand-tag">Ahmedabad Municipal Corporation<br>National TB Elimination Programme</div>
        </div>
        """, unsafe_allow_html=True)
    with outer_r:
        st.markdown('<span class="form-panel-marker"></span>', unsafe_allow_html=True)
        st.markdown("<div class='form-panel-heading'><h3>Sign in</h3><div class='sub'>Enter your assigned credentials to continue</div></div>", unsafe_allow_html=True)
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
b64_amc = img_to_b64("amc.png")
b64_ntep = img_to_b64("ntep.png")
st.markdown("""
<style>
    #MainMenu, footer, header {visibility: hidden;}
    html, body, [data-testid="stAppViewContainer"] { background: #F4F7FB !important; }
    * { color: #0f172a; }
    .gov-topbar {
        background: #0A3A6E; color: #dbeafe; text-align:center;
        font-size: 11.5px; letter-spacing: 0.6px; font-weight: 600;
        padding: 6px 0; text-transform: uppercase; margin: -1rem -1rem 12px -1rem;
        border-bottom: 3px solid #c9a227;
    }
    .app-header {
        background: linear-gradient(120deg, #0A3A6E 0%, #124a8a 100%);
        border-radius: 14px; padding: 16px 26px; margin-bottom: 16px;
        display: flex; justify-content: space-between; align-items: center;
        box-shadow: 0 8px 20px rgba(10,58,110,0.15);
    }
    .app-header h2 { margin:0; font-weight:800; color:#fff !important; font-size: 21px; letter-spacing: 0.4px; }
    .app-header .subtitle { color:#bcd7f5 !important; font-size: 12px; margin-top:2px; }
    .app-header img { height: 52px; background:#fff; border-radius: 8px; padding: 4px; }
    .user-chip {
        display:inline-flex; align-items:center; gap:8px;
        background: #e7f6ec; color:#166534 !important; padding: 9px 16px; border-radius: 999px;
        font-weight:700; font-size: 13px; margin-bottom: 18px; border: 1px solid #bbf0cc;
    }
    .section-title {
        color:#0f172a !important; font-weight:800; font-size:17px; margin: 6px 0 14px 0;
        display:flex; align-items:center; gap:8px;
    }
    /* ---- KPI CARDS: clean enterprise style, white with accent top border ---- */
    .kpi-card {
        background:#fff; border-radius: 12px; padding: 18px 16px 16px 16px; height:100%;
        border: 1px solid #e7ecf3; border-top: 4px solid var(--accent, #0A3A6E);
        box-shadow: 0 4px 14px rgba(15,23,42,0.06);
        display:flex; flex-direction:column; gap: 6px;
    }
    .kpi-top { display:flex; align-items:center; gap:10px; }
    .kpi-icon-badge {
        width:34px; height:34px; border-radius:9px; display:flex; align-items:center; justify-content:center;
        font-size:16px; background: var(--accent-soft, #eef2ff); color: var(--accent, #0A3A6E);
        flex-shrink:0;
    }
    .kpi-title { font-size: 11.5px; text-transform: uppercase; font-weight: 800; color:#64748b !important; letter-spacing:0.4px; }
    .kpi-value { font-size: 30px; font-weight: 900; color:#0f172a !important; margin-top: 2px; }
    .kpi-sub { font-size: 11.5px; color: #64748b !important; font-weight: 600; }
    .kpi-years-wrap { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
    .kpi-year-chip { font-size: 10.5px; font-weight: 700; color: #334155 !important; background: #f1f5f9; border-radius: 5px; padding: 2px 6px; }
    .breakdown-card {
        background: #fff; border-radius: 12px; padding: 16px 18px 18px 18px;
        border: 1px solid #e7ecf3; height:100%; max-height: 300px; overflow-y:auto;
        box-shadow: 0 4px 14px rgba(15,23,42,0.05);
    }
    .breakdown-title { font-size: 13px; font-weight: 800; color: #1e293b !important; margin-bottom: 10px; }
    .breakdown-row { display: flex; justify-content: space-between; font-size: 12.5px; color: #475569 !important; margin-top: 8px; }
    .breakdown-row b { color: #0f172a !important; }
    .progress-bg { background: #eef2f7; border-radius: 4px; height: 6px; margin-top: 4px; overflow: hidden; }
    .progress-fill { height: 100%; border-radius: 4px; }
    .breakdown-empty { font-size: 12px; color: #94a3b8 !important; font-style: italic; }
    /* ---- FILTER STRIP: clearer, easier to use ---- */
    .filter-strip {
        background:#fff; border:1px solid #e7ecf3; border-radius: 14px; padding: 18px 20px;
        margin-bottom: 16px; box-shadow: 0 4px 12px rgba(15,23,42,0.04);
    }
    .filter-strip .label { font-size:13.5px; font-weight:800; color:#0A3A6E !important; margin-bottom:10px; }
    .filter-col-label { font-size: 12px; font-weight:700; color:#334155 !important; margin-bottom:4px; }
    /* Force visible select / multiselect / label text everywhere */
    label, .stSelectbox label, .stMultiSelect label, .stDateInput label {
        color: #1e293b !important; font-weight: 600 !important;
    }
    [data-baseweb="select"] * { color: #0f172a !important; }
</style>
""", unsafe_allow_html=True)
st.markdown('<div class="gov-topbar">Government of Gujarat · Ahmedabad Municipal Corporation · National TB Elimination Programme</div>', unsafe_allow_html=True)
st.markdown(f"""
<div class="app-header">
    <img src='data:image/png;base64,{b64_amc}'>
    <div style="text-align:center;">
        <h2>AMC | NTEP DASHBOARD</h2>
        <div class="subtitle">Adverse Outcomes &amp; Field Entry Module</div>
    </div>
    <img src='data:image/png;base64,{b64_ntep}'>
</div>
""", unsafe_allow_html=True)
st.markdown(f"<div class='user-chip'>👤 Logged in as: {st.session_state.target} &nbsp;·&nbsp; {st.session_state.role}</div>", unsafe_allow_html=True)
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
except Exception:
    st.error("Could not connect to the New Google Sheet. Check credentials.")
    st.stop()
# ---------------------------------------------------------
# 🗺️ ZONE LOOKUP  (reads the "zone" sub-sheet you added: Name of PHI | Zone | UHC | TU)
# Used to reliably resolve ZONE for new adverse outcomes instead of guessing
# columns from the weekly register, which was producing blank/"0" zones.
# ---------------------------------------------------------
ZONE_LOOKUP_SHEET_NAME = "zone"
@st.cache_data(ttl=300, show_spinner=False)
def load_zone_lookup():
    tu_to_zone, uhc_to_tu_zone = {}, {}
    try:
        zone_ws = client.open_by_url(NEW_SHEET_URL).worksheet(ZONE_LOOKUP_SHEET_NAME)
        df_zone_map = pd.DataFrame(zone_ws.get_all_records())
    except Exception:
        return tu_to_zone, uhc_to_tu_zone
    if df_zone_map.empty:
        return tu_to_zone, uhc_to_tu_zone
    df_zone_map.columns = [str(c).strip() for c in df_zone_map.columns]
    tu_col = find_column(df_zone_map, ["TU", "TB Unit", "TU NAME", "NAME OF TU"])
    zone_col = find_column(df_zone_map, ZONE_NAME_CANDIDATES)
    uhc_col = find_column(df_zone_map, ["UHC", "PHI (Current)", "PHI", "NAME OF PHI"])
    if tu_col and zone_col:
        for _, row in df_zone_map.iterrows():
            tu_val = str(row.get(tu_col, "")).strip().upper()
            zone_val = str(row.get(zone_col, "")).strip()
            if tu_val and zone_val:
                tu_to_zone.setdefault(tu_val, zone_val)
    if uhc_col and zone_col:
        for _, row in df_zone_map.iterrows():
            uhc_val = str(row.get(uhc_col, "")).strip().upper()
            tu_val = str(row.get(tu_col, "")).strip() if tu_col else ""
            zone_val = str(row.get(zone_col, "")).strip()
            if uhc_val and zone_val:
                uhc_to_tu_zone.setdefault(uhc_val, (tu_val, zone_val))
    return tu_to_zone, uhc_to_tu_zone
def resolve_zone_for_row(existing_zone, tb_unit_val, phi_current_val, tu_to_zone, uhc_to_tu_zone):
    """Best-effort ZONE resolver: keeps a genuinely valid existing zone, otherwise
    matches TB Unit against the zone-sheet TU column, then falls back to matching
    PHI (Current) against the zone-sheet UHC column. Returns "" if nothing matches
    (never fabricates a fake value like "0")."""
    ez = str(existing_zone).strip()
    if ez and ez.upper() not in ("0", "0.0", "NAN", "NONE", "NAT", "<NA>", ""):
        return ez
    tu_key = str(tb_unit_val).strip().upper()
    if tu_key in tu_to_zone:
        return tu_to_zone[tu_key]
    phi_key = str(phi_current_val).strip().upper()
    if phi_key in uhc_to_tu_zone:
        return uhc_to_tu_zone[phi_key][1]
    return ""
@st.cache_data(ttl=10, show_spinner="Syncing Live Data Tracker...")
def get_live_tracker():
    try:
        return pd.DataFrame(new_sheet.get_all_records())
    except Exception:
        return pd.DataFrame()
df_live_raw = get_live_tracker()
# ---------------------------------------------------------
# 🧮 FIELD DATA COLUMN CONSTANTS
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
# ---------------------------------------------------------
# 🧹 SMART DATA CLEANER (Translates Gujarati to English & Normalizes Time)
# ---------------------------------------------------------
def parse_gujarati_time(val):
    if pd.isna(val): return pd.NA
    val_str = str(val).strip().lower()
    if not val_str or val_str == 'nan': return pd.NA
    guj_digits = str.maketrans('૦૧૨૩૪૫૬૭૮૯', '0123456789')
    val_str = val_str.translate(guj_digits)
    nums = re.findall(r'\d+\.?\d*', val_str)
    if not nums: return pd.NA
    num = float(nums[0])
    if any(k in val_str for k in ['year', 'yr', 'વર્ષ', 'સાલ', 'varsh', 'sal']): return int(num * 12)
    else: return int(num)
def clean_resided(val):
    if pd.isna(val): return ""
    val_str = str(val).strip().upper()
    if val_str in ['હા', 'HA', 'YES']: return 'YES'
    if val_str in ['ના', 'NA', 'NO']: return 'NO'
    return val_str
if not df_live_raw.empty:
    if COL_MONTHS_RESIDING in df_live_raw.columns:
        df_live_raw[COL_MONTHS_RESIDING] = df_live_raw[COL_MONTHS_RESIDING].apply(parse_gujarati_time)
    if COL_RESIDED_THROUGHOUT in df_live_raw.columns:
        df_live_raw[COL_RESIDED_THROUGHOUT] = df_live_raw[COL_RESIDED_THROUGHOUT].apply(clean_resided)
# ==========================================
# 🎯 APPLY ROLE SCOPE  (once, for everything downstream)
# ==========================================
df_live, tu_scope_col = apply_scope_filter(df_live_raw)
scope_col_missing = (tu_scope_col == "NOT_FOUND")
if scope_col_missing:
    st.warning(
        "⚠️ Could not find a TB Unit/Zone column in the live tracker sheet to scope this login to. "
        "Showing all records instead — please confirm the exact column header name so scoping can be applied."
    )
# 🚀 RESTORED DELTA ENGINE LOADER
@st.cache_data(ttl=600, show_spinner="Fetching This & Previous Week Registers...")
def load_source_data():
    import urllib.request
    def fetch(gid):
        try:
            url = f"https://docs.google.com/spreadsheets/d/1Dfvl87uaZZ12_5F4dhHXTP_u8i9NM9TASWN8wyX18nE/export?format=csv&gid={gid}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as response:
                return pd.read_csv(io.BytesIO(response.read()), low_memory=False, dtype=str, on_bad_lines='skip')
        except Exception:
            return pd.DataFrame()
    return fetch("1898426568"), fetch("1981365704")
df_this_raw_full, df_prev_raw_full = load_source_data()
df_this_raw, kpi_scope_col = apply_scope_filter(df_this_raw_full)
# ==========================================
# 📅 DATE FILTERS — QUICK PRESETS + MONTH-JUMP PICKER
# ==========================================
DATE_PRESETS = ["All Time", "Today", "Last 7 Days", "Last 30 Days", "This Month", "This Year", "Jump to Month", "Custom Range"]
def shift_month(d, delta):
    total = d.year * 12 + (d.month - 1) + delta
    y, m = divmod(total, 12)
    return d.replace(year=y, month=m + 1, day=1)
def resolve_preset(preset, custom_range, month_anchor=None):
    today = datetime.now(india_tz).date()
    if preset == "Today": return (today, today)
    if preset == "Last 7 Days": return (today - timedelta(days=6), today)
    if preset == "Last 30 Days": return (today - timedelta(days=29), today)
    if preset == "This Month": return (today.replace(day=1), today)
    if preset == "This Year": return (today.replace(month=1, day=1), today)
    if preset == "Jump to Month":
        anchor = month_anchor or today.replace(day=1)
        end = shift_month(anchor, 1) - timedelta(days=1)
        return (anchor, end)
    if preset == "Custom Range":
        if custom_range and len(custom_range) == 2: return (custom_range[0], custom_range[1])
        elif custom_range and len(custom_range) == 1: return (custom_range[0], custom_range[0])
        return None
    return None
diag_preset = st.session_state.get("diag_preset", "All Time")
init_preset = st.session_state.get("init_preset", "All Time")
out_preset = st.session_state.get("out_preset", "All Time")
diag_custom = st.session_state.get("diag_custom", [])
init_custom = st.session_state.get("init_custom", [])
out_custom = st.session_state.get("out_custom", [])
today_first = datetime.now(india_tz).date().replace(day=1)
diag_month = st.session_state.get("diag_month_anchor", today_first)
init_month = st.session_state.get("init_month_anchor", today_first)
out_month = st.session_state.get("out_month_anchor", today_first)
diag_range = resolve_preset(diag_preset, diag_custom, diag_month)
init_range = resolve_preset(init_preset, init_custom, init_month)
out_range = resolve_preset(out_preset, out_custom, out_month)
def parse_indian_dates(series):
    def fix_date_string(x):
        if pd.isna(x) or x in ['nan', 'NaN', 'None', '<NA>', '']: return pd.NA
        x = str(x).strip()
        if re.match(r'^[A-Za-z]{3}[-/]\d{2}$', x): return f"01-{x[:3]}-20{x[-2:]}"
        if re.match(r'^[A-Za-z]{3}[-/]\d{4}$', x): return f"01-{x[:3]}-{x[-4:]}"
        return x
    s = series.apply(fix_date_string)
    parsed = pd.to_datetime(s, dayfirst=True, errors='coerce')
    failed = parsed.isna() & s.notna()
    if failed.any():
        parsed[failed] = pd.to_datetime(s[failed], errors='coerce')
    return parsed
if not df_live.empty:
    for c in ['Diagnosis Date', 'Initiation Date', 'Outcome Date']:
        if c in df_live.columns:
            df_live[c + '_dt'] = parse_indian_dates(df_live[c])
df_live_filtered = df_live.copy()
def filter_by_range(df, col, d_range):
    if d_range is None: return df
    start, end = d_range
    return df[(df[col].dt.date >= start) & (df[col].dt.date <= end)]
if not df_live_filtered.empty:
    if 'Diagnosis Date_dt' in df_live_filtered.columns: df_live_filtered = filter_by_range(df_live_filtered, 'Diagnosis Date_dt', diag_range)
    if 'Initiation Date_dt' in df_live_filtered.columns: df_live_filtered = filter_by_range(df_live_filtered, 'Initiation Date_dt', init_range)
    if 'Outcome Date_dt' in df_live_filtered.columns: df_live_filtered = filter_by_range(df_live_filtered, 'Outcome Date_dt', out_range)
# ==========================================
# 🎯 ZONE / OUTCOME / ENTRY-STATUS QUICK FILTERS
# ==========================================
df_options_source = df_live_filtered.copy()
sel_out_val = st.session_state.get("linelist_outcome_filter", [])
sel_zone_val = st.session_state.get("linelist_zone_filter", [])
entry_status_val = st.session_state.get("linelist_entry_status", "All")
if sel_out_val and 'Treatment Outcome' in df_live_filtered.columns: df_live_filtered = df_live_filtered[df_live_filtered['Treatment Outcome'].isin(sel_out_val)]
if sel_zone_val and 'ZONE' in df_live_filtered.columns: df_live_filtered = df_live_filtered[df_live_filtered['ZONE'].isin(sel_zone_val)]
if entry_status_val == "Pending Entry" and COL_RESIDED_THROUGHOUT in df_live_filtered.columns: df_live_filtered = df_live_filtered[df_live_filtered[COL_RESIDED_THROUGHOUT].astype(str).str.strip() == ""]
elif entry_status_val == "Completed" and COL_RESIDED_THROUGHOUT in df_live_filtered.columns: df_live_filtered = df_live_filtered[df_live_filtered[COL_RESIDED_THROUGHOUT].astype(str).str.strip() != ""]
total_adverse_count = len(df_live_filtered)
# ---------------------------------------------------------
# 🧮 CALCULATION ENGINE: YEAR-WISE SUCCESS & DEATH RATES (UNAFFECTED BY DATES)
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
    diag_series_raw = get_col_series(df_this_raw, ['DIAGNOSIS DATE'], 'S').fillna("").astype(str).str.strip()
    init_series_raw = get_col_series(df_this_raw, ['INITIATION DATE'], 'BM').fillna("").astype(str).str.strip()
    out_date_series_raw = get_col_series(df_this_raw, ['OUTCOME DATE'], 'CB').fillna("").astype(str).str.strip()
    df_calc = pd.DataFrame({
        'Valid': ~ep_series.isin(["", "NAN", "NONE", "NULL", "N/A"]),
        'Regimen_Eligible': regimen_series.str.contains("2HRZE/4HRE|2HRZES|4HRE|2HRZE", regex=True, na=False),
        'Is_Success': outcome_series.str.contains("COMPLETE|CURED", regex=True, na=False),
        'Is_Death': outcome_series.str.contains("DIED|DEATH", regex=True, na=False),
        'Init_Year': pd.to_datetime(init_series_raw, errors='coerce').dt.year,
        'Diag_Year': pd.to_datetime(diag_series_raw, errors='coerce').dt.year,
        'Has_Diag': diag_series_raw != "",
        'Has_OutDate': out_date_series_raw != "",
        'No_Init': init_series_raw == ""
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
# ---------------------------------------------------------
# 🧮 AHMEDABAD RESIDENT COUNT 
# ---------------------------------------------------------
ahmedabad_count = 0
ahmedabad_pct_str = "0%"
if total_adverse_count > 0 and 'ZONE' in df_live_filtered.columns:
    zone_mask = df_live_filtered['ZONE'].astype(str).str.upper().str.contains("AHMEDABAD|EAST|WEST|NORTH|SOUTH|CENTRAL|AMC", regex=True, na=False)
    if COL_MONTHS_RESIDING in df_live_filtered.columns:
        months_series = pd.to_numeric(df_live_filtered[COL_MONTHS_RESIDING], errors='coerce')
        months_valid_mask = (months_series >= 6) | (months_series.isna())
        ahmedabad_mask = zone_mask & months_valid_mask
    else:
        ahmedabad_mask = zone_mask
    ahmedabad_count = int(ahmedabad_mask.sum())
    ahmedabad_pct_str = f"{int((ahmedabad_count / total_adverse_count) * 100)}%"
# ---------------------------------------------------------
# 🧮 MORE FIELD OPTIONS
# ---------------------------------------------------------
META_ENTRY_COLS = [COL_SUBMITTED_BY, COL_LAST_UPDATED]
COMORBIDITY_OPTIONS = [
    "", "Diabetes", "Cardiovascular disease", "Hypertension", "COPD", "Asthama",
    "Other lung disease", "Chronic liver disease", "Chronic kidney disease", "Cancer",
    "HIV/AIDS", "Occupational lung disease", "Anaemia", "Mental health disorder",
    "Autoimmune disorder", "Severe malnutrition", "Congenital disorder",
    "Chronic alcoholism", "P/H of covid 19", "Sickle cell trait or anaemia",
    "Other", "Multiple", "NA"
]
PLACE_OF_DEATH_OPTIONS = [
    "", "Home", "PHC", "UHC", "CHC", "SDH", "DH", "Medical College",
    "Grant in aid hospital", "ESIS Hospital", "ESIC Hospital",
    "Other Central GOVT Hospital", "Private Hospital", "Private NGO",
    "In transit", "Other", "Not Known"
]
TRANSFER_REASON_OPTIONS = ["", "Migration for Work", "Family Relocation", "Better Treatment Facility", "Other"]
INDIAN_STATES_UTS = [
    "", "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat",
    "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra",
    "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim",
    "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Andaman and Nicobar Islands", "Chandigarh", "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
]
def split_multi(val): return [x.strip() for x in str(val).split(",") if x.strip()]
def safe_unique_options(series):
    """Build a sorted list of clean string options from a column, safely.
    Prevents: TypeError: '<' not supported between instances of 'NoneType' and 'str'
    which happens when sorted() tries to compare a real None with real strings.
    Every value is converted to a string BEFORE sorting, and blank/NaN/None-like
    values are dropped."""
    if series is None:
        return []
    cleaned = set()
    for x in series.dropna().tolist():
        s = str(x).strip()
        if s and s.lower() not in ("nan", "none", "nat", "<na>"):
            cleaned.add(s)
    return sorted(cleaned)
def colnum_to_letter(n):
    letters = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters
# ---------------------------------------------------------
# 🧮 BIFURCATED BREAKDOWNS 
# ---------------------------------------------------------
comorbidity_breakdown = {}
residency_breakdown = {}
outcome_breakdown = {}
entry_completed_count = 0
if not df_live_filtered.empty:
    if COL_RESIDED_THROUGHOUT in df_live_filtered.columns:
        resided_series = df_live_filtered[COL_RESIDED_THROUGHOUT].fillna("").astype(str).str.strip().str.upper()
        entry_completed_count = int((resided_series != "").sum())
        pending_count = total_adverse_count - entry_completed_count
        residency_breakdown = {
            "Resided in Ahmedabad Throughout": int((resided_series == "YES").sum()),
            "Did Not Reside Throughout":       int((resided_series == "NO").sum()),
        }
        if pending_count > 0: residency_breakdown["⏳ Data Pending"] = pending_count
    if COL_COMORBIDITY in df_live_filtered.columns:
        comorb_counts = {label: 0 for label in COMORBIDITY_OPTIONS if label != ""}
        comorb_pending_count = 0
        for val in df_live_filtered[COL_COMORBIDITY].fillna(""):
            val_str = str(val).strip()
            if not val_str: comorb_pending_count += 1
            else:
                for token in split_multi(val_str):
                    for label in COMORBIDITY_OPTIONS:
                        if label and token.lower() == label.lower():
                            comorb_counts[label] += 1
                            break
        comorbidity_breakdown = {k: v for k, v in sorted(comorb_counts.items(), key=lambda x: x[1], reverse=True) if v > 0}
        if comorb_pending_count > 0: comorbidity_breakdown["⏳ Data Pending"] = comorb_pending_count
    if 'Treatment Outcome' in df_live_filtered.columns:
        outcomes_series = df_live_filtered['Treatment Outcome'].fillna("").astype(str).str.strip().str.upper()
        outcomes_dict = outcomes_series.value_counts().to_dict()
        outcome_breakdown = {k: v for k, v in outcomes_dict.items() if k != ""}
# ==========================================
# 📊 KPI CARDS
# ==========================================
kpi_placeholder = st.container()
st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
st.markdown("<div class='section-title'>📋 Detailed Breakdown of Adverse Outcomes</div>", unsafe_allow_html=True)
breakdown_placeholder = st.container()
def render_kpi_card(icon, label, value, sub="", years_str="", accent="#0A3A6E", accent_soft="#eef2ff"):
    sub_html = f"<div class='kpi-sub'>{sub}</div>" if sub else ""
    years_html = ""
    if years_str:
        chips = "".join([f"<span class='kpi-year-chip'>{part.strip()}</span>" for part in years_str.split("|")])
        years_html = f"<div class='kpi-years-wrap'>{chips}</div>"
    return f"""
    <div class="kpi-card" style="--accent:{accent}; --accent-soft:{accent_soft};">
        <div class="kpi-top">
            <div class="kpi-icon-badge">{icon}</div>
            <div class="kpi-title">{label}</div>
        </div>
        <div class="kpi-value">{value}</div>
        {sub_html}
        {years_html}
    </div>
    """
with kpi_placeholder:
    k_col1, k_col2, k_col3, k_col4, k_col5 = st.columns(5)
    with k_col1:
        st.markdown(render_kpi_card("📊", "Total Adverse Outcomes", total_adverse_count, sub=f"{entry_completed_count} of {total_adverse_count} entries completed", accent="#0A3A6E", accent_soft="#e8eef7"), unsafe_allow_html=True)
    with k_col2:
        st.markdown(render_kpi_card("🏠", "Ahmedabad Residents", ahmedabad_pct_str, sub=f"{ahmedabad_count} of {total_adverse_count} records", accent="#1d4ed8", accent_soft="#e8edfd"), unsafe_allow_html=True)
    with k_col3:
        st.markdown(render_kpi_card("✅", "Success Rate", success_overall_str, sub="Among eligible regimens", years_str=success_years_str, accent="#16a34a", accent_soft="#e8f8ee"), unsafe_allow_html=True)
    with k_col4:
        st.markdown(render_kpi_card("⚠️", "Initial Death Rate", init_death_overall_str, sub="Died before treatment initiation", years_str=init_death_years_str, accent="#f97316", accent_soft="#fff1e6"), unsafe_allow_html=True)
    with k_col5:
        st.markdown(render_kpi_card("💔", "Normal Death Rate", death_overall_str, sub="During treatment", years_str=death_years_str, accent="#dc2626", accent_soft="#fdeaea"), unsafe_allow_html=True)
def render_breakdown_card(title, data_dict, total, accent):
    if total > 0 and data_dict:
        row_parts = []
        for label, count in data_dict.items():
            pct = (count / total * 100) if total > 0 else 0
            is_pending = label == "⏳ Data Pending"
            val_color = "#dc2626" if is_pending else "#0f172a"
            bar_color = "#f87171" if is_pending else accent
            row_parts.append(
                f'<div class="breakdown-row"><span>{label}</span><span style="color:{val_color}; font-weight:700;">{count}&nbsp;({pct:.0f}%)</span></div>'
                f'<div class="progress-bg"><div class="progress-fill" style="width:{pct:.0f}%; background:{bar_color};"></div></div>'
            )
        rows_html = "".join(row_parts)
    else:
        rows_html = "<div class='breakdown-empty'>No entries recorded yet</div>"
    return f"""
    <div class="breakdown-card">
        <div class="breakdown-title">
            <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:{accent}; margin-right:6px;"></span>
            {title}&nbsp;<span style="color:#94a3b8; font-weight:500;">(out of {total})</span>
        </div>
        {rows_html}
    </div>
    """
with breakdown_placeholder:
    b1, b2, b3 = st.columns(3)
    with b1: st.markdown(render_breakdown_card("Comorbidity", comorbidity_breakdown, total_adverse_count, accent="#0891b2"), unsafe_allow_html=True)
    with b2: st.markdown(render_breakdown_card("Ahmedabad Residency (During Treatment)", residency_breakdown, total_adverse_count, accent="#2563eb"), unsafe_allow_html=True)
    with b3: st.markdown(render_breakdown_card("Adverse Outcomes Overview", outcome_breakdown, total_adverse_count, accent="#ca8a04"), unsafe_allow_html=True)
st.markdown("<hr style='border: none; border-top: 1px solid #e2e8f0; margin: 28px 0;'>", unsafe_allow_html=True)
# ==========================================
# 🚨 DISCOVER & AUTO-SYNC NEW ADVERSE OUTCOMES
# ==========================================
PUSH_ALLOWED_ROLES = ["ADMIN", "CTO"]
if st.session_state.role in PUSH_ALLOWED_ROLES:
    with st.expander("🚨 Discover & Auto-Sync New Adverse Outcomes", expanded=False):
        st.markdown("<div style='font-size: 14px; margin-bottom:15px; color:#555;'>This engine scans the 'This Week' register against the 'Previous Week' register to accurately isolate exactly what changed this week, preventing bulk historical duplicates.</div>", unsafe_allow_html=True)
        
        if not df_this_raw_full.empty and not df_prev_raw_full.empty:
            def get_col_series_sync(df, possible_names, fallback_idx):
                for p in possible_names:
                    p_clean = re.sub(r'[^A-Z0-9]', '', str(p).upper())
                    for c in df.columns:
                        c_clean = re.sub(r'[^A-Z0-9]', '', str(c).upper())
                        if c_clean == p_clean: return df[c]
                if fallback_idx < len(df.columns): return df.iloc[:, fallback_idx]
                return pd.Series([""] * len(df))
            # THIS WEEK
            out_this = get_col_series_sync(df_this_raw_full, ['TREATMENT OUTCOME'], 62).fillna("").astype(str).str.upper().str.strip()
            id_this = get_col_series_sync(df_this_raw_full, ['EPISODE ID'], 12).fillna("").astype(str).str.upper().str.strip()
            
            # PREV WEEK
            out_prev = get_col_series_sync(df_prev_raw_full, ['TREATMENT OUTCOME'], 62).fillna("").astype(str).str.upper().str.strip()
            id_prev = get_col_series_sync(df_prev_raw_full, ['EPISODE ID'], 12).fillna("").astype(str).str.upper().str.strip()
            
            good_outcomes = ["CURED", "COMPLETE", "CHANGED", "SUCCESS", "WRONGLY"]
            blank_variants = ["", "NAN", "N/A", "NONE", "(BLANKS)", "BLANK", "NULL"]
            
            # Identify purely Adverse in This Week
            is_adv_this = ~out_this.str.contains('|'.join(good_outcomes), na=False)
            has_out_this = ~out_this.isin(blank_variants)
            df_adv_this = df_this_raw_full[is_adv_this & has_out_this & (id_this != "")].copy()
            id_out_this = id_this[is_adv_this & has_out_this & (id_this != "")] + "_" + out_this[is_adv_this & has_out_this & (id_this != "")]
            
            # Identify Keys in Prev Week
            prev_keys = set((id_prev + "_" + out_prev).tolist())
            
            # DELTA ENGINE: Keep rows from This Week NOT present in Prev Week
            new_delta_mask = ~id_out_this.isin(prev_keys)
            df_new_adv = df_adv_this[new_delta_mask].copy()
            # EXTRA SAFETY: Ensure they aren't already in the Master
            if not df_new_adv.empty:
                existing_live_ids = set(df_live_raw['Episode ID'].astype(str).str.upper().str.strip().tolist()) if 'Episode ID' in df_live_raw.columns else set()
                new_adv_ids = get_col_series_sync(df_new_adv, ['EPISODE ID'], 12).astype(str).str.upper().str.strip()
                df_new_adv = df_new_adv[~new_adv_ids.isin(existing_live_ids)].copy()
            if df_new_adv.empty:
                st.success("✅ Your Master Database is fully up to date! No new adverse outcomes found this week.")
            else:
                st.warning(f"⚠️ Found {len(df_new_adv)} truly new adverse outcomes that occurred this week.")
                
                # Tagging mechanism for easy sharing
                default_tag = datetime.now(india_tz).strftime('%d %b %Y').upper()
                st.markdown("<div style='background-color: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #b91c1c; margin-bottom: 15px;'>", unsafe_allow_html=True)
                adverse_date_tag = st.text_input("🏷️ Tag for New Outcomes (Used to filter and share the weekly list):", value=default_tag)
                st.markdown("</div>", unsafe_allow_html=True)
                upload_cols = df_live_raw.columns.tolist()
                df_upload = pd.DataFrame(columns=upload_cols)
                
                if 'ADVERSE DATE' in upload_cols: df_upload['ADVERSE DATE'] = adverse_date_tag
                if 'ZONE' in upload_cols: df_upload['ZONE'] = get_col_series_sync(df_new_adv, ['ZONE', 'CURRENT DISTRICT'], 43).values
                if 'TB Unit' in upload_cols: df_upload['TB Unit'] = get_col_series_sync(df_new_adv, ['TB UNIT', 'CURRENT TU'], 2).values
                if 'PHI (Current)' in upload_cols: df_upload['PHI (Current)'] = get_col_series_sync(df_new_adv, ['PHI', 'CURRENT PHI'], 4).values
                if 'PHI (diagnosis)' in upload_cols: df_upload['PHI (diagnosis)'] = get_col_series_sync(df_new_adv, ['SPECTRUM DIAGNOSING PHI'], 9).values
                if 'Facility Type' in upload_cols: df_upload['Facility Type'] = get_col_series_sync(df_new_adv, ['FACILITY TYPE', 'TYPE'], 3).values
                if 'Patient Name' in upload_cols: df_upload['Patient Name'] = get_col_series_sync(df_new_adv, ['PATIENT NAME'], 13).values
                if 'Episode ID' in upload_cols: df_upload['Episode ID'] = get_col_series_sync(df_new_adv, ['EPISODE ID'], 12).values
                if 'AGE' in upload_cols: df_upload['AGE'] = get_col_series_sync(df_new_adv, ['AGE', 'PATIENT AGE'], 52).values
                if 'Mobile No.' in upload_cols: df_upload['Mobile No.'] = get_col_series_sync(df_new_adv, ['PRIMARY PHONE', 'MOBILE NO'], 14).values
                if 'REGIME' in upload_cols: df_upload['REGIME'] = get_col_series_sync(df_new_adv, ['TYPE OF TB REGIMEN', 'REGIMEN'], 61).values
                if 'Diagnosis Date' in upload_cols: df_upload['Diagnosis Date'] = get_col_series_sync(df_new_adv, ['DIAGNOSIS DATE'], 18).values
                if 'Initiation Date' in upload_cols: df_upload['Initiation Date'] = get_col_series_sync(df_new_adv, ['INITIATION DATE'], 64).values
                if 'Outcome Date' in upload_cols: df_upload['Outcome Date'] = get_col_series_sync(df_new_adv, ['OUTCOME DATE'], 79).values
                if 'Treatment Outcome' in upload_cols: df_upload['Treatment Outcome'] = get_col_series_sync(df_new_adv, ['TREATMENT OUTCOME'], 62).values
                
                for d_col in ['Diagnosis Date', 'Initiation Date', 'Outcome Date']:
                    if d_col in df_upload.columns:
                        parsed_d = parse_indian_dates(df_upload[d_col])
                        df_upload[d_col] = parsed_d.dt.strftime('%d-%b-%Y').fillna("")
                if 'On Treatment Days' in upload_cols and 'Initiation Date' in df_upload.columns and 'Outcome Date' in df_upload.columns:
                    init_dt = pd.to_datetime(df_upload['Initiation Date'], errors='coerce')
                    out_dt = pd.to_datetime(df_upload['Outcome Date'], errors='coerce')
                    today_dt = pd.Timestamp.today(tz='Asia/Kolkata').tz_localize(None).normalize()
                    df_upload['On Treatment Days'] = ((out_dt.fillna(today_dt) - init_dt).dt.days).apply(lambda x: f"{int(x)} Days" if pd.notna(x) else "")
                df_upload = df_upload.fillna("")
                
                # ---- Resolve ZONE using the "zone" mapping sub-sheet you added ----
                tu_to_zone, uhc_to_tu_zone = load_zone_lookup()
                if (tu_to_zone or uhc_to_tu_zone) and 'ZONE' in df_upload.columns:
                    tb_unit_col_vals = df_upload['TB Unit'] if 'TB Unit' in df_upload.columns else pd.Series([""] * len(df_upload))
                    phi_col_vals = df_upload['PHI (Current)'] if 'PHI (Current)' in df_upload.columns else pd.Series([""] * len(df_upload))
                    df_upload['ZONE'] = [
                        resolve_zone_for_row(z, tu, phi, tu_to_zone, uhc_to_tu_zone)
                        for z, tu, phi in zip(df_upload['ZONE'], tb_unit_col_vals, phi_col_vals)
                    ]
                elif not (tu_to_zone or uhc_to_tu_zone):
                    st.info(
                        f"ℹ️ Couldn't read the '{ZONE_LOOKUP_SHEET_NAME}' mapping sheet (or it has no usable "
                        "TU/Zone columns) — falling back to the register's own Zone/District column."
                    )
                
                # ---- Clean placeholder/junk values so a blank ZONE never gets
                # ---- pushed to the sheet as a literal "0" or "0.0" ----
                BLANK_LIKE = {"0", "0.0", "NAN", "NONE", "NAT", "<NA>", "-"}
                for junk_col in ["ZONE", "TB Unit", "PHI (Current)", "Facility Type"]:
                    if junk_col in df_upload.columns:
                        df_upload[junk_col] = df_upload[junk_col].astype(str).str.strip()
                        df_upload[junk_col] = df_upload[junk_col].apply(lambda v: "" if v.upper() in BLANK_LIKE else v)
                
                st.dataframe(df_upload, hide_index=True)
                
                # Warn (don't silently push) if ZONE couldn't be matched for any row —
                # this is almost always a column-name mismatch in the source register.
                if 'ZONE' in df_upload.columns:
                    n_blank_zone = int((df_upload['ZONE'].astype(str).str.strip() == "").sum())
                    if n_blank_zone > 0:
                        st.error(
                            f"⚠️ {n_blank_zone} of {len(df_upload)} row(s) have a BLANK Zone. "
                            "This means their TB Unit / PHI (Current) value didn't match anything in the "
                            f"'{ZONE_LOOKUP_SHEET_NAME}' sheet. Add that TB Unit/UHC to the '{ZONE_LOOKUP_SHEET_NAME}' "
                            "sheet, or edit the Zone cell above, before pushing."
                        )
                
                if st.button("🚀 Push to Master Database", type="primary"):
                    with st.spinner("Appending new outcomes to Google Sheets..."):
                        try:
                            values_list = df_upload.values.tolist()
                            new_sheet.append_rows(values_list)
                            st.success(f"✅ Successfully appended {len(values_list)} new outcomes!")
                            get_live_tracker.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Failed to append rows: {e}")
# ==========================================
# 🛠️ REPAIR TOOL — fix rows already pushed with a blank/"0" ZONE
# ==========================================
if st.session_state.role in PUSH_ALLOWED_ROLES:
    with st.expander("🛠️ Repair Blank / \"0\" Zones in Master Database", expanded=False):
        st.markdown(
            "<div style='font-size: 13px; margin-bottom:12px; color:#555;'>"
            f"Scans the Master Sheet for rows where Zone is blank or literally \"0\", and tries to fill it in "
            f"by matching TB Unit / PHI (Current) against the '{ZONE_LOOKUP_SHEET_NAME}' sheet.</div>",
            unsafe_allow_html=True
        )
        tu_to_zone_fix, uhc_to_tu_zone_fix = load_zone_lookup()
        if not df_live_raw.empty and 'ZONE' in df_live_raw.columns:
            zone_raw = df_live_raw['ZONE'].astype(str).str.strip()
            broken_mask = zone_raw.isin(["", "0", "0.0"]) | zone_raw.str.upper().isin(["NAN", "NONE", "NAT", "<NA>"])
            df_broken = df_live_raw[broken_mask].copy()
            if df_broken.empty:
                st.success("✅ No blank/\"0\" Zone values found in the Master Sheet.")
            elif not (tu_to_zone_fix or uhc_to_tu_zone_fix):
                st.error(f"Found {len(df_broken)} broken row(s), but the '{ZONE_LOOKUP_SHEET_NAME}' sheet couldn't be read.")
            else:
                st.warning(f"Found {len(df_broken)} row(s) with a blank or \"0\" Zone.")
                phi_col_name = 'PHI (Current)' if 'PHI (Current)' in df_broken.columns else None
                tu_col_name = 'TB Unit' if 'TB Unit' in df_broken.columns else None
                fixes = []
                for idx, row in df_broken.iterrows():
                    tb_unit_val = row.get(tu_col_name, '') if tu_col_name else ''
                    phi_val = row.get(phi_col_name, '') if phi_col_name else ''
                    new_zone = resolve_zone_for_row("", tb_unit_val, phi_val, tu_to_zone_fix, uhc_to_tu_zone_fix)
                    fixes.append({
                        "Episode ID": row.get('Episode ID', ''),
                        "TB Unit": tb_unit_val,
                        "PHI (Current)": phi_val,
                        "Resolved Zone": new_zone if new_zone else "❌ Still unresolved",
                    })
                df_fixes_preview = pd.DataFrame(fixes)
                st.dataframe(df_fixes_preview, hide_index=True)
                n_resolvable = int((df_fixes_preview["Resolved Zone"] != "❌ Still unresolved").sum())
                st.info(
                    f"{n_resolvable} of {len(fixes)} can be auto-fixed from the '{ZONE_LOOKUP_SHEET_NAME}' sheet. "
                    f"The rest need that TB Unit/UHC added to '{ZONE_LOOKUP_SHEET_NAME}', or manual entry in the line list below."
                )
                if n_resolvable > 0 and st.button("🔧 Apply Auto-Fixable Zones to Master Sheet"):
                    with st.spinner("Updating Zone column in Google Sheets..."):
                        try:
                            sheet_headers = new_sheet.row_values(1)
                            header_to_col = {h: i + 1 for i, h in enumerate(sheet_headers) if h}
                            zone_col_idx = header_to_col.get('ZONE')
                            ep_col_idx = header_to_col.get('Episode ID', 8)
                            if not zone_col_idx:
                                st.error("Could not find a 'ZONE' column header in the Master Sheet.")
                            else:
                                updates = []
                                for f_row, (idx, row) in zip(fixes, df_broken.iterrows()):
                                    if f_row["Resolved Zone"] == "❌ Still unresolved":
                                        continue
                                    ep_id = str(row.get('Episode ID', '')).strip()
                                    if not ep_id:
                                        continue
                                    cell = new_sheet.find(ep_id, in_column=ep_col_idx)
                                    if cell:
                                        letter = colnum_to_letter(zone_col_idx)
                                        updates.append({"range": f"{letter}{cell.row}", "values": [[f_row["Resolved Zone"]]]})
                                if updates:
                                    new_sheet.batch_update(updates)
                                    st.success(f"✅ Fixed Zone for {len(updates)} row(s).")
                                    get_live_tracker.clear()
                                    st.rerun()
                                else:
                                    st.info("Nothing to update.")
                        except Exception as e:
                            st.error(f"❌ Failed to update Zones: {e}")
        else:
            st.info("No ZONE column found in the Master Sheet to repair.")
# ==========================================
# 📝 LINE LIST SECTION — quick-pick date filters directly above the table
# ==========================================
st.markdown("<div class='section-title'>🗂️ Interactive Line List &amp; Field Data Entry</div>", unsafe_allow_html=True)
st.markdown("<div class='filter-strip'>", unsafe_allow_html=True)
top_label_col, top_reset_col = st.columns([5, 1])
with top_label_col:
    st.markdown("<div class='label'>📅 Date Range Filters — pick a quick range, jump straight to a month, or choose Custom Range (affects totals &amp; breakdowns above)</div>", unsafe_allow_html=True)
with top_reset_col:
    if st.button("↺ Reset Filters", use_container_width=True):
        for k in [
            "diag_preset", "init_preset", "out_preset",
            "diag_custom", "init_custom", "out_custom",
            "diag_month_anchor", "init_month_anchor", "out_month_anchor",
            "linelist_outcome_filter", "linelist_zone_filter", "linelist_entry_status",
        ]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()
def render_date_filter_col(label, preset_key, custom_key, month_key):
    st.markdown(f"<div class='filter-col-label'>{label}</div>", unsafe_allow_html=True)
    preset_val = st.session_state.get(preset_key, "All Time")
    sel_preset = st.selectbox(f"{label} preset", DATE_PRESETS, index=DATE_PRESETS.index(preset_val), key=preset_key, label_visibility="collapsed")
    if sel_preset == "Custom Range":
        st.date_input(f"Pick {label} dates", value=st.session_state.get(custom_key, []), key=custom_key, label_visibility="collapsed")
    elif sel_preset == "Jump to Month":
        anchor = st.session_state.get(month_key, today_first)
        cp, cl, cn = st.columns([1, 3, 1])
        with cp:
            if st.button("◀", key=f"{month_key}_prev", use_container_width=True):
                st.session_state[month_key] = shift_month(anchor, -1)
                st.rerun()
        with cl:
            st.markdown(f"<div style='text-align:center; font-weight:800; padding-top:6px; color:#0A3A6E;'>{anchor.strftime('%B %Y')}</div>", unsafe_allow_html=True)
        with cn:
            if st.button("▶", key=f"{month_key}_next", use_container_width=True):
                st.session_state[month_key] = shift_month(anchor, 1)
                st.rerun()
d1, d2, d3 = st.columns(3)
with d1: render_date_filter_col("Diagnosis Date", "diag_preset", "diag_custom", "diag_month_anchor")
with d2: render_date_filter_col("Initiation Date", "init_preset", "init_custom", "init_month_anchor")
with d3: render_date_filter_col("Outcome Date", "out_preset", "out_custom", "out_month_anchor")
st.markdown("</div>", unsafe_allow_html=True)
if not df_live_filtered.empty:
    df_display = df_live_filtered.copy()
    df_display = df_display.drop(columns=[c for c in df_display.columns if c.endswith('_dt')], errors='ignore')
    missing_cols = [c for c in REQUIRED_ENTRY_COLS if c not in df_display.columns]
    
    if missing_cols:
        st.error("⚠️ Setup Required: your Google Sheet is missing these column headers. Add them exactly as written, in row 1:")
        st.markdown("<div style='font-size:13px; color:#64748b;'>" + "<br>".join([f"• {c}" for c in missing_cols]) + "</div>", unsafe_allow_html=True)
        st.stop()
        
    TEXT_LIKE_COLS = [c for c in REQUIRED_ENTRY_COLS if c not in (COL_MONTHS_RESIDING, COL_TRANSFER_OUT_DATE, COL_REJECT_DATE)]
    for col in TEXT_LIKE_COLS:
        df_display[col] = df_display[col].fillna("").astype(str)
        
    df_display[COL_MONTHS_RESIDING] = pd.to_numeric(df_display[COL_MONTHS_RESIDING], errors='coerce')
    df_display[COL_TRANSFER_OUT_DATE] = pd.to_datetime(df_display[COL_TRANSFER_OUT_DATE], errors='coerce', dayfirst=True)
    df_display[COL_REJECT_DATE] = pd.to_datetime(df_display[COL_REJECT_DATE], errors='coerce', dayfirst=True)
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        opts_out = safe_unique_options(df_options_source['Treatment Outcome']) if 'Treatment Outcome' in df_options_source.columns else []
        st.multiselect("Filter by Treatment Outcome", opts_out, key="linelist_outcome_filter")
    with f2:
        opts_zone = safe_unique_options(df_options_source['ZONE']) if 'ZONE' in df_options_source.columns else []
        st.multiselect("Filter by Zone", opts_zone, key="linelist_zone_filter")
    with f3:
        opts_adv = safe_unique_options(df_options_source['ADVERSE DATE']) if 'ADVERSE DATE' in df_options_source.columns else []
        st.multiselect("Filter by Adverse Date Tag", opts_adv, key="linelist_adverse_filter")
    with f4:
        st.selectbox("Data Entry Status", ["All", "Pending Entry", "Completed"], key="linelist_entry_status")
    # Apply the new ADVERSE DATE tag filter
    sel_adv_val = st.session_state.get("linelist_adverse_filter", [])
    if sel_adv_val and 'ADVERSE DATE' in df_live_filtered.columns:
        df_display = df_display[df_display['ADVERSE DATE'].isin(sel_adv_val)]
    df_display = df_display.reset_index(drop=True)
    editable_cols = [c for c in REQUIRED_ENTRY_COLS]
    locked_cols = [col for col in df_display.columns if col not in editable_cols]
    
    column_configuration = {
        COL_MONTHS_RESIDING: st.column_config.NumberColumn(COL_MONTHS_RESIDING, min_value=0, step=1, format="%d"),
        COL_RESIDED_THROUGHOUT: st.column_config.SelectboxColumn(COL_RESIDED_THROUGHOUT, options=["", "YES", "NO"]),
        COL_PLACE_OF_DEATH: st.column_config.SelectboxColumn(
            COL_PLACE_OF_DEATH, options=PLACE_OF_DEATH_OPTIONS,
            help="Only applicable when Treatment Outcome is Died"
        ),
        COL_COMORBIDITY: st.column_config.SelectboxColumn(
            COL_COMORBIDITY, options=COMORBIDITY_OPTIONS,
            help="Select condition. If Multiple, log details in Remarks."
        ),
        COL_STATE_NON_AMC: st.column_config.SelectboxColumn(COL_STATE_NON_AMC, options=INDIAN_STATES_UTS),
        COL_DISTRICT_NON_AMC: st.column_config.TextColumn(COL_DISTRICT_NON_AMC),
        COL_TRANSFER_REASON: st.column_config.SelectboxColumn(COL_TRANSFER_REASON, options=TRANSFER_REASON_OPTIONS),
        COL_TRANSFER_OUT_DATE: st.column_config.DateColumn(COL_TRANSFER_OUT_DATE, format="DD-MMM-YYYY"),
        COL_REJECT_DATE: st.column_config.DateColumn(COL_REJECT_DATE, format="DD-MMM-YYYY", help="Only applicable when the record is Rejected"),
        COL_REMARKS: st.column_config.TextColumn(COL_REMARKS),
    }
    
    edited_df = st.data_editor(
        df_display,
        use_container_width=True,
        hide_index=True,
        disabled=locked_cols,
        column_config=column_configuration,
        key="master_data_editor"
    )
    
    # Download Button
    csv_data = df_display.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download This Line List (CSV)", csv_data, "Adverse_Outcomes_LineList.csv", "text/csv")
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
                            try:
                                if pd.isna(v):
                                    return ""
                            except (TypeError, ValueError):
                                pass
                            if hasattr(v, "strftime"):
                                return v.strftime("%d-%b-%Y")
                            return str(v)
                        field_values = {col: val_for(col) for col in editable_cols}
                        field_values[COL_SUBMITTED_BY] = st.session_state.current_user
                        field_values[COL_LAST_UPDATED] = datetime.now(india_tz).strftime("%d-%b-%Y %H:%M:%S")
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
                get_live_tracker.clear()
                st.rerun()
else:
    st.info("ℹ️ No records found for your scope in the New Sheet.")
