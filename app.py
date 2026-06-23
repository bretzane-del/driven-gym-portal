import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from supabase import create_client, Client
from PIL import Image
import io
import base64

# --- CRITICAL: MUST BE THE ABSOLUTE FIRST STREAMLIT COMMAND ---
st.set_page_config(page_title="Driven Gym Portal", page_icon="💪", layout="wide")

# --- LIVE DIAGNOSTIC PIPELINE ---
st.write("✨ *System Status: Initializing core app engines...*")

# --- SECURE DATABASE CONNECTION ---
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

st.write("⚡ *System Status: Establishing connection to secure cloud vault...*")
try:
    supabase = init_supabase()
except Exception as e:
    st.error("🔒 Cloud Vault Connection Pending. Please configure your Streamlit Secrets.")
    st.stop()

# --- DATA UNPACKING & CONVERSION HELPERS ---
FRACTIONS = ["0", "1/16", "1/8", "3/16", "1/4", "5/16", "3/8", "7/16", "1/2", "9/16", "5/8", "11/16", "3/4", "13/16", "7/8", "15/16"]
FRACTION_VALUES = {f: i/16 for i, f in enumerate(FRACTIONS)}

def extract_dict(data_source):
    """Safely extracts a single dictionary out of deeply nested list structures."""
    if not data_source:
        return {}
    current = data_source
    while isinstance(current, list):
        if len(current) > 0:
            current = current
        else:
            return {}
    return current if isinstance(current, dict) else {}

def float_to_fraction(val):
    if not val or val == 0: return "0"
    whole = int(val)
    frac = val - whole
    closest_frac = min(FRACTIONS, key=lambda x: abs(FRACTION_VALUES[x] - frac))
    return f"{whole}\"" if closest_frac == "0" else f"{whole} {closest_frac}\""

def get_inch_and_frac_index(val):
    """Parses saved decimal floats back into separate whole inches and selectbox indices."""
    if not val:
        return 0, 0
    whole = int(val)
    frac = val - whole
    closest_frac = min(FRACTIONS, key=lambda x: abs(FRACTION_VALUES[x] - frac))
    return whole, FRACTIONS.index(closest_frac)

# --- DYNAMIC SUCCESS GRADING SCALE ---
def get_success_badge(rate):
    if rate >= 90: return f"{rate:.1f}% — On Fire 🔥"
    if rate >= 75: return f"{rate:.1f}% — On Track 🏃‍♂️"
    if rate >= 60: return f"{rate:.1f}% — Needs Focus ⚠️"
    return f"{rate:.1f}% — Danger Zone 🛑"

# --- DEFENSIVE SYSTEM SETTINGS LOAD ---
st.write("📡 *System Status: Fetching global challenge launch configurations...*")
DEFAULT_SETTINGS = {
    "admin_secret_key": "driven2026", 
    "challenge_duration_weeks": 6, 
    "global_start_date": "2026-06-22", 
    "workout_name": "TBD", 
    "workout_notes": ""
}

try:
    settings_query = supabase.table("challenge_settings").select("*").eq("id", 1).execute()
    settings = extract_dict(settings_query.data) if settings_query.data else DEFAULT_SETTINGS
except Exception as e:
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

# --- USER STATE APP FLOW ---
if "user" not in st.session_state:
    st.session_state.user = None

if "nav_page" not in st.session_state:
    st.session_state.nav_page = "Dashboard"

# --- SIDEBAR NAVIGATION WITH SECURE FUNNEL GATES ---
st.sidebar.markdown("### CHALLENGE MENU")

has_baseline = False
if st.session_state.user:
    st.sidebar.write(f"Logged in: **{st.session_state.user['email']}**")
    if st.sidebar.button("Log Out"):
        st.session_state.user = None
        st.session_state.nav_page = "Dashboard"
        st.rerun()
    
    # Strict Verification: Only unlock advanced modules if starting weight exists
    st.write("🔐 *System Status: Validating user onboarding credentials...*")
    try:
        baseline_check = supabase.table("user_baselines").select("start_weight").eq("user_id", st.session_state.user["id"]).execute()
        b_check_row = extract_dict(baseline_check.data)
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

# --- SIGN UP & LOGIN INTERFACE ---
if not st.session_state.user and page != "Admin Configuration Panel":
    # Clean up diagnostic text immediately once we confirm we reached the login screen safely
    st.empty() 
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

# --- HIGH-COMPACT REVISION-AWARE SELECTOR ---
def fraction_selector(label, unique_key, current_val=0.0):
    st.markdown(f"<div style='margin-top: 10px; font-weight: 600; color: #FAFAFA;'>{label}</div>", unsafe_allow_html=True)
    default_inch, default_frac_idx = get_inch_and_frac_index(current_val)
    
    c1, c2, c3 = st.columns()
    whole_opts = list(range(0, 80))
    def_inch_idx = whole_opts.index(default_inch) if default_inch in whole_opts else 0
    
    whole = c1.selectbox("Inches", whole_opts, index=def_inch_idx, key=f"{unique_key}_w")
    frac = c2.selectbox("Fraction", FRACTIONS, index=default_frac_idx, key=f"{unique_key}_f")
    return whole + FRACTION_VALUES[frac]

# --- PAGES CONTENT IMPLEMENTATION ---
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
        b_data = extract_dict(existing_baseline_query.data)
    except Exception:
        b_data = {}
    
    # PHASE 1: Initial Baseline Window (First 7 Days)
    if days_since_start <= 7:
        st.markdown("### Step 1: Enter Your Starting Measurements")
        if has_baseline:
            st.info("✏️ **Revision Mode Active:** Your currently saved measurements are pre-populated below. You can modify any field and save changes until your initial challenge week expires.")
            current_weight = b_data.get("start_weight")
        else:
            current_weight = None
        
        with st.form("baseline_form"):
            st.markdown("#### Weight")
            w = st.number_input("Starting Weight (lbs)", min_value=0.0, step=0.1, value=current_weight, placeholder="Enter weight...")
            
            st.markdown("---")
            st.markdown("#### Measurements")
            
            ch = fraction_selector("Chest", "start_chest", b_data.get("start_chest", 0.0))
            wa = fraction_selector("Waist", "start_waist", b_data.get("start_waist", 0.0))
            hi = fraction_selector("Hips", "start_hips", b_data.get("start_hips", 0.0))
            la = fraction_selector("Left Arm", "start_chest_arm_l", b_data.get("start_left_arm", 0.0))
            ra = fraction_selector("Right Arm", "start_chest_arm_r", b_data.get("start_right_arm", 0.0))
            lt = fraction_selector("Left Thigh", "start_chest_thigh_l", b_data.get("start_left_thigh", 0.0))
            rt = fraction_selector("Right Thigh", "start_chest_thigh_r", b_data.get("start_right_thigh", 0.0))
            
            st.markdown("---")
            st.subheader("Private Profile Photo (Optional)")
            uploaded_photo = st.file_uploader("Snap or select a baseline photo", type=["jpg", "jpeg", "png"])
            
            if st.form_submit_button("Save", type="primary"):
                if w is None:
                    st.error("Starting weight entry is required to save your metrics.")
                else:
                    img_str = b_data.get("before_photo", "")
                    if uploaded_photo is not None:
                        try:
                            img = Image.open(uploaded_photo)
                            if img.mode in ("RGBA", "P"):
                                img = img.convert("RGB")
                            img.thumbnail((400, 400))
                            buffered = io.BytesIO()
                            img.save(buffered, format="JPEG", quality=75)
                            img_str = base64.b64encode(buffered.getvalue()).decode()
                        except Exception:
                            pass
                    
                    try:
                        supabase.table("user_baselines").upsert({
                            "user_id": st.session_state.user["id"],
                            "start_weight": w, "start_chest": ch, "start_waist": wa, "start_hips": hi,
                            "start_left_arm": la, "start_right_arm": ra, "start_left_thigh": lt, "start_right_thigh": rt,
                            "before_photo": img_str
                        }).execute()
                        st.success("Measurements recorded successfully!")
                        st.session_state.nav_page = "Dashboard"
                        st.rerun()
                    except Exception as db_err:
                        st.error(f"Database error: {db_err}")

    # PHASE 2: Final Transformation Window
    elif days_since_start >= (total_challenge_days - 7) and days_since_start <= (total_challenge_days + 7):
        st.markdown("### Step 2: Submit Your Final Transformation Numbers")
        with st.form("final_form"):
            st.subheader("Finishing Measurements")
            w_end = st.number_input("Ending Weight (lbs)", min_value=0.0, step=0.1, value=b_data.get("end_weight"), placeholder="Enter weight...")
            ch_end = fraction_selector("Ending Chest", "end_chest", b_data.get("end_chest", 0.0))
            wa_end = fraction_selector("Ending Waist", "end_waist", b_data.get("end_waist", 0.0))
            hi_end = fraction_selector("Ending Hips", "end_hips", b_data.get("end_hips", 0.0))
            la_end = fraction_selector("Ending Left Arm", "end_arm_l", b_data.get("end_left_arm", 0.0))
            ra_end = fraction_selector("Ending Right Arm", "end_arm_r", b_data.get("end_right_arm", 0.0))
            lt_end = fraction_selector("Ending Left Thigh", "end_thigh_l", b_data.get("end_left_thigh", 0.0))
            rt_end = fraction_selector("Ending Right Thigh", "end_thigh_r", b_data.get("end_right_thigh", 0.0))
            
            if st.form_submit_button("Save", type="primary"):
                try:
                    supabase.table("user_baselines").upsert({
                        "user_id": st.session_state.user["id"],
                        "end_weight": w_end, "end_chest": ch_end, "end_waist": wa_end, "end_hips": hi_end,
                        "end_left_arm": la_end, "end_right_arm": ra_end, "end_left_thigh": lt_end, "end_right_thigh": rt_end
                    }).execute()
                    st.success("Finishing numbers locked in!")
                    st.session_state.nav_page = "Dashboard"
                    st.rerun()
                except Exception as db_err:
                    st.error(f"Database error: {db_err}")

    # PHASE 3: Mid-Challenge Locked State
    else:
        st.markdown("### Measurement Logs Locked")
        st.subheader("🔒 Initial Baselines Secured")
        st.info("Initial measurements are safely encrypted. Your finishing submission window will automatically open during the final week of the challenge.")
        st.markdown("#### Your Locked Starting Stats:")
        st.write(f"**Starting Weight:** {b_data.get('start_weight', 0.0)} lbs")

elif page == "Benchmark Workout":
    st.markdown("<h2 style='text-transform: uppercase; letter-spacing: 1px;'>Benchmark Workout Score Entry</h2>", unsafe_allow_html=True)
    st.info(f"🏋️‍♂️ **Official Workout Designation:** {settings.get('workout_name', 'TBD')}\n\n*Instructions:* {settings.get('workout_notes', 'Performance parameters pending update from coach.')}")
    
    try:
        existing_baseline = supabase.table("user_baselines").select("benchmark_score").eq("user_id", st.session_state.user["id"]).execute()
        b_row = extract_dict(existing_baseline.data)
        current_saved_score = b_row.get("benchmark_score", "") if b_row else ""
    except Exception:
        current_saved_score = ""
    
    if current_saved_score:
        st.success(f"Locked Score on Profile: **{current_saved_score}**")
        
    with st.form("workout_score_form"):
        score = st.text_input("Enter Your Workout Performance Result", value=current_saved_score, placeholder="e.g., 14:22, 185 lbs, 4 Rounds...")
        if st.form_submit_button("Submit Score Parameters"):
            try:
                supabase.table("user_baselines").upsert({
                    "user_id": st.session_state.user["id"],
                    "benchmark_score": score
                }).execute()
                st.success("Performance metrics successfully recorded!")
                st.rerun()
            except Exception as db_err:
                st.error(f"Database error: {db_err}")

elif page == "Daily Log":
    st.markdown("<h2 style='text-transform: uppercase; letter-spacing: 1px;'>Daily Performance Log</h2>", unsafe_allow_html=True)
    log_date = st.date_input("Date", date.today())
    
    try:
        existing = supabase.table("daily_logs").select("*").eq("user_id", st.session_state.user["id"]).eq("log_date", str(log_date)).execute()
        log_data = extract_dict(existing.data) if existing.data else {"diet": False, "water": False, "sleep": False, "exercise": False}
    except Exception:
        log_data = {"diet": False, "water": False, "sleep": False, "exercise": False}
    
    diet = st.checkbox("Strict Paleo Menu Adherence — **5 pts**", value=log_data.get("diet", False))
    water = st.checkbox("Water Tracker Placeholder — **1 pt**", value=log_data.get("water", False))
    sleep = st.checkbox("Sleep Metrics (7-8+ Rest Hours) — **1 pt**", value=log_data.get("sleep", False))
    exercise = st.checkbox("Daily Activity or Designated Mobility Session — **1 pt**", value=log_data.get("exercise", False))
    
    score = (5 if diet else 0) + (1 if water else 0) + (1 if sleep else 0) + (1 if exercise else 0)
    st.metric("Points Scored", f"{score} / 8")
    
    if st.button("Submit Daily Points"):
        try:
            supabase.table("daily_logs").upsert({
                "user_id": st.session_state.user["id"], "log_date": str(log_date),
                "diet": diet, "water": water, "sleep": sleep, "exercise": exercise, "daily_score": score
            }).execute()
            st.success("Points posted successfully!")
        except Exception as db_err:
            st.error(f"Database error: {db_err}")

elif page == "Dashboard":
    st.markdown("<h2 style='text-transform: uppercase; letter-spacing: 1px;'>Your Progress Dashboard</h2>", unsafe_allow_html=True)
    
    if not has_baseline:
        st.markdown("<br>", unsafe_allow_html=True)
        st.warning("👉 Enter your 'starting' measurements to get set up for the Challenge!")
        if st.button("Go Lock In Your Measurements Now →", type="primary"):
            st.session_state.nav_page = "Challenge Measurements"
            st.rerun()
    else:
        try:
            baselines = supabase.table("user_baselines").select("*").eq("user_id", st.session_state.user["id"]).execute()
            logs = supabase.table("daily_logs").select("*").eq("user_id", st.session_state.user["id"]).execute()
            b = extract_dict(baselines.data)
            logs_list = logs.data if logs.data else []
        except Exception:
            b = {}
            logs_list = []
            
        start_dt = challenge_start_date
        try:
            total_weeks = int(settings.get("challenge_duration_weeks", 6))
        except (ValueError, TypeError):
            total_weeks = 6
        total_days = total_weeks * 7
        days_in = max((date.today() - start_dt).days + 1, 1)
        
        total_earned = sum([day.get("daily_score", 0) for day in logs_list if isinstance(day, dict)])
        possible_so_far = min(days_in, total_days) * 8
        success_rate = (total_earned / possible_so_far * 100) if possible_so_far > 0 else 100.0
        
        st.markdown("### ⚡ Current Momentum")
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.metric(label="Timeline Milestone", value=f"Day {min(days_in, total_days)}", delta=f"out of {total_days} total days")
        with c2:
            st.metric(label="Accumulated Points", value=f"{total_earned} Pts", delta="earned so far")
        with c3:
            st.metric(label="Your Success Rate", value=f"{success_rate:.1f}%", delta=get_success_badge(success_rate))
        
        st.markdown("---")
        
        st.markdown("### 🔒 Sealed Personal Configuration (Private)")
        st.caption("These numbers are safely encrypted. No other members or leaderboards can view these metrics.")
        
        dc1, dc2, dc3, dc4 = st.columns(4)
        with dc1:
            st.info(f"**Starting Weight**\n\n### {b.get('start_weight', 0.0)} lbs")
        with dc2:
            st.info(f"**Chest / Waist / Hips**\n\n### {float_to_fraction(b.get('start_chest', 0.0))} / {float_to_fraction(b.get('start_waist', 0.0))} / {float_to_fraction(b.get('start_hips', 0.0))}")
        with dc3:
            st.info(f"**Arms (L / R)**\n\n### {float_to_fraction(b.get('start_left_arm', 0.0))} / {float_to_fraction(b.get('start_right_arm', 0.0))}")
        with dc4:
            st.info(f"**Thighs (L / R)**\n\n### {float_to_fraction(b.get('start_left_thigh', 0.0))} / {float_to_fraction(b.get('start_right_thigh', 0.0))}")

elif page == "Leaderboard":
    st.markdown("<h2 style='text-transform: uppercase; letter-spacing: 1px;'>The Consolidated Gym Standings</h2>", unsafe_allow_html=True)
    
    try:
        profiles = supabase.table("user_profiles").select("*").execute()
        all_logs = supabase.table("daily_logs").select("*").execute()
        all_baselines = supabase.table("user_baselines").select("*").execute()
        
        leaderboard_data = []
        for p in profiles.data:
            user_points = sum([l.get("daily_score", 0) for l in all_logs.data if isinstance(l, dict) and l.get("user_id") == p.get("user_id")])
            ub = next((b for b in all_baselines.data if isinstance(b, dict) and b.get("user_id") == p.get("user_id")), None)
            
            lbs_lost = 0.0
            if ub and ub.get("end_weight") and ub.get("start_weight"):
                lbs_lost = float(ub["start_weight"] - ub["end_weight"])
            
            leaderboard_data.append({
                "Athlete Name": p.get("full_name", "Anonymous"),
                "Division": p.get("gender", "Unassigned"),
                "Total Points": user_points,
                "Pounds Dropped": f"{lbs_lost:.1f} lbs" if lbs_lost > 0 else "0.0 lbs",
            })
            
        df = pd.DataFrame(leaderboard_data).sort_values(by="Total Points", ascending=False)
        st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(f"Could not load leaderboard stats: {e}")

elif page == "Admin Configuration Panel":
    st.markdown("<h2 style='text-transform: uppercase; letter-spacing: 1px;'>Shared Executive Administration Panel</h2>", unsafe_allow_html=True)
    master_key = settings.get("admin_secret_key", "driven2026")
    input_key = st.text_input("Enter Master Secret Admin Key", type="password")
    
    if input_key == master_key:
        st.success("Access Verified.")
        with st.form("admin_form"):
            duration_options = (4, 5, 6, 8)
            try:
                current_weeks = int(settings.get("challenge_duration_weeks", 6))
                default_selection_index = duration_options.index(current_weeks)
            except (ValueError, TypeError):
                default_selection_index = 2
            
            new_dur = st.selectbox("Challenge Duration (Weeks)", duration_options, index=default_selection_index)
            new_start = st.date_input("Global Challenge Launch Date", challenge_start_date)
            new_wkout = st.text_input("Global Benchmark Workout Title", value=settings.get("workout_name", "TBD"))
            new_notes = st.text_area("Scoring Rules & Instructions Box", value=settings.get("workout_notes", ""))
            
            if st.form_submit_button("Apply Global System Overrides"):
                try:
                    supabase.table("challenge_settings").upsert({
                        "id": 1, 
                        "admin_secret_key": master_key,
                        "challenge_duration_weeks": new_dur, 
                        "global_start_date": str(new_start),
                        "workout_name": new_wkout, 
                        "workout_notes": new_notes
                    }).execute()
                    st.success("Global overrides applied! Refreshing pipeline.")
                    st.rerun()
                except Exception as db_err:
                    st.error(f"Database error: {db_err}")
