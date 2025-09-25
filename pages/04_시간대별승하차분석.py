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
st.header("🏆 시간대별 1위 역 변천사")
st.markdown("각 시간대별로 가장 많은 사람이 이용한 역은 어디일까요? 시간의 흐름에 따른 '챔피언'의 변화를 확인해보세요.")

df_long = load_and_prep_data()

if df_long is not None:
    combine_stations = st.checkbox("🔁 동일 역명 데이터 합산", help="체크 시, 환승역 데이터를 합산하여 분석합니다.")
    
    show_line_contribution = False
    if combine_stations:
        show_line_contribution = st.checkbox("📊 호선별 구성 보기 (스택 그래프)", help="체크 시, 1위 역의 총 이용객이 각 호선별로 얼마나 구성되는지 보여줍니다.")

    st.markdown("---")

    # 데이터 준비
    if combine_stations:
        grouped_by_name = df_long.groupby(['시간대', '구분', '지하철역'])['인원수'].sum().reset_index()
        top_station_info = grouped_by_name.loc[grouped_by_name.groupby(['시간대', '구분'])['인원수'].idxmax()]
        
        top_station_filter = top_station_info[['시간대', '구분', '지하철역']]
        plot_data_stacked = pd.merge(df_long, top_station_filter, on=['시간대', '구분', '지하철역'])
        
        top_stations_by_time_combined = top_station_info.copy()
        top_stations_by_time_combined['역명(호선)'] = top_stations_by_time_combined['지하철역'] + " (통합)"

    else:
        top_stations_by_time_individual = df_long.loc[df_long.groupby(['시간대', '구분'])['인원수'].idxmax()]
        top_stations_by_time_individual['역명(호선)'] = top_stations_by_time_individual['지하철역'] + "(" + top_stations_by_time_individual['호선명'] + ")"

    # 시간 순서를 올바르게 정의
    time_slots = [f"{h:02d}" for h in range(4, 24)] + ["00", "01"]

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🔼 시간대별 최다 승차역")
        data_ride = (top_stations_by_time_combined if combine_stations else top_stations_by_time_individual).copy()
        data_ride = data_ride[data_ride['구분'] == '승차']

        # 데이터 자체에 시간 순서를 명확하게 정의
        data_ride['시간대'] = pd.Categorical(data_ride['시간대'], categories=time_slots, ordered=True)
        data_ride = data_ride.sort_values('시간대')

        if show_line_contribution:
            plot_data_ride = plot_data_stacked[plot_data_stacked['구분'] == '승차'].copy()
            plot_data_ride['시간대'] = pd.Categorical(plot_data_ride['시간대'], categories=time_slots, ordered=True)
            plot_data_ride = plot_data_ride.sort_values('시간대')
            
            fig_ride = px.bar(
                plot_data_ride, x='시간대', y='인원수', color='호선명', text='지하철역',
                title='시간대별 최다 승차역 (호선별 구성)'
            )
            fig_ride.update_traces(textposition='outside')
        else:
            fig_ride = px.bar(
                data_ride, x='시간대', y='인원수', color='역명(호선)', text='지하철역',
                title='시간대별 최다 승차역'
            )
            fig_ride.update_traces(textposition='outside')
        st.plotly_chart(fig_ride, use_container_width=True)

    with col2:
        st.subheader("🔽 시간대별 최다 하차역")
        data_alight = (top_stations_by_time_combined if combine_stations else top_stations_by_time_individual).copy()
        data_alight = data_alight[data_alight['구분'] == '하차']

        # 데이터 자체에 시간 순서를 명확하게 정의
        data_alight['시간대'] = pd.Categorical(data_alight['시간대'], categories=time_slots, ordered=True)
        data_alight = data_alight.sort_values('시간대')

        if show_line_contribution:
            plot_data_alight = plot_data_stacked[plot_data_stacked['구분'] == '하차'].copy()
            plot_data_alight['시간대'] = pd.Categorical(plot_data_alight['시간대'], categories=time_slots, ordered=True)
            plot_data_alight = plot_data_alight.sort_values('시간대')

            fig_alight = px.bar(
                plot_data_alight, x='시간대', y='인원수', color='호선명', text='지하철역',
                title='시간대별 최다 하차역 (호선별 구성)'
            )
            fig_alight.update_traces(textposition='outside')
        else:
            fig_alight = px.bar(
                data_alight, x='시간대', y='인원수', color='역명(호선)', text='지하철역',
                title='시간대별 최다 하차역'
            )
            fig_alight.update_traces(textposition='outside')
        st.plotly_chart(fig_alight, use_container_width=True)

