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
def get_supabase():
    # postgrest_py의 기본 Client import 에러 방지를 위해 문자열 타입 힌트 제거 및 필요시 로컬 참조하도록 처리
    from supabase import create_client, Client
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

# ════════════════════════════════════════════════
# 세션 상태 초기화
# ════════════════════════════════════════════════
if "app_page" not in st.session_state:
    st.session_state.app_page = "LOGIN"
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
if "group_id" not in st.session_state:
    st.session_state.group_id = None
if "group_name" not in st.session_state:
    st.session_state.group_name = ""
if "current_year" not in st.session_state:
    st.session_state.current_year = datetime.now(KST).year
if "current_month" not in st.session_state:
    st.session_state.current_month = datetime.now(KST).month

# 일정 수정/등록 관련 임시 상태
if "selected_date" not in st.session_state:
    st.session_state.selected_date = None
if "edit_event_id" not in st.session_state:
    st.session_state.edit_event_id = None

# DB 데이터 로컬 캐시 (매번 fetch하지 않도록)
if "db_user_events" not in st.session_state:
    st.session_state.db_user_events = []
if "db_timetable" not in st.session_state:
    st.session_state.db_timetable = []
if "db_group_members" not in st.session_state:
    st.session_state.db_group_members = {}

# ════════════════════════════════════════════════
# DB 연동 헬퍼 함수
# ════════════════════════════════════════════════
def load_user_data():
    """로그인한 유저의 모든 일정(events)과 타임테이블(timetable), 그리고 그룹 정보를 한 번에 로드"""
    uid = st.session_state.user_id
    gid = st.session_state.group_id
    if not uid:
        return

    # 1. 개인 일정 로드
    try:
        res = supabase.table("events").select("*").eq("user_id", uid).execute()
        st.session_state.db_user_events = res.data if res.data else []
    except Exception as e:
        st.error(f"일정 로드 실패: {e}")

    # 2. 개인 타임테이블 로드
    try:
        res_t = supabase.table("timetable").select("*").eq("user_id", uid).execute()
        st.session_state.db_timetable = res_t.data if res_t.data else []
    except Exception as e:
        st.error(f"타임테이블 로드 실패: {e}")

    # 3. 그룹 멤버 데이터 로드
    if gid:
        try:
            # 먼저 해당 그룹에 속한 유저 리스트 가져오기
            res_m = supabase.table("users").select("id", "name", "color").eq("group_id", gid).execute()
            members = res_m.data if res_m.data else []
            
            g_data = {}
            for m in members:
                m_id = m["id"]
                # 각 멤버의 이벤트와 타임테이블 가져오기
                res_e = supabase.table("events").select("*").eq("user_id", m_id).execute()
                res_tt = supabase.table("timetable").select("*").eq("user_id", m_id).execute()
                
                g_data[m_id] = {
                    "name": m["name"],
                    "color": m["color"] or "#4D96FF",
                    "events": res_e.data if res_e.data else [],
                    "timetable": res_tt.data if res_tt.data else []
                }
            st.session_state.db_group_members = g_data
        except Exception as e:
            st.error(f"그룹 데이터 로드 실패: {e}")

def require_login():
    if not st.session_state.user_id:
        st.session_state.app_page = "LOGIN"
        st.rerun()

# ════════════════════════════════════════════════
# 네비게이션 바 UI
# ════════════════════════════════════════════════
def render_navbar():
    st.markdown("""
        <style>
        .nav-container {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background-color: #f8f9fa;
            padding: 10px 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        .nav-title {
            font-size: 20px;
            font-weight: bold;
            color: #333;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # 상단 바 레이아웃 분할
    col_t, col_b1, col_b2, col_b3, col_b4 = st.columns([3, 1, 1, 1, 1])
    
    with col_t:
        g_name = st.session_state.group_name if st.session_state.group_id else "개인"
        st.markdown(f"### 📅 {st.session_state.user_name}님의 캘린더 <span style='font-size:14px; color:#666;'>({g_name} 그룹)</span>", unsafe_allow_html=True)
        
    with col_b1:
        if st.button("📆 내 달력 보기", use_container_width=True):
            st.session_state.app_page = "MY_CALENDAR"
            st.session_state.selected_date = None
            st.session_state.edit_event_id = None
            st.rerun()
            
    with col_b2:
        if st.button("👥 그룹 달력 보기", use_container_width=True):
            if not st.session_state.group_id:
                st.warning("소속된 그룹이 없습니다. 계정 설정에서 그룹을 생성하거나 참여하세요.")
            else:
                st.session_state.app_page = "GROUP_CALENDAR"
                st.session_state.selected_date = None
                st.session_state.edit_event_id = None
                st.rerun()
                
    with col_b3:
        if st.button("⚙️ 계정 / 그룹 설정", use_container_width=True):
            st.session_state.app_page = "ACCOUNT"
            st.rerun()
            
    with col_b4:
        if st.button("🚪 로그아웃", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()
    st.write("---")

# ════════════════════════════════════════════════
# 1. 로그인 / 회원가입 페이지
# ════════════════════════════════════════════════
def page_login():
    st.title("📅 When We Meet")
    st.subheader("언제 만날지, 고민하지 말고 한눈에!")
    
    tab1, tab2 = st.tabs(["로그인", "회원가입"])
    
    with tab1:
        st.markdown("### 로그인")
        login_id = st.text_input("아이디", key="login_id_input").strip()
        login_pw = st.text_input("비밀번호", type="password", key="login_pw_input").strip()
        
        if st.button("로그인", type="primary"):
            if not login_id or not login_pw:
                st.error("아이디와 비밀번호를 입력해주세요.")
                return
            
            hashed_pw = hashlib.sha256(login_pw.encode()).hexdigest()
            try:
                res = supabase.table("users").select("*").eq("login_id", login_id).eq("password", hashed_pw).execute()
                if res.data and len(res.data) > 0:
                    user = res.data[0]
                    st.session_state.user_id = user["id"]
                    st.session_state.user_name = user["name"]
                    st.session_state.group_id = user["group_id"]
                    
                    # 그룹명 가져오기
                    if user["group_id"]:
                        g_res = supabase.table("groups").select("name").eq("id", user["group_id"]).execute()
                        if g_res.data:
                            st.session_state.group_name = g_res.data[0]["name"]
                            
                    st.session_state.app_page = "MY_CALENDAR"
                    st.success(f"{user['name']}님 환영합니다!")
                    load_user_data()
                    st.rerun()
                else:
                    st.error("아이디 또는 비밀번호가 일치하지 않습니다.")
            except Exception as e:
                st.error(f"로그인 중 오류 발생: {e}")
                
    with tab2:
        st.markdown("### 회원가입")
        new_id = st.text_input("새 아이디", key="new_id_input").strip()
        new_pw = st.text_input("새 비밀번호", type="password", key="new_pw_input").strip()
        new_name = st.text_input("이름 (닉네임)", key="new_name_input").strip()
        
        if st.button("회원가입 완료"):
            if not new_id or not new_pw or not new_name:
                st.error("모든 필드를 입력해주세요.")
                return
            
            hashed_pw = hashlib.sha256(new_pw.encode()).hexdigest()
            rand_color = random.choice(COLOR_PALETTE)
            
            try:
                # 중복 확인
                chk = supabase.table("users").select("id").eq("login_id", new_id).execute()
                if chk.data and len(chk.data) > 0:
                    st.error("이미 존재하는 아이디입니다.")
                    return
                
                # 가입 진행
                supabase.table("users").insert({
                    "login_id": new_id,
                    "password": hashed_pw,
                    "name": new_name,
                    "color": rand_color
                }).execute()
                st.success("회원가입이 완료되었습니다! 로그인 탭에서 로그인해주세요.")
            except Exception as e:
                st.error(f"회원가입 중 오류 발생: {e}")

# ════════════════════════════════════════════════
# 2. 계정 / 그룹 설정 페이지
# ════════════════════════════════════════════════
def page_account():
    render_navbar()
    st.header("⚙️ 계정 및 그룹 설정")
    
    # 1. 개인 프로필 변경
    with st.expander("👤 개인 정보 관리", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**현재 이름:** {st.session_state.user_name}")
            ch_name = st.text_input("변경할 이름", value=st.session_state.user_name)
            if st.button("이름 변경 저장"):
                if ch_name.strip():
                    try:
                        supabase.table("users").update({"name": ch_name.strip()}).eq("id", st.session_state.user_id).execute()
                        st.session_state.user_name = ch_name.strip()
                        st.success("이름이 변경되었습니다.")
                        load_user_data()
                        st.rerun()
                    except Exception as e:
                        st.error(f"변경 실패: {e}")
        with col2:
            try:
                u_res = supabase.table("users").select("color").eq("id", st.session_state.user_id).execute()
                curr_color = u_res.data[0]["color"] if u_res.data else "#4D96FF"
            except:
                curr_color = "#4D96FF"
                
            st.markdown(f"**현재 고유 색상:** <span style='color:{curr_color}; font-weight:bold;'>■</span> {curr_color}", unsafe_allow_html=True)
            ch_color = st.color_picker("나만의 색상 선택", value=curr_color)
            if st.button("색상 변경 저장"):
                try:
                    supabase.table("users").update({"color": ch_color}).eq("id", st.session_state.user_id).execute()
                    st.success("색상이 변경되었습니다.")
                    load_user_data()
                    st.rerun()
                except Exception as e:
                    st.error(f"변경 실패: {e}")

    # 2. 그룹 생성 및 참여
    with st.expander("👥 그룹 관리 (생성 / 참여 / 탈퇴)", expanded=True):
        if st.session_state.group_id:
            st.subheader(f"현재 소속 그룹: '{st.session_state.group_name}'")
            
            # 그룹 코드 확인
            try:
                g_code_res = supabase.table("groups").select("code").eq("id", st.session_state.group_id).execute()
                g_code = g_code_res.data[0]["code"] if g_code_res.data else "없음"
            except:
                g_code = "오류"
                
            st.info(f"🔗 **그룹 초대 코드:** {g_code}  \n(친구에게 이 코드를 알려주면 그룹에 참여할 수 있습니다.)")
            
            # 현재 그룹 멤버 리스트 출력
            st.write("**그룹 멤버 목록:**")
            try:
                m_list = supabase.table("users").select("name", "color").eq("group_id", st.session_state.group_id).execute()
                if m_list.data:
                    for m in m_list.data:
                        st.markdown(f"- <span style='color:{m['color']}'>■</span> **{m['name']}**", unsafe_allow_html=True)
            except:
                st.write("멤버를 불러올 수 없습니다.")
                
            st.write("---")
            if st.button("🚨 그룹 탈퇴하기", type="secondary"):
                try:
                    supabase.table("users").update({"group_id": None}).eq("id", st.session_state.user_id).execute()
                    st.session_state.group_id = None
                    st.session_state.group_name = ""
                    st.success("그룹을 탈퇴했습니다.")
                    load_user_data()
                    st.rerun()
                except Exception as e:
                    st.error(f"탈퇴 실패: {e}")
        else:
            st.warning("현재 참여 중인 그룹이 없습니다. 아래에서 그룹을 새로 만들거나 초대 코드를 입력해 참여하세요.")
            
            tab_c, tab_j = st.tabs(["➕ 새 그룹 생성", "🔗 초대 코드로 참여"])
            with tab_c:
                g_new_name = st.text_input("새 그룹 이름 입력")
                if st.button("그룹 만들기"):
                    if g_new_name.strip():
                        # 랜덤 6자리 대문자+숫자 코드 생성
                        g_code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
                        try:
                            res_g = supabase.table("groups").insert({"name": g_new_name.strip(), "code": g_code}).execute()
                            if res_g.data:
                                new_gid = res_g.data[0]["id"]
                                # 유저 정보 갱신
                                supabase.table("users").update({"group_id": new_gid}).eq("id", st.session_state.user_id).execute()
                                st.session_state.group_id = new_gid
                                st.session_state.group_name = g_new_name.strip()
                                st.success(f"'{g_new_name}' 그룹이 생성되었습니다! 코드: {g_code}")
                                load_user_data()
                                st.rerun()
                        except Exception as e:
                            st.error(f"그룹 생성 실패: {e}")
            with tab_j:
                g_join_code = st.text_input("6자리 초대 코드 입력").strip().upper()
                if st.button("그룹 참여하기"):
                    if g_join_code:
                        try:
                            res_find = supabase.table("groups").select("*").eq("code", g_join_code).execute()
                            if res_find.data and len(res_find.data) > 0:
                                target_g = res_find.data[0]
                                supabase.table("users").update({"group_id": target_g["id"]}).eq("id", st.session_state.user_id).execute()
                                st.session_state.group_id = target_g["id"]
                                st.session_state.group_name = target_g["name"]
                                st.success(f"'{target_g['name']}' 그룹에 성공적으로 참여했습니다!")
                                load_user_data()
                                st.rerun()
                            else:
                                st.error("해당 코드를 가진 그룹을 찾을 수 없습니다.")
                        except Exception as e:
                            st.error(f"그룹 참여 실패: {e}")

    # 3. 고정 공강 / 타임테이블 설정 (주간 반복 일정)
    with st.expander("🕒 주간 고정 타임테이블 설정 (정기 공강 / 불가능한 시간대)", expanded=True):
        st.subheader("매주 반복되는 고정 스케줄 등록")
        st.caption("여기 등록한 시간은 그룹 달력 종합 뷰에서 '불가능한 시간'으로 차감되어 계산됩니다. (학교 수업, 고정 알바 등)")
        
        col_t1, col_t2 = st.columns([1, 2])
        with col_t1:
            st.markdown("##### **고정 일정 추가**")
            tt_day = st.selectbox("요일 선택", ["월", "화", "수", "목", "금", "토", "일"])
            tt_start = st.time_input("시작 시간", value=datetime.strptime("09:00", "%H:%M").time(), step=3600)
            tt_end = st.time_input("종료 시간", value=datetime.strptime("10:00", "%H:%M").time(), step=3600)
            tt_title = st.text_input("일정 명칭 (예: 캡스톤 디자인, 알바)")
            
            if st.button("➕ 고정 일정 추가"):
                sh = tt_start.hour
                eh = tt_end.hour
                if sh >= eh:
                    st.error("종료 시간은 시작 시간보다 늦어야 합니다.")
                else:
                    try:
                        supabase.table("timetable").insert({
                            "user_id": st.session_state.user_id,
                            "day": tt_day,
                            "start": f"{sh:02d}:00",
                            "end": f"{eh:02d}:00",
                            "title": tt_title.strip() or "고정 일정"
                        }).execute()
                        st.success("고정 일정이 추가되었습니다.")
                        load_user_data()
                        st.rerun()
                    except Exception as e:
                        st.error(f"고정 일정 추가 실패: {e}")
                        
        with col_t2:
            st.markdown("##### **현재 등록된 주간 고정 일정 목록**")
            tt_list = st.session_state.db_timetable
            if not tt_list:
                st.info("등록된 고정 일정이 없습니다.")
            else:
                # 요일 정렬용
                sorted_tt = sorted(tt_list, key=lambda x: (DAY_ORDER.get(x["day"], 0), x["start"]))
                for item in sorted_tt:
                    col_it1, col_it2 = st.columns([4, 1])
                    with col_it1:
                        st.markdown(f"**[{item['day']}요일]** {item['start']} ~ {item['end']}  |  *{item['title']}*")
                    with col_it2:
                        if st.button("❌ 삭제", key=f"del_tt_{item['id']}"):
                            try:
                                supabase.table("timetable").delete().eq("id", item["id"]).execute()
                                st.success("삭제되었습니다.")
                                load_user_data()
                                st.rerun()
                            except Exception as e:
                                st.error(f"삭제 실패: {e}")

# ════════════════════════════════════════════════
# 달력 랜더링 핵심 유틸 (HTML/CSS 기반 월간 달력)
# ════════════════════════════════════════════════
def render_calendar_html(year, month, events_by_date, is_group=False, group_members_data=None):
    """
    HTML Table 형태로 월간 달력을 정밀 렌더링.
    날짜 칸을 클릭하면 Streamlit의 세션 값을 바꾸도록 투명/미니멀 버튼 기법 적용 가능하나,
    여기서는 단순 직관적으로 '날짜 선택용 버튼 목록'을 사이드바나 하단에 배치하기 편하도록 
    달력 내부는 직관적 시각 자료로 완성도 높게 빌드합니다.
    """
    cal = calendar.Calendar()
    month_days = cal.monthdayscalendar(year, month)
    
    # CSS 스타일정의
    html = """
    <style>
    .cal-table { width: 100%; border-collapse: collapse; font-family: sans-serif; table-layout: fixed; }
    .cal-th { background-color: #f1f3f5; text-align: center; padding: 10px; font-weight: bold; border: 1px solid #dee2e6; width: 14.28%; }
    .cal-td { vertical-align: top; padding: 6px; border: 1px solid #dee2e6; height: 110px; background-color: #fff; }
    .cal-td-empty { background-color: #f8f9fa; border: 1px solid #dee2e6; }
    .cal-day-num { font-weight: bold; margin-bottom: 4px; font-size: 14px; }
    .cal-day-sun { color: #e03131; }
    .cal-day-sat { color: #1c7ed6; }
    .event-badge { 
        font-size: 11px; 
        padding: 2px 6px; 
        margin-bottom: 3px; 
        border-radius: 4px; 
        color: white; 
        overflow: hidden; 
        text-overflow: ellipsis; 
        white-space: nowrap;
        font-weight: 500;
    }
    </style>
    <table class='cal-table'>
        <tr>
            <th class='cal-th cal-day-num cal-day-sun'>일</th>
            <th class='cal-th'>월</th>
            <th class='cal-th'>화</th>
            <th class='cal-th'>수</th>
            <th class='cal-th'>목</th>
            <th class='cal-th'>금</th>
            <th class='cal-th cal-day-num cal-day-sat'>토</th>
        </tr>
    """
    
    for week in month_days:
        html += "<tr>"
        for idx, day in enumerate(week):
            if day == 0:
                html += "<td class='cal-td-empty'></td>"
            else:
                # 주말 색상 클래스 분류
                day_cls = ""
                if idx == 0: day_cls = " cal-day-sun"
                elif idx == 6: day_cls = " cal-day-sat"
                
                html += f"<td class='cal-td'><div class='cal-day-num{day_cls}'>{day}</div>"
                
                # 일정 출력
                date_str = f"{year}-{month:02d}-{day:02d}"
                day_events = events_by_date.get(date_str, [])
                
                for ev in day_events:
                    bg_color = ev.get("color", "#4D96FF")
                    title = ev.get("title", "일정")
                    disp_time = ""
                    if ev.get("start_time"):
                        disp_time = f"[{ev['start_time'][:5]}] "
                    
                    html += f"<div class='event-badge' style='background-color:{bg_color};' title='{title}'>{disp_time}{title}</div>"
                    
                html += "</td>"
        html += "</tr>"
    html += "</table>"
    return html

# ════════════════════════════════════════════════
# 3. 내 달력 보기 페이지 (개인 일정 마스터)
# ════════════════════════════════════════════════
def page_my_calendar():
    render_navbar()
    
    # 월 선택 컨트롤러
    c_yr = st.session_state.current_year
    c_mo = st.session_state.current_month
    
    col_m1, col_m2, col_m3, col_m4 = st.columns([2, 1, 1, 2])
    with col_m1:
        st.subheader(f"📅 {c_yr}년 {c_mo}월")
    with col_m2:
        if st.button("◀ 이전 달", use_container_width=True):
            if c_mo == 1:
                st.session_state.current_month = 12
                st.session_state.current_year -= 1
            else:
                st.session_state.current_month -= 1
            st.rerun()
    with col_m3:
        if st.button("다음 달 ▶", use_container_width=True):
            if c_mo == 12:
                st.session_state.current_month = 1
                st.session_state.current_year += 1
            else:
                st.session_state.current_month += 1
            st.rerun()
            
    # 개인 데이터를 날짜별 매핑 구조로 가공
    events_by_date = {}
    my_color = "#4D96FF"
    try:
        u_res = supabase.table("users").select("color").eq("id", st.session_state.user_id).execute()
        if u_res.data: my_color = u_res.data[0]["color"] or "#4D96FF"
    except: pass
    
    for ev in st.session_state.db_user_events:
        d_str = ev["date"]
        if d_str not in events_by_date:
            events_by_date[d_str] = []
        events_by_date[d_str].append({
            "id": ev["id"],
            "title": ev["title"],
            "start_time": ev["start_time"],
            "end_time": ev["end_time"],
            "color": my_color
        })
        
    # 달력 메인 화면 출력
    st.markdown(render_calendar_html(c_yr, c_mo, events_by_date), unsafe_allow_html=True)
    st.write("")
    
    # 레이아웃 하단 분할: [왼쪽] 날짜 선택 및 내 일정 현황, [오른쪽] 등록/수정 폼
    col_left, col_right = st.columns([1, 1])
    
    with col_left:
        st.mark_highlight = "💛"
        st.markdown("### 💛 나의 일정 상세 확인")
        
        # 날짜를 선택할 수 있도록 날짜 선택기 제공
        chosen_date = st.date_input(
            "상세 조회를 원하는 날짜를 선택하세요", 
            value=st.session_state.selected_date if st.session_state.selected_date else date_type(c_yr, c_mo, 1)
        )
        
        if chosen_date:
            st.session_state.selected_date = chosen_date
            
        sel_date_str = st.session_state.selected_date.strftime("%Y-%m-%d")
        st.markdown(f"##### **{sel_date_str}의 스케줄 목록**")
        
        day_evs = events_by_date.get(sel_date_str, [])
        if not day_evs:
            st.info("이 날짜에 등록된 일정이 없습니다.")
        else:
            for ev in sorted(day_evs, key=lambda x: x["start_time"] or ""):
                t_info = "하루 종일"
                if ev["start_time"]:
                    t_info = f"{ev['start_time'][:5]} ~ {ev['end_time'][:5]}"
                
                col_e1, col_e2, col_e3 = st.columns([3, 1, 1])
                with col_e1:
                    st.markdown(f"• **{ev['title']}** ({t_info})")
                with col_e2:
                    if st.button("✏️ 수정", key=f"edit_btn_{ev['id']}"):
                        st.session_state.edit_event_id = ev["id"]
                        st.rerun()
                with col_e3:
                    if st.button("🗑️ 삭제", key=f"del_btn_{ev['id']}"):
                        try:
                            supabase.table("events").delete().eq("id", ev["id"]).execute()
                            st.success("일정이 삭제되었습니다.")
                            load_user_data()
                            st.rerun()
                        except Exception as e:
                            st.error(f"삭제 오류: {e}")

    with col_right:
        # 수정 모드인지 신규 등록 모드인지 식별
        if st.session_state.edit_event_id:
            st.markdown("### ✏️ 일정 수정하기")
            # 기존 값 확보
            target_ev = next((x for x in st.session_state.db_user_events if x["id"] == st.session_state.edit_event_id), None)
            if not target_ev:
                st.session_state.edit_event_id = None
                st.rerun()
                
            ed_title = st.text_input("일정명 수정", value=target_ev["title"])
            
            # 시간 파싱 안전 처리
            def p_time(t_str):
                try: return datetime.strptime(t_str, "%H:%M:%S").time()
                except: return datetime.strptime("09:00", "%H:%M").time()
                
            ed_start = st.time_input("시작 시간 수정", value=p_time(target_ev["start_time"]), step=1800)
            ed_end = st.time_input("종료 시간 수정", value=p_time(target_ev["end_time"]), step=1800)
            
            col_ed_b1, col_ed_b2 = st.columns([1, 1])
            with col_ed_b1:
                if st.button("💾 변경사항 저장", type="primary"):
                    if not ed_title.strip():
                        st.error("일정 명칭을 입력해주세요.")
                    else:
                        try:
                            supabase.table("events").update({
                                "title": ed_title.strip(),
                                "start_time": ed_start.strftime("%H:%M:00"),
                                "end_time": ed_end.strftime("%H:%M:00")
                            }).eq("id", st.session_state.edit_event_id).execute()
                            st.success("수정 완료!")
                            st.session_state.edit_event_id = None
                            load_user_data()
                            st.rerun()
                        except Exception as e:
                            st.error(f"수정 실패: {e}")
            with col_ed_b2:
                # 취소 버튼 기능이 모호하여 요청에 따라 삭제했습니다.
                pass
        else:
            st.markdown("### ➕ 새 일정 추가")
            reg_date_str = st.session_state.selected_date.strftime("%Y-%m-%d") if st.session_state.selected_date else datetime.now(KST).strftime("%Y-%m-%d")
            st.caption(f"선택된 날짜: **{reg_date_str}**")
            
            new_title = st.text_input("일정 명칭 입력", placeholder="예: 미팅, 과제 회의, 데이트")
            new_start = st.time_input("시작 시간", value=datetime.strptime("12:00", "%H:%M").time(), step=1800)
            new_end = st.time_input("종료 시간", value=datetime.strptime("13:00", "%H:%M").time(), step=1800)
            
            if st.button("🗓️ 일정 등록하기", type="primary", use_container_width=True):
                if not new_title.strip():
                    st.error("일정 이름을 입력해 주세요.")
                elif new_start >= new_end:
                    st.error("종료 시간은 시작 시간보다 이후여야 합니다.")
                else:
                    try:
                        supabase.table("events").insert({
                            "user_id": st.session_state.user_id,
                            "date": reg_date_str,
                            "title": new_title.strip(),
                            "start_time": new_start.strftime("%H:%M:00"),
                            "end_time": new_end.strftime("%H:%M:00")
                        }).execute()
                        st.success("일정이 성공적으로 등록되었습니다!")
                        load_user_data()
                        st.rerun()
                    except Exception as e:
                        st.error(f"등록 실패: {e}")

# ════════════════════════════════════════════════
# 4. 그룹 달력 종합 보기 페이지 (When We Meet의 핵심)
# ════════════════════════════════════════════════
def page_group_calendar():
    render_navbar()
    
    if not st.session_state.group_id:
        st.warning("소속된 그룹이 없습니다. 계정 설정에서 그룹을 생성하거나 참여해주세요.")
        return
        
    c_yr = st.session_state.current_year
    c_mo = st.session_state.current_month
    
    st.subheader(f"👥 '{st.session_state.group_name}' 그룹 통합 스케줄 현황")
    
    col_m1, col_m2, col_m3 = st.columns([4, 1, 1])
    with col_m1:
        st.markdown(f"#### 🗓️ {c_yr}년 {c_mo}월 종합 뷰")
    with col_m2:
        if st.button("◀ 이전 달 ", key="g_prev"):
            if c_mo == 1:
                st.session_state.current_month = 12
                st.session_state.current_year -= 1
            else:
                st.session_state.current_month -= 1
            st.rerun()
    with col_m3:
        if st.button("다음 달 ▶ ", key="g_next"):
            if c_mo == 12:
                st.session_state.current_month = 1
                st.session_state.current_year += 1
            else:
                st.session_state.current_month += 1
            st.rerun()

    # 모든 그룹 멤버의 이벤트를 단일 캘린더 데이터 세트로 병합
    g_members = st.session_state.db_group_members
    merged_events = {}
    
    for m_id, m_data in g_members.items():
        m_color = m_data["color"]
        m_name = m_data["name"]
        
        for ev in m_data.get("events", []):
            d_str = ev["date"]
            if d_str not in merged_events:
                merged_events[d_str] = []
            merged_events[d_str].append({
                "title": f"{m_name}: {ev['title']}",
                "start_time": ev["start_time"],
                "end_time": ev["end_time"],
                "color": m_color
            })
            
    # 종합 달력 출력
    st.markdown(render_calendar_html(c_yr, c_mo, merged_events, is_group=True, group_members_data=g_members), unsafe_allow_html=True)
    st.write("---")
    
    # 그룹 빈자리(모두가 안바쁜 시간) 추천 기능 고도화
    st.subheader("💡 우리 언제 만날까? 추천 빈시간 계산기")
    st.caption("선택한 날짜에 그룹원 전체의 개인 일정과 고정 공강 타임테이블을 종합하여, 아무도 일정이 없는 골든 타임을 찾아줍니다.")
    
    calc_date = st.date_input("빈 시간 매칭을 진행할 날짜 선택", value=date_type(c_yr, c_mo, 1), key="calc_date_picker")
    
    # 시간 분석 범위 (오전 9시 ~ 오후 10시)
    hours_range = range(9, 22) 
    w_day_idx = calc_date.weekday() # 0=월, 1=화...
    day_kor_map = {0: "월", 1: "화", 2: "수", 3: "목", 4: "금", 5: "토", 6: "일"}
    w_day = day_kor_map[w_day_idx]
    
    calc_date_str = calc_date.strftime("%Y-%m-%d")
    
    # 각 시간대별로 불가능한 사람 체크
    st.markdown(f"##### **{calc_date_str} ({w_day}요일) 시간대별 모임 가능 여부**")
    
    # HTML 타임라인 보드 생성
    w_table = "<div style='overflow-x:auto;'><table style='width:100%;text-align:center;border-collapse:collapse;font-size:13px;'>"
    w_table += "<tr style='background-color:#f1f3f5;'>"
    w_table += "<th style='border:1px solid #ddd;padding:6px;'>구분</th>"
    for h in hours_range:
        w_table += f"<th style='border:1px solid #ddd;padding:6px;'>{h}시</th>"
    w_table += "</tr><tr>"
    w_table += f"<td style='border:1px solid #ddd;padding:6px;'>{w_day}</td>"
    for h in hours_range:
        is_free = True
        for name, m_data in g_members.items():
            # 1. 개인 일정 체크
            for ev in m_data.get("events", []):
                if ev["date"] == calc_date_str:
                    try:
                        sh = int(ev["start_time"].split(":")[0])
                        eh = int(ev["end_time"].split(":")[0])
                        if sh <= h < eh:
                            is_free = False
                    except: pass
            # 2. 고정 타임테이블 체크
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
elif page == "GROUP_CALENDAR":
    require_login(); load_user_data(); page_group_calendar()
