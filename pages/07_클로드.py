import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import folium
from folium.plugins import HeatMap, MarkerCluster
from streamlit_folium import st_folium
import re

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

@st.cache_data
def load_coordinates():
    """역 좌표 데이터 로드 - 여러 인코딩 자동 감지"""
    encodings = ['cp949', 'euc-kr', 'utf-8', 'utf-8-sig', 'latin1']
    
    for enc in encodings:
        try:
            coord_df = pd.read_csv('서울시 역사마스터 정보.csv', encoding=enc)
            
            # 컬럼명이 정상적으로 읽혔는지 확인
            if len(coord_df.columns) >= 5:
                # 컬럼명 표준화
                coord_df.columns = ['역사_ID', '역사명', '호선', '위도', '경도']
                
                # 첫 번째 행의 역사명이 한글인지 확인
                if not coord_df.empty and isinstance(coord_df.iloc[0]['역사명'], str):
                    test_name = coord_df.iloc[0]['역사명']
                    # 한글이 포함되어 있으면 성공
                    if any('\uac00' <= c <= '\ud7a3' for c in test_name):
                        # 역사명 정규화
                        coord_df['역사명_원본'] = coord_df['역사명']
                        coord_df['역사명'] = coord_df['역사명'].str.strip()
                        
                        # 위도, 경도가 유효한 행만 유지
                        coord_df = coord_df.dropna(subset=['위도', '경도'])
                        
                        # 중복 제거 (같은 역명이 여러 번 나오면 첫 번째만 사용)
                        coord_df = coord_df.drop_duplicates(subset=['역사명'], keep='first')
                        
                        st.session_state['coord_encoding'] = enc
                        return coord_df
        except Exception as e:
            continue
    
    # 모든 인코딩 실패 시 빈 데이터프레임
    st.session_state['coord_encoding'] = 'failed'
    return pd.DataFrame(columns=['역사_ID', '역사명', '호선', '위도', '경도', '역사명_원본'])

# 환승역 데이터 생성 함수
@st.cache_data
def create_merged_station_data(df, time_slots):
    """같은 역명의 여러 호선을 합산한 데이터 생성"""
    merged_data = []
    
    for station in df['지하철역'].unique():
        station_rows = df[df['지하철역'] == station]
        lines = station_rows['호선명'].tolist()
        
        merged_row = {
            '지하철역': station,
            '호선': ', '.join(lines) if len(lines) > 1 else lines[0],
            '호선수': len(lines),
            '환승역여부': '환승역' if len(lines) > 1 else '일반역'
        }
        
        # 시간대별 데이터 합산
        for time in time_slots:
            merged_row[f'{time}_승차'] = station_rows[f'{time}_승차'].sum()
            merged_row[f'{time}_하차'] = station_rows[f'{time}_하차'].sum()
        
        merged_data.append(merged_row)
    
    return pd.DataFrame(merged_data)

def normalize_station_name(name):
    """역명 정규화"""
    if pd.isna(name):
        return ""
    
    name = str(name).strip()
    # 괄호와 그 안의 내용 제거 (예: "서울역(1,4호선)" -> "서울역")
    name = re.sub(r'\([^)]*\)', '', name)
    name = name.strip()
    
    # "역" 제거
    if name.endswith('역'):
        name = name[:-1]
    
    # 공백 제거
    name = name.replace(' ', '')
    
    return name

@st.cache_data
def merge_with_coordinates(station_df, coord_df, time_slots):
    """역 이용 데이터와 좌표 데이터 병합 - 강력한 매칭"""
    if coord_df.empty:
        return pd.DataFrame()
    
    # 좌표 데이터의 역명 정규화
    coord_df = coord_df.copy()
    coord_df['역사명_정규화'] = coord_df['역사명'].apply(normalize_station_name)
    
    # 빠른 조회를 위한 딕셔너리 생성
    coord_dict_exact = {}
    coord_dict_normalized = {}
    
    for idx, row in coord_df.iterrows():
        station_name = row['역사명']
        station_normalized = row['역사명_정규화']
        
        coord_dict_exact[station_name] = row
        coord_dict_normalized[station_normalized] = row
    
    # 역별 총 이용객 계산 및 매칭
    result_data = []
    matched_count = 0
    not_matched = []
    matching_details = []
    
    for idx, row in station_df.iterrows():
        station_name = row['지하철역']
        station_name_normalized = normalize_station_name(station_name)
        
        coord = None
        match_type = None
        
        # 1차: 정확한 이름 매칭
        if station_name in coord_dict_exact:
            coord = coord_dict_exact[station_name]
            match_type = "정확매칭"
        
        # 2차: 정규화된 이름 매칭
        elif station_name_normalized in coord_dict_normalized:
            coord = coord_dict_normalized[station_name_normalized]
            match_type = "정규화매칭"
        
        # 3차: 부분 문자열 매칭 (긴 이름 우선)
        elif len(station_name_normalized) >= 2:
            for coord_normalized, coord_row in coord_dict_normalized.items():
                if (coord_normalized and station_name_normalized in coord_normalized) or \
                   (coord_normalized and coord_normalized in station_name_normalized):
                    coord = coord_row
                    match_type = "부분매칭"
                    break
        
        if coord is not None:
            matched_count += 1
            
            total_board = sum(row[f'{time}_승차'] for time in time_slots)
            total_alight = sum(row[f'{time}_하차'] for time in time_slots)
            total_users = total_board + total_alight
            
            board_ratio = (total_board / total_users * 100) if total_users > 0 else 50
            
            result_data.append({
                '역명': station_name,
                '호선': row.get('호선', row.get('호선명', '')),
                '위도': coord['위도'],
                '경도': coord['경도'],
                '승차': total_board,
                '하차': total_alight,
                '총이용': total_users,
                '승차비율': board_ratio,
                '특성': '주거지역' if board_ratio > 55 else ('업무지역' if board_ratio < 45 else '균형'),
                '환승역여부': row.get('환승역여부', '일반역')
            })
            
            matching_details.append({
                '역명': station_name,
                '매칭방식': match_type,
                '좌표역명': coord['역사명']
            })
        else:
            not_matched.append(station_name)
    
    result_df = pd.DataFrame(result_data)
    
    # 매칭 통계 저장
    st.session_state.matching_stats = {
        'matched': matched_count,
        'total': len(station_df),
        'not_matched': not_matched,
        'match_rate': (matched_count / len(station_df) * 100) if len(station_df) > 0 else 0,
        'details': matching_details[:20]  # 처음 20개만
    }
    
    return result_df

# 데이터 로드
df, time_slots = load_data()
merged_df = create_merged_station_data(df, time_slots)
coord_df = load_coordinates()

# 사이드바 필터
st.sidebar.header("🔍 필터 옵션")

# 데이터 모드 선택
data_mode = st.sidebar.radio(
    "데이터 표시 방식",
    ["호선별 개별", "역명 통합 (환승역 합산)"],
    help="환승역의 여러 호선을 합쳐서 볼지, 개별로 볼지 선택"
)

# 호선 선택 (호선별 개별 모드일 때만)
if data_mode == "호선별 개별":
    lines = sorted(df['호선명'].unique())
    selected_line = st.sidebar.selectbox("호선 선택", ['전체'] + lines)
    
    if selected_line == '전체':
        filtered_df = df.copy()
    else:
        filtered_df = df[df['호선명'] == selected_line].copy()
    
    # 역 선택
    stations = sorted(filtered_df['지하철역'].unique())
    selected_station = st.sidebar.selectbox("역 선택 (상세 분석용)", ['전체'] + stations)
    
    # 선택된 역이 환승역인지 확인
    if selected_station != '전체':
        station_lines = filtered_df[filtered_df['지하철역'] == selected_station]['호선명'].unique()
        if len(station_lines) > 0:
            selected_station_line = st.sidebar.selectbox(
                "호선 선택 (해당 역)",
                station_lines.tolist()
            )
else:
    # 역명 통합 모드
    filtered_df = merged_df.copy()
    
    # 환승역 필터
    transfer_filter = st.sidebar.selectbox(
        "역 유형",
        ['전체', '환승역만', '일반역만']
    )
    
    if transfer_filter == '환승역만':
        filtered_df = filtered_df[filtered_df['환승역여부'] == '환승역']
    elif transfer_filter == '일반역만':
        filtered_df = filtered_df[filtered_df['환승역여부'] == '일반역']
    
    # 역 선택
    stations = sorted(filtered_df['지하철역'].unique())
    selected_station = st.sidebar.selectbox("역 선택 (상세 분석용)", ['전체'] + stations)

# 메인 대시보드
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📊 전체 현황", 
    "⏰ 시간대별 분석", 
    "🏆 역별 순위", 
    "🔄 승하차 불균형",
    "🔀 환승역 분석",
    "🗺️ 지도 시각화",
    "📈 히트맵"
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
    if data_mode == "역명 통합 (환승역 합산)":
        transfer_count = len(filtered_df[filtered_df['환승역여부'] == '환승역'])
        col4.metric("분석 역 수", f"{len(filtered_df)}개역", f"환승역 {transfer_count}개")
    else:
        col4.metric("분석 역 수", f"{len(filtered_df)}개역")
    
    st.markdown("---")
    
    # 호선별 이용 현황
    if data_mode == "호선별 개별" and selected_line == '전체':
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
    
    elif data_mode == "역명 통합 (환승역 합산)":
        st.subheader("📈 환승역 vs 일반역 비교")
        
        col1, col2 = st.columns(2)
        
        with col1:
            transfer_total = filtered_df[filtered_df['환승역여부'] == '환승역'][[f'{time}_승차' for time in time_slots]].sum().sum() + \
                           filtered_df[filtered_df['환승역여부'] == '환승역'][[f'{time}_하차' for time in time_slots]].sum().sum()
            normal_total = filtered_df[filtered_df['환승역여부'] == '일반역'][[f'{time}_승차' for time in time_slots]].sum().sum() + \
                         filtered_df[filtered_df['환승역여부'] == '일반역'][[f'{time}_하차' for time in time_slots]].sum().sum()
            
            comparison_df = pd.DataFrame({
                '구분': ['환승역', '일반역'],
                '이용객': [transfer_total, normal_total]
            })
            
            fig = px.pie(comparison_df, values='이용객', names='구분',
                        title='환승역 vs 일반역 이용 비율',
                        color_discrete_map={'환승역': '#FF6B6B', '일반역': '#4ECDC4'})
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            transfer_count = len(merged_df[merged_df['환승역여부'] == '환승역'])
            normal_count = len(merged_df[merged_df['환승역여부'] == '일반역'])
            
            count_df = pd.DataFrame({
                '구분': ['환승역', '일반역'],
                '개수': [transfer_count, normal_count]
            })
            
            fig = px.bar(count_df, x='구분', y='개수',
                        title='환승역 vs 일반역 개수',
                        color='구분',
                        color_discrete_map={'환승역': '#FF6B6B', '일반역': '#4ECDC4'})
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

# Tab 2: 시간대별 분석
with tab2:
    st.subheader("⏰ 시간대별 승하차 패턴")
    
    if selected_station != '전체':
        if data_mode == "호선별 개별":
            station_df = filtered_df[
                (filtered_df['지하철역'] == selected_station) & 
                (filtered_df['호선명'] == selected_station_line)
            ].iloc[0]
            
            hourly_data = []
            for time in time_slots:
                hourly_data.append({
                    '시간대': time,
                    '승차': station_df[f'{time}_승차'],
                    '하차': station_df[f'{time}_하차']
                })
            hourly_df = pd.DataFrame(hourly_data)
            
            st.markdown(f"### 📍 {selected_station}역 ({selected_station_line}) 시간대별 패턴")
        else:
            station_df = filtered_df[filtered_df['지하철역'] == selected_station].iloc[0]
            
            hourly_data = []
            for time in time_slots:
                hourly_data.append({
                    '시간대': time,
                    '승차': station_df[f'{time}_승차'],
                    '하차': station_df[f'{time}_하차']
                })
            hourly_df = pd.DataFrame(hourly_data)
            
            if station_df['환승역여부'] == '환승역':
                st.markdown(f"### 📍 {selected_station}역 시간대별 패턴 (환승역: {station_df['호선']})")
            else:
                st.markdown(f"### 📍 {selected_station}역 ({station_df['호선']}) 시간대별 패턴")
        
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
    
    station_stats = []
    for idx, row in filtered_df.iterrows():
        total_board = sum(row[f'{time}_승차'] for time in time_slots)
        total_alight = sum(row[f'{time}_하차'] for time in time_slots)
        
        stat_row = {
            '역명': row['지하철역'],
            '승차': total_board,
            '하차': total_alight,
            '총 이용': total_board + total_alight
        }
        
        if data_mode == "호선별 개별":
            stat_row['호선'] = row['호선명']
        else:
            stat_row['호선'] = row['호선']
            stat_row['환승역여부'] = row['환승역여부']
        
        station_stats.append(stat_row)
    
    station_stats_df = pd.DataFrame(station_stats).sort_values('총 이용', ascending=False)
    
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
                    color_continuous_scale=color_scale,
                    hover_data=['호선'])
        fig.update_layout(height=600, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("#### 📋 상세 데이터")
        display_detail = display_df.copy()
        display_detail['승차'] = display_detail['승차'].apply(lambda x: f"{x:,.0f}")
        display_detail['하차'] = display_detail['하차'].apply(lambda x: f"{x:,.0f}")
        display_detail['총 이용'] = display_detail['총 이용'].apply(lambda x: f"{x:,.0f}")
        
        if data_mode == "역명 통합 (환승역 합산)":
            st.dataframe(display_detail[['역명', '호선', '환승역여부', '총 이용']], height=600)
        else:
            st.dataframe(display_detail[['역명', '호선', '총 이용']], height=600)

# Tab 4: 승하차 불균형
with tab4:
    st.subheader("🔄 승하차 불균형 분석")
    st.markdown("출근지와 주거지의 특성을 파악할 수 있습니다.")
    
    imbalance_stats = []
    for idx, row in filtered_df.iterrows():
        total_board = sum(row[f'{time}_승차'] for time in time_slots)
        total_alight = sum(row[f'{time}_하차'] for time in time_slots)
        total = total_board + total_alight
        
        if total > 0:
            board_ratio = (total_board / total) * 100
            imbalance = abs(total_board - total_alight)
            
            stat_row = {
                '역명': row['지하철역'],
                '승차': total_board,
                '하차': total_alight,
                '승차비율': board_ratio,
                '불균형도': imbalance,
                '특성': '주거지역' if board_ratio > 55 else ('업무지역' if board_ratio < 45 else '균형')
            }
            
            if data_mode == "호선별 개별":
                stat_row['호선'] = row['호선명']
            else:
                stat_row['호선'] = row['호선']
                stat_row['환승역여부'] = row['환승역여부']
            
            imbalance_stats.append(stat_row)
    
    imbalance_df = pd.DataFrame(imbalance_stats)
    
    col1, col2, col3 = st.columns(3)
    
    residence = len(imbalance_df[imbalance_df['특성'] == '주거지역'])
    business = len(imbalance_df[imbalance_df['특성'] == '업무지역'])
    balanced = len(imbalance_df[imbalance_df['특성'] == '균형'])
    
    col1.metric("🏠 주거지역 특성", f"{residence}개역", "승차 > 하차")
    col2.metric("🏢 업무지역 특성", f"{business}개역", "하차 > 승차")
    col3.metric("⚖️ 균형 지역", f"{balanced}개역", "승차 ≈ 하차")
    
    fig = px.scatter(imbalance_df, x='승차', y='하차',
                    color='특성',
                    hover_data=['역명', '호선'],
                    title='승차 vs 하차 분포',
                    color_discrete_map={'주거지역': '#FF6B6B', '업무지역': '#4ECDC4', '균형': '#95E1D3'},
                    size='불균형도',
                    size_max=20)
    
    max_val = max(imbalance_df['승차'].max(), imbalance_df['하차'].max())
    fig.add_trace(go.Scatter(x=[0, max_val], y=[0, max_val],
                            mode='lines',
                            name='균형선',
                            line=dict(dash='dash', color='gray')))
    
    fig.update_layout(height=600)
    st.plotly_chart(fig, use_container_width=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🏠 주거지역 특성 상위 10개역")
        residence_top = imbalance_df[imbalance_df['특성'] == '주거지역'].nlargest(10, '승차비율')
        st.dataframe(residence_top[['역명', '호선', '승차비율']].style.format({'승차비율': '{:.1f}%'}))
    
    with col2:
        st.markdown("#### 🏢 업무지역 특성 상위 10개역")
        business_top = imbalance_df[imbalance_df['특성'] == '업무지역'].nsmallest(10, '승차비율')
        st.dataframe(business_top[['역명', '호선', '승차비율']].style.format({'승차비율': '{:.1f}%'}))

# Tab 5: 환승역 분석
with tab5:
    st.subheader("🔀 환승역 심층 분석")
    
    transfer_stations = merged_df[merged_df['환승역여부'] == '환승역'].copy()
    
    transfer_stats = []
    for idx, row in transfer_stations.iterrows():
        total_board = sum(row[f'{time}_승차'] for time in time_slots)
        total_alight = sum(row[f'{time}_하차'] for time in time_slots)
        transfer_stats.append({
            '역명': row['지하철역'],
            '호선': row['호선'],
            '호선수': row['호선수'],
            '총 이용': total_board + total_alight
        })
    
    transfer_stats_df = pd.DataFrame(transfer_stats).sort_values('총 이용', ascending=False)
    
    col1, col2, col3, col4 = st.columns(4)
    
    total_transfer = len(transfer_stations)
    col1.metric("총 환승역 수", f"{total_transfer}개역")
    
    max_lines = transfer_stations['호선수'].max()
    col2.metric("최대 호선 수", f"{int(max_lines)}개 호선")
    
    transfer_total_users = transfer_stats_df['총 이용'].sum()
    all_total_users = sum(merged_df[f'{time}_승차'].sum() + merged_df[f'{time}_하차'].sum() for time in time_slots)
    transfer_ratio = (transfer_total_users / all_total_users) * 100
    col3.metric("환승역 이용 비중", f"{transfer_ratio:.1f}%")
    
    avg_transfer_users = transfer_total_users / total_transfer
    col4.metric("환승역 평균 이용", f"{avg_transfer_users:,.0f}명")
    
    st.markdown("---")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### 🏆 환승역 이용 순위 Top 20")
        top20_transfer = transfer_stats_df.head(20)
        
        fig = px.bar(top20_transfer, y='역명', x='총 이용',
                    orientation='h',
                    title='환승역 이용객 순위',
                    labels={'총 이용': '총 이용자 수', '역명': ''},
                    color='호선수',
                    color_continuous_scale='Viridis',
                    hover_data=['호선'])
        fig.update_layout(height=600)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("### 📊 호선 수별 분포")
        
        line_count_dist = transfer_stations['호선수'].value_counts().sort_index()
        
        fig = px.bar(x=line_count_dist.index, y=line_count_dist.values,
                    labels={'x': '호선 수', 'y': '역 개수'},
                    title='환승 호선 수 분포',
                    color=line_count_dist.values,
                    color_continuous_scale='Blues')
        fig.update_layout(height=300, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("### 📋 상세 정보")
        display_detail = top20_transfer.copy()
        display_detail['총 이용'] = display_detail['총 이용'].apply(lambda x: f"{x:,.0f}")
        st.dataframe(display_detail[['역명', '호선수', '호선', '총 이용']], height=300)
    
    st.markdown("### 🗺️ 환승 가능 호선 조합")
    
    line_combinations = transfer_stations['호선'].value_counts().head(15)
    
    fig = px.bar(x=line_combinations.values, y=line_combinations.index,
                orientation='h',
                title='주요 환승 호선 조합 (Top 15)',
                labels={'x': '역 개수', 'y': '호선 조합'},
                color=line_combinations.values,
                color_continuous_scale='Plasma')
    fig.update_layout(height=500, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

# Tab 6: 지도 시각화 (새로운 탭)
with tab6:
    st.subheader("🗺️ 서울 지하철 지도 시각화")
    
    # 인코딩 정보 표시
    if 'coord_encoding' in st.session_state:
        if st.session_state['coord_encoding'] == 'failed':
            st.error("⚠️ 역사마스터 파일을 읽을 수 없습니다. 파일 인코딩을 확인해주세요.")
        else:
            st.success(f"✅ 역사마스터 파일 로드 완료 (인코딩: {st.session_state['coord_encoding']})")
    
    # 좌표와 병합
    map_data = merge_with_coordinates(filtered_df, coord_df, time_slots)
    
    # 매칭 통계 표시
    if 'matching_stats' in st.session_state:
        stats = st.session_state.matching_stats
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("📍 매칭 성공", f"{stats['matched']}개", f"{stats['match_rate']:.1f}%")
        col2.metric("📊 전체 역", f"{stats['total']}개")
        col3.metric("❌ 미매칭", f"{len(stats['not_matched'])}개")
        
        if stats['match_rate'] >= 90:
            col4.success("🎉 우수!")
        elif stats['match_rate'] >= 70:
            col4.warning("⚠️ 보통")
        else:
            col4.error("❌ 낮음")
        
        # 매칭 상세 정보
        if stats['not_matched']:
            with st.expander(f"⚠️ 매칭되지 않은 역 목록 ({len(stats['not_matched'])}개)"):
                not_matched_text = ", ".join(stats['not_matched'][:30])
                if len(stats['not_matched']) > 30:
                    not_matched_text += f"... 외 {len(stats['not_matched']) - 30}개"
                st.write(not_matched_text)
                st.caption("💡 이 역들은 지도에 표시되지 않습니다. 역사마스터 파일에 해당 역명이 없거나 표기가 다를 수 있습니다.")
        
        # 매칭 방식 상세 (처음 20개)
        if 'details' in stats and stats['details']:
            with st.expander("🔍 매칭 방식 상세 (샘플 20개)"):
                details_df = pd.DataFrame(stats['details'])
                st.dataframe(details_df, use_container_width=True)
    
    if len(map_data) == 0:
        st.warning("⚠️ 좌표 데이터와 매칭되는 역이 없습니다. 다음을 확인해주세요:\n"
                  "1. 서울시 역사마스터 정보.csv 파일이 올바르게 업로드되었는지\n"
                  "2. 파일의 인코딩이 올바른지 (cp949, euc-kr, utf-8 자동 시도)\n"
                  "3. 역명 표기가 일치하는지")
    else:
        st.success(f"✅ 총 {len(map_data)}개 역의 위치 정보를 찾았습니다!")
        
        # 지도 옵션
        map_type = st.radio(
            "지도 유형",
            ["🔴 이용객 규모", "🎨 승하차 특성", "🔥 히트맵"],
            horizontal=True
        )
        
        # 서울 중심 좌표
        seoul_center = [37.5665, 126.9780]
        
        if map_type == "🔴 이용객 규모":
            st.markdown("### 역별 이용객 규모 (원의 크기 = 이용객 수)")
            
            # Folium 지도 생성
            m = folium.Map(
                location=seoul_center,
                zoom_start=11,
                tiles='OpenStreetMap'
            )
            
            # 이용객 수에 따라 원 크기 조절
            max_users = map_data['총이용'].max()
            
            for idx, row in map_data.iterrows():
                # 원 반지름 계산 (최소 50, 최대 500)
                radius = 50 + (row['총이용'] / max_users) * 450
                
                # 환승역 여부에 따라 색상 변경
                color = '#FF6B6B' if row['환승역여부'] == '환승역' else '#4ECDC4'
                
                popup_text = f"""
                <div style="font-family: Arial; min-width: 200px;">
                    <h4 style="margin: 0;">{row['역명']}</h4>
                    <p style="margin: 5px 0;"><b>호선:</b> {row['호선']}</p>
                    <p style="margin: 5px 0;"><b>총 이용:</b> {row['총이용']:,.0f}명</p>
                    <p style="margin: 5px 0;"><b>승차:</b> {row['승차']:,.0f}명</p>
                    <p style="margin: 5px 0;"><b>하차:</b> {row['하차']:,.0f}명</p>
                    <p style="margin: 5px 0;"><b>특성:</b> {row['특성']}</p>
                </div>
                """
                
                folium.CircleMarker(
                    location=[row['위도'], row['경도']],
                    radius=radius / 30,  # 화면에 맞게 스케일 조정
                    popup=folium.Popup(popup_text, max_width=300),
                    color=color,
                    fill=True,
                    fillColor=color,
                    fillOpacity=0.6,
                    weight=2
                ).add_to(m)
            
            # 범례 추가
            legend_html = '''
            <div style="position: fixed; 
                        bottom: 50px; right: 50px; width: 180px; height: 90px; 
                        background-color: white; border:2px solid grey; z-index:9999; 
                        font-size:14px; padding: 10px">
                <p style="margin: 5px;"><span style="color: #FF6B6B;">●</span> 환승역</p>
                <p style="margin: 5px;"><span style="color: #4ECDC4;">●</span> 일반역</p>
                <p style="margin: 5px; font-size: 12px;">원의 크기 = 이용객 수</p>
            </div>
            '''
            m.get_root().html.add_child(folium.Element(legend_html))
            
            st_folium(m, width=1400, height=700)
            
        elif map_type == "🎨 승하차 특성":
            st.markdown("### 역별 승하차 특성 (주거지역 vs 업무지역)")
            
            m = folium.Map(
                location=seoul_center,
                zoom_start=11,
                tiles='OpenStreetMap'
            )
            
            max_users = map_data['총이용'].max()
            
            for idx, row in map_data.iterrows():
                radius = 50 + (row['총이용'] / max_users) * 450
                
                # 특성에 따라 색상 변경
                if row['특성'] == '주거지역':
                    color = '#FF6B6B'
                elif row['특성'] == '업무지역':
                    color = '#4ECDC4'
                else:
                    color = '#95E1D3'
                
                popup_text = f"""
                <div style="font-family: Arial; min-width: 200px;">
                    <h4 style="margin: 0;">{row['역명']}</h4>
                    <p style="margin: 5px 0;"><b>호선:</b> {row['호선']}</p>
                    <p style="margin: 5px 0;"><b>특성:</b> {row['특성']}</p>
                    <p style="margin: 5px 0;"><b>승차비율:</b> {row['승차비율']:.1f}%</p>
                    <p style="margin: 5px 0;"><b>총 이용:</b> {row['총이용']:,.0f}명</p>
                </div>
                """
                
                folium.CircleMarker(
                    location=[row['위도'], row['경도']],
                    radius=radius / 30,
                    popup=folium.Popup(popup_text, max_width=300),
                    color=color,
                    fill=True,
                    fillColor=color,
                    fillOpacity=0.7,
                    weight=2
                ).add_to(m)
            
            legend_html = '''
            <div style="position: fixed; 
                        bottom: 50px; right: 50px; width: 180px; height: 110px; 
                        background-color: white; border:2px solid grey; z-index:9999; 
                        font-size:14px; padding: 10px">
                <p style="margin: 5px;"><span style="color: #FF6B6B;">●</span> 주거지역</p>
                <p style="margin: 5px;"><span style="color: #4ECDC4;">●</span> 업무지역</p>
                <p style="margin: 5px;"><span style="color: #95E1D3;">●</span> 균형지역</p>
                <p style="margin: 5px; font-size: 12px;">원의 크기 = 이용객 수</p>
            </div>
            '''
            m.get_root().html.add_child(folium.Element(legend_html))
            
            st_folium(m, width=1400, height=700)
            
        else:  # 히트맵
            st.markdown("### 지하철 이용 밀집도 히트맵")
            
            m = folium.Map(
                location=seoul_center,
                zoom_start=11,
                tiles='OpenStreetMap'
            )
            
            # 히트맵 데이터 준비
            heat_data = [[row['위도'], row['경도'], row['총이용']] for idx, row in map_data.iterrows()]
            
            # 히트맵 추가
            HeatMap(
                heat_data,
                min_opacity=0.3,
                max_zoom=18,
                radius=25,
                blur=35,
                gradient={0.4: 'blue', 0.6: 'lime', 0.8: 'yellow', 1.0: 'red'}
            ).add_to(m)
            
            st_folium(m, width=1400, height=700)
        
        # 통계
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        
        top_station = map_data.nlargest(1, '총이용').iloc[0]
        col1.metric("🥇 최다 이용 역", top_station['역명'], f"{top_station['총이용']:,.0f}명")
        
        residence_count = len(map_data[map_data['특성'] == '주거지역'])
        col2.metric("🏠 주거지역 특성", f"{residence_count}개역")
        
        business_count = len(map_data[map_data['특성'] == '업무지역'])
        col3.metric("🏢 업무지역 특성", f"{business_count}개역")

# Tab 7: 히트맵
with tab7:
    st.subheader("📈 시간대별 역 이용 히트맵")
    
    metric_type = st.radio("분석 지표", ['승차', '하차'], horizontal=True)
    
    heatmap_stats = []
    for idx, row in filtered_df.iterrows():
        total = sum(row[f'{time}_{metric_type}'] for time in time_slots)
        heatmap_stats.append({
            'index': idx,
            '역명': row['지하철역'],
            '총량': total
        })
    
    heatmap_stats_df = pd.DataFrame(heatmap_stats).sort_values('총량', ascending=False)
    
    top_30_indices = heatmap_stats_df.head(30)['index'].tolist()
    heatmap_df = filtered_df.loc[top_30_indices]
    
    heatmap_data = []
    station_labels = []
    
    for idx, row in heatmap_df.iterrows():
        if data_mode == "호선별 개별":
            station_label = f"{row['지하철역']} ({row['호선명']})"
        else:
            if row['환승역여부'] == '환승역':
                station_label = f"{row['지하철역']} ⚡"
            else:
                station_label = row['지하철역']
        
        station_labels.append(station_label)
        station_data = [row[f'{time}_{metric_type}'] for time in time_slots]
        heatmap_data.append(station_data)
    
    fig = go.Figure(data=go.Heatmap(
        z=heatmap_data,
        x=time_slots,
        y=station_labels,
        colorscale='YlOrRd' if metric_type == '승차' else 'Blues',
        hoverongaps=False,
        hovertemplate='역: %{y}<br>시간: %{x}<br>인원: %{z:,.0f}명<extra></extra>'
    ))
    
    fig.update_layout(
        title=f'상위 30개역 시간대별 {metric_type} 패턴 (⚡ = 환승역)',
        xaxis_title='시간대',
        yaxis_title='역명',
        height=900
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    st.info("💡 **인사이트**: 색이 진할수록 해당 시간대에 이용이 많은 것을 의미합니다. "
           "출근/퇴근 시간대의 패턴을 한눈에 확인할 수 있습니다. ⚡ 표시는 환승역을 나타냅니다.")

# 푸터
st.markdown("---")
st.markdown("**데이터 출처**: 서울 지하철 승하차 데이터 (2025년 8월) | **분석 기간**: 월간 집계")
st.caption("💡 이 대시보드는 시간대별 승하차 패턴을 분석하여 지하철 이용 트렌드와 역별 특성을 파악합니다. 지도 시각화로 공간적 패턴도 확인 가능합니다.")
