import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from supabase import create_client, Client
from PIL import Image
import io
import base64

# --- SECURE DATABASE CONNECTION ---
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = init_supabase()
except Exception as e:
    st.error("🔒 Cloud Vault Connection Pending. Please configure your Streamlit Secrets.")
    st.stop()

st.set_page_config(page_title="Driven Gym Portal", page_icon="💪", layout="wide")

# --- CONVERSION HELPERS ---
FRACTIONS = ["0", "1/16", "1/8", "3/16", "1/4", "5/16", "3/8", "7/16", "1/2", "9/16", "5/8", "11/16", "3/4", "13/16", "7/8", "15/16"]
FRACTION_VALUES = {f: i/16 for i, f in enumerate(FRACTIONS)}

def float_to_fraction(val):
    if not val or val == 0: return "0"
    whole = int(val)
    frac = val - whole
    closest_frac = min(FRACTIONS, key=lambda x: abs(FRACTION_VALUES[x] - frac))
    return f"{whole}\"" if closest_frac == "0" else f"{whole} {closest_frac}\""

# --- DYNAMIC SUCCESS GRADING SCALE ---
def get_success_badge(rate):
    if rate >= 90: return f"{rate:.1f}% — On Fire 🔥"
    if rate >= 75: return f"{rate:.1f}% — On Track 🏃‍♂️"
    if rate >= 60: return f"{rate:.1f}% — Needs Focus ⚠️"
    return f"{rate:.1f}% — Danger Zone 🛑"

# --- SYSTEM SETTINGS LOAD ---
settings_query = supabase.table("challenge_settings").select("*").eq("id", 1).execute()
settings = settings_query.data if settings_query.data else {"admin_secret_key": "driven2026", "challenge_duration_weeks": 6, "global_start_date": "2026-06-22", "workout_name": "TBD", "workout_notes": ""}

# --- USER STATE APP FLOW ---
if "user" not in st.session_state:
    st.session_state.user = None

# --- SIDEBAR NAVIGATION & AUTH LINK ---
st.sidebar.title("🏁 Navigation")
if st.session_state.user:
    st.sidebar.write(f"Logged in as: **{st.session_state.user['email']}**")
    if st.sidebar.button("Log Out"):
        st.session_state.user = None
        st.rerun()

page = st.sidebar.radio("Go To", ["Dashboard", "Daily Logger", "Initial Setup & Baselines", "Leaderboard", "Hidden Admin Panel"])

# --- SIGN UP & LOGIN INTERFACE ---
if not st.session_state.user and page != "Hidden Admin Panel":
    st.header("💪 Driven Community Fitness Challenge")
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
                    # Save profile details including the new gender selection
                    supabase.table("user_profiles").insert({
                        "user_id": res.user.id, 
                        "full_name": fullname, 
                        "email": email, 
                        "age": age,
                        "gender": gender
                    }).execute()
                    
                    # AUTO-LOGIN ARCHITECTURE: Instantly log them in 
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

# --- CUSTOM TWO-PART FRACTION INPUT COMPONENT ---
def fraction_selector(label):
    st.markdown(f"**{label}**")
    c1, c2 = st.columns(2)
    whole = c1.selectbox("Inches", list(range(0, 80)), index=0, key=f"{label}_w")
    frac = c2.selectbox("Fraction", FRACTIONS, index=0, key=f"{label}_f")
    return whole + FRACTION_VALUES[frac]

# --- PAGES CONTENT IMPLEMENTATION ---
if page == "Initial Setup & Baselines":
    st.header("🏁 Lock In Your Baselines")
    start_dt = datetime.strptime(settings["global_start_date"], "%Y-%m-%d").date()
    days_since_start = (date.today() - start_dt).days
    
    if days_since_start > 7:
        st.error(f"🛑 Entry Window Closed. Baselines had to be locked in within the first week of the start date ({start_dt}). Please contact Coach Bret.")
    else:
        st.info(f"🏋️‍♂️ **Official Benchmark Workout:** {settings['workout_name']}\n\n*Instructions:* {settings['workout_notes']}")
        
        with st.form("baseline_form"):
            score = st.text_input("Enter Your Benchmark Workout Score")
            
            st.subheader("Tape Measurements")
            w = st.number_input("Weight (lbs)", min_value=0.0, step=0.1)
            ch = fraction_selector("Chest")
            wa = fraction_selector("Waist")
            hi = fraction_selector("Hips")
            la = fraction_selector("Left Arm")
            ra = fraction_selector("Right Arm")
            lt = fraction_selector("Left Thigh")
            rt = fraction_selector("Right Thigh")
            
            st.subheader("Private Before Photo (Optional)")
            cam_photo = st.camera_input("Snap Baseline Selfie")
            
            if st.form_submit_button("Securely Save My Starting Numbers"):
                img_str = ""
                if cam_photo:
                    img = Image.open(cam_photo)
                    img.thumbnail((400, 400))
                    buffered = io.BytesIO()
                    img.save(buffered, format="JPEG", quality=75)
                    img_str = base64.b64encode(buffered.getvalue()).decode()
                
                supabase.table("user_baselines").upsert({
                    "user_id": st.session_state.user["id"],
                    "start_weight": w, "start_chest": ch, "start_waist": wa, "start_hips": hi,
                    "start_left_arm": la, "start_right_arm": ra, "start_left_thigh": lt, "start_right_thigh": rt,
                    "benchmark_score": score, "before_photo": img_str
                }).execute()
                st.success("Baselines successfully encrypted and saved to your private profile vault!")

elif page == "Daily Logger":
    st.header("📝 Daily Performance Log")
    log_date = st.date_input("Date", date.today())
    
    existing = supabase.table("daily_logs").select("*").eq("user_id", st.session_state.user["id"]).eq("log_date", str(log_date)).execute()
    log_data = existing.data if existing.data else {"diet": False, "water": False, "sleep": False, "exercise": False}
    
    diet = st.checkbox("Strict Paleo Menu Adherence — **5 pts**", value=log_data["diet"])
    water = st.checkbox("Water Tracker Placeholder (Awaiting target confirmation from Coach Bret) — **1 pt**", value=log_data["water"])
    sleep = st.checkbox("Sleep Metrics (7-8+ Rest Hours) — **1 pt**", value=log_data["sleep"])
    exercise = st.checkbox("Daily Activity or Designated Mobility Session — **1 pt**", value=log_data["exercise"])
    
    score = (5 if diet else 0) + (1 if water else 0) + (1 if sleep else 0) + (1 if exercise else 0)
    st.metric("Points Scored", f"{score} / 8")
    
    if st.button("Submit Daily Points"):
        supabase.table("daily_logs").upsert({
            "user_id": st.session_state.user["id"], "log_date": str(log_date),
            "diet": diet, "water": water, "sleep": sleep, "exercise": exercise, "daily_score": score
        }).execute()
        st.success("Points posted successfully!")

elif page == "Dashboard":
    st.header("📊 Athlete Recovery & Score Command")
    
    profile = supabase.table("user_profiles").select("*").eq("user_id", st.session_state.user["id"]).execute()
    baselines = supabase.table("user_baselines").select("*").eq("user_id", st.session_state.user["id"]).execute()
    logs = supabase.table("daily_logs").select("*").eq("user_id", st.session_state.user["id"]).execute()
    
    if not baselines.data:
        st.warning("👋 Set up your profile metrics inside 'Initial Setup & Baselines' to initialize your pipeline.")
    else:
        b = baselines.data
        start_dt = datetime.strptime(settings["global_start_date"], "%Y-%m-%d").date()
        total_days = settings["challenge_duration_weeks"] * 7
        days_in = max((date.today() - start_dt).days + 1, 1)
        
        total_earned = sum([day["daily_score"] for day in logs.data])
        possible_so_far = min(days_in, total_days) * 8
        success_rate = (total_earned / possible_so_far * 100) if possible_so_far > 0 else 100.0
        
        # --- 21st CENTURY METRIC CARDS OVERHAUL ---
        st.markdown("### ⚡ Current Momentum")
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.markdown(f"""
            <div style="background-color: #1E222B; padding: 20px; border-radius: 12px; border-left: 5px solid #FF4B4B; box-shadow: 2px 2px 10px rgba(0,0,0,0.3);">
                <span style="color: #8A9AAB; font-size: 12px; font-weight: bold; text-transform: uppercase;">Timeline Milestone</span>
                <h2 style="margin: 5px 0 0 0; color: #FAFAFA; font-size: 28px;">Day {min(days_in, total_days)} <span style="font-size: 16px; color: #8A9AAB;">/ {total_days}</span></h2>
            </div>
            """, unsafe_allow_html=True)
            
        with c2:
            st.markdown(f"""
            <div style="background-color: #1E222B; padding: 20px; border-radius: 12px; border-left: 5px solid #00E676; box-shadow: 2px 2px 10px rgba(0,0,0,0.3);">
                <span style="color: #8A9AAB; font-size: 12px; font-weight: bold; text-transform: uppercase;">Accumulated Points</span>
                <h2 style="margin: 5px 0 0 0; color: #00E676; font-size: 28px;">{total_earned} <span style="font-size: 16px; color: #8A9AAB;">Pts</span></h2>
            </div>
            """, unsafe_allow_html=True)
            
        with c3:
            badge_color = "#FF4B4B" if success_rate < 60 else ("#FFD600" if success_rate < 75 else "#00E676")
            st.markdown(f"""
            <div style="background-color: #1E222B; padding: 20px; border-radius: 12px; border-left: 5px solid {badge_color}; box-shadow: 2px 2px 10px rgba(0,0,0,0.3);">
                <span style="color: #8A9AAB; font-size: 12px; font-weight: bold; text-transform: uppercase;">Your Success Rate</span>
                <h4 style="margin: 8px 0 0 0; color: #FAFAFA; font-size: 18px;">{get_success_badge(success_rate)}</h4>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("---")
        
        # --- PRIVATE MEASUREMENTS VAULT CARD ---
        st.markdown(f"""
        <div style="background-color: #151922; padding: 25px; border-radius: 16px; border: 1px solid #2C3545; box-shadow: 2px 4px 15px rgba(0,0,0,0.4); margin-top: 15px;">
            <div style="display: flex; align-items: center; margin-bottom: 15px;">
                <span style="font-size: 22px; margin-right: 10px;">🔒</span>
                <h3 style="margin: 0; color: #FAFAFA; font-size: 20px;">Your Sealed Personal Configuration (Private)</h3>
            </div>
            <p style="color: #8A9AAB; font-size: 13px; margin: -5px 0 20px 0;">These numbers are safely encrypted. No other members or leaderboards can view these raw metrics.</p>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px;">
                <div style="background-color: #1E222B; padding: 15px; border-radius: 8px;">
                    <span style="color: #8A9AAB; font-size: 11px; text-transform: uppercase; font-weight: bold;">Starting Weight</span>
                    <p style="margin: 5px 0 0 0; font-size: 20px; font-weight: bold; color: #FAFAFA;">{b['start_weight']} lbs</p>
                </div>
                <div style="background-color: #1E222B; padding: 15px; border-radius: 8px;">
                    <span style="color: #8A9AAB; font-size: 11px; text-transform: uppercase; font-weight: bold;">Chest / Waist / Hips</span>
                    <p style="margin: 5px 0 0 0; font-size: 18px; font-weight: bold; color: #FAFAFA;">{float_to_fraction(b['start_chest'])} / {float_to_fraction(b['start_waist'])} / {float_to_fraction(b['start_hips'])}</p>
                </div>
                <div style="background-color: #1E222B; padding: 15px; border-radius: 8px;">
                    <span style="color: #8A9AAB; font-size: 11px; text-transform: uppercase; font-weight: bold;">Arms (L / R)</span>
                    <p style="margin: 5px 0 0 0; font-size: 20px; font-weight: bold; color: #FAFAFA;">{float_to_fraction(b['start_left_arm'])} / {float_to_fraction(b['start_right_arm'])}</p>
                </div>
                <div style="background-color: #1E222B; padding: 15px; border-radius: 8px;">
                    <span style="color: #8A9AAB; font-size: 11px; text-transform: uppercase; font-weight: bold;">Thighs (L / R)</span>
                    <p style="margin: 5px 0 0 0; font-size: 20px; font-weight: bold; color: #FAFAFA;">{float_to_fraction(b['start_left_thigh'])} / {float_to_fraction(b['start_right_thigh'])}</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

elif page == "Leaderboard":
    st.header("🏆 The Consolidated Gym Standings")
    
    profiles = supabase.table("user_profiles").select("*").execute()
    all_logs = supabase.table("daily_logs").select("*").execute()
    all_baselines = supabase.table("user_baselines").select("*").execute()
    
    leaderboard_data = []
    
    for p in profiles.data:
        user_points = sum([l["daily_score"] for l in all_logs.data if l["user_id"] == p["user_id"]])
        ub = next((b for b in all_baselines.data if b["user_id"] == p["user_id"]), None)
        
        lbs_lost = 0.0
        if ub and ub["end_weight"] and ub["start_weight"]:
            lbs_lost = float(ub["start_weight"] - ub["end_weight"])
        
        leaderboard_data.append({
            "Athlete Name": p["full_name"],
            "Total Points": user_points,
            "Pounds Dropped": f"{lbs_lost:.1f} lbs" if lbs_lost > 0 else "0.0 lbs",
        })
        
    df = pd.DataFrame(leaderboard_data).sort_values(by="Total Points", ascending=False)
    st.dataframe(df, use_container_width=True)

elif page == "Hidden Admin Panel":
    st.header("⚙️ Shared Executive Administration Panel")
    input_key = st.text_input("Enter Master Secret Admin Key", type="password")
    
    if input_key == settings["admin_secret_key"]:
        st.success("Access Verified.")
with st.form("admin_form"):
            # 1. Define the week options cleanly
            duration_options =
            
            # 2. Find the default choice 
            default_selection_index = duration_options.index(settings["challenge_duration_weeks"])
            
            # 3. Create the dropdown selector with zero nested commas
            new_dur = st.selectbox("Challenge Duration", duration_options, index=default_selection_index)
            
            new_start = st.date_input("Global Challenge Launch Date", datetime.strptime(settings["global_start_date"], "%Y-%m-%d").date())
            new_wkout = st.text_input("Global Benchmark Workout Title", value=settings["workout_name"])
            new_notes = st.text_area("Scoring Rules & Instructions Box", value=settings["workout_notes"])
            
            if st.form_submit_button("Apply Global System Overrides"):
                supabase.table("challenge_settings").upsert({
                    "id": 1, "admin_secret_key": settings["admin_secret_key"],
                    "challenge_duration_weeks": new_dur, "global_start_date": str(new_start),
                    "workout_name": new_wkout, "workout_notes": new_notes
                }).execute()
                st.success("Global overrides applied! Refreshing pipeline.")
