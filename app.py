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

st.set_page_config(page_title="When We Meet", page_icon="📅", layout="wide")

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
    c1, c2 = st.columns([5, 1])
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
    c1, c2 = st.columns([5, 1])
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
    cols = st.columns(7)
    for i, d in enumerate(["일", "월", "화", "수", "목", "금", "토"]):
        cols[i].markdown(f"<center><b>{d}</b></center>", unsafe_allow_html=True)

    for week in cal_matrix:
        cols = st.columns(7)
        for idx, day_num in enumerate(week):
            if day_num != 0:
                if day_num == now.day:
                    cols[idx].markdown(
                        f"<div style='background-color:#E3F2FD; text-align:center; padding:10px; "
                        f"border-radius:5px; border:1px solid #2196F3; font-weight:bold;'>"
                        f"{day_num}<br><span style='color:blue; font-size:10px;'>Today</span></div>",
                        unsafe_allow_html=True
                    )
                else:
                    cols[idx].markdown(
                        f"<div style='background-color:white; text-align:center; padding:10px; "
                        f"border-radius:5px; border:1px solid #ddd;'>{day_num}</div>",
                        unsafe_allow_html=True
                    )
            else:
                cols[idx].write("")

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
# 나의 일정 (안 눌러도 바로 내용이 보이는 개편된 달력)
# ════════════════════════════════════════════════
def page_my_calendar():
    # ── 💡 버튼 자체가 컬러 바(Bar)가 되어 텍스트를 바로 보여주도록 CSS 주입 ──
    st.markdown("""
        <style>
        /* 캘린더 내부 일정 바(Bar) 버튼 스타일 최적화 */
        div[data-testid="stColumn"] div.stButton > button {
            color: #FFFFFF !important;              /* 글자색 무조건 흰색 강제 */
            border: none !important;
            border-radius: 4px !important;
            padding: 3px 6px !important;            /* 내부 여백 */
            font-size: 11px !important;             /* 모바일 가독성 크기 */
            font-weight: bold !important;
            margin-top: 2px !important;
            margin-bottom: 2px !important;
            width: 100% !important;                 /* 가로 꽉 차게 */
            display: block !important;
            text-align: left !important;            /* 순정 캘린더처럼 왼쪽 정렬 */
            white-space: nowrap !important;         /* 말줄임 처리 활성화 */
            overflow: hidden !important;
            text-overflow: ellipsis !important;
            height: 24px !important;                /* 바 두께 확보 */
            line-height: 1.2 !important;
        }
        /* 마우스 호버 효과 */
        div[data-testid="stColumn"] div.stButton > button:hover {
            opacity: 0.85 !important;
            color: #FFFFFF !important;
        }
        /* 추가(+) 버튼 전용 미니멀 스타일 정의 */
        div[data-testid="stColumn"] div.stButton > button[key^="add_btn_"] {
            color: #555555 !important;
            background-color: #ECEFF1 !important;
            text-align: center !important;
            height: 22px !important;
            font-size: 10px !important;
            font-weight: normal !important;
        }
        </style>
    """, unsafe_allow_html=True)

    h1, h2 = st.columns([5, 1])
    with h2:
        if st.button("홈으로", use_container_width=True, key="cal_home_btn"):
            st.session_state.app_page = "HOME"
            st.rerun()
    with h1:
        st.title("📆 나의 일정")

    n1, n2, n3 = st.columns([1, 4, 1])
    with n1:
        if st.button("<", use_container_width=True, key="cal_prev_month"):
            st.session_state.view_month -= 1
            if st.session_state.view_month == 0:
                st.session_state.view_month = 12
                st.session_state.view_year -= 1
            st.rerun()
    with n2:
        st.markdown(
            f"<h3 style='text-align:center;'>{st.session_state.view_year}년 "
            f"{st.session_state.view_month}월</h3>", unsafe_allow_html=True
        )
    with n3:
        if st.button(">", use_container_width=True, key="cal_next_month"):
            st.session_state.view_month += 1
            if st.session_state.view_month == 13:
                st.session_state.view_month = 1
                st.session_state.view_year += 1
            st.rerun()

    cal_matrix = calendar.monthcalendar(st.session_state.view_year, st.session_state.view_month)

    cols = st.columns(7)
    for i, d in enumerate(["일", "월", "화", "수", "목", "금", "토"]):
        cols[i].markdown(f"<center><b>{d}</b></center>", unsafe_allow_html=True)

    for week in cal_matrix:
        cols = st.columns(7)
        for idx, day_num in enumerate(week):
            if day_num != 0:
                date_str = (
                    f"{st.session_state.view_year}-"
                    f"{st.session_state.view_month:02d}-"
                    f"{day_num:02d}"
                )
                
                # 해당 날짜에 포함되는 일정 필터링
                day_events = [
                    (i, ev) for i, ev in enumerate(st.session_state.my_events)
                    if ev["start"].split()[0] <= date_str <= ev["end"].split()[0]
                ]

                with cols[idx]:
                    # 날짜 숫자 표기
                    st.markdown(f"<div style='font-weight:bold; font-size:14px; border-top:1px solid #ddd; padding-top:4px;'>{day_num}</div>", unsafe_allow_html=True)
                    
                    # 숨겨진 글자판 방식 대신, 버튼 자체에 디자인 컬러와 텍스트를 주입하여 렌더링
                    for ev_i, ev in day_events:
                        color = ev.get("color", "#FF6B6B")
                        s_t = ev["start"].split()[1] if " " in ev["start"] else ""
                        
                        # 버튼 키별로 배경색을 다이내믹하게 삽입
                        st.markdown(f"""
                            <style>
                            div[data-testid="stColumn"] div.stButton > button[key="edit_ev_{date_str}_{ev_i}"] {{
                                background-color: {color} !important;
                            }}
                            </style>
                        """, unsafe_allow_html=True)
                        
                        # 버튼 텍스트에 시간과 제목을 동시에 포함시켜 안 눌러도 내용이 보이게 처리
                        if st.button(f"{s_t} {ev['title']}", key=f"edit_ev_{date_str}_{ev_i}", use_container_width=True):
                            st.session_state.editing_event_idx = ev_i
                            st.session_state.active_add_day = None
                            st.rerun()
                    
                    # 일정 추가 버튼
                    if st.button("+ 추가", key=f"add_btn_{date_str}", use_container_width=True):
                        st.session_state.active_add_day = day_num
                        st.session_state.editing_event_idx = None
                        st.rerun()
            else:
                cols[idx].write("")

    # 수정 폼
    ev_idx = st.session_state.editing_event_idx
    if ev_idx is not None and 0 <= ev_idx < len(st.session_state.my_events):
        ev = st.session_state.my_events[ev_idx]
        st.markdown("---")
        st.subheader("📋 일정 상세 / 수정")
        try:
            s_d = datetime.strptime(ev["start"].split()[0], "%Y-%m-%d").date()
            s_t = datetime.strptime(ev["start"].split()[1], "%H:%M").time()
            e_d = datetime.strptime(ev["end"].split()[0], "%Y-%m-%d").date()
            e_t = datetime.strptime(ev["end"].split()[1], "%H:%M").time()
        except Exception:
            s_d = e_d = datetime.now().date()
            s_t = datetime.strptime("09:00", "%H:%M").time()
            e_t = datetime.strptime("18:00", "%H:%M").time()

        st.info(f"📌 **{ev['title']}** | {ev['start']} → {ev['end']}")
        with st.form("edit_event_form"):
            new_title = st.text_input("일정 제목", value=ev["title"])
            new_s_date = st.date_input("시작 날짜", value=s_d)
            new_s_time = st.time_input("시작 시간", value=s_t)
            new_e_date = st.date_input("종료 날짜", value=e_d)
            new_e_time = st.time_input("종료 시간", value=e_t)
            col_save, col_del, col_cancel = st.columns(3)
            saved = col_save.form_submit_button("💾 저장")
            deleted = col_del.form_submit_button("🗑️ 삭제")
            cancelled = col_cancel.form_submit_button("✖ 취소")

        if saved:
            updated = {
                "id": ev.get("id"),
                "title": new_title,
                "start": f"{new_s_date} {new_s_time.strftime('%H:%M')}",
                "end": f"{new_e_date} {new_e_time.strftime('%H:%M')}",
                "color": ev.get("color", get_random_color()),
            }
            db_save_event(st.session_state.user_id, updated)
            st.session_state.my_events[ev_idx] = updated
            st.session_state.editing_event_idx = None
            st.rerun()
        elif deleted:
            if ev.get("id"):
                db_delete_event(ev["id"])
            st.session_state.my_events.pop(ev_idx)
            st.session_state.editing_event_idx = None
            st.rerun()
        elif cancelled:
            st.session_state.editing_event_idx = None
            st.rerun()

    # 추가 폼
    add_day = st.session_state.active_add_day
    if add_day:
        st.markdown("---")
        st.subheader(f"➕ {add_day}일 일정 추가")
        with st.form("event_form"):
            ev_title = st.text_input("일정 제목")
            s_date = st.date_input("시작 날짜",
                value=datetime(st.session_state.view_year, st.session_state.view_month, add_day))
            s_time = st.time_input("시작 시간", value=datetime.strptime("09:00", "%H:%M").time())
            e_date = st.date_input("종료 날짜",
                value=datetime(st.session_state.view_year, st.session_state.view_month, add_day))
            e_time = st.time_input("종료 시간", value=datetime.strptime("18:00", "%H:%M").time())
            if st.form_submit_button("저장"):
                new_ev = {
                    "title": ev_title,
                    "start": f"{s_date} {s_time.strftime('%H:%M')}",
                    "end": f"{e_date} {e_time.strftime('%H:%M')}",
                    "color": get_random_color(),
                }
                db_save_event(st.session_state.user_id, new_ev)
                st.session_state.data_loaded = False
                load_user_data()
                st.session_state.active_add_day = None
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("⚙️ 고정 시간표 관리", type="secondary", use_container_width=True):
        st.session_state.app_page = "FIXED_TIMETABLE"
        st.rerun()


# ════════════════════════════════════════════════
# 고정 시간표
# ════════════════════════════════════════════════
def page_fixed_timetable():
    h1, h2 = st.columns([5, 1])
    with h2:
        if st.button("달력 보기", use_container_width=True):
            st.session_state.app_page = "MY_CALENDAR"
            st.rerun()
    with h1:
        st.title("🕞 고정 시간표 목록")

    with st.expander("➕ 고정 일정 추가", expanded=st.session_state.fixed_expander_open):
        f_title = st.text_input("일정 제목", key="ft_title")
        f_day = st.selectbox("요일", ["월", "화", "수", "목", "금", "토", "일"], key="ft_day")
        f_start = st.text_input("시작 시각 (예: 09:15)", value="09:00", key="ft_start")
        f_end = st.text_input("종료 시각 (예: 11:45)", value="12:00", key="ft_end")
        if st.button("저장", key="ft_save", type="primary"):
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
            col_a, col_b = st.columns([5, 1])
            with col_a:
                st.markdown(
                    f"<div style='background-color:{t.get('color','#BBDEFB')}; padding:8px; "
                    f"border-radius:5px; margin-bottom:4px; color:#333;'>"
                    f"<b>{t['title']}</b> | {t['day']}요일 {t['start']} ~ {t['end']}</div>",
                    unsafe_allow_html=True
                )
            with col_b:
                if st.button("🗑️", key=f"del_tt_{ti}"):
                    if t.get("id"):
                        db_delete_timetable_entry(t["id"])
                    st.session_state.my_timetable.pop(ti)
                    st.rerun()

    st.write("### 📊 일주일 타임라인 (15분 단위)")
    table_html = (
        "<table style='width:100%; border-collapse:collapse; text-align:center; "
        "font-size:12px; border:1px solid #ddd;'>"
        "<tr style='background-color:#F5F5F5; font-weight:bold;'>"
    )
    for d in ["시간", "월", "화", "수", "목", "금", "토", "일"]:
        table_html += f"<th style='border:1px solid #ddd; padding:8px;'>{d}</th>"
    table_html += "</tr>"
    for hour in range(24):
        for minute in [0, 15, 30, 45]:
            time_str = f"{hour:02d}:{minute:02d}"
            table_html += (
                f"<tr><td style='border:1px solid #ddd; background-color:#FAFAFA; "
                f"font-weight:bold;'>{time_str}</td>"
            )
            for d_name in ["월", "화", "수", "목", "금", "토", "일"]:
                bg, text = "white", ""
                for t in st.session_state.my_timetable:
                    if t["day"] == d_name and t["start"] <= time_str < t["end"]:
                        bg, text = t.get("color", "#BBDEFB"), t["title"]
                table_html += (
                    f"<td style='border:1px solid #ddd; background-color:{bg}; color:#1565C0;'>{text}</td>"
                )
            table_html += "</tr>"
    table_html += "</table>"
    st.markdown(table_html, unsafe_allow_html=True)


# ════════════════════════════════════════════════
# 그룹 목록
# ════════════════════════════════════════════════
def page_group_list():
    h1, h2 = st.columns([5, 1])
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
        if st.button("방 생성 🚀"):
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
        if st.button("입장 🚪"):
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
            col_r1, col_r2 = st.columns([4, 1])
            with col_r1:
                st.info(f"🏠 **{info['name']}** (코드: `{c}`) | 닉네임: {info['my_nickname']}")
            with col_r2:
                if st.button("입장", key=f"enter_{c}", use_container_width=True):
                    st.session_state.current_group_code = c
                    st.session_state.my_nickname = info["my_nickname"]
                    st.session_state.app_page = "GROUP_ROOM"
                    st.rerun()


# ════════════════════════════════════════════════
# 그룹 방
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

    h1, h2 = st.columns([5, 1])
    with h2:
        if st.button("< 그룹 목록", use_container_width=True):
            st.session_state.app_page = "GROUP_LIST"
            st.rerun()
        st.warning(f"코드: `{code}`")
        if st.button("👥 참여자 보기", use_container_width=True):
            st.info(f"{len(g_members)}명: {', '.join(g_members.keys())}")
    with h1:
        st.title(f"🏢 {room_info['name']}")

    st.markdown("---")
    st.subheader("🔍 약속 가능 날짜 찾기")

    now = datetime.now()
    last_day = calendar.monthrange(now.year, now.month)[1]
    from datetime import date as date_type, timedelta

    col_d, col_m = st.columns(2)
    with col_d:
        date_range = st.date_input(
            "📅 날짜 범위",
            value=(datetime(now.year, now.month, 1).date(),
                   datetime(now.year, now.month, last_day).date()),
            key="grp_date_range"
        )
    with col_m:
        min_h = st.number_input("⏱️ 최소 연속 가능 시간 (시간)", min_value=1, max_value=12, value=2, key="grp_min_h")

    st.markdown("🕐 **희망 시간대**")
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        time_start_h = st.selectbox(
            "시작 시각", options=list(range(0, 24)),
            index=9, format_func=lambda x: f"{x:02d}:00", key="grp_time_start_sel"
        )
    with col_t2:
        time_end_h = st.selectbox(
            "종료 시각", options=list(range(1, 25)),
            index=20, format_func=lambda x: f"{x:02d}:00", key="grp_time_end_sel"
        )

    if st.button("📊 일정 대조하기", type="primary", use_container_width=True):
        if time_start_h >= time_end_h:
            st.error("종료 시각은 시작 시각보다 늦어야 합니다.")
        else:
            if len(date_range) == 2:
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
        st.info("조건을 설정하고 '일정 대조하기' 버튼을 눌러보세요.")
        return

    colors = st.session_state.grp_date_colors
    start_d = st.session_state.grp_start_d
    end_d = st.session_state.grp_end_d
    t_start = st.session_state.grp_time_start
    t_end = st.session_state.grp_time_end

    st.markdown("---")

    green_cnt = sum(1 for v in colors.values() if v == "green")
    red_cnt = sum(1 for v in colors.values() if v == "red")
    mc1, mc2, mc3 = st.columns(3)
    mc1.metric("✅ 가능한 날", f"{green_cnt}일")
    mc2.metric("❌ 불가능한 날", f"{red_cnt}일")
    mc3.metric("👥 참여 인원", f"{len(g_members)}명")

    st.markdown("### 📅 일정 대조 달력")
    st.markdown(
        "<div style='display:flex; gap:16px; margin-bottom:8px; font-size:13px;'>"
        "<span>🟩 약속 가능</span><span>🟥 약속 불가</span><span>⬜ 범위 외</span></div>",
        unsafe_allow_html=True
    )

    render_year, render_month = start_d.year, start_d.month
    end_year, end_month = end_d.year, end_d.month

    while (render_year, render_month) <= (end_year, end_month):
        cal_matrix = calendar.monthcalendar(render_year, render_month)
        cur_selected = st.session_state.get("grp_selected_day")

        cal_html = (
            f"<div style='margin-bottom:4px; font-weight:bold; font-size:15px;'>{render_year}년 {render_month}월</div>"
            "<table style='width:100%; border-collapse:separate; border-spacing:3px; table-layout:fixed;'>"
            "<tr>"
        )
        for dn in ["일", "월", "화", "수", "목", "금", "토"]:
            cal_html += f"<th style='text-align:center; padding:6px 2px; font-size:12px; color:#555;'>{dn}</th>"
        cal_html += "</tr>"

        for week in cal_matrix:
            cal_html += "<tr>"
            for d_num in week:
                if d_num == 0:
                    cal_html += "<td></td>"
                    continue
                d_key = f"{render_year}-{render_month:02d}-{d_num:02d}"
                d_date = date_type(render_year, render_month, d_num)
                in_range = start_d <= d_date <= end_d
                is_sel = (d_key == cur_selected)

                if in_range:
                    color_val = colors.get(d_key, "red")
                    if color_val == "green":
                        bg, txt = "#C8E6C9", "#1B5E20"
                        bdr = "#1976D2" if is_sel else "#388E3C"
                    else:
                        bg, txt = "#FFCDD2", "#7F0000"
                        bdr = "#1976D2" if is_sel else "#D32F2F"
                    bw = "3px" if is_sel else "1px"
                    shadow = "box-shadow:0 0 0 2px #1976D2;" if is_sel else ""
                else:
                    bg, txt, bdr, bw, shadow = "#F5F5F5", "#bbb", "#ddd", "1px", ""

                cal_html += f"<td style='background:{bg}; color:{txt}; text-align:center; padding:8px 2px; border-radius:6px; border:{bw} solid {bdr}; font-weight:bold; font-size:13px; {shadow}'>{d_num}</td>"
            cal_html += "</tr>"
        cal_html += "</table>"
        st.markdown(cal_html, unsafe_allow_html=True)

        for week in cal_matrix:
            has_any = any(d_num != 0 and start_d <= date_type(render_year, render_month, d_num) <= end_d for d_num in week)
            if not has_any:
                continue
            btn_cols = st.columns(7)
            for idx, d_num in enumerate(week):
                if d_num == 0:
                    continue
                d_key = f"{render_year}-{render_month:02d}-{d_num:02d}"
                d_date = date_type(render_year, render_month, d_num)
                if start_d <= d_date <= end_d:
                    is_sel = (d_key == cur_selected)
                    lbl = "✔ 선택" if is_sel else "상세"
                    if btn_cols[idx].button(lbl, key=f"detail_{d_key}", use_container_width=True):
                        st.session_state.grp_selected_day = None if is_sel else d_key
                        st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        render_month += 1
        if render_month > 12:
            render_month = 1
            render_year += 1

    selected = st.session_state.get("grp_selected_day")
    if selected:
        slots = st.session_state.grp_free_slots.get(selected, [False] * 96)
        year_s, month_s, day_s = map(int, selected.split("-"))

        st.markdown("---")
        col_title, col_close = st.columns([5, 1])
        with col_title:
            st.subheader(f"📍 {year_s}년 {month_s}월 {day_s}일 시간대 분석")
        with col_close:
            if st.button("✖ 닫기", key="close_detail"):
                st.session_state.grp_selected_day = None
                st.rerun()

        s_idx = t_start * 4
        e_idx = t_end * 4
        avail_slots = [i for i in range(s_idx, e_idx) if i < len(slots) and slots[i]]

        if not avail_slots:
            st.error("이 날짜에는 모두가 가능한 시간대가 없습니다.")
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

            range_texts = [f"<b>{slot_to_time(rs)} &#8209; {slot_to_time(re)}</b>" for rs, re in ranges]
            st.markdown(
                "<div style='background:#E8F5E9; border:1px solid #388E3C; border-radius:8px; padding:14px 16px; font-size:14px; color:#1B5E20; line-height:2;'>✅ 연속 가능 시간대:<br>" + " &nbsp;/&nbsp; ".join(range_texts) + "</div>",
                unsafe_allow_html=True
            )
            st.markdown("<br>", unsafe_allow_html=True)

            st.markdown("##### ⏰ 약속 시간 확정")
            btn_cols = st.columns(min(len(ranges), 3))
            for idx, (rs, re) in enumerate(ranges):
                duration_min = (re - rs) * 15
                dur_str = f"{duration_min // 60}시간 {duration_min % 60}분" if duration_min % 60 else f"{duration_min // 60}시간"
                if btn_cols[idx % 3].button(f"{slot_to_time(rs)} - {slot_to_time(re)} ({dur_str})", key=f"confirm_{selected}_{rs}", use_container_width=True):
                    st.balloons()
                    st.success(f"🎉 약속 확정!  {year_s}년 {month_s}월 {day_s}일  {slot_to_time(rs)} - {slot_to_time(re)}")

    st.markdown("---")
    st.subheader("📊 요일별 공통 가용 시간표")
    t_start = st.session_state.get("grp_time_start", 9)
    t_end = st.session_state.get("grp_time_end", 21)
    w_days = ["월", "화", "수", "목", "금", "토", "일"]
    hours_range = list(range(t_start, t_end))

    w_table = (
        "<table style='width:100%; text-align:center; font-size:11px; border-collapse:collapse;'><tr style='background-color:#F5F5F5;'><th style='padding:6px; border:1px solid #ddd;'>요일/시간</th>"
    )
    for h in hours_range:
        w_table += f"<th style='border:1px solid #ddd; padding:4px;'>{h:02d}</th>"
    w_table += "</tr>"

    for w_day in w_days:
        w_table += f"<tr><td style='font-weight:bold; border:1px solid #ddd; padding:6px;'>{w_day}</td>"
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
            w_table += f"<td style='background-color:{bg}; border:1px solid #ddd;'></td>"
        w_table += "</tr>"
    w_table += "</table>"
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
