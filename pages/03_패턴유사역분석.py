import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from sklearn.metrics.pairwise import cosine_similarity

# 데이터 로딩 및 전처리 함수 (오류 수정됨)
@st.cache_data
def load_data():
    dtype_spec = {'호선명': str, '지하철역': str}
    try:
        df = pd.read_csv('지하철데이터.csv', encoding='cp949', dtype=dtype_spec)
    except UnicodeDecodeError:
        df = pd.read_csv('지하철데이터.csv', encoding='utf-8-sig', dtype=dtype_spec)
    except FileNotFoundError:
        st.error("😥 '지하철데이터.csv' 파일을 찾을 수 없습니다. 프로젝트 루트 디렉토리에 파일을 업로드해주세요.")
        return None, None, None
    
    df.dropna(subset=['호선명', '지하철역'], inplace=True)
        
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
    df_long['시간대'] = df_long['시간구분'].str.split('_').str[0]
    df_long['구분'] = df_long['시간구분'].str.split('_').str[1]
    df_long = df_long.drop(columns=['시간구분'])
    
    ride_cols = [c for c in df.columns if '_승차' in c]
    alight_cols = [c for c in df.columns if '_하차' in c]
    df_pattern = df.set_index(['호선명', '지하철역'])[ride_cols + alight_cols]
    df_pattern_normalized = df_pattern.div(df_pattern.sum(axis=1), axis=0).fillna(0)
    
    return df_long, df, df_pattern_normalized

df_long, df_wide, df_pattern_normalized = load_data()

st.title("🤝 패턴 유사역 분석")
st.markdown("특정 역과 시간대별 승하차 패턴이 가장 비슷한 역 3곳을 찾아 비교합니다.")

if df_pattern_normalized is not None and not df_pattern_normalized.empty:
    # 역 선택
    station_list = sorted(df_pattern_normalized.index.to_list(), key=lambda x: x[1])
    selected_station = st.selectbox(
        "기준이 될 역을 선택하세요.",
        station_list,
        format_func=lambda x: f"{x[1]} ({x[0]})"
    )

    # 코사인 유사도 계산
    similarity_matrix = cosine_similarity(df_pattern_normalized)
    similarity_df = pd.DataFrame(similarity_matrix, index=df_pattern_normalized.index, columns=df_pattern_normalized.index)

    # 선택한 역과 다른 역들의 유사도 추출
    similar_stations = similarity_df[selected_station].sort_values(ascending=False)

    # 자기 자신을 제외하고 상위 3개 역 선택
    top_3_similar = similar_stations.iloc[1:4]

    st.markdown("---")
    st.subheader(f"📊 '{selected_station[1]} ({selected_station[0]})' 역과 가장 유사한 역 TOP 3")

    cols = st.columns(3)
    for i, (station, score) in enumerate(top_3_similar.items()):
        with cols[i]:
            st.metric(label=f"🥇 {i+1}위: {station[1]} ({station[0]})", value=f"유사도: {score:.2%}")

    st.markdown("---")
    st.subheader("📈 시간대별 승하차 패턴 비교")

    # 시각화를 위한 데이터 준비
    time_labels = [f"{int(c.split('_')[0]):02d}시" for c in df_wide.columns if '_승차' in c]
    
    # 선택된 역 + 유사역 3곳 데이터 추출
    stations_to_plot = [selected_station] + top_3_similar.index.to_list()
    plot_data = df_wide[df_wide.set_index(['호선명', '지하철역']).index.isin(stations_to_plot)]

    # 승차 패턴 그래프
    fig_ride = go.Figure()
    for _, row in plot_data.iterrows():
        station_name = f"{row['지하철역']} ({row['호선명']})"
        ride_values = row[[c for c in df_wide.columns if '_승차' in c]].values
        fig_ride.add_trace(go.Scatter(
            x=time_labels, 
            y=ride_values, 
            mode='lines+markers', 
            name=station_name,
            line=dict(width=4 if station_name == f"{selected_station[1]} ({selected_station[0]})" else 2),
            opacity=1.0 if station_name == f"{selected_station[1]} ({selected_station[0]})" else 0.7
        ))
    fig_ride.update_layout(title='시간대별 승차 인원 패턴', xaxis_title='시간대', yaxis_title='승차 인원수')
    st.plotly_chart(fig_ride, use_container_width=True)

    # 하차 패턴 그래프
    fig_alight = go.Figure()
    for _, row in plot_data.iterrows():
        station_name = f"{row['지하철역']} ({row['호선명']})"
        alight_values = row[[c for c in df_wide.columns if '_하차' in c]].values
        fig_alight.add_trace(go.Scatter(
            x=time_labels, 
            y=alight_values, 
            mode='lines+markers', 
            name=station_name,
            line=dict(width=4 if station_name == f"{selected_station[1]} ({selected_station[0]})" else 2),
            opacity=1.0 if station_name == f"{selected_station[1]} ({selected_station[0]})" else 0.7
        ))
    fig_alight.update_layout(title='시간대별 하차 인원 패턴', xaxis_title='시간대', yaxis_title='하차 인원수')
    st.plotly_chart(fig_alight, use_container_width=True)

