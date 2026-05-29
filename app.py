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
    hdr_html = "<div style='display:grid;grid-template-columns:repeat(7,1fr);gap:2px;margin-bottom:2px;'> stream"
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
                # 폰 화면 한눈에 들어오도록 미니멈 높이를 65px -> 45px로 압축 고정
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

        # 구조 유지 + 모바일 한눈에 뷰 적용 (상세 패널을 스크롤 박스에 가두기)
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

            # 📱 핵심: 상세 일정이 길어져도 화면 밖으로 안 튕기게 최대 높이를 180px로 제한하고 내부 스크롤 부여
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
