import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
import requests

# 1. 페이지 설정
st.set_page_config(page_title="생산관리 AI 통합 관제 센터", layout="wide")

# 2. 포텐스닷 API 호출 함수
def ask_potensdot(question):
    url = "https://ai.potens.ai/api/chat"
    api_key = "qD2gfuVAkMJexDAcFb5GnEb1SZksTs7o" 
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    
    system_prompt = "너는 생산 라인 조절 전문가야. 17가지 생산 규칙을 준수해 답변하고, 사용자가 대안을 물으면 반드시 리스트를 제안해."
    payload = {"prompt": f"시스템 지침: {system_prompt}\n\n사용자 질문: {question}"}

    try:
        response = requests.post(url, headers=headers, json=payload)
        return response.json() if response.status_code == 200 else f"❌ 오류: {response.status_code}"
    except Exception as e:
        return f"❌ 연결 에러: {e}"

# --- 세션 상태 초기화 (중요) ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "show_right_panel" not in st.session_state:
    st.session_state.show_right_panel = False

st.title("🤖 생산관리 AI 통합 관제 센터")
st.info("💡 입력 형식: **날짜, 라인, 이슈** (예: 9/17, 조립1, 공정감사)")

# 레이아웃 분할
left_col, right_col = st.columns([1, 1.2])

# --- 왼쪽: 말풍선 채팅 UI ---
with left_col:
    st.subheader("💬 AI 생산 비서")
    
    # 1. 대화 기록 표시
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # 2. 채팅 입력 및 처리
    if prompt := st.chat_input("이슈를 입력하거나 대안을 선택하세요"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # 특정 키워드가 포함되면 오른쪽 패널을 활성화
        if "대안" in prompt or "분산" in prompt or "리스트" in prompt:
            st.session_state.show_right_panel = True
        
        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):
            with st.spinner("분석 중..."):
                response = ask_potensdot(prompt)
                answer = response if isinstance(response, str) else str(response)
                st.write(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
        st.rerun()

# --- 오른쪽: 상세 실행 계획 (이 부분이 활성화됨) ---
with right_col:
    st.subheader("📋 규칙 준수 상세 내역")
    
    # 세션 상태에 따라 조건부로 화면을 보여줌
    if st.session_state.show_right_panel:
        st.success("✅ 선택하신 대안에 따른 상세 이동 계획입니다.")
        
        # 시뮬레이션 상세 데이터
        detail_df = pd.DataFrame([
            {"품명": "BERGSTROM_A", "원안": 600, "조정": 300, "PLT": 150, "비고": "규칙 5번 준수"},
            {"품명": "표준품목_X", "원안": 800, "조정": 400, "PLT": 100, "비고": "배수 준수"},
            {"품명": "표준품목_Y", "원안": 500, "조정": 250, "PLT": 50, "비고": "배수 준수"}
        ])
        st.table(detail_df)
        
        st.markdown("""
        **🔍 분석 요약**
        - **가동률**: 9/16 (90.2%) / 9/17 (44.5%)
        - **준수 사항**: BERGSTROM 일 525개 제한 준수 및 모든 품목 PL트 배수 적용
        """)
        
        if st.button("🚀 이 계획으로 DB 반영"):
            st.balloons()
            st.toast("DB 반영 성공!")
    else:
        st.info("왼쪽 대화창에서 이슈를 입력하거나 구체적인 대안(예: 대안 1번)을 선택하시면 상세 내역이 이곳에 표시됩니다.")
