import streamlit as st
import calendar
import random
import string
import threading
import json
import os
from datetime import datetime

# --- 페이지 기본 설정 ---
st.set_page_config(page_title="When We Meet", page_icon="📅", layout="wide")

# ────────────────────────────────────────────────
# 파일 기반 영구 데이터베이스 (그룹용 & 개인용)
# ────────────────────────────────────────────────
_LOCK = threading.Lock()
GROUP_DB_FILE = "shared_rooms.json"
PERSONAL_DB_FILE = "personal_schedules.json"

def load_global_rooms():
    """파일에서 전체 그룹 방 데이터를 읽어옴"""
    if os.path.exists(GROUP_DB_FILE):
        try:
            with open(GROUP_DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_global_rooms(rooms):
    """전체 그룹 방 데이터를 파일에 영구 저장"""
    with open(GROUP_DB_FILE, "w", encoding="utf-8") as f:
        json.dump(rooms, f, ensure_ascii=False, indent=4)

def load_personal_db():
    """파일에서 개인 일정 데이터를 읽어옴"""
    if os.path.exists(PERSONAL_DB_FILE):
        try:
            with open(PERSONAL_DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_personal_db(db):
    """개인 일정 데이터를 파일에 영구 저장"""
    with open(PERSONAL_DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=4)

# 색상 팔레트 (랜덤 bar 색상용)
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
        st.session_state.user_id = ""  # 개인 고유 ID 저장용
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
        st.session_state.my_joined_rooms = []

init_session()

def _sync_my_events():
    """내 일정 변경 시 실시간으로 파일 DB(개인 및 그룹)에 반영"""
    # 1. 개인 저장소 동기화
    user_id = st.session_state.user_id
    if user_id:
        with _LOCK:
            p_db = load_personal_db()
            p_db[user_id] = {
                "events": st.session_state.my_events,
                "timetable": st.session_state.my_timetable
            }
            save_personal_db(p_db)

    # 2. 활성화된 그룹 방 동기화
    nick = st.session_state.my_nickname
    code = st.session_state.current_group_code
    if nick and code:
        with _LOCK:
            rooms = load_global_rooms()
            if code in rooms and nick in rooms[code]["members"]:
                rooms[code]["members"][nick]["events"] = st.session_state.my_events
                rooms[code]["members"][nick]["timetable"] = st.session_state.my_timetable
                save_global_rooms(rooms)

# ────────────────────────────────────────────────
# 사이드바 패널 (개인 로그인 / 동기화)
# ────────────────────────────────────────────────
with st.sidebar:
    st.header("👤 개인 일정 동기화")
    st.caption("새로고침 후에도 나만의 일정(달력/시간표)을 유지하려면 고유 ID를 등록하고 불러오세요.")
    
    user_id_input = st.text_input("개인 고유 ID 입력", value=st.session_state.user_id).strip()
    
    if st.button("내 일정 불러오기 / 연동 🔄", use_container_width=True):
        if user_id_input:
            st.session_state.user_id = user_id_input
            with _LOCK:
                p_db = load_personal_db()
            if user_id_input in p_db:
                st.session_state.my_events = p_db[user_id_input].get("events", [])
                st.session_state.my_timetable = p_db[user_id_input].get("timetable", [])
                st.success(f"✅ '{user_id_input}'님의 개인 일정을 복구했습니다!")
            else:
                # 새 ID인 경우 현재 세션에 있는 일정을 기본으로 등록해줌
                with _LOCK:
                    p_db = load_personal_db()
                    p_db[user_id_input] = {
                        "events": st.session_state.my_events,
                        "timetable": st.session_state.my_timetable
                    }
                    save_personal_db(p_db)
                st.success(f"✨ '{user_id_input}'님으로 새로운 개인 ID가 등록되었습니다!")
            st.rerun()
        else:
            st.warning("ID를 입력해 주세요.")
            
    if st.session_state.user_id:
        st.markdown(f"--- \n🟢 현재 연동된 ID: **`{st.session_state.user_id}`**")
        st.caption("작성하시는 모든 달력/시간표 일정이 이 ID에 실시간으로 자동 저장됩니다.")
        if st.button("연동 해제 (로그아웃)", type="secondary", use_container_width=True):
            st.session_state.user_id = ""
            st.session_state.my_events = []
            st.session_state.my_timetable = []
            st.session_state.app_page = "HOME"
            st.rerun()

# ════════════════════════════════════════════════
# 1. 홈 화면
# ════════════════════════════════════════════════
def page_home():
    st.title("🤝 When We Meet")
    now = datetime.now()
    st.subheader(f"📅 {now.year}년 {now.month}월")

    cal_matrix = calendar.Calendar(firstweekday=6).monthdayscalendar(now.year, now.month)
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
                        f"font-weight:bold; color:black;'>{day_num}<br><span style='color:blue; "
                        f"font-size:10px;'>Today</span></div>",
                        unsafe_allow_html=True
                    )
                else:
                    cols[idx].markdown(
                        f"<div style='background-color:white; text-align:center; "
                        f"padding:10px; border-radius:5px; border:1px solid #ddd; color:black;'>{day_num}</div>",
                        unsafe_allow_html=True
                    )
            else:
                cols[idx].write("")

    st.markdown("<br><br>", unsafe_allow_html=True)
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
        st.warning("⚠️ 현재 비로그인 상태입니다. 왼쪽 사이드바에서 개인 고유 ID를 연동하시면 새로고침해도 일정이 안전하게 저장됩니다!")

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

    cal_matrix = calendar.Calendar(firstweekday=6).monthdayscalendar(st.session_state.view_year, st.session_state.view_month)
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
                    f"padding:5px; border-radius:5px; color:black;'>"
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

    # 수정 폼
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
                st.session_state.my_events.append({
                    "title": ev_title,
                    "start": f"{s_date} {s_time.strftime('%H:%M')}",
                    "end": f"{e_date} {e_time.strftime('%H:%M')}",
                    "color": get_random_color(),
                })
                st.session_state.active_add_day = None
                _sync_my_events()
                st.rerun()

    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.button("⚙️ 고정 일정 섹션 (고정 시간표 페이지로 이동)", type="secondary", use_container_width=True):
        st.session_state.app_page = "FIXED_TIMETABLE"
        st.rerun()

# ════════════════════════════════════════════════
# 2-1. 고정 시간표
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
                st.session_state.my_timetable.append({
                    "title": f_title,
                    "day": f_day,
                    "start": f_start,
                    "end": f_end,
                    "color": get_random_color(),
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
                st.markdown(
                    f"<div style='background-color:{color}; padding:8px; border-radius:5px; "
                    f"margin-bottom:4px; color:#333;'> "
                    f"<b>{t['title']}</b> | {t['day']}요일 {t['start']} ~ {t['end']}</div>",
                    unsafe_allow_html=True
                )
            with col_b:
                if st.button("🗑️", key=f"del_tt_{ti}"):
                    st.session_state.my_timetable.pop(ti)
                    _sync_my_events()
                    st.rerun()

    st.write("### 📊 일주일 타임라인 도표 (15분 단위)")
    week_days_header = ["시간", "월", "화", "수", "목", "금", "토", "일"]

    table_html = (
        "<table style='width:100%; border-collapse:collapse; text-align:center; "
        "font-size:12px; border:1px solid #ddd;'>"
        "<tr style='background-color:#F5F5F5; font-weight:bold; color:black;'>"
    )
    for d in week_days_header:
        table_html += f"<th style='border:1px solid #ddd; padding:8px;'>{d}</th>"
    table_html += "</tr>"

    for hour in range(24):
        for minute in [0, 15, 30, 45]:
            time_str = f"{hour:02d}:{minute:02d}"
            table_html += (
                f"<tr><td style='border:1px solid #ddd; background-color:#FAFAFA; "
                f"font-weight:bold; color:black;'>{time_str}</td>"
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
# 3. 그룹 목록 및 가입
# ════════════════════════════════════════════════
def page_group_list():
    st.title("👥 그룹 방 관리 및 로그인 패널")
    if st.button("< 홈으로 이동"):
        st.session_state.app_page = "HOME"
        st.rerun()

    st.markdown("### ➕ 그룹 생성 및 기존 기록 불러오기")
    g_action = st.radio(
        "작업을 선택하세요",
        ["선택 안 함", "새로운 그룹 만들기", "코드로 그룹 입장하기 (또는 이어하기)"],
        horizontal=True
    )

    if g_action == "새로운 그룹 만들기":
        g_name = st.text_input("새로운 그룹명 입력")
        nickname = st.text_input("내 닉네임 설정 입력", value=st.session_state.user_id) # 개인 ID가 있으면 기본값으로 채워줌
        if st.button("방 생성 및 입장 완료 🚀"):
            if g_name and nickname:
                with _LOCK:
                    rooms = load_global_rooms()
                    while True:
                        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
                        if code not in rooms:
                            break
                    rooms[code] = {
                        "name": g_name,
                        "members": {
                            nickname: {
                                "events": st.session_state.my_events,
                                "timetable": st.session_state.my_timetable,
                            }
                        },
                    }
                    save_global_rooms(rooms)
                st.session_state.my_nickname = nickname
                st.session_state.current_group_code = code
                st.session_state.run_match = False
                if code not in st.session_state.my_joined_rooms:
                    st.session_state.my_joined_rooms.append(code)
                st.success(f"✅ 방 생성 완료! 친구에게 이 코드를 공유하세요: **`{code}`**")
                st.session_state.app_page = "GROUP_ROOM"
                st.rerun()
            else:
                st.warning("그룹명과 닉네임을 모두 입력해주세요.")

    elif g_action == "코드로 그룹 입장하기 (또는 이어하기)":
        st.info("💡 새로고침을 하셨다면, 이전에 사용하던 방 코드와 닉네임을 그대로 입력 시 일정이 자동으로 복구됩니다.")
        join_code = st.text_input("고유 입장 코드 5자리 입력").strip().upper()
        nickname = st.text_input("내 닉네임 설정 입력", value=st.session_state.user_id)
        if st.button("해당 코드 방 입장하기 🚪"):
            if join_code and nickname:
                with _LOCK:
                    rooms = load_global_rooms()
                if join_code in rooms:
                    with _LOCK:
                        if nickname in rooms[join_code]["members"]:
                            st.session_state.my_events = rooms[join_code]["members"][nickname].get("events", [])
                            st.session_state.my_timetable = rooms[join_code]["members"][nickname].get("timetable", [])
                            st.success(f"🔄 그룹 내 기존 기록({nickname})이 확인되어 일정을 성공적으로 복구했습니다!")
                        else:
                            rooms[join_code]["members"][nickname] = {
                                "events": st.session_state.my_events,
                                "timetable": st.session_state.my_timetable,
                            }
                            save_global_rooms(rooms)
                            st.success(f"🎉 {nickname}님, 새 멤버로 방에 입장했습니다!")
                    
                    st.session_state.my_nickname = nickname
                    st.session_state.current_group_code = join_code
                    st.session_state.run_match = False
                    if join_code not in st.session_state.my_joined_rooms:
                        st.session_state.my_joined_rooms.append(join_code)
                    st.session_state.app_page = "GROUP_ROOM"
                    st.rerun()
                else:
                    st.error("유효하지 않거나 존재하지 않는 코드입니다.")
            else:
                st.warning("코드와 닉네임을 모두 입력해 주세요.")

    st.markdown("---")
    st.subheader("내가 참여 중인 방 리스트")
    with _LOCK:
        rooms = load_global_rooms()
    my_codes = st.session_state.my_joined_rooms
    my_rooms = {c: rooms[c] for c in my_codes if c in rooms}
    
    if not my_rooms:
        st.caption("현재 세션에 활성화된 방이 없습니다. 새로고침을 하셨다면 위 메뉴에서 방 코드와 닉네임을 적어 이어하기를 해주세요.")
    else:
        for c, info in my_rooms.items():
            col_r1, col_r2 = st.columns([4, 1])
            with col_r1:
                st.info(f"🏠 **{info['name']}** (코드: `{c}`) | 참여 인원: {len(info['members'])}명")
            with col_r2:
                if st.button("입장", key=f"enter_room_{c}", use_container_width=True):
                    st.session_state.current_group_code = c
                    nick = st.session_state.my_nickname
                    if nick in info["members"]:
                        st.session_state.my_events = info["members"][nick].get("events", [])
                        st.session_state.my_timetable = info["members"][nick].get("timetable", [])
                    st.session_state.app_page = "GROUP_ROOM"
                    st.session_state.run_match = False
                    st.rerun()

# ════════════════════════════════════════════════
# 4. 그룹 방 화면
# ════════════════════════════════════════════════
def page_group_room():
    code = st.session_state.current_group_code
    with _LOCK:
        rooms = load_global_rooms()
    g_info = rooms.get(code)

    if not g_info:
        st.error("방 정보를 찾을 수 없습니다. (서버에서 만료되거나 삭제된 방일 수 있습니다)")
        if st.button("그룹 목록으로"):
            st.session_state.app_page = "GROUP_LIST"
            st.rerun()
        return

    st.title(f"🏢 그룹 방: {g_info['name']}")

    c_hdr1, c_hdr2, c_hdr3 = st.columns([3, 1, 1])
    with c_hdr1:
        if st.button("👥 참여자 목록 확인"):
            st.write(
                f"현재 참여자 ({len(g_info['members'])}명): "
                f"{', '.join(list(g_info['members'].keys()))}"
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
    col_in1, col_in2, col_in3 = st.columns([2, 1, 2])
    with col_in1:
        date_range = st.date_input(
            "조율할 시작일과 종료일",
            value=(datetime(now.year, now.month, 1), datetime(now.year, now.month, last_day)),
            key="match_date_range"
        )
    with col_in2:
        min_h = st.number_input("최소 약속 시간 (시간)", min_value=1, max_value=24, value=2, key="match_min_h")
    with col_in3:
        preferred_time = st.slider(
            "🕒 희망 시간 범위 선택",
            min_value=0, max_value=24, value=(10, 20), step=1, key="match_pref_time"
        )

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

    date_colors = {}
    free_slots_cache = {}

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
                
                cols[idx].markdown(
                    f"<div style='background-color:{bg}; text-align:center; "
                    f"padding:8px; border-radius:5px; border:1px solid #ddd; "
                    f"font-weight:bold; color:black; margin-bottom:2px;'>{d_num}</div>",
                    unsafe_allow_html=True
                )
                
                if cols[idx].button("선택", key=f"g_day_{d_num}", use_container_width=True):
                    st.session_state.active_room_day = d_num
                    st.rerun()
            else:
                cols[idx].write("")

    st.markdown("---")
    st.subheader("📊 일주일 시간표 뷰 (공통 빈 시간대)")
    w_days_list = ["월", "화", "수", "목", "금", "토", "일"]

    w_table = (
        "<table style='width:100%; text-align:center; font-size:11px; border-collapse:collapse;'>"
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
                                sh = int(t["start"].split(":")[0])
                                eh = int(t["end"].split(":")[0])
                                if sh <= h < eh:
                                    is_free = False
                            except Exception:
                                pass
            else:
                is_free = False
                
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
            st.error("해당 날짜에는 공통 가용 시간이 없습니다. (설정하신 희망 시간 범위를 확인해보세요)")

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