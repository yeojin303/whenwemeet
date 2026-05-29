import streamlit as st
import calendar
import random
import string
import hashlib
import threading
from datetime import datetime, date as date_type, timedelta, timezone

# 대한민국 표준시 (UTC+9) 설정
KST = timezone(timedelta(hours=9))

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

@st.cache_resource
def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = get_supabase()

st.set_page_config(page_title="When We Meet", page_icon="📅", layout="wide")

_LOCK = threading.Lock()
calendar.setfirstweekday(6)

COLOR_PALETTE = [\
    "#FF6B6B", "#FF8E53", "#FFC300", "#6BCB77", "#4D96FF",\
    "#C77DFF", "#FF6FD8", "#00C9A7", "#F4845F", "#56CFE1",\
    "#72EFDD", "#F77F00", "#9B5DE5", "#F15BB5", "#00BBF9",\
]

DAY_ORDER = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}

# ════════════════════════════════════════════════
# 세션 상태 초기화
# ════════════════════════════════════════════════
if "app_page" not in st.session_state:
    st.session_state.app_page = "LOGIN"
if "user" not in st.session_state:
    st.session_state.user = None
if "groups" not in st.session_state:
    st.session_state.groups = []
if "current_group_id" not in st.session_state:
    st.session_state.current_group_id = None
if "group_members" not in st.session_state:
    st.session_state.group_members = {}

# 나의 일정 관련 세션
if "my_cal_year" not in st.session_state:
    st.session_state.my_cal_year = datetime.now(KST).year
if "my_cal_month" not in st.session_state:
    st.session_state.my_cal_month = datetime.now(KST).month
if "my_cal_selected_date" not in st.session_state:
    st.session_state.my_cal_selected_date = None
if "my_cal_edit_schedule" not in st.session_state:
    st.session_state.my_cal_edit_schedule = None

# 모임 일정 관련 세션
if "group_cal_year" not in st.session_state:
    st.session_state.group_cal_year = datetime.now(KST).year
if "group_cal_month" not in st.session_state:
    st.session_state.group_cal_month = datetime.now(KST).month
if "group_cal_selected_date" not in st.session_state:
    st.session_state.group_cal_selected_date = None

# ════════════════════════════════════════════════
# 헬퍼 함수
# ════════════════════════════════════════════════
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def generate_group_code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

def require_login():
    if not st.session_state.user:
        st.session_state.app_page = "LOGIN"
        st.rerun()

def load_user_data():
    if not st.session_state.user:
        return
    u_id = st.session_state.user["id"]
    try:
        res = supabase.table("users").select("*").eq("id", u_id).single().execute()
        if res.data:
            st.session_state.user = res.data
        g_res = supabase.table("group_members").select("group_id, groups(id, name, code, created_at)").eq("user_id", u_id).execute()
        gps = []
        for row in g_res.data:
            if row.get("groups"):
                gps.append(row["groups"])
        st.session_state.groups = gps
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")

def load_group_members(g_id: str):
    try:
        res = supabase.table("group_members").select("user_id, users(id, name, timetable, calendar_schedules)").eq("group_id", g_id).execute()
        m_dict = {}
        for row in res.data:
            u = row.get("users")
            if u:
                m_dict[u["id"]] = {
                    "name": u["name"],
                    "timetable": u.get("timetable") or [],
                    "calendar_schedules": u.get("calendar_schedules") or []
                }
        st.session_state.group_members = m_dict
    except Exception as e:
        st.error(f"그룹 멤버 로드 실패: {e}")

def save_user_field(field_name: str, value):
    if not st.session_state.user:
        return
    u_id = st.session_state.user["id"]
    try:
        supabase.table("users").update({field_name: value}).eq("id", u_id).execute()
        st.session_state.user[field_name] = value
    except Exception as e:
        st.error(f"저장 실패: {e}")

# ════════════════════════════════════════════════
# CSS 스타일
# ════════════════════════════════════════════════
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap');
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Noto Sans KR', sans-serif;
        background-color: #F8F9FA;
    }
    .main-header {
        font-size: 2rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 1.5rem;
        text-align: center;
    }
    .card {
        background: #FFFFFF;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -1px rgba(0,0,0,0.03);
        margin-bottom: 1.5rem;
    }
    .stButton>button {
        border-radius: 8px;
        font-weight: 500;
    }
    div[data-testid="stSidebarUserContent"] {
        padding-top: 2rem;
    }
    .sidebar-title {
        font-size: 1.25rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════
# 사이드바 내비게이션
# ════════════════════════════════════════════════
if st.session_state.user:
    with st.sidebar:
        st.markdown(f"<div class='sidebar-title'>📅 When We Meet</div>", unsafe_allow_html=True)
        st.markdown(f"**{st.session_state.user['name']}**님 환영합니다!")
        st.write("---")
        
        if st.button("🏠 홈 (그룹 관리)", use_container_width=True):
            st.session_state.app_page = "HOME"
            st.session_state.current_group_id = None
            st.rerun()
            
        if st.button("👤 내 계정 설정", use_container_width=True):
            st.session_state.app_page = "ACCOUNT"
            st.rerun()
            
        if st.button("🗓️ 나의 일정 관리", use_container_width=True):
            st.session_state.app_page = "MY_CALENDAR"
            st.session_state.my_cal_selected_date = None
            st.session_state.my_cal_edit_schedule = None
            st.rerun()
            
        st.write("---")
        st.markdown("**참여 중인 그룹**")
        
        load_user_data()
        if st.session_state.groups:
            for g in st.session_state.groups:
                if st.button(f"👥 {g['name']}", key=f"side_g_{g['id']}", use_container_width=True):
                    st.session_state.current_group_id = g["id"]
                    st.session_state.app_page = "GROUP_DETAIL"
                    st.session_state.group_cal_selected_date = None
                    st.rerun()
        else:
            st.caption("참여 중인 그룹이 없습니다.")
            
        st.write("---")
        if st.button("로그아웃", color="secondary", use_container_width=True):
            st.session_state.user = None
            st.session_state.groups = []
            st.session_state.current_group_id = None
            st.session_state.app_page = "LOGIN"
            st.rerun()

# ════════════════════════════════════════════════
# 1. 로그인 / 회원가입 페이지
# ════════════════════════════════════════════════
def page_login():
    st.markdown("<div class='main-header'>📅 When We Meet</div>", unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["로그인", "회원가입"])
    
    with tab1:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        login_email = st.text_input("이메일", key="login_email_input")
        login_pw = st.text_input("비밀번호", type="password", key="login_pw_input")
        
        if st.button("로그인", type="primary", use_container_width=True):
            if not login_email or not login_pw:
                st.error("이메일과 비밀번호를 입력해주세요.")
            else:
                try:
                    res = supabase.table("users").select("*").eq("email", login_email).execute()
                    if res.data:
                        user = res.data[0]
                        if user["password_hash"] == hash_password(login_pw):
                            st.session_state.user = user
                            st.session_state.app_page = "HOME"
                            st.success("로그인 성공!")
                            st.rerun()
                        else:
                            st.error("비밀번호가 일치하지 않습니다.")
                    else:
                        st.error("존재하지 않는 이메일입니다.")
                except Exception as e:
                    st.error(f"오류 발생: {e}")
        st.markdown("</div>", unsafe_allow_html=True)
        
    with tab2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        reg_email = st.text_input("이메일", key="reg_email_input")
        reg_name = st.text_input("이름", key="reg_name_input")
        reg_pw = st.text_input("비밀번호", type="password", key="reg_pw_input")
        reg_pw_confirm = st.text_input("비밀번호 확인", type="password", key="reg_pw_confirm_input")
        
        if st.button("회원가입", type="primary", use_container_width=True):
            if not reg_email or not reg_name or not reg_pw:
                st.error("모든 필드를 입력해주세요.")
            elif reg_pw != reg_pw_confirm:
                st.error("비밀번호가 일치하지 않습니다.")
            else:
                try:
                    chk = supabase.table("users").select("id").eq("email", reg_email).execute()
                    if chk.data:
                        st.error("이미 사용 중인 이메일입니다.")
                    else:
                        new_user = {
                            "email": reg_email,
                            "name": reg_name,
                            "password_hash": hash_password(reg_pw),
                            "timetable": [],
                            "calendar_schedules": []
                        }
                        supabase.table("users").insert(new_user).execute()
                        st.success("회원가입이 완료되었습니다! 로그인 탭에서 로그인해주세요.")
                except Exception as e:
                    st.error(f"오류 발생: {e}")
        st.markdown("</div>", unsafe_allow_html=True)

# ════════════════════════════════════════════════
# 2. 홈 페이지 (그룹 생성 및 참여)
# ════════════════════════════════════════════════
def page_home():
    st.markdown("<div class='main-header'>🏠 나의 모임 관리</div>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("<div class='card'><h3>👥 새 모임 만들기</h3>", unsafe_allow_html=True)
        new_g_name = st.text_input("모임 이름", key="new_g_name_input")
        if st.button("모임 생성", type="primary"):
            if not new_g_name.strip():
                st.error("모임 이름을 입력해주세요.")
            else:
                try:
                    code = generate_group_code()
                    g_res = supabase.table("groups").insert({"name": new_g_name.strip(), "code": code}).execute()
                    if g_res.data:
                        new_group = g_res.data[0]
                        supabase.table("group_members").insert({
                            "group_id": new_group["id"],
                            "user_id": st.session_state.user["id"]
                        }).execute()
                        st.success(f"'{new_g_name}' 모임이 생성되었습니다! (코드는 사이드바 등에서 확인 가능)")
                        load_user_data()
                        st.rerun()
                except Exception as e:
                    st.error(f"모임 생성 실패: {e}")
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col2:
        st.markdown("<div class='card'><h3>🔑 코드로 모임 참여하기</h3>", unsafe_allow_html=True)
        join_code = st.text_input("참여 코드 (6자리)", key="join_code_input").strip().upper()
        if st.button("모임 참여", type="primary"):
            if not join_code:
                st.error("코드를 입력해주세요.")
            else:
                try:
                    res = supabase.table("groups").select("*").eq("code", join_code).execute()
                    if res.data:
                        target_g = res.data[0]
                        chk = supabase.table("group_members").select("*").eq("group_id", target_g["id"]).eq("user_id", st.session_state.user["id"]).execute()
                        if chk.data:
                            st.warning("이미 참여 중인 모임입니다.")
                        else:
                            supabase.table("group_members").insert({
                                "group_id": target_g["id"],
                                "user_id": st.session_state.user["id"]
                            }).execute()
                            st.success(f"'{target_g['name']}' 모임에 성공적으로 참여했습니다!")
                            load_user_data()
                            st.rerun()
                    else:
                        st.error("해당 코드를 가진 모임을 찾을 수 없습니다.")
                except Exception as e:
                    st.error(f"모임 참여 실패: {e}")
        st.markdown("</div>", unsafe_allow_html=True)
        
    st.markdown("<div class='card'><h3>📋 내 모임 목록</h3>", unsafe_allow_html=True)
    if st.session_state.groups:
        for g in st.session_state.groups:
            g_col1, g_col2 = st.columns([3, 1])
            with g_col1:
                st.markdown(f"**{g['name']}** (코드: `{g['code']}`)")
            with g_col2:
                if st.button("입장", key=f"home_g_{g['id']}", use_container_width=True):
                    st.session_state.current_group_id = g["id"]
                    st.session_state.app_page = "GROUP_DETAIL"
                    st.session_state.group_cal_selected_date = None
                    st.rerun()
            st.write("---")
    else:
        st.info("아직 참여 중인 모임이 없습니다. 위에서 새로 만들거나 코드로 참여해보세요!")
    st.markdown("</div>", unsafe_allow_html=True)

# ════════════════════════════════════════════════
# 3. 내 계정 설정 페이지 (고정 시간표 관리)
# ════════════════════════════════════════════════
def page_account():
    st.markdown("<div class='main-header'>👤 내 계정 및 고정 시간표 설정</div>", unsafe_allow_html=True)
    
    st.markdown("<div class='card'><h3>🔒 비밀번호 변경</h3>", unsafe_allow_html=True)
    new_pw = st.text_input("새 비밀번호", type="password")
    if st.button("비밀번호 변경"):
        if not new_pw:
            st.error("새 비밀번호를 입력해주세요.")
        else:
            save_user_field("password_hash", hash_password(new_pw))
            st.success("비밀번호가 변경되었습니다.")
    st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown("<div class='card'><h3>🚫 주간 고정 불가 시간대 설정</h3>", unsafe_allow_html=True)
    st.write("매주 정기적으로 미팅이 불가능한 요일과 시간대를 등록해두면, 그룹 캘린더 계산 시 자동으로 제외됩니다.")
    
    current_tt = st.session_state.user.get("timetable") or []
    
    with st.form("add_timetable_form", clear_on_submit=True):
        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1:
            day = st.selectbox("요일", ["월", "화", "수", "목", "금", "토", "일"])
        with f_col2:
            start_h = st.selectbox("시작 시간", [f"{h:02d}:00" for h in range(24)])
        with f_col3:
            end_h = st.selectbox("종료 시간", [f"{h:02d}:00" for h in range(24)])
            
        if st.form_submit_button("불가 시간 추가", type="primary"):
            sh = int(start_h.split(":")[0])
            eh = int(end_h.split(":")[0])
            if sh >= eh:
                st.error("종0료 시간은 시작 시간보다 늦어야 합니다.")
            else:
                overlap = False
                for t in current_tt:
                    if t["day"] == day:
                        t_sh = int(t["start"].split(":")[0])
                        t_eh = int(t["end"].split(":")[0])
                        if not (eh <= t_sh or sh >= t_eh):
                            overlap = True
                            break
                if overlap:
                    st.error("이미 등록된 시간대와 겹칩니다.")
                else:
                    current_tt.append({"day": day, "start": start_h, "end": end_h})
                    save_user_field("timetable", current_tt)
                    st.success("고정 불가 시간이 추가되었습니다.")
                    st.rerun()
                    
    if current_tt:
        st.markdown("#### 📋 등록된 고정 불가 시간 목록")
        sorted_tt = sorted(current_tt, key=lambda x: (DAY_ORDER.get(x["day"], 0), int(x["start"].split(":")[0])))
        
        for idx, t in enumerate(sorted_tt):
            t_col1, t_col2 = st.columns([3, 1])
            with t_col1:
                st.write(f"• **{t['day']}요일** {t['start']} ~ {t['end']}")
            with t_col2:
                if st.button("삭제", key=f"del_tt_{idx}"):
                    current_tt.remove(t)
                    save_user_field("timetable", current_tt)
                    st.success("삭제되었습니다.")
                    st.rerun()
    else:
        st.caption("등록된 고정 불가 시간이 없습니다.")
    st.markdown("</div>", unsafe_allow_html=True)

# ════════════════════════════════════════════════
# 4. 나의 일정 관리 페이지 (개인 캘린더)
# ════════════════════════════════════════════════
def page_my_calendar():
    st.markdown("<div class='main-header'>🗓️ 나의 일정 관리</div>", unsafe_allow_html=True)
    
    schedules = st.session_state.user.get("calendar_schedules") or []
    
    c_col1, c_col2 = st.columns([7, 5])
    
    with c_col1:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])
        with nav_col1:
            if st.button("◀ 이전 달", use_container_width=True):
                st.session_state.my_cal_month -= 1
                if st.session_state.my_cal_month == 0:
                    st.session_state.my_cal_month = 12
                    st.session_state.my_cal_year -= 1
                st.session_state.my_cal_selected_date = None
                st.session_state.my_cal_edit_schedule = None
                st.rerun()
        with nav_col2:
            st.markdown(f"<h3 style='text-align:center;'>{st.session_state.my_cal_year}년 {st.session_state.my_cal_month}월</h3>", unsafe_allow_html=True)
        with nav_col3:
            if st.button("다음 달 ▶", use_container_width=True):
                st.session_state.my_cal_month += 1
                if st.session_state.my_cal_month == 13:
                    st.session_state.my_cal_month = 1
                    st.session_state.my_cal_year += 1
                st.session_state.my_cal_selected_date = None
                st.session_state.my_cal_edit_schedule = None
                st.rerun()
                
        cal = calendar.Calendar(firstweekday=6)
        month_days = cal.monthdayscalendar(st.session_state.my_cal_year, st.session_state.my_cal_month)
        
        days_header = ["일", "월", "화", "수", "목", "금", "토"]
        cols = st.columns(7)
        for idx, d_name in enumerate(days_header):
            color = "#EF4444" if idx == 0 else ("#3B82F6" if idx == 6 else "#1E293B")
            cols[idx].markdown(f"<p style='text-align:center; font-weight:bold; color:{color}; margin-bottom:5px;'>{d_name}</p>", unsafe_allow_html=True)
            
        for week in month_days:
            cols = st.columns(7)
            for idx, day in enumerate(week):
                if day == 0:
                    cols[idx].write("")
                else:
                    d_str = f"{st.session_state.my_cal_year}-{st.session_state.my_cal_month:02d}-{day:02d}"
                    day_schedules = [s for s in schedules if s["date"] == d_str]
                    
                    bg_color = "#FFFFFF"
                    border_color = "#E2E8F0"
                    
                    if st.session_state.my_cal_selected_date == d_str:
                        border_color = "#4D96FF"
                        bg_color = "#EDF5FF"
                    elif day_schedules:
                        bg_color = "#FFF9E6"
                        
                    btn_label = f"{day}"
                    if day_schedules:
                        btn_label += f"\n({len(day_schedules)})"
                        
                    if cols[idx].button(btn_label, key=f"my_day_{day}", use_container_width=True):
                        st.session_state.my_cal_selected_date = d_str
                        st.session_state.my_cal_edit_schedule = None
                        st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        
    with c_col2:
        if st.session_state.my_cal_selected_date:
            sel_date = st.session_state.my_cal_selected_date
            st.markdown(f"<div class='card'><h3>📅 {sel_date} 일정 목록</h3>", unsafe_allow_html=True)
            
            day_schedules = [s for s in schedules if s["date"] == sel_date]
            day_schedules = sorted(day_schedules, key=lambda x: x["start_time"])
            
            if day_schedules:
                for s in day_schedules:
                    s_col1, s_col2 = st.columns([3, 1])
                    with s_col1:
                        st.markdown(f"**[{s['start_time']} ~ {s['end_time']}]** \n{s['title']}")
                    with s_col2:
                        if st.button("수정", key=f"edit_s_{s['id']}"):
                            st.session_state.my_cal_edit_schedule = s
                            st.rerun()
                    st.write("---")
            else:
                st.caption("이 날짜에 등록된 일정이 없습니다.")
                
            if st.session_state.my_cal_edit_schedule:
                curr_edit = st.session_state.my_cal_edit_schedule
                st.markdown("#### ✏️ 일정 수정 / 삭제")
                edit_title = st.text_input("일정 제목", value=curr_edit["title"], key="edit_title")
                edit_start = st.selectbox("시작 시간", [f"{h:02d}:00" for h in range(24)], index=int(curr_edit["start_time"].split(":")[0]), key="edit_start")
                edit_end = st.selectbox("종료 시간", [f"{h:02d}:00" for h in range(24)], index=int(curr_edit["end_time"].split(":")[0]), key="edit_end")
                
                ec1, ec2 = st.columns(2)
                with ec1:
                    if st.button("저장", type="primary", use_container_width=True):
                        if int(edit_start.split(":")[0]) >= int(edit_end.split(":")[0]):
                            st.error("종료 시간은 시작 시간보다 늦어야 합니다.")
                        else:
                            for s in schedules:
                                if s["id"] == curr_edit["id"]:
                                    s["title"] = edit_title
                                    s["start_time"] = edit_start
                                    s["end_time"] = edit_end
                                    break
                            save_user_field("calendar_schedules", schedules)
                            st.success("일정이 수정되었습니다.")
                            st.session_state.my_cal_edit_schedule = None
                            st.rerun()
                with ec2:
                    if st.button("삭제", color="danger", use_container_width=True):
                        schedules = [s for s in schedules if s["id"] != curr_edit["id"]]
                        save_user_field("calendar_schedules", schedules)
                        st.success("일정이 삭제되었습니다.")
                        st.session_state.my_cal_edit_schedule = None
                        st.rerun()
            else:
                st.markdown("#### ➕ 새 일정 추가")
                with st.form("add_calendar_schedule_form", clear_on_submit=True):
                    new_title = st.text_input("일정 제목")
                    ns_col1, ns_col2 = st.columns(2)
                    with ns_col1:
                        new_start = st.selectbox("시작 시간", [f"{h:02d}:00" for h in range(24)])
                    with ns_col2:
                        new_end = st.selectbox("종료 시간", [f"{h:02d}:00" for h in range(24)], index=1)
                        
                    if st.form_submit_button("추가", type="primary"):
                        if not new_title.strip():
                            st.error("일정 제목을 입력해주세요.")
                        elif int(new_start.split(":")[0]) >= int(new_end.split(":")[0]):
                            st.error("종료 시간은 시작 시간보다 늦어야 합니다.")
                        else:
                            new_id = "".join(random.choices(string.ascii_letters + string.digits, k=10))
                            schedules.append({
                                "id": new_id,
                                "date": sel_date,
                                "title": new_title.strip(),
                                "start_time": new_start,
                                "end_time": new_end
                            })
                            save_user_field("calendar_schedules", schedules)
                            st.success("새 일정이 추가되었습니다.")
                            st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("왼쪽 달력에서 날짜를 클릭하면 해당 날짜의 일정을 관리할 수 있습니다.")

# ════════════════════════════════════════════════
# 5. 그룹 상세 페이지 (대망의 핵심 기능)
# ════════════════════════════════════════════════
def page_group_detail():
    g_id = st.session_state.current_group_id
    if not g_id:
        st.session_state.app_page = "HOME"
        st.rerun()
        
    try:
        g_res = supabase.table("groups").select("*").eq("id", g_id).single().execute()
        group = g_res.data
    except Exception as e:
        st.error(f"그룹 정보 로드 실패: {e}")
        return
        
    st.markdown(f"<div class='main-header'>👥 {group['name']}</div>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align:center;'>모임 참여 코드: <code>{group['code']}</code></p>", unsafe_allow_html=True)
    
    load_group_members(g_id)
    g_members = st.session_state.group_members
    
    st.markdown("<div class='card'><h3>👥 참여 멤버</h3>", unsafe_allow_html=True)
    m_names = [m["name"] for m in g_members.values()]
    st.write(", ".join(m_names))
    st.markdown("</div>", unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["📊 이번 달 모임 날짜 찾기", "⏳ 주간 고정 시간표 비교"])
    
    with tab1:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.write("모두가 고정 불가 시간 및 개인 일정이 없는 **가장 최적의 미팅 날짜**를 계산하여 대시보드로 보여줍니다.")
        
        gnav_col1, gnav_col2, gnav_col3 = st.columns([1, 2, 1])
        with gnav_col1:
            if st.button("◀ 이전 달 ", key="g_prev_m", use_container_width=True):
                st.session_state.group_cal_month -= 1
                if st.session_state.group_cal_month == 0:
                    st.session_state.group_cal_month = 12
                    st.session_state.group_cal_year -= 1
                st.session_state.group_cal_selected_date = None
                st.rerun()
        with gnav_col2:
            st.markdown(f"<h3 style='text-align:center;'>{st.session_state.group_cal_year}년 {st.session_state.group_cal_month}월</h3>", unsafe_allow_html=True)
        with gnav_col3:
            if st.button("다음 달 ▶ ", key="g_next_m", use_container_width=True):
                st.session_state.group_cal_month += 1
                if st.session_state.group_cal_month == 13:
                    st.session_state.group_cal_month = 1
                    st.session_state.group_cal_year += 1
                st.session_state.group_cal_selected_date = None
                st.rerun()
                
        cal = calendar.Calendar(firstweekday=6)
        month_days = cal.monthdayscalendar(st.session_state.group_cal_year, st.session_state.group_cal_month)
        
        hours_range = range(9, 22)
        total_slots_per_day = len(hours_range)
        
        day_scores = {}
        day_busy_details = {}
        
        for week in month_days:
            for day in week:
                if day == 0:
                    continue
                try:
                    d_obj = date_type(st.session_state.group_cal_year, st.session_state.group_cal_month, day)
                    w_day_idx = d_obj.weekday()
                    w_day_str = ["월", "화", "수", "목", "금", "토", "일"][w_day_idx]
                except ValueError:
                    continue
                    
                d_str = f"{st.session_state.group_cal_year}-{st.session_state.group_cal_month:02d}-{day:02d}"
                
                free_slots_count = 0
                busy_infos = []
                
                for h in hours_range:
                    slot_busy_users = []
                    
                    for m_id, m_data in g_members.items():
                        is_busy = False
                        
                        for t in m_data["timetable"]:
                            if t["day"] == w_day_str:
                                try:
                                    sh = int(t["start"].split(":")[0])
                                    eh = int(t["end"].split(":")[0])
                                    if sh <= h < eh:
                                        is_busy = True
                                        break
                                except Exception:
                                    pass
                                    
                        if not is_busy:
                            for s in m_data["calendar_schedules"]:
                                if s["date"] == d_str:
                                    try:
                                        sh = int(s["start_time"].split(":")[0])
                                        eh = int(s["end_time"].split(":")[0])
                                        if sh <= h < eh:
                                            is_busy = True
                                            break
                                    except Exception:
                                        pass
                                        
                        if is_busy:
                            slot_busy_users.append(m_data["name"])
                            
                    if len(slot_busy_users) == 0:
                        free_slots_count += 1
                    else:
                        busy_infos.append({"hour": h, "users": list(set(slot_busy_users))})
                        
                day_scores[day] = free_slots_count / total_slots_per_day if total_slots_per_day > 0 else 0
                day_busy_details[day] = busy_infos
                
        days_header = ["일", "월", "화", "수", "목", "금", "토"]
        cols = st.columns(7)
        for idx, d_name in enumerate(days_header):
            color = "#EF4444" if idx == 0 else ("#3B82F6" if idx == 6 else "#1E293B")
            cols[idx].markdown(f"<p style='text-align:center; font-weight:bold; color:{color}; margin-bottom:5px;'>{d_name}</p>", unsafe_allow_html=True)
            
        for week in month_days:
            cols = st.columns(7)
            for idx, day in enumerate(week):
                if day == 0:
                    cols[idx].write("")
                else:
                    score = day_scores.get(day, 0)
                    
                    if score == 1.0:
                        bg_color = "#D1FAE5"
                        text_color = "#065F46"
                    elif score >= 0.5:
                        bg_color = "#FEF3C7"
                        text_color = "#92400E"
                    elif score > 0:
                        bg_color = "#FFEDD5"
                        text_color = "#9A3412"
                    else:
                        bg_color = "#FEE2E2"
                        text_color = "#991B1B"
                        
                    d_str = f"{st.session_state.group_cal_year}-{st.session_state.group_cal_month:02d}-{day:02d}"
                    if st.session_state.group_cal_selected_date == d_str:
                        bg_color = "#3B82F6"
                        text_color = "#FFFFFF"
                        
                    btn_html = f"""
                    <div style="background-color:{bg_color}; color:{text_color}; border-radius:8px; padding:4px; text-align:center; font-size:0.85rem; font-weight:500;">
                        {day}<br><span style="font-size:0.7rem;">가능:{int(score*100)}%</span>
                    </div>
                    """
                    cols[idx].markdown(btn_html, unsafe_allow_html=True)
                    if cols[idx].button("보기", key=f"g_day_btn_{day}", use_container_width=True):
                        st.session_state.group_cal_selected_date = d_str
                        st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        
        if st.session_state.group_cal_selected_date:
            sel_date_str = st.session_state.group_cal_selected_date
            sel_day = int(sel_date_str.split("-")[2])
            
            st.markdown(f"<div class='card'><h3>📅 {sel_date_str} 상세 시간대별 현황 (09시 ~ 22시)</h3>", unsafe_allow_html=True)
            
            busy_list = day_busy_details.get(sel_day, [])
            
            table_html = "<table style='width:100%; border-collapse: collapse; text-align:center;'>"
            table_html += "<tr style='background-color:#F1F5F9;'><th>시간</th><th>상태</th><th>불가능한 사람</th></tr>"
            
            for h in hours_range:
                b_info = next((b for b in busy_list if b["hour"] == h), None)
                if b_info:
                    status = "<span style='color:#EF4444; font-weight:bold;'>❌ 불가능</span>"
                    users_str = ", ".join(b_info["users"])
                    bg = "#FFF5F5"
                else:
                    status = "<span style='color:#10B981; font-weight:bold;'>🟢 모두 가능</span>"
                    users_str = "-"
                    bg = "#F0FDF4"
                    
                table_html += f"<tr style='background-color:{bg}; border-bottom:1px solid #E2E8F0;'>"
                table_html += f"<td style='padding:8px;'>{h:02d}:00 ~ {h+1:02d}:00</td>"
                table_html += f"<td>{status}</td>"
                table_html += f"<td>{users_str}</td>"
                table_html += "</tr>"
            table_html += "</table>"
            
            st.markdown(table_html, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            
    with tab2:
        st.markdown("<div class='card'><h3>⏳ 주간 고정 시간표 매트릭스</h3>", unsafe_allow_html=True)
        st.write("멤버들이 설정한 '주간 고정 불가 시간대'만 겹쳐서 보여주는 표입니다. (초록색: 모두 가능, 빨간색: 한 명이라도 불가)")
        
        hours_range = range(9, 22)
        w_days = ["월", "화", "수", "목", "금", "토", "일"]
        
        w_table = "<div style='overflow-x:auto;'><table style='width:100%; border-collapse:collapse; text-align:center; font-size:0.9rem;'>"
        w_table += "<tr style='background-color:#F1F5F9;'><th>요일 / 시간</th>"
        for h in hours_range:
            w_table += f"<th style='padding:6px; min-width:45px;'>{h:02d}시</th>"
        w_table += "</tr>"
        
        for w_day in w_days:
            w_table += f"<tr><td style='background-color:#F8F9FA; font-weight:bold; border:1px solid #ddd; padding:6px;'>{w_day}</td>"
            for h in hours_range:
                is_free = True
                for name, m_data in g_members.items():
                    for t in m_data.get("timetable", []):
                        if t["day"] == w_day:
                            try:
                                sh = int(t["start"].split(":")[0])
                                eh = int(t["end"].split(":")[0])
                                if sh <= h < eh:
                                    is_free = False
                            except Exception:
                                pass
                bg = "#4CAF50" if is_free else "#F44336"
                w_table += f"<td style='background-color:{bg};border:1px solid #ddd;height:22px;'></td>"
            w_table += "</tr>"
        w_table += "</table></div>"
        st.markdown(w_table, unsafe_allow_html=True)

# ════════════════════════════════════════════════
# 라우터
# ════════════════════════════════════════════════
page = st.session_state.app_page

if page == "LOGIN":
    page_login()
elif page == "HOME":
    require_login(); load_user_data(); page_home()
elif page == "ACCOUNT":
    require_login(); page_account()
elif page == "MY_CALENDAR":
    require_login(); load_user_data(); page_my_calendar()
elif page == "GROUP_DETAIL":
    require_login(); page_group_detail()
