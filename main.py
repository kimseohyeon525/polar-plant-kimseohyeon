import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import unicodedata
import io

# 페이지 설정
st.set_page_config(page_title="나도수영 환경-생육 상관관계 연구", layout="wide")

# 한글 폰트 깨짐 방지 설정 (CSS)
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR&display=swap');
html, body, [class*="css"], .stMarkdown {
    font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
}
</style>
""", unsafe_allow_html=True)

# 파일명 정규화 및 유틸리티 함수
def normalize_nfc(text):
    return unicodedata.normalize('NFC', text)

@st.cache_data
def load_data():
    data_path = Path("data")
    if not data_path.exists():
        st.error("❌ 'data' 폴더를 찾을 수 없습니다.")
        return None, None, None

    # 1. 환경 데이터 로드 (NFC/NFD 대응)
    env_files = {
        "송도고": "송도고_환경데이터.csv",
        "하늘고": "하늘고_환경데이터.csv",
        "아라고": "아라고_환경데이터.csv",
        "동산고": "동산고_환경데이터.csv"
    }
    
    env_data_list = []
    # 파일 시스템의 실제 파일 목록 가져오기
    actual_files = {normalize_nfc(f.name): f for f in data_path.iterdir() if f.is_file()}

    for school_name, target_filename in env_files.items():
        norm_target = normalize_nfc(target_filename)
        if norm_target in actual_files:
            df = pd.read_csv(actual_files[norm_target])
            df['학교'] = school_name
            # EC 목표값 매핑
            ec_map = {"송도고": 1.0, "하늘고": 2.0, "아라고": 4.0, "동산고": 8.0}
            df['목표_EC'] = ec_map[school_name]
            env_data_list.append(df)
    
    all_env_df = pd.concat(env_data_list, ignore_index=True) if env_data_list else pd.DataFrame()

    # 2. 생육 결과 데이터 로드 (xlsx)
    growth_filename = "4개교_생육결과데이터.xlsx"
    norm_growth_target = normalize_nfc(growth_filename)
    
    growth_data_list = []
    if norm_growth_target in actual_files:
        excel_path = actual_files[norm_growth_target]
        xl = pd.ExcelFile(excel_path)
        for sheet in xl.sheet_names:
            norm_sheet = normalize_nfc(sheet)
            df_sheet = pd.read_excel(excel_path, sheet_name=sheet)
            df_sheet['학교'] = norm_sheet
            growth_data_list.append(df_sheet)
    
    all_growth_df = pd.concat(growth_data_list, ignore_index=True) if growth_data_list else pd.DataFrame()

    # 학교별 평균 생육량 계산
    if not all_growth_df.empty:
        summary_growth = all_growth_df.groupby('학교').mean(numeric_only=True).reset_index()
        # EC 정보 결합
        ec_info = pd.DataFrame([
            {"학교": "송도고", "EC": 1.0},
            {"학교": "하늘고", "EC": 2.0},
            {"학교": "아라고", "EC": 4.0},
            {"학교": "동산고", "EC": 8.0}
        ])
        summary_growth = pd.merge(summary_growth, ec_info, on="학교")
    else:
        summary_growth = pd.DataFrame()

    return all_env_df, all_growth_df, summary_growth

# 데이터 로딩 실행
with st.spinner('데이터를 분석 중입니다...'):
    env_df, growth_df, summary_df = load_data()

if env_df is None or env_df.empty or growth_df.empty:
    st.error("데이터 로드에 실패했습니다. 파일 구조와 한글 파일명을 확인해주세요.")
    st.stop()

# 사이드바 설정
st.sidebar.header("🔍 데이터 필터링")
school_options = ["전체", "송도고", "하늘고", "아라고", "동산고"]
selected_school = st.sidebar.selectbox("학교 선택", school_options)

# 데이터 필터링
if selected_school == "전체":
    f_env = env_df
    f_growth = growth_df
else:
    f_env = env_df[env_df['학교'] == selected_school]
    f_growth = growth_df[growth_df['학교'] == selected_school]

# 제목
st.title("🌱 나도수영의 환경과 생육의 상관관계")
st.markdown("---")

# 메인 탭 구성
tab1, tab2, tab3 = st.tabs(["📉 EC와 생육량", "☁️ 환경 복합 요인", "🧪 요인별 상관관계"])

# Tab 1: EC 수준에 따른 생육량 변화
# --- Tab 1 수정 부분 ---
# --- Tab 1: EC 수준 변화에 따른 생육량 ---
with tab1:
    st.subheader("EC(전기전도도) 수준별 평균 생육 지표 변화")
    col1, col2 = st.columns([3, 1])
    
    if summary_df is not None and not summary_df.empty:
        with col1:
            # 1. 데이터 정렬 (EC 기준)
            plot_df = summary_df.sort_values('EC')
            
            # 2. 그래프 생성
            fig1 = go.Figure()
            
            # 평균 생중량 선
            fig1.add_trace(go.Scatter(
                x=plot_df['EC'], 
                y=plot_df['생중량(g)'], 
                name='평균 생중량(g)', 
                line=dict(color='green', width=4), 
                mode='lines+markers'
            ))
            
            # 지상부 길이 선
            fig1.add_trace(go.Scatter(
                x=plot_df['EC'], 
                y=plot_df['지상부 길이(mm)'], 
                name='지상부 길이(mm)', 
                line=dict(dash='dash', color='orange'),
                mode='lines+markers'
            ))
            
            # 3. 최적값(EC 2.0) 어노테이션 추가 (에러 방지 강화)
            try:
                # 2.0에 가장 가까운 값을 찾거나 정확히 일치하는 행 선택
                target_row = plot_df[abs(plot_df['EC'] - 2.0) < 0.1]
                
                if not target_row.empty:
                    # 데이터가 있을 때만 어노테이션 추가
                    best_y = target_row['생중량(g)'].values[0]
                    fig1.add_annotation(
                        x=2.0, 
                        y=best_y,
                        text="최적 EC (2.0)", 
                        showarrow=True, 
                        arrowhead=2, 
                        ax=0, 
                        ay=-40,
                        font=dict(color="red", size=12),
                        arrowcolor="red"
                    )
            except Exception:
                # 에러 발생 시 어노테이션만 생략하고 그래프는 출력
                pass
            
            # 4. 레이아웃 설정
            fig1.update_layout(
                title="EC 농도에 따른 생육 지표 변화", 
                xaxis_title="EC (dS/m)", 
                yaxis_title="측정치",
                font=dict(family="Malgun Gothic, sans-serif"),
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            st.plotly_chart(fig1, use_container_width=True)
            
        with col2:
            st.info("**분석 결과**\n\nEC 2.0(하늘고)에서 생중량이 가장 높게 나타나는 경향을 보입니다. 단, 다른 환경 요인에 따라 결과는 달라질 수 있습니다.")
    else:
        st.error("📉 표시할 생육 요약 데이터가 없습니다. 파일의 시트 이름과 '학교' 컬럼을 확인해 주세요.")
# Tab 2: 다른 요인들의 영향 (습도 등)
with tab2:
    st.subheader("EC 외 환경 요인이 생육에 미치는 영향")
    
    # 평균 습도 데이터 결합
    avg_hum = env_df.groupby('학교')['humidity'].mean().reset_index()
    hum_growth_df = pd.merge(summary_df, avg_hum, on='학교').sort_values('humidity')
    
    col_l, col_r = st.columns(2)
    
    with col_l:
        fig_ec = px.line(plot_df, x='EC', y='생중량(g)', title="EC별 생중량 변화 (재확인)", markers=True)
        fig_ec.update_traces(line_color='green')
        st.plotly_chart(fig_ec, use_container_width=True)
        
    with col_r:
        fig_hum = px.line(hum_growth_df, x='humidity', y='생중량(g)', title="평균 습도별 생중량 변화", markers=True)
        fig_hum.update_traces(line_color='blue')
        st.plotly_chart(fig_hum, use_container_width=True)

    st.warning("💡 **핵심 관찰**: EC가 최적값에서 벗어나더라도 습도나 온도와 같은 다른 환경 요인이 최적 상태에 가까울 경우, 생육량 저하가 상쇄될 수 있음을 시사합니다.")

# Tab 3: 환경 요인 간 상관관계 (EC vs pH)
with tab3:
    st.subheader("환경 데이터 간 상관계수 분석")
    
    fig_corr = px.scatter(env_df, x='ec', y='ph', color='학교', 
                         trendline="ols",
                         title="EC와 pH 사이의 음의 상관관계 분석",
                         labels={'ec': '전기전도도(EC)', 'ph': '산도(pH)'})
    
    fig_corr.update_layout(font=dict(family="Malgun Gothic, sans-serif"))
    st.plotly_chart(fig_corr, use_container_width=True)
    
    st.markdown("""
    > **상관관계 해석**:
    > 산점도와 추세선을 통해 **EC가 높아질수록 pH가 낮아지는 음의 상관관계**를 확인할 수 있습니다. 
    > 이는 양액의 농도가 높아짐에 따라 이온 구성 변화가 산도에 영향을 미치기 때문으로 분석됩니다.
    """)

# 데이터 원본 확인 및 다운로드 영역
st.markdown("---")
with st.expander("📂 원본 데이터 확인 및 다운로드"):
    st.write(f"현재 선택된 데이터: {selected_school}")
    st.dataframe(f_growth)
    
    # XLSX 다운로드 로직
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        f_growth.to_excel(writer, index=False, sheet_name='Sheet1')
    
    st.download_button(
        label="📥 선택된 학교 생육 데이터 다운로드 (XLSX)",
        data=buffer.getvalue(),
        file_name=f"{selected_school}_생육데이터.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
