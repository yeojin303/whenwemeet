import streamlit as st
import calendar
import random
import string
import hashlib
import threading
from datetime import datetime, date as date_type, timedelta
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

# ── 전역 CSS (모바일 최적화) ─────────────────────────────────────────────────
GLOBAL_CSS = """
<style>
/* 앱 전체 좌우 여백 최소화 */
.main .block-container {
    padding-left: 0.75rem !important;
    padding-right: 0.75rem !important;
    max-width: 100% !important;
}
/* 네비게이션 3-col 버튼 패딩 최소화 */
[data-testid="stHorizontalBlock"] [data-testid="column"] {
    padding-left: 2px !important;
    padding-right: 2px !important;
}
/* CSS Grid 달력 */
.wwm-cal {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 3px;
    width: 100%;
    box-sizing: border-box;
}
.wwm-hdr {
    text-align: center;
    font-size: 12px;
    font-weight: 700;
    padding: 5px 0;
}
.wwm-cell {
    text-align: center;
    border-radius: 6px;
    border: 1px solid #E0E0E0;
    padding: 4px 2px 5px;
    min-height: 62px;
    box-sizing: border-box;
    overflow: hidden;
    background: white;
}
.wwm-cell-sel {
    border: 2px solid #1976D2 !important;
    background: #EEF4FF !important;
}
.wwm-cell-today { background: #FFF9C4 !important; }
.wwm-dnum { font-size: 11px; font-weight: 700; display: block; }
.wwm-today-lbl { font-size: 7px; color: #1E88E5; display: block; }
.wwm-evbar {
    font-size: 8px; border-radius: 2px; padding: 1px 2px;
    margin-top: 2px; color: white;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.wwm-more { font-size: 8px; color: #999; margin-top: 1px; }
/* 그룹달력 */
.wwm-gcell {
    text-align: center; border-radius: 6px;
    padding: 6px 2px; min-height: 52px;
    box-sizing: border-box; overflow: hidden;
    font-size: 11px; font-weight: 700;
}
.wwm-gcell-in  { border: 1px solid; }
.wwm-gcell-out { background: #FAFAFA; border: 1px solid #eee; color: #bbb; }
.wwm-glbl { font-size: 8px; display: block; margin-top: 2px; }
</style>
"""

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
        # 예외 테이블이 DB에 있을 경우 함께 삭제 시도
        try:
            supabase.table("timetable_exceptions").delete().eq("user_id", user_id).execute()
        except Exception:
            pass
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

# 고정시간표 예외(휴강) 헬퍼 함수
def db_get_timetable_exceptions(user_id):
    try:
        res = supabase.table("timetable_exceptions").select("*").eq("user_id", user_id).execute()
        return res.data or []
    except Exception:
        return st.session_state.get("local_exceptions", {}).get(user_id, [])

def db_save_timetable_exception(user_id, exc):
    try:
        supabase.table("timetable_exceptions").insert({
            "user_id": user_id,
            "exception_date": exc["date"],
            "timetable_title": exc["title"]
        }).execute()
    except Exception:
        if "local_exceptions" not in st.session_state:
            st.session_state["local_exceptions"] = {}
        if user_id not in st.session_state["local_exceptions"]:
            st.session_state["local_exceptions"][user_id] = []
        st.session_state["local_exceptions"][user_id].append(exc)

def db_delete_timetable_exception(user_id, exc_idx):
    if "local_exceptions" in st.session_state and user_id in st.session_state["local_exceptions"]:
        try:
            st.session_state["local_exceptions"][user_id].pop(exc_idx)
        except Exception:
            pass

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
            exceptions_raw = db_get_timetable_exceptions(uid)
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
                "exceptions": [
                    {"date": ex.get("exception_date") or ex.get("date"), "title": ex["timetable_title"] or ex["title"]}
                    for ex in exceptions_raw
                ]
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
        "my_exceptions": [],
        "current_group_code": None,
        "my_nickname": "",
        "fixed_expander_open": False,
        "my_joined_rooms": {},
        "user_id": None,
        "username": None,
        "data_loaded": False,
        "confirm_delete_account": False,
        "view_year": datetime.now().year,
        "view_month": datetime.now().month,
        # 달력 선택된 날짜 (date 객체)
        "cal_selected_date": None,
        "cal_selected_ev_id": None,
        "cal_selected_ev_idx": None,
        # 그룹 달력
        "grp_date_colors": None,
        "grp_free_slots": None,
        "grp_selected_day": None,
        "grp_start_d": None,
        "grp_end_d": None,
        "grp_time_start": 9,
        "grp_time_end": 21,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session()
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


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
    st.session_state.my_exceptions = db_get_timetable_exceptions(uid)
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
# 공통 헤더
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
# HTML 달력 빌더 (순수 CSS Grid – 버튼 없음)
# ════════════════════════════════════════════════
def build_calendar_html(year, month, events, selected_date_str=None, exceptions=None):
    """
    순수 HTML/CSS Grid 달력을 반환한다.
    events: [{"start": "YYYY-MM-DD HH:MM", "end": ..., "title": ..., "color": ...}, ...]
    selected_date_str: "YYYY-MM-DD" or None
    """
    today = datetime.now()
    cal_matrix = calendar.monthcalendar(year, month)

    day_names   = ["일", "월", "화", "수", "목", "금", "토"]
    hdr_colors  = ["#E53935","#555","#555","#555","#555","#555","#1565C0"]

    html = '<div class="wwm-cal">'

    # 요일 헤더
    for i, dn in enumerate(day_names):
        html += f'<div class="wwm-hdr" style="color:{hdr_colors[i]};">{dn}</div>'

    for week in cal_matrix:
        for col_idx, day_num in enumerate(week):
            if day_num == 0:
                html += '<div></div>'
                continue

            date_str  = f"{year}-{month:02d}-{day_num:02d}"
            is_today  = (day_num == today.day and month == today.month and year == today.year)
            is_sel    = (selected_date_str == date_str)
            is_sun    = (col_idx == 0)
            is_sat    = (col_idx == 6)

            num_color = "#E53935" if is_sun else ("#1565C0" if is_sat else "#212121")

            cls = "wwm-cell"
            if is_sel:
                cls += " wwm-cell-sel"
            elif is_today:
                cls += " wwm-cell-today"

            day_events = [
                ev for ev in events
                if ev["start"].split()[0] <= date_str <= ev["end"].split()[0]
            ]

            # 해당 날짜에 휴강(예외) 일정이 있는지 체크하여 추가
            if exceptions:
                for exc in exceptions:
                    exc_date = exc.get("exception_date") or exc.get("date")
                    exc_title = exc.get("timetable_title") or exc.get("title")
                    if exc_date == date_str:
                        day_events.append({
                            "title": f"[휴강] {exc_title}",
                            "start": f"{date_str} 00:00",
                            "end": f"{date_str} 23:59",
                            "color": "#9E9E9E"
                        })

            bars = ""
            for ev in day_events[:2]:
                c = ev.get("color", "#4D96FF")
                t_s = ev["title"][:4] + ("…" if len(ev["title"]) > 4 else "")
                bars += f'<div class="wwm-evbar" style="background:{c};">{t_s}</div>'
            if len(day_events) > 2:
                bars += f'<div class="wwm-more">+{len(day_events)-2}</div>'

            today_lbl = '<span class="wwm-today-lbl">Today</span>' if is_today else ""
            sel_ring  = ""  # 요청에 의해 당일 날짜의 태양 이모지 '🌞 ' 삭제됨

            html += (
                f'<div class="{cls}">'
                f'<span class="wwm-dnum" style="color:{num_color};">{sel_ring}{day_num}</span>'
                f'{today_lbl}{bars}'
                f'</div>'
            )

    html += '</div>'
    return html


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
                    st.session_state.user_id   = user["id"]
                    st.session_state.username  = user["username"]
                    st.session_state.data_loaded = False
                    load_user_data()
                    st.session_state.app_page  = "HOME"
                    st.rerun()

    with tab_signup:
        new_id  = st.text_input("아이디 (4자 이상)", key="signup_id")
        new_pw  = st.text_input("비밀번호 (6자 이상)", type="password", key="signup_pw")
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
        cur_pw  = st.text_input("현재 비밀번호", type="password")
        new_pw  = st.text_input("새 비밀번호 (6자 이상)", type="password")
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

    # 홈 달력: 순수 HTML CSS Grid
    cal_html = build_calendar_html(now.year, now.month, [], None, st.session_state.get("my_exceptions", []))
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
# 나의 일정 – 모바일 최적화 버전
# ════════════════════════════════════════════════
def page_my_calendar():
    h1, h2 = st.columns([5, 2])
    with h2:
        if st.button("홈으로", use_container_width=True):
            st.session_state.app_page = "HOME"
            st.session_state.cal_selected_date = None
            st.rerun()
    with h1:
        st.title("📆 나의 일정")

    # ── 월 네비게이션 (3-col 은 모바일도 OK) ──
    n1, n2, n3 = st.columns([1, 4, 1])
    with n1:
        if st.button("‹", use_container_width=True):
            st.session_state.view_month -= 1
            if st.session_state.view_month == 0:
                st.session_state.view_month = 12
                st.session_state.view_year -= 1
            st.session_state.cal_selected_date  = None
            st.session_state.cal_selected_ev_id  = None
            st.session_state.cal_selected_ev_idx = None
            st.rerun()
    with n2:
        st.markdown(
            f"<h4 style='text-align:center;margin:0;'>"
            f"{st.session_state.view_year}년 {st.session_state.view_month}월</h4>",
            unsafe_allow_html=True
        )
    with n3:
        if st.button("›", use_container_width=True):
            st.session_state.view_month += 1
            if st.session_state.view_month == 13:
                st.session_state.view_month = 1
                st.session_state.view_year += 1
            st.session_state.cal_selected_date  = None
            st.session_state.cal_selected_ev_id  = None
            st.session_state.cal_selected_ev_idx = None
            st.rerun()

    cur_year  = st.session_state.view_year
    cur_month = st.session_state.view_month

    # 선택된 날짜 문자열
    sel_date_obj = st.session_state.cal_selected_date
    sel_date_str = sel_date_obj.strftime("%Y-%m-%d") if sel_date_obj else None
    # 현재 월이 아니면 선택 초기화
    if sel_date_obj and (sel_date_obj.year != cur_year or sel_date_obj.month != cur_month):
        sel_date_str = None
        st.session_state.cal_selected_date = None

    # ── 순수 HTML CSS Grid 달력 렌더링 ──
    cal_html = build_calendar_html(cur_year, cur_month, st.session_state.my_events, sel_date_str, st.session_state.get("my_exceptions", []))
    st.markdown(cal_html, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 날짜 선택 위젯 (모바일 네이티브 UI) ──
    st.markdown("**📌 날짜를 선택하면 일정을 확인·추가할 수 있어요**")
    picked = st.date_input(
        "날짜 선택",
        value=sel_date_obj if sel_date_obj else date_type(cur_year, cur_month, 1),
        key="cal_date_picker",
        label_visibility="collapsed",
    )
    if isinstance(picked, date_type):
        if picked != st.session_state.cal_selected_date:
            st.session_state.cal_selected_date  = picked
            st.session_state.cal_selected_ev_id  = None
            st.session_state.cal_selected_ev_idx = None
            # 뷰 월 동기화
            st.session_state.view_year  = picked.year
            st.session_state.view_month = picked.month
            st.rerun()

    # ── 선택된 날짜의 상세 패널 ──
    if st.session_state.cal_selected_date:
        active_date = st.session_state.cal_selected_date
        active_str  = active_date.strftime("%Y-%m-%d")

        day_events_sel = [
            (i, ev) for i, ev in enumerate(st.session_state.my_events)
            if ev["start"].split()[0] <= active_str <= ev["end"].split()[0]
        ]
        
        # 하단 바 예외일정 표시용 리스트업
        for exc in st.session_state.get("my_exceptions", []):
            exc_date = exc.get("exception_date") or exc.get("date")
            exc_title = exc.get("timetable_title") or exc.get("title")
            if exc_date == active_str:
                day_events_sel.append((-1, {
                    "title": f"[휴강] {exc_title}",
                    "start": f"{active_str} 00:00",
                    "end": f"{active_str} 23:59",
                    "color": "#9E9E9E"
                }))

        st.markdown("---")
        hc1, hc2 = st.columns([5, 1])
        with hc1:
            st.markdown(f"#### 📅 {active_date.year}년 {active_date.month}월 {active_date.day}일")
        with hc2:
            if st.button("✖", key="close_day_panel"):
                st.session_state.cal_selected_date  = None
                st.session_state.cal_selected_ev_id  = None
                st.session_state.cal_selected_ev_idx = None
                st.rerun()

        # 이 날 일정 목록
        if day_events_sel:
            st.markdown("**이 날 일정:**")
            for ev_i, ev in day_events_sel:
                color   = ev.get("color", "#4D96FF")
                s_t     = ev["start"].split()[1] if " " in ev["start"] else ""
                e_t     = ev["end"].split()[1]   if " " in ev["end"]   else ""
                ev_id   = ev.get("id") or f"idx_{ev_i}"
                is_sel  = (st.session_state.cal_selected_ev_id == ev_id)

                r_int = int(color[1:3], 16)
                g_int = int(color[3:5], 16)
                b_int = int(color[5:7], 16)
                bg_s  = f"rgba({r_int},{g_int},{b_int},{0.22 if is_sel else 0.10})"
                bdr_c = "#1976D2" if is_sel else color

                col_bar, col_btn = st.columns([6, 1])
                with col_bar:
                    st.markdown(
                        f"<div style='background:{bg_s};border-left:4px solid {bdr_c};"
                        f"border-radius:0 8px 8px 0;padding:8px 12px;margin-bottom:4px;'>"
                        f"<div style='font-weight:700;font-size:14px;color:{color};'>{ev['title']}</div>"
                        f"<div style='font-size:12px;color:#555;margin-top:2px;'>🕐 {s_t} ~ {e_t}</div>"
                        f"</div>",
                        unsafe_allow_html=True
                    )
                with col_btn:
                    if ev_i == -1:
                        st.write("")
                    else:
                        lbl = "✖" if is_sel else "···"
                        if st.button(lbl, key=f"sel_ev_{ev_id}", use_container_width=True):
                            if is_sel:
                                st.session_state.cal_selected_ev_id  = None
                                st.session_state.cal_selected_ev_idx = None
                            else:
                                st.session_state.cal_selected_ev_id  = ev_id
                                st.session_state.cal_selected_ev_idx = ev_i
                            st.rerun()

                # 편집 폼 (선택된 이벤트)
                if is_sel and ev_i != -1:
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
                        new_title  = st.text_input("일정 제목", value=ev["title"])
                        c1, c2     = st.columns(2)
                        new_s_date = c1.date_input("시작 날짜", value=s_d_obj)
                        new_s_time = c2.time_input("시작 시간", value=s_t_obj)
                        c3, c4     = st.columns(2)
                        new_e_date = c3.date_input("종료 날짜", value=e_d_obj)
                        new_e_time = c4.time_input("종료 시간", value=e_t_obj)
                        col_save, col_del, col_cancel = st.columns(3)
                        saved     = col_save.form_submit_button("💾 저장",   use_container_width=True)
                        deleted   = col_del.form_submit_button("🗑️ 삭제",  use_container_width=True)
                        cancelled = col_cancel.form_submit_button("✖ 닫기", use_container_width=True)

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
                        st.session_state.cal_selected_ev_id  = None
                        st.session_state.cal_selected_ev_idx = None
                        st.rerun()
                    elif deleted:
                        if ev.get("id"):
                            db_delete_event(ev["id"])
                        st.session_state.my_events.pop(ev_i)
                        st.session_state.cal_selected_ev_id  = None
                        st.session_state.cal_selected_ev_idx = None
                        st.rerun()
                    elif cancelled:
                        st.session_state.cal_selected_ev_id  = None
                        st.session_state.cal_selected_ev_idx = None
                        st.rerun()

        # 새 일정 추가 폼
        st.markdown(f"**➕ {active_date.day}일 새 일정 추가**")
        with st.form("event_form"):
            ev_title = st.text_input("일정 제목")
            c1, c2   = st.columns(2)
            s_date   = c1.date_input("시작 날짜", value=active_date)
            s_time   = c2.time_input("시작 시간", value=datetime.strptime("09:00", "%H:%M").time())
            c3, c4   = st.columns(2)
            e_date   = c3.date_input("종료 날짜", value=active_date)
            e_time   = c4.time_input("종료 시간", value=datetime.strptime("18:00", "%H:%M").time())
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
                st.session_state.cal_selected_date = None
                st.rerun()
        elif do_cancel:
            st.session_state.cal_selected_date = None
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("⚙️ 고정 시간표 관리", type="secondary", use_container_width=True):
        st.session_state.app_page = "FIXED_TIMETABLE"
        st.rerun()


# ════════════════════════════════════════════════
# 고정 시간표
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
        f_day   = st.selectbox("요일", ["월","화","수","목","금","토","일"], key="ft_day")
        f_start = st.text_input("시작 시각 (예: 09:00)", value="09:00", key="ft_start")
        f_end   = st.text_input("종료 시각 (예: 12:00)", value="12:00", key="ft_end")
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

    # ── 휴강 / 고정일정 예외 등록 창 생성 ──
    st.markdown("---")
    with st.expander("⚠️ 고정 일정 예외 등록 (휴강 등)"):
        if not st.session_state.my_timetable:
            st.caption("먼저 고정 일정을 등록해주세요.")
        else:
            titles_list = list(set([t["title"] for t in st.session_state.my_timetable]))
            exc_title = st.selectbox("예외 대상 일정 선택", titles_list)
            exc_date = st.date_input("예외 적용 날짜 (휴강일)")
            if st.button("예외 등록하기", type="warning", use_container_width=True):
                db_save_timetable_exception(st.session_state.user_id, {
                    "date": exc_date.strftime("%Y-%m-%d"),
                    "title": exc_title
                })
                st.session_state.data_loaded = False
                load_user_data()
                st.success("✅ 예외 일정이 등록되었습니다. 그룹 대조 시 해당 시간은 빈 시간으로 계산됩니다.")
                st.rerun()

    if st.session_state.get("my_exceptions"):
        st.markdown("##### 📋 등록된 예외 목록 (휴강)")
        for ex_idx, ex in enumerate(st.session_state.my_exceptions):
            exc_date = ex.get("exception_date") or ex.get("date")
            exc_title = ex.get("timetable_title") or ex.get("title")
            ex_c1, ex_c2 = st.columns([5, 2])
            with ex_c1:
                st.caption(f"🗓️ {exc_date} | **{exc_title}** (제외됨)")
            with ex_c2:
                if st.button("삭제", key=f"del_ex_{ex_idx}", use_container_width=True):
                    db_delete_timetable_exception(st.session_state.user_id, ex_idx)
                    st.session_state.data_loaded = False
                    load_user_data()
                    st.rerun()

    st.markdown("---")
    if st.session_state.my_timetable:
        st.markdown("### 📋 등록된 고정 일정")
        for ti, t in enumerate(st.session_state.my_timetable):
            col_a, col_b = st.columns([5, 2])
            with col_a:
                st.markdown(
                    f"<div style='background-color:{t.get('color','#BBDEFB')};padding:8px;"
                    f"border-radius:5px;margin-bottom:4px;color:#333;font-size:12px;'>"
                    f"<b>{t['title']}</b> | {t['day']}요일 {t['start']} ~ {t['end']}</div>",
                    unsafe_allow_html=True
                )
            with col_b:
                if st.button("🗑️", key=f"del_tt_{ti}", use_container_width=True):
                    if t.get("id"):
                        db_delete_timetable_entry(t["id"])
                    st.session_state.my_timetable.pop(ti)
                    st.rerun()

    st.write("### 📊 일주일 타임라인 (15분 단위)")
    table_html = (
        "<div style='overflow-x:auto;-webkit-overflow-scrolling:touch;'>"
        "<table style='width:100%;min-width:600px;table-layout:fixed;border-collapse:collapse;"
        "text-align:center;font-size:11px;border:1px solid #ddd;word-break:break-all;'>"
        "<tr style='background-color:#F5F5F5;font-weight:bold;'>"
    )
    for d in ["시간","월","화","수","목","금","토","일"]:
        table_html += f"<th style='border:1px solid #ddd;padding:6px;'>{d}</th>"
    table_html += "</tr>"
    for hour in range(24):
        for minute in [0, 15, 30, 45]:
            time_str   = f"{hour:02d}:{minute:02d}"
            table_html += (
                f"<tr><td style='border:1px solid #ddd;background-color:#FAFAFA;"
                f"font-weight:bold;padding:4px;'>{time_str}</td>"
            )
            for d_name in ["월","화","수","목","금","토","일"]:
                bg, text = "white", ""
                for t in st.session_state.my_timetable:
                    if t["day"] == d_name and t["start"] <= time_str < t["end"]:
                        bg, text = t.get("color","#BBDEFB"), t["title"]
                table_html += (
                    f"<td style='border:1px solid #ddd;background-color:{bg};"
                    f"color:#1565C0;padding:2px;'>{text[:4]}</td>"
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
        "작업 선택", ["선택 안 함","새로운 그룹 만들기","코드로 그룹 입장하기"], horizontal=True
    )

    if g_action == "새로운 그룹 만들기":
        g_name   = st.text_input("그룹명")
        nickname = st.text_input("내 닉네임")
        if st.button("방 생성 🚀", use_container_width=True):
            if g_name and nickname:
                code = db_create_room(st.session_state.user_id, g_name, nickname)
                if code:
                    st.session_state.my_nickname          = nickname
                    st.session_state.current_group_code   = code
                    st.session_state.my_joined_rooms[code] = {"name": g_name, "my_nickname": nickname}
                    st.success(f"✅ 방 코드: **`{code}`** 를 친구에게 공유하세요!")
                    st.session_state.app_page = "GROUP_ROOM"
                    st.rerun()
            else:
                st.warning("그룹명과 닉네임을 입력해주세요.")

    elif g_action == "코드로 그룹 입장하기":
        join_code = st.text_input("입장 코드 5자리").strip().upper()
        nickname  = st.text_input("내 닉네임")
        if st.button("입장 🚪", use_container_width=True):
            if join_code and nickname:
                if db_join_room(st.session_state.user_id, join_code, nickname):
                    room_info = db_get_room_info(join_code)
                    st.session_state.my_nickname         = nickname
                    st.session_state.current_group_code  = join_code
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
                    st.session_state.my_nickname        = info["my_nickname"]
                    st.session_state.app_page = "GROUP_ROOM"
                    st.rerun()


# ════════════════════════════════════════════════
# 그룹 방 – 모바일 최적화 버전
# ════════════════════════════════════════════════
def slot_to_time(i):
    return f"{i // 4:02d}:{(i % 4) * 15:02d}"

def compute_free_slots(g_members, year, month, day, time_start_h, time_end_h):
    curr_date = date_type(year, month, day)
    w_str = ["월","화","수","목","금","토","일"][curr_date.weekday()]
    d_str = f"{year}-{month:02d}-{day:02d}"

    SLOTS = 96
    slots = [False] * SLOTS
    for i in range(time_start_h * 4, time_end_h * 4):
        slots[i] = True

    for name, m_data in g_members.items():
        # 해당 유저가 오늘 날짜에 가지고 있는 예외(휴강) 리스트 추출
        user_exceptions = [ex["title"] for ex in m_data.get("exceptions", []) if ex["date"] == d_str]
        
        for t in m_data.get("timetable", []):
            if t["day"] == w_str:
                # 만약 예외(휴강) 처리된 시간표 제목 리스트에 포함되어 있다면, 점유 대상에서 스킵하여 빈 시간으로 둠
                if t["title"] in user_exceptions:
                    continue
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


def build_group_calendar_html(year, month, start_d, end_d, date_colors, selected_day_str=None):
    """그룹 결과 달력 – 순수 HTML CSS Grid"""
    cal_matrix = calendar.monthcalendar(year, month)
    day_names   = ["일","월","화","수","목","금","토"]
    hdr_colors  = ["#E53935","#555","#555","#555","#555","#555","#1565C0"]

    html = '<div class="wwm-cal">'
    for i, dn in enumerate(day_names):
        html += f'<div class="wwm-hdr" style="color:{hdr_colors[i]};">{dn}</div>'

    for week in cal_matrix:
        for col_idx, d_num in enumerate(week):
            if d_num == 0:
                html += '<div></div>'
                continue

            d_key  = f"{year}-{month:02d}-{d_num:02d}"
            d_date = date_type(year, month, d_num)
            in_range = start_d <= d_date <= end_d
            is_sun   = (col_idx == 0)
            is_sat   = (col_idx == 6)
            is_sel   = (selected_day_str == d_key)
            num_color = "#E53935" if is_sun else ("#1565C0" if is_sat else "#212121")

            if in_range:
                if date_colors.get(d_key, "red") == "green":
                    bg     = "#C8E6C9" if is_sel else "#E8F5E9"
                    border = f"{'2px' if is_sel else '1px'} solid {'#2E7D32' if is_sel else '#81C784'}"
                    lbl    = '<span class="wwm-glbl" style="color:#2E7D32;">🟢가능</span>'
                else:
                    bg     = "#FFCDD2" if is_sel else "#FFEBEE"
                    border = f"{'2px' if is_sel else '1px'} solid {'#B71C1C' if is_sel else '#E57373'}"
                    lbl    = '<span class="wwm-glbl" style="color:#C62828;">🔴불가</span>'
            else:
                bg, border = "#FAFAFA", "1px solid #eee"
                lbl = '<span class="wwm-glbl" style="color:#bbb;">⚪제외</span>'

            html += (
                f'<div class="wwm-gcell wwm-gcell-in" style="background:{bg};border:{border};">'
                f'<span style="font-size:11px;font-weight:700;color:{num_color};">{d_num}</span>'
                f'{lbl}</div>'
            )

    html += '</div>'
    return html


def page_group_room():
    code      = st.session_state.current_group_code
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
        st.warning(f"코드: `{code}`")
        if st.button("👥 참여자 보기", use_container_width=True):
            st.info(f"{len(g_members)}명: {', '.join(g_members.keys())}")
    with h1:
        st.title(f"🏢 {room_info['name']}")

    st.markdown("---")
    st.subheader("🔍 약속 가능 날짜 찾기")

    now      = datetime.now()
    last_day = calendar.monthrange(now.year, now.month)[1]

    col_d, col_m = st.columns(2)
    with col_d:
        date_range = st.date_input(
            "📅 날짜 범위",
            value=(date_type(now.year, now.month, 1),
                   date_type(now.year, now.month, last_day)),
            key="grp_date_range"
        )
    with col_m:
        min_h = st.number_input("⏱️ 최소 연속 가능 시간(시간)", min_value=1, max_value=12, value=2, key="grp_min_h")

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
            if isinstance(date_range, tuple) and len(date_range) == 2:
                start_d, end_d = date_range
            else:
                start_d = date_type(now.year, now.month, 1)
                end_d   = date_type(now.year, now.month, last_day)

            date_colors     = {}
            free_slots_cache = {}
            cur = start_d
            while cur <= end_d:
                slots = compute_free_slots(g_members, cur.year, cur.month, cur.day, time_start_h, time_end_h)
                max_c = curr_c = 0
                for i in range(time_start_h * 4, time_end_h * 4):
                    if slots[i]:
                        curr_c += 1; max_c = max(max_c, curr_c)
                    else:
                        curr_c = 0
                key = cur.strftime("%Y-%m-%d")
                date_colors[key]      = "green" if max_c >= min_h * 4 else "red"
                free_slots_cache[key] = slots
                cur += timedelta(days=1)

            st.session_state.grp_date_colors  = date_colors
            st.session_state.grp_free_slots   = free_slots_cache
            st.session_state.grp_selected_day = None
            st.session_state.grp_start_d      = start_d
            st.session_state.grp_end_d        = end_d
            st.session_state.grp_time_start   = time_start_h
            st.session_state.grp_time_end     = time_end_h
            st.rerun()

    if st.session_state.grp_date_colors is None:
        st.info("조건을 설정하고 '일정 대조하기' 버튼을 눌러보세요.")
        return

    colors  = st.session_state.grp_date_colors
    start_d = st.session_state.grp_start_d
    end_d   = st.session_state.grp_end_d
    t_start = st.session_state.grp_time_start
    t_end   = st.session_state.grp_time_end

    st.markdown("---")
    green_cnt = sum(1 for v in colors.values() if v == "green")
    red_cnt   = sum(1 for v in colors.values() if v == "red")
    mc1, mc2, mc3 = st.columns(3)
    mc1.metric("✅ 가용한 날",    f"{green_cnt}일")
    mc2.metric("❌ 불가능한 날",  f"{red_cnt}일")
    mc3.metric("👥 참여 인원",   f"{len(g_members)}명")

    st.markdown("### 📅 일정 대조 달력")
    st.markdown(
        "<div style='font-size:12px;margin-bottom:8px;color:#555;'>"
        "🟢 가능 | 🔴 불가 | ⚪ 범위 외</div>", unsafe_allow_html=True
    )

    # ── 월별 CSS Grid 달력 렌더링 ──
    render_year, render_month = start_d.year, start_d.month
    end_year, end_month       = end_d.year, end_d.month

    sel_day = st.session_state.grp_selected_day

    while (render_year, render_month) <= (end_year, end_month):
        st.markdown(f"##### 📅 {render_year}년 {render_month}월")

        gcal_html = build_group_calendar_html(
            render_year, render_month, start_d, end_d, colors, sel_day
        )
        st.markdown(gcal_html, unsafe_allow_html=True)

        render_month += 1
        if render_month > 12:
            render_month = 1
            render_year += 1

    # ── 날짜 선택 (모바일 네이티브) ──
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("**📌 날짜를 선택하면 가능 시간대를 분석해요**")

    green_days = sorted([k for k, v in colors.items() if v == "green"])
    all_days   = sorted(colors.keys())

    if green_days:
        default_sel = date_type.fromisoformat(green_days[0])
    elif all_days:
        default_sel = date_type.fromisoformat(all_days[0])
    else:
        default_sel = start_d

    cur_sel_obj = (date_type.fromisoformat(sel_day)
                   if sel_day and sel_day in colors else default_sel)

    grp_picked = st.date_input(
        "날짜 선택",
        value=cur_sel_obj,
        min_value=start_d,
        max_value=end_d,
        key="grp_date_picker",
        label_visibility="collapsed",
    )
    if isinstance(grp_picked, date_type):
        new_sel = grp_picked.strftime("%Y-%m-%d")
        if new_sel != st.session_state.grp_selected_day:
            st.session_state.grp_selected_day = new_sel
            st.rerun()

    # ── 선택된 날짜 상세 분석 ──
    if sel_day and sel_day in colors:
        slots = st.session_state.grp_free_slots.get(sel_day, [False] * 96)
        sy, sm, sd = map(int, sel_day.split("-"))

        st.markdown("---")
        st.markdown(f"### 📊 {sy}년 {sm}월 {sd}일 분석")

        # 시간대 바 차트
        bar_rows = []
        for hour in range(24):
            cells = "".join(
                '<div style="background:{bg};flex:1;height:18px;border-radius:2px;margin:0 1px;"></div>'.format(
                    bg="#4CAF50" if (slots[hour*4+mi] if hour*4+mi < len(slots) else False) else "#F44336"
                )
                for mi in range(4)
            )
            bar_rows.append(
                '<div style="display:flex;align-items:center;gap:4px;margin-bottom:2px;">'
                f'<span style="font-size:10px;color:#555;min-width:34px;text-align:right;">{hour:02d}:00</span>'
                f'<div style="display:flex;flex:1;">{cells}</div>'
                '</div>'
            )
        bar_html = (
            '<div style="overflow-x:auto;-webkit-overflow-scrolling:touch;background:#fafafa;'
            'border:1px solid #ddd;border-radius:8px;padding:10px;margin-bottom:8px;">'
            + "".join(bar_rows) +
            '</div>'
            '<div style="font-size:11px;color:#555;margin-bottom:12px;">'
            '<span style="background:#4CAF50;padding:2px 8px;border-radius:3px;color:white;margin-right:8px;">가능</span>'
            '<span style="background:#F44336;padding:2px 8px;border-radius:3px;color:white;">불가</span>'
            '</div>'
        )
        st.markdown(bar_html, unsafe_allow_html=True)

        s_idx = t_start * 4
        e_idx = t_end   * 4
        avail_slots = [i for i in range(s_idx, e_idx) if i < len(slots) and slots[i]]

        if not avail_slots:
            st.error("선택하신 날짜에는 모든 멤버의 가용 시간대가 겹치지 않습니다.")
        else:
            ranges = []
            seg_s = seg_e = avail_slots[0]
            for i in avail_slots[1:]:
                if i == seg_e + 1:
                    seg_e = i
                else:
                    ranges.append((seg_s, seg_e + 1)); seg_s = seg_e = i
            ranges.append((seg_s, seg_e + 1))

            range_texts = [f"<b>{slot_to_time(rs)} ~ {slot_to_time(re)}</b>" for rs, re in ranges]
            st.markdown(
                "<div style='background:#E8F5E9;border:1px solid #388E3C;border-radius:8px;"
                "padding:12px;font-size:13px;color:#1B5E20;line-height:1.8;word-break:break-all;'>"
                "✅ 공통 가용 시간대:<br>" + " | ".join(range_texts) + "</div>",
                unsafe_allow_html=True
            )
            st.markdown("<br>", unsafe_allow_html=True)

            st.markdown("##### ⏰ 시간 직접 설정하여 확정하기")
            time_options = [f"{h:02d}:{m:02d}" for h in range(24) for m in [0,15,30,45]]
            custom_start = st.selectbox("시작", options=time_options, index=time_options.index("12:00"), key=f"cstart_{sel_day}")
            custom_end   = st.selectbox("종료", options=time_options, index=time_options.index("14:00"), key=f"cend_{sel_day}")
            if st.button("🚀 커스텀 시간으로 약속 확정", use_container_width=True, type="primary", key=f"custom_confirm_{sel_day}"):
                if custom_start >= custom_end:
                    st.error("종료 시간은 시작 시간보다 늦어야 합니다.")
                else:
                    st.balloons()
                    st.success(f"🎉 약속 확정! {sy}년 {sm}월 {sd}일 {custom_start} - {custom_end}")

            st.markdown("---")
            st.markdown("##### ✨ 가용 시간대에서 바로 선택")
            for idx, (rs, re) in enumerate(ranges):
                duration_min = (re - rs) * 15
                dur_str = (f"{duration_min // 60}시간 {duration_min % 60}분"
                           if duration_min % 60 else f"{duration_min // 60}시간")
                if st.button(
                    f"👍 {slot_to_time(rs)} - {slot_to_time(re)} ({dur_str})",
                    key=f"confirm_{sel_day}_{rs}", use_container_width=True
                ):
                    st.balloons()
                    st.success(f"🎉 약속 확정! {sy}년 {sm}월 {sd}일 "
                               f"{slot_to_time(rs)} - {slot_to_time(re)}")

    # ── 요일별 공통 가용 시간표 ──
    st.markdown("---")
    st.subheader("📊 요일별 공통 가용 시간표")
    w_days      = ["월","화","수","목","금","토","일"]
    hours_range = list(range(t_start, t_end))

    w_table = (
        "<div style='overflow-x:auto;-webkit-overflow-scrolling:touch;'>"
        "<table style='width:100%;min-width:500px;table-layout:fixed;text-align:center;"
        "font-size:10px;border-collapse:collapse;border:1px solid #ddd;word-break:break-all;'>"
        "<tr style='background-color:#F5F5F5;'><th style='padding:6px;border:1px solid #ddd;'>요일/시간</th>"
    )
    for h in hours_range:
        w_table += f"<th style='border:1px solid #ddd;padding:2px;'>{h:02d}</th>"
    w_table += "</tr>"

    for w_day in w_days:
        w_table += f"<tr><td style='font-weight:bold;border:1px solid #ddd;padding:6px;'>{w_day}</td>"
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
    require_login(); page_my_calendar()
elif page == "FIXED_TIMETABLE":
    require_login(); page_fixed_timetable()
elif page == "GROUP_LIST":
    require_login(); page_group_list()
elif page == "GROUP_ROOM":
    require_login(); page_group_room()
