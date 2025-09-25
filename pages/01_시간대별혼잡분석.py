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
st.header("🕒 시간대별 혼잡도 분석")
st.markdown("선택한 시간 범위 내에서 승하차 인원이 가장 많은 역의 순위를 확인합니다.")

df_long = load_and_prep_data()

if df_long is not None:
    top_n = st.slider("📈 TOP N 선택", 5, 30, 10)
    combine_stations = st.checkbox("🔁 동일 역명 데이터 합산", help="체크 시, 모든 호선의 데이터를 합산하여 역별 순위를 계산합니다.")

    # --- FIX: 시간 순서를 올바르게 정의하여 슬라이더에 적용 ---
    time_slots = [f"{h:02d}" for h in range(4, 24)] + ["00", "01"]
    selected_hour_start, selected_hour_end = st.select_slider(
        '⏰ 시간 범위를 선택하세요.',
        options=time_slots,
        value=('08', '18')
    )

    # 선택된 시간 범위에 해당하는 시간 슬롯 필터링
    start_index = time_slots.index(selected_hour_start)
    end_index = time_slots.index(selected_hour_end)
    if start_index <= end_index:
        selected_times = time_slots[start_index:end_index+1]
    else: # 23시 -> 01시처럼 자정을 넘어가는 경우
        selected_times = time_slots[start_index:] + time_slots[:end_index+1]

    # 데이터 집계
    df_filtered = df_long[df_long['시간대'].isin(selected_times)]
    
    if combine_stations:
        grouped = df_filtered.groupby(['지하철역', '구분'])['인원수'].sum().reset_index()
        grouped['역명(호선)'] = grouped['지하철역'] + " (통합)"
    else:
        grouped = df_filtered.groupby(['호선명', '지하철역', '구분'])['인원수'].sum().reset_index()
        grouped['역명(호선)'] = grouped['지하철역'] + "(" + grouped['호선명'] + ")"
        
    st.markdown("---")

    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🔼 승차 TOP")
        ride_data = grouped[grouped['구분'] == '승차'].nlargest(top_n, '인원수').sort_values('인원수', ascending=True)
        fig_ride = px.bar(
            ride_data, x='인원수', y='역명(호선)', orientation='h', text='인원수',
            title=f'{selected_hour_start}시-{selected_hour_end}시 승차 TOP {top_n}'
        )
        fig_ride.update_traces(texttemplate='%{text:,.0f}명', textposition='outside')
        fig_ride.update_layout(yaxis_title='지하철역', xaxis_title='총 승차 인원수', height=top_n*35+150)
        st.plotly_chart(fig_ride, use_container_width=True)

    with col2:
        st.subheader("🔽 하차 TOP")
        alight_data = grouped[grouped['구분'] == '하차'].nlargest(top_n, '인원수').sort_values('인원수', ascending=True)
        fig_alight = px.bar(
            alight_data, x='인원수', y='역명(호선)', orientation='h', text='인원수',
            title=f'{selected_hour_start}시-{selected_hour_end}시 하차 TOP {top_n}'
        )
        fig_alight.update_traces(texttemplate='%{text:,.0f}명', textposition='outside')
        fig_alight.update_layout(yaxis_title='지하철역', xaxis_title='총 하차 인원수', height=top_n*35+150)
        st.plotly_chart(fig_alight, use_container_width=True)

