import streamlit as st
import calendar
import random
import string
import hashlib
import threading
from datetime import datetime
from supabase import create_client, Client

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

@st.cache_resource
def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = get_supabase()

# layout="wide"를 유지하되 CSS로 모바일 최대 폭을 강제 제어합니다.
st.set_page_config(page_title="When We Meet", page_icon="📅", layout="wide")

# 🔥 [모바일 화면 가로 스크롤 완전 파괴 및 폭 맞춤 CSS 치트키]
st.markdown("""
<style>
    /* 전체 화면 가로 스크롤 방지 및 패딩 최소화 */
    html, body, [data-testid="stAppViewContainer"] {
        max-width: 100vw !important;
        overflow-x: hidden !important;
    }
    
    .block-container {
        padding-left: 6px !important;
        padding-right: 6px !important;
        padding-top: 1rem !important;
        max-width: 100% !important;
    }

    /* 7열 달력(stHorizontalBlock)이 화면 밖으로 터져나가지 않도록 강제 균등 분할 */
    div[data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        width: 100% !important;
        gap: 2px !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    
    /* 7개 컬럼 각각의 너비를 정확히 1/7(약 14%)로 고정하여 폰 화면에 가둠 */
    div[data-testid="column"] {
        flex: 1 1 0% !important;
        min-width: 0 !important;
        max-width: 14.28% !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    
    /* 버튼 글자가 깨지거나 튀어나오지 않도록 모바일용으로 완전 압축 */
    div.stButton > button {
        font-size: 9px !important;
        padding: 2px 0px !important;
        margin: 0 !important;
        min-height: 20px !important;
        max-height: 24px !important;
        width: 100% !important;
        text-align: center !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        white-space: nowrap !important;
    }
    
    /* 타임라인 및 시간표 테이블이 가로로 터지는 현상 방지 (폰 화면 안에서만 스크롤 되도록 격리) */
    .mobile-table-container {
        width: 100% !important;
        overflow-x: auto !important;
        -webkit-overflow-scrolling: touch !important;
        margin-bottom: 10px;
    }
    
    table {
        width: 100% !important;
        table-layout: fixed !important;
    }
</style>
""", unsafe_allow_html=True)

_LOCK = threading.Lock()
calendar.setfirstweekday(6)

COLOR_PALETTE = [
    "#FF6B6B", "#FF8E53", "#FFC300", "#6BCB77", "#4D96FF",
    "#C77DFF", "#FF6FD8", "#00C9A7", "#F4845F", "#56CFE1",
    "#72EFDD", "#F77F00", "#9B5DE5", "#F15BB5", "#00BBF9",
]

def get_random_color():
    return random.choice(COLOR_PALETTE)

def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


# ════════════════════════════════════════════════
# DB 헬퍼 함수
# ════════════════════════════════════════════════

def db_get_user(username):
    try:
        res = supabase.table("users").select("*").eq("username", username).execute()
        return res.data[0] if res.data else None
    except Exception:
        return None

def db_create_user(username, password):
    try:
        if db_get_user(username):
            return None, "이미 사용 중인 아이디입니다."
        res = supabase.table("users").insert({
            "username": username,
            "password_hash": hash_password(password),
        }).execute()
        return res.data[0], None
    except Exception as e:
        return None, str(e)

def db_login(username, password):
    user = db_get_user(username)
    if not user:
        return None, "존재하지 않는 아이디입니다."
    if user["password_hash"] != hash_password(password):
        return None, "비밀번호가 틀렸습니다."
    return user, None

def db_delete_user(user_id):
    try:
        supabase.table("events").delete().eq("user_id", user_id).execute()
        supabase.table("timetable").delete().eq("user_id", user_id).execute()
        supabase.table("room_members").delete().eq("user_id", user_id).execute()
        supabase.table("users").delete().eq("id", user_id).execute()
        return True
    except Exception as e:
        st.error(f"탈퇴 오류: {e}")
        return False

def db_get_user_events(user_id):
    try:
        res = supabase.table("events").select("*").eq("user_id", user_id).execute()
        return res.data or []
    except Exception:
        return []

def db_save_event(user_id, event):
    try:
        payload = {
            "user_id": user_id,
            "title": event["title"],
            "start_dt": event["start"],
            "end_dt": event["end"],
            "color": event.get("color", get_random_color()),
        }
        if event.get("id"):
            supabase.table("events").update(payload).eq("id", event["id"]).execute()
        else:
            supabase.table("events").insert(payload).execute()
    except Exception as e:
        st.error(f"일정 저장 오류: {e}")

def db_delete_event(event_id):
    try:
        supabase.table("events").delete().eq("id", event_id).execute()
    except Exception as e:
        st.error(f"일정 삭제 오류: {e}")

def db_get_timetable(user_id):
    try:
        res = supabase.table("timetable").select("*").eq("user_id", user_id).execute()
        return res.data or []
    except Exception:
        return []

def db_save_timetable_entry(user_id, entry):
    try:
        supabase.table("timetable").insert({
            "user_id": user_id,
            "title": entry["title"],
            "day": entry["day"],
            "start_time": entry["start"],
            "end_time": entry["end"],
            "color": entry.get("color", get_random_color()),
        }).execute()
    except Exception as e:
        st.error(f"시간표 저장 오류: {e}")

def db_delete_timetable_entry(entry_id):
    try:
        supabase.table("timetable").delete().eq("id", entry_id).execute()
    except Exception as e:
        st.error(f"시간표 삭제 오류: {e}")

def db_get_rooms(user_id):
    try:
        res = (
            supabase.table("room_members")
            .select("room_code, nickname, rooms(name)")
            .eq("user_id", user_id)
            .execute()
        )
        rooms = {}
        for row in (res.data or []):
            code = row["room_code"]
            rooms[code] = {"name": row["rooms"]["name"], "my_nickname": row["nickname"]}
        return rooms
    except Exception:
        return {}

def db_create_room(user_id, room_name, nickname):
    try:
        while True:
            code = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
            if not supabase.table("rooms").select("code").eq("code", code).execute().data:
                break
        supabase.table("rooms").insert({"code": code, "name": room_name}).execute()
        supabase.table("room_members").insert({
            "room_code": code, "user_id": user_id, "nickname": nickname,
        }).execute()
        return code
    except Exception as e:
        st.error(f"방 생성 오류: {e}")
        return ""

def db_join_room(user_id, room_code, nickname):
    try:
        if not supabase.table("rooms").select("code").eq("code", room_code).execute().data:
            return False
        existing = (
            supabase.table("room_members")
            .select("id").eq("room_code", room_code).eq("user_id", user_id).execute()
        )
        if not existing.data:
            supabase.table("room_members").insert({
                "room_code": room_code, "user_id": user_id, "nickname": nickname,
            }).execute()
        return True
    except Exception as e:
        st.error(f"방 입장 오류: {e}")
        return False

def db_get_room_members(room_code):
    try:
        members_res = (
            supabase.table("room_members")
            .select("user_id, nickname").eq("room_code", room_code).execute()
        )
        members = {}
        for m in (members_res.data or []):
            uid, nick = m["user_id"], m["nickname"]
            events_raw = db_get_user_events(uid)
            timetable_raw = db_get_timetable(uid)
            members[nick] = {
                "events": [
                    {"title": e["title"], "start": e["start_dt"], "end": e["end_dt"]}
                    for e in events_raw
                ],
                "timetable": [
                    {"title": t["title"], "day": t["day"],
                     "start": t["start_time"], "end": t["end_time"]}
                    for t in timetable_raw
                ],
            }
        return members
    except Exception:
        return {}

def db_get_room_info(room_code):
    try:
        res = supabase.table("rooms").select("name").eq("code", room_code).execute()
        return res.data[0] if res.data else None
    except Exception:
        return None


# ════════════════════════════════════════════════
# 세션 초기화
# ════════════════════════════════════════════════
def init_session():
    defaults = {
        "app_page": "LOGIN",
        "my_events": [],
        "my_timetable": [],
        "current_group_code": None,
        "my_nickname": "",
        "editing_event_idx": None,
        "active_add_day": None,
        "fixed_expander_open": False,
        "my_joined_rooms": {},
        "user_id": None,
        "username": None,
        "data_loaded": False,
        "confirm_delete_account": False,
        "view_year": datetime.now().year,
        "view_month": datetime.now().month,
        "selected_event_id": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session()


def load_user_data():
    if st.session_state.data_loaded:
        return
    uid = st.session_state.user_id
    if not uid:
        return
    st.session_state.my_events = [
        {"id": e["id"], "title": e["title"], "start": e["start_dt"],
         "end": e["end_dt"], "color": e.get("color", get_random_color())}
        for e in db_get_user_events(uid)
    ]
    st.session_state.my_timetable = [
        {"id": t["id"], "title": t["title"], "day": t["day"],
         "start": t["start_time"], "end": t["end_time"], "color": t.get("color", get_random_color())}
        for t in db_get_timetable(uid)
    ]
    st.session_state.my_joined_rooms = db_get_rooms(uid)
    st.session_state.data_loaded = True

def do_logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

def require_login():
    if not st.session_state.user_id:
        st.session_state.app_page = "LOGIN"
        st.rerun()


# ════════════════════════════════════════════════
# 공통 상단 헤더
# ════════════════════════════════════════════════
def render_header(title, back_page=None, back_label="← 홈으로"):
    c1, c2 = st.columns([5, 2])
    with c2:
        st.caption(f"👤 {st.session_state.username}")
        if st.button("로그아웃", use_container_width=True, key="hdr_logout"):
            do_logout()
        if back_page:
            if st.button(back_label, use_container_width=True, key="hdr_back"):
                st.session_state.app_page = back_page
                st.rerun()
    with c1:
        st.title(title)


# ════════════════════════════════════════════════
# 0. 로그인 / 회원가입
# ════════════════════════════════════════════════
def page_login():
    st.title("🤝 When We Meet")
    st.subheader("로그인 또는 회원가입")

    tab_login, tab_signup = st.tabs(["🔐 로그인", "📝 회원가입"])

    with tab_login:
        username = st.text_input("아이디", key="login_id")
        password = st.text_input("비밀번호", type="password", key="login_pw")
        if st.button("로그인", type="primary", use_container_width=True):
            if not username or not password:
                st.warning("아이디와 비밀번호를 모두 입력해주세요.")
            else:
                user, err = db_login(username, password)
                if err:
                    st.error(err)
                else:
                    st.session_state.user_id = user["id"]
                    st.session_state.username = user["username"]
                    st.session_state.data_loaded = False
                    load_user_data()
                    st.session_state.app_page = "HOME"
                    st.rerun()

    with tab_signup:
        new_id = st.text_input("아이디 (4자 이상)", key="signup_id")
        new_pw = st.text_input("비밀번호 (6자 이상)", type="password", key="signup_pw")
        new_pw2 = st.text_input("비밀번호 확인", type="password", key="signup_pw2")
        if st.button("회원가입", type="primary", use_container_width=True):
            if not new_id or not new_pw:
                st.warning("아이디와 비밀번호를 입력해주세요.")
            elif len(new_id) < 4:
                st.warning("아이디는 4자 이상이어야 합니다.")
            elif len(new_pw) < 6:
                st.warning("비밀번호는 6자 이상이어야 합니다.")
            elif new_pw != new_pw2:
                st.warning("비밀번호가 일치하지 않습니다.")
            else:
                user, err = db_create_user(new_id, new_pw)
                if err:
                    st.error(err)
                else:
                    st.success("✅ 회원가입 완료! 로그인해주세요.")


# ════════════════════════════════════════════════
# 계정 설정
# ════════════════════════════════════════════════
def page_account():
    render_header("⚙️ 계정 설정", back_page="HOME")
    st.markdown(f"현재 아이디: **{st.session_state.username}**")
    st.markdown("---")

    st.subheader("🔑 비밀번호 변경")
    with st.form("change_pw_form"):
        cur_pw = st.text_input("현재 비밀번호", type="password")
        new_pw = st.text_input("새 비밀번호 (6자 이상)", type="password")
        new_pw2 = st.text_input("새 비밀번호 확인", type="password")
        if st.form_submit_button("변경하기", type="primary"):
            if not cur_pw or not new_pw:
                st.warning("모든 칸을 입력해주세요.")
            elif len(new_pw) < 6:
                st.warning("비밀번호는 6자 이상이어야 합니다.")
            elif new_pw != new_pw2:
                st.warning("새 비밀번호가 일치하지 않습니다.")
            else:
                user, err = db_login(st.session_state.username, cur_pw)
                if err:
                    st.error("현재 비밀번호가 틀렸습니다.")
                else:
                    supabase.table("users").update({
                        "password_hash": hash_password(new_pw)
                    }).eq("id", st.session_state.user_id).execute()
                    st.success("✅ 비밀번호가 변경됐습니다.")

    st.markdown("---")
    st.subheader("🗑️ 회원탈퇴")
    st.warning("탈퇴하면 모든 일정, 시간표, 그룹 데이터가 영구 삭제됩니다.")

    if not st.session_state.confirm_delete_account:
        if st.button("회원탈퇴", use_container_width=True):
            st.session_state.confirm_delete_account = True
            st.rerun()
    else:
        st.error("정말로 탈퇴하시겠습니까? 되돌릴 수 없습니다.")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ 네, 탈퇴합니다", type="primary", use_container_width=True):
                if db_delete_user(st.session_state.user_id):
                    do_logout()
        with c2:
            if st.button("취소", use_container_width=True):
                st.session_state.confirm_delete_account = False
                st.rerun()


# ════════════════════════════════════════════════
# 홈 화면
# ════════════════════════════════════════════════
def page_home():
    c1, c2 = st.columns([5, 2])
    with c2:
        st.caption(f"👤 {st.session_state.username}")
        if st.button("로그아웃", use_container_width=True):
            do_logout()
        if st.button("⚙️ 계정 설정", use_container_width=True):
            st.session_state.app_page = "ACCOUNT"
            st.rerun()
    with c1:
        st.title("🤝 When We Meet")

    now = datetime.now()
    st.subheader(f"📅 {now.year}년 {now.month}월")

    cal_matrix = calendar.monthcalendar(now.year, now.month)
    
    cal_html = """
    <div style="display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; text-align: center;">
    """
    for d in ["일", "월", "화", "수", "목", "금", "토"]:
        cal_html += f"<div style='font-weight: bold; padding: 6px 0; font-size: 12px;'>{d}</div>"

    for week in cal_matrix:
        for day_num in week:
            if day_num != 0:
                if day_num == now.day:
                    cal_html += (
                        f"<div style='background-color:#E3F2FD; padding:6px 1px; "
                        f"border-radius:6px; border:1px solid #2196F3; font-weight:bold; font-size:12px;'>"
                        f"{day_num}<br><span style='color:#1E88E5; font-size:8px; font-weight:normal;'>Today</span></div>"
                    )
                else:
                    cal_html += (
                        f"<div style='background-color:white; padding:10px 1px; "
                        f"border-radius:6px; border:1px solid #eee; font-size:12px; color:#333;'>{day_num}</div>"
                    )
            else:
                cal_html += "<div></div>"
    cal_html += "</div>"
    st.markdown(cal_html, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("---")
    b1, b2 = st.columns(2)
    with b1:
        if st.button("나의 일정", type="primary", use_container_width=True):
            st.session_state.app_page = "MY_CALENDAR"
            st.rerun()
    with b2:
        if st.button("📅 그룹 목록", use_container_width=True):
            st.session_state.app_page = "GROUP_LIST"
            st.rerun()


# ════════════════════════════════════════════════
# 나의 일정 (컴팩트 7열 달력 형태 스마트폰 완전 최적화)
# ════════════════════════════════════════════════
def page_my_calendar():
    h1, h2 = st.columns([5, 2])
    with h2:
        if st.button("홈으로", use_container_width=True):
            st.session_state.app_page = "HOME"
            st.rerun()
    with h1:
        st.title("📆 나의 일정")

    n1, n2, n3 = st.columns([1, 4, 1])
    with n1:
        if st.button("<", use_container_width=True):
            st.session_state.view_month -= 1
            if st.session_state.view_month == 0:
                st.session_state.view_month = 12
                st.session_state.view_year -= 1
            st.session_state.active_add_day = None
            st.session_state.selected_event_id = None
            st.session_state.editing_event_idx = None
            st.rerun()
    with n2:
        st.markdown(
            f"<h4 style='text-align:center; margin: 0; font-size:16px;'>{st.session_state.view_year}년 "
            f"{st.session_state.view_month}월</h4>", unsafe_allow_html=True
        )
    with n3:
        if st.button(">", use_container_width=True):
            st.session_state.view_month += 1
            if st.session_state.view_month == 13:
                st.session_state.view_month = 1
                st.session_state.view_year += 1
            st.session_state.active_add_day = None
            st.session_state.selected_event_id = None
            st.session_state.editing_event_idx = None
            st.rerun()

    cur_year   = st.session_state.view_year
    cur_month  = st.session_state.view_month
    today      = datetime.now()
    cal_matrix = calendar.monthcalendar(cur_year, cur_month)
    active_day = st.session_state.get("active_add_day")

    # 요일 헤더 (폰 화면 안 깨지도록 폰트 축소)
    day_names = ["일", "월", "화", "수", "목", "금", "토"]
    cols_hdr = st.columns(7)
    for i, dn in enumerate(day_names):
        color = "#E53935" if i == 0 else ("#1565C0" if i == 6 else "#555")
        cols_hdr[i].markdown(f"<div style='text-align:center;font-size:10px;font-weight:bold;color:{color};'>{dn}</div>", unsafe_allow_html=True)

    # 주(week) 단위로 달력 격자 렌더
    for week in cal_matrix:
        cols = st.columns(7)
        
        for col_idx, day_num in enumerate(week):
            if day_num == 0:
                with cols[col_idx]:
                    st.markdown("<div style='min-height:36px;'></div>", unsafe_allow_html=True)
                continue
                
            date_str  = f"{cur_year}-{cur_month:02d}-{day_num:02d}"
            is_today  = (day_num == today.day and cur_month == today.month and cur_year == today.year)
            is_active = (active_day == day_num)
            is_sun    = (col_idx == 0)
            is_sat    = (col_idx == 6)

            num_color = "#E53935" if is_sun else ("#1565C0" if is_sat else "#212121")
            bg_color  = "#EEF4FF" if is_active else ("#FFF9C4" if is_today else "#FFFFFF")
            border_c  = "#1976D2" if is_active else "#E0E0E0"
            border_w  = "1.5px" if is_active else "1px"

            day_events = [
                ev for ev in st.session_state.my_events
                if ev["start"].split()[0] <= date_str <= ev["end"].split()[0]
            ]
            
            # 모바일 최적화 미니 점표시
            bars_html = ""
            if day_events:
                c = day_events[0].get("color", "#4D96FF")
                bars_html += f"<div style='background:{c};height:3px;border-radius:1.5px;margin:1px auto 0 auto;width:70%;'></div>"
            else:
                bars_html += "<div style='height:3px;'></div>"

            with cols[col_idx]:
                container_style = f"""
                <div style="background:{bg_color}; border:{border_w} solid {border_c}; border-radius:4px; padding:1px 0px; text-align:center; min-height:35px; display:flex; flex-direction:column; justify-content:center; align-items:center;">
                    <span style="font-size:10px; font-weight:bold; color:{num_color}; line-height:1;">{day_num}</span>
                    {bars_html}
                </div>
                """
                st.markdown(container_style, unsafe_allow_html=True)
                
                # 폰 크기에 딱 맞춘 초소형 선택 버튼 (CSS 효과로 절대 줄 안 깨짐)
                if st.button("선택" if not is_active else "✔", key=f"day_{date_str}", use_container_width=True):
                    if is_active:
                        st.session_state.active_add_day = None
                    else:
                        st.session_state.active_add_day = day_num
                        st.session_state.selected_event_id = None
                        st.session_state.editing_event_idx = None
                    st.rerun()

        # 주(Week) 바로 밑에 상세 칸이 나타나는 완벽한 사용자 인터페이스 보존
        if active_day and active_day in week:
            add_day = active_day
            date_str_sel   = f"{cur_year}-{cur_month:02d}-{add_day:02d}"
            day_events_sel = [
                (i, ev) for i, ev in enumerate(st.session_state.my_events)
                if ev["start"].split()[0] <= date_str_sel <= ev["end"].split()[0]
            ]

            st.markdown("---")
            hc1, hc2 = st.columns([5, 2])
            with hc1:
                st.markdown(f"<h5 style='margin:0;'>📅 {cur_year}년 {cur_month}월 {add_day}일</h5>", unsafe_allow_html=True)
            with hc2:
                if st.button("✖ 닫기", key="close_day_panel"):
                    st.session_state.active_add_day   = None
                    st.session_state.selected_event_id = None
                    st.session_state.editing_event_idx = None
                    st.rerun()

            if day_events_sel:
                st.markdown("**이 날 일정:**")
                for ev_i, ev in day_events_sel:
                    color   = ev.get("color", "#4D96FF")
                    s_t     = ev["start"].split()[1] if " " in ev["start"] else ""
                    e_t     = ev["end"].split()[1]   if " " in ev["end"]   else ""
                    ev_id   = ev.get("id") or f"idx_{ev_i}"
                    is_sel  = (st.session_state.selected_event_id == ev_id)

                    r_int = int(color[1:3], 16)
                    g_int = int(color[3:5], 16)
                    b_int = int(color[5:7], 16)
                    bg_style = f"rgba({r_int},{g_int},{b_int},{0.22 if is_sel else 0.10})"
                    border_c = "#1976D2" if is_sel else color

                    col_bar, col_btn = st.columns([5, 2])
                    with col_bar:
                        st.markdown(
                            f"<div style='background:{bg_style}; border-left:4px solid {border_c}; "
                            f"border-radius:0 6px 6px 0; padding:6px 10px; margin-bottom:4px;'>"
                            f"<div style='font-weight:700; font-size:13px; color:{color};'>{ev['title']}</div>"
                            f"<div style='font-size:11px; color:#555; margin-top:1px;'>🕐 {s_t} ~ {e_t}</div>"
                            f"</div>",
                            unsafe_allow_html=True
                        )
                    with col_btn:
                        lbl = "✖" if is_sel else "수정"
                        if st.button(lbl, key=f"sel_ev_{ev_id}", use_container_width=True):
                            if is_sel:
                                st.session_state.selected_event_id = None
                                st.session_state.editing_event_idx = None
                            else:
                                st.session_state.selected_event_id = ev_id
                                st.session_state.editing_event_idx = ev_i
                            st.rerun()

                    if is_sel:
                        try:
                            s_d_obj = datetime.strptime(ev["start"].split()[0], "%Y-%m-%d").date()
                            s_t_obj = datetime.strptime(ev["start"].split()[1], "%H:%M").time()
                            e_d_obj = datetime.strptime(ev["end"].split()[0],   "%Y-%m-%d").date()
                            e_t_obj = datetime.strptime(ev["end"].split()[1],   "%H:%M").time()
                        except Exception:
                            s_d_obj = e_d_obj = datetime.now().date()
                            s_t_obj = datetime.strptime("09:00", "%H:%M").time()
                            e_t_obj = datetime.strptime("18:00", "%H:%M").time()

                        with st.form(f"edit_event_form_{ev_id}"):
                            new_title = st.text_input("일정 제목", value=ev["title"])
                            new_s_date = st.date_input("시작 날짜", value=s_d_obj)
                            new_s_time = st.time_input("시작 시간", value=s_t_obj)
                            new_e_date = st.date_input("종료 날짜", value=e_d_obj)
                            new_e_time = st.time_input("종료 시간", value=e_t_obj)
                            col_save, col_del = st.columns(2)
                            saved = col_save.form_submit_button("💾 저장", use_container_width=True)
                            deleted = col_del.form_submit_button("🗑️ 삭제", use_container_width=True)

                        if saved:
                            updated = {
                                "id":    ev.get("id"),
                                "title": new_title,
                                "start": f"{new_s_date} {new_s_time.strftime('%H:%M')}",
                                "end":   f"{new_e_date} {new_e_time.strftime('%H:%M')}",
                                "color": ev.get("color", get_random_color()),
                            }
                            db_save_event(st.session_state.user_id, updated)
                            st.session_state.my_events[ev_i] = updated
                            st.session_state.selected_event_id = None
                            st.session_state.editing_event_idx = None
                            st.rerun()
                        elif deleted:
                            if ev.get("id"):
                                db_delete_event(ev["id"])
                            st.session_state.my_events.pop(ev_i)
                            st.session_state.selected_event_id = None
                            st.session_state.editing_event_idx = None
                            st.rerun()

            st.markdown(f"**➕ {add_day}일 새 일정 추가**")
            with st.form("event_form"):
                ev_title = st.text_input("일정 제목")
                s_date = st.date_input("시작 날짜", value=datetime(cur_year, cur_month, add_day))
                s_time = st.time_input("시작 시간", value=datetime.strptime("09:00", "%H:%M").time())
                e_date = st.date_input("종료 날짜", value=datetime(cur_year, cur_month, add_day))
                e_time = st.time_input("종료 시간", value=datetime.strptime("18:00", "%H:%M").time())
                col_s, col_c = st.columns(2)
                do_save   = col_s.form_submit_button("💾 저장", use_container_width=True)
                do_cancel = col_c.form_submit_button("✖ 취소", use_container_width=True)

            if do_save:
                if not ev_title:
                    st.warning("일정 제목을 입력해주세요.")
                else:
                    new_ev = {
                        "title": ev_title,
                        "start": f"{s_date} {s_time.strftime('%H:%M')}",
                        "end":   f"{e_date} {e_time.strftime('%H:%M')}",
                        "color": get_random_color(),
                    }
                    db_save_event(st.session_state.user_id, new_ev)
                    st.session_state.data_loaded = False
                    load_user_data()
                    st.session_state.active_add_day = None
                    st.rerun()
            elif do_cancel:
                st.session_state.active_add_day = None
                st.rerun()

    st.write(" ")
    if st.button("⚙️ 고정 시간표 관리", type="secondary", use_container_width=True):
        st.session_state.app_page = "FIXED_TIMETABLE"
        st.rerun()


# ════════════════════════════════════════════════
# 고정 시간표 (가로 터짐 방지 컨테이너 스크롤 적용)
# ════════════════════════════════════════════════
def page_fixed_timetable():
    h1, h2 = st.columns([5, 2])
    with h2:
        if st.button("달력 보기", use_container_width=True):
            st.session_state.app_page = "MY_CALENDAR"
            st.rerun()
    with h1:
        st.title("🕞 고정 시간표 목록")

    with st.expander("➕ 고정 일정 추가", expanded=st.session_state.fixed_expander_open):
        f_title = st.text_input("일정 제목", key="ft_title")
        f_day = st.selectbox("요일", ["월", "화", "수", "목", "금", "토", "일"], key="ft_day")
        f_start = st.text_input("시작 시각 (예: 09:00)", value="09:00", key="ft_start")
        f_end = st.text_input("종료 시각 (예: 12:00)", value="12:00", key="ft_end")
        if st.button("저장", key="ft_save", type="primary", use_container_width=True):
            if f_title:
                db_save_timetable_entry(st.session_state.user_id, {
                    "title": f_title, "day": f_day,
                    "start": f_start, "end": f_end, "color": get_random_color(),
                })
                st.session_state.fixed_expander_open = False
                st.session_state.data_loaded = False
                load_user_data()
                st.rerun()
            else:
                st.warning("일정 제목을 입력해주세요.")

    if st.session_state.my_timetable:
        st.markdown("### 📋 등록된 고정 일정")
        for ti, t in enumerate(st.session_state.my_timetable):
            col_a, col_b = st.columns([5, 2])
            with col_a:
                st.markdown(
                    f"<div style='background-color:{t.get('color','#BBDEFB')}; padding:6px; "
                    f"border-radius:5px; margin-bottom:4px; color:#333; font-size:11px;'>"
                    f"<b>{t['title']}</b> | {t['day']}요일 {t['start']} ~ {t['end']}</div>",
                    unsafe_allow_html=True
                )
            with col_b:
                if st.button("🗑️", key=f"del_tt_{ti}", use_container_width=True):
                    if t.get("id"):
                        db_delete_timetable_entry(t["id"])
                    st.session_state.my_timetable.pop(ti)
                    st.rerun()

    st.write("### 📊 일주일 타임라인")
    # mobile-table-container 클래스로 감싸서 화면 전체가 늘어나는 현상을 완벽 차단
    table_html = (
        "<div class='mobile-table-container'>"
        "<table style='width:100%; min-width:450px; table-layout:fixed; border-collapse:collapse; text-align:center; "
        "font-size:10px; border:1px solid #ddd; word-break:break-all;'>"
        "<tr style='background-color:#F5F5F5; font-weight:bold;'>"
    )
    for d in ["시간", "월", "화", "수", "목", "금", "토", "일"]:
        table_html += f"<th style='border:1px solid #ddd; padding:4px;'>{d}</th>"
    table_html += "</tr>"
    for hour in range(24):
        for minute in [0, 15, 30, 45]:
            time_str = f"{hour:02d}:{minute:02d}"
            table_html += (
                f"<tr><td style='border:1px solid #ddd; background-color:#FAFAFA; "
                f"font-weight:bold; padding:2px;'>{time_str}</td>"
            )
            for d_name in ["월", "화", "수", "목", "금", "토", "일"]:
                bg, text = "white", ""
                for t in st.session_state.my_timetable:
                    if t["day"] == d_name and t["start"] <= time_str < t["end"]:
                        bg, text = t.get("color", "#BBDEFB"), t["title"]
                table_html += (
                    f"<td style='border:1px solid #ddd; background-color:{bg}; color:#1565C0; padding:1px;'>{text[:3]}</td>"
                )
            table_html += "</tr>"
    table_html += "</table></div>"
    st.markdown(table_html, unsafe_allow_html=True)


# ════════════════════════════════════════════════
# 그룹 목록
# ════════════════════════════════════════════════
def page_group_list():
    h1, h2 = st.columns([5, 2])
    with h2:
        if st.button("홈으로", use_container_width=True):
            st.session_state.app_page = "HOME"
            st.rerun()
    with h1:
        st.title("👥 그룹 방 관리")

    g_action = st.radio(
        "작업 선택", ["선택 안 함", "새로운 그룹 만들기", "코드로 그룹 입장하기"], horizontal=True
    )

    if g_action == "새로운 그룹 만들기":
        g_name = st.text_input("그룹명")
        nickname = st.text_input("내 닉네임")
        if st.button("방 생성 🚀", use_container_width=True):
            if g_name and nickname:
                code = db_create_room(st.session_state.user_id, g_name, nickname)
                if code:
                    st.session_state.my_nickname = nickname
                    st.session_state.current_group_code = code
                    st.session_state.my_joined_rooms[code] = {"name": g_name, "my_nickname": nickname}
                    st.success(f"✅ 방 코드: **`{code}`** 를 친구에게 공유하세요!")
                    st.session_state.app_page = "GROUP_ROOM"
                    st.rerun()
            else:
                st.warning("그룹명과 닉네임을 입력해주세요.")

    elif g_action == "코드로 그룹 입장하기":
        join_code = st.text_input("입장 코드 5자리").strip().upper()
        nickname = st.text_input("내 닉네임")
        if st.button("입장 🚪", use_container_width=True):
            if join_code and nickname:
                if db_join_room(st.session_state.user_id, join_code, nickname):
                    room_info = db_get_room_info(join_code)
                    st.session_state.my_nickname = nickname
                    st.session_state.current_group_code = join_code
                    st.session_state.my_joined_rooms[join_code] = {
                        "name": room_info["name"] if room_info else join_code,
                        "my_nickname": nickname,
                    }
                    st.session_state.app_page = "GROUP_ROOM"
                    st.rerun()
                else:
                    st.error("유효하지 않은 코드입니다.")
            else:
                st.warning("코드와 닉네임을 입력해주세요.")

    st.markdown("---")
    st.subheader("참여 중인 방")
    if not st.session_state.my_joined_rooms:
        st.caption("참여 중인 방이 없습니다.")
    else:
        for c, info in st.session_state.my_joined_rooms.items():
            col_r1, col_r2 = st.columns([4, 2])
            with col_r1:
                st.info(f"🏠 **{info['name']}** (코드: `{c}`) \n\n 닉네임: {info['my_nickname']}")
            with col_r2:
                if st.button("입장", key=f"enter_{c}", use_container_width=True):
                    st.session_state.current_group_code = c
                    st.session_state.my_nickname = info["my_nickname"]
                    st.session_state.app_page = "GROUP_ROOM"
                    st.rerun()


# ════════════════════════════════════════════════
# 그룹 방 (캘린더 형태 유지 + 모바일 가로 찌그러짐 파괴)
# ════════════════════════════════════════════════
def slot_to_time(i):
    return f"{i // 4:02d}:{(i % 4) * 15:02d}"

def compute_free_slots(g_members, year, month, day, time_start_h, time_end_h):
    from datetime import date as date_type
    curr_date = date_type(year, month, day)
    w_str = ["월", "화", "수", "목", "금", "토", "일"][curr_date.weekday()]
    d_str = f"{year}-{month:02d}-{day:02d}"

    SLOTS = 96
    slots = [False] * SLOTS
    for i in range(time_start_h * 4, time_end_h * 4):
        slots[i] = True

    for name, m_data in g_members.items():
        for t in m_data.get("timetable", []):
            if t["day"] == w_str:
                try:
                    sh, sm = map(int, t["start"].split(":"))
                    eh, em = map(int, t["end"].split(":"))
                    for i in range(sh * 4 + sm // 15, eh * 4 + em // 15):
                        slots[i] = False
                except Exception:
                    pass
        for ev in m_data.get("events", []):
            if ev["start"].split()[0] <= d_str <= ev["end"].split()[0]:
                try:
                    sh, sm = map(int, ev["start"].split()[1].split(":"))
                    eh, em = map(int, ev["end"].split()[1].split(":"))
                    for i in range(sh * 4 + sm // 15, eh * 4 + em // 15):
                        slots[i] = False
                except Exception:
                    pass
    return slots

def page_group_room():
    code = st.session_state.current_group_code
    room_info = db_get_room_info(code)

    if not room_info:
        st.error("방 정보를 찾을 수 없습니다.")
        if st.button("그룹 목록으로"):
            st.session_state.app_page = "GROUP_LIST"
            st.rerun()
        return

    g_members = db_get_room_members(code)

    h1, h2 = st.columns([5, 2])
    with h2:
        if st.button("< 그룹 목록", use_container_width=True):
            st.session_state.app_page = "GROUP_LIST"
            st.rerun()
        st.caption(f"방 코드: `{code}`")
        if st.button("👥 멤버", use_container_width=True):
            st.info(f"{len(g_members)}명: {', '.join(g_members.keys())}")
    with h1:
        st.title(f"🏢 {room_info['name']}")

    st.markdown("---")
    st.subheader("🔍 약속 가능 찾기")

    now = datetime.now()
    last_day = calendar.monthrange(now.year, now.month)[1]
    from datetime import date as date_type, timedelta

    date_range = st.date_input(
        "📅 범위 설정",
        value=(datetime(now.year, now.month, 1).date(),
               datetime(now.year, now.month, last_day).date()),
        key="grp_date_range"
    )
    min_h = st.number_input("⏱️ 최소 시간 (시간)", min_value=1, max_value=12, value=2, key="grp_min_h")

    st.markdown("🕐 **희망 시간대**")
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        time_start_h = st.selectbox("시작", options=list(range(0, 24)), index=9, key="grp_time_start_sel")
    with col_t2:
        time_end_h = st.selectbox("종료", options=list(range(1, 25)), index=20, key="grp_time_end_sel")

    if st.button("📊 일정 대조하기", type="primary", use_container_width=True):
        if time_start_h >= time_end_h:
            st.error("종료 시각은 시작 시각보다 늦어야 합니다.")
        else:
            if isinstance(date_range, tuple) and len(date_range) == 2:
                start_d, end_d = date_range
            else:
                start_d = date_type(now.year, now.month, 1)
                end_d = date_type(now.year, now.month, last_day)

            date_colors = {}
            free_slots_cache = {}

            cur = start_d
            while cur <= end_d:
                slots = compute_free_slots(g_members, cur.year, cur.month, cur.day, time_start_h, time_end_h)
                max_c = curr_c = 0
                for i in range(time_start_h * 4, time_end_h * 4):
                    if slots[i]:
                        curr_c += 1
                        max_c = max(max_c, curr_c)
                    else:
                        curr_c = 0
                key = cur.strftime("%Y-%m-%d")
                if max_c >= min_h * 4:
                    date_colors[key] = "green"
                else:
                    date_colors[key] = "red"
                free_slots_cache[key] = slots
                cur += timedelta(days=1)

            st.session_state.grp_date_colors = date_colors
            st.session_state.grp_free_slots = free_slots_cache
            st.session_state.grp_selected_day = None
            st.session_state.grp_start_d = start_d
            st.session_state.grp_end_d = end_d
            st.session_state.grp_time_start = time_start_h
            st.session_state.grp_time_end = time_end_h
            st.rerun()

    if "grp_date_colors" not in st.session_state:
        st.info("조건 설정 후 대조하기를 눌러주세요.")
        return

    colors = st.session_state.grp_date_colors
    start_d = st.session_state.grp_start_d
    end_d = st.session_state.grp_end_d
    t_start = st.session_state.grp_time_start
    t_end = st.session_state.grp_time_end

    st.markdown("---")
    st.markdown("### 📅 일정 대조 달력")
    st.markdown("<div style='font-size:10px; text-align:center; color:#555;'>🟢가능 | 🔴불가 | ⚪제외</div>", unsafe_allow_html=True)

    if "grp_selected_day" not in st.session_state:
        st.session_state.grp_selected_day = None

    render_year, render_month = start_d.year, start_d.month
    end_year, end_month = end_d.year, end_d.month

    # 주 밑에 표시되는 그룹 분석창 최적화
    def render_day_detail(sel_day):
        slots = st.session_state.grp_free_slots.get(sel_day, [False] * 96)
        year_s, month_s, day_s = map(int, sel_day.split("-"))

        st.markdown("---")
        dc1, dc2 = st.columns([5, 2])
        with dc1:
            st.markdown(f"<h5 style='margin:0;'>📊 {month_s}월 {day_s}일 분석</h5>", unsafe_allow_html=True)
        with dc2:
            if st.button("✖ 닫기", key=f"grp_close_{sel_day}"):
                st.session_state.grp_selected_day = None
                st.rerun()

        bar_rows = []
        for hour in range(24):
            cells = "".join(
                '<div style="background:{bg};flex:1;height:12px;border-radius:1px;margin:0 1px;"></div>'.format(
                    bg="#4CAF50" if (slots[hour*4+mi] if hour*4+mi < len(slots) else False) else "#F44336"
                )
                for mi in range(4)
            )
            bar_rows.append(
                '<div style="display:flex;align-items:center;gap:3px;margin-bottom:1px;">'
                '<span style="font-size:9px;color:#555;min-width:28px;text-align:right;">{h:02d}:00</span>'
                '<div style="display:flex;flex:1;">{cells}</div>'
                '</div>'.format(h=hour, cells=cells)
            )
        
        # 스크롤바 컴팩트화
        bar_html = (
            '<div class="mobile-table-container" style="background:#fafafa; border:1px solid #ddd; border-radius:6px; padding:6px;">'
            + "".join(bar_rows) +
            '</div>'
        )
        st.markdown(bar_html, unsafe_allow_html=True)

        s_idx = t_start * 4
        e_idx = t_end * 4
        avail_slots = [i for i in range(s_idx, e_idx) if i < len(slots) and slots[i]]

        if not avail_slots:
            st.error("가용 시간이 없습니다.")
        else:
            ranges = []
            seg_s = avail_slots[0]
            seg_e = avail_slots[0]
            for i in avail_slots[1:]:
                if i == seg_e + 1:
                    seg_e = i
                else:
                    ranges.append((seg_s, seg_e + 1))
                    seg_s = seg_e = i
            ranges.append((seg_s, seg_e + 1))

            range_texts = [f"<b>{slot_to_time(rs)} ~ {slot_to_time(re)}</b>" for rs, re in ranges]
            st.markdown(
                "<div style='background:#E8F5E9; border:1px solid #388E3C; border-radius:6px; "
                "padding:8px; font-size:12px; color:#1B5E20; line-height:1.5;'>"
                "✅ 추천 시간대:<br>" + " | ".join(range_texts) + "</div>",
                unsafe_allow_html=True
            )

            with st.form(f"c_confirm_{sel_day}"):
                time_options = [f"{h:02d}:{m:02d}" for h in range(24) for m in [0, 15, 30, 45]]
                c_start = st.selectbox("시작 시간", options=time_options, index=48)
                c_end = st.selectbox("종료 시간", options=time_options, index=56)
                btn_sub = st.form_submit_button("🚀 시간 확정", use_container_width=True)
            if btn_sub:
                if c_start >= c_end:
                    st.error("시간 설정 오류")
                else:
                    st.balloons()
                    st.success(f"🎉 확정! {month_s}/{sd} {c_start}~{c_end}")

    # 월별 렌더링 루프
    while (render_year, render_month) <= (end_year, end_month):
        st.markdown(f"<h6 style='margin:10px 0 2px 0;'>📅 {render_year}년 {render_month}월</h6>", unsafe_allow_html=True)
        cal_matrix = calendar.monthcalendar(render_year, render_month)

        cols_hdr = st.columns(7)
        for i, dn in enumerate(["일", "월", "화", "수", "목", "금", "토"]):
            cols_hdr[i].markdown(f"<div style='font-weight:bold;font-size:10px;text-align:center;'>{dn}</div>", unsafe_allow_html=True)

        for week in cal_matrix:
            cols = st.columns(7)
            
            for col_idx, d_num in enumerate(week):
                if d_num == 0:
                    with cols[col_idx]:
                        st.markdown("<div style='min-height:32px;'></div>", unsafe_allow_html=True)
                    continue
                    
                d_key = f"{render_year}-{render_month:02d}-{d_num:02d}"
                d_date = date_type(render_year, render_month, d_num)
                in_range = start_d <= d_date <= end_d
                is_sat = (col_idx == 6)
                is_sun = (col_idx == 0)
                num_color = "#E53935" if is_sun else ("#1565C0" if is_sat else "#212121")
                is_sel = (st.session_state.grp_selected_day == d_key)

                if in_range:
                    if colors.get(d_key, "red") == "green":
                        bg = "#C8E6C9" if is_sel else "#E8F5E9"
                        border = "1.5px solid #2E7D32" if is_sel else "1px solid #81C784"
                        status_lbl = "<span style='color:#2E7D32; font-size:7px;'>🟢가능</span>"
                    else:
                        bg = "#FFCDD2" if is_sel else "#FFEBEE"
                        border = "1.5px solid #B71C1C" if is_sel else "1px solid #E57373"
                        status_lbl = "<span style='color:#C62828; font-size:7px;'>🔴불가</span>"
                else:
                    bg, border, status_lbl = "#FAFAFA", "1px solid #eee", "<span style='color:#bbb; font-size:7px;'>⚪제외</span>"

                with cols[col_idx]:
                    container_style = f"""
                    <div style="background:{bg}; border:{border}; padding:1px 0px; text-align:center; border-radius:4px; min-height:32px; display:flex; flex-direction:column; justify-content:center; align-items:center;">
                        <span style="font-size:9px; font-weight:bold; color:{num_color}; line-height:1;">{d_num}</span>
                        {status_lbl}
                    </div>
                    """
                    st.markdown(container_style, unsafe_allow_html=True)
                    
                    if in_range:
                        if st.button("조회" if not is_sel else "✔", key=f"grp_day_{d_key}", use_container_width=True):
                            st.session_state.grp_selected_day = None if is_sel else d_key
                            st.rerun()

            # 선택된 주 밑에 상세 창 출력 구조 200% 보존
            sel = st.session_state.grp_selected_day
            if sel:
                sp = sel.split("-")
                sy, sm, sd = int(sp[0]), int(sp[1]), int(sp[2])
                if sy == render_year and sm == render_month and sd in week:
                    render_day_detail(sel)

        render_month += 1
        if render_month > 12:
            render_month = 1
            render_year += 1

    # 공통 요일별 시간표 터짐 방지 레이아웃
    st.markdown("---")
    st.subheader("📊 요일별 공통 가용 시간표")
    t_start = st.session_state.get("grp_time_start", 9)
    t_end = st.session_state.get("grp_time_end", 21)
    w_days = ["월", "화", "수", "목", "금", "토", "일"]
    hours_range = list(range(t_start, t_end))

    w_table = (
        "<div class='mobile-table-container'> "
        "<table style='width:100%; min-width:400px; table-layout:fixed; text-align:center; font-size:9px; border-collapse:collapse; border:1px solid #ddd; word-break:break-all;'> "
        "<tr style='background-color:#F5F5F5;'><th style='padding:4px; border:1px solid #ddd;'>요일/시간</th>"
    )
    for h in hours_range:
        w_table += f"<th style='border:1px solid #ddd; padding:1px;'>{h:02d}</th>"
    w_table += "</tr>"

    for w_day in w_days:
        w_table += f"<tr><td style='font-weight:bold; border:1px solid #ddd; padding:4px;'>{w_day}</td>"
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
            w_table += f"<td style='background-color:{bg}; border:1px solid #ddd; height:18px;'></td>"
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
    require_login(); page_my_calendar()
elif page == "FIXED_TIMETABLE":
    require_login(); page_fixed_timetable()
elif page == "GROUP_LIST":
    require_login(); page_group_list()
elif page == "GROUP_ROOM":
    require_login(); page_group_room()
