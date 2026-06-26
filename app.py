import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from supabase import create_client, Client
from PIL import Image
import io
import base64

# --- 1. CRITICAL PAGE CONFIGURATION ---
st.set_page_config(page_title="Driven Gym Portal", page_icon="💪", layout="wide")

# --- 2. SECURE DATABASE CONNECTION ---
@st.cache_resource
def init_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

try:
    supabase = init_supabase()
except Exception:
    st.error("🔒 Cloud Vault Connection Pending. Please configure your Streamlit Secrets in the app settings.")
    st.stop()

# --- 3. SAFE DATA CONVERSION HELPERS (NO LOOPS) ---
FRACTIONS = ["0", "1/16", "1/8", "3/16", "1/4", "5/16", "3/8", "7/16", "1/2", "9/16", "5/8", "11/16", "3/4", "13/16", "7/8", "15/16"]
FRACTION_VALUES = {f: i/16 for i, f in enumerate(FRACTIONS)}

def safe_extract(data_source):
    """Safely extracts a dictionary in exactly one linear step. Zero risk of infinite loops."""
    try:
        if isinstance(data_source, list) and len(data_source) > 0:
            return data_source if isinstance(data_source, dict) else {}
        if isinstance(data_source, dict):
            return data_source
    except Exception:
        pass
    return {}

def float_to_fraction(val):
    try:
        if val is None or float(val) == 0: return "0"
        val = float(val)
        whole = int(val)
        frac = val - whole
        closest_frac = min(FRACTIONS, key=lambda x: abs(FRACTION_VALUES[x] - frac))
        return f"{whole}\"" if closest_frac == "0" else f"{whole} {closest_frac}\""
    except Exception:
        return "0"

def get_inch_and_frac_index(val):
    try:
        if val is None: return 0, 0
        val = float(val)
        whole = int(val)
        frac = val - whole
        closest_frac = min(FRACTIONS, key=lambda x: abs(FRACTION_VALUES[x] - frac))
        return whole, FRACTIONS.index(closest_frac)
    except Exception:
        return 0, 0

def get_success_badge(rate):
    if rate >= 90: return f"{rate:.1f}% — On Fire 🔥"
    if rate >= 75: return f"{rate:.1f}% — On Track 🏃‍♂️"
    if rate >= 60: return f"{rate:.1f}% — Needs Focus ⚠️"
    return f"{rate:.1f}% — Danger Zone 🛑"

# --- 4. LINEAR CONFIGURATION ENGINE ---
DEFAULT_SETTINGS = {
    "admin_secret_key": "driven2026", 
    "challenge_duration_weeks": 6, 
    "global_start_date": "2026-06-22", 
    "workout_name": "TBD", 
    "workout_notes": ""
}

try:
    settings_query = supabase.table("challenge_settings").select("*").eq("id", 1).execute()
    settings = safe_extract(settings_query.data) if settings_query.data else DEFAULT_SETTINGS
except Exception:
    settings = DEFAULT_SETTINGS

challenge_start_date = date(2026, 6, 22)
raw_start_date = settings.get("global_start_date", "2026-06-22")

if isinstance(raw_start_date, str):
    try:
        challenge_start_date = datetime.strptime(raw_start_date, "%Y-%m-%d").date()
    except ValueError:
        pass
elif hasattr(raw_start_date, "year"):
    challenge_start_date = raw_start_date

# --- 5. USER STATE APP FLOW ---
if "user" not in st.session_state:
    st.session_state.user = None

if "nav_page" not in st.session_state:
    st.session_state.nav_page = "Dashboard"

# --- 6. SIDEBAR NAVIGATION ---
st.sidebar.markdown("### CHALLENGE MENU")

has_baseline = False
if st.session_state.user:
    st.sidebar.write(f"Logged in: **{st.session_state.user['email']}**")
    if st.sidebar.button("Log Out"):
        st.session_state.user = None
        st.session_state.nav_page = "Dashboard"
        st.rerun()
    
    try:
        baseline_check = supabase.table("user_baselines").select("start_weight").eq("user_id", st.session_state.user["id"]).execute()
        b_check_row = safe_extract(baseline_check.data)
        if b_check_row and b_check_row.get("start_weight") is not None:
