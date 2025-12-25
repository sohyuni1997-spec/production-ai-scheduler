import streamlit as st
import pandas as pd
from supabase import create_client, Client
import requests

# 1. Supabase 설정 (이미 알고 계신 URL과 Key를 넣어주세요)
url: str = "YOUR_SUPABASE_URL"
key: str = "YOUR_SUPABASE_ANON_KEY"
supabase: Client = create_client(url, key)

# 2. 포텐스닷 API 함수 (DB 데이터를 문맥으로 함께 전달)
def ask_ai_with_data(question, db_context):
    api_url = "https://ai.potens.ai/api/chat"
    api_key = "qD2gfuVAkMJexDAcFb5GnEb1SZksTs7o"
    
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    
    # 17가지 규칙 + 실제 DB 데이터를 시스템 지침에 포함
    system_prompt = f"""
    당신은 생산 스케줄러입니다. 아래 17가지 규칙과 실제 DB 데이터를 바탕으로 답변하세요.
    [규칙 요약] 1.가동률 90% / 5.BERGSTROM 일 525개 / 6.PLT 배수 / 11.감사 시 20% 비우기 등.
    [현재 DB 물량 정보]: {db_context}
    
    위 데이터를 바탕으로, 감사 대상 라인의 물량 20%를 어떤 품목에서 몇 PLT만큼 옮겨야 하는지 '표'로 제시하세요.
    뻔한 질문(감사 시간이 언제냐 등)은 하지 말고 바로 실행 계획을 제안하세요.
    """
    
    payload = {"prompt": f"지침: {system_prompt}\n\n사용자 질문: {question}"}
    response = requests.post(api_url, headers=headers, json=payload)
    return response.json()['message'] if response.status_code == 200 else "에러 발생"

# --- 화면 구성 ---
st.title("🤖 Supabase 연동 생산 AI 관제 센터")

if prompt := st.chat_input("9/17, 조립1, 공정감사"):
    # 1. 사용자 질문 분석 (날짜와 라인 추출)
    try:
        parts = [p.strip() for p in prompt.split(",")]
        date_query = parts[0] # "9/17"
        line_query = parts[1] # "조립1"
        
        # 2. Supabase에서 해당 날짜/라인 물량 직접 가져오기 (실시간 연동)
        # 테이블명과 컬럼명은 실제 환경에 맞게 수정하세요.
        res = supabase.table("production_plan").select("*").eq("date", date_query).eq("line", line_query).execute()
        db_data = res.data # 실제 DB 행 데이터 2,239건 중 해당되는 것들
        
        # 3. AI에게 DB 데이터를 함께 던져서 답변 받기
        with st.chat_message("assistant"):
            answer = ask_ai_with_data(prompt, str(db_data))
            st.write(answer)
            
            # 오른쪽 표 업데이트를 위한 데이터 저장
            st.session_state.current_db_data = pd.DataFrame(db_data)
            st.session_state.show_analysis = True
    except Exception as e:
        st.error(f"데이터 조회 중 오류: {e}")

# --- 오른쪽 화면 (DB에서 가져온 원본 물량 표시) ---
st.sidebar.subheader("📊 실시간 DB 조회 결과")
if "current_db_data" in st.session_state:
    st.sidebar.write("조회된 9/17 원본 계획:")
    st.sidebar.dataframe(st.session_state.current_db_data)
