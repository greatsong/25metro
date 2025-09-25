import streamlit as st
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MinMaxScaler

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
        return None
    
    df.dropna(subset=['호선명', '지하철역'], inplace=True)
    return df

# 원본 데이터 로드
df_raw = load_data()

st.header("📊 나와 비슷한 역은 어디일까?")
st.markdown("시간대별 승하차 패턴을 기준으로, 선택한 역과 가장 유사한 패턴을 보이는 역 3곳을 찾아봅니다.")

if df_raw is not None:
    combine_stations = st.checkbox("🔁 동일 역명 데이터 합산", help="체크 시, 모든 호선의 데이터를 합산하여 역별 패턴을 분석합니다.")

    # 데이터 전처리 및 패턴 생성 (옵션에 따라 동적 처리)
    @st.cache_data
    def get_pattern_data(_df, _combine):
        df = _df.iloc[:, :-1]
        id_vars = ['사용월', '호선명', '역ID', '지하철역']
        if _combine:
            # 호선명, 역ID 제외하고 역명으로만 집계
            value_vars = [c for c in df.columns if c not in id_vars]
            df = df.groupby('지하철역')[value_vars].sum().reset_index()
            id_vars = ['지하철역']
        
        col_names = id_vars[:]
        for i in range(len(id_vars), len(df.columns), 2):
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

        if _combine:
            df_wide = df.set_index('지하철역')
        else:
            df_wide = df.set_index(['호선명', '지하철역'])
        
        scaler = MinMaxScaler()
        df_normalized = pd.DataFrame(scaler.fit_transform(df_wide), index=df_wide.index, columns=df_wide.columns)
        return df_normalized

    df_pattern_normalized = get_pattern_data(df_raw.copy(), combine_stations)
    
    if combine_stations:
        station_list = sorted(df_pattern_normalized.index.tolist())
        format_func = lambda x: x
    else:
        station_list = sorted(df_pattern_normalized.index.to_list())
        format_func = lambda x: f"{x[1]} ({x[0]})"
        
    selected_station = st.selectbox(
        '기준이 될 역을 선택하세요.',
        station_list,
        format_func=format_func
    )

    similarity_matrix = cosine_similarity(df_pattern_normalized)
    similarity_df = pd.DataFrame(similarity_matrix, index=df_pattern_normalized.index, columns=df_pattern_normalized.index)

    if selected_station:
        similar_stations = similarity_df[selected_station].sort_values(ascending=False).iloc[1:4]
        st.subheader(f"📈 '{format_func(selected_station)}' 역과 가장 유사한 역 TOP 3")
        
        for station, score in similar_stations.items():
            st.markdown(f"##### **{format_func(station)}** (유사도: {score:.2f})")
