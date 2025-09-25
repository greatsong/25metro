import streamlit as st
import pandas as pd

# 데이터 로딩 함수 (다른 페이지와 캐시 공유)
@st.cache_data
def load_data():
    """
    데이터를 불러오고 기본적인 전처리를 수행합니다.
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
    return df

# --- 메인 페이지 UI ---
st.set_page_config(
    page_title="서울 지하철 데이터 분석",
    page_icon="🚇",
    layout="wide",
)

st.title("🚇 서울 지하철 데이터 분석 대시보드")
st.markdown("이 대시보드는 서울 지하철의 시간대별 이용 현황 데이터를 시각적으로 분석하고 탐색하기 위해 만들어졌습니다.")
st.markdown("왼쪽 사이드바 메뉴를 통해 다양한 분석 페이지로 이동할 수 있습니다.")
st.markdown("---")


# --- 페이지별 사용 설명서 ---
st.header("📊 페이지별 사용 설명서")

st.info("""
**💡 공통 기능: 동일 역명 데이터 합산**\n
대부분의 페이지에는 **'동일 역명 데이터 합산'** 체크박스가 있습니다. 
이 옵션을 선택하면 '강남(2호선)', '강남(신분당선)'처럼 나뉘어 있는 환승역 데이터를 하나의 **'강남 (통합)'** 데이터로 합산하여 분석합니다.
""")

col1, col2, col3 = st.columns(3)
with col1:
    with st.container(border=True):
        st.subheader("1. 시간대별 혼잡 분석")
        st.markdown("- **무엇을 하나요?**: 특정 시간대를 선택하여 가장 붐비는 역의 순위를 확인합니다.")
        st.markdown("- **사용 방법**: 슬라이더를 조절해 원하는 시간과 순위(TOP N)를 선택하세요. 승차/하차 인원 그래프가 각각 표시됩니다.")

    with st.container(border=True):
        st.subheader("2. 유동인구 분석")
        st.markdown("- **무엇을 하나요?**: 하루 총 승하차 인원이 가장 많은 역의 순위를 확인합니다.")
        st.markdown("- **사용 방법**: 전체 또는 특정 호선을 선택하고, 슬라이더로 보고 싶은 순위(TOP N)를 조절할 수 있습니다.")

with col2:
    with st.container(border=True):
        st.subheader("3. 패턴 유사역 분석")
        st.markdown("- **무엇을 하나요?**: 특정 역과 시간대별 이용 패턴(하루의 리듬)이 가장 비슷한 역을 찾습니다.")
        st.markdown("- **사용 방법**: 기준 역, 분석 종류(종합/승차/하차), 비교할 역의 개수(TOP N)를 선택하세요. 인원 비율 패턴을 그래프로 비교하고 유사도 순위를 확인할 수 있습니다.")

    with st.container(border=True):
        st.subheader("4. 시간대별 전체순위 분석")
        st.markdown("- **무엇을 하나요?**: 각 시간대의 '챔피언' (가장 이용객이 많은 역)이 어떻게 변하는지 확인합니다.")
        st.markdown("- **사용 방법**: 막대 또는 꺾은선 그래프를 선택하여 시간의 흐름에 따른 1위 역의 변화를 탐색할 수 있습니다.")

with col3:
    with st.container(border=True):
        st.subheader("5. 두 역 비교 분석")
        st.markdown("- **무엇을 하나요?**: 비교하고 싶은 두 역을 직접 선택하여 시간대별 승하차 인원 추이를 나란히 비교합니다.")
        st.markdown("- **사용 방법**: 두 개의 선택 상자에서 각각 원하는 역을 고르면, 승차 및 하차 데이터 비교 그래프가 즉시 나타납니다.")


# --- 데이터 다운로드 기능 ---
st.markdown("---")
st.header("💾 원본 데이터 확인 및 다운로드")
df = load_data()
if df is not None:
    st.dataframe(df.head(10))
    
    # 다운로드를 위한 CSV 변환 함수
    @st.cache_data
    def convert_df_to_csv(df):
        return df.to_csv(index=False).encode('utf-8-sig')

    csv_data = convert_df_to_csv(df)
    
    st.download_button(
       label="📊 전처리된 데이터 다운로드 (CSV)",
       data=csv_data,
       file_name='seoul_metro_processed.csv',
       mime='text/csv',
    )

