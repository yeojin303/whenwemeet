import streamlit as pd
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os

# --- 파일 경로 설정 ---
SCHEDULE_FILE = "fixed_schedule.csv"
EXCEPTION_FILE = "exception_schedule.csv"

# --- 데이터 로드 및 저장 함수 ---
def load_data(file_path, columns):
    if os.path.exists(file_path):
        try:
            return pd.read_csv(file_path)
        except Exception:
            return pd.DataFrame(columns=columns)
    return pd.DataFrame(columns=columns)

def save_data(df, file_path):
    df.to_csv(file_path, index=False)

# --- 초기 데이터프레임 생성 ---
fixed_cols = ["요일", "시작시간", "종료시간", "일정명"]
exception_cols = ["날짜", "시작시간", "종료시간", "일정명", "유형"]

fixed_df = load_data(SCHEDULE_FILE, fixed_cols)
exception_df = load_data(EXCEPTION_FILE, exception_cols)

# --- 스트림릿 세션 상태 초기화 ---
if "fixed_df" not in st.session_state:
    st.session_state.fixed_df = fixed_df
if "exception_df" not in st.session_state:
    st.session_state.exception_df = exception_df
if "selected_date" not in st.session_state:
    st.session_state.selected_date = None
if "show_add_form" not in st.session_state:
    st.session_state.show_add_form = False

# --- UI 설정 ---
st.set_page_config(layout="wide")

# CSS를 이용해 전체적인 폰트 및 스타일 조정 (보라색 포인트)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap');
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Noto Sans KR', sans-serif;
        background-color: #F8F9FA;
    }
    .main-title {
        font-size: 28px;
        font-weight: 700;
        color: #4A148C;
        margin-bottom: 20px;
    }
    .sub-title {
        font-size: 18px;
        font-weight: 500;
        color: #6A1B9A;
        margin-top: 15px;
        margin-bottom: 10px;
    }
    .calendar-container {
        background-color: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    .day-box {
        border: 1px solid #E0E0E0;
        border-radius: 8px;
        padding: 10px;
        min-height: 100px;
        background-color: white;
        transition: all 0.2s;
    }
    .day-box:hover {
        border-color: #AB47BC;
        box-shadow: 0 2px 8px rgba(171, 71, 188, 0.2);
    }
    .today-box {
        border: 2px solid #7B1FA2 !important;
        background-color: #F3E5F5-50;
    }
    /* 버튼 스타일 커스텀 */
    div.stButton > button {
        border-radius: 8px;
    }
    </style>
""", unsafe_allow_value=True)

# --- 캘린더 생성 로직 ---
now = datetime.now()
current_year = now.year
current_month = now.month

# 월 변경 기능 (간단히 상단에 배치)
col1, col2, col3 = st.columns([1, 3, 1])
with col1:
    if st.button("◀ 이전 달"):
        # 이전달 이동 로직 (필요시 구현 가능)
        pass
with col2:
    st.markdown(f"<h1 style='text-align: center; color: #4A148C;'>📅 {current_year}년 {current_month}월 일정</h1>", unsafe_allow_value=True)
with col3:
    if st.button("다음 달 ▶"):
        # 다음달 이동 로직 (필요시 구현 가능)
        pass

# 달력 데이터 계산
first_day_of_month = datetime(current_year, current_month, 1)
start_diag = first_day_of_month - timedelta(days=first_day_of_month.weekday() if first_day_of_month.weekday() != 6 else 0) # 일요일 시작 기준 조율 필요시 수정 (현재는 월욜기준 예시에서 자동조정)
# 한국 정서에 맞게 일요일(6)부터 시작하도록 조정
start_weekday = first_day_of_month.weekday() # 0:월, 6:일
if start_weekday != 6: # 일요일이 아니면
    start_date = first_day_of_month - timedelta(days=start_weekday + 1)
else:
    start_date = first_day_of_month

days_letters = ["일", "월", "화", "수", "목", "금", "토"]

# 요일 헤더 출력
cols = st.columns(7)
for idx, day_letter in enumerate(days_letters):
    color = "#E53935" if idx == 0 else ("#1E88E5" if idx == 6 else "#333333")
    cols[idx].markdown(f"<h4 style='text-align: center; color: {color}; margin-bottom:5px;'>{day_letter}</h4>", unsafe_allow_value=True)

# 5주 혹은 6주 달력 그리기
current_plot_date = start_date
weekday_map = {0:"월", 1:"화", 2:"수", 3:"목", 4:"금", 5:"토", 6:"일"}

for week in range(6):
    cols = st.columns(7)
    for day_idx in range(7):
        # 이번 달 날짜인지 확인하여 색상 다르게 표시
        is_current_month = current_plot_date.month == current_month
        date_str = current_plot_date.strftime("%Y/%m/%d")
        
        # 오늘 날짜 확인
        is_today = current_plot_date.date() == now.date()
        
        # 해당 날짜의 고정 일정 + 예외 일정 취합
        day_wkd = weekday_map[current_plot_date.weekday()]
        day_fixed = st.session_state.fixed_df[st.session_state.fixed_df["요일"] == day_wkd]
        day_exceptions = st.session_state.exception_df[st.session_state.exception_df["날짜"] == date_str]
        
        with cols[day_idx]:
            # 날짜 박스 컨테이너
            box_class = "today-box" if is_today else ""
            opacity = "1.0" if is_current_month else "0.4"
            day_color = "#E53935" if day_idx == 0 else ("#1E88E5" if day_idx == 6 else "#212121")
            
            # 버튼으로 날짜 선택 가능하게 구현
            if st.button(f"{current_plot_date.day}", key=f"btn_{date_str}", help=f"{date_str} 일정 보기"):
                st.session_state.selected_date = date_str
                st.session_state.show_add_form = False
                st.rerun()
                
            # 간략 일정 표시 (최대 2개까지만 노출)
            display_count = 0
            # 고정 일정 중 제외(삭제)된 거 없는지 필터링 필요하나 여기선 단순 노출
            for _, row in day_fixed.iterrows():
                # 해당 날짜에 이 고정일정이 '제외'되었는지 체크
                is_excluded = not st.session_state.exception_df[
                    (st.session_state.exception_df["날짜"] == date_str) & 
                    (st.session_state.exception_df["일정명"] == row["일정명"]) & 
                    (st.session_state.exception_df["유형"] == "제외")
                ].empty
                
                if not is_excluded and display_count < 2:
                    st.markdown(f"<div style='font-size:11px; color:#7B1FA2; background-color:#F3E5F5; padding:2px 4px; border-radius:4px; margin-bottom:2px; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;'>📌 {row['일정명']}</div>", unsafe_allow_value=True)
                    display_count += 1
            
            for _, row in day_exceptions.iterrows():
                if row["유형"] == "추가" and display_count < 2:
                    st.markdown(f"<div style='font-size:11px; color:#C2185B; background-color:#FCE4EC; padding:2px 4px; border-radius:4px; margin-bottom:2px; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;'>➕ {row['일정명']}</div>", unsafe_allow_value=True)
                    display_count += 1
                    
        current_plot_date += timedelta(days=1)
    
    # 다음 달로 넘어가고 주가 끝나면 종료
    if current_plot_date.month != current_month and day_idx == 6:
        # 단, 최소 4줄 이상 그리도록 유도하거나 6주 다 채우기
        if week >= 4:
            break

st.markdown("---")

# --- 하단: 선택된 날짜의 세부 일정 및 관리 ---
if st.session_state.selected_date:
    sel_date = st.session_state.selected_date
    st.markdown(f"📌 **날짜를 선택하면 일정을 확인·추가할 수 있어요**")
    st.info(f"{sel_date}")
    
    # 상세 일정 박스
    st.markdown(f"### 📅 {sel_date.split('/')[0]}년 {int(sel_date.split('/')[1])}월 {int(sel_date.split('/')[2])}일")
    
    # 원래 이 자리에 있던 날짜 옆 'x' 우측 버튼 컴포넌트가 제거되었습니다.
    
    # 해당 날짜의 일정 가져오기
    dt_obj = datetime.strptime(sel_date, "%Y/%m/%d")
    sel_wkd = weekday_map[dt_obj.weekday()]
    
    day_fixed = st.session_state.fixed_df[st.session_state.fixed_df["요일"] == sel_wkd]
    day_exceptions = st.session_state.exception_df[st.session_state.exception_df["날짜"] == sel_date]
    
    # 실제 노출할 최종 일정 리스트 조립
    final_schedules = []
    
    for _, row in day_fixed.iterrows():
        is_excluded = not st.session_state.exception_df[
            (st.session_state.exception_df["날짜"] == sel_date) & 
            (st.session_state.exception_df["일정명"] == row["일정명"]) & 
            (st.session_state.exception_df["유형"] == "제외")
        ].empty
        if not is_excluded:
            final_schedules.append({
                "일정명": row["일정명"],
                "시작시간": row["시작시간"],
                "종료시간": row["종료시간"],
                "유형": "고정 일정"
            })
            
    for _, row in day_exceptions.iterrows():
        if row["유형"] == "추가":
            final_schedules.append({
                "일정명": row["일정명"],
                "시작시간": row["시작시간"],
                "종료시간": row["종료시간"],
                "유형": "새 일시적 일정"
            })
            
    # 일정 출력
    if final_schedules:
        for idx, sched in enumerate(final_schedules):
            col_icon, col_txt, col_del = st.columns([1, 8, 2])
            with col_icon:
                st.write("⏰" if sched["유형"] == "고정 일정" else "⭐")
            with col_txt:
                st.markdown(f"**{sched['시작시간']} ~ {sched['종료시간']}** | {sched['일정명']} ({sched['유형']})")
            with col_del:
                if st.button("삭제", key=f"del_{sel_date}_{idx}"):
                    if sched["유형"] == "고정 일정":
                        # 고정 일정을 이 날짜에서 제외하기 위해 제외 레코드 추가
                        new_ex = pd.DataFrame([{
                            "날짜": sel_date,
                            "시작시간": sched["시작시간"],
                            "종료시간": sched["종료시간"],
                            "일정명": sched["일정명"],
                            "유형": "제외"
                        }])
                        st.session_state.exception_df = pd.concat([st.session_state.exception_df, new_ex], ignore_index=True)
                        save_data(st.session_state.exception_df, EXCEPTION_FILE)
                    else:
                        # 추가된 예외 일정을 리스트에서 직접 삭제
                        st.session_state.exception_df = st.session_state.exception_df[
                            ~((st.session_state.exception_df["날짜"] == sel_date) & 
                              (st.session_state.exception_df["일정명"] == sched["일정명"]) & 
                              (st.session_state.exception_df["유형"] == "추가"))
                        ]
                        save_data(st.session_state.exception_df, EXCEPTION_FILE)
                    st.success("일정이 삭제되었습니다.")
                    st.rerun()
    else:
        st.text("등록된 일정이 없습니다.")
        
    # 일정 추가 버튼
    if not st.session_state.show_add_form:
        if st.button("➕ 1일 새 일정 추가"):
            st.session_state.show_add_form = True
            st.rerun()
            
    # 일정 추가 폼 전개
    if st.session_state.show_add_form:
        st.write("---")
        with st.container():
            new_title = st.text_input("일정 제목", key="new_title_input")
            
            c1, c2 = st.columns(2)
            with c1:
                start_date_val = st.text_input("시작 날짜", value=sel_date, disabled=True)
                # 시간 선택을 단순 텍스트 혹은 셀렉트박스로 구성
                hours = [f"{h:02d}:00" for h in range(24)] + [f"{h:02d}:30" for h in range(24)]
                hours.sort()
                start_time_val = st.selectbox("시작 시간", options=hours, index=hours.index("09:00"))
            with c2:
                end_date_val = st.text_input("종료 날짜", value=sel_date, disabled=True)
                end_time_val = st.selectbox("종료 시간", options=hours, index=hours.index("18:00"))
                
            b1, b2 = st.columns(2)
            with b1:
                if st.button("💾 저장", use_container_width=True):
                    if new_title.strip() == "":
                        st.error("일정 제목을 입력해주세요.")
                    else:
                        new_row = pd.DataFrame([{
                            "날짜": sel_date,
                            "시작시간": start_time_val,
                            "종료시간": end_time_val,
                            "일정명": new_title,
                            "유형": "추가"
                        }])
                        st.session_state.exception_df = pd.concat([st.session_state.exception_df, new_row], ignore_index=True)
                        save_data(st.session_state.exception_df, EXCEPTION_FILE)
                        st.success("새 일정이 추가되었습니다.")
                        st.session_state.show_add_form = False
                        st.rerun()
            with b2:
                # 원래 이 자리에 있던 '취소' 버튼 컴포넌트가 제거되었습니다.
                pass

st.markdown("<br><br><center style='font-size:12px; color:#999;'>⚙️ 고정 시간표 및 예외 관리</center>", unsafe_allow_value=True)
