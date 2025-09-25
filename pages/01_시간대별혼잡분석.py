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

st.header(" busiest subway stations by time of day")
st.markdown("""
- **시간, 승하차, TOP N**을 선택하여 해당 시간대에 가장 붐볐던 역을 확인합니다.
- '동일 역명 데이터 합산'을 체크하면 모든 호선의 이용객을 합산하여 순위를 계산합니다.
""")

if df_long is not None:
    col1, col2 = st.columns([1, 4])
    with col1:
        ride_alight_option = st.radio("승차/하차", ('승차', '하차'))
        
        time_list = sorted(df_long['시간대'].unique())
        start_time, end_time = st.select_slider(
            '시간을 선택하세요.',
            options=time_list,
            value=('08', '09')
        )
        
        top_n = st.slider("TOP N", 5, 20, 10)

        combine_stations = st.checkbox("🔁 동일 역명 데이터 합산", help="체크 시, 모든 호선의 데이터를 합산하여 역별 순위를 계산합니다.")

    # 데이터 필터링
    filtered_df = df_long[
        (df_long['구분'] == ride_alight_option) &
        (df_long['시간대'] >= start_time) &
        (df_long['시간대'] <= end_time)
    ]

    if combine_stations:
        # 역명 기준으로 합산
        station_total = filtered_df.groupby('지하철역')['인원수'].sum().nlargest(top_n)
        station_total = station_total.reset_index()
        station_total['역명(호선)'] = station_total['지하철역']
    else:
        # 기존 방식 (호선 포함)
        station_total = filtered_df.groupby(['호선명', '지하철역'])['인원수'].sum().nlargest(top_n)
        station_total = station_total.reset_index()
        station_total['역명(호선)'] = station_total['지하철역'] + "(" + station_total['호선명'] + ")"
        
    station_total = station_total.sort_values(by='인원수', ascending=True)

    with col2:
        title = f'**{start_time}시~{end_time}시** 가장 **{ride_alight_option}** 인원이 많은 역 (TOP {top_n})'
        st.subheader(title)
        
        fig = px.bar(
            station_total,
            x='인원수',
            y='역명(호선)',
            orientation='h',
            text='인원수'
        )
        fig.update_traces(texttemplate='%{text:,.0f}명', textposition='outside')
        fig.update_layout(
            yaxis_title='지하철역',
            xaxis_title=f'{ride_alight_option} 인원수',
            yaxis={'categoryorder':'total ascending'}
        )
        st.plotly_chart(fig, use_container_width=True)

