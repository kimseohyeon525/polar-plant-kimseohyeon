import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import unicodedata
import io

# 1. 페이지 설정
st.set_page_config(page_title="🌱 극지식물 최적 EC 농도 연구", layout="wide")

# 2. 한글 폰트 설정 (CSS)
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@100;400;700&display=swap');
html, body, [class*="css"], .stMarkdown {
    font-family: 'Noto Sans KR', sans-serif;
}
</style>
""", unsafe_allow_html=True)

# --- 유틸리티 함수 ---
def normalize_path(path_obj):
    """경로 내의 한글 파일명을 NFC로 정규화하여 반환"""
    return unicodedata.normalize('NFC', str(path_obj))

def find_file(directory, target_name):
    """NFC/NFD 차이를 극복하며 파일을 검색"""
    p = Path(directory)
    target_norm = unicodedata.normalize('NFC', target_name)
    for file in p.iterdir():
        if unicodedata.normalize('NFC', file.name) == target_norm:
            return file
    return None

# --- 데이터 로딩 ---
@st.cache_data
def load_data():
    data_dir = Path("data")
    if not data_dir.exists():
        st.error("📁 'data' 폴더를 찾을 수 없습니다.")
        return None, None

    school_info = {
        "송도고": {"ec_target": 1.0, "file": "송도고_환경데이터.csv", "color": "#AB63FA"},
        "하늘고": {"ec_target": 2.0, "file": "하늘고_환경데이터.csv", "color": "#EF553B"}, # 최적
        "아라고": {"ec_target": 4.0, "file": "아라고_환경데이터.csv", "color": "#00CC96"},
        "동산고": {"ec_target": 8.0, "file": "동산고_환경데이터.csv", "color": "#636EFA"}
    }

    env_dfs = []
    for school, info in school_info.items():
        file_path = find_file(data_dir, info["file"])
        if file_path:
            df = pd.read_csv(file_path)
            df['school'] = school
            df['target_ec'] = info["ec_target"]
            env_dfs.append(df)
    
    env_total = pd.concat(env_dfs, ignore_index=True) if env_dfs else pd.DataFrame()

    # 생육 데이터 로드
    growth_file = find_file(data_dir, "4개교_생육결과데이터.xlsx")
    growth_data = {}
    if growth_file:
        xlsx = pd.ExcelFile(growth_file)
        for sheet in xlsx.sheet_names:
            sheet_norm = unicodedata.normalize('NFC', sheet)
            df_sheet = pd.read_excel(growth_file, sheet_name=sheet)
            df_sheet['school'] = sheet_norm
            growth_data[sheet_norm] = df_sheet
    
    growth_total = pd.concat(growth_data.values(), ignore_index=True) if growth_data else pd.DataFrame()
    
    return env_total, growth_total, school_info

# 데이터 실행
with st.spinner('데이터를 불러오는 중입니다...'):
    env_df, growth_df, school_cfg = load_data()

if env_df.empty or growth_df.empty:
    st.error("데이터 파일을 로드하지 못했습니다. 파일명과 경로를 확인해주세요.")
    st.stop()

# --- 사이드바 ---
st.sidebar.header("📍 필터 설정")
school_list = ["전체"] + list(school_cfg.keys())
selected_school = st.sidebar.selectbox("분석 대상 학교 선택", school_list)

# 데이터 필터링
if selected_school == "전체":
    disp_env = env_df
    disp_growth = growth_df
else:
    disp_env = env_df[env_df['school'] == selected_school]
    disp_growth = growth_df[growth_df['school'] == selected_school]

# --- 메인 화면 ---
st.title("🌱 극지식물 최적 EC 농도 연구")

tab1, tab2, tab3 = st.tabs(["📖 실험 개요", "🌡️ 환경 데이터", "📊 생육 결과"])

# --- Tab 1: 실험 개요 ---
with tab1:
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("연구 배경 및 목적")
        st.info("""
        본 연구는 극지 환경에서 생존하는 식물의 최적 생육 조건을 규명하기 위해, 
        각 학교별로 서로 다른 **EC(전기전도도) 농도**를 설정하여 생육 데이터를 수집하였습니다.
        데이터 분석을 통해 가장 높은 생산성을 보이는 최적 EC 값을 도출합니다.
        """)
    
    with col2:
        st.subheader("학교별 설정 조건")
        info_table = []
        for s, info in school_cfg.items():
            count = len(growth_df[growth_df['school'] == s])
            info_table.append({"학교명": s, "EC 목표": info["ec_target"], "개체수": f"{count}개"})
        st.table(pd.DataFrame(info_table))

    st.divider()
    
    # 주요 지표 카드
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("총 개체수", f"{len(growth_df)} 장")
    m2.metric("평균 온도", f"{env_df['temperature'].mean():.1f}°C")
    m3.metric("평균 습도", f"{env_df['humidity'].mean():.1f}%")
    m4.metric("최적 EC(추정)", "2.0 (하늘고)", delta="Best", delta_color="normal")

# --- Tab 2: 환경 데이터 ---
with tab2:
    st.subheader("학교별 환경 지표 비교")
    
    # 2x2 서브플롯
    fig_env = make_subplots(rows=2, cols=2, 
                            subplot_titles=("평균 온도 (°C)", "평균 습도 (%)", "평균 pH", "목표 EC vs 실측 EC"))
    
    avg_env = env_df.groupby('school').mean(numeric_only=True).reset_index()
    
    fig_env.add_trace(go.Bar(x=avg_env['school'], y=avg_env['temperature'], marker_color='indianred', name='온도'), row=1, col=1)
    fig_env.add_trace(go.Bar(x=avg_env['school'], y=avg_env['humidity'], marker_color='royalblue', name='습도'), row=1, col=2)
    fig_env.add_trace(go.Bar(x=avg_env['school'], y=avg_env['ph'], marker_color='goldenrod', name='pH'), row=2, col=1)
    
    # 목표 vs 실측 EC
    fig_env.add_trace(go.Bar(x=avg_env['school'], y=avg_env['target_ec'], name='목표 EC', marker_color='lightgray'), row=2, col=2)
    fig_env.add_trace(go.Bar(x=avg_env['school'], y=avg_env['ec'], name='실측 EC', marker_color='darkgreen'), row=2, col=2)
    
    fig_env.update_layout(height=600, showlegend=False, font=dict(family="Malgun Gothic, sans-serif"))
    st.plotly_chart(fig_env, use_container_width=True)

    if selected_school != "전체":
        st.subheader(f"📈 {selected_school} 시계열 변화")
        fig_line = make_subplots(specs=[[{"secondary_y": True}]])
        fig_line.add_trace(go.Scatter(x=disp_env['time'], y=disp_env['temperature'], name="온도(°C)"), secondary_y=False)
        fig_line.add_trace(go.Scatter(x=disp_env['time'], y=disp_env['humidity'], name="습도(%)", line=dict(dash='dash')), secondary_y=True)
        
        # EC 수평선 포함한 EC 그래프
        fig_ec = px.line(disp_env, x='time', y='ec', title=f"{selected_school} EC 변화 및 목표선")
        fig_ec.add_hline(y=school_cfg[selected_school]['ec_target'], line_dash="dot", line_color="red", annotation_text="목표 EC")
        
        st.plotly_chart(fig_line, use_container_width=True)
        st.plotly_chart(fig_ec, use_container_width=True)

    with st.expander("📥 환경 데이터 원본 확인 및 다운로드"):
        st.dataframe(disp_env)
        csv = disp_env.to_csv(index=False).encode('utf-8-sig')
        st.download_button("CSV 다운로드", csv, "env_data.csv", "text/csv")

# --- Tab 3: 생육 결과 ---
with tab3:
    # 핵심 결과 카드
    avg_growth = growth_df.groupby('school').mean(numeric_only=True).reset_index()
    best_school = avg_growth.loc[avg_growth['생중량(g)'].idxmax(), 'school']
    
    st.success(f"🥇 분석 결과, **{best_school}**의 EC 조건에서 가장 높은 생중량을 보였습니다.")

    # 2x2 생육 비교
    fig_growth = make_subplots(rows=2, cols=2, 
                               subplot_titles=("평균 생중량 (g)", "평균 잎 수 (장)", "평균 지상부 길이 (mm)", "학교별 개체수"))
    
    # 생중량 강조 (하늘고/최대값)
    colors = ['#EF553B' if s == '하늘고' else '#636EFA' for s in avg_growth['school']]
    
    fig_growth.add_trace(go.Bar(x=avg_growth['school'], y=avg_growth['생중량(g)'], marker_color=colors), row=1, col=1)
    fig_growth.add_trace(go.Bar(x=avg_growth['school'], y=avg_growth['잎 수(장)'], marker_color='seagreen'), row=1, col=2)
    fig_growth.add_trace(go.Bar(x=avg_growth['school'], y=avg_growth['지상부 길이(mm)'], marker_color='orange'), row=2, col=1)
    
    counts = growth_df['school'].value_counts().reset_index()
    fig_growth.add_trace(go.Bar(x=counts['school'], y=counts['count'], marker_color='gray'), row=2, col=2)
    
    fig_growth.update_layout(height=700, showlegend=False)
    st.plotly_chart(fig_growth, use_container_width=True)

    # 분포 및 상관관계
    col_a, col_b = st.columns(2)
    with col_a:
        fig_box = px.box(growth_df, x='school', y='생중량(g)', color='school', title="학교별 생중량 분포")
        st.plotly_chart(fig_box, use_container_width=True)
    with col_b:
        fig_scat = px.scatter(growth_df, x='잎 수(장)', y='생중량(g)', color='school', title="잎 수 vs 생중량 상관관계")
        st.plotly_chart(fig_scat, use_container_width=True)

    with st.expander("📥 생육 데이터 원본 확인 및 다운로드"):
        st.dataframe(disp_growth)
        
        # XLSX 다운로드 (BytesIO 사용)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            disp_growth.to_excel(writer, index=False, sheet_name='Growth_Data')
        buffer.seek(0)
        
        st.download_button(
            label="XLSX 다운로드",
            data=buffer,
            file_name=f"{selected_school}_생육데이터.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
