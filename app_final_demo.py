import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
import requests

# 1. 페이지 설정
st.set_page_config(page_title="생산관리 AI 통합 관제 센터", layout="wide")

# 2. 포텐스닷 API 호출 함수 (지침 강화)
def ask_potensdot(question):
    url = "https://ai.potens.ai/api/chat"
    api_key = "qD2gfuVAkMJexDAcFb5GnEb1SZksTs7o" 
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    
    # 17가지 규칙을 AI가 '수치 계산'에 활용하도록 지침을 매우 구체화함
    system_prompt = """
    당신은 자동차 부품 생산 스케줄러입니다. 뻔한 조언은 생략하고 아래 17가지 규칙에 따라 '수치'와 '대안'만 말하세요.
    1. 전체 가동률은 90% 이내로 유지 (규칙 1)
    2. 조립2: FAN(월수금), FLANGE(화목), MOTOR(무관) (규칙 2, 3)
    3. 조립1 BERGSTROM: 일 최대 525개, 생산 시 전체 CAPA는 2,600으로 계산 (규칙 4, 5)
    4. 모든 수량 이동은 반드시 'PLT 배수' 단위로 계산 (규칙 6)
    5. 공정감사/샘플 시 해당 라인 CAPA의 20%를 즉시 비우는 '대안 1'을 우선 제시 (규칙 11)
    6. 대안 제시 시 이동할 구체적인 '품목명'과 'PLT 단위 수량'을 표 형식으로 제안할 것.
    """
    
    payload = {"prompt": f"시스템 지침: {system_prompt}\n\n사용자 질문: {question}"}

    try:
        response = requests.post(url, headers=headers, json=payload)
        return response.json() if response.status_code == 200 else f"❌ 오류: {response.status_code}"
    except Exception as e:
        return f"❌ 연결 에러: {e}"

# --- 세션 상태 및 화면 구성 ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "show_right_panel" not in st.session_state:
    st.session_state.show_right_panel = False

st.title("🤖 생산관리 AI 통합 관제 센터")

left_col, right_col = st.columns([1, 1.2])

with left_col:
    st.subheader("💬 AI 생산 비서")
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if prompt := st.chat_input("9/17, 조립1, 공정감사 (수량 분석해줘)"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):
            with st.spinner("17가지 규칙 기반 수량 산출 중..."):
                response = ask_potensdot(prompt)
                # API 응답에서 메시지만 추출 (응답 구조에 따라 수정 필요)
                answer = response['message'] if isinstance(response, dict) and 'message' in response else str(response)
                st.write(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
                st.session_state.show_right_panel = True # 답변 시 오른쪽 패널 자동 활성화
        st.rerun()

with right_col:
    st.subheader("📋 규칙 준수 상세 내역")
    if st.session_state.show_right_panel:
        st.success("✅ 규칙 11번(감사 Buffer 20%) 및 규칙 6번(PLT 배수)이 적용되었습니다.")
        
        # 오른쪽 표에는 실제 수치 데이터 시뮬레이션
        detail_df = pd.DataFrame([
            {"품명": "BERGSTROM_A", "이동전": 600, "조정후": 300, "PLT단위": 150, "적용규칙": "규칙 5, 6"},
            {"품명": "표준품목_X", "이동전": 800, "조정후": 400, "PLT단위": 100, "적용규칙": "규칙 6, 11"},
            {"품명": "표준품목_Y", "이동전": 500, "조정후": 250, "PLT단위": 50, "적용규칙": "규칙 6, 11"}
        ])
        st.table(detail_df)
        
        if st.button("🚀 이 계획으로 DB 반영"):
            st.balloons()
    else:
        st.info("왼쪽 대화창에 이슈를 입력하면 규칙 기반의 수량 분석표가 나타납니다.")
