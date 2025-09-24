import streamlit as st
import pandas as pd
import plotly.express as px
from PIL import Image

# Streamlit 페이지 설정
st.set_page_config(
    page_title="🚇 서울 지하철 데이터 분석 대시보드",
    page_icon="🚇",
    layout="wide",
)

# 데이터 로딩 및 전처리 함수 (Streamlit 캐싱으로 성능 최적화)
@st.cache_data
def load_data():
    """
    지하철 데이터를 불러오고 기본 전처리를 수행하는 함수.
    결과는 캐시되어 페이지 이동 시에도 데이터를 다시 불러오지 않습니다.
    """
    # 데이터 불러오기
    try:
        df = pd.read_csv('지하철데이터.csv', encoding='utf8')
    except FileNotFoundError:
        st.error("😥 '지하철데이터.csv' 파일을 찾을 수 없습니다. 프로젝트 루트 디렉토리에 파일을 업로드해주세요.")
        return None, None, None

    # 불필요한 마지막 '등록일자' 열 제거
    df = df.iloc[:, :-1]

    # 컬럼 이름 재정의
    col_names = ['사용월', '호선명', '역ID', '지하철역']
    for i in range(4, len(df.columns), 2):
        time_str = df.columns[i].split('~')[0][:2]
        col_names.append(f'{time_str}_승차')
        col_names.append(f'{time_str}_하차')
    df.columns = col_names

    # 승하차 인원 데이터에서 쉼표(,) 제거 및 숫자형으로 변환
    value_cols = [c for c in df.columns if '_승차' in c or '_하차' in c]
    for col in value_cols:
        if df[col].dtype == 'object':
            df[col] = df[col].str.replace(',', '').astype(int)
        else:
            df[col] = df[col].astype(int)

    # Wide to Long 포맷으로 데이터 구조 변경
    id_vars = ['사용월', '호선명', '역ID', '지하철역']
    df_long = df.melt(id_vars=id_vars, var_name='시간구분', value_name='인원수')
    
    df_long['시간대'] = df_long['시간구분'].str.split('_').str[0]
    df_long['구분'] = df_long['시간구분'].str.split('_').str[1]
    df_long = df_long.drop(columns=['시간구분'])
    
    # 유사도 분석을 위한 패턴 데이터 생성
    ride_cols = [c for c in df.columns if '_승차' in c]
    alight_cols = [c for c in df.columns if '_하차' in c]
    
    df_pattern = df.set_index(['호선명', '지하철역'])[ride_cols + alight_cols]
    df_pattern_normalized = df_pattern.div(df_pattern.sum(axis=1), axis=0).fillna(0)
    
    return df_long, df, df_pattern_normalized

# 데이터 로드
df_long, df_wide, df_pattern_normalized = load_data()


# 메인 페이지 UI
if df_long is not None:
    st.title("🚇 서울 지하철 데이터 분석 대시보드")
    st.markdown("---")
    st.markdown("""
    안녕하세요! 이 대시보드는 서울 지하철의 시간대별 승하차 데이터를 분석하여 다양한 인사이트를 제공합니다.
    
    👈 **왼쪽 사이드바에서 원하는 분석 페이지를 선택하세요.**
    
    ### 📊 각 페이지 소개
    
    1.  **시간대별 혼잡 분석**: 출퇴근 시간 등 특정 시간대를 지정하여 가장 붐비는 역을 승차/하차별로 확인할 수 있습니다.
    2.  **유동인구 분석**: 전체 또는 특정 호선에서 유동인구(총 승하차 인원)가 가장 많은 역의 순위를 보여줍니다.
    3.  **패턴 유사역 분석**: 특정 역을 선택하면, 그 역과 시간대별 승하차 패턴이 가장 유사한 역 3곳을 찾아 비교해줍니다.
    
    데이터를 기반으로 서울의 심장, 지하철의 움직임을 함께 탐험해봐요!
    """)
    
    st.markdown("---")

    st.subheader("💡 더 재미있는 분석 주제 제안!")
    st.markdown("""
    - **요일별 분석**: 평일과 주말의 이용 패턴은 어떻게 다를까요?
    - **환승역 분석**: 주요 환승역의 독특한 승하차 패턴을 분석해볼 수 있습니다.
    - **심야 시간대 분석**: 밤 10시 이후, 사람들이 가장 많이 이용하는 역은 어디일까요?
    - **'유령역' 찾기**: 승하차 인원이 극도로 적은 역들을 찾아보고 그 이유를 탐색해보기
    """)
    
    st.info("데이터는 `지하철데이터.csv` 파일을 기반으로 하며, 모든 분석은 해당 파일의 데이터를 따릅니다.", icon="ℹ️")

    # 샘플 데이터 보여주기
    st.subheader("🔍 원본 데이터 샘플")
    st.dataframe(df_wide.head())

    # 데이터 다운로드 버튼 추가
    # 데이터프레임을 CSV로 변환하는 함수 (캐싱 사용)
    @st.cache_data
    def convert_df_to_csv(df):
        return df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')

    csv_data = convert_df_to_csv(df_wide)

    st.download_button(
        label="📊 전처리된 데이터 다운로드 (CSV)",
        data=csv_data,
        file_name='seoul_metro_processed.csv',
        mime='text/csv',
        help='열 이름 정리, 숫자 형식 변환 등 전처리가 완료된 데이터를 다운로드합니다.'
    )

