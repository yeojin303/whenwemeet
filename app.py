import streamlit as st
import calendar
import random
import string
import hashlib
from datetime import datetime

# ────────────────────────────────────────────────
# Supabase 초기화
# ────────────────────────────────────────────────
from supabase import create_client

@st.cache_resource
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_supabase()

def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

# --- 페이지 기본 설정 및 모바일 반응형 CSS 주입 ---
st.set_page_config(page_title="When We Meet", page_icon="📅", layout="wide")

st.markdown("""
<style>
/* 1. 모바일에서 7열 달력 레이아웃이 세로로 깨지는 현상 방지 (가로 스크롤 제공) */
div[data-testid="stHorizontalBlock"]:has(> div:nth-child(7)) {
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    overflow-x: auto !important;
    padding-bottom: 8px;
}
div[data-testid="stHorizontalBlock"]:has(> div:nth-child(7)) > div {
    min-width: 105px !important;
    flex: 0 0 auto !important;
}

/* 2. 가로 스크롤바 디자인을 깔끔하고 슬림하게 조정 */
div[data-testid="stHorizontalBlock"]::-webkit-scrollbar {
    height: 5px;
}
div[data-testid="stHorizontalBlock"]::-webkit-scrollbar-thumb {
    background-color: #cbd5e1;
    border-radius: 3px;
}
</style>
""", unsafe_allow_html=True)


# ────────────────────────────────────────────────
# Supabase DB 함수
# ────────────────────────────────────────────────
def load_global_rooms():
    res = supabase.table("group_rooms").select("*").execute()
    return {r["code"]: {"name": r["name"], "members": r["members"]} for r in res.data}

def save_room(code, name, members):
    supabase.table("group_rooms").upsert({
        "code": code, "name": name, "members": members
    }).execute()

def delete_room(code):
    supabase.table("group_rooms").delete().eq("code", code).execute()

def load_personal_db(user_id):
    res = supabase.table("personal_data").select("*").eq("user_id", user_id).execute()
    return res.data[0] if res.data else None

def save_personal_db(user_id, events, timetable, joined_rooms):
    supabase.table("personal_data").upsert({
        "user_id": user_id,
        "events": events,
        "timetable": timetable,
        "joined_rooms": joined_rooms
    }).execute()


COLOR_PALETTE = [
    "#FF6B6B", "#FF8E53", "#FFC300", "#6BCB77", "#4D96FF",
    "#C77DFF", "#FF6FD8", "#00C9A7", "#F4845F", "#56CFE1",
    "#72EFDD", "#F77F00", "#9B5DE5", "#F15BB5", "#00BBF9",
]

def get_random_color():
    return random.choice(COLOR_PALETTE)


# ────────────────────────────────────────────────
# 세션 상태 초기화
# ────────────────────────────────────────────────
def init_session():
    if "app_page" not in st.session_state:
        st.session_state.app_page = "HOME"
    if "user_id" not in st.session_state:
        st.session_state.user_id = ""
    if "my_events" not in st.session_state:
        st.session_state.my_events = []
    if "my_timetable" not in st.session_state:
        st.session_state.my_timetable = []
    if "current_group_code" not in st.session_state:
        st.session_state.current_group_code = None
    if "my_nickname" not in st.session_state:
        st.session_state.my_nickname = ""
    if "editing_event_idx" not in st.session_state:
        st.session_state.editing_event_idx = None
    if "active_add_day" not in st.session_state:
        st.session_state.active_add_day = None
    if "fixed_expander_open" not in st.session_state:
        st.session_state.fixed_expander_open = False
    if "my_joined_rooms" not in st.session_state:
        st.session_state.my_joined_rooms = {}

init_session()


def _sync_my_events():
    user_id = st.session_state.user_id
    if user_id:
        save_personal_db(
            user_id,
            st.session_state.my_events,
            st.session_state.my_timetable,
            st.session_state.my_joined_rooms
        )

    nick = st.session_state.my_nickname
    code = st.session_state.current_group_code
    if nick and code:
        rooms = load_global_rooms()
        if code in rooms and nick in rooms[code]["members"]:
            rooms[code]["members"][nick]["events"] = st.session_state.my_events
            rooms[code]["members"][nick]["timetable"] = st.session_state.my_timetable
            save_room(code, rooms[code]["name"], rooms[code]["members"])


# ────────────────────────────────────────────────
# 사이드바 패널 (로그인 / 회원가입)
# ────────────────────────────────────────────────
with st.sidebar:
    st.header("👤 로그인 / 회원가입")

    if not st.session_state.user_id:
        auth_tab = st.radio("", ["로그인", "회원가입"], horizontal=True, label_visibility="collapsed")
        input_id = st.text_input("아이디").strip()
        input_pw = st.text_input("비밀번호", type="password").strip()

        if auth_tab == "회원가입":
            input_pw2 = st.text_input("비밀번호 확인", type="password").strip()
            if st.button("회원가입 ✨", use_container_width=True):
                if not input_id or not input_pw:
                    st.warning("아이디와 비밀번호를 입력해주세요.")
                elif input_pw != input_pw2:
                    st.error("비밀번호가 일치하지 않습니다.")
                elif len(input_pw) < 4:
                    st.error("비밀번호는 4자 이상이어야 합니다.")
                else:
                    existing = supabase.table("users").select("user_id").eq("user_id", input_id).execute()
                    if existing.data:
                        st.error("이미 존재하는 아이디입니다.")
                    else:
                        supabase.table("users").insert({
                            "user_id": input_id,
                            "password_hash": hash_password(input_pw)
                        }).execute()
                        supabase.table("personal_data").insert({
                            "user_id": input_id,
                            "events": [],
                            "timetable": [],
                            "joined_rooms": {}
                        }).execute()
                        st.success(f"✅ '{input_id}'님 가입 완료! 로그인 탭에서 로그인해주세요.")

        else:  # 로그인
            if st.button("로그인 🔄", use_container_width=True):
                if not input_id or not input_pw:
                    st.warning("아이디와 비밀번호를 입력해주세요.")
                else:
                    res = supabase.table("users").select("*").eq("user_id", input_id).execute()
                    if not res.data or res.data[0]["password_hash"] != hash_password(input_pw):
                        st.error("아이디 또는 비밀번호가 틀렸습니다.")
                    else:
                        st.session_state.user_id = input_id
                        p = load_personal_db(input_id)
                        if p:
                            st.session_state.my_events = p["events"]
                            st.session_state.my_timetable = p["timetable"]
                            st.session_state.my_joined_rooms = p["joined_rooms"]
                        st.success(f"🎉 '{input_id}'님 환영합니다!")
                        st.rerun()

    else:
        st.caption("고유 ID를 연동하면 내 시간표와 소속 그룹 목록이 자동으로 복구됩니다.")
        st.markdown(f"---\n🟢 로그인 중: **`{st.session_state.user_id}`**")
        if st.button("로그아웃", type="secondary", use_container_width=True):
            st.session_state.user_id = ""
            st.session_state.my_events = []
            st.session_state.my_timetable = []
            st.session_state.my_joined_rooms = {}
            st.session_state.app_page = "HOME"
            st.rerun()

        st.markdown("---")
        with st.expander("⚠️ 회원 탈퇴"):
            st.warning("탈퇴 시 모든 일정과 그룹 정보가 **영구 삭제**됩니다.")
            del_pw = st.text_input("비밀번호 확인", type="password", key="del_pw").strip()
            if st.button("회원 탈퇴 확인 🗑️", type="primary", use_container_width=True):
                if not del_pw:
                    st.error("비밀번호를 입력해주세요.")
                else:
                    uid = st.session_state.user_id
                    res = supabase.table("users").select("*").eq("user_id", uid).execute()
                    if not res.data or res.data[0]["password_hash"] != hash_password(del_pw):
                        st.error("비밀번호가 틀렸습니다.")
                    else:
                        # 참여 중인 그룹에서 멤버 제거
                        rooms = load_global_rooms()
                        nick = st.session_state.my_nickname
                        for code, info in rooms.items():
                            if nick and nick in info["members"]:
                                del info["members"][nick]
                                if not info["members"]:
                                    delete_room(code)
                                else:
                                    save_room(code, info["name"], info["members"])
                        # DB에서 계정 삭제
                        supabase.table("personal_data").delete().eq("user_id", uid).execute()
                        supabase.table("users").delete().eq("user_id", uid).execute()
                        # 세션 초기화
                        st.session_state.user_id = ""
                        st.session_state.my_events = []
                        st.session_state.my_timetable = []
                        st.session_state.my_joined_rooms = {}
                        st.session_state.my_nickname = ""
                        st.session_state.current_group_code = None
                        st.session_state.app_page = "HOME"
                        st.success("탈퇴가 완료되었습니다.")
                        st.rerun()


# ════════════════════════════════════════════════
# 1. 홈 화면 (반응형 HTML 달력 적용)
# ════════════════════════════════════════════════
def page_home():
    st.title("🤝 When We Meet")
    now = datetime.now()
    st.subheader(f"📅 {now.year}년 {now.month}월")

    cal_matrix = calendar.Calendar(firstweekday=6).monthdayscalendar(now.year, now.month)
    days = ["일", "월", "화", "수", "목", "금", "토"]

    home_cal_html = """
    <div style='overflow-x: auto; -webkit-overflow-scrolling: touch; margin-bottom: 20px;'>
      <table style='width:100%; min-width:450px; border-collapse:collapse; text-align:center; font-size:14px;'>
        <tr style='background-color:#F8FAFC; font-weight:bold; color:#475569;'>
    """
    for d in days:
        home_cal_html += f"<th style='padding:10px; border:1px solid #e2e8f0;'>{d}</th>"
    home_cal_html += "</tr>"

    for week in cal_matrix:
        home_cal_html += "<tr>"
        for day_num in week:
            if day_num != 0:
                if day_num == now.day:
                    home_cal_html += (
                        f"<td style='background-color:#EFF6FF; border:2px solid #3B82F6; "
                        f"padding:12px; font-weight:bold; color:#1E3A8A;'>{day_num}<br>"
                        f"<span style='color:#2563EB; font-size:10px;'>Today</span></td>"
                    )
                else:
                    home_cal_html += f"<td style='background-color:white; border:1px solid #e2e8f0; padding:12px; color:#334155;'>{day_num}</td>"
            else:
                home_cal_html += "<td style='border:1px solid #e2e8f0; background-color:#F8FAFC;'></td>"
        home_cal_html += "</tr>"
    home_cal_html += "</table></div>"

    st.markdown(home_cal_html, unsafe_allow_html=True)

    st.markdown("---")
    b1, b2 = st.columns(2)
    with b1:
        if st.button("나의 일정 (달력 / 시간표)", type="primary", use_container_width=True):
            st.session_state.app_page = "MY_CALENDAR"
            st.rerun()
    with b2:
        if st.button("📅 그룹 목록 / 약속 대조하기", use_container_width=True):
            st.session_state.app_page = "GROUP_LIST"
            st.rerun()


# ════════════════════════════════════════════════
# 2. 나의 일정 (개인 캘린더)
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

    st.title("📆 나의 일정 달력")
    if not st.session_state.user_id:
        st.warning("⚠️ 현재 비로그인 상태입니다. 왼쪽 사이드바에서 로그인해 주세요!")

    n1, n2, n3 = st.columns([1, 4, 1])
    with n1:
        if st.button("<", use_container_width=True):
            st.session_state.view_month -= 1
            if st.session_state.view_month == 0:
                st.session_state.view_month = 12
                st.session_state.view_year -= 1
            st.rerun()
    with n2:
        st.markdown(f"<h3 style='text-align:center;'>{st.session_state.view_year}년 {st.session_state.view_month}월</h3>", unsafe_allow_html=True)
    with n3:
        if st.button(">", use_container_width=True):
            st.session_state.view_month += 1
            if st.session_state.view_month == 13:
                st.session_state.view_month = 1
                st.session_state.view_year += 1
            st.rerun()

    cal_matrix = calendar.Calendar(firstweekday=6).monthdayscalendar(st.session_state.view_year, st.session_state.view_month)
    days = ["일", "월", "화", "수", "목", "금", "토"]

    cols = st.columns(7)
    for i, d in enumerate(days):
        cols[i].markdown(f"<center><b>{d}</b></center>", unsafe_allow_html=True)

    for week in cal_matrix:
        cols = st.columns(7)
        for idx, day_num in enumerate(week):
            if day_num != 0:
                date_str = f"{st.session_state.view_year}-{st.session_state.view_month:02d}-{day_num:02d}"
                cell_html = f"<div style='min-height:80px; border:1px solid #ddd; padding:5px; border-radius:5px; color:black;'><div style='font-weight:bold; font-size:14px;'>{day_num}</div>"

                day_events = [
                    (i, ev) for i, ev in enumerate(st.session_state.my_events)
                    if ev["start"].split()[0] <= date_str <= ev["end"].split()[0]
                ]

                for ev_i, ev in day_events:
                    color = ev.get("color", "#FFCDD2")
                    s_time = ev["start"].split()[1] if " " in ev["start"] else ""
                    e_time = ev["end"].split()[1] if " " in ev["end"] else ""
                    cell_html += f"<div style='background-color:{color}; font-size:10px; margin-top:2px; border-radius:3px; padding:2px; color:#333;'>🕐 {s_time}~{e_time} {ev['title']}</div>"

                cell_html += "</div>"
                cols[idx].markdown(cell_html, unsafe_allow_html=True)

                if cols[idx].button(f"+ 추가", key=f"add_btn_{date_str}"):
                    st.session_state.active_add_day = day_num
                    st.session_state.editing_event_idx = None

                for ev_i, ev in day_events:
                    if cols[idx].button(f"✏️ {ev['title'][:5]}", key=f"edit_ev_{date_str}_{ev_i}"):
                        st.session_state.editing_event_idx = ev_i
                        st.session_state.active_add_day = None
            else:
                cols[idx].write("")

    # 수정 및 추가 폼 섹션
    ev_idx = st.session_state.editing_event_idx
    if ev_idx is not None and 0 <= ev_idx < len(st.session_state.my_events):
        ev = st.session_state.my_events[ev_idx]
        st.markdown("---")
        st.subheader(f"📋 일정 상세 / 수정")
        try:
            s_parts = ev["start"].split()
            e_parts = ev["end"].split()
            s_d = datetime.strptime(s_parts[0], "%Y-%m-%d").date()
            s_t = datetime.strptime(s_parts[1], "%H:%M").time()
            e_d = datetime.strptime(e_parts[0], "%Y-%m-%d").date()
            e_t = datetime.strptime(e_parts[1], "%H:%M").time()
        except Exception:
            s_d, s_t = datetime.now().date(), datetime.strptime("09:00", "%H:%M").time()
            e_d, e_t = datetime.now().date(), datetime.strptime("18:00", "%H:%M").time()

        with st.form("edit_event_form"):
            new_title = st.text_input("일정 제목", value=ev["title"])
            new_s_date = st.date_input("시작 날짜", value=s_d)
            new_s_time = st.time_input("시작 시간", value=s_t)
            new_e_date = st.date_input("종료 날짜", value=e_d)
            new_e_time = st.time_input("종료 시간", value=e_t)
            col_save, col_del, col_cancel = st.columns(3)
            with col_save: saved = st.form_submit_button("💾 저장")
            with col_del: deleted = st.form_submit_button("🗑️ 삭제")
            with col_cancel: cancelled = st.form_submit_button("✖ 취소")

        if saved:
            st.session_state.my_events[ev_idx] = {
                "title": new_title,
                "start": f"{new_s_date} {new_s_time.strftime('%H:%M')}",
                "end": f"{new_e_date} {new_e_time.strftime('%H:%M')}",
                "color": ev.get("color", get_random_color()),
            }
            st.session_state.editing_event_idx = None
            _sync_my_events()
            st.rerun()
        elif deleted:
            st.session_state.my_events.pop(ev_idx)
            st.session_state.editing_event_idx = None
            _sync_my_events()
            st.rerun()
        elif cancelled:
            st.session_state.editing_event_idx = None
            st.rerun()

    add_day = st.session_state.active_add_day
    if add_day:
        st.markdown("---")
        st.subheader(f"➕ {add_day}일 일정 추가")
        with st.form("event_form"):
            ev_title = st.text_input("일정 제목")
            s_date = st.date_input("시작 날짜", value=datetime(st.session_state.view_year, st.session_state.view_month, add_day))
            s_time = st.time_input("시작 시간", value=datetime.strptime("09:00", "%H:%M").time())
            e_date = st.date_input("종료 날짜", value=datetime(st.session_state.view_year, st.session_state.view_month, add_day))
            e_time = st.time_input("종료 시간", value=datetime.strptime("18:00", "%H:%M").time())

            if st.form_submit_button("저장"):
                st.session_state.my_events.append({
                    "title": ev_title,
                    "start": f"{s_date} {s_time.strftime('%H:%M')}",
                    "end": f"{e_date} {e_time.strftime('%H:%M')}",
                    "color": get_random_color(),
                })
                st.session_state.active_add_day = None
                _sync_my_events()
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("⚙️ 고정 일정 섹션 (고정 시간표 페이지로 이동)", type="secondary", use_container_width=True):
        st.session_state.app_page = "FIXED_TIMETABLE"
        st.rerun()


# ════════════════════════════════════════════════
# 2-1. 고정 시간표 (모바일 가로스크롤 적용)
# ════════════════════════════════════════════════
def page_fixed_timetable():
    h_col1, h_col2 = st.columns([5, 1])
    with h_col2:
        if st.button("달력 보기", use_container_width=True):
            st.session_state.app_page = "MY_CALENDAR"
            st.rerun()

    st.title("🕞 고정 시간표 목록")

    with st.expander("➕ 누르면 고정 일정 추가 창 열림", expanded=st.session_state.fixed_expander_open):
        f_title = st.text_input("일정 제목", key="ft_title")
        f_day = st.selectbox("요일", ["월", "화", "수", "목", "금", "토", "일"], key="ft_day")
        f_start = st.text_input("시작 시각 (예: 09:15)", value="09:00", key="ft_start")
        f_end = st.text_input("종료 시각 (예: 11:45)", value="12:00", key="ft_end")

        if st.button("저장", key="ft_save", type="primary"):
            if f_title:
                st.session_state.my_timetable.append({
                    "title": f_title, "day": f_day, "start": f_start, "end": f_end, "color": get_random_color()
                })
                st.session_state.fixed_expander_open = False
                _sync_my_events()
                st.rerun()
            else:
                st.warning("일정 제목을 입력해주세요.")

    if st.session_state.my_timetable:
        st.markdown("### 📋 등록된 고정 일정")
        for ti, t in enumerate(st.session_state.my_timetable):
            color = t.get("color", "#BBDEFB")
            col_a, col_b = st.columns([5, 1])
            with col_a:
                st.markdown(f"<div style='background-color:{color}; padding:8px; border-radius:5px; margin-bottom:4px; color:#333;'><b>{t['title']}</b> | {t['day']}요일 {t['start']} ~ {t['end']}</div>", unsafe_allow_html=True)
            with col_b:
                if st.button("🗑️", key=f"del_tt_{ti}"):
                    st.session_state.my_timetable.pop(ti)
                    _sync_my_events()
                    st.rerun()

    st.write("### 📊 일주일 타임라인 도표 (15분 단위)")
    week_days_header = ["시간", "월", "화", "수", "목", "금", "토", "일"]

    table_html = (
        "<div style='overflow-x: auto; -webkit-overflow-scrolling: touch;'>"
        "<table style='width:100%; min-width:650px; border-collapse:collapse; text-align:center; font-size:12px; border:1px solid #ddd;'>"
        "<tr style='background-color:#F5F5F5; font-weight:bold; color:black;'>"
    )
    for d in week_days_header:
        table_html += f"<th style='border:1px solid #ddd; padding:8px;'>{d}</th>"
    table_html += "</tr>"

    for hour in range(24):
        for minute in [0, 15, 30, 45]:
            time_str = f"{hour:02d}:{minute:02d}"
            table_html += f"<tr><td style='border:1px solid #ddd; background-color:#FAFAFA; font-weight:bold; color:black;'>{time_str}</td>"
            for d_name in ["월", "화", "수", "목", "금", "토", "일"]:
                bg_color = "white"
                cell_text = ""
                for t in st.session_state.my_timetable:
                    if t["day"] == d_name and t["start"] <= time_str < t["end"]:
                        bg_color = t.get("color", "#BBDEFB")
                        cell_text = t["title"]
                table_html += f"<td style='border:1px solid #ddd; background-color:{bg_color}; color:#1565C0;'>{cell_text}</td>"
            table_html += "</tr>"
    table_html += "</table></div>"
    st.markdown(table_html, unsafe_allow_html=True)


# ════════════════════════════════════════════════
# 3. 그룹 목록 및 가입
# ════════════════════════════════════════════════
def page_group_list():
    st.title("👥 그룹 방 관리 패널")
    if st.button("< 홈으로 이동"):
        st.session_state.app_page = "HOME"
        st.rerun()

    st.markdown("### ➕ 그룹 신규 생성 및 코드 참여")
    g_action = st.radio("작업을 선택하세요", ["선택 안 함", "새로운 그룹 만들기", "코드로 그룹 입장하기"], horizontal=True)

    if g_action == "새로운 그룹 만들기":
        g_name = st.text_input("새로운 그룹명 입력")
        nickname = st.text_input("내 닉네임 설정 입력", value=st.session_state.user_id if st.session_state.user_id else "")
        if st.button("방 생성 및 입장 완료 🚀"):
            if g_name and nickname:
                rooms = load_global_rooms()
                while True:
                    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
                    if code not in rooms:
                        break
                save_room(code, g_name, {nickname: {"events": st.session_state.my_events, "timetable": st.session_state.my_timetable}})
                st.session_state.my_nickname = nickname
                st.session_state.current_group_code = code
                st.session_state.run_match = False
                st.session_state.my_joined_rooms[code] = nickname
                _sync_my_events()
                st.success(f"✅ 방 생성 완료! 입장 코드: **`{code}`**")
                st.session_state.app_page = "GROUP_ROOM"
                st.rerun()
            else:
                st.warning("그룹명과 닉네임을 모두 입력해주세요.")

    elif g_action == "코드로 그룹 입장하기":
        join_code = st.text_input("고유 입장 코드 5자리 입력").strip().upper()
        nickname = st.text_input("내 닉네임 설정 입력", value=st.session_state.user_id if st.session_state.user_id else "")
        if st.button("해당 코드 방 입장하기 🚪"):
            if join_code and nickname:
                rooms = load_global_rooms()
                if join_code in rooms:
                    members = rooms[join_code]["members"]
                    if nickname in members:
                        st.session_state.my_events = members[nickname].get("events", [])
                        st.session_state.my_timetable = members[nickname].get("timetable", [])
                    else:
                        members[nickname] = {"events": st.session_state.my_events, "timetable": st.session_state.my_timetable}
                        save_room(join_code, rooms[join_code]["name"], members)
                    st.session_state.my_nickname = nickname
                    st.session_state.current_group_code = join_code
                    st.session_state.run_match = False
                    st.session_state.my_joined_rooms[join_code] = nickname
                    _sync_my_events()
                    st.success(f"🎉 {nickname}님, 방에 입장했습니다!")
                    st.session_state.app_page = "GROUP_ROOM"
                    st.rerun()
                else:
                    st.error("존재하지 않는 코드입니다.")
            else:
                st.warning("코드와 닉네임을 모두 입력해 주세요.")

    st.markdown("---")
    st.subheader("🏠 내가 참여 중인 방 리스트")
    rooms = load_global_rooms()

    my_rooms_dict = st.session_state.my_joined_rooms
    active_my_rooms = {c: (rooms[c], nick) for c, nick in my_rooms_dict.items() if c in rooms}

    if not active_my_rooms:
        st.caption("현재 참여 중인 방이 없습니다.")
    else:
        for c, (info, nick) in active_my_rooms.items():
            col_r1, col_r2, col_r3 = st.columns([3, 1, 1])
            with col_r1:
                st.info(f"🏠 **{info['name']}** (코드: `{c}`) | 닉네임: `{nick}` | 참여: {len(info['members'])}명")
            with col_r2:
                if st.button("입장 🚪", key=f"enter_room_{c}", use_container_width=True):
                    st.session_state.current_group_code = c
                    st.session_state.my_nickname = nick
                    if nick in info["members"]:
                        st.session_state.my_events = info["members"][nick].get("events", [])
                        st.session_state.my_timetable = info["members"][nick].get("timetable", [])
                    st.session_state.app_page = "GROUP_ROOM"
                    st.session_state.run_match = False
                    st.rerun()
            with col_r3:
                if st.button("나가기 ❌", key=f"leave_room_{c}", use_container_width=True):
                    rooms2 = load_global_rooms()
                    if c in rooms2 and nick in rooms2[c]["members"]:
                        del rooms2[c]["members"][nick]
                        if not rooms2[c]["members"]:
                            delete_room(c)
                        else:
                            save_room(c, rooms2[c]["name"], rooms2[c]["members"])
                    del st.session_state.my_joined_rooms[c]
                    _sync_my_events()
                    st.success(f"'{info['name']}' 방에서 퇴장했습니다.")
                    st.rerun()


# ════════════════════════════════════════════════
# 4. 그룹 방 화면 (모바일 스크롤 완벽 최적화)
# ════════════════════════════════════════════════
def page_group_room():
    code = st.session_state.current_group_code
    rooms = load_global_rooms()
    g_info = rooms.get(code)

    if not g_info:
        st.error("방 정보를 찾을 수 없습니다.")
        if st.button("그룹 목록으로"):
            st.session_state.app_page = "GROUP_LIST"
            st.rerun()
        return

    st.title(f"🏢 그룹 방: {g_info['name']}")

    c_hdr1, c_hdr2, c_hdr3, c_hdr4 = st.columns([2, 1, 1, 1])
    with c_hdr1:
        if st.button("👥 참여자 목록 확인", use_container_width=True):
            st.write(f"현재 참여자 ({len(g_info['members'])}명): {', '.join(list(g_info['members'].keys()))}")
    with c_hdr2:
        st.warning(f"📋 코드: `{code}`")
    with c_hdr3:
        if st.button("< 그룹 목록", use_container_width=True):
            st.session_state.app_page = "GROUP_LIST"
            st.rerun()
    with c_hdr4:
        if st.button("🚪 그룹 나가기", type="secondary", use_container_width=True):
            nick = st.session_state.my_nickname
            rooms2 = load_global_rooms()
            if code in rooms2 and nick in rooms2[code]["members"]:
                del rooms2[code]["members"][nick]
                if not rooms2[code]["members"]:
                    delete_room(code)
                else:
                    save_room(code, rooms2[code]["name"], rooms2[code]["members"])
            if code in st.session_state.my_joined_rooms:
                del st.session_state.my_joined_rooms[code]
            _sync_my_events()
            st.session_state.current_group_code = None
            st.session_state.my_nickname = ""
            st.session_state.app_page = "GROUP_LIST"
            st.rerun()

    st.subheader("📅 전체 달력 현황 뷰")
    now = datetime.now()
    last_day = calendar.monthrange(now.year, now.month)[1]

    st.markdown("### 🔍 약속 조율 일정 대조 옵션")
    col_in1, col_in2, col_in3 = st.columns([2, 1, 2])
    with col_in1:
        date_range = st.date_input("조율할 시작일과 종료일", value=(datetime(now.year, now.month, 1), datetime(now.year, now.month, last_day)), key="match_date_range")
    with col_in2:
        min_h = st.number_input("최소 약속 시간 (시간)", min_value=1, max_value=24, value=2, key="match_min_h")
    with col_in3:
        preferred_time = st.slider("🕒 희망 시간 범위 선택", min_value=0, max_value=24, value=(10, 20), step=1, key="match_pref_time")

    if st.button("일정 대조하기 🚀", type="primary", use_container_width=True):
        st.session_state.run_match = True
        st.rerun()

    if not st.session_state.get("run_match", False):
        st.info("위의 버튼을 눌러 일정을 대조해보세요.")
        return

    if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
        start_date_picked, end_date_picked = date_range[0], date_range[1]
    else:
        start_date_picked = datetime(now.year, now.month, 1).date()
        end_date_picked = datetime(now.year, now.month, last_day).date()

    date_colors, free_slots_cache = {}, {}

    for d in range(1, last_day + 1):
        curr_loop_date = datetime(now.year, now.month, d).date()
        if curr_loop_date < start_date_picked or curr_loop_date > end_date_picked:
            continue

        w_str = ["월", "화", "수", "목", "금", "토", "일"][curr_loop_date.weekday()]
        slots = [False] * 24
        p_start, p_end = preferred_time
        for h in range(p_start, p_end):
            slots[h] = True

        for name, m_data in g_info["members"].items():
            for t in m_data.get("timetable", []):
                if t["day"] == w_str:
                    try:
                        sh, eh = int(t["start"].split(":")[0]), int(t["end"].split(":")[0])
                        for h in range(sh, eh):
                            slots[h] = False
                    except Exception:
                        pass
            for ev in m_data.get("events", []):
                d_str = f"{now.year}-{now.month:02d}-{d:02d}"
                if ev["start"].split()[0] <= d_str <= ev["end"].split()[0]:
                    try:
                        sh, eh = int(ev["start"].split()[1].split(":")[0]), int(ev["end"].split()[1].split(":")[0])
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
    cal_matrix = calendar.Calendar(firstweekday=6).monthdayscalendar(now.year, now.month)

    cols = st.columns(7)
    for i, d in enumerate(["일", "월", "화", "수", "목", "금", "토"]):
        cols[i].markdown(f"<center><b>{d}</b></center>", unsafe_allow_html=True)

    for week in cal_matrix:
        cols = st.columns(7)
        for idx, d_num in enumerate(week):
            if d_num != 0:
                bg = "white"
                if d_num in colors:
                    bg = "#C8E6C9" if colors[d_num] == "green" else "#FFCDD2"
                cols[idx].markdown(f"<div style='background-color:{bg}; text-align:center; padding:8px; border-radius:5px; border:1px solid #ddd; font-weight:bold; color:black; margin-bottom:2px;'>{d_num}</div>", unsafe_allow_html=True)
                if cols[idx].button("선택", key=f"g_day_{d_num}", use_container_width=True):
                    st.session_state.active_room_day = d_num
                    st.rerun()
            else:
                cols[idx].write("")

    st.markdown("---")
    st.subheader("📊 일주일 시간표 뷰 (공통 빈 시간대)")
    w_days_list = ["월", "화", "수", "목", "금", "토", "일"]

    w_table = (
        "<div style='overflow-x: auto; -webkit-overflow-scrolling: touch;'>"
        "<table style='width:100%; min-width:700px; text-align:center; font-size:11px; border-collapse:collapse;'>"
        "<tr style='background-color:#F5F5F5; color:black;'><th>요일/시간</th>"
    )
    for h in range(24):
        w_table += f"<th>{h:02d}</th>"
    w_table += "</tr>"

    for w_day in w_days_list:
        w_table += f"<tr><td style='font-weight:bold; border:1px solid #ddd; padding:5px; color:black;'>{w_day}</td>"
        for h in range(24):
            p_start, p_end = preferred_time
            if p_start <= h < p_end:
                is_free = True
                for name, m_data in g_info["members"].items():
                    for t in m_data.get("timetable", []):
                        if t["day"] == w_day:
                            try:
                                sh, eh = int(t["start"].split(":")[0]), int(t["end"].split(":")[0])
                                if sh <= h < eh:
                                    is_free = False
                            except Exception:
                                pass
            else:
                is_free = False
            bg = "#4CAF50" if is_free else "#F44336"
            w_table += f"<td style='background-color:{bg}; border:1px solid #ddd; width:25px;'></td>"
        w_table += "</tr>"
    w_table += "</table></div>"
    st.markdown(w_table, unsafe_allow_html=True)

    if "active_room_day" in st.session_state:
        sel_d = st.session_state.active_room_day
        st.markdown("---")
        st.subheader(f"📍 {sel_d}일 상세 가용 분석막대")

        slots = st.session_state.get("cached_slots", {}).get(sel_d, [False] * 24)

        bar_html = """
<div style='overflow-x: auto; -webkit-overflow-scrolling: touch;'>
  <div style='width:100%; min-width:600px; font-size:11px; padding-bottom:5px;'>
    <div style='display:flex; width:100%; height:40px; border:1px solid #aaa; margin-bottom:4px; box-sizing:border-box;'>
"""
        for s in slots:
            bg = "#4CAF50" if s else "#F44336"
            bar_html += f"<div style='flex:1; background-color:{bg}; border-right:1px solid white;'></div>"
        bar_html += "  </div>\n"

        bar_html += "  <div style='display:flex; width:100%; box-sizing:border-box;'>\n"
        for h in range(24):
            label = str(h) if h % 3 == 0 else ""
            bar_html += f"<div style='flex:1; text-align:center; color:#555; border-left:1px solid #ccc; line-height:1;'>{label}</div>\n"
        bar_html += "  </div>\n</div></div>"

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

if page == "HOME":
    page_home()
elif page == "MY_CALENDAR":
    page_my_calendar()
elif page == "FIXED_TIMETABLE":
    page_fixed_timetable()
elif page == "GROUP_LIST":
    page_group_list()
elif page == "GROUP_ROOM":
    page_group_room()
