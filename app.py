import streamlit as st
import calendar
import random
import string
import threading
from datetime import datetime
from supabase import create_client, Client

# ────────────────────────────────────────────────
# Supabase 설정
# Streamlit Cloud 사용 시: .streamlit/secrets.toml 에 아래 추가
#   SUPABASE_URL = "https://xxxx.supabase.co"
#   SUPABASE_KEY = "eyJ..."
# 로컬 사용 시: 아래 두 줄에 직접 입력 가능
# ────────────────────────────────────────────────
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

@st.cache_resource
def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = get_supabase()

# ────────────────────────────────────────────────
# 페이지 기본 설정
# ────────────────────────────────────────────────
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


# ════════════════════════════════════════════════
# Supabase DB 헬퍼 함수
# ════════════════════════════════════════════════

def db_get_user_events(user_id: str):
    """유저의 개인 일정 목록 조회"""
    try:
        res = supabase.table("events").select("*").eq("user_id", user_id).execute()
        return res.data or []
    except Exception:
        return []

def db_save_event(user_id: str, event: dict):
    """개인 일정 저장 (upsert)"""
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

def db_delete_event(event_id: str):
    """개인 일정 삭제"""
    try:
        supabase.table("events").delete().eq("id", event_id).execute()
    except Exception as e:
        st.error(f"일정 삭제 오류: {e}")

def db_get_timetable(user_id: str):
    """고정 시간표 조회"""
    try:
        res = supabase.table("timetable").select("*").eq("user_id", user_id).execute()
        return res.data or []
    except Exception:
        return []

def db_save_timetable_entry(user_id: str, entry: dict):
    """고정 시간표 항목 저장"""
    try:
        payload = {
            "user_id": user_id,
            "title": entry["title"],
            "day": entry["day"],
            "start_time": entry["start"],
            "end_time": entry["end"],
            "color": entry.get("color", get_random_color()),
        }
        supabase.table("timetable").insert(payload).execute()
    except Exception as e:
        st.error(f"시간표 저장 오류: {e}")

def db_delete_timetable_entry(entry_id: str):
    """고정 시간표 항목 삭제"""
    try:
        supabase.table("timetable").delete().eq("id", entry_id).execute()
    except Exception as e:
        st.error(f"시간표 삭제 오류: {e}")

def db_get_rooms(user_id: str):
    """내가 참여한 방 목록 조회"""
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
            rooms[code] = {
                "name": row["rooms"]["name"],
                "my_nickname": row["nickname"],
            }
        return rooms
    except Exception:
        return {}

def db_create_room(user_id: str, room_name: str, nickname: str) -> str:
    """방 생성 후 코드 반환"""
    try:
        while True:
            code = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
            existing = supabase.table("rooms").select("code").eq("code", code).execute()
            if not existing.data:
                break
        supabase.table("rooms").insert({"code": code, "name": room_name}).execute()
        supabase.table("room_members").insert({
            "room_code": code,
            "user_id": user_id,
            "nickname": nickname,
        }).execute()
        return code
    except Exception as e:
        st.error(f"방 생성 오류: {e}")
        return ""

def db_join_room(user_id: str, room_code: str, nickname: str) -> bool:
    """방 입장"""
    try:
        room = supabase.table("rooms").select("code").eq("code", room_code).execute()
        if not room.data:
            return False
        # 이미 참여 중인지 확인
        existing = (
            supabase.table("room_members")
            .select("id")
            .eq("room_code", room_code)
            .eq("user_id", user_id)
            .execute()
        )
        if not existing.data:
            supabase.table("room_members").insert({
                "room_code": room_code,
                "user_id": user_id,
                "nickname": nickname,
            }).execute()
        return True
    except Exception as e:
        st.error(f"방 입장 오류: {e}")
        return False

def db_get_room_members(room_code: str):
    """방의 모든 멤버와 그들의 일정/시간표 조회"""
    try:
        members_res = (
            supabase.table("room_members")
            .select("user_id, nickname")
            .eq("room_code", room_code)
            .execute()
        )
        members = {}
        for m in (members_res.data or []):
            uid = m["user_id"]
            nick = m["nickname"]
            events_raw = db_get_user_events(uid)
            timetable_raw = db_get_timetable(uid)
            members[nick] = {
                "events": [
                    {"title": e["title"], "start": e["start_dt"],
                     "end": e["end_dt"], "color": e.get("color", "")}
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

def db_get_room_info(room_code: str):
    """방 기본 정보 조회"""
    try:
        res = supabase.table("rooms").select("name").eq("code", room_code).execute()
        if res.data:
            return res.data[0]
        return None
    except Exception:
        return None


# ════════════════════════════════════════════════
# 세션 상태 초기화
# ════════════════════════════════════════════════
def init_session():
    defaults = {
        "app_page": "LOGIN",
        "cal_linked": None,
        "my_events": [],          # DB에서 불러온 리스트 (dict with id, title, start, end, color)
        "my_timetable": [],       # DB에서 불러온 리스트
        "current_group_code": None,
        "my_nickname": "",
        "editing_event_idx": None,
        "active_add_day": None,
        "fixed_expander_open": False,
        "my_joined_rooms": {},    # {code: {name, my_nickname}}
        "user_id": None,
        "user_email": None,
        "data_loaded": False,     # 로그인 후 DB 데이터 1회 로드 여부
        "run_match": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session()


def load_user_data():
    """로그인 직후 DB에서 사용자 데이터를 세션으로 불러오기"""
    if st.session_state.data_loaded:
        return
    uid = st.session_state.user_id
    if not uid:
        return
    events_raw = db_get_user_events(uid)
    st.session_state.my_events = [
        {
            "id": e["id"],
            "title": e["title"],
            "start": e["start_dt"],
            "end": e["end_dt"],
            "color": e.get("color", get_random_color()),
        }
        for e in events_raw
    ]
    timetable_raw = db_get_timetable(uid)
    st.session_state.my_timetable = [
        {
            "id": t["id"],
            "title": t["title"],
            "day": t["day"],
            "start": t["start_time"],
            "end": t["end_time"],
            "color": t.get("color", get_random_color()),
        }
        for t in timetable_raw
    ]
    st.session_state.my_joined_rooms = db_get_rooms(uid)
    st.session_state.data_loaded = True


# ════════════════════════════════════════════════
# 0. 로그인 / 회원가입 페이지
# ════════════════════════════════════════════════
def page_login():
    st.title("🤝 When We Meet")
    st.subheader("로그인 또는 회원가입")

    tab_login, tab_signup = st.tabs(["🔐 로그인", "📝 회원가입"])

    with tab_login:
        email = st.text_input("이메일", key="login_email")
        password = st.text_input("비밀번호", type="password", key="login_pw")
        if st.button("로그인", type="primary", use_container_width=True, key="btn_login"):
            if not email or not password:
                st.warning("이메일과 비밀번호를 모두 입력해주세요.")
            else:
                try:
                    res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    user = res.user
                    st.session_state.user_id = user.id
                    st.session_state.user_email = user.email
                    st.session_state.data_loaded = False
                    load_user_data()
                    st.session_state.app_page = "CAL_LINK" if st.session_state.cal_linked is None else "HOME"
                    st.rerun()
                except Exception as e:
                    st.error(f"로그인 실패: 이메일 또는 비밀번호를 확인해주세요.")

    with tab_signup:
        new_email = st.text_input("이메일", key="signup_email")
        new_pw = st.text_input("비밀번호 (6자 이상)", type="password", key="signup_pw")
        new_pw2 = st.text_input("비밀번호 확인", type="password", key="signup_pw2")
        if st.button("회원가입", type="primary", use_container_width=True, key="btn_signup"):
            if not new_email or not new_pw:
                st.warning("이메일과 비밀번호를 입력해주세요.")
            elif len(new_pw) < 6:
                st.warning("비밀번호는 6자 이상이어야 합니다.")
            elif new_pw != new_pw2:
                st.warning("비밀번호가 일치하지 않습니다.")
            else:
                try:
                    res = supabase.auth.sign_up({"email": new_email, "password": new_pw})
                    if res.user:
                        st.success("✅ 회원가입 완료! 이메일 인증 후 로그인해주세요.")
                        st.info("📧 가입하신 이메일로 인증 메일이 발송됐습니다. 확인 후 로그인하세요.")
                    else:
                        st.error("회원가입에 실패했습니다. 다시 시도해주세요.")
                except Exception as e:
                    st.error(f"회원가입 오류: {e}")


# ════════════════════════════════════════════════
# 1. 캘린더 연동 팝업
# ════════════════════════════════════════════════
def page_cal_link():
    st.markdown("### 🔔 캘린더 앱 연동")
    st.write("캘린더 앱과 연동하시겠습니까?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Yes", use_container_width=True):
            st.session_state.cal_linked = True
            st.session_state.app_page = "HOME"
            st.rerun()
    with c2:
        if st.button("No", use_container_width=True):
            st.session_state.cal_linked = False
            st.session_state.app_page = "HOME"
            st.rerun()


# ════════════════════════════════════════════════
# 2. 홈 화면
# ════════════════════════════════════════════════
def page_home():
    # 상단 우측: 로그아웃
    h1, h2 = st.columns([5, 1])
    with h2:
        st.caption(f"👤 {st.session_state.user_email}")
        if st.button("로그아웃", use_container_width=True):
            supabase.auth.sign_out()
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    with h1:
        st.title("🤝 When We Meet")

    now = datetime.now()
    st.subheader(f"📅 {now.year}년 {now.month}월")

    cal_matrix = calendar.monthcalendar(now.year, now.month)
    days = ["일", "월", "화", "수", "목", "금", "토"]

    cols = st.columns(7)
    for i, d in enumerate(days):
        cols[i].markdown(f"<center><b>{d}</b></center>", unsafe_allow_html=True)

    for week in cal_matrix:
        cols = st.columns(7)
        for idx, day_num in enumerate(week):
            if day_num != 0:
                if day_num == now.day:
                    cols[idx].markdown(
                        f"<div style='background-color:#E3F2FD; text-align:center; "
                        f"padding:10px; border-radius:5px; border:1px solid #2196F3; "
                        f"font-weight:bold;'>{day_num}<br><span style='color:blue; "
                        f"font-size:10px;'>Today</span></div>",
                        unsafe_allow_html=True
                    )
                else:
                    cols[idx].markdown(
                        f"<div style='background-color:white; text-align:center; "
                        f"padding:10px; border-radius:5px; border:1px solid #ddd;'>{day_num}</div>",
                        unsafe_allow_html=True
                    )
            else:
                cols[idx].write("")

    st.markdown("<br><br>", unsafe_allow_html=True)
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
# 3. 나의 일정 (개인 캘린더)
# ════════════════════════════════════════════════
def page_my_calendar():
    if "view_year" not in st.session_state:
        st.session_state.view_year = datetime.now().year
        st.session_state.view_month = datetime.now().month

    h_col1, h_col2 = st.columns([5, 1])
    with h_col2:
        if st.button("홈 화면으로 이동", use_container_width=True):
            st.session_state.app_page = "HOME"
            st.rerun()

    st.title("📆 나의 일정")

    n1, n2, n3 = st.columns([1, 4, 1])
    with n1:
        if st.button("<", use_container_width=True):
            st.session_state.view_month -= 1
            if st.session_state.view_month == 0:
                st.session_state.view_month = 12
                st.session_state.view_year -= 1
            st.rerun()
    with n2:
        st.markdown(
            f"<h3 style='text-align:center;'>{st.session_state.view_year}년 "
            f"{st.session_state.view_month}월</h3>",
            unsafe_allow_html=True
        )
    with n3:
        if st.button(">", use_container_width=True):
            st.session_state.view_month += 1
            if st.session_state.view_month == 13:
                st.session_state.view_month = 1
                st.session_state.view_year += 1
            st.rerun()

    cal_matrix = calendar.monthcalendar(st.session_state.view_year, st.session_state.view_month)
    days = ["일", "월", "화", "수", "목", "금", "토"]

    cols = st.columns(7)
    for i, d in enumerate(days):
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

                cell_html = (
                    f"<div style='min-height:80px; border:1px solid #ddd; "
                    f"padding:5px; border-radius:5px;'>"
                    f"<div style='font-weight:bold; font-size:14px;'>{day_num}</div>"
                )

                day_events = [
                    (i, ev) for i, ev in enumerate(st.session_state.my_events)
                    if ev["start"].split()[0] <= date_str <= ev["end"].split()[0]
                ]

                for ev_i, ev in day_events:
                    color = ev.get("color", "#FFCDD2")
                    s_time = ev["start"].split()[1] if " " in ev["start"] else ""
                    e_time = ev["end"].split()[1] if " " in ev["end"] else ""
                    cell_html += (
                        f"<div style='background-color:{color}; font-size:10px; "
                        f"margin-top:2px; border-radius:3px; padding:2px; color:#333;'>"
                        f"🕐 {s_time}~{e_time} {ev['title']}</div>"
                    )

                cell_html += "</div>"
                cols[idx].markdown(cell_html, unsafe_allow_html=True)

                if cols[idx].button(f"+ 추가", key=f"add_btn_{date_str}"):
                    st.session_state.active_add_day = day_num
                    st.session_state.editing_event_idx = None

                for ev_i, ev in day_events:
                    if cols[idx].button(
                        f"✏️ {ev['title'][:6]}",
                        key=f"edit_ev_{date_str}_{ev_i}"
                    ):
                        st.session_state.editing_event_idx = ev_i
                        st.session_state.active_add_day = None

            else:
                cols[idx].write("")

    # 일정 수정 폼
    ev_idx = st.session_state.editing_event_idx
    if ev_idx is not None and 0 <= ev_idx < len(st.session_state.my_events):
        ev = st.session_state.my_events[ev_idx]
        st.markdown("---")
        st.subheader("📋 일정 상세 / 수정")

        try:
            s_parts = ev["start"].split()
            e_parts = ev["end"].split()
            s_d = datetime.strptime(s_parts[0], "%Y-%m-%d").date()
            s_t = datetime.strptime(s_parts[1], "%H:%M").time()
            e_d = datetime.strptime(e_parts[0], "%Y-%m-%d").date()
            e_t = datetime.strptime(e_parts[1], "%H:%M").time()
        except Exception:
            s_d = datetime.now().date()
            s_t = datetime.strptime("09:00", "%H:%M").time()
            e_d = datetime.now().date()
            e_t = datetime.strptime("18:00", "%H:%M").time()

        st.info(f"📌 **{ev['title']}** | 시작: {ev['start']}  →  종료: {ev['end']}")

        with st.form("edit_event_form"):
            new_title = st.text_input("일정 제목", value=ev["title"])
            new_s_date = st.date_input("시작 날짜", value=s_d)
            new_s_time = st.time_input("시작 시간", value=s_t)
            new_e_date = st.date_input("종료 날짜", value=e_d)
            new_e_time = st.time_input("종료 시간", value=e_t)
            col_save, col_del, col_cancel = st.columns(3)
            with col_save:
                saved = st.form_submit_button("💾 저장")
            with col_del:
                deleted = st.form_submit_button("🗑️ 삭제")
            with col_cancel:
                cancelled = st.form_submit_button("✖ 취소")

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

    # 일정 추가 폼
    add_day = st.session_state.active_add_day
    if add_day:
        st.markdown("---")
        st.subheader(f"➕ {add_day}일 일정 추가")
        with st.form("event_form"):
            ev_title = st.text_input("일정 제목")
            s_date = st.date_input(
                "시작 날짜",
                value=datetime(st.session_state.view_year, st.session_state.view_month, add_day)
            )
            s_time = st.time_input("시작 시간", value=datetime.strptime("09:00", "%H:%M").time())
            e_date = st.date_input(
                "종료 날짜",
                value=datetime(st.session_state.view_year, st.session_state.view_month, add_day)
            )
            e_time = st.time_input("종료 시간", value=datetime.strptime("18:00", "%H:%M").time())

            if st.form_submit_button("저장"):
                new_ev = {
                    "title": ev_title,
                    "start": f"{s_date} {s_time.strftime('%H:%M')}",
                    "end": f"{e_date} {e_time.strftime('%H:%M')}",
                    "color": get_random_color(),
                }
                db_save_event(st.session_state.user_id, new_ev)
                # DB에서 id 포함해서 다시 불러오기
                st.session_state.data_loaded = False
                load_user_data()
                st.session_state.active_add_day = None
                st.rerun()

    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.button("⚙️ 고정 일정 섹션 (고정 시간표 페이지로 이동)", type="secondary", use_container_width=True):
        st.session_state.app_page = "FIXED_TIMETABLE"
        st.rerun()


# ════════════════════════════════════════════════
# 3-1. 고정 시간표
# ════════════════════════════════════════════════
def page_fixed_timetable():
    h_col1, h_col2 = st.columns([5, 1])
    with h_col2:
        if st.button("달력 보기", use_container_width=True):
            st.session_state.app_page = "MY_CALENDAR"
            st.rerun()

    st.title("🕞 고정 시간표 목록")

    with st.expander(
        "➕ 누르면 고정 일정 추가 창 열림",
        expanded=st.session_state.fixed_expander_open
    ):
        f_title = st.text_input("일정 제목", key="ft_title")
        f_day = st.selectbox("요일", ["월", "화", "수", "목", "금", "토", "일"], key="ft_day")
        f_start = st.text_input("시작 시각 (예: 09:15)", value="09:00", key="ft_start")
        f_end = st.text_input("종료 시각 (예: 11:45)", value="12:00", key="ft_end")

        if st.button("저장", key="ft_save", type="primary"):
            if f_title:
                entry = {
                    "title": f_title,
                    "day": f_day,
                    "start": f_start,
                    "end": f_end,
                    "color": get_random_color(),
                }
                db_save_timetable_entry(st.session_state.user_id, entry)
                st.session_state.fixed_expander_open = False
                # 다시 불러오기
                st.session_state.data_loaded = False
                load_user_data()
                st.rerun()
            else:
                st.warning("일정 제목을 입력해주세요.")

    if st.session_state.my_timetable:
        st.markdown("### 📋 등록된 고정 일정")
        for ti, t in enumerate(st.session_state.my_timetable):
            color = t.get("color", "#BBDEFB")
            col_a, col_b = st.columns([5, 1])
            with col_a:
                st.markdown(
                    f"<div style='background-color:{color}; padding:8px; border-radius:5px; "
                    f"margin-bottom:4px; color:#333;'>"
                    f"<b>{t['title']}</b> | {t['day']}요일 {t['start']} ~ {t['end']}</div>",
                    unsafe_allow_html=True
                )
            with col_b:
                if st.button("🗑️", key=f"del_tt_{ti}"):
                    if t.get("id"):
                        db_delete_timetable_entry(t["id"])
                    st.session_state.my_timetable.pop(ti)
                    st.rerun()

    st.write("### 📊 일주일 타임라인 도표 (15분 단위)")
    week_days_header = ["시간", "월", "화", "수", "목", "금", "토", "일"]

    table_html = (
        "<table style='width:100%; border-collapse:collapse; text-align:center; "
        "font-size:12px; border:1px solid #ddd;'>"
        "<tr style='background-color:#F5F5F5; font-weight:bold;'>"
    )
    for d in week_days_header:
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
                bg_color = "white"
                cell_text = ""
                for t in st.session_state.my_timetable:
                    if t["day"] == d_name and t["start"] <= time_str < t["end"]:
                        bg_color = t.get("color", "#BBDEFB")
                        cell_text = t["title"]
                table_html += (
                    f"<td style='border:1px solid #ddd; background-color:{bg_color}; "
                    f"color:#1565C0;'>{cell_text}</td>"
                )
            table_html += "</tr>"
    table_html += "</table>"
    st.markdown(table_html, unsafe_allow_html=True)


# ════════════════════════════════════════════════
# 4. 그룹 목록 및 가입
# ════════════════════════════════════════════════
def page_group_list():
    st.title("👥 그룹 방 관리 목록")
    if st.button("< 홈으로 이동"):
        st.session_state.app_page = "HOME"
        st.rerun()

    st.markdown("### ➕ 새로운 그룹 입장 제어 패널")
    g_action = st.radio(
        "작업을 선택하세요",
        ["선택 안 함", "새로운 그룹 만들기", "코드로 그룹 입장하기"],
        horizontal=True
    )

    if g_action == "새로운 그룹 만들기":
        g_name = st.text_input("새로운 그룹명 입력")
        nickname = st.text_input("내 닉네임 설정 입력")
        if st.button("방 생성 및 입장 완료 🚀"):
            if g_name and nickname:
                code = db_create_room(st.session_state.user_id, g_name, nickname)
                if code:
                    st.session_state.my_nickname = nickname
                    st.session_state.current_group_code = code
                    st.session_state.run_match = False
                    st.session_state.my_joined_rooms[code] = {"name": g_name, "my_nickname": nickname}
                    st.success(f"✅ 방 생성 완료! 친구에게 이 코드를 공유하세요: **`{code}`**")
                    st.session_state.app_page = "GROUP_ROOM"
                    st.rerun()
            else:
                st.warning("그룹명과 닉네임을 모두 입력해주세요.")

    elif g_action == "코드로 그룹 입장하기":
        join_code = st.text_input("고유 입장 코드 5자리 입력").strip().upper()
        nickname = st.text_input("내 닉네임 설정 입력")
        if st.button("해당 코드 방 입장하기 🚪"):
            if join_code and nickname:
                ok = db_join_room(st.session_state.user_id, join_code, nickname)
                if ok:
                    room_info = db_get_room_info(join_code)
                    st.session_state.my_nickname = nickname
                    st.session_state.current_group_code = join_code
                    st.session_state.run_match = False
                    st.session_state.my_joined_rooms[join_code] = {
                        "name": room_info["name"] if room_info else join_code,
                        "my_nickname": nickname,
                    }
                    st.session_state.app_page = "GROUP_ROOM"
                    st.rerun()
                else:
                    st.error("유효하지 않거나 존재하지 않는 코드입니다.")
            else:
                st.warning("코드와 닉네임을 모두 입력해주세요.")

    st.markdown("---")
    st.subheader("현재 참여 중인 방 리스트")
    my_rooms = st.session_state.my_joined_rooms
    if not my_rooms:
        st.caption("참여 중인 방이 없습니다. 상단에서 방을 새로 만들거나 코드를 입력하세요.")
    else:
        for c, info in my_rooms.items():
            col_r1, col_r2 = st.columns([4, 1])
            with col_r1:
                st.info(f"🏠 **{info['name']}** (코드: `{c}`) | 내 닉네임: {info['my_nickname']}")
            with col_r2:
                if st.button("입장", key=f"enter_room_{c}", use_container_width=True):
                    st.session_state.current_group_code = c
                    st.session_state.my_nickname = info["my_nickname"]
                    st.session_state.app_page = "GROUP_ROOM"
                    st.session_state.run_match = False
                    st.rerun()


# ════════════════════════════════════════════════
# 5. 그룹 방 화면
# ════════════════════════════════════════════════
def page_group_room():
    code = st.session_state.current_group_code
    room_info = db_get_room_info(code)

    if not room_info:
        st.error("방 정보를 찾을 수 없습니다.")
        if st.button("그룹 목록으로"):
            st.session_state.app_page = "GROUP_LIST"
            st.rerun()
        return

    # 멤버 및 일정 실시간 조회
    g_members = db_get_room_members(code)

    st.title(f"🏢 그룹 방: {room_info['name']}")

    c_hdr1, c_hdr2, c_hdr3 = st.columns([3, 1, 1])
    with c_hdr1:
        if st.button("👥 참여자 목록 확인"):
            st.write(
                f"현재 참여자 ({len(g_members)}명): "
                f"{', '.join(list(g_members.keys()))}"
            )
    with c_hdr2:
        st.warning(f"📋 코드: `{code}`")
    with c_hdr3:
        if st.button("< 그룹 목록"):
            st.session_state.app_page = "GROUP_LIST"
            st.rerun()

    st.subheader("📅 전체 달력 현황 뷰")
    now = datetime.now()
    last_day = calendar.monthrange(now.year, now.month)[1]

    st.markdown("### 🔍 약속 조율 일정 대조 옵션")
    col_in1, col_in2 = st.columns([2, 1])
    with col_in1:
        date_range = st.date_input(
            "조율할 시작일과 종료일",
            value=(datetime(now.year, now.month, 1), datetime(now.year, now.month, last_day))
        )
    with col_in2:
        min_h = st.number_input("최소 약속 시간 (시간)", min_value=1, max_value=24, value=2)

    if st.button("일정 대조하기 🚀", type="primary", use_container_width=True):
        st.session_state.run_match = True
        st.rerun()

    if not st.session_state.get("run_match", False):
        st.info("위의 버튼을 눌러 일정을 대조해보세요.")
        return

    if len(date_range) == 2:
        start_date_picked, end_date_picked = date_range[0], date_range[1]
    else:
        start_date_picked = datetime(now.year, now.month, 1).date()
        end_date_picked = datetime(now.year, now.month, last_day).date()

    date_colors = {}
    free_slots_cache = {}

    for d in range(1, last_day + 1):
        curr_loop_date = datetime(now.year, now.month, d).date()
        if curr_loop_date < start_date_picked or curr_loop_date > end_date_picked:
            continue

        w_str = ["월", "화", "수", "목", "금", "토", "일"][curr_loop_date.weekday()]
        slots = [True] * 24

        for name, m_data in g_members.items():
            for t in m_data.get("timetable", []):
                if t["day"] == w_str:
                    try:
                        sh = int(t["start"].split(":")[0])
                        eh = int(t["end"].split(":")[0])
                        for h in range(sh, eh):
                            slots[h] = False
                    except Exception:
                        pass
            for ev in m_data.get("events", []):
                d_str = f"{now.year}-{now.month:02d}-{d:02d}"
                if ev["start"].split()[0] <= d_str <= ev["end"].split()[0]:
                    try:
                        sh = int(ev["start"].split()[1].split(":")[0])
                        eh = int(ev["end"].split()[1].split(":")[0])
                        for h in range(sh, eh):
                            slots[h] = False
                    except Exception:
                        pass

        max_c, curr_c = 0, 0
        for s in slots:
            if s:
                curr_c += 1
                max_c = max(max_c, curr_c)
            else:
                curr_c = 0

        if max_c >= min_h:
            date_colors[d] = "green"
            free_slots_cache[d] = slots
        else:
            date_colors[d] = "red"
            free_slots_cache[d] = [False] * 24

    st.session_state.cached_slots = free_slots_cache
    st.session_state.cached_colors = date_colors

    colors = st.session_state.get("cached_colors", {})
    cal_matrix = calendar.monthcalendar(now.year, now.month)
    cols = st.columns(7)
    for i, d in enumerate(["일", "월", "화", "수", "목", "금", "토"]):
        cols[i].markdown(f"<center><b>{d}</b></center>", unsafe_allow_html=True)

    for week in cal_matrix:
        cols = st.columns(7)
        for idx, d_num in enumerate(week):
            if d_num != 0:
                if d_num in colors:
                    bg = "#C8E6C9" if colors[d_num] == "green" else "#FFCDD2"
                else:
                    bg = "white"
                if cols[idx].button(f"{d_num}", key=f"g_day_{d_num}", use_container_width=True):
                    st.session_state.active_room_day = d_num
            else:
                cols[idx].write("")

    st.markdown("---")
    st.subheader("📊 일주일 시간표 뷰 (공통 빈 시간대)")
    w_days_list = ["월", "화", "수", "목", "금", "토", "일"]

    w_table = (
        "<table style='width:100%; text-align:center; font-size:11px; border-collapse:collapse;'>"
        "<tr style='background-color:#F5F5F5;'><th>요일/시간</th>"
    )
    for h in range(24):
        w_table += f"<th>{h:02d}</th>"
    w_table += "</tr>"

    for w_day in w_days_list:
        w_table += f"<tr><td style='font-weight:bold; border:1px solid #ddd; padding:5px;'>{w_day}</td>"
        for h in range(24):
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
            w_table += f"<td style='background-color:{bg}; border:1px solid #ddd; width:25px;'></td>"
        w_table += "</tr>"
    w_table += "</table>"
    st.markdown(w_table, unsafe_allow_html=True)

    if "active_room_day" in st.session_state:
        sel_d = st.session_state.active_room_day
        st.markdown("---")
        st.subheader(f"📍 {sel_d}일 상세 가용 분석막대")

        slots = st.session_state.get("cached_slots", {}).get(sel_d, [False] * 24)

        bar_html = """
<div style='width:100%; font-size:11px;'>
  <div style='display:flex; width:100%; height:40px; border:1px solid #aaa; margin-bottom:4px; box-sizing:border-box;'>
"""
        for s in slots:
            bg = "#4CAF50" if s else "#F44336"
            bar_html += f"<div style='flex:1; background-color:{bg}; border-right:1px solid white;'></div>"
        bar_html += "  </div>\n"

        bar_html += "  <div style='display:flex; width:100%; box-sizing:border-box;'>\n"
        for h in range(24):
            label = str(h) if h % 3 == 0 else ""
            bar_html += (
                f"<div style='flex:1; text-align:center; color:#555; "
                f"border-left:1px solid #ccc; line-height:1;'>{label}</div>\n"
            )
        bar_html += "  </div>\n</div>"

        st.markdown(bar_html, unsafe_allow_html=True)

        st.write("##### **시간 선택 버튼**")
        avail_hours = [h for h in range(24) if slots[h]]
        if avail_hours:
            btn_cols = st.columns(6)
            for idx, h in enumerate(avail_hours):
                if btn_cols[idx % 6].button(f"{h}:00", key=f"final_lock_{h}", use_container_width=True):
                    st.balloons()
                    st.success(f"🎉 약속 확정! [{sel_d}일 {h}:00]")
        else:
            st.error("해당 날짜에는 공통 가용 시간이 없습니다.")


# ════════════════════════════════════════════════
# 라우터
# ════════════════════════════════════════════════
page = st.session_state.app_page

if page == "LOGIN":
    page_login()
elif page == "CAL_LINK":
    page_cal_link()
elif page == "HOME":
    if not st.session_state.user_id:
        st.session_state.app_page = "LOGIN"
        st.rerun()
    load_user_data()
    page_home()
elif page == "MY_CALENDAR":
    if not st.session_state.user_id:
        st.session_state.app_page = "LOGIN"
        st.rerun()
    page_my_calendar()
elif page == "FIXED_TIMETABLE":
    if not st.session_state.user_id:
        st.session_state.app_page = "LOGIN"
        st.rerun()
    page_fixed_timetable()
elif page == "GROUP_LIST":
    if not st.session_state.user_id:
        st.session_state.app_page = "LOGIN"
        st.rerun()
    page_group_list()
elif page == "GROUP_ROOM":
    if not st.session_state.user_id:
        st.session_state.app_page = "LOGIN"
        st.rerun()
    page_group_room()
