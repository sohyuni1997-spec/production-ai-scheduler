import streamlit as st
import pandas as pd
from supabase import create_client, Client
import requests
from datetime import datetime, timedelta
import re

# 1. Supabase 연결 설정
URL = "https://suaajrdahixouinbfcfo.supabase.co"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN1YWFqcmRhaGl4b3VpbmJmY2ZvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjYzMTk4NzAsImV4cCI6MjA4MTg5NTg3MH0.Ic4izQY-ihIw75jKh9iJicZvuZ4gCRs4OH3rCGyo0Zk"
supabase: Client = create_client(URL, KEY)

# CAPA 정보
CAPA_INFO = {
    "조립1": 3000,
    "조립2": 2500,
    "조립3": 2000
}

# 날짜 파싱 함수
def parse_date(date_str):
    """9/17 -> 2025-09-17 변환"""
    try:
        if '/' in date_str:
            parts = date_str.split('/')
            month = parts[0].zfill(2)
            day = parts[1].zfill(2)
            return f"2025-{month}-{day}"
        return date_str
    except:
        return None

# 날짜 범위 계산
def get_date_range(target_date, days_before=14, days_after=7):
    """특정 날짜 기준 전후 범위 계산"""
    try:
        dt = datetime.strptime(target_date, '%Y-%m-%d')
        start = (dt - timedelta(days=days_before)).strftime('%Y-%m-%d')
        end = (dt + timedelta(days=days_after)).strftime('%Y-%m-%d')
        return start, end
    except:
        return None, None

# DB 조회 함수 (버전별)
def fetch_production_data(target_date, version='2차'):
    """
    특정 날짜 포함 전후 2주 데이터 조회
    version: '0차', '1차', '2차'
    """
    start_date, end_date = get_date_range(target_date)
    
    if not start_date:
        return None
    
    response = supabase.table("pattern_learning")\
        .select("*")\
        .eq("version", version)\
        .gte("plan_date", start_date)\
        .lte("plan_date", end_date)\
        .order("plan_date", desc=False)\
        .execute()
    
    return pd.DataFrame(response.data) if response.data else None

# 0차 vs 2차 비교 함수
def compare_versions(df_0, df_2):
    """0차(원본)와 2차(실제) 비교"""
    if df_0 is None or df_2 is None:
        return None
    
    # 공통 키로 병합 (plan_date, line, product_name)
    merged = pd.merge(
        df_0[['plan_date', 'line', 'product_name', 'category', 'qty_0차']],
        df_2[['plan_date', 'line', 'product_name', 'category', 'qty_2차', 'production_date', 'worker_memo']],
        on=['plan_date', 'line', 'product_name', 'category'],
        how='outer',
        suffixes=('_0차', '_2차')
    )
    
    # 변경사항 계산
    merged['qty_diff'] = merged['qty_2차'].fillna(0) - merged['qty_0차'].fillna(0)
    merged['changed'] = merged['qty_diff'] != 0
    
    return merged

# 데이터 분석 함수
def analyze_data(df, version='2차'):
    """CAPA 사용률, 요일별 분포 등 분석"""
    analysis = {'version': version}
    
    # 날짜를 datetime으로 변환
    df['plan_date_dt'] = pd.to_datetime(df['plan_date'])
    df['weekday'] = df['plan_date_dt'].dt.day_name()
    df['weekday_kr'] = df['plan_date_dt'].dt.strftime('%A').map({
        'Monday': '월', 'Tuesday': '화', 'Wednesday': '수',
        'Thursday': '목', 'Friday': '금', 'Saturday': '토', 'Sunday': '일'
    })
    
    # 수량 컬럼 선택 (버전에 따라)
    qty_col = f'qty_{version}'
    
    # 라인별 일일 생산량 계산
    for line in ["조립1", "조립2", "조립3"]:
        line_data = df[df['line'] == line]
        daily_sum = line_data.groupby('plan_date')[qty_col].sum()
        
        max_capa = CAPA_INFO[line]
        target_capa = max_capa * 0.9
        
        analysis[line] = {
            'max_capa': max_capa,
            'target_90': int(target_capa),
            'daily_production': daily_sum.to_dict(),
            'over_capacity_days': daily_sum[daily_sum > target_capa].to_dict()
        }
    
    # BERGSTROM 생산일 확인
    bergstrom_data = df[df['product_name'].str.contains('BERGSTROM', case=False, na=False)]
    bergstrom_days = bergstrom_data.groupby('plan_date')[qty_col].sum().to_dict()
    
    # 조립2 요일별 FAN/FLANGE 체크
    line2_data = df[df['line'] == '조립2'].copy()
    
    # FAN: 월/수/금만 가능
    fan_data = line2_data[line2_data['category'] == 'FAN']
    fan_wrong = fan_data[~fan_data['weekday_kr'].isin(['월', '수', '금'])]
    
    # FLANGE: 화/목만 가능
    flange_data = line2_data[line2_data['category'] == 'FLANGE']
    flange_wrong = flange_data[~flange_data['weekday_kr'].isin(['화', '목'])]
    
    analysis['bergstrom_days'] = bergstrom_days
    analysis['fan_violations'] = fan_wrong[['plan_date', 'product_name', qty_col, 'weekday_kr']].to_dict('records')
    analysis['flange_violations'] = flange_wrong[['plan_date', 'product_name', qty_col, 'weekday_kr']].to_dict('records')
    
    # 조립2 일일 품목 수 체크
    line2_daily_products = line2_data.groupby('plan_date')['product_name'].nunique()
    analysis['line2_over_5products'] = line2_daily_products[line2_daily_products > 5].to_dict()
    
    return analysis

# AI 분석 함수
def ask_professional_scheduler(question, df, analysis, comparison_df=None):
    api_url = "https://ai.potens.ai/api/chat"
    api_key = "qD2gfuVAkMJexDAcFb5GnEb1SZksTs7o"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    
    # 버전 정보
    version = analysis.get('version', '2차')
    qty_col = f'qty_{version}'
    
    # 데이터 요약
    df_summary = df[['plan_date', 'line', 'product_name', 'category', 'plt', qty_col, 'worker_memo']].to_string(index=False, max_rows=100)
    
    # 0차 vs 2차 변경사항 요약
    change_summary = ""
    if comparison_df is not None:
        changed = comparison_df[comparison_df['changed'] == True]
        if not changed.empty:
            change_summary = f"\n\n[0차 대비 2차 변경사항]\n총 {len(changed)}건 변경\n"
            change_summary += changed[['plan_date', 'line', 'product_name', 'qty_0차', 'qty_2차', 'qty_diff', 'worker_memo']].to_string(index=False, max_rows=20)
    
    # 위반사항 요약
    violations_summary = ""
    if analysis['fan_violations']:
        violations_summary += f"\n⚠️ FAN 요일규칙 위반: {len(analysis['fan_violations'])}건"
        for v in analysis['fan_violations'][:3]:
            violations_summary += f"\n  - {v['plan_date']} ({v['weekday_kr']}): {v['product_name']} {v.get(qty_col, 0)}개"
    
    if analysis['flange_violations']:
        violations_summary += f"\n⚠️ FLANGE 요일규칙 위반: {len(analysis['flange_violations'])}건"
        for v in analysis['flange_violations'][:3]:
            violations_summary += f"\n  - {v['plan_date']} ({v['weekday_kr']}): {v['product_name']} {v.get(qty_col, 0)}개"
    
    if analysis['line2_over_5products']:
        violations_summary += f"\n⚠️ 조립2 5품목 초과일: {list(analysis['line2_over_5products'].keys())}"
    
    system_rules = f"""
당신은 자동차 부품 조립라인의 '수석 생산 스케줄러'입니다.

[데이터 버전 정보]
현재 분석 대상: **{version}** (실제 조정본)
- 0차: 원본 납기 데이터 (자동분배 전)
- 1차: 10가지 규칙 적용한 자동분배 결과 (팀원 개발 예정)
- 2차: 긴급상황 반영한 실제 생산 계획 (현재)

[현재 CAPA 정보 및 사용 현황]
• 조립1: 최대 {CAPA_INFO['조립1']}개/일 (목표 90% = {analysis['조립1']['target_90']}개)
  → 초과 발생일: {list(analysis['조립1']['over_capacity_days'].keys()) if analysis['조립1']['over_capacity_days'] else '없음'}

• 조립2: 최대 {CAPA_INFO['조립2']}개/일 (목표 90% = {analysis['조립2']['target_90']}개)
  → 초과 발생일: {list(analysis['조립2']['over_capacity_days'].keys()) if analysis['조립2']['over_capacity_days'] else '없음'}

• 조립3: 최대 {CAPA_INFO['조립3']}개/일 (목표 90% = {analysis['조립3']['target_90']}개)
  → 초과 발생일: {list(analysis['조립3']['over_capacity_days'].keys()) if analysis['조립3']['over_capacity_days'] else '없음'}

[특이사항 및 위반사항]
• BERGSTROM 생산 계획: {analysis['bergstrom_days']}
  (⚠️ 해당일 조립1 CAPA는 2,600개로 제한, 하루 최대 525개만 생산 가능)
{violations_summary}

{change_summary}

[자동분배 핵심 규칙 - 1차 생성 시 적용 예정]
1. **CAPA 제약**: 각 조립 라인 1일 생산량은 최대 CAPA의 90% 이내
2. **PLT 배수**: 납기일(plan_date) 포함 이전 날짜에 PLT 배수로 분배
3. **휴무 제약**: worker_memo에 '휴무' 있으면 생산 불가
4. **조립2 카테고리별 요일 제약**:
   - **FAN**: 월/수/금만 생산 가능
   - **FLANGE**: 화/목만 생산 가능
   - **MOTOR**: 요일 무관
5. **균등 분배**: 하루에 0개 배분 금지, 최대한 고르게 분포
6. **2주 제약**: 납기일 기준 2주 전부터 배분 시작
7. **조립2 품목 제한**: 하루 최대 5품목 생산
8. **0 배분 금지**: 어떤 날도 0개가 배분되지 않도록 조정
9. **고른 분포**: 최대한 균등하게 수량 분산
10. **물류 제약**: 납기일 2주 전부터만 생산 가능

[예외상황 대응 규칙]
11. **조립1 Buffer**: 샘플요청/공정감사 대비 여유 20% 권장
12. **BERGSTROM 특수 처리**: 시간당 90개, 하루 최대 525개, 해당일 조립1 CAPA 2,600개
13. **수밀 라인 확장**: 'T6 (P703) 수밀(U725)' 조립1 초과 시 1/2/3 라인 모두 활용
14. **월말 유연성**: 조립2 요일규칙은 월말(25일 이후) 유연 적용 가능
15. **CAPA 변동**: 긴급 상황 시 CAPA 조정 가능

[현재 생산 계획 데이터 - {version}]
{df_summary}

[필수 출력 형식]
반드시 아래 형식으로 **3가지 대안**을 제시하십시오:

---
## 🎯 대안 1: [대안명]

### 📌 구체적 조치사항
- **[날짜]** [품목명] (category: [FAN/FLANGE/MOTOR]) [기존수량]개 → [변경수량]개 ([기존라인] → [변경라인])
  *이유: [구체적 사유]*

### ✅ 장점
1. 
2. 

### ⚠️ 단점
1. 
2. 

### 🔮 발생 가능 상황
1. 
2. 

---
## 🎯 대안 2: [대안명]
(동일 형식)

---
## 🎯 대안 3: [대안명]
(동일 형식)
"""
    
    payload = {"prompt": f"{system_rules}\n\n[사용자 긴급 요청]\n{question}"}
    
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=90)
        if response.status_code == 200:
            return response.json().get('message', '응답 형식 오류')
        else:
            return f"❌ API 오류 (Status {response.status_code}): {response.text}"
    except Exception as e:
        return f"❌ 요청 실패: {str(e)}"

# --- UI 구성 ---
st.set_page_config(page_title="수석 스케줄러 AI 관제 센터", layout="wide")
st.title("👨‍✈️ 수석 스케줄러 AI 통합 제어 (Real-DB)")

# 세션 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# 상단 버전 선택
version_option = st.radio(
    "📂 분석 대상 선택",
    options=['2차 (실제 조정본)', '0차 vs 2차 비교'],
    horizontal=True,
    help="1차(자동분배)는 팀원 개발 완료 후 추가 예정"
)

# 2단 레이아웃
left_col, right_col = st.columns([1, 1.2])

with left_col:
    st.subheader("💬 AI 상담 창구")
    
    # 대화 히스토리 표시
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 사용자 입력
    if prompt := st.chat_input("예: 9/17 조립1 공정감사 이슈 분석하고 대안 리스트 뽑아줘."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        try:
            # 날짜 추출
            date_match = re.search(r'(\d{1,2})/(\d{1,2})', prompt)
            if not date_match:
                st.error("❌ 날짜 형식을 찾을 수 없습니다. (예: 9/17)")
                st.stop()
            
            date_val = f"{date_match.group(1)}/{date_match.group(2)}"
            formatted_date = parse_date(date_val)
            
            # 버전별 데이터 조회
            if '비교' in version_option:
                # 0차와 2차 모두 조회
                with st.spinner(f"📡 {date_val} 기준 0차/2차 데이터 조회 중..."):
                    df_0 = fetch_production_data(formatted_date, version='0차')
                    df_2 = fetch_production_data(formatted_date, version='2차')
                
                if df_0 is None or df_2 is None:
                    st.warning(f"⚠️ {date_val}에 해당하는 데이터가 없습니다.")
                    st.stop()
                
                # 비교 데이터 생성
                comparison_df = compare_versions(df_0, df_2)
                
                # 2차 기준으로 분석
                with st.spinner("🔍 변경사항 분석 중..."):
                    analysis = analyze_data(df_2, version='2차')
                
                # AI 분석 (비교 정보 포함)
                with st.chat_message("assistant"):
                    with st.spinner("🧠 수석 스케줄러가 대안을 수립 중입니다..."):
                        answer = ask_professional_scheduler(prompt, df_2, analysis, comparison_df)
                        st.markdown(answer)
                        st.session_state.messages.append({"role": "assistant", "content": answer})
                
                # 오른쪽에 비교 데이터 표시
                with right_col:
                    st.subheader(f"📊 0차 vs 2차 비교 ({date_val})")
                    
                    # 변경사항만 필터링
                    changed_only = st.checkbox("변경사항만 보기", value=True)
                    
                    if changed_only:
                        display_df = comparison_df[comparison_df['changed'] == True]
                    else:
                        display_df = comparison_df
                    
                    # 색상 표시
                    def highlight_changes(row):
                        if row['qty_diff'] > 0:
                            return ['background-color: #d4edda'] * len(row)  # 증가 (녹색)
                        elif row['qty_diff'] < 0:
                            return ['background-color: #f8d7da'] * len(row)  # 감소 (빨강)
                        return [''] * len(row)
                    
                    st.dataframe(
                        display_df[['plan_date', 'line', 'product_name', 'category', 'qty_0차', 'qty_2차', 'qty_diff', 'worker_memo']].style.apply(highlight_changes, axis=1),
                        use_container_width=True,
                        height=400
                    )
                    
                    # 통계
                    st.metric("총 변경 건수", len(comparison_df[comparison_df['changed'] == True]))
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("증가", len(comparison_df[comparison_df['qty_diff'] > 0]))
                    with col2:
                        st.metric("감소", len(comparison_df[comparison_df['qty_diff'] < 0]))
            
            else:
                # 2차만 조회
                with st.spinner(f"📡 {date_val} 기준 2차 데이터 조회 중..."):
                    df = fetch_production_data(formatted_date, version='2차')
                
                if df is None or df.empty:
                    st.warning(f"⚠️ {date_val}에 해당하는 데이터가 없습니다.")
                    st.stop()
                
                # 데이터 분석
                with st.spinner("🔍 CAPA 및 요일규칙 위반 검사 중..."):
                    analysis = analyze_data(df, version='2차')
                
                # AI 분석
                with st.chat_message("assistant"):
                    with st.spinner("🧠 수석 스케줄러가 대안을 수립 중입니다..."):
                        answer = ask_professional_scheduler(prompt, df, analysis)
                        st.markdown(answer)
                        st.session_state.messages.append({"role": "assistant", "content": answer})
                
                # 오른쪽에 데이터 표시
                with right_col:
                    st.subheader(f"📊 {date_val} 전후 2주 데이터 (2차)")
                    
                    tab1, tab2, tab3 = st.tabs(["📋 전체 데이터", "⚠️ 위반사항", "📈 CAPA 현황"])
                    
                    with tab1:
                        col1, col2 = st.columns(2)
                        with col1:
                            filter_line = st.multiselect(
                                "라인 필터",
                                options=df['line'].unique(),
                                default=df['line'].unique()
                            )
                        with col2:
                            filter_category = st.multiselect(
                                "카테고리 필터",
                                options=df['category'].dropna().unique(),
                                default=df['category'].dropna().unique()
                            )
                        
                        filtered_df = df[
                            (df['line'].isin(filter_line)) & 
                            (df['category'].isin(filter_category))
                        ]
                        
                        st.dataframe(
                            filtered_df[['plan_date', 'line', 'product_name', 'category', 'plt', 'qty_2차', 'production_date', 'worker_memo']],
                            use_container_width=True,
                            height=400
                        )
                    
                    with tab2:
                        st.subheader("🚨 요일규칙 위반")
                        
                        if analysis['fan_violations']:
                            st.error(f"**FAN 위반**: {len(analysis['fan_violations'])}건")
                            for v in analysis['fan_violations']:
                                st.write(f"- {v['plan_date']} ({v['weekday_kr']}): {v['product_name']} {v.get('qty_2차', 0)}개")
                        else:
                            st.success("✅ FAN 요일규칙 준수")
                        
                        st.divider()
                        
                        if analysis['flange_violations']:
                            st.error(f"**FLANGE 위반**: {len(analysis['flange_violations'])}건")
                            for v in analysis['flange_violations']:
                                st.write(f"- {v['plan_date']} ({v['weekday_kr']}): {v['product_name']} {v.get('qty_2차', 0)}개")
                        else:
                            st.success("✅ FLANGE 요일규칙 준수")
                        
                        st.divider()
                        
                        if analysis['line2_over_5products']:
                            st.warning(f"**조립2 5품목 초과**: {len(analysis['line2_over_5products'])}일")
                            for date, count in analysis['line2_over_5products'].items():
                                st.write(f"- {date}: {count}품목")
                        else:
                            st.success("✅ 조립2 품목 수 준수")
                    
                    with tab3:
                        st.subheader("📊 라인별 CAPA 사용률")
                        
                        for line in ["조립1", "조립2", "조립3"]:
                            info = analysis[line]
                            st.write(f"**{line}**")
                            st.write(f"최대: {info['max_capa']}개/일 | 목표(90%): {info['target_90']}개/일")
                            
                            if info['over_capacity_days']:
                                st.error(f"⚠️ 초과 발생일:")
                                for date, qty in info['over_capacity_days'].items():
                                    over_percent = (qty / info['max_capa']) * 100
                                    st.write(f"  - {date}: {int(qty)}개 ({over_percent:.1f}%)")
                            else:
                                st.success("✅ 모든 날짜 정상 범위")
                            
                            st.divider()
                        
                        if analysis['bergstrom_days']:
                            st.warning("⚠️ BERGSTROM 생산일")
                            for date, qty in analysis['bergstrom_days'].items():
                                st.write(f"- {date}: {int(qty)}개")
        
        except Exception as e:
            st.error(f"❌ 시스템 오류: {str(e)}")
            import traceback
            with st.expander("상세 오류 로그"):
                st.code(traceback.format_exc())

# 사이드바
with st.sidebar:
    st.header("📖 사용 가이드")
    
    st.info("""
    ### 📂 데이터 버전
    - **0차**: 원본 납기 데이터
    - **1차**: 자동분배 (개발 예정 🔨)
    - **2차**: 실제 조정본 ✅
    """)
    
    st.markdown("""
    ### 💬 질문 예시
    ```
    9/17 조립1 공정감사로 생산 불가
    ```
    ```
    10/5 BERGSTROM 긴급 증가
    ```
    
    ### 🎯 주요 기능
    - ✅ 0차 vs 2차 변경사항 비교
    - ✅ CAPA 90% 초과 감지
    - ✅ FAN/FLANGE 요일 위반 체크
    - ✅ 3가지 대안 + 장단점 분석
    
    ### 📋 카테고리 요일 규칙
    - **FAN**: 월/수/금
    - **FLANGE**: 화/목
    - **MOTOR**: 무관
    """)
    
    st.divider()
    st.caption("Powered by Potens.AI")
