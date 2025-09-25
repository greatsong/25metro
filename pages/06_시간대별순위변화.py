import streamlit as st
import pandas as pd
import plotly.express as px

# 데이터 로딩 및 전처리 함수
@st.cache_data
def load_and_prep_data():
    """
    데이터를 로드하고 모든 전처리를 수행하여 분석에 바로 사용할 수 있는
    깨끗한 '와이드' 포맷의 데이터프레임을 반환합니다.
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
    df = df.iloc[:, :-1].copy() # 불필요한 마지막 열 제거 및 복사본 생성
    
    # 컬럼 이름 재정의
    col_names = ['사용월', '호선명', '역ID', '지하철역']
    for i in range(4, len(df.columns), 2):
        time_str = df.columns[i].split('~')[0][:2]
        col_names.append(f'{time_str}_승차')
        col_names.append(f'{time_str}_하차')
    df.columns = col_names
    
    # 인원수 데이터 숫자형으로 변환
    value_cols = [c for c in df.columns if '_승차' in c or '_하차' in c]
    for col in value_cols:
        if df[col].dtype == 'object':
            df[col] = pd.to_numeric(df[col].str.replace(',', ''), errors='coerce').fillna(0).astype(int)
        else:
            df[col] = df[col].fillna(0).astype(int)
            
    # Long format으로 변환
    id_vars = ['사용월', '호선명', '역ID', '지하철역']
    df_long = df.melt(id_vars=id_vars, var_name='시간구분', value_name='인원수')
    df_long['시간대'] = df_long['시간구분'].str.split('_').str[0]
    df_long['구분'] = df_long['시간구분'].str.split('_').str[1]
    df_long = df_long.drop(columns=['시간구분'])
    return df_long

# --- 앱 UI 부분 ---
st.header("🏁 시간대별 누적 유동인구 레이싱 차트")
st.markdown("시간의 흐름에 따라 각 역의 **누적** 승하차 인원 순위가 어떻게 변하는지 애니메이션으로 확인합니다. 최종 승자는 누가 될까요?")

df_long = load_and_prep_data()

if df_long is not None:
    combine_stations = st.checkbox("🔁 동일 역명 데이터 합산", help="체크 시, 환승역 데이터를 합산하여 분석합니다.")
    analysis_type = st.radio("📈 분석 기준 선택", ('종합', '승차', '하차'), horizontal=True)
    top_n = st.slider("📊 표시할 순위 (TOP N)", 5, 20, 10)
    
    # --- NEW: 애니메이션 속도 조절 슬라이더 추가 ---
    animation_speed = st.slider(
        "💨 애니메이션 속도 조절 (ms)",
        min_value=100, max_value=1000, value=300, step=50,
        help="프레임 전환 속도입니다. 값이 낮을수록 빨라집니다."
    )

    # 분석 기준에 따라 데이터 필터링
    if analysis_type != '종합':
        df_long = df_long[df_long['구분'] == analysis_type]

    # 데이터 집계
    if combine_stations:
        grouped = df_long.groupby(['시간대', '지하철역'])['인원수'].sum().reset_index()
        grouped['역명(호선)'] = grouped['지하철역']
    else:
        grouped = df_long.groupby(['시간대', '호선명', '지하철역'])['인원수'].sum().reset_index()
        grouped['역명(호선)'] = grouped['지하철역'] + "(" + grouped['호선명'] + ")"

    # 시간 순서 정의 및 데이터 정렬
    time_slots = [f"{h:02d}" for h in range(4, 24)] + ["00", "01"]
    grouped['시간대'] = pd.Categorical(grouped['시간대'], categories=time_slots, ordered=True)
    grouped = grouped.sort_values(['역명(호선)', '시간대'])

    # 누적 인원수 계산
    grouped['누적인원수'] = grouped.groupby('역명(호선)')['인원수'].cumsum()

    # 각 시간대별 TOP N 필터링 (누적 인원수 기준)
    animation_data = grouped.groupby('시간대').apply(lambda x: x.nlargest(top_n, '누적인원수')).reset_index(drop=True)

    st.markdown("---")
    st.info("▶️ 아래 그래프의 재생 버튼을 눌러 시간대별 **누적** 순위 변화를 확인하세요!")

    # 애니메이션 바 차트 생성
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

    # 각 프레임의 y축 순서 및 x축 범위 설정
    fig.update_yaxes(categoryorder="total ascending")
    fig.update_layout(
        xaxis_title="누적 인원수",
        yaxis_title="지하철역",
        showlegend=False,
        height=600,
    )
    
    # --- FIX: 슬라이더 값으로 애니메이션 속도 조절 ---
    fig.layout.updatemenus[0].buttons[0].args[1]['frame']['duration'] = animation_speed
    fig.layout.updatemenus[0].buttons[0].args[1]['transition']['duration'] = int(animation_speed * 0.3) # 전환 효과는 더 빠르게
    
    max_value = animation_data['누적인원수'].max()
    fig.update_xaxes(range=[0, max_value * 1.2])
    fig.update_traces(texttemplate='%{text:,.0f}', textposition='outside')

    st.plotly_chart(fig, use_container_width=True)

