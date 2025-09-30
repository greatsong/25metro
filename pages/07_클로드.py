import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

# 페이지 설정
st.set_page_config(page_title="서울 지하철 승하차 분석", layout="wide", page_icon="🚇")

# 타이틀
st.title("🚇 서울 지하철 승하차 데이터 분석 대시보드")
st.markdown("#### 2025년 8월 시간대별 승하차 패턴 인사이트")

# 데이터 로드 함수
@st.cache_data
def load_data():
    # CSV 파일 읽기 - 헤더가 2줄이므로 특별 처리
    df = pd.read_csv('지하철데이터.csv', encoding='utf-8', skiprows=1)
    
    # 컬럼명 정리
    time_slots = [
        '04:00', '05:00', '06:00', '07:00', '08:00', '09:00',
        '10:00', '11:00', '12:00', '13:00', '14:00', '15:00',
        '16:00', '17:00', '18:00', '19:00', '20:00', '21:00',
        '22:00', '23:00', '00:00', '01:00', '02:00', '03:00'
    ]
    
    new_columns = ['사용월', '호선명', '역ID', '지하철역']
    for time in time_slots:
        new_columns.extend([f'{time}_승차', f'{time}_하차'])
    new_columns.append('작업일시')
    
    df.columns = new_columns
    
    # 숫자 컬럼 정리 (콤마 제거 및 숫자 변환)
    for col in df.columns[4:-1]:
        if '_승차' in col or '_하차' in col:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    
    return df, time_slots

# 데이터 로드
df, time_slots = load_data()

# 사이드바 필터
st.sidebar.header("🔍 필터 옵션")

# 호선 선택
lines = sorted(df['호선명'].unique())
selected_line = st.sidebar.selectbox("호선 선택", ['전체'] + lines)

# 필터링된 데이터
if selected_line == '전체':
    filtered_df = df.copy()
else:
    filtered_df = df[df['호선명'] == selected_line].copy()

# 역 선택
stations = sorted(filtered_df['지하철역'].unique())
selected_station = st.sidebar.selectbox("역 선택 (상세 분석용)", ['전체'] + stations)

# 메인 대시보드
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 전체 현황", 
    "⏰ 시간대별 분석", 
    "🏆 역별 순위", 
    "🔄 승하차 불균형", 
    "🗺️ 히트맵"
])

# Tab 1: 전체 현황
with tab1:
    col1, col2, col3, col4 = st.columns(4)
    
    # 총 승차 인원
    total_board = sum(filtered_df[f'{time}_승차'].sum() for time in time_slots)
    col1.metric("총 승차 인원", f"{total_board:,.0f}명")
    
    # 총 하차 인원
    total_alight = sum(filtered_df[f'{time}_하차'].sum() for time in time_slots)
    col2.metric("총 하차 인원", f"{total_alight:,.0f}명")
    
    # 일평균 이용자
    daily_avg = (total_board + total_alight) / 31 / 2
    col3.metric("일평균 이용자", f"{daily_avg:,.0f}명")
    
    # 역 수
    col4.metric("분석 역 수", f"{len(filtered_df)}개역")
    
    st.markdown("---")
    
    # 호선별 이용 현황
    if selected_line == '전체':
        st.subheader("📈 호선별 이용 현황")
        
        line_stats = []
        for line in lines:
            line_df = df[df['호선명'] == line]
            line_board = sum(line_df[f'{time}_승차'].sum() for time in time_slots)
            line_alight = sum(line_df[f'{time}_하차'].sum() for time in time_slots)
            line_stats.append({
                '호선': line,
                '승차': line_board,
                '하차': line_alight,
                '총 이용': line_board + line_alight
            })
        
        line_stats_df = pd.DataFrame(line_stats).sort_values('총 이용', ascending=False)
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.bar(line_stats_df, x='호선', y=['승차', '하차'],
                        title='호선별 승하차 인원',
                        labels={'value': '인원', 'variable': '구분'},
                        barmode='group',
                        color_discrete_map={'승차': '#FF6B6B', '하차': '#4ECDC4'})
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig = px.pie(line_stats_df, values='총 이용', names='호선',
                        title='호선별 이용 비율',
                        color_discrete_sequence=px.colors.qualitative.Bold)
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

# Tab 2: 시간대별 분석
with tab2:
    st.subheader("⏰ 시간대별 승하차 패턴")
    
    if selected_station != '전체':
        # 특정 역의 시간대별 패턴
        station_df = filtered_df[filtered_df['지하철역'] == selected_station].iloc[0]
        
        hourly_data = []
        for time in time_slots:
            hourly_data.append({
                '시간대': time,
                '승차': station_df[f'{time}_승차'],
                '하차': station_df[f'{time}_하차']
            })
        hourly_df = pd.DataFrame(hourly_data)
        
        st.markdown(f"### 📍 {selected_station}역 시간대별 패턴")
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hourly_df['시간대'], y=hourly_df['승차'],
                                mode='lines+markers', name='승차',
                                line=dict(color='#FF6B6B', width=3),
                                marker=dict(size=8)))
        fig.add_trace(go.Scatter(x=hourly_df['시간대'], y=hourly_df['하차'],
                                mode='lines+markers', name='하차',
                                line=dict(color='#4ECDC4', width=3),
                                marker=dict(size=8)))
        
        fig.update_layout(
            title=f'{selected_station}역 시간대별 승하차 인원',
            xaxis_title='시간대',
            yaxis_title='인원 (명)',
            hovermode='x unified',
            height=500
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # 주요 통계
        col1, col2, col3 = st.columns(3)
        
        peak_board_time = hourly_df.loc[hourly_df['승차'].idxmax(), '시간대']
        peak_board_count = hourly_df['승차'].max()
        col1.metric("승차 피크 시간", peak_board_time, f"{peak_board_count:,.0f}명")
        
        peak_alight_time = hourly_df.loc[hourly_df['하차'].idxmax(), '시간대']
        peak_alight_count = hourly_df['하차'].max()
        col2.metric("하차 피크 시간", peak_alight_time, f"{peak_alight_count:,.0f}명")
        
        total_station = hourly_df['승차'].sum() + hourly_df['하차'].sum()
        col3.metric("월 총 이용", f"{total_station:,.0f}명")
        
    else:
        # 전체 시간대별 패턴
        hourly_totals = []
        for time in time_slots:
            board = filtered_df[f'{time}_승차'].sum()
            alight = filtered_df[f'{time}_하차'].sum()
            hourly_totals.append({
                '시간대': time,
                '승차': board,
                '하차': alight
            })
        hourly_df = pd.DataFrame(hourly_totals)
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hourly_df['시간대'], y=hourly_df['승차'],
                                mode='lines+markers', name='승차',
                                fill='tozeroy',
                                line=dict(color='#FF6B6B', width=3)))
        fig.add_trace(go.Scatter(x=hourly_df['시간대'], y=hourly_df['하차'],
                                mode='lines+markers', name='하차',
                                fill='tozeroy',
                                line=dict(color='#4ECDC4', width=3)))
        
        fig.update_layout(
            title='전체 시간대별 승하차 인원',
            xaxis_title='시간대',
            yaxis_title='인원 (명)',
            hovermode='x unified',
            height=500
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # 출퇴근 시간대 분석
        st.markdown("### 🚶 출퇴근 시간대 특성")
        col1, col2 = st.columns(2)
        
        with col1:
            morning_rush = hourly_df[hourly_df['시간대'].isin(['07:00', '08:00', '09:00'])]
            st.info(f"**아침 출근 시간 (07~09시)**\n\n"
                   f"- 승차: {morning_rush['승차'].sum():,.0f}명\n"
                   f"- 하차: {morning_rush['하차'].sum():,.0f}명\n"
                   f"- 승차 비율: {morning_rush['승차'].sum()/(morning_rush['승차'].sum()+morning_rush['하차'].sum())*100:.1f}%")
        
        with col2:
            evening_rush = hourly_df[hourly_df['시간대'].isin(['18:00', '19:00', '20:00'])]
            st.info(f"**저녁 퇴근 시간 (18~20시)**\n\n"
                   f"- 승차: {evening_rush['승차'].sum():,.0f}명\n"
                   f"- 하차: {evening_rush['하차'].sum():,.0f}명\n"
                   f"- 하차 비율: {evening_rush['하차'].sum()/(evening_rush['승차'].sum()+evening_rush['하차'].sum())*100:.1f}%")

# Tab 3: 역별 순위
with tab3:
    st.subheader("🏆 역별 이용 순위")
    
    # 역별 통계 계산
    station_stats = []
    for idx, row in filtered_df.iterrows():
        total_board = sum(row[f'{time}_승차'] for time in time_slots)
        total_alight = sum(row[f'{time}_하차'] for time in time_slots)
        station_stats.append({
            '호선': row['호선명'],
            '역명': row['지하철역'],
            '승차': total_board,
            '하차': total_alight,
            '총 이용': total_board + total_alight
        })
    
    station_stats_df = pd.DataFrame(station_stats).sort_values('총 이용', ascending=False)
    
    # Top/Bottom 선택
    rank_type = st.radio("순위 유형", ['Top 20 (이용 많은 역)', 'Bottom 20 (이용 적은 역)'], horizontal=True)
    
    if rank_type == 'Top 20 (이용 많은 역)':
        display_df = station_stats_df.head(20)
        color_scale = 'Reds'
    else:
        display_df = station_stats_df.tail(20).sort_values('총 이용')
        color_scale = 'Blues'
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        fig = px.bar(display_df, y='역명', x='총 이용',
                    orientation='h',
                    title=f'{rank_type} 역',
                    labels={'총 이용': '총 이용자 수', '역명': ''},
                    color='총 이용',
                    color_continuous_scale=color_scale)
        fig.update_layout(height=600, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("#### 📋 상세 데이터")
        display_detail = display_df.copy()
        display_detail['승차'] = display_detail['승차'].apply(lambda x: f"{x:,.0f}")
        display_detail['하차'] = display_detail['하차'].apply(lambda x: f"{x:,.0f}")
        display_detail['총 이용'] = display_detail['총 이용'].apply(lambda x: f"{x:,.0f}")
        st.dataframe(display_detail[['역명', '호선', '총 이용']], height=600)

# Tab 4: 승하차 불균형
with tab4:
    st.subheader("🔄 승하차 불균형 분석")
    st.markdown("출근지와 주거지의 특성을 파악할 수 있습니다.")
    
    # 승하차 비율 계산
    imbalance_stats = []
    for idx, row in filtered_df.iterrows():
        total_board = sum(row[f'{time}_승차'] for time in time_slots)
        total_alight = sum(row[f'{time}_하차'] for time in time_slots)
        total = total_board + total_alight
        
        if total > 0:
            board_ratio = (total_board / total) * 100
            imbalance = abs(total_board - total_alight)
            
            imbalance_stats.append({
                '호선': row['호선명'],
                '역명': row['지하철역'],
                '승차': total_board,
                '하차': total_alight,
                '승차비율': board_ratio,
                '불균형도': imbalance,
                '특성': '주거지역' if board_ratio > 55 else ('업무지역' if board_ratio < 45 else '균형')
            })
    
    imbalance_df = pd.DataFrame(imbalance_stats)
    
    # 특성별 분류
    col1, col2, col3 = st.columns(3)
    
    residence = len(imbalance_df[imbalance_df['특성'] == '주거지역'])
    business = len(imbalance_df[imbalance_df['특성'] == '업무지역'])
    balanced = len(imbalance_df[imbalance_df['특성'] == '균형'])
    
    col1.metric("🏠 주거지역 특성", f"{residence}개역", "승차 > 하차")
    col2.metric("🏢 업무지역 특성", f"{business}개역", "하차 > 승차")
    col3.metric("⚖️ 균형 지역", f"{balanced}개역", "승차 ≈ 하차")
    
    # 산점도
    fig = px.scatter(imbalance_df, x='승차', y='하차',
                    color='특성',
                    hover_data=['역명', '호선'],
                    title='승차 vs 하차 분포',
                    color_discrete_map={'주거지역': '#FF6B6B', '업무지역': '#4ECDC4', '균형': '#95E1D3'},
                    size='불균형도',
                    size_max=20)
    
    # 대각선 추가 (균형선)
    max_val = max(imbalance_df['승차'].max(), imbalance_df['하차'].max())
    fig.add_trace(go.Scatter(x=[0, max_val], y=[0, max_val],
                            mode='lines',
                            name='균형선',
                            line=dict(dash='dash', color='gray')))
    
    fig.update_layout(height=600)
    st.plotly_chart(fig, use_container_width=True)
    
    # 주요 역 표시
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🏠 주거지역 특성 상위 10개역")
        residence_top = imbalance_df[imbalance_df['특성'] == '주거지역'].nlargest(10, '승차비율')
        st.dataframe(residence_top[['역명', '호선', '승차비율']].style.format({'승차비율': '{:.1f}%'}))
    
    with col2:
        st.markdown("#### 🏢 업무지역 특성 상위 10개역")
        business_top = imbalance_df[imbalance_df['특성'] == '업무지역'].nsmallest(10, '승차비율')
        st.dataframe(business_top[['역명', '호선', '승차비율']].style.format({'승차비율': '{:.1f}%'}))

# Tab 5: 히트맵
with tab5:
    st.subheader("🗺️ 시간대별 역 이용 히트맵")
    
    # 승차/하차 선택
    metric_type = st.radio("분석 지표", ['승차', '하차'], horizontal=True)
    
    # 상위 30개 역만 표시
    top_stations = station_stats_df.head(30)['역명'].tolist()
    heatmap_df = filtered_df[filtered_df['지하철역'].isin(top_stations)]
    
    # 히트맵 데이터 구성
    heatmap_data = []
    for _, row in heatmap_df.iterrows():
        station_data = [row['지하철역']]
        for time in time_slots:
            station_data.append(row[f'{time}_{metric_type}'])
        heatmap_data.append(station_data)
    
    heatmap_matrix_df = pd.DataFrame(heatmap_data, columns=['역명'] + time_slots)
    heatmap_matrix_df = heatmap_matrix_df.set_index('역명')
    
    # 히트맵 생성
    fig = go.Figure(data=go.Heatmap(
        z=heatmap_matrix_df.values,
        x=time_slots,
        y=heatmap_matrix_df.index,
        colorscale='YlOrRd' if metric_type == '승차' else 'Blues',
        hoverongaps=False,
        hovertemplate='역: %{y}<br>시간: %{x}<br>인원: %{z:,.0f}명<extra></extra>'
    ))
    
    fig.update_layout(
        title=f'상위 30개역 시간대별 {metric_type} 패턴',
        xaxis_title='시간대',
        yaxis_title='역명',
        height=800
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    st.info("💡 **인사이트**: 색이 진할수록 해당 시간대에 이용이 많은 것을 의미합니다. "
           "출근/퇴근 시간대의 패턴을 한눈에 확인할 수 있습니다.")

# 푸터
st.markdown("---")
st.markdown("**데이터 출처**: 서울 지하철 승하차 데이터 (2025년 8월) | **분석 기간**: 월간 집계")
st.caption("💡 이 대시보드는 시간대별 승하차 패턴을 분석하여 지하철 이용 트렌드와 역별 특성을 파악합니다.")
