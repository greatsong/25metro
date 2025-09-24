import streamlit as st
import pandas as pd
import plotly.express as px

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

st.title("🕒 시간대별 혼잡 분석")
st.markdown("특정 시간대를 선택하여 승차 및 하차 인원이 가장 많은 지하철역을 확인해보세요.")

if df_long is not None:
    # 시간대 선택 슬라이더
    st.markdown("### ⏰ 분석할 시간대를 선택하세요 (24시간 기준)")
    selected_hours = st.slider(
        "시간을 선택해주세요.",
        0, 23, (7, 9)  # 기본값: 오전 7-9시
    )
    
    start_hour, end_hour = selected_hours
    st.info(f"선택된 시간: **{start_hour:02d}시부터 {end_hour:02d}시까지**")

    # 선택된 시간대의 데이터 필터링
    hour_strings = [f"{h:02d}" for h in range(start_hour, end_hour + 1)]
    filtered_df = df_long[df_long['시간대'].isin(hour_strings)]

    if filtered_df.empty:
        st.warning("선택하신 시간대에 해당하는 데이터가 없습니다.")
    else:
        # 승차/하차 데이터 분리 및 집계
        grouped = filtered_df.groupby(['호선명', '지하철역', '구분'])['인원수'].sum().reset_index()
        
        # 승차 Top 10
        ride_df = grouped[grouped['구분'] == '승차'].sort_values(by='인원수', ascending=False).head(10)
        ride_df['역명(호선)'] = ride_df['지하철역'] + "(" + ride_df['호선명'] + ")"

        # 하차 Top 10
        alight_df = grouped[grouped['구분'] == '하차'].sort_values(by='인원수', ascending=False).head(10)
        alight_df['역명(호선)'] = alight_df['지하철역'] + "(" + alight_df['호선명'] + ")"

        st.markdown("---")
        
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("📈 승차 인원 TOP 10")
            fig_ride = px.bar(
                ride_df, 
                x='인원수', 
                y='역명(호선)', 
                orientation='h',
                title=f'{start_hour:02d}시-{end_hour:02d}시 승차 TOP 10',
                labels={'인원수': '총 승차 인원수', '역명(호선)': '지하철역'},
                color='인원수',
                color_continuous_scale=px.colors.sequential.Viridis
            )
            fig_ride.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_ride, use_container_width=True)

        with col2:
            st.subheader("📉 하차 인원 TOP 10")
            fig_alight = px.bar(
                alight_df, 
                x='인원수', 
                y='역명(호선)', 
                orientation='h',
                title=f'{start_hour:02d}시-{end_hour:02d}시 하차 TOP 10',
                labels={'인원수': '총 하차 인원수', '역명(호선)': '지하철역'},
                color='인원수',
                color_continuous_scale=px.colors.sequential.Plasma
            )
            fig_alight.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_alight, use_container_width=True)

