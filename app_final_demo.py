import streamlit as st
import pandas as pd
from supabase import create_client, Client
import requests

# 1. Supabase 연결 설정
URL = "YOUR_SUPABASE_URL"
KEY = "YOUR_SUPABASE_ANON_KEY"
supabase: Client = create_client(URL, KEY)

# 2. 포텐스닷 API 호출 함수
def ask_ai_with_actual_data(question, actual_plan_text):
    api_url = "https://ai.potens.ai/api/chat"
    api_key = "qD2gfuVAkMJexDAcFb5GnEb1SZksTs7o" 
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    
    # 시스템 지침 강화: 반드시 제공된 실제 품명(product_name)만 사용하도록 고정
    system_prompt = f"""
    당신은 자동차 부품 생산 스케줄링 전문가입니다. 
    반드시 아래 [실제 계획 데이터]의 'product_name' 컬럼에 있는 품명만 사용하여 답변하세요. 
    가상의 품명(FAN-A, 조립2 잔여 등)은 절대 사용하지 마세요.
    
    [실제 계획 데이터 (해당 날짜/라인)]:
    {actual_plan_text}
    
    [준수해야 할 17가지 규칙 중 핵심]:
    - 규칙 11: 공정감사 시 해당 라인 전체 수량의 20%를 비울 것.
    - 규칙 6: 모든 이동 수량은 'plt_unit'의 배수여야 함.
    - 규칙 5: BERGSTROM은 일 최대 525개 제한.
    
    이동이 필요한 품목의 'product_name', '이동 전 수량', '이동 후 수량', 'PLT 배수'를 포함한 표를 제시하세요.
    """
    
    payload = {"prompt": f"시스템 지침: {system_prompt}\n\n사용자 질문: {question}"}
    response = requests.post(api_url, headers=headers, json=payload)
    return response.json()['message'] if response.status_code == 200 else "API 응답 오류"

# --- UI 구성 ---
st.title("🏭 생산관리 AI 관제 센터 (DB 연동형)")

if prompt := st.chat_input("9/17, 조립1, 공정감사"):
    try:
        # 입력값 파싱
        parts = [p.strip() for p in prompt.split(",")]
        date_val, line_val = parts[0], parts[1]
        
        # 3. 실제 테이블명 'pattern_learning'에서 데이터 추출
        # product_name 컬럼 데이터를 포함하여 쿼리 실행
        res = supabase.table("pattern_learning").select("product_name, qty, plt_unit").eq("date", date_val).eq("line", line_val).execute()
        
        if res.data:
            df = pd.DataFrame(res.data)
            # AI가 읽을 수 있도록 실제 품명 리스트를 텍스트로 변환
            actual_plan_text = df.to_string(index=False)
            
            with st.chat_message("assistant"):
                with st.spinner(f"DB({date_val}) 데이터를 분석 중입니다..."):
                    # 실제 데이터를 AI에게 전달하여 답변 생성
                    answer = ask_ai_with_actual_data(prompt, actual_plan_text)
                    st.write(answer)
                
                # 원본 데이터 확인용 사이드바
                st.sidebar.subheader(f"📊 {date_val} 로드된 실제 데이터")
                st.sidebar.dataframe(df)
        else:
            st.warning(f"DB의 'pattern_learning' 테이블에 {date_val} {line_val} 데이터가 없습니다.")
            
    except Exception as e:
        st.error(f"오류 발생: {e}. 입력 형식을 확인하세요 (예: 9/17, 조립1, 공정감사)")
