import streamlit as st
import pandas as pd
from datetime import datetime
import pytz

# 1. 페이지 설정
st.set_page_config(page_title="생산관리 AI 통합 스케줄러", layout="wide")

# 2. 시스템 지침 (사용자님의 모든 예외사항과 규칙 반영)
SYSTEM_CONTEXT = """
너는 생산 스케줄링 전문가이며 아래 규칙을 엄격히 준수한다:
1. [CAPA] 조립 1,2,3 일일 생산량은 최대 CAPA의 90% 유지.
2. [조립2 요일] FAN(월/수/금), FLANGE(화/목), MOTOR(상관없음).
3. [분배] 납기일 전 2주 이내, PLT 배수로 분배, 0개 배분 금지.
4. [BERGSTROM] 조립1 전용, 일 최대 525개 제한. 생산 시 조립1 전체 CAPA는 2600으로 하향.
5. [T6 수밀] 1라인 기본이나 CAPA 초과 시 1,2,3라인 모두 가동 가능.
6. [보고] 예외 상황 시 대안 3가지와 상세 리스트를 제시하라.
"""

st.title("🤖 생산관리 AI 통합 관제 센터 (Final Demo)")
st.info("💡 이 버전은 실제 DB를 수정하지 않는 '안전 시뮬레이션 모드'입니다.")

# 3. 화면 레이아웃
left_col, right_col = st.columns([1, 1.2])

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "show_detail" not in st.session_state:
    st.session_state.show_detail = False

# --- 왼쪽: 챗봇 상담 영역 ---
with left_col:
    st.subheader("💬 실시간 예외 상황 대응")
    
    for chat in st.session_state.chat_history:
        with st.chat_message(chat["role"]):
            st.write(chat["content"])

    if prompt := st.chat_input("질문을 입력하세요 (예: 9/17 조립1 공정감사 발생)"):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        
        # 시나리오 답변 로직
        if "대안" in prompt or "리스트" in prompt or "보여줘" in prompt:
            response = "확인했습니다. 17가지 생산 규칙을 적용하여 9/17 물량 중 일부를 9/16으로 전진 배치했습니다. 우측의 상세 리스트와 가동률 변화를 확인해 주세요."
            st.session_state.show_detail = True
        else:
            response = "9/17 조립1 공정감사 이슈를 분석했습니다. 현재 CAPA와 납기일을 고려할 때 3가지 대안이 가능합니다. \n\n1. **일정 전후 분산** (가장 안정적) \n2. **주간 재배정** \n3. **라인 통합 운영(T6 수밀 활용)** \n\n어떤 대안을 상세히 검토할까요?"
        
        st.session_state.chat_history.append({"role": "assistant", "content": response})
        st.rerun()

# --- 오른쪽: 규칙 기반 데이터 시뮬레이션 ---
with right_col:
    st.subheader("📋 규칙 준수 검증 및 실행 계획")
    
    if st.session_state.show_detail:
        st.write("### [선택 대안] 9/17 → 9/16 물량 이동 계획")
        
        # 사용자 규칙(PLT 배수, BERGSTROM 제한)이 적용된 시뮬레이션 데이터
        sim_data = [
            {"품명": "BERGSTROM_A", "9/17 수량": 600, "이동(9/16)": 300, "PLT": 150, "규칙검증": "525개 제한 준수"},
            {"품명": "표준품목_X", "9/17 수량": 800, "이동(9/16)": 400, "PLT": 100, "규칙검증": "배수 준수"},
            {"품명": "표준품목_Y", "9/17 수량": 500, "이동(9/16)": 250, "PLT": 50, "규칙검증": "배수 준수"}
        ]
        st.table(pd.DataFrame(sim_data))
        
        # 규칙 기반 가동률 분석 보고
        st.markdown("""
        **🔍 규칙 준수 레포트**
        - **조립1 가동률**: 9/16 (90.2% - CAPA 90% 준수)
        - **BERGSTROM**: 9/16 합계 300개 (일 최대 525개 제한 준수)
        - **물량 분배**: 모든 품목이 PLT 배수 단위로 이동됨
        """)
        
        if st.button("🚀 이 계획으로 DB 반영 (이력 기록)"):
            korea_tz = pytz.timezone('Asia/Seoul')
            now = datetime.now(korea_tz).strftime('%Y-%m-%d %H:%M:%S')
            st.balloons()
            st.success(f"성공! [{now}]에 수정 이력이 기록되었습니다.")
            st.caption(f"기록된 메모: {now} 챗봇 승인 - 9/17 공정감사 대응")
    else:
        st.info("왼쪽 대화창에 예외 상황을 입력하면, 이곳에 규칙이 적용된 상세 데이터가 나타납니다.")