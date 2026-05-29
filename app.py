import streamlit as st
import calendar
import random
import string
import hashlibimport streamlit as st
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

DAY_ORDER = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}

# ── 전역 CSS (모바일 최적화) ─────────────────────────────────────────────────
GLOBAL_CSS = """
<style>
.main .block-container {
    padding-left: 0.75rem !important;
    padding-right: 0.75rem !important;
    max-width: 100% !important;
}
[data-testid="stHorizontalBlock"] [data-testid="column"] {
    padding-left: 2px !important;
    padding-right: 2px !important;
}
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
        payload = {
            "user_id": user_id,
            "title": entry["title"],
            "day": entry["day"],
            "start_time": entry["start"],
            "end_time": entry["end"],
            "color": entry.get("color", get_random_color()),
        }
        if entry.get("id"):
            supabase.table("timetable").update(payload).eq("id", entry["id"]).execute()
        else:
            supabase.table("timetable").insert(payload).execute()
    except Exception as e:
        st.error(f"시간표 저장 오류: {e}")

def db_delete_timetable_entry(entry_id):
    try:
        supabase.table("timetable_exceptions").delete().eq("timetable_id", entry_id).execute()
        supabase.table("timetable").delete().eq("id", entry_id).execute()
    except Exception as e:
        st.error(f"시간표 삭제 오류: {e}")

def db_check_exception_exists(timetable_id, exception_date):
    try:
        res = supabase.table("timetable_exceptions").select("id").eq("timetable_id", timetable_id).eq("exception_date", exception_date).execute()
        return len(res.data) > 0
    except Exception:
        return False

def db_save_timetable_exception(timetable_id, exception_date):
    try:
        res = supabase.table("timetable_exceptions").insert({
            "timetable_id": timetable_id,
            "exception_date": exception_date
        }).execute()
        return res.data, None
    except Exception as e:
        return None, str(e)

def db_delete_timetable_exception(timetable_id, exception_date):
    try:
        supabase.table("timetable_exceptions").delete().eq("timetable_id", timetable_id).eq("exception_date", exception_date).execute()
        return True
    except Exception as e:
        st.error(f"예외 삭제 오류: {e}")
        return False

def db_get_all_exceptions(user_id):
    try:
        res = supabase.table("timetable").select("id, title, start_time, end_time, color, timetable_exceptions(exception_date)").eq("user_id", user_id).execute()
        exceptions = []
        for row in (res.data or []):
            for exc in row.get("timetable_exceptions", []):
                exceptions.append({
                    "timetable_id": row["id"],
                    "title": f"[예외] {row['title']}",
                    "date": exc["exception_date"],
                    "start": f"{exc['exception_date']} {row['start_time']}",
                    "end": f"{exc['exception_date']} {row['end_time']}",
                    "color": row.get("color", "#E0E0E0")
                })
        return exceptions
    except Exception:
        return []

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
            
            tt_res = supabase.table("timetable").select("*, timetable_exceptions(exception_date)").eq("user_id", uid).execute()
            timetable_raw = tt_res.data or []
            
            members[nick] = {
                "events": [
                    {"title": e["title"], "start": e["start_dt"], "end": e["end_dt"]}
                    for e in events_raw
                ],
                "timetable": [
                    {
                        "id": t["id"], 
                        "title": t["title"], 
                        "day": t["day"],
                        "start": t["start_time"], 
                        "end": t["end_time"],
                        "exceptions": [ex["exception_date"] for ex in t.get("timetable_exceptions", [])]
                    }
                    for t in timetable_raw
                ],
            }
        return members
    except Exception as e:
        st.error(f"멤버 조회 오류: {e}")
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
        "my_exceptions": [],
        "my_timetable": [],
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
        "cal_selected_date": None,
        "cal_selected_ev_id": None,
        "cal_selected_ev_idx": None,
        "tt_selected_id": None,
        "grp_date_colors": None,
        "grp_free_slots": None,
        "grp_selected_day": None,
        "grp_start_d": None,
        "grp_end_d": None,
        "grp_time_start": 9,
        "grp_time_end": 21,
        "ft_success_msg": None 
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
    
    st.session_state.my_exceptions = db_get_all_exceptions(uid)
    
    raw_timetable = db_get_timetable(uid)
    sorted_timetable = sorted(
        raw_timetable,
        key=lambda x: (DAY_ORDER.get(x["day"], 7), x["start_time"])
    )
    st.session_state.my_timetable = [
        {"id": t["id"], "title": t["title"], "day": t["day"],
         "start": t["start_time"], "end": t["end_time"], "color": t.get("color", get_random_color())}
        for t in sorted_timetable
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
# HTML 달력 빌더
# ════════════════════════════════════════════════
def build_calendar_html(year, month, events, selected_date_str=None):
    today = datetime.now()
    cal_matrix = calendar.monthcalendar(year, month)

    day_names   = ["일", "월", "화", "수", "목", "금", "토"]
    hdr_colors  = ["#E53935","#555","#555","#555","#555","#555","#1565C0"]

    html = '<div class="wwm-cal">'

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
            
            # 달력 내부 바 렌더링 시 항상 시간 순서대로 정렬하도록 반영
            day_events = sorted(day_events, key=lambda x: x["start"])

            bars = ""
            for ev in day_events[:2]:
                c = ev.get("color", "#4D96FF")
                t_s = ev["title"][:4] + ("…" if len(ev["title"]) > 4 else "")
                bars += f'<div class="wwm-evbar" style="background:{c};">{t_s}</div>'
            if len(day_events) > 2:
                bars += f'<div class="wwm-more">+{len(day_events)-2}</div>'

            today_lbl = '<span class="wwm-today-lbl">Today</span>' if is_today else ""
            
            html += (
                f'<div class="{cls}">'
                f'<span class="wwm-dnum" style="color:{num_color};">{day_num}</span>'
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

    cal_html = build_calendar_html(now.year, now.month, [], None)
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
# 나의 일정
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

    sel_date_obj = st.session_state.cal_selected_date
    sel_date_str = sel_date_obj.strftime("%Y-%m-%d") if sel_date_obj else None
    if sel_date_obj and (sel_date_obj.year != cur_year or sel_date_obj.month != cur_month):
        sel_date_str = None
        st.session_state.cal_selected_date = None

    # 일반 일정과 고정 시간표 예외 일정을 합쳐서 캘린더 화면에 바(Bar)로 출력
    combined_display_events = st.session_state.my_events + st.session_state.my_exceptions
    cal_html = build_calendar_html(cur_year, cur_month, combined_display_events, sel_date_str)
    st.markdown(cal_html, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

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
            st.session_state.view_year  = picked.year
            st.session_state.view_month = picked.month
            st.rerun()

    if st.session_state.cal_selected_date:
        active_date = st.session_state.cal_selected_date
        active_str  = active_date.strftime("%Y-%m-%d")

        # 일반 일정 필터링
        day_events_sel = [
            ("event", i, ev) for i, ev in enumerate(st.session_state.my_events)
            if ev["start"].split()[0] <= active_str <= ev["end"].split()[0]
        ]
        
        # 고정 일정 예외 건 필터링 추가
        day_exceptions_sel = [
            ("exception", i, ex) for i, ex in enumerate(st.session_state.my_exceptions)
            if ex["date"] == active_str
        ]
        
        # 전체를 병합한 후 캘린더 하단 리스트에서도 완벽하게 시간 정렬
        combined_day_items = sorted(day_events_sel + day_exceptions_sel, key=lambda x: x[2]["start"])

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

        if combined_day_items:
            st.markdown("**이 날 일정:**")
            for item_type, original_idx, item_data in combined_day_items:
                color   = item_data.get("color", "#4D96FF")
                s_t     = item_data["start"].split()[1] if " " in item_data["start"] else ""
                e_t     = item_data["end"].split()[1]   if " " in item_data["end"]   else ""
                
                if item_type == "event":
                    ev_id = item_data.get("id") or f"idx_{original_idx}"
                    is_sel = (st.session_state.cal_selected_ev_id == ev_id)
                else:
                    # 예외 일정 식별용 키 생성
                    ev_id = f"exc_{item_data['timetable_id']}_{item_data['date']}"
                    is_sel = (st.session_state.cal_selected_ev_id == ev_id)

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
                        f"<div style='font-weight:700;font-size:14px;color:{color};'>{item_data['title']}</div>"
                        f"<div style='font-size:12px;color:#555;margin-top:2px;'>🕐 {s_t} ~ {e_t}</div>"
                        f"</div>",
                        unsafe_allow_html=True
                    )
                with col_btn:
                    if item_type == "event":
                        lbl = "✖" if is_sel else "···"
                        if st.button(lbl, key=f"sel_ev_{ev_id}", use_container_width=True):
                            if is_sel:
                                st.session_state.cal_selected_ev_id  = None
                                st.session_state.cal_selected_ev_idx = None
                            else:
                                st.session_state.cal_selected_ev_id  = ev_id
                                st.session_state.cal_selected_ev_idx = original_idx
                            st.rerun()
                    else:
                        # 예외 일정은 바로 삭제 처리 진행할 수 있도록 구현
                        if st.button("✖", key=f"del_exc_btn_{ev_id}", use_container_width=True, help="예외 설정 해제"):
                            db_delete_timetable_exception(item_data["timetable_id"], item_data["date"])
                            st.session_state.data_loaded = False
                            st.session_state.cal_selected_ev_id = None
                            st.rerun()

                if item_type == "event" and is_sel:
                    try:
                        s_d_obj = datetime.strptime(item_data["start"].split()[0], "%Y-%m-%d").date()
                        s_t_obj = datetime.strptime(item_data["start"].split()[1], "%H:%M").time()
                        e_d_obj = datetime.strptime(item_data["end"].split()[0],   "%Y-%m-%d").date()
                        e_t_obj = datetime.strptime(item_data["end"].split()[1],   "%H:%M").time()
                    except Exception:
                        s_d_obj = e_d_obj = datetime.now().date()
                        s_t_obj = datetime.strptime("09:00", "%H:%M").time()
                        e_t_obj = datetime.strptime("18:00", "%H:%M").time()

                    with st.form(f"edit_event_form_{ev_id}"):
                        new_title  = st.text_input("일정 제목", value=item_data["title"])
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
                            "id":    item_data.get("id"),
                            "title": new_title,
                            "start": f"{new_s_date} {new_s_time.strftime('%H:%M')}",
                            "end":   f"{new_e_date} {new_e_time.strftime('%H:%M')}",
                            "color": item_data.get("color", get_random_color()),
                        }
                        db_save_event(st.session_state.user_id, updated)
                        st.session_state.data_loaded = False
                        st.session_state.cal_selected_ev_id  = None
                        st.session_state.cal_selected_ev_idx = None
                        st.rerun()
                    elif deleted:
                        if item_data.get("id"):
                            db_delete_event(item_data["id"])
                        st.session_state.data_loaded = False
                        st.session_state.cal_selected_ev_id  = None
                        st.session_state.cal_selected_ev_idx = None
                        st.rerun()
                    elif cancelled:
                        st.session_state.cal_selected_ev_id  = None
                        st.session_state.cal_selected_ev_idx = None
                        st.rerun()

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
                st.toast("✅ 일정이 성공적으로 추가되었습니다!")
                st.rerun()
        elif do_cancel:
            st.session_state.cal_selected_date = None
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("⚙️ 고정 시간표 및 예외 관리", type="secondary", use_container_width=True):
        st.session_state.app_page = "FIXED_TIMETABLE"
        st.session_state.ft_success_msg = None
        st.rerun()


# ════════════════════════════════════════════════
# 고정 시간표 및 예외 등록
# ════════════════════════════════════════════════
def page_fixed_timetable():
    h1, h2 = st.columns([5, 2])
    with h2:
        if st.button("달력 보기", use_container_width=True):
            st.session_state.app_page = "MY_CALENDAR"
            st.session_state.ft_success_msg = None
            st.session_state.tt_selected_id = None
            st.rerun()
    with h1:
        st.title("🕞 고정 시간표 및 예외 관리")

    if st.session_state.ft_success_msg:
        st.success(st.session_state.ft_success_msg)

    with st.expander("➕ 고정 일정 추가 및 수정", expanded=st.session_state.fixed_expander_open or (st.session_state.tt_selected_id is not None)):
        editing_entry = None
        if st.session_state.tt_selected_id:
            for t in st.session_state.my_timetable:
                if t["id"] == st.session_state.tt_selected_id:
                    editing_entry = t
                    break

        if editing_entry:
            st.markdown(f"**✏️ '{editing_entry['title']}' 고정 일정 수정 중**")
            f_title = st.text_input("일정 제목", value=editing_entry["title"], key="ft_title")
            f_day   = st.selectbox("요일", ["월","화","수","목","금","토","일"], index=["월","화","수","목","금","토","일"].index(editing_entry["day"]), key="ft_day")
            f_start = st.text_input("시작 시각 (예: 09:00)", value=editing_entry["start"], key="ft_start")
            f_end   = st.text_input("종료 시각 (예: 12:00)", value=editing_entry["end"], key="ft_end")
            
            c_btn1, c_btn2 = st.columns(2)
            if c_btn1.button("💾 수정 완료", type="primary", use_container_width=True):
                if f_title:
                    db_save_timetable_entry(st.session_state.user_id, {
                        "id": editing_entry["id"], "title": f_title, "day": f_day,
                        "start": f_start, "end": f_end, "color": editing_entry["color"]
                    })
                    st.session_state.tt_selected_id = None
                    st.session_state.data_loaded = False
                    st.session_state.ft_success_msg = "✅ 고정 일정이 성공적으로 수정되었습니다."
                    load_user_data()
                    st.rerun()
            if c_btn2.button("취소", use_container_width=True):
                st.session_state.tt_selected_id = None
                st.rerun()
        else:
            st.markdown("**➕ 새로운 고정 일정 추가**")
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
                    st.session_state.ft_success_msg = "✅ 새 고정 일정이 저장되었습니다."
                    load_user_data()
                    st.rerun()
                else:
                    st.warning("일정 제목을 입력해주세요.")

    with st.expander("🚨 🛑 고정 시간표 예외 등록", expanded=True):
        st.markdown("<p style='font-size:13px; color:#555;'>특정 날짜에 개인 사정 등으로 비워지는 고정 일정을 선택하세요.</p>", unsafe_allow_html=True)
        
        if not st.session_state.my_timetable:
            st.caption("등록된 고정 일정이 없습니다.")
        else:
            options = []
            option_map = {}
            for t in st.session_state.my_timetable:
                display_text = f"[{t['day']}요일] {t['title']} ({t['start']}~{t['end']})"
                options.append(display_text)
                option_map[display_text] = t
                
            selected_option = st.selectbox("제외할 고정 일정 선택", options=options, key="exc_tt_select", label_visibility="collapsed")
            exception_date = st.date_input("예외 날짜 선택", value=datetime.now().date(), key="exc_date_picker")
            
            if st.button("선택한 고정 일정 예외 등록 💾", type="primary", use_container_width=True):
                target_timetable = option_map[selected_option]
                target_timetable_id = target_timetable["id"]
                target_day = target_timetable["day"]
                
                # 1. 요일 불일치 검증
                weekdays_kr = ["월", "화", "수", "목", "금", "토", "일"]
                chosen_date_day = weekdays_kr[exception_date.weekday()]
                
                if target_day != chosen_date_day:
                    st.error(f"❌ 요일이 일치하지 않습니다! 선택하신 고정 일정은 {target_day}요일이지만, 선택한 날짜는 {chosen_date_day}요일입니다.")
                # 2. 중복 예외 등록 검증
                elif db_check_exception_exists(target_timetable_id, str(exception_date)):
                    st.error("❌ 이미 예외 설정이 돼있습니다.")
                else:
                    res, err = db_save_timetable_exception(target_timetable_id, str(exception_date))
                    if err:
                        st.error(f"예외 등록 오류: {err}")
                    else:
                        st.session_state.ft_success_msg = f"✅ [{exception_date}] 해당 고정 일정에 대한 예외 처리가 정상 저장되었습니다!"
                        st.session_state.data_loaded = False
                        load_user_data()
                        st.rerun()

    if st.session_state.my_timetable:
        st.markdown("### 📋 등록된 고정 일정")
        for ti, t in enumerate(st.session_state.my_timetable):
            col_a, col_edit, col_del = st.columns([5, 1, 1])
            with col_a:
                st.markdown(
                    f"<div style='background-color:{t.get('color','#BBDEFB')};padding:8px;"
                    f"border-radius:5px;margin-bottom:4px;color:#333;font-size:12px;'>"
                    f"<b>{t['title']}</b> | {t['day']}요일 {t['start']} ~ {t['end']}</div>",
                    unsafe_allow_html=True
                )
            with col_edit:
                if st.button("✏️", key=f"edit_tt_{t['id']}", use_container_width=True):
                    st.session_state.tt_selected_id = t["id"]
                    st.rerun()
            with col_del:
                if st.button("🗑️", key=f"del_tt_{ti}", use_container_width=True):
                    if t.get("id"):
                        db_delete_timetable_entry(t["id"])
                    st.session_state.my_timetable.pop(ti)
                    if st.session_state.tt_selected_id == t.get("id"):
                        st.session_state.tt_selected_id = None
                    st.session_state.ft_success_msg = None
                    st.session_state.data_loaded = False
                    load_user_data()
                    st.rerun()

    st.write("### 🗑️ 일주일 타임라인 (15분 단위)")
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
# 그룹 방 (가용 시간 대조)
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
        for t in m_data.get("timetable", []):
            if t["day"] == w_str:
                if d_str in t.get("exceptions", []):
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

    if sel_day and sel_day in colors:
        slots = st.session_state.grp_free_slots.get(sel_day, [False] * 96)
        sy, sm, sd = map(int, sel_day.split("-"))

        st.markdown("---")
        st.markdown(f"### 📊 {sy}년 {sm}월 {sd}일 분석")

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

DAY_ORDER = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}
WEEKDAY_MAPPING = {0: "월", 1: "화", 2: "수", 3: "목", 4: "금", 5: "토", 6: "일"}

# ── 전역 CSS (모바일 최적화) ─────────────────────────────────────────────────
GLOBAL_CSS = """
<style>
.main .block-container {
    padding-left: 0.75rem !important;
    padding-right: 0.75rem !important;
    max-width: 100% !important;
}
[data-testid="stHorizontalBlock"] [data-testid="column"] {
    padding-left: 2px !important;
    padding-right: 2px !important;
}
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
        payload = {
            "user_id": user_id,
            "title": entry["title"],
            "day": entry["day"],
            "start_time": entry["start"],
            "end_time": entry["end"],
            "color": entry.get("color", get_random_color()),
        }
        if entry.get("id"):
            supabase.table("timetable").update(payload).eq("id", entry["id"]).execute()
        else:
            supabase.table("timetable").insert(payload).execute()
    except Exception as e:
        st.error(f"시간표 저장 오류: {e}")

def db_delete_timetable_entry(entry_id):
    try:
        supabase.table("timetable").delete().eq("id", entry_id).execute()
    except Exception as e:
        st.error(f"시간표 삭제 오류: {e}")

def db_save_timetable_exception(timetable_id, exception_date):
    try:
        res = supabase.table("timetable_exceptions").insert({
            "timetable_id": timetable_id,
            "exception_date": exception_date
        }).execute()
        return res.data, None
    except Exception as e:
        return None, str(e)

# 중복된 예외 일정이 있는지 확인하기 위한 헬퍼 함수
def db_check_exception_exists(timetable_id, exception_date):
    try:
        res = supabase.table("timetable_exceptions").select("id").eq("timetable_id", timetable_id).eq("exception_date", exception_date).execute()
        return len(res.data) > 0
    except Exception:
        return False

def db_get_user_timetable_exceptions(user_id):
    try:
        res = supabase.table("timetable").select("id, title, timetable_exceptions(id, exception_date)").eq("user_id", user_id).execute()
        exceptions = []
        for row in (res.data or []):
            for ex in row.get("timetable_exceptions", []):
                exceptions.append({
                    "exception_id": ex["id"],
                    "timetable_title": row["title"],
                    "exception_date": ex["exception_date"]
                })
        return exceptions
    except Exception:
        return []

def db_delete_timetable_exception(exception_id):
    try:
        supabase.table("timetable_exceptions").delete().eq("id", exception_id).execute()
        return True
    except Exception as e:
        st.error(f"예외 삭제 오류: {e}")
        return False

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
            
            tt_res = supabase.table("timetable").select("*, timetable_exceptions(exception_date)").eq("user_id", uid).execute()
            timetable_raw = tt_res.data or []
            
            members[nick] = {
                "events": [
                    {"title": e["title"], "start": e["start_dt"], "end": e["end_dt"]}
                    for e in events_raw
                ],
                "timetable": [
                    {
                        "id": t["id"], 
                        "title": t["title"], 
                        "day": t["day"],
                        "start": t["start_time"], 
                        "end": t["end_time"],
                        "exceptions": [ex["exception_date"] for ex in t.get("timetable_exceptions", [])]
                    }
                    for t in timetable_raw
                ],
            }
        return members
    except Exception as e:
        st.error(f"멤버 조회 오류: {e}")
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
        "cal_selected_date": None,
        "cal_selected_ev_id": None,
        "cal_selected_ev_idx": None,
        "tt_selected_id": None, 
        "grp_date_colors": None,
        "grp_free_slots": None,
        "grp_selected_day": None,
        "grp_start_d": None,
        "grp_end_d": None,
        "grp_time_start": 9,
        "grp_time_end": 21,
        "ft_success_msg": None 
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
    
    raw_timetable = db_get_timetable(uid)
    sorted_timetable = sorted(
        raw_timetable,
        key=lambda x: (DAY_ORDER.get(x["day"], 7), x["start_time"])
    )
    st.session_state.my_timetable = [
        {"id": t["id"], "title": t["title"], "day": t["day"],
         "start": t["start_time"], "end": t["end_time"], "color": t.get("color", get_random_color())}
        for t in sorted_timetable
    ]
    
    st.session_state.my_exceptions = db_get_user_timetable_exceptions(uid)
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
# HTML 달력 빌더
# ════════════════════════════════════════════════
def build_calendar_html(year, month, events, selected_date_str=None):
    today = datetime.now()
    cal_matrix = calendar.monthcalendar(year, month)

    day_names   = ["일", "월", "화", "수", "목", "금", "토"]
    hdr_colors  = ["#E53935","#555","#555","#555","#555","#555","#1565C0"]

    html = '<div class="wwm-cal">'

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

            bars = ""
            for ev in day_events[:2]:
                c = ev.get("color", "#4D96FF")
                t_s = ev["title"][:4] + ("…" if len(ev["title"]) > 4 else "")
                bars += f'<div class="wwm-evbar" style="background:{c};">{t_s}</div>'
            if len(day_events) > 2:
                bars += f'<div class="wwm-more">+{len(day_events)-2}</div>'

            today_lbl = '<span class="wwm-today-lbl">Today</span>' if is_today else ""
            
            html += (
                f'<div class="{cls}">'
                f'<span class="wwm-dnum" style="color:{num_color};">{day_num}</span>'
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

    cal_html = build_calendar_html(now.year, now.month, [], None)
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
# 나의 일정
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

    sel_date_obj = st.session_state.cal_selected_date
    sel_date_str = sel_date_obj.strftime("%Y-%m-%d") if sel_date_obj else None
    if sel_date_obj and (sel_date_obj.year != cur_year or sel_date_obj.month != cur_month):
        sel_date_str = None
        st.session_state.cal_selected_date = None

    cal_html = build_calendar_html(cur_year, cur_month, st.session_state.my_events, sel_date_str)
    st.markdown(cal_html, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

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
            st.session_state.view_year  = picked.year
            st.session_state.view_month = picked.month
            st.rerun()

    if st.session_state.cal_selected_date:
        active_date = st.session_state.cal_selected_date
        active_str  = active_date.strftime("%Y-%m-%d")

        day_events_sel = [
            (i, ev) for i, ev in enumerate(st.session_state.my_events)
            if ev["start"].split()[0] <= active_str <= ev["end"].split()[0]
        ]
        
        day_events_sel = sorted(day_events_sel, key=lambda x: x[1]["start"])

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
                    lbl = "✖" if is_sel else "···"
                    if st.button(lbl, key=f"sel_ev_{ev_id}", use_container_width=True):
                        if is_sel:
                            st.session_state.cal_selected_ev_id  = None
                            st.session_state.cal_selected_ev_idx = None
                        else:
                            st.session_state.cal_selected_ev_id  = ev_id
                            st.session_state.cal_selected_ev_idx = ev_i
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
                        st.session_state.data_loaded = False
                        st.session_state.cal_selected_ev_id  = None
                        st.session_state.cal_selected_ev_idx = None
                        st.rerun()
                    elif deleted:
                        if ev.get("id"):
                            db_delete_event(ev["id"])
                        st.session_state.data_loaded = False
                        st.session_state.cal_selected_ev_id  = None
                        st.session_state.cal_selected_ev_idx = None
                        st.rerun()
                    elif cancelled:
                        st.session_state.cal_selected_ev_id  = None
                        st.session_state.cal_selected_ev_idx = None
                        st.rerun()

        day_exceptions_sel = [
            ex for ex in st.session_state.my_exceptions
            if ex["exception_date"] == active_str
        ]
        
        if day_exceptions_sel:
            st.markdown("**🛑 등록된 예외 일정(개인 사정 등):**")
            for ex in day_exceptions_sel:
                ec1, ec2 = st.columns([5, 1])
                with ec1:
                    st.markdown(
                        f"<div style='background-color:#FFEBEE;border-left:4px solid #D32F2F;"
                        f"border-radius:0 5px 5px 0;padding:6px 12px;margin-bottom:4px;color:#C62828;font-size:13px;'>"
                        f"<b>[고정 예외] {ex['timetable_title']}</b> 일정이 제외 상태입니다.</div>",
                        unsafe_allow_html=True
                    )
                with ec2:
                    if st.button("🗑️ 예외 삭제", key=f"del_ex_cal_{ex['exception_id']}", use_container_width=True):
                        if db_delete_timetable_exception(ex["exception_id"]):
                            st.session_state.data_loaded = False
                            st.toast("✅ 예외 일정이 성공적으로 삭제되었습니다.")
                            st.rerun()

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
                st.toast("✅ 일정이 성공적으로 추가되었습니다!")
                st.rerun()
        elif do_cancel:
            st.session_state.cal_selected_date = None
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("⚙️ 고정 시간표 및 예외 관리", type="secondary", use_container_width=True):
        st.session_state.app_page = "FIXED_TIMETABLE"
        st.rerun()


# ════════════════════════════════════════════════
# 고정 시간표 및 예외 등록
# ════════════════════════════════════════════════
def page_fixed_timetable():
    h1, h2 = st.columns([5, 2])
    with h2:
        if st.button("달력 보기", use_container_width=True):
            st.session_state.app_page = "MY_CALENDAR"
            st.session_state.ft_success_msg = None
            st.session_state.tt_selected_id = None
            st.rerun()
    with h1:
        st.title("🕞 고정 시간표 및 예외 관리")

    if st.session_state.ft_success_msg:
        st.success(st.session_state.ft_success_msg)

    with st.expander("➕ 고정 일정 추가 및 수정", expanded=st.session_state.fixed_expander_open or (st.session_state.tt_selected_id is not None)):
        editing_entry = None
        if st.session_state.tt_selected_id:
            for t in st.session_state.my_timetable:
                if t["id"] == st.session_state.tt_selected_id:
                    editing_entry = t
                    break

        if editing_entry:
            st.markdown(f"**✏️ '{editing_entry['title']}' 고정 일정 수정 중**")
            f_title = st.text_input("일정 제목", value=editing_entry["title"], key="ft_title")
            f_day   = st.selectbox("요일", ["월","화","수","목","금","토","일"], index=["월","화","수","목","금","토","일"].index(editing_entry["day"]), key="ft_day")
            f_start = st.text_input("시작 시각 (예: 09:00)", value=editing_entry["start"], key="ft_start")
            f_end   = st.text_input("종료 시각 (예: 12:00)", value=editing_entry["end"], key="ft_end")
            
            c_btn1, c_btn2 = st.columns(2)
            if c_btn1.button("💾 수정 완료", type="primary", use_container_width=True):
                if f_title:
                    db_save_timetable_entry(st.session_state.user_id, {
                        "id": editing_entry["id"], "title": f_title, "day": f_day,
                        "start": f_start, "end": f_end, "color": editing_entry["color"]
                    })
                    st.session_state.tt_selected_id = None
                    st.session_state.data_loaded = False
                    st.session_state.ft_success_msg = "✅ 고정 일정이 성공적으로 수정되었습니다."
                    load_user_data()
                    st.rerun()
            if c_btn2.button("취소", use_container_width=True):
                st.session_state.tt_selected_id = None
                st.rerun()
        else:
            st.markdown("**➕ 새로운 고정 일정 추가**")
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
                    st.session_state.ft_success_msg = "✅ 새 고정 일정이 저장되었습니다."
                    load_user_data()
                    st.rerun()
                else:
                    st.warning("일정 제목을 입력해주세요.")

    with st.expander("🚨 🛑 고정 시간표 예외 등록", expanded=True):
        st.markdown("<p style='font-size:13px; color:#555;'>특정 날짜에 개인 사정이나 기타 이유로 비워지는 고정 일정을 선택하세요.</p>", unsafe_allow_html=True)
        
        if not st.session_state.my_timetable:
            st.caption("등록된 고정 일정이 없습니다.")
        else:
            options = []
            option_map = {}
            for t in st.session_state.my_timetable:
                display_text = f"[{t['day']}요일] {t['title']} ({t['start']}~{t['end']})"
                options.append(display_text)
                option_map[display_text] = (t["id"], t["day"]) # 요일 검증을 위해 요일 텍스트도 매핑 저장
                
            selected_option = st.selectbox("제외할 고정 일정 선택", options=options, key="exc_tt_select", label_visibility="collapsed")
            exception_date = st.date_input("예외 날짜 선택", value=datetime.now().date(), key="exc_date_picker")
            
            if st.button("선택한 고정 일정 예외 등록 💾", type="primary", use_container_width=True):
                target_timetable_id, target_day = option_map[selected_option]
                
                # 1. 요일 불일치 검증
                picked_weekday_num = exception_date.weekday() # 0:월 ~ 6:일
                picked_weekday_str = WEEKDAY_MAPPING.get(picked_weekday_num, "")
                
                if picked_weekday_str != target_day:
                    st.warning(f"⚠️ 선택하신 날짜({exception_date})는 {picked_weekday_str}요일입니다. 해당 일정의 요일({target_day}요일)과 일치하지 않습니다.")
                
                # 2. 🛠️ [기능 추가] 이미 예외가 등록된 경우 검증 (노란색 팝업 창 활성화)
                elif db_check_exception_exists(target_timetable_id, str(exception_date)):
                    st.warning("⚠️ 이미 예외 설정이 되어 있습니다.")
                
                # 3. 모두 통과 시 정상 저장
                else:
                    res, err = db_save_timetable_exception(target_timetable_id, str(exception_date))
                    if err:
                        st.error(f"예외 등록 오류: {err}")
                    else:
                        st.session_state.ft_success_msg = f"✅ [{exception_date}] 해당 고정 일정에 대한 예외 처리가 정상 저장되었습니다!"
                        st.session_state.data_loaded = False
                        st.rerun()

    if st.session_state.my_timetable:
        st.markdown("### 📋 등록된 고정 일정")
        for ti, t in enumerate(st.session_state.my_timetable):
            col_a, col_edit, col_del = st.columns([5, 1, 1])
            with col_a:
                st.markdown(
                    f"<div style='background-color:{t.get('color','#BBDEFB')};padding:8px;"
                    f"border-radius:5px;margin-bottom:4px;color:#333;font-size:12px;'>"
                    f"<b>{t['title']}</b> | {t['day']}요일 {t['start']} ~ {t['end']}</div>",
                    unsafe_allow_html=True
                )
            with col_edit:
                if st.button("✏️", key=f"edit_tt_{t['id']}", use_container_width=True):
                    st.session_state.tt_selected_id = t["id"]
                    st.rerun()
            with col_del:
                if st.button("🗑️", key=f"del_tt_{ti}", use_container_width=True):
                    if t.get("id"):
                        db_delete_timetable_entry(t["id"])
                    st.session_state.my_timetable.pop(ti)
                    if st.session_state.tt_selected_id == t.get("id"):
                        st.session_state.tt_selected_id = None
                    st.session_state.ft_success_msg = None
                    st.rerun()

    st.write("### 🗑️ 일주일 타임라인 (15분 단위)")
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
# 그룹 방 (가용 시간 대조)
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
        for t in m_data.get("timetable", []):
            if t["day"] == w_str:
                if d_str in t.get("exceptions", []):
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

    if sel_day and sel_day in colors:
        slots = st.session_state.grp_free_slots.get(sel_day, [False] * 96)
        sy, sm, sd = map(int, sel_day.split("-"))

        st.markdown("---")
        st.markdown(f"### 📊 {sy}년 {sm}월 {sd}일 분석")

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
