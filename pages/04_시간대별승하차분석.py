import streamlit as st
import pandas as pd
import plotly.express as px

# 데이터 로딩 및 전처리 함수 (다른 페이지와 동일한 캐시 사용)
@st.cache_data
def load_data():
    """
    지하철 데이터를 불러오고 롱 포맷으로 변환하는 함수.
    """
    dtype_spec = {'호선명': str, '지하철역': str}
    try:
        df = pd.read_csv('지하철데이터.csv', encoding='cp949', dtype=dtype_spec)
    except UnicodeDecodeError:
        df = pd.read_csv('지하철데이터.csv', encoding='utf-8-sig', dtype=dtype_spec)
    except FileNotFoundError:
        st.error("😥 '지하철데이터.csv' 파일을 찾을 수 없습니다. 프로젝트 루트 디렉토리에 파일을 업로드해주세요.")
        return None
    
    # 필수 컬럼에 빈 값이 있는 행 제거
    df.dropna(subset=['호선명', '지하철역'], inplace=True)
        
    # 불필요한 마지막 '등록일자' 열 제거
    df = df.iloc[:, :-1]

    # 컬럼 이름 재정의
    col_names = ['사용월', '호선명', '역ID', '지하철역']
    for i in range(4, len(df.columns), 2):
        time_str = df.columns[i].split('~')[0][:2]
        col_names.append(f'{time_str}_승차')
        col_names.append(f'{time_str}_하차')
    df.columns = col_names

    # 승하차 인원 데이터 숫자형으로 변환
    value_cols = [c for c in df.columns if '_승차' in c or '_하차' in c]
    for col in value_cols:
        if df[col].dtype == 'object':
            df[col] = pd.to_numeric(df[col].str.replace(',', ''), errors='coerce').fillna(0).astype(int)
        else:
            df[col] = df[col].fillna(0).astype(int)

    # Wide to Long 포맷으로 데이터 구조 변경
    id_vars = ['사용월', '호선명', '역ID', '지하철역']
    df_long = df.melt(id_vars=id_vars, var_name='시간구분', value_name='인원수')
    df_long['시간대'] = df_long['시간구분'].str.split('_').str[0]
    df_long['구분'] = df_long['시간구분'].str.split('_').str[1]
    df_long = df_long.drop(columns=['시간구분'])
    return df_long

# 데이터 로드
df_long = load_data()

# 페이지 타이틀 및 설명
st.title("⏰ 시간대별 최다 이용역 분석")
st.markdown("각 시간대별로 승차 또는 하차 인원이 가장 많았던 역은 어디일까요? 시간의 흐름에 따른 '최고의 역'들을 확인해보세요.")

if df_long is not None:
    # --- 기능 추가: 동일 역명 데이터 합산 옵션 ---
    combine_stations = st.checkbox(
        "🔁 동일 역명 데이터 합산하여 보기",
        help="체크 시, '서울역(1호선)', '서울역(4호선)' 등을 '서울역 (통합)'으로 합산하여 분석합니다."
    )
    
    st.markdown("---")

    # 그래프 종류 선택
    chart_type = st.radio(
        "📈 그래프 종류를 선택하세요.",
        ('막대 그래프', '꺾은선 그래프'),
        horizontal=True
    )
    
    st.markdown("---")

    # 데이터 준비
    if combine_stations:
        # 합산 로직: 역명 기준으로 그룹화하여 최다 이용역 정보 추출
        grouped_by_name = df_long.groupby(['시간대', '구분', '지하철역'])['인원수'].sum().reset_index()
        top_station_info = grouped_by_name.loc[grouped_by_name.groupby(['시간대', '구분'])['인원수'].idxmax()]
        
        # 스택 막대 그래프를 위한 데이터 준비
        top_station_filter = top_station_info[['시간대', '구분', '지하철역']]
        plot_data_stacked = pd.merge(df_long, top_station_filter, on=['시간대', '구분', '지하철역'])
        plot_data_stacked = plot_data_stacked.sort_values(by=['시간대', '호선명'])
        
        # 꺾은선 그래프를 위한 데이터 준비 (합산된 총 인원)
        top_stations_by_time_combined = top_station_info.copy()
        top_stations_by_time_combined['역명(호선)'] = top_stations_by_time_combined['지하철역'] + " (통합)"
        top_stations_by_time_combined = top_stations_by_time_combined.sort_values(by='시간대')

    else:
        # 기존 로직: 개별 호선 기준 1위 찾기
        top_stations_by_time_individual = df_long.loc[df_long.groupby(['시간대', '구분'])['인원수'].idxmax()]
        top_stations_by_time_individual['역명(호선)'] = top_stations_by_time_individual['지하철역'] + "(" + top_stations_by_time_individual['호선명'] + ")"
        top_stations_by_time_individual = top_stations_by_time_individual.sort_values(by='시간대')

    # 두 개의 컬럼으로 나누어 그래프 표시
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🔼 시간대별 최다 승차역")
        if combine_stations and chart_type == '막대 그래프':
            # 스택 막대 그래프 (합산 모드)
            data_to_plot = plot_data_stacked[plot_data_stacked['구분'] == '승차']
            fig_ride = px.bar(
                data_to_plot, x='시간대', y='인원수', color='호선명',
                labels={'시간대': '시간대', '인원수': '최다 승차 인원수', '호선명': '호선'},
                title='시간대별 최다 승차역 (호선별 구성)',
                hover_name='지하철역'
            )
            st.info("💡 각 막대는 해당 시간대 최다 이용역의 **호선별 인원 구성**을 보여줍니다.")
        else:
            # 일반 그래프 (개별 모드 또는 꺾은선 그래프)
            data_to_plot = top_stations_by_time_combined[top_stations_by_time_combined['구분'] == '승차'] if combine_stations else top_stations_by_time_individual[top_stations_by_time_individual['구분'] == '승차']
            if chart_type == '막대 그래프':
                fig_ride = px.bar(
                    data_to_plot, x='시간대', y='인원수', color='역명(호선)', text='지하철역',
                    labels={'시간대': '시간대', '인원수': '최다 승차 인원수', '역명(호선)': '역 정보'},
                    title='시간대별 최다 승차역')
                fig_ride.update_traces(textposition='outside')
            else: # 꺾은선 그래프
                fig_ride = px.line(
                    data_to_plot, x='시간대', y='인원수', markers=True, text='역명(호선)',
                    labels={'시간대': '시간대', '인원수': '최다 승차 인원수'},
                    title='시간대별 최다 승차 인원')
                fig_ride.update_traces(textposition='top center', textfont_size=10)
        st.plotly_chart(fig_ride, use_container_width=True)

    with col2:
        st.subheader("🔽 시간대별 최다 하차역")
        if combine_stations and chart_type == '막대 그래프':
            # 스택 막대 그래프 (합산 모드)
            data_to_plot = plot_data_stacked[plot_data_stacked['구분'] == '하차']
            fig_alight = px.bar(
                data_to_plot, x='시간대', y='인원수', color='호선명',
                labels={'시간대': '시간대', '인원수': '최다 하차 인원수', '호선명': '호선'},
                title='시간대별 최다 하차역 (호선별 구성)',
                hover_name='지하철역'
            )
        else:
            # 일반 그래프 (개별 모드 또는 꺾은선 그래프)
            data_to_plot = top_stations_by_time_combined[top_stations_by_time_combined['구분'] == '하차'] if combine_stations else top_stations_by_time_individual[top_stations_by_time_individual['구분'] == '하차']
            if chart_type == '막대 그래프':
                fig_alight = px.bar(
                    data_to_plot, x='시간대', y='인원수', color='역명(호선)', text='지하철역',
                    labels={'시간대': '시간대', '인원수': '최다 하차 인원수', '역명(호선)': '역 정보'},
                    title='시간대별 최다 하차역')
                fig_alight.update_traces(textposition='outside')
            else: # 꺾은선 그래프
                fig_alight = px.line(
                    data_to_plot, x='시간대', y='인원수', markers=True, text='역명(호선)',
                    labels={'시간대': '시간대', '인원수': '최다 하차 인원수'},
                    title='시간대별 최다 하차 인원')
                fig_alight.update_traces(textposition='top center', textfont_size=10)
        st.plotly_chart(fig_alight, use_container_width=True)

