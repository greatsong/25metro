import streamlit as st
import pandas as pd
import plotly.express as px

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
    return df_long

df_long = load_data()

st.header("🚉 유동인구가 가장 많은 역은?")
st.markdown("전체 또는 특정 호선에서 하루 동안 가장 많은 사람이 오고 간 역을 확인합니다.")

if df_long is not None:
    top_n = st.slider("📈 TOP N 선택", 5, 50, 20)
    combine_stations = st.checkbox("🔁 동일 역명 데이터 합산", help="체크 시, 모든 호선의 데이터를 합산하여 역별 순위를 계산합니다.")

    # 데이터 집계
    if combine_stations:
        st.info("동일 역명 합산 모드에서는 전체 호선 기준으로 유동인구를 분석합니다.")
        total_traffic = df_long.groupby('지하철역')['인원수'].sum().nlargest(top_n).reset_index()
        total_traffic['역명(호선)'] = total_traffic['지하철역'] + " (통합)"
    else:
        line_list = ['전체'] + sorted(df_long['호선명'].unique())
        selected_line = st.selectbox('호선을 선택하세요.', line_list)
        
        if selected_line == '전체':
            df_filtered = df_long
        else:
            df_filtered = df_long[df_long['호선명'] == selected_line]
        
        total_traffic = df_filtered.groupby(['호선명', '지하철역'])['인원수'].sum().nlargest(top_n).reset_index()
        total_traffic['역명(호선)'] = total_traffic['지하철역'] + "(" + total_traffic['호선명'] + ")"

    # 1위 역 정보 추출 및 표시
    if not total_traffic.empty:
        top_station = total_traffic.sort_values(by='인원수', ascending=False).iloc[0]
        st.subheader("🏆 유동인구 최다 역")
        st.metric(
            label=f"**{top_station['역명(호선)']}**",
            value=f"{top_station['인원수']:,} 명"
        )
        st.markdown("---")
        
    # 수평 막대 그래프를 위해 오름차순 정렬 (큰 값이 위로)
    total_traffic_sorted_for_plot = total_traffic.sort_values(by='인원수', ascending=True)
    
    # 시각화
    st.subheader(f"📈 유동인구 TOP {top_n} 역")
    fig = px.bar(
        total_traffic_sorted_for_plot,
        x='인원수',
        y='역명(호선)',
        orientation='h',
        text='인원수',
        title='총 승하차 인원수 기준'
    )
    fig.update_traces(texttemplate='%{text:,.0f}명', textposition='outside')
    
    # --- FIX: 가장 긴 막대의 텍스트가 잘리지 않도록 x축 범위 자동 조정 ---
    if not total_traffic_sorted_for_plot.empty:
        max_value = total_traffic_sorted_for_plot['인원수'].max()
        fig.update_layout(
            yaxis_title='지하철역', 
            xaxis_title='총 인원수', 
            yaxis={'categoryorder':'total ascending'},
            xaxis=dict(range=[0, max_value * 1.15]) # x축 범위에 15% 여유 공간 추가
        )
    st.plotly_chart(fig, use_container_width=True)

