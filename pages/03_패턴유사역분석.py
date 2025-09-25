import streamlit as st
import pandas as pd
import plotly.express as px
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# 데이터 로딩 함수 (모든 페이지에서 캐시 공유)
@st.cache_data
def load_data():
    dtype_spec = {'호선명': str, '지하철역': str}
    try:
        df = pd.read_csv('지하철데이터.csv', encoding='cp949', dtype=dtype_spec)
    except UnicodeDecodeError:
        df = pd.read_csv('지하철데이터.csv', encoding='utf-8-sig', dtype=dtype_spec)
    except FileNotFoundError:
        st.error("😥 '지하철데이터.csv' 파일을 찾을 수 없습니다. 프로젝트 루트 디렉토리에 파일을 업로드해주세요.")
        return None, None
    
    df.dropna(subset=['호선명', '지하철역'], inplace=True)
    df_raw = df.copy() # 원본 데이터 복사
    df = df.iloc[:, :-1]
    
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
    
    return df_long, df_raw # df_long과 원본 df_raw 반환

# 패턴 분석용 데이터 생성 함수
@st.cache_data
def get_pattern_data(df_raw, combine_stations):
    id_vars = ['사용월', '호선명', '역ID', '지하철역']
    df = df_raw.melt(id_vars=id_vars, var_name='시간구분', value_name='인원수')
    df['시간구분'] = df['시간구분'].str.replace(r'~.*', '', regex=True)

    # 문자열 인원수 -> 숫자 변환
    if df['인원수'].dtype == 'object':
        df['인원수'] = pd.to_numeric(df['인원수'].str.replace(',', ''), errors='coerce').fillna(0)

    if combine_stations:
        df_wide = df.groupby(['지하철역', '시간구분'])['인원수'].sum().unstack()
    else:
        df_wide = df.groupby(['호선명', '지하철역', '시간구분'])['인원수'].sum().unstack()
    
    df_wide.fillna(0, inplace=True)
    
    # --- FIX: 숫자형 데이터만 선택하여 스케일링 수행 ---
    numeric_cols = df_wide.select_dtypes(include=np.number).columns
    
    scaler = MinMaxScaler()
    df_normalized_data = scaler.fit_transform(df_wide[numeric_cols])
    
    df_normalized = pd.DataFrame(df_normalized_data, index=df_wide.index, columns=numeric_cols)
    
    return df_normalized

# --- 앱 UI 부분 ---
st.header("🤔 나와 비슷한 역은 어디?")
st.markdown("선택한 역과 시간대별 승하차 패턴이 가장 유사한 역을 찾아봅니다.")

df_long, df_raw = load_data()

if df_long is not None and df_raw is not None:
    combine_stations = st.checkbox("🔁 동일 역명 데이터 합산", help="체크 시, 모든 호선의 데이터를 합산하여 패턴을 분석합니다.")
    df_pattern_normalized = get_pattern_data(df_raw.copy(), combine_stations)

    if combine_stations:
        station_list = sorted(df_pattern_normalized.index.to_list())
        selected_station_name = st.selectbox("기준이 될 역을 선택하세요.", station_list)
        selected_station_pattern = df_pattern_normalized.loc[selected_station_name]
        
        similarity = cosine_similarity([selected_station_pattern], df_pattern_normalized)
        sim_df = pd.DataFrame(similarity.T, index=df_pattern_normalized.index, columns=['유사도'])
        sim_df = sim_df.drop(selected_station_name).sort_values(by='유사도', ascending=False)
        
        st.subheader(f"'{selected_station_name}'(와)과 패턴이 가장 비슷한 역 TOP 3")
        top_3_similar = sim_df.head(3)
        
    else:
        station_list = sorted(df_pattern_normalized.index.to_list(), key=lambda x: (x[1], x[0]))
        selected_station_tuple = st.selectbox(
            "기준이 될 역을 선택하세요.",
            station_list,
            format_func=lambda x: f"{x[1]} ({x[0]})"
        )
        selected_station_pattern = df_pattern_normalized.loc[selected_station_tuple]

        similarity = cosine_similarity([selected_station_pattern], df_pattern_normalized)
        sim_df = pd.DataFrame(similarity.T, index=df_pattern_normalized.index, columns=['유사도'])
        sim_df = sim_df.drop(selected_station_tuple).sort_values(by='유사도', ascending=False)

        st.subheader(f"'{selected_station_tuple[1]} ({selected_station_tuple[0]})'(와)과 패턴이 가장 비슷한 역 TOP 3")
        top_3_similar = sim_df.head(3)

    for i, (idx, row) in enumerate(top_3_similar.iterrows()):
        rank = i + 1
        station_name_display = f"{idx} (통합)" if combine_stations else f"{idx[1]} ({idx[0]})"
        st.metric(f"👑 {rank}위: {station_name_display}", f"유사도: {row['유사도']:.2%}")

