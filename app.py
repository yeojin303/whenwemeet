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
if "logged_in_user" not in st.session_state:
    st.session_state.logged_in_user = None
if "current_group_id" not in st.session_state:
    st.session_state.current_group_id = None
if "user_data" not in st.session_state:
    st.session_state.user_data = {"fixed_schedules": [], "timetable": []}

# ════════════════════════════════════════════════
# 헬퍼 함수 및 DB 연동
# ════════════════════════════════════════════════
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def generate_group_code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

def get_color_for_member(name: str) -> str:
    h = hashlib.md5(name.encode()).hexdigest()
    idx = int(h, 16) % len(COLOR_PALETTE)
    return COLOR_PALETTE[idx]

def load_user_data():
    if not st.session_state.logged_in_user:
        return
    u_id = st.session_state.logged_in_user["id"]
    try:
        res = supabase.table("users").select("fixed_schedules", "timetable").eq("id", u_id).execute()
        if res.data:
            st.session_state.user_data["fixed_schedules"] = res.data[0].get("fixed_schedules") or []
            st.session_state.user_data["timetable"] = res.data[0].get("timetable") or []
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")

def save_user_data():
    if not st.session_state.logged_in_user:
        return
    u_id = st.session_state.logged_in_user["id"]
    try:
        supabase.table("users").update({
            "fixed_schedules": st.session_state.user_data["fixed_schedules"],
            "timetable": st.session_state.user_data["timetable"]
        }).eq("id", u_id).execute()
    except Exception as e:
        st.error(f"데이터 저장 실패: {e}")

def require_login():
    if not st.session_state.logged_in_user:
        st.session_state.app_page = "LOGIN"
        st.rerun()

# ════════════════════════════════════════════════
# 네비게이션 바
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
            border-radius: 8px;
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
    
    col1, col2 = st.columns([2, 5])
    with col1:
        st.markdown(f"### 📅 When We Meet")
    with col2:
        sub_col1, sub_col2, sub_col3, sub_col4 = st.columns(4)
        with sub_col1:
            if st.button("🏠 홈 (그룹)", use_container_width=True):
                st.session_state.app_page = "HOME"
                st.rerun()
        with sub_col2:
            if st.button("🗓️ 나의 일정 관리", use_container_width=True):
                st.session_state.app_page = "MY_CALENDAR"
                st.rerun()
        with sub_col3:
            if st.button("👤 계정 설정", use_container_width=True):
                st.session_state.app_page = "ACCOUNT"
                st.rerun()
        with sub_col4:
            if st.button("🚪 로그아웃", use_container_width=True):
                st.session_state.logged_in_user = None
                st.session_state.current_group_id = None
                st.session_state.app_page = "LOGIN"
                st.rerun()
    st.markdown("---")

# ════════════════════════════════════════════════
# [페이지] 로그인 / 회원가입
# ════════════════════════════════════════════════
def page_login():
    st.title("📅 When We Meet")
    st.subheader("팀원들과의 완벽한 만남을 위한 일정 조율 서비스")
    
    tab1, tab2 = st.tabs(["로그인", "회원가입"])
    
    with tab1:
        with st.form("login_form"):
            login_id = st.text_input("아이디(이메일)", key="l_id").strip()
            login_pw = st.text_input("비밀번호", type="password", key="l_pw")
            submitted = st.form_submit_button("로그인", use_container_width=True)
            if submitted:
                if not login_id or not login_pw:
                    st.error("아이디와 비밀번호를 모두 입력해주세요.")
                else:
                    try:
                        res = supabase.table("users").select("*").eq("email", login_id).execute()
                        if res.data:
                            user = res.data[0]
                            if user["password"] == hash_password(login_pw):
                                st.session_state.logged_in_user = user
                                st.session_state.app_page = "HOME"
                                st.success(f"{user['username']}님 환영합니다!")
                                st.rerun()
                            else:
                                st.error("비밀번호가 일치하지 않습니다.")
                        else:
                            st.error("존재하지 않는 아이디입니다.")
                    except Exception as e:
                        st.error(f"로그인 오류: {e}")
                        
    with tab2:
        with st.form("signup_form"):
            new_id = st.text_input("아이디(이메일)", key="s_id").strip()
            new_name = st.text_input("이름 (실명 권장)", key="s_name").strip()
            new_pw = st.text_input("비밀번호", type="password", key="s_pw")
            new_pw_chk = st.text_input("비밀번호 확인", type="password", key="s_pw_chk")
            submitted = st.form_submit_button("회원가입", use_container_width=True)
            if submitted:
                if not new_id or not new_name or not new_pw:
                    st.error("모든 필드를 입력해주세요.")
                elif new_pw != new_pw_chk:
                    st.error("비밀번호가 일치하지 않습니다.")
                else:
                    try:
                        chk = supabase.table("users").select("id").eq("email", new_id).execute()
                        if chk.data:
                            st.error("이미 사용 중인 아이디입니다.")
                        else:
                            supabase.table("users").insert({
                                "email": new_id,
                                "username": new_name,
                                "password": hash_password(new_pw),
                                "fixed_schedules": [],
                                "timetable": []
                            }).execute()
                            st.success("회원가입이 완료되었습니다! 로그인 탭에서 로그인해주세요.")
                    except Exception as e:
                        st.error(f"회원가입 오류: {e}")

# ════════════════════════════════════════════════
# [페이지] 계정 설정
# ════════════════════════════════════════════════
def page_account():
    render_navbar()
    st.title("👤 계정 설정")
    user = st.session_state.logged_in_user
    
    st.markdown(f"**현재 로그인 계정:** {user['email']} ({user['username']} 님)")
    
    with st.form("update_profile_form"):
        st.subheader("이름 변경")
        new_name = st.text_input("새 이름", value=user['username']).strip()
        if st.form_submit_button("이름 저장"):
            if not new_name:
                st.error("이름을 입력해주세요.")
            else:
                try:
                    supabase.table("users").update({"username": new_name}).eq("id", user["id"]).execute()
                    st.session_state.logged_in_user["username"] = new_name
                    st.success("이름이 변경되었습니다.")
                    st.rerun()
                except Exception as e:
                    st.error(f"변경 실패: {e}")
                    
    with st.form("update_pw_form"):
        st.subheader("비밀번호 변경")
        cur_pw = st.text_input("현재 비밀번호", type="password")
        nxt_pw = st.text_input("새 비밀번호", type="password")
        nxt_pw_chk = st.text_input("새 비밀번호 확인", type="password")
        if st.form_submit_button("비밀번호 변경"):
            if hash_password(cur_pw) != user["password"]:
                st.error("현재 비밀번호가 틀렸습니다.")
            elif nxt_pw != nxt_pw_chk:
                st.error("새 비밀번호 확인이 일치하지 않습니다.")
            elif len(nxt_pw) < 4:
                st.error("비밀번호는 4자리 이상이어야 합니다.")
            else:
                try:
                    hpw = hash_password(nxt_pw)
                    supabase.table("users").update({"password": hpw}).eq("id", user["id"]).execute()
                    st.session_state.logged_in_user["password"] = hpw
                    st.success("비밀번호가 변경되었습니다.")
                except Exception as e:
                    st.error(f"변경 실패: {e}")

# ════════════════════════════════════════════════
# [페이지] 나의 일정 관리
# ════════════════════════════════════════════════
def page_my_calendar():
    render_navbar()
    st.title("🗓️ 나의 일정 관리")
    
    t1, t2 = st.tabs(["특정 날짜 일정 (달력형)", "매주 반복 일정 (타임테이블)"])
    
    # ------------------------------------------------
    # 탭 1: 특정 날짜 일정
    # ------------------------------------------------
    with t1:
        st.subheader("특정 날짜 일정 추가/관리")
        
        # 년/월 선택
        now_dt = datetime.now(KST)
        c_year = st.selectbox("년도", options=list(range(now_dt.year, now_dt.year+3)), index=0)
        c_month = st.selectbox("월", options=list(range(1, 13)), index=now_dt.month-1)
        
        cal_obj = calendar.Calendar()
        month_days = cal_obj.monthdayscalendar(c_year, c_month)
        
        # 현재 유저 일정 매핑
        schedules = st.session_state.user_data.get("fixed_schedules", [])
        sched_by_date = {}
        for s in schedules:
            try:
                dt = datetime.fromisoformat(s["date"]).date()
                sched_by_date.setdefault(dt, []).append(s)
            except Exception:
                pass
                
        # 달력 그리기
        st.markdown("""
            <style>
            .cal-table { width:100%; border-collapse:collapse; table-layout:fixed; }
            .cal-th { text-align:center; padding:5px; background-color:#eee; border:1px solid #ddd; font-weight:bold;}
            .cal-td { vertical-align:top; padding:5px; border:1px solid #ddd; height:100px; width:14.28%;}
            .day-num { font-weight:bold; margin-bottom:4px; }
            .sched-item { font-size:11px; padding:2px 4px; margin-bottom:2px; border-radius:3px; color:#white; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;}
            </style>
        """, unsafe_allow_html=True)
        
        days_html = "<table class='cal-table'><tr>"
        for w_name in ["일", "월", "화", "수", "목", "금", "토"]:
            color = "#ff4d4d" if w_name=="일" else ("#4d79ff" if w_name=="토" else "#333")
            days_html += f"<th class='cal-th' style='color:{color};'>{w_name}</th>"
        days_html += "</tr>"
        
        for week in month_days:
            days_html += "<tr>"
            for day in week:
                if day == 0:
                    days_html += "<td class='cal-td' style='background-color:#fafafa;'></td>"
                else:
                    cur_date = date_type(c_year, c_month, day)
                    day_scheds = sched_by_date.get(cur_date, [])
                    
                    bg_color = "#fff"
                    if cur_date == now_dt.date():
                        bg_color = "#e6f7ff"
                        
                    inner_html = f"<div class='day-num'>{day}</div>"
                    for ds in day_scheds:
                        title = ds.get("title", "일정")
                        sh = ds.get("start", "00:00")
                        inner_html += f"<div class='sched-item' style='background-color:#FFC300; color:#333;' title='{title} ({sh})'>{sh} {title}</div>"
                        
                    days_html += f"<td class='cal-td' style='background-color:{bg_color};'>{inner_html}</td>"
            days_html += "</tr>"
        days_html += "</table>"
        st.markdown(days_html, unsafe_allow_html=True)
        
        st.write("")
        
        # 일정 추가 & 리스트/수정/삭제 분할
        col_add, col_list = st.columns([1, 1])
        
        with col_add:
            st.markdown("### ➕ 새 일정 추가")
            with st.form("add_fixed_form", clear_on_submit=True):
                a_date = st.date_input("날짜", value=now_dt.date())
                a_title = st.text_input("일정명").strip()
                a_start = st.time_input("시작 시간", value=datetime.strptime("09:00", "%H:%M").time())
                a_end = st.time_input("종료 시간", value=datetime.strptime("10:00", "%H:%M").time())
                
                if st.form_submit_button("추가하기"):
                    if not a_title:
                        st.error("일정명을 입력해주세요.")
                    elif a_start >= a_end:
                        st.error("시작 시간이 종료 시간보다 빨라야 합니다.")
                    else:
                        new_item = {
                            "id": "f_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8)),
                            "date": a_date.isoformat(),
                            "title": a_title,
                            "start": a_start.strftime("%H:%M"),
                            "end": a_end.strftime("%H:%M")
                        }
                        st.session_state.user_data["fixed_schedules"].append(new_item)
                        save_user_data()
                        st.success("일정이 추가되었습니다.")
                        st.rerun()
                        
        with col_list:
            st.markdown("### 📋 등록된 일정 리스트")
            sorted_scheds = sorted(
                st.session_state.user_data.get("fixed_schedules", []),
                key=lambda x: (x.get("date", ""), x.get("start", ""))
            )
            
            if not sorted_scheds:
                st.info("등록된 일정이 없습니다.")
            else:
                for s in sorted_scheds:
                    s_id = s["id"]
                    # 수정 모드 활성화 여부 체크
                    edit_key = f"edit_active_{s_id}"
                    if edit_key not in st.session_state:
                        st.session_state[edit_key] = False
                        
                    if not st.session_state[edit_key]:
                        # 일반 조회 모드
                        with st.expander(f"{s['date']} | {s['start']}~{s['end']} : {s['title']}"):
                            c1, c2 = st.columns(2)
                            with c1:
                                if st.button("수정", key=f"btn_edit_{s_id}", use_container_width=True):
                                    st.session_state[edit_key] = True
                                    st.rerun()
                            with c2:
                                if st.button("삭제", key=f"btn_del_{s_id}", use_container_width=True):
                                    st.session_state.user_data["fixed_schedules"] = [
                                        x for x in st.session_state.user_data["fixed_schedules"] if x["id"] != s_id
                                    ]
                                    save_user_data()
                                    st.success("삭제되었습니다.")
                                    st.rerun()
                    else:
                        # 수정 폼 모드
                        with st.expander(f"{s['date']} | {s['title']} (수정 중)"):
                            with st.form(f"form_edit_{s_id}"):
                                e_date = st.date_input("날짜", value=datetime.fromisoformat(s["date"]).date(), key=f"e_date_{s_id}")
                                e_title = st.text_input("일정명", value=s["title"], key=f"e_title_{s_id}").strip()
                                e_start = st.time_input("시작", value=datetime.strptime(s["start"], "%H:%M").time(), key=f"e_start_{s_id}")
                                e_end = st.time_input("종료", value=datetime.strptime(s["end"], "%H:%M").time(), key=f"e_end_{s_id}")
                                
                                if st.form_submit_button("저장"):
                                    if not e_title:
                                        st.error("일정명을 입력해주세요.")
                                    elif e_start >= e_end:
                                        st.error("시작 시간이 종료 시간보다 빨라야 합니다.")
                                    else:
                                        # 데이터 업데이트
                                        for idx, item in enumerate(st.session_state.user_data["fixed_schedules"]):
                                            if item["id"] == s_id:
                                                st.session_state.user_data["fixed_schedules"][idx] = {
                                                    "id": s_id,
                                                    "date": e_date.isoformat(),
                                                    "title": e_title,
                                                    "start": e_start.strftime("%H:%M"),
                                                    "end": e_end.strftime("%H:%M")
                                                }
                                                break
                                        save_user_data()
                                        st.session_state[edit_key] = False
                                        st.success("수정되었습니다.")
                                        st.rerun()

    # ------------------------------------------------
    # 탭 2: 매주 반복 일정 (타임테이블)
    # ------------------------------------------------
    with t2:
        st.subheader("매주 정기적으로 안 되는 시간 지정 (요일/시간 단위)")
        st.caption("수업, 정기 회의, 알바 등 매주 고정되어 비울 수 없는 시간을 입력하세요.")
        
        hours_range = list(range(0, 24))
        
        col_t_add, col_t_view = st.columns([1, 1])
        
        with col_t_add:
            st.markdown("### ➕ 반복 일정 불가능 시간 추가")
            with st.form("add_tt_form", clear_on_submit=True):
                tt_day = st.selectbox("요일", ["월", "화", "수", "목", "금", "토", "일"])
                tt_sh = st.selectbox("시작 시각", hours_range, index=9)
                tt_eh = st.selectbox("종료 시각", hours_range, index=18)
                
                if st.form_submit_button("불가능 시간 추가"):
                    if tt_sh >= tt_eh:
                        st.error("시작 시간이 종료 시간보다 빨라야 합니다.")
                    else:
                        new_tt = {
                            "id": "t_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8)),
                            "day": tt_day,
                            "start": f"{tt_sh:02d}:00",
                            "end": f"{tt_eh:02d}:00"
                        }
                        st.session_state.user_data["timetable"].append(new_tt)
                        save_user_data()
                        st.success("반복 일정이 등록되었습니다.")
                        st.rerun()
                        
            # 리스트 및 개별 삭제
            st.markdown("### 📋 설정된 반복 불가능 리스트")
            tt_sorted = sorted(
                st.session_state.user_data.get("timetable", []),
                key=lambda x: (DAY_ORDER.get(x["day"], 0), x["start"])
            )
            if not tt_sorted:
                st.info("등록된 정기 반복 일정이 없습니다.")
            else:
                for t in tt_sorted:
                    t_id = t["id"]
                    col_item, col_btn = st.columns([3, 1])
                    with col_item:
                        st.markdown(f"**[{t['day']}요일]** {t['start']} ~ {t['end']}")
                    with col_btn:
                        if st.button("삭제", key=f"del_tt_{t_id}", use_container_width=True):
                            st.session_state.user_data["timetable"] = [
                                x for x in st.session_state.user_data["timetable"] if x["id"] != t_id
                            ]
                            save_user_data()
                            st.success("삭제 완료")
                            st.rerun()
                            
        with col_t_view:
            st.markdown("### 📊 주간 타임테이블 시각화")
            st.caption("🔴 빨간색 표시 영역이 내가 바쁘다고 등록한 시간입니다.")
            
            w_table = "<div style='overflow-x:auto;'><table style='width:100%; border-collapse:collapse; text-align:center; font-size:12px;'>"
            w_table += "<tr><th style='border:1px solid #ddd; padding:6px; background-color:#f2f2f2;'>요일</th>"
            for h in hours_range:
                w_table += f"<th style='border:1px solid #ddd; padding:4px; background-color:#f2f2f2;'>{h}시</th>"
            w_table += "</tr>"
            
            for w_day in ["월", "화", "수", "목", "금", "토", "일"]:
                w_table += f"<tr><td style='font-weight:bold; background-color:#f9f9f9; border:1px solid #ddd; padding:6px;'>{w_day}</td>"
                for h in hours_range:
                    is_busy = False
                    for t in st.session_state.user_data.get("timetable", []):
                        if t["day"] == w_day:
                            try:
                                sh = int(t["start"].split(":")[0])
                                eh = int(t["end"].split(":")[0])
                                if sh <= h < eh:
                                    is_busy = True
                            except Exception:
                                pass
                    bg = "#F44336" if is_busy else "#FFF"
                    w_table += f"<td style='background-color:{bg}; border:1px solid #ddd; height:24px;'></td>"
                w_table += "</tr>"
            w_table += "</table></div>"
            st.markdown(w_table, unsafe_allow_html=True)

# ════════════════════════════════════════════════
# [페이지] 홈 / 그룹 허브
# ════════════════════════════════════════════════
def page_home():
    render_navbar()
    user = st.session_state.logged_in_user
    
    st.title(f"🏠 {user['username']} 님의 그룹 대시보드")
    
    col_g1, col_g2 = st.columns([1, 1])
    
    with col_g1:
        st.subheader("🧱 새 그룹 만들기")
        with st.form("create_group_form", clear_on_submit=True):
            g_name = st.text_input("그룹 이름").strip()
            if st.form_submit_button("그룹 생성"):
                if not g_name:
                    st.error("그룹 이름을 입력해주세요.")
                else:
                    try:
                        code = generate_group_code()
                        supabase.table("groups").insert({
                            "group_name": g_name,
                            "group_code": code,
                            "creator_id": user["id"],
                            "members": [user["id"]]
                        }).execute()
                        st.success(f"그룹 [{g_name}]이 생성되었습니다! 입장 코드: {code}")
                    except Exception as e:
                        st.error(f"생성 실패: {e}")
                        
    with col_g2:
        st.subheader("🚪 기존 그룹 참여하기 (코드 입력)")
        with st.form("join_group_form", clear_on_submit=True):
            g_code = st.text_input("참여 코드 (6자리)").strip().upper()
            if st.form_submit_button("그룹 참여"):
                if not g_code:
                    st.error("코드를 입력해주세요.")
                else:
                    try:
                        res = supabase.table("groups").select("*").eq("group_code", g_code).execute()
                        if res.data:
                            group = res.data[0]
                            m_list = group.get("members") or []
                            if user["id"] in m_list:
                                st.warning("이미 참여 중인 그룹입니다.")
                            else:
                                m_list.append(user["id"])
                                supabase.table("groups").update({"members": m_list}).eq("id", group["id"]).execute()
                                st.success(f"[{group['group_name']}] 그룹에 성공적으로 참여했습니다.")
                        else:
                            st.error("해당 코드를 가진 그룹을 찾을 수 없습니다.")
                    except Exception as e:
                        st.error(f"참여 실패: {e}")
                        
    st.markdown("---")
    st.subheader("👥 참여 중인 그룹 목록")
    
    try:
        res = supabase.table("groups").select("*").execute()
        my_groups = []
        if res.data:
            for g in res.data:
                if user["id"] in (g.get("members") or []):
                    my_groups.append(g)
    except Exception as e:
        st.error(f"그룹 목록 조회 실패: {e}")
        my_groups = []
        
    if not my_groups:
        st.info("아직 속한 그룹이 없습니다. 그룹을 생성하거나 코드를 입력해 참여해보세요!")
        return
        
    # 그룹 그리드 배치
    g_cols = st.columns(3)
    for idx, g in enumerate(my_groups):
        with g_cols[idx % 3]:
            with st.container(border=True):
                st.markdown(f"### 👥 {g['group_name']}")
                st.markdown(f"**🔑 입장 코드:** `{g['group_code']}`")
                st.markdown(f"**👥 참여 인원:** {len(g.get('members') or [])}명")
                
                if st.button("📅 일정 조율하러 가기", key=f"go_g_{g['id']}", use_container_width=True, type="primary"):
                    st.session_state.current_group_id = g["id"]
                    st.session_state.app_page = "GROUP_DETAIL"
                    st.rerun()

# ════════════════════════════════════════════════
# [페이지] 그룹 내 상세 보기 및 조율 (종합 화면)
# ════════════════════════════════════════════════
def page_group_detail():
    if not st.session_state.current_group_id:
        st.session_state.app_page = "HOME"
        st.rerun()
        
    render_navbar()
    
    g_id = st.session_state.current_group_id
    user = st.session_state.logged_in_user
    
    try:
        g_res = supabase.table("groups").select("*").eq("id", g_id).execute()
        if not g_res.data:
            st.error("그룹 정보를 불러올 수 없습니다.")
            return
        group = g_res.data[0]
        
        m_ids = group.get("members") or []
        u_res = supabase.table("users").select("id", "username", "fixed_schedules", "timetable").in_("id", m_ids).execute()
        
        g_members = {}
        for u in u_res.data:
            g_members[u["id"]] = {
                "name": u["username"],
                "fixed_schedules": u.get("fixed_schedules") or [],
                "timetable": u.get("timetable") or []
            }
    except Exception as e:
        st.error(f"데이터 연동 실패: {e}")
        return
        
    st.title(f"👥 {group['group_name']}")
    st.markdown(f"**초대 코드:** `{group['group_code']}` | **소속 팀원:** {', '.join([m['name'] for m in g_members.values()])}")
    
    # 탭 구성: 1. 특정 날짜 조율, 2. 매주 정기 조율
    g_tab1, g_tab2 = st.tabs(["📅 특정 날짜 통합 일정", "⏳ 주간 고정 타임테이블 통합"])
    
    # ------------------------------------------------
    # 그룹 탭 1: 특정 날짜 통합 일정 (종합 캘린더)
    # ------------------------------------------------
    with g_tab1:
        st.subheader("특정 날짜 타겟 조율 캘린더")
        st.caption("선택한 월에 팀원들이 등록한 모든 일정(불가능 시간)이 종합되어 달력에 시각화됩니다.")
        
        now_dt = datetime.now(KST)
        g_year = st.selectbox("조율 년도", options=list(range(now_dt.year, now_dt.year+3)), index=0, key="g_yr")
        g_month = st.selectbox("조율 월", options=list(range(1, 13)), index=now_dt.month-1, key="g_mo")
        
        cal_obj = calendar.Calendar()
        month_days = cal_obj.monthdayscalendar(g_year, g_month)
        
        # 전체 팀원 고정 일정 날짜별 바인딩
        all_fixed_by_date = {}
        for m_id, m_data in g_members.items():
            for s in m_data.get("fixed_schedules", []):
                try:
                    d_obj = datetime.fromisoformat(s["date"]).date()
                    all_fixed_by_date.setdefault(d_obj, []).append({
                        "user_id": m_id,
                        "name": m_data["name"],
                        "title": s["title"],
                        "start": s["start"],
                        "end": s["end"]
                    })
                except Exception:
                    pass
                    
        # 달력 렌더링
        st.markdown("""
            <style>
            .g-cal-table { width:100%; border-collapse:collapse; table-layout:fixed; }
            .g-cal-th { text-align:center; padding:6px; background-color:#eaeaea; border:1px solid #ccc; font-weight:bold;}
            .g-cal-td { vertical-align:top; padding:4px; border:1px solid #ccc; height:120px; width:14.28%; position:relative;}
            .g-day-num { font-weight:bold; margin-bottom:4px;}
            .g-sched-badge { font-size:10px; padding:1px 3px; margin-bottom:2px; border-radius:3px; color:white; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-weight:500;}
            </style>
        """, unsafe_allow_html=True)
        
        g_days_html = "<table class='g-cal-table'><tr>"
        for w_name in ["일", "월", "화", "수", "목", "금", "토"]:
            color = "#ff4d4d" if w_name=="일" else ("#4d79ff" if w_name=="토" else "#333")
            g_days_html += f"<th class='g-cal-th' style='color:{color};'>{w_name}</th>"
        g_days_html += "</tr>"
        
        for week in month_days:
            g_days_html += "<tr>"
            for day in week:
                if day == 0:
                    g_days_html += "<td class='g-cal-td' style='background-color:#fdfdfd;'></td>"
                else:
                    cur_date = date_type(g_year, g_month, day)
                    day_items = all_fixed_by_date.get(cur_date, [])
                    
                    bg_color = "#fff"
                    if cur_date == now_dt.date():
                        bg_color = "#eaf8ff"
                        
                    inner_html = f"<div class='g-day-num'>{day}</div>"
                    
                    # 시간순 정렬하여 보여주기
                    day_items_sorted = sorted(day_items, key=lambda x: x["start"])
                    for item in day_items_sorted:
                        u_color = get_color_for_member(item["name"])
                        inner_html += f"<div class='g-sched-badge' style='background-color:{u_color};' title='[{item['name']}] {item['start']}~{item['end']} {item['title']}'>{item['name']}: {item['title']}</div>"
                        
                    g_days_html += f"<td class='g-cal-td' style='background-color:{bg_color};'>{inner_html}</td>"
            g_days_html += "</tr>"
        g_days_html += "</table>"
        st.markdown(g_days_html, unsafe_allow_html=True)
        
        # 하단 날짜별 정밀 타임라인 체크 도구
        st.write("")
        st.markdown("### 🔍 날짜별 팀원 타임라인 상세 분석")
        target_day = st.number_input("조회할 날짜(일) 입력", min_value=1, max_value=31, value=min(now_dt.day, 28))
        
        try:
            sel_date = date_type(g_year, g_month, target_day)
            st.markdown(f"#### 📅 {sel_date.strftime('%Y년 %m월 %d일')} 팀원 일정 상황")
            
            day_items = all_fixed_by_date.get(sel_date, [])
            
            # 24시간 타임라인 테이블로 빈 공간 찾기
            h_range = list(range(0, 24))
            tl_html = "<div style='overflow-x:auto;'><table style='width:100%; border-collapse:collapse; text-align:center; font-size:12px;'>"
            tl_html += "<tr><th style='border:1px solid #ddd; padding:8px; background-color:#f2f2f2; width:100px;'>이름</th>"
            for h in h_range:
                tl_html += f"<th style='border:1px solid #ddd; padding:4px; background-color:#f2f2f2;'>{h}시</th>"
            tl_html += "</tr>"
            
            # 각 팀원별 행 생성
            for m_id, m_data in g_members.items():
                tl_html += f"<tr><td style='font-weight:bold; border:1px solid #ddd; padding:6px; background-color:#fafafa;'>{m_data['name']}</td>"
                m_color = get_color_for_member(m_data["name"])
                
                for h in h_range:
                    is_busy = False
                    # 1) 특정 날짜 일정 체크
                    for it in day_items:
                        if it["user_id"] == m_id:
                            sh = int(it["start"].split(":")[0])
                            eh = int(it["end"].split(":")[0])
                            if sh <= h < eh:
                                is_busy = True
                    
                    # 2) 주간 정기 일정(해당 요일)도 동시 반영하여 빈틈 찾기
                    w_day_str = ["월", "화", "수", "목", "금", "토", "일"][sel_date.weekday()]
                    for t in m_data.get("timetable", []):
                        if t["day"] == w_day_str:
                            sh = int(t["start"].split(":")[0])
                            eh = int(t["end"].split(":")[0])
                            if sh <= h < eh:
                                is_busy = True
                                
                    bg = m_color if is_busy else "#FFF"
                    tl_html += f"<td style='background-color:{bg}; border:1px solid #ddd; height:22px;'></td>"
                tl_html += "</tr>"
                
            # 전체가 다 비어있는 시간(모두 초록색으로 표시할 수 있는 공통 시간) 행 추가
            tl_html += "<tr><td style='font-weight:bold; border:1px solid #ddd; padding:6px; background-color:#e6ffed; color:#2e7d32;'>모두 가능?</td>"
            for h in h_range:
                anyone_busy = False
                for m_id, m_data in g_members.items():
                    # 날짜 일정 체크
                    for it in day_items:
                        if it["user_id"] == m_id:
                            if int(it["start"].split(":")[0]) <= h < int(it["end"].split(":")[0]):
                                anyone_busy = True
                    # 요일 일정 체크
                    w_day_str = ["월", "화", "수", "목", "금", "토", "일"][sel_date.weekday()]
                    for t in m_data.get("timetable", []):
                        if t["day"] == w_day_str:
                            if int(t["start"].split(":")[0]) <= h < int(t["end"].split(":")[0]):
                                anyone_busy = True
                bg = "#4CAF50" if not anyone_busy else "#F44336"
                tl_html += f"<td style='background-color:{bg}; border:1px solid #ddd;'></td>"
            tl_html += "</tr>"
            
            tl_html += "</table></div>"
            st.markdown(tl_html, unsafe_allow_html=True)
            st.caption("🟢 초록색 시간대가 모든 팀원의 일정이 비어 있어 **만남이 가능한 시간**입니다.")
            
        except Exception as e:
            st.error(f"날짜 계산 오류: {e}")

    # ------------------------------------------------
    # 그룹 탭 2: 매주 정기 조율 (주간 고정 타임테이블 통합)
    # ------------------------------------------------
    with g_tab2:
        st.subheader("팀원 주간 공통 공강/비는 시간 찾기")
        st.caption("매주 반복되는 고정 일정들을 겹쳐서, 팀 전체가 동시에 공통으로 비는 시간을 추출합니다.")
        
        hours_range = list(range(0, 24))
        
        w_table = "<div style='overflow-x:auto;'><table style='width:100%; border-collapse:collapse; text-align:center; font-size:12px;'>"
        w_table += "<tr><th style='border:1px solid #ddd; padding:6px; background-color:#f2f2f2;'>요일</th>"
        for h in hours_range:
            w_table += f"<th style='border:1px solid #ddd; padding:4px; background-color:#f2f2f2;'>{h}시</th>"
        w_table += "</tr>"
        
        for w_day in ["월", "화", "수", "목", "금", "토", "일"]:
            w_table += f"<tr><td style='font-weight:bold; background-color:#f9f9f9; border:1px solid #ddd; padding:6px;'>{w_day}</td>"
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
                w_table += f"<td style='background-color:{bg}; border:1px solid #ddd; height:22px;'></td>"
            w_table += "</tr>"
        w_table += "</table></div>"
        st.markdown(w_table, unsafe_allow_html=True)
        st.caption("🟢 초록색: 전원 가용 가능 시간 | 🔴 빨간색: 최소 한 명 이상의 팀원이 불가능한 시간")


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
