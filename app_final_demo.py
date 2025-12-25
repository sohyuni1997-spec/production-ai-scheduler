import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
import requests
import json

# 1. 페이지 설정
st.set_page_config(page_title="생산관리 AI 통합 관제 센터", layout="wide")

# 2. 포텐스닷 API 호출 함수
def ask_potensdot(question):
    url = "https://ai.potens.ai/api/chat"
    api_key = "qD2gfuVAkMJexDAcFb5GnEb1SZksTs7o" # 사용자님의 API KEY
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    # 17가지 생산 규칙을 시스템 지침으로 주입
    system_prompt = """
    너는 자동차 부품 생산 라인 조절 전문가야. 아래 17가지 생산 규칙을 절대적으로 준수해:
    1. CAPA 90% 유지 / 2. 조립2 요일제(FAN:월수금, FLANGE:화목) / 3. MOTOR 요일무관 
    4. BERGSTROM 생산 시 조립1 CAPA 2600 하향 / 5. BERGSTROM 일 최대 525개 제한
    6. PLT 배수 준수 / 7. 납기 2주 전 생산 금지 / 8. 0개 배분 지양
    9. T6 수밀 유연 운영 / 10. 고부가가치 라인 고정 / 11. 감사 시 Buffer 20% 확보
    12. 월말 3일 요일제 완화 / 13. 긴급 오더 시 기존 물량 Push-back
    14. Change-over 최소화 / 15. 잔량 PLT 단위 관리 / 16. 수정 이력 기록 / 17. 대안 3가지 제시
    현재 DB에는 2025년 8월~11월 데이터 2,239건이 저장되어 있음을 인지하고 답변해.
    """

    payload = {
        "prompt": f"시스템 지침: {system_prompt}\n\n사용자 질문: {question}"
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            # API 응답 구조에 따라 response.json()['content'] 등으로 수정이 필요할 수 있습니다.
            return response.json() 
        else:
            return f"❌ API 오류: {response.status_code}"
    except Exception as e:
        return f"❌ 연결 에러: {e}"

# --- 웹 화면 구성 ---
st.title("🧠 생산관리 AI 통합 관제 센터 (Potensdot API)")
st.info("💡 입력 형식: **날짜, 라인, 이슈** (예: 9/17, 조립1, 공정감사)")

# 3. 레이아웃 분할
left_col, right_col = st.columns([1, 1.2])

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "안녕하세요! 포텐스닷 AI와 17가지 규칙을 통해 생산 계획을 최적화합니다. '날짜, 라인, 이슈'를 입력해주세요."}]

# --- 왼쪽: 리얼 채팅 UI (API 연동) ---
with left_col:
    st.subheader("💬 AI 생산 비서")
    chat_container = st.container(height=500)
    
    with chat_container:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

    if prompt := st.chat_input("9/17, 조립1, 공정감사"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.write(prompt)

        # 포텐스닷 API 호출
        with st.chat_message("assistant"):
            with st.spinner("AI가 17가지 규칙을 검토 중입니다..."):
                api_res = ask_potensdot(prompt)
                # 응답이 딕셔너리일 경우 문자열로 변환 (API 응답 형식에 맞게 조정 필요)
                answer = api_res if isinstance(api_res, str) else str(api_res)
                st.write(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
        st.rerun()

# --- 오른쪽: 실행 계획 (추가 리스트) ---
with right_col:
    st.subheader("📋 규칙 기반 상세 분석 표")
    st.write("채팅 답변을 바탕으로 실제 이동이 필요한 품목 리스트를 확인하세요.")
    
    # 시연용 표 (AI가 표 형식의 텍스트를 주면 그것을 파싱해서 보여주는 기능의 자리)
    st.markdown("**[시뮬레이션 데이터]**")
    st.table(pd.DataFrame([
        {"항목": "분석 대상", "내용": "입력된 날짜 및 라인"},
        {"항목": "핵심 적용 규칙", "내용": "규칙 5번, 11번 외"},
        {"항목": "조치 제안", "내용": "물량 50% 전일 이동 및 PLT 배수 조정"}
    ]))

    if st.button("🚀 분석 결과 DB 최종 승인"):
        st.balloons()
        st.success("포텐스닷 AI 분석 결과가 승인되었습니다. (데모 모드)")
