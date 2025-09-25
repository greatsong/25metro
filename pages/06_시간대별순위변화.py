import streamlit as st
import pandas as pd
import plotly.express as px

# 데이터 로딩 및 기본 전처리 함수
@st.cache_data
def load_and_prep_data():
    """
    CSV 파일을 로드하고 기본적인 전처리(컬럼명 변경, 타입 변환, long format 변환)를 수행합니다.
    이 함수는 앱 세션 동안 한 번만 실행됩니다.
    """
    dtype_spec = {'호선명': str, '지하철역': str}
    try:
        df = pd.read_csv('지하철데이터.csv', encoding='cp949', dtype=dtype_spec)
    except UnicodeDecodeError:
        df = pd.read_csv('지하철데이터.csv', encoding='utf-8-sig', dtype=dtype_spec)
    except FileNotFoundError:
        st.error("😥 '지하철데이터.csv' 파일을 찾을 수 없습니다. 프로젝트 루트 디렉토리에 파일을 업로드해주세요.")
        return None
    
    df.dropna(subset=['호선명', '지하철역'], inplace=True)
    df = df.iloc[:, :-1].copy()
    
    col_names = ['사용월', '호선명', '역ID', '지하철역']
    for i in range(4, len(df.columns), 2):
        time_str = df.columns[i].split('~')[0][:2]
        col_names.append(f'{time_str}_승차')
        col_names.append(f'{time_str}_하차')
    df.columns = col_names
    
    value_cols = [c for c in df.columns if '_승차' in c or '_하차' in c]
    for col in value_cols:
        if df[col].dtype == 'object':
            df[col] = pd.to_numeric(df[col].str.replace(',', ''), errors='coerce').fillna(0).astype(int)
        else:
            df[col] = df[col].fillna(0).astype(int)
            
    id_vars = ['사용월', '호선명', '역ID', '지하철역']
    df_long = df.melt(id_vars=id_vars, var_name='시간구분', value_name='인원수')
    df_long['시간대'] = df_long['시간구분'].str.split('_').str[0]
    df_long['구분'] = df_long['시간구분'].str.split('_').str[1]
    df_long = df_long.drop(columns=['시간구분'])
    return df_long

# --- FIX: 모든 무거운 계산을 하나의 캐시 함수로 통합 ---
@st.cache_data
def get_animation_data(df_long, combine_stations, analysis_type, top_n):
    """
    선택된 옵션에 따라 최종 애니메이션 데이터를 생성합니다.
    이 함수는 top_n을 포함한 주요 옵션이 변경될 때만 재실행됩니다.
    """
    if analysis_type != '종합':
        df_filtered = df_long[df_long['구분'] == analysis_type]
    else:
        df_filtered = df_long

    if combine_stations:
        grouped = df_filtered.groupby(['시간대', '지하철역'])['인원수'].sum().reset_index()
        grouped['역명(호선)'] = grouped['지하철역']
    else:
        grouped = df_filtered.groupby(['시간대', '호선명', '지하철역'])['인원수'].sum().reset_index()
        grouped['역명(호선)'] = grouped['지하철역'] + "(" + grouped['호선명'] + ")"

    time_slots = [f"{h:02d}" for h in range(4, 24)] + ["00", "01"]
    grouped['시간대'] = pd.Categorical(grouped['시간대'], categories=time_slots, ordered=True)
    grouped = grouped.sort_values(['역명(호선)', '시간대'])

    grouped['누적인원수'] = grouped.groupby('역명(호선)')['인원수'].cumsum()
    
    # 애니메이션 데이터 생성 로직
    top_n_per_slot = grouped.groupby('시간대').apply(lambda x: x.nlargest(top_n, '누적인원수')).reset_index(drop=True)
    all_top_stations = top_n_per_slot['역명(호선)'].unique()
    
    animation_data = grouped[grouped['역명(호선)'].isin(all_top_stations)]
    return animation_data

# --- 앱 UI 부분 ---
st.header("🏁 시간대별 누적 유동인구 레이싱 차트")
st.markdown("시간의 흐름에 따라 각 역의 **누적** 승하차 인원 순위가 어떻게 변하는지 애니메이션으로 확인합니다. 최종 승자는 누가 될까요?")

df_long = load_and_prep_data()

if df_long is not None:
    combine_stations = st.checkbox("🔁 동일 역명 데이터 합산", help="체크 시, 환승역 데이터를 합산하여 분석합니다.")
    analysis_type = st.radio("📈 분석 기준 선택", ('종합', '승차', '하차'), horizontal=True)
    top_n = st.slider("📊 표시할 순위 (TOP N)", 5, 20, 10)
    animation_speed = st.slider(
        "💨 애니메이션 속도 조절 (ms)",
        min_value=100, max_value=1000, value=300, step=50,
        help="프레임 전환 속도입니다. 값이 낮을수록 빨라집니다."
    )

    # 모든 데이터 처리를 하나의 캐시 함수로 통합하여 호출
    animation_data = get_animation_data(df_long, combine_stations, analysis_type, top_n)

    st.markdown("---")
    st.info("▶️ 아래 그래프의 재생 버튼을 눌러 시간대별 **누적** 순위 변화를 확인하세요!")

    fig = px.bar(
        animation_data,
        x="누적인원수",
        y="역명(호선)",
        orientation='h',
        color="역명(호선)",
        animation_frame="시간대",
        animation_group="역명(호선)",
        text="누적인원수",
        title=f"시간대별 누적 {analysis_type} 인원 TOP {top_n} 레이싱 차트"
    )

    chart_height = top_n * 40 + 150

    fig.update_yaxes(categoryorder="total ascending")
    fig.update_layout(
        xaxis_title="누적 인원수",
        yaxis_title="지하철역",
        showlegend=False,
        height=chart_height,
        margin=dict(l=0, r=0, t=100, b=20)
    )
    
    fig.layout.updatemenus[0].buttons[0].args[1]['frame']['duration'] = animation_speed
    fig.layout.updatemenus[0].buttons[0].args[1]['transition']['duration'] = int(animation_speed * 0.3)
    
    if not animation_data.empty:
        max_value = animation_data['누적인원수'].max()
        fig.update_xaxes(range=[0, max_value * 1.25])
    
    fig.update_traces(texttemplate='%{text:,.0f}', textposition='outside')

    st.plotly_chart(fig, use_container_width=True)

