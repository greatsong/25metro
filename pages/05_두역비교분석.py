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
            
    return df

# --- 앱 UI 부분 ---
st.header("🆚 두 역 시간대별 데이터 비교")
st.markdown("두 개의 역을 선택하여 시간대별 승차 및 하차 인원 추이를 비교합니다.")

df_clean = load_and_prep_data()

if df_clean is not None:
    combine_stations = st.checkbox("🔁 동일 역명 데이터 합산", help="체크 시, 모든 호선의 데이터를 합산하여 역별 데이터를 분석합니다.")

    # 역 선택 목록 준비
    if combine_stations:
        station_list = sorted(df_clean['지하철역'].unique())
        # 기본 선택 역 설정
        default_station_1 = "강남" if "강남" in station_list else station_list[0]
        default_station_2 = "홍대입구" if "홍대입구" in station_list else station_list[1]
        
        station1_name = st.selectbox("첫 번째 역을 선택하세요.", station_list, index=station_list.index(default_station_1))
        station2_name = st.selectbox("두 번째 역을 선택하세요.", station_list, index=station_list.index(default_station_2))

        # 데이터 집계
        station1_data = df_clean[df_clean['지하철역'] == station1_name].sum(numeric_only=True)
        station2_data = df_clean[df_clean['지하철역'] == station2_name].sum(numeric_only=True)
        
        # 역 이름 포맷팅
        station1_display_name = f"{station1_name} (통합)"
        station2_display_name = f"{station2_name} (통합)"

    else:
        station_list = sorted(list(zip(df_clean['호선명'], df_clean['지하철역'])), key=lambda x: (x[1], x[0]))
        
        # 기본 선택 역 설정
        default_station_1 = ('2호선', '강남')
        default_station_2 = ('2호선', '홍대입구')
        default_index_1 = station_list.index(default_station_1) if default_station_1 in station_list else 0
        default_index_2 = station_list.index(default_station_2) if default_station_2 in station_list else 1

        station1_tuple = st.selectbox("첫 번째 역을 선택하세요.", station_list, index=default_index_1, format_func=lambda x: f"{x[1]} ({x[0]})")
        station2_tuple = st.selectbox("두 번째 역을 선택하세요.", station_list, index=default_index_2, format_func=lambda x: f"{x[1]} ({x[0]})")
        
        # 데이터 추출
        station1_data = df_clean[(df_clean['호선명'] == station1_tuple[0]) & (df_clean['지하철역'] == station1_tuple[1])].iloc[0]
        station2_data = df_clean[(df_clean['호선명'] == station2_tuple[0]) & (df_clean['지하철역'] == station2_tuple[1])].iloc[0]

        # 역 이름 포맷팅
        station1_display_name = f"{station1_tuple[1]} ({station1_tuple[0]})"
        station2_display_name = f"{station2_tuple[1]} ({station2_tuple[0]})"

    # 그래프용 데이터프레임 생성
    time_slots = [f"{h:02d}" for h in range(4, 24)] + ["00", "01"]
    
    data_to_plot = []
    for t in time_slots:
        data_to_plot.append([t, station1_data[f'{t}_승차'], station1_data[f'{t}_하차'], station1_display_name])
        data_to_plot.append([t, station2_data[f'{t}_승차'], station2_data[f'{t}_하차'], station2_display_name])

    plot_df = pd.DataFrame(data_to_plot, columns=['시간대', '승차인원', '하차인원', '역 정보'])

    st.markdown("---")

    # 두 개의 컬럼으로 나누어 그래프 표시
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🔼 승차 인원 비교")
        fig_ride = px.line(
            plot_df,
            x='시간대',
            y='승차인원',
            color='역 정보',
            markers=True,
            title='시간대별 승차 인원'
        )
        fig_ride.update_layout(xaxis_title="시간", yaxis_title="승차 인원수")
        st.plotly_chart(fig_ride, use_container_width=True)

    with col2:
        st.subheader("🔽 하차 인원 비교")
        fig_alight = px.line(
            plot_df,
            x='시간대',
            y='하차인원',
            color='역 정보',
            markers=True,
            title='시간대별 하차 인원'
        )
        fig_alight.update_layout(xaxis_title="시간", yaxis_title="하차 인원수")
        st.plotly_chart(fig_alight, use_container_width=True)
