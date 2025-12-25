import streamlit as st
import pandas as pd
from supabase import create_client, Client
import requests

# 1. 연결 설정 (본인의 URL과 Key를 꼭 넣어주세요)
URL = "https://suaajrdahixouinbfcfo.supabase.co"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN1YWFqcmRhaGl4b3VpbmJmY2ZvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjYzMTk4NzAsImV4cCI6MjA4MTg5NTg3MH0.Ic4izQY-ihIw75jKh9iJicZvuZ4gCRs4OH3rCGyo0Zk"
supabase: Client = create_client(URL, KEY)

# 2. 포텐스닷 API 함수 (실제 데이터 기반 분석)
def ask_ai_production(question, df_html):
    api_url = "https://ai.potens.ai/api/chat"
    api_key = "qD2gfuVAkMJexDAcFb5GnEb1SZksTs7o" 
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    
    system_prompt = f"""
    당신은 자동차 부품 생산 스케줄링 전문가입니다.
    제공된 [실제 생산 데이터]의 'product_name'과 'qty'를 바탕으로 분석하세요.
    
    [실제 생산 데이터 (2차 - production_date 기준)]:
    {df_html}
    
    [핵심 규칙]:
    1. 규칙 11: 공정감사/이슈 발생 시 해당 라인 물량의 20%를 즉시 비울 것.
    2. 규칙 6: 모든 이동은 'plt_unit'의 배수로 계산할 것.
    
    답변 시 반드시 실제 품명(A2XX 등)을 언급하고, 구체적인 이동 수량을 표로 제시하세요.
    """
    
    payload = {"prompt": f"시스템 지침: {system_prompt}\n\n사용자 질문: {question}"}
    response = requests.post(api_url, headers=headers, json=payload)
    return response.json()['message'] if response.status_code == 200 else "API 응답 오류"

# --- 웹 화면 구성 (말풍선 디자인) ---
st.set_page_config(page_title="생산관리 AI 관제 센터", layout="wide")
st.title("🤖 생산관리 AI 통합 관제 센터 (Real-DB 연동)")

if "messages" not in st.session_state:
    st.session_state.messages = []

left_col, right_col = st.columns([1, 1.2])

with left_col:
    # 대화 이력 표시
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if prompt := st.chat_input("예: 9/17, 조립1, 공정감사"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        # DB에서 2차 생산일(production_date) 기준으로 데이터 조회
        try:
            parts = [p.strip() for p in prompt.split(",")]
            date_val = parts[0] # "9/17"을 "2025-09-17" 형태로 변환이 필요할 수 있습니다.
            # 만약 입력이 '9/17'이면 DB 형식 '2025-09-17'로 맞춰주는 로직
            formatted_date = f"2025-0{date_val.replace('/', '-')}" if '/' in date_val else date_val

            res = supabase.table("pattern_learning").select("product_name, qty, plt_unit").eq("production_date", formatted_date).execute()
            
            if res.data:
                df = pd.DataFrame(res.data)
                df_html = df.to_html(index=False)
                
                with st.chat_message("assistant"):
                    with st.spinner("DB 데이터를 분석 중입니다..."):
                        answer = ask_ai_production(prompt, df_html)
                        st.write(answer)
                        st.session_state.messages.append({"role": "assistant", "content": answer})
                
                # 오른쪽 화면에 실제 로드된 데이터 표시
                with right_col:
                    st.subheader(f"📊 {date_val} 실제 생산 계획 (2차)")
                    st.dataframe(df)
            else:
                with st.chat_message("assistant"):
                    st.write(f"죄송합니다. DB에 {date_val}에 해당하는 생산 데이터가 없습니다.")
        except Exception as e:
            st.error(f"오측 발생: {e}")

        st.rerun()
