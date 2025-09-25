import streamlit as st
import pandas as pd
import plotly.express as px
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

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

# 패턴 분석용 데이터 생성 함수
@st.cache_data
def get_pattern_data(df_clean, combine_stations):
    """
    전처리된 데이터프레임을 받아 그룹화 및 정규화를 수행합니다.
    """
    value_cols = [c for c in df_clean.columns if '_승차' in c or '_하차' in c]

    if combine_stations:
        df_wide = df_clean.groupby('지하철역')[value_cols].sum()
    else:
        df_wide = df_clean.set_index(['호선명', '지하철역'])[value_cols]
    
    df_wide.fillna(0, inplace=True)
    
    # --- FIX: 정규화 방식을 '각 역의 총합으로 나눈 비율'로 변경 ---
    # 각 역(행)의 총합을 계산합니다.
    row_sums = df_wide.sum(axis=1)
    # 총합이 0인 경우 0으로 나누는 것을 방지하기 위해 1로 바꿔줍니다.
    row_sums[row_sums == 0] = 1
    # 각 역의 데이터를 해당 역의 총합으로 나누어 비율을 만듭니다.
    df_normalized = df_wide.div(row_sums, axis=0)
    
    return df_normalized

# --- 앱 UI 부분 ---
st.header("🤔 나와 비슷한 역은 어디?")
st.markdown("선택한 역과 시간대별 승하차 패턴이 가장 유사한 역을 찾아봅니다.")

df_clean = load_and_prep_data()

if df_clean is not None:
    combine_stations = st.checkbox("🔁 동일 역명 데이터 합산", help="체크 시, 모든 호선의 데이터를 합산하여 패턴을 분석합니다.")
    
    top_n = st.slider("📊 비교할 유사역 개수 (TOP N)", 1, 10, 3, help="비교하고 싶은 상위 유사역의 개수를 선택하세요.")

    df_pattern_normalized = get_pattern_data(df_clean.copy(), combine_stations)

    if combine_stations:
        station_list = sorted(df_pattern_normalized.index.to_list())
        selected_station_name = st.selectbox("기준이 될 역을 선택하세요.", station_list)
        selected_station_pattern = df_pattern_normalized.loc[selected_station_name]
        
        similarity = cosine_similarity([selected_station_pattern], df_pattern_normalized)
        sim_df = pd.DataFrame(similarity.T, index=df_pattern_normalized.index, columns=['유사도'])
        sim_df = sim_df.drop(selected_station_name).sort_values(by='유사도', ascending=False)
        
        st.subheader(f"'{selected_station_name}'(와)과 패턴이 가장 비슷한 역 TOP {top_n}")
        top_n_similar = sim_df.head(top_n)
        
    else:
        station_list = sorted(df_pattern_normalized.index.to_list(), key=lambda x: (x[1], x[0]))
        
        default_station = ('2호선', '강남')
        default_index = 0
        if default_station in station_list:
            default_index = station_list.index(default_station)
            
        selected_station_tuple = st.selectbox(
            "기준이 될 역을 선택하세요.",
            station_list,
            index=default_index,
            format_func=lambda x: f"{x[1]} ({x[0]})"
        )
        selected_station_pattern = df_pattern_normalized.loc[selected_station_tuple]

        similarity = cosine_similarity([selected_station_pattern], df_pattern_normalized)
        sim_df = pd.DataFrame(similarity.T, index=df_pattern_normalized.index, columns=['유사도'])
        sim_df = sim_df.drop(selected_station_tuple).sort_values(by='유사도', ascending=False)

        st.subheader(f"'{selected_station_tuple[1]} ({selected_station_tuple[0]})'(와)과 패턴이 가장 비슷한 역 TOP {top_n}")
        top_n_similar = sim_df.head(top_n)

    for i, (idx, row) in enumerate(top_n_similar.iterrows()):
        rank = i + 1
        station_name_display = f"{idx} (통합)" if combine_stations else f"{idx[1]} ({idx[0]})"
        st.metric(f"👑 {rank}위: {station_name_display}", f"유사도: {row['유사도']:.2%}")

    # --- 패턴 비교 그래프 ---
    st.markdown("---")
    st.subheader("📊 패턴 비교 그래프")
    st.markdown(f"기준 역과 TOP {top_n} 유사역의 시간대별 인원 패턴(비율 기준)을 비교합니다.")

    if combine_stations:
        stations_to_plot = [selected_station_name] + top_n_similar.index.to_list()
    else:
        stations_to_plot = [selected_station_tuple] + top_n_similar.index.to_list()

    plot_df = df_pattern_normalized.loc[stations_to_plot].T.reset_index()
    
    plot_df = plot_df.rename(columns={plot_df.columns[0]: '시간구분'})

    if not combine_stations:
        new_columns = ['시간구분']
        for col in plot_df.columns[1:]:
            new_columns.append(f"{col[1]} ({col[0]})")
        plot_df.columns = new_columns
    
    plot_df_long = plot_df.melt(
        id_vars='시간구분',
        var_name='역 정보',
        value_name='정규화된 인원수 (비율)'
    )

    fig = px.line(
        plot_df_long,
        x='시간구분',
        y='정규화된 인원수 (비율)',
        color='역 정보',
        markers=True,
        title='선택역 및 유사역 패턴 비교'
    )
    fig.update_layout(
        xaxis_title="시간 구분",
        yaxis_title="정규화된 인원수 (비율)",
        legend_title="역 정보",
        xaxis={'tickangle': -45}
    )
    st.plotly_chart(fig, use_container_width=True)

