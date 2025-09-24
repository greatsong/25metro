import streamlit as st
import pandas as pd
import plotly.express as px

# 데이터 로딩 및 전처리 함수 (app.py와 동일한 함수)
@st.cache_data
def load_data():
    try:
        df = pd.read_csv('지하철데이터.csv', encoding='cp949')
    except FileNotFoundError:
        st.error("😥 '지하철데이터.csv' 파일을 찾을 수 없습니다. 프로젝트 루트 디렉토리에 파일을 업로드해주세요.")
        return None
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
            df[col] = df[col].str.replace(',', '').astype(int)
        else:
            df[col] = df[col].astype(int)
    id_vars = ['사용월', '호선명', '역ID', '지하철역']
    df_long = df.melt(id_vars=id_vars, var_name='시간구분', value_name='인원수')
    df_long['시간대'] = df_long['시간구분'].str.split('_').str[0]
    df_long['구분'] = df_long['시간구분'].str.split('_').str[1]
    df_long = df_long.drop(columns=['시간구분'])
    return df_long

df_long = load_data()

st.title("🚶 유동인구 분석")
st.markdown("총 승하차 인원을 기준으로 유동인구가 가장 많은 역을 전체 및 호선별로 살펴봅니다.")

if df_long is not None:
    # 역별 총 유동인구 계산
    total_traffic = df_long.groupby(['호선명', '지하철역'])['인원수'].sum().reset_index()
    total_traffic = total_traffic.sort_values(by='인원수', ascending=False)
    total_traffic.rename(columns={'인원수': '총유동인구'}, inplace=True)
    total_traffic['역명(호선)'] = total_traffic['지하철역'] + "(" + total_traffic['호선명'] + ")"

    st.markdown("---")

    # 전체 유동인구 TOP 15
    st.subheader("👑 서울 전체 유동인구 TOP 15")
    top_15_all = total_traffic.head(15)
    fig_all = px.bar(
        top_15_all,
        x='총유동인구',
        y='역명(호선)',
        orientation='h',
        title='서울 지하철 전체 유동인구 TOP 15',
        labels={'총유동인구': '총 유동인구 (승하차 합계)', '역명(호선)': '지하철역'},
        color='총유동인구',
        color_continuous_scale=px.colors.sequential.Cividis_r
    )
    fig_all.update_layout(yaxis={'categoryorder':'total ascending'})
    st.plotly_chart(fig_all, use_container_width=True)

    st.markdown("---")

    # 호선별 유동인구 분석
    st.subheader("🚇 호선별 유동인구 분석")
    
    # 호선 선택
    line_list = ['전체'] + sorted(df_long['호선명'].unique())
    selected_line = st.selectbox('분석할 호선을 선택하세요.', line_list)

    if selected_line == '전체':
        st.info("현재 전체 호선에 대한 유동인구 순위를 보고 계십니다. 특정 호선을 선택하여 자세히 살펴보세요.")
    else:
        line_traffic = total_traffic[total_traffic['호선명'] == selected_line].head(15)
        
        fig_line = px.bar(
            line_traffic,
            x='총유동인구',
            y='지하철역',
            orientation='h',
            title=f'{selected_line} 유동인구 TOP 15',
            labels={'총유동인구': '총 유동인구 (승하차 합계)', '지하철역': f'{selected_line} 역'},
            color='총유동인구',
            color_continuous_scale=px.colors.sequential.OrRd
        )
        fig_line.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_line, use_container_width=True)

