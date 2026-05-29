import streamlit as st
import calendar
import random
import string
import hashlib
import threading
from datetime import datetime, date as date_type

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

@st.cache_resource
def get_supabase():
    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = get_supabase()

# 모바일 세로 화면 최적화를 위해 레이아웃을 wide로 설정하고 CSS로 마진을 최소화합니다.
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
# 세션 상태 초기화
# ════════════════════════════════════════════════
if "app_page" not in st.session_state:
    st.session_state.app_page = "LOGIN"
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "user_name" not in st.session_state:
    st.session_state.user_name = None
if "data_loaded" not in st.session_state:
    st.session_state.data_loaded = False
if "my_events" not in st.session_state:
    st.session_state.my_events = []
if "my_timetable" not in st.session_state:
    st.session_state.my_timetable = []
if "my_rooms" not in st.session_state:
    st.session_state.my_rooms = []

# 달력 네비게이션용
if "view_year" not in st.session_state:
    st.session_state.view_year = datetime.now().year
if "view_month" not in st.session_state:
    st.session_state.view_month = datetime.now().month

# 이벤트 조작용
if "active_add_day" not in st.session_state:
    st.session_state.active_add_day = None
if "selected_event_id" not in st.session_state:
    st.session_state.selected_event_id = None
if "editing_event_idx" not in st.session_state:
    st.session_state.editing_event_idx = None

# 그룹 룸 내부용
if "current_room_id" not in st.session_state:
    st.session_state.current_room_id = None
if "grp_selected_day" not in st.session_state:
    st.session_state.grp_selected_day = None
if "grp_free_slots" not in st.session_state:
    st.session_state.grp_free_slots = {}


# ════════════════════════════════════════════════
# DB 함수들
# ════════════════════════════════════════════════
def db_login(uid, r_pw):
    try:
        res = supabase.table("users").select("*").eq("id", uid).execute()
        if res.data:
            u = res.data[0]
            if u["password"] == hash_password(r_pw):
                return u["name"]
        return None
    except Exception:
        return None

def db_signup(uid, r_pw, name):
    try:
        hpw = hash_password(r_pw)
        supabase.table("users").insert({"id": uid, "password": hpw, "name": name}).execute()
        return True
    except Exception:
        return False

def load_user_data():
    if st.session_state.data_loaded:
        return
    uid = st.session_state.user_id
    if not uid:
        return
    try:
        ev_res = supabase.table("events").select("*").eq("user_id", uid).execute()
        st.session_state.my_events = ev_res.data if ev_res.data else []
        tt_res = supabase.table("timetables").select("*").eq("user_id", uid).execute()
        st.session_state.my_timetable = tt_res.data if tt_res.data else []
        rm_res = supabase.table("room_members").select("room_id, rooms(title, code)").eq("user_id", uid).execute()
        rooms = []
        if rm_res.data:
            for r in rm_res.data:
                if r.get("rooms"):
                    rooms.append({
                        "id": r["room_id"],
                        "title": r["rooms"]["title"],
                        "code": r["rooms"]["code"]
                    })
        st.session_state.my_rooms = rooms
        st.session_state.data_loaded = True
    except Exception:
        pass

def db_save_event(uid, ev):
    try:
        data = {
            "user_id": uid,
            "title": ev["title"],
            "start": ev["start"],
            "end": ev["end"],
            "color": ev.get("color", "#4D96FF")
        }
        if ev.get("id"):
            supabase.table("events").update(data).eq("id", ev["id"]).execute()
        else:
            supabase.table("events").insert(data).execute()
        st.session_state.data_loaded = False
    except Exception:
        pass

def db_delete_event(ev_id):
    try:
        supabase.table("events").delete().eq("id", ev_id).execute()
        st.session_state.data_loaded = False
    except Exception:
        pass

def db_save_timetable(uid, tt_list):
    try:
        supabase.table("timetables").delete().eq("user_id", uid).execute()
        if tt_list:
            for t in tt_list:
                t["user_id"] = uid
                if "id" in t: del t["id"]
            supabase.table("timetables").insert(tt_list).execute()
        st.session_state.data_loaded = False
    except Exception:
        pass

def db_create_room(uid, title):
    try:
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        res = supabase.table("rooms").insert({"title": title, "code": code}).execute()
        if res.data:
            rid = res.data[0]["id"]
            supabase.table("room_members").insert({"room_id": rid, "user_id": uid}).execute()
            st.session_state.data_loaded = False
            return True
        return False
    except Exception:
        return False

def db_join_room(uid, code):
    try:
        res = supabase.table("rooms").select("id").eq("code", code.upper().strip()).execute()
        if res.data:
            rid = res.data[0]["id"]
            check = supabase.table("room_members").select("*").eq("room_id", rid).eq("user_id", uid).execute()
            if not check.data:
                supabase.table("room_members").insert({"room_id": rid, "user_id": uid}).execute()
            st.session_state.data_loaded = False
            return True
        return False
    except Exception:
        return False

def db_get_room_details(rid):
    try:
        r_res = supabase.table("rooms").select("*").eq("id", rid).execute()
        if not r_res.data: return None, {}
        room_info = r_res.data[0]
        m_res = supabase.table("room_members").select("user_id, users(name)").eq("room_id", rid).execute()
        members = {}
        if m_res.data:
            for m in m_res.data:
                uid = m["user_id"]
                uname = m["users"]["name"] if m.get("users") else "알수없음"
                members[uid] = {"name": uname, "events": [], "timetable": []}
        uids = list(members.keys())
        if uids:
            ev_res = supabase.table("events").select("*").in_("user_id", uids).execute()
            if ev_res.data:
                for ev in ev_res.data:
                    members[ev["user_id"]]["events"].append(ev)
            tt_res = supabase.table("timetables").select("*").in_("user_id", uids).execute()
            if tt_res.data:
                for tt in tt_res.data:
                    members[tt["user_id"]]["timetable"].append(tt)
        return room_info, members
    except Exception:
        return None, {}


# ════════════════════════════════════════════════
# 헬퍼 함수
# ════════════════════════════════════════════════
def require_login():
    if not st.session_state.user_id:
        st.session_state.app_page = "LOGIN"
        st.rerun()

def slot_to_time(slot_idx):
    h = slot_idx // 4
    m = (slot_idx % 4) * 15
    return f"{h:02d}:{m:02d}"


# ════════════════════════════════════════════════
# 페이지 렌더링 함수들
# ════════════════════════════════════════════════

def page_login():
    st.title("🔒 로그인 / 회원가입")
    tab1, tab2 = st.tabs(["로그인", "회원가입"])
    with tab1:
        with st.form("login_form"):
            uid = st.text_input("아이디(ID)", key="l_id")
            upw = st.text_input("비밀번호", type="password", key="l_pw")
            if st.form_submit_button("로그인", use_container_width=True):
                name = db_login(uid, upw)
                if name:
                    st.session_state.user_id = uid
                    st.session_state.user_name = name
                    st.session_state.data_loaded = False
                    st.session_state.app_page = "HOME"
                    st.rerun()
                else:
                    st.error("아이디 또는 비밀번호가 틀렸습니다.")
    with tab2:
        with st.form("signup_form"):
            suid = st.text_input("아이디(ID)", key="s_id")
            supw = st.text_input("비밀번호", type="password", key="s_pw")
            sname = st.text_input("이름 / 닉네임", key="s_name")
            if st.form_submit_button("회원가입", use_container_width=True):
                if not suid or not supw or not sname:
                    st.warning("모든 필드를 입력해주세요.")
                else:
                    if db_signup(suid, supw, sname):
                        st.success("회원가입 성공! 로그인 탭에서 로그인 해주세요.")
                    else:
                        st.error("이미 존재하는 아이디이거나 오류가 발생했습니다.")


def page_home():
    st.title(f"👋 반갑습니다, {st.session_state.user_name}님!")
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("📆 나의 일정 및 캘린더 관리", use_container_width=True, type="primary"):
            st.session_state.app_page = "MY_CALENDAR"
            st.rerun()
    with c2:
        if st.button("⚙️ 개인 정보 관리", use_container_width=True):
            st.session_state.app_page = "ACCOUNT"
            st.rerun()

    st.markdown("<hr style='margin:15px 0;'>", unsafe_allow_html=True)
    st.subheader("👥 참여 중인 그룹 캘린더 방")
    
    if st.session_state.my_rooms:
        for r in st.session_state.my_rooms:
            col_t, col_b = st.columns([5, 2])
            with col_t:
                st.markdown(f"**{r['title']}** (참여코드: `{r['code']}`)")
            with col_b:
                if st.button("입장하기", key=f"enter_{r['id']}", use_container_width=True):
                    st.session_state.current_room_id = r['id']
                    st.session_state.grp_selected_day = None
                    st.session_state.app_page = "GROUP_ROOM"
                    st.rerun()
    else:
        st.info("아직 참여 중인 방이 없습니다. 아래에서 방을 만들거나 코드를 입력해 참여해보세요!")

    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("➕ 새 그룹 방 만들기 / 참여하기"):
        t1, t2 = st.tabs(["방 만들기", "코드로 참여"])
        with t1:
            with st.form("create_room_form"):
                r_title = st.text_input("그룹 방 이름")
                if st.form_submit_button("생성하기", use_container_width=True):
                    if r_title:
                        if db_create_room(st.session_state.user_id, r_title):
                            st.success("방이 생성되었습니다!")
                            st.rerun()
                    else:
                        st.warning("방 이름을 입력해주세요.")
        with t2:
            with st.form("join_room_form"):
                r_code = st.text_input("참여 코드 (6자리)")
                if st.form_submit_button("참여하기", use_container_width=True):
                    if r_code:
                        if db_join_room(st.session_state.user_id, r_code):
                            st.success("성공적으로 방에 참여했습니다!")
                            st.rerun()
                        else:
                            st.error("코드가 올바르지 않거나 방을 찾을 수 없습니다.")
                    else:
                        st.warning("코드를 입력해주세요.")


def page_account():
    st.title("⚙️ 개인 정보 관리")
    st.write(f"아이디: **{st.session_state.user_id}**")
    st.write(f"이름/닉네임: **{st.session_state.user_name}**")
    
    if st.button("로그아웃", type="inverse", use_container_width=True):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()
    if st.button("메인 홈으로", use_container_width=True):
        st.session_state.app_page = "HOME"
        st.rerun()


def page_my_calendar():
    h1, h2 = st.columns([5, 2])
    with h2:
        if st.button("홈으로", use_container_width=True):
            st.session_state.app_page = "HOME"
            st.rerun()
    with h1:
        st.title("📆 나의 일정")

    # 모바일 화면 공간 절약을 위해 상단 여백 및 크기 최적화 CSS 주입
    st.markdown("""
        <style>
            .stButton > button { padding: 2px 4px !important; font-size: 12px !important; min-height: 28px !important; }
            div[data-testid="stForm"] { padding: 8px !important; margin-top: 5px !important; }
            h4 { margin-top: 5px !important; margin-bottom: 5px !important; }
        </style>
    """, unsafe_allow_html=True)

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

    # ── 요일 헤더 ──────────────────────────────────────
    day_names = ["일", "월", "화", "수", "목", "금", "토"]
    hdr_html = "<div style='display:grid;grid-template-columns:repeat(7,1fr);gap:2px;margin-bottom:2px;'>"
    for i, dn in enumerate(day_names):
        color = "#E53935" if i == 0 else ("#1565C0" if i == 6 else "#555")
        hdr_html += f"<div style='text-align:center;font-size:11px;font-weight:bold;color:{color};padding:2px 0;'>{dn}</div>"
    hdr_html += "</div>"
    st.markdown(hdr_html, unsafe_allow_html=True)

    # ── 주(week) 단위로 달력 행 + 상세패널 렌더 ──
    for week in cal_matrix:
        cols = st.columns(7)
        
        for col_idx, day_num in enumerate(week):
            if day_num == 0:
                continue
                
            date_str  = f"{cur_year}-{cur_month:02d}-{day_num:02d}"
            is_today  = (day_num == today.day and cur_month == today.month and cur_year == today.year)
            is_active = (active_day == day_num)
            is_sun    = (col_idx == 0)
            is_sat    = (col_idx == 6)

            num_color = "#E53935" if is_sun else ("#1565C0" if is_sat else "#212121")
            bg_color  = "#EEF4FF" if is_active else ("#FFF9C4" if is_today else "#FFFFFF")
            border_c  = "#1976D2" if is_active else "#E0E0E0"
            border_w  = "2px" if is_active else "1px"

            day_events = [
                ev for ev in st.session_state.my_events
                if ev["start"].split()[0] <= date_str <= ev["end"].split()[0]
            ]
            
            bars_html = ""
            for ev in day_events[:2]:
                c = ev.get("color", "#4D96FF")
                t_short = ev["title"][:3] + (".." if len(ev["title"]) > 3 else "")
                bars_html += f"<div style='background:{c};color:white;font-size:7px;border-radius:2px;padding:1px;margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;'>{t_short}</div>"
            if len(day_events) > 2:
                bars_html += f"<div style='font-size:7px;color:#999;margin-top:1px;'>+{len(day_events)-2}</div>"

            with cols[col_idx]:
                # 미니멈 높이를 45px로 압축 고정하여 폰 화면에 한눈에 들어오게 함
                container_style = f"""
                <div style="background:{bg_color}; border:{border_w} solid {border_c}; border-radius:4px; padding:2px; text-align:center; min-height:45px;">
                    <span style="font-size:10px; font-weight:bold; color:{num_color};">{'⭐' if is_today else ''}{day_num}</span>
                    {bars_html}
                </div>
                """
                st.markdown(container_style, unsafe_allow_html=True)
                
                if st.button("선택" if not is_active else "✔", key=f"day_{date_str}", use_container_width=True):
                    if is_active:
                        st.session_state.active_add_day = None
                    else:
                        st.session_state.active_add_day = day_num
                        st.session_state.selected_event_id = None
                        st.session_state.editing_event_idx = None
                    st.rerun()

        # 구조 유지 + 모바일 한눈에 뷰 적용 (상세 패널을 내부 스크롤 박스에 가두기)
        if active_day and active_day in week:
            add_day = active_day
            date_str_sel   = f"{cur_year}-{cur_month:02d}-{add_day:02d}"
            day_events_sel = [
                (i, ev) for i, ev in enumerate(st.session_state.my_events)
                if ev["start"].split()[0] <= date_str_sel <= ev["end"].split()[0]
            ]

            st.markdown("<hr style='margin:8px 0;'>", unsafe_allow_html=True)
            hc1, hc2 = st.columns([5, 2])
            with hc1:
                st.markdown(f"<h5 style='margin:0; font-size:14px;'>📅 {add_day}일 일정 목록</h5>", unsafe_allow_html=True)
            with hc2:
                if st.button("✖ 닫기", key="close_day_panel", use_container_width=True):
                    st.session_state.active_add_day   = None
                    st.session_state.selected_event_id = None
                    st.session_state.editing_event_idx = None
                    st.rerun()

            # 📱 상세 일정이 길어져도 화면 밖으로 안 넘어가게 최대 높이를 제한하고 내부 스크롤 부여
            panel_html = "<div style='max-height: 180px; overflow-y: auto; padding-right: 4px; margin-bottom: 8px;'>"
            st.markdown(panel_html, unsafe_allow_html=True)

            if day_events_sel:
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

                    col_bar, col_btn = st.columns([6, 1.5])
                    with col_bar:
                        st.markdown(
                            f"<div style='background:{bg_style}; border-left:3px solid {border_c}; "
                            f"border-radius:0 4px 4px 0; padding:4px 8px; margin-bottom:2px;'>"
                            f"<div style='font-weight:700; font-size:12px; color:{color};'>{ev['title']}</div>"
                            f"<div style='font-size:10px; color:#555;'>🕐 {s_t}~{e_t}</div>"
                            f"</div>",
                            unsafe_allow_html=True
                        )
                    with col_btn:
                        lbl = "✖" if is_sel else "•••"
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
                            new_title  = st.text_input("제목", value=ev["title"])
                            c1, c2     = st.columns(2)
                            new_s_date = c1.date_input("시작일", value=s_d_obj)
                            new_s_time = c2.time_input("시작시", value=s_t_obj)
                            c3, c4     = st.columns(2)
                            new_e_date = c3.date_input("종료일", value=e_d_obj)
                            new_e_time = c4.time_input("종료시", value=e_t_obj)
                            col_save, col_del, col_cancel = st.columns(3)
                            saved     = col_save.form_submit_button("💾",   use_container_width=True)
                            deleted   = col_del.form_submit_button("🗑️",  use_container_width=True)
                            cancelled = col_cancel.form_submit_button("✖", use_container_width=True)

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
                        elif cancelled:
                            st.session_state.selected_event_id = None
                            st.session_state.editing_event_idx = None
                            st.rerun()
            
            st.markdown("</div>", unsafe_allow_html=True) # 스크롤 박스 끝

            st.markdown(f"<p style='margin:0; font-size:12px; font-weight:bold;'>➕ {add_day}일 일정 추가</p>", unsafe_allow_html=True)
            with st.form("event_form"):
                ev_title = st.text_input("일정 제목", placeholder="제목을 입력하세요")
                c1, c2   = st.columns(2)
                s_date   = c1.date_input("시작일", value=datetime(cur_year, cur_month, add_day))
                s_time   = c2.time_input("시작시", value=datetime.strptime("09:00", "%H:%M").time())
                c3, c4   = st.columns(2)
                e_date   = c3.date_input("종료일", value=datetime(cur_year, cur_month, add_day))
                e_time   = c4.time_input("종료시", value=datetime.strptime("18:00", "%H:%M").time())
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

    if st.button("⚙️ 고정 시간표 관리", type="secondary", use_container_width=True):
        st.session_state.app_page = "FIXED_TIMETABLE"
        st.rerun()


def page_fixed_timetable():
    st.title("⚙️ 고정 시간표 관리")
    st.write("매주 반복되는 고정 일정(수업, 알바 등)을 등록해두면 약속 조율 시 자동으로 제외됩니다.")
    
    days_list = ["월", "화", "수", "목", "금", "토", "일"]
    time_options = [f"{h:02d}:00" for h in range(24)]
    
    with st.form("new_tt_form"):
        st.markdown("**반복 일정 추가**")
        t_day = st.selectbox("요일", options=days_list)
        c1, c2 = st.columns(2)
        t_start = c1.selectbox("시작 시간", options=time_options, index=9)
        t_end = c2.selectbox("종료 시간", options=time_options, index=18)
        if st.form_submit_button("➕ 시간표에 추가", use_container_width=True):
            if t_start >= t_end:
                st.error("종료 시간은 시작 시간보다 늦어야 합니다.")
            else:
                st.session_state.my_timetable.append({"day": t_day, "start": t_start, "end": t_end})
                st.success(f"추가됨: {t_day}요일 {t_start} ~ {t_end}")
                
    st.markdown("<hr style='margin:15px 0;'>", unsafe_allow_html=True)
    st.markdown("**현재 등록된 고정 목록**")
    
    if st.session_state.my_timetable:
        to_remove = None
        for i, t in enumerate(st.session_state.my_timetable):
            c_txt, c_btn = st.columns([6, 1.5])
            with c_txt:
                st.write(f"• **{t['day']}요일** {t['start']} ~ {t['end']}")
            with c_btn:
                if st.button("삭제", key=f"del_tt_{i}", use_container_width=True):
                    to_remove = i
        if to_remove is not None:
            st.session_state.my_timetable.pop(to_remove)
            st.rerun()
    else:
        st.info("등록된 고정 시간표가 없습니다.")
        
    c_b1, c_b2 = st.columns(2)
    with c_b1:
        if st.button("💾 최종 저장하기", type="primary", use_container_width=True):
            db_save_timetable(st.session_state.user_id, st.session_state.my_timetable)
            st.success("데이터베이스에 저장되었습니다!")
    with c_b2:
        if st.button("🔙 내 캘린더로", use_container_width=True):
            st.session_state.app_page = "MY_CALENDAR"
            st.rerun()


def page_group_room():
    rid = st.session_state.current_room_id
    if not rid:
        st.session_state.app_page = "HOME"
        st.rerun()
        
    room_info, g_members = db_get_room_details(rid)
    if not room_info:
        st.error("방 정보를 불러올 수 없습니다.")
        if st.button("홈으로"):
            st.session_state.app_page = "HOME"
            st.rerun()
        return

    h1, h2 = st.columns([5, 2])
    with h2:
        if st.button("방 나가기", use_container_width=True):
            st.session_state.current_room_id = None
            st.session_state.grp_selected_day = None
            st.session_state.app_page = "HOME"
            st.rerun()
    with h1:
        st.title(f"👥 {room_info['title']}")
        st.caption(f"참여 코드: **{room_info['code']}** | 멤버 수: {len(g_members)}명")

    # 약속 조율 범위 설정
    with st.expander("📅 대조 조건 및 범위 설정", expanded=False):
        c1, c2 = st.columns(2)
        start_d = c1.date_input("대조 시작일", value=datetime.now().date())
        end_d = c2.date_input("대조 종료일", value=datetime.now().date())
        c3, c4 = st.columns(2)
        t_start = c3.number_input("하루 시작시각", min_value=0, max_value=23, value=9)
        t_end = c4.number_input("하루 종료시각", min_value=1, max_value=24, value=22)

    if start_d > end_d or t_start >= t_end:
        st.error("시간 또는 날짜 설정 범위가 올바르지 않습니다.")
        return

    # 시간표 대조 메인 로직 생성
    with _LOCK:
        colors = {}
        st.session_state.grp_free_slots = {}
        
        curr = start_d
        while curr <= end_d:
            d_str = curr.strftime("%Y-%m-%d")
            w_idx = curr.weekday()
            w_days = ["월", "화", "수", "목", "금", "토", "일"]
            w_day = w_days[w_idx]

            slots = [True] * 96 # 15분 단위 24시간
            
            for m_id, m_data in g_members.items():
                for ev in m_data.get("events", []):
                    s_d, s_t = ev["start"].split() if " " in ev["start"] else (ev["start"], "00:00")
                    e_d, e_t = ev["end"].split() if " " in ev["end"] else (ev["end"], "23:59")
                    if s_d <= d_str <= e_d:
                        sh, sm = map(int, s_t.split(":"))
                        eh, em = map(int, e_t.split(":"))
                        s_idx = sh * 4 + sm // 15 if d_str == s_d else 0
                        e_idx = eh * 4 + em // 15 if d_str == e_d else 96
                        for i in range(s_idx, e_idx):
                            if i < 96: slots[i] = False

                for tt in m_data.get("timetable", []):
                    if tt["day"] == w_day:
                        try:
                            sh = int(tt["start"].split(":")[0])
                            eh = int(tt["end"].split(":")[0])
                            for i in range(sh * 4, eh * 4):
                                if i < 96: slots[i] = False
                        except Exception:
                            pass

            st.session_state.grp_free_slots[d_str] = slots
            
            # 지정된 탐색 시간대 내에 한 번이라도 공통 가능 시간이 있는지 확인
            req_start_idx = t_start * 4
            req_end_idx = t_end * 4
            day_has_free = any(slots[i] for i in range(req_start_idx, req_end_idx) if i < 96)
            colors[d_str] = "green" if day_has_free else "red"
            
            curr += date_type.resolution

    render_year = start_d.year
    render_month = start_d.month
    end_year = end_d.year
    end_month = end_d.month

    # ── 헬퍼: 선택된 날짜의 상세 분석 패널 (모바일 맞춤 압축 버전) ──────────────
    def render_day_detail(sel_day):
        slots = st.session_state.grp_free_slots.get(sel_day, [False] * 96)
        year_s, month_s, day_s = map(int, sel_day.split("-"))

        st.markdown("<hr style='margin:8px 0;'>", unsafe_allow_html=True)
        dc1, dc2 = st.columns([5, 2])
        with dc1:
            st.markdown(f"<h5 style='margin:0; font-size:14px;'>📊 {day_s}일 가용 분석</h5>", unsafe_allow_html=True)
        with dc2:
            if st.button("✖ 닫기", key=f"grp_close_{sel_day}", use_container_width=True):
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
                '<div style="display:flex;align-items:center;gap:4px;margin-bottom:1px;">'
                '<span style="font-size:9px;color:#555;min-width:28px;text-align:right;">{h:02d}시</span>'
                '<div style="display:flex;flex:1;">{cells}</div>'
                '</div>'.format(h=hour, cells=cells)
            )
            
        # 📱 24시간 타임라인 바가 너무 길어 폰 화면을 다 차지하지 않도록 max-height 박스로 압축!
        bar_html = (
            '<div style="max-height:140px; overflow-y:auto; background:#fafafa;'
            'border:1px solid #ddd;border-radius:6px;padding:6px;margin-bottom:4px;">'
            + "".join(bar_rows) +
            '</div>'
            '<div style="font-size:10px;color:#555;margin-bottom:6px;">'
            '<span style="background:#4CAF50;padding:1px 4px;border-radius:2px;color:white;margin-right:6px;">가능</span>'
            '<span style="background:#F44336;padding:1px 4px;border-radius:2px;color:white;">불가</span>'
            '</div>'
        )
        st.markdown(bar_html, unsafe_allow_html=True)

        s_idx = t_start * 4
        e_idx = t_end * 4
        avail_slots = [i for i in range(s_idx, e_idx) if i < len(slots) and slots[i]]

        if not avail_slots:
            st.error("멤버의 가용 시간대가 겹치지 않습니다.")
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

            range_texts = [f"{slot_to_time(rs)}~{slot_to_time(re)}" for rs, re in ranges]
            st.markdown(
                "<div style='background:#E8F5E9; border:1px solid #388E3C; border-radius:6px; "
                "padding:6px; font-size:11px; color:#1B5E20; line-height:1.4; word-break:break-all;'>"
                "✅ 추천 시간:<br>" + " | ".join(range_texts) + "</div>",
                unsafe_allow_html=True
            )

            st.markdown("<p style='margin:4px 0 0 0; font-size:11px; font-weight:bold;'>⏰ 시간 직접 설정</p>", unsafe_allow_html=True)
            time_options = [f"{h:02d}:{m:02d}" for h in range(24) for m in [0, 15, 30, 45]]
            c_custom1, c_custom2 = st.columns(2)
            with c_custom1:
                custom_start = st.selectbox("시작", options=time_options, index=time_options.index("12:00"), key=f"cstart_{sel_day}")
            with c_custom2:
                custom_end = st.selectbox("종료", options=time_options, index=time_options.index("14:00"), key=f"cend_{sel_day}")
            if st.button("🚀 커스텀 시간 확정", use_container_width=True, type="primary", key=f"custom_confirm_{sel_day}"):
                if custom_start >= custom_end:
                    st.error("종료 시간이 시작 시간보다 늦어야 합니다.")
                else:
                    st.balloons()
                    st.success(f"🎉 확정! {day_s}일 {custom_start} - {custom_end}")

            st.markdown("<p style='margin:4px 0 0 0; font-size:11px; font-weight:bold;'>✨ 바로 선택</p>", unsafe_allow_html=True)
            for idx, (rs, re) in enumerate(ranges):
                duration_min = (re - rs) * 15
                dur_str = f"{duration_min // 60}h" if not duration_min % 60 else f"{duration_min // 60}h{duration_min % 60}m"
                if st.button(
                    f"👍 {slot_to_time(rs)}-{slot_to_time(re)} ({dur_str}) 확정",
                    key=f"confirm_{sel_day}_{rs}",
                    use_container_width=True
                ):
                    st.balloons()
                    st.success(f"🎉 확정! {day_s}일 {slot_to_time(rs)}-{slot_to_time(re)}")

    # ── 월별 달력 렌더링 ──
    while (render_year, render_month) <= (end_year, end_month):
        st.markdown(f"<p style='margin:8px 0 2px 0; font-size:13px; font-weight:bold;'>📅 {render_year}년 {render_month}월</p>", unsafe_allow_html=True)
        cal_matrix = calendar.monthcalendar(render_year, render_month)

        hdr = "<div style='display:grid;grid-template-columns:repeat(7,1fr);gap:2px;margin-bottom:2px;'>"
        for dn in ["일", "월", "화", "수", "목", "금", "토"]:
            hdr += f"<div style='font-weight:bold;font-size:11px;padding:2px 0;text-align:center;'>{dn}</div>"
        hdr += "</div>"
        st.markdown(hdr, unsafe_allow_html=True)

        for week in cal_matrix:
            cols = st.columns(7)
            
            for col_idx, d_num in enumerate(week):
                if d_num == 0:
                    continue
                    
                d_key  = f"{render_year}-{render_month:02d}-{d_num:02d}"
                d_date = date_type(render_year, render_month, d_num)
                in_range = start_d <= d_date <= end_d
                is_sat    = (col_idx == 6)
                is_sun    = (col_idx == 0)
                num_color = "#E53935" if is_sun else ("#1565C0" if is_sat else "#212121")
                is_sel   = (st.session_state.grp_selected_day == d_key)

                if in_range:
                    if colors.get(d_key, "red") == "green":
                        bg = "#C8E6C9" if is_sel else "#E8F5E9"
                        border = "2px solid #2E7D32" if is_sel else "1px solid #81C784"
                        status_lbl = "<span style='color:#2E7D32; font-size:8px;'>🟢가능</span>"
                    else:
                        bg = "#FFCDD2" if is_sel else "#FFEBEE"
                        border = "2px solid #B71C1C" if is_sel else "1px solid #E57373"
                        status_lbl = "<span style='color:#C62828; font-size:8px;'>🔴불가</span>"
                else:
                    bg, border, status_lbl = "#FAFAFA", "1px solid #eee", "<span style='color:#bbb; font-size:8px;'>⚪제외</span>"

                with cols[col_idx]:
                    # 대조 달력 칸 높이 축소 (38px 고정)
                    container_style = f"""
                    <div style="background:{bg}; border:{border}; padding:1px; text-align:center; border-radius:4px; min-height:38px;">
                        <span style="font-size:10px; font-weight:bold; color:{num_color};">{d_num}</span><br>
                        {status_lbl}
                    </div>
                    """
                    st.markdown(container_style, unsafe_allow_html=True)
                    
                    if in_range:
                        if st.button("확인" if not is_sel else "✔", key=f"grp_day_{d_key}", use_container_width=True):
                            st.session_state.grp_selected_day = None if is_sel else d_key
                            st.rerun()

            # 구조 유지: 날짜 버튼을 누른 주(Week) 바로 밑에 분석 패널 등장
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

    st.markdown("<hr>", unsafe_allow_html=True)
    st.subheader("📋 멤버별 등록 현황 총합")
    
    hours_range = range(t_start, t_end)
    w_table = """
    <div style='overflow-x:auto; font-size:12px;'>
    <table style='width:100%; border-collapse:collapse; text-align:center;'>
    <tr style='background-color:#f1f3f5;'>
    <th style='border:1px solid #ddd; padding:6px; font-size:10px;'>요일</th>
    """
    for h in hours_range:
        w_table += f"<th style='border:1px solid #ddd; padding:4px; font-size:9px;'>{h}시</th>"
    w_table += "</tr>"

    w_days = ["월", "화", "수", "목", "금", "토", "일"]
    for w_day in w_days:
        w_table += f"<tr><td style='font-weight:bold; border:1px solid #ddd; padding:6px;'>{w_day}</td>"
        for h in hours_range:
            is_free = True
            for name, m_data in g_members.items():
                for tt in m_data.get("timetable", []):
                    if tt["day"] == w_day:
                        try:
                            sh = int(tt["start"].split(":")[0])
                            eh = int(tt["end"].split(":")[0])
                            if sh <= h < eh:
                                is_free = False
                        except Exception:
                            pass
            bg = "#4CAF50" if is_free else "#F44336"
            w_table += f"<td style='background-color:{bg}; border:1px solid #ddd; height:22px;'></td>"
        w_table += "</tr>"
    w_table += "</table></div>"
    st.markdown(w_table, unsafe_allow_html=True)


# ════════════════════════════════════════════════
# 라우터 처리
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
elif page == "FIXED_TIMETABLE":
    require_login(); page_fixed_timetable()
elif page == "GROUP_ROOM":
    require_login(); page_group_room()
