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
            has_baseline = True
    except Exception:
        has_baseline = False

is_coach = st.query_params.get("role") == "coach"

if not st.session_state.user:
    navigation_options = ["Dashboard"]
elif not has_baseline:
    navigation_options = ["Dashboard", "Challenge Measurements"]
else:
    navigation_options = ["Dashboard", "Daily Log", "Benchmark Workout", "Challenge Measurements", "Leaderboard"]

if is_coach:
    navigation_options.append("Admin Configuration Panel")

try:
    default_selection_index = navigation_options.index(st.session_state.nav_page)
except ValueError:
    default_selection_index = 0
    st.session_state.nav_page = "Dashboard"

page = st.sidebar.radio("Go To", navigation_options, index=default_selection_index)
st.session_state.nav_page = page

# --- 7. SIGN UP & LOGIN INTERFACE ---
if not st.session_state.user and page != "Admin Configuration Panel":
    st.markdown("<h2 style='text-transform: uppercase; letter-spacing: 1px;'>Driven Community Fitness Challenge</h2>", unsafe_allow_html=True)
    auth_mode = st.radio("Choose Action", ["Login", "Register Account"])
    
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    
    if auth_mode == "Register Account":
        fullname = st.text_input("Full Name")
        age = st.number_input("Age", min_value=12, max_value=100, value=30)
        gender = st.radio("Gender / Division", ["Male", "Female"])
        
        if st.button("Sign Up"):
            try:
                res = supabase.auth.sign_up({"email": email, "password": password})
                if res.user:
                    supabase.table("user_profiles").insert({
                        "user_id": res.user.id, 
                        "full_name": fullname, 
                        "email": email, 
                        "age": age,
                        "gender": gender
                    }).execute()
                    
                    st.session_state.user = {"id": res.user.id, "email": res.user.email}
                    st.success("Welcome aboard! Initializing your dashboard...")
                    st.rerun()
            except Exception as e:
                st.error(f"Signup error: {e}")
    else:
        if st.button("Login"):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                if res.user:
                    st.session_state.user = {"id": res.user.id, "email": res.user.email}
                    st.rerun()
            except Exception as e:
                st.error("Invalid login credentials.")
    st.stop()

# --- 8. REVISION-AWARE SELECTOR ---
def fraction_selector(label, unique_key, current_val=0.0):
    st.markdown(f"<div style='margin-top: 10px; font-weight: 600; color: #FAFAFA;'>{label}</div>", unsafe_allow_html=True)
    default_inch, default_frac_idx = get_inch_and_frac_index(current_val)
    
    c1, c2, c3 = st.columns()
    whole_opts = list(range(0, 80))
    def_inch_idx = whole_opts.index(default_inch) if default_inch in whole_opts else 0
    
    whole = c1.selectbox("Inches", whole_opts, index=def_inch_idx, key=f"{unique_key}_w")
    frac = c2.selectbox("Fraction", FRACTIONS, index=default_frac_idx, key=f"{unique_key}_f")
    return whole + FRACTION_VALUES[frac]

# --- 9. PAGES CONTENT IMPLEMENTATION ---
if page == "Challenge Measurements":
    st.markdown("<h2 style='text-transform: uppercase; letter-spacing: 1px;'>Challenge Measurements</h2>", unsafe_allow_html=True)
    
    start_dt = challenge_start_date
    try:
        weeks_count = int(settings.get("challenge_duration_weeks", 6))
    except (ValueError, TypeError):
        weeks_count = 6
    total_challenge_days = weeks_count * 7
    end_dt = start_dt + timedelta(days=total_challenge_days)
    days_since_start = (date.today() - start_dt).days
    
    try:
        existing_baseline_query = supabase.table("user_baselines").select("*").eq("user_id", st.session_state.user["id"]).execute()
        b_data = safe_extract(existing_baseline_query.data)
    except Exception:
        b_data = {}
    
    if days_since_start <= 7:
        st.markdown("### Step 1: Enter Your Starting Measurements")
        if has_baseline:
            st.info("✏️ **Revision Mode Active:** Your currently saved measurements are pre-populated below. You can modify any field and save changes
