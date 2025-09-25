import io
import re
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="지하철 레이싱 차트", layout="wide")

# =========================
# 유틸: CSV 읽기 (인코딩 자동 시도)
# =========================
def _read_csv_any_encoding(src, dtype_spec):
    def _read(reader):
        # cp949 -> utf-8-sig 순서로 시도
        try:
            return pd.read_csv(reader, encoding="cp949", dtype=dtype_spec)
        except UnicodeDecodeError:
            if hasattr(reader, "seek"):
                reader.seek(0)
            return pd.read_csv(reader, encoding="utf-8-sig", dtype=dtype_spec)

    # 파일 경로나 파일객체/바이트 모두 지원
    if isinstance(src, (str, bytes, bytearray)):
        return _read(src)
    elif hasattr(src, "read"):  # file-like
        return _read(src)
    else:  # 바이트(메모리)라면 BytesIO로 감싸기
        return _read(io.BytesIO(src))

# =========================
# 전처리 핵심: 견고한 컬럼 파싱
# =========================
def _parse_hour(raw_col: str) -> str | None:
    """
    헤더에서 '시간'을 추출해 2자리로 반환. (예: '04', '18')
    허용 예: '04:00~05:00 승차', '04시-05시 하차', '04시 승차', '04 ~ 05 승차'
    """
    s = str(raw_col)
    # 우선 ':' 또는 '시' 앞의 숫자 1~2자리
    m = re.search(r'(\d{1,2})(?=[:시])', s)
    if not m:
        # 백업: 시작 부분의 1~2자리 숫자
        m = re.search(r'(^|\s)(\d{1,2})(?=\D)', s)
        if m:
            hh = int(m.group(2))
        else:
            return None
    else:
        hh = int(m.group(1))
    if 0 <= hh <= 23:
        return f"{hh:02d}"
    return None

def _rename_columns_safely(df: pd.DataFrame) -> pd.DataFrame:
    base = ['사용월', '호선명', '역ID', '지하철역']
    new_cols = []
    keep_mask = []

    for c in df.columns:
        c_str = str(c).strip()
        if c_str in base:
            new_cols.append(c_str)
            keep_mask.append(True)
            continue

        # 승차/하차 컬럼만 추림
        if ('승차' in c_str) or ('하차' in c_str):
            hh = _parse_hour(c_str)
            if hh is not None:
                gu = '승차' if '승차' in c_str else '하차'
                new_cols.append(f"{hh}_{gu}")
                keep_mask.append(True)
                continue

        # 그 외는 제거
        new_cols.append(None)
        keep_mask.append(False)

    df = df.loc[:, keep_mask].copy()
    df.columns = [c for c in new_cols if c is not None]
    return df

# =========================
# 데이터 로딩 + 전처리 (캐시)
# =========================
@st.cache_data(show_spinner=False)
def load_and_prep_data(file_bytes: bytes | None, source_hint: str | None):
    """
    CSV를 로드 후:
      - 불필요 열 제거(패턴 기반)
      - 시간/승하차 컬럼 표준화(04_승차 등)
      - 숫자 변환
      - long 포맷 변환
    반환: df_long (컬럼: 지하철역, 호선명, 사용월?, 시간대, 구분, 인원수)
    """
    dtype_spec = {'호선명': 'string', '지하철역': 'string', '역ID': 'string', '사용월': 'string'}

    df = None
    # 1) 업로드 파일 우선
    if file_bytes is not None:
        df = _read_csv_any_encoding(io.BytesIO(file_bytes), dtype_spec)
    else:
        # 2) 폴백 경로 시도
        for path in ["/mnt/data/지하철데이터.csv", "지하철데이터.csv"]:
            try:
                df = _read_csv_any_encoding(path, dtype_spec)
                break
            except FileNotFoundError:
                continue

    if df is None:
        st.error("😥 CSV를 업로드하거나 `/mnt/data` 또는 앱 폴더에 `지하철데이터.csv`를 두세요.")
        return None

    # 필수 컬럼 존재 확인(지하철역은 최소 필요)
    if '지하철역' not in df.columns:
        st.error("데이터에 '지하철역' 컬럼이 없습니다. 헤더를 확인하세요.")
        return None

    # 결측 제거(핵심 식별)
    key_cols = [c for c in ['호선명', '지하철역'] if c in df.columns]
    if key_cols:
        df.dropna(subset=key_cols, inplace=True)

    # 안전한 컬럼 표준화
    df = _rename_columns_safely(df)

    # value 컬럼(승/하차) 숫자 변환
    value_cols = [c for c in df.columns if c.endswith('_승차') or c.endswith('_하차')]
    if not value_cols:
        st.error("시간대 승/하차 컬럼을 찾지 못했습니다. 헤더 형식을 확인하세요.")
        return None

    for col in value_cols:
        df[col] = (
            pd.to_numeric(
                df[col].astype(str).str.replace(',', '', regex=False),
                errors='coerce'
            ).fillna(0).astype('int64')
        )

    # id_vars는 존재하는 컬럼만 사용
    id_candidates = ['사용월', '호선명', '역ID', '지하철역']
    id_vars = [c for c in id_candidates if c in df.columns]

    df_long = df.melt(id_vars=id_vars, var_name='시간구분', value_name='인원수')
    df_long['시간대'] = df_long['시간구분'].str.split('_').str[0]
    df_long['구분'] = df_long['시간구분'].str.split('_').str[1]
    df_long.drop(columns=['시간구분'], inplace=True)

    # 타입 정리
    df_long['시간대'] = df_long['시간대'].astype('string')
    df_long['구분'] = df_long['구분'].astype('string')
    if '호선명' in df_long.columns:
        df_long['호선명'] = df_long['호선명'].astype('string')
    df_long['지하철역'] = df_long['지하철역'].astype('string')

    return df_long

# =========================
# 누적/그룹 계산 (캐시)
# =========================
@st.cache_data(show_spinner=False)
def get_cumulative_data(df_long: pd.DataFrame, combine_stations: bool, analysis_type: str):
    """
    analysis_type: '종합' | '승차' | '하차'
    combine_stations: True → 환승역 합산(호선 무시)
    """
    if analysis_type != '종합':
        df_filtered = df_long[df_long['구분'] == analysis_type]
    else:
        df_filtered = df_long

    # 레이블 생성용: 호선이 없으면 자동으로 역명만 사용
    has_line = '호선명' in df_filtered.columns

    if combine_stations or not has_line:
        grouped = df_filtered.groupby(['시간대', '지하철역'], as_index=False)['인원수'].sum()
        grouped['역명(호선)'] = grouped['지하철역']
    else:
        grouped = df_filtered.groupby(['시간대', '호선명', '지하철역'], as_index=False)['인원수'].sum()
        grouped['역명(호선)'] = grouped['지하철역'] + "(" + grouped['호선명'] + ")"

    # 시간대 정렬: 04~23 → 00~03 (데이터에 존재하는 값만)
    seen = pd.unique(grouped['시간대']).tolist()
    desired = [f"{h:02d}" for h in range(4, 24)] + [f"{h:02d}" for h in range(0, 4)]
    order = [t for t in desired if t in seen]
    if not order:  # 전부 미일치하면 등장순 유지
        order = seen

    grouped['시간대'] = pd.Categorical(grouped['시간대'], categories=order, ordered=True)
    grouped.sort_values(['역명(호선)', '시간대'], inplace=True)

    grouped['누적인원수'] = grouped.groupby('역명(호선)', sort=False)['인원수'].cumsum()
    return grouped

# =========================
# UI
# =========================
st.header("🏁 시간대별 누적 유동인구 레이싱 차트")
st.markdown("시간의 흐름에 따라 각 역의 **누적** 승·하차 인원 순위가 어떻게 변하는지 애니메이션으로 확인해요.")

uploaded = st.file_uploader("CSV 업로드 (지하철데이터.csv)", type=["csv"])
file_bytes = uploaded.getvalue() if uploaded is not None else None
source_hint = uploaded.name if uploaded is not None else None

df_long = load_and_prep_data(file_bytes, source_hint)

if df_long is None:
    st.stop()

# 옵션
combine_stations = st.checkbox("🔁 동일 역명 데이터 합산", help="체크 시, 환승역(여러 호선) 데이터를 역명 기준으로 합산합니다.")
analysis_type = st.radio("📈 분석 기준 선택", ('종합', '승차', '하차'), horizontal=True, index=0)
top_n = st.slider("📊 표시할 순위 (TOP N)", 5, 30, 10)
animation_speed = st.slider(
    "💨 애니메이션 속도 (ms/프레임)", min_value=100, max_value=1000, value=300, step=50,
    help="값이 낮을수록 더 빠르게 진행됩니다."
)

# 계산
cumulative_data = get_cumulative_data(df_long, combine_stations, analysis_type)

# TOP N 추리기: rank 방식(빠르고 경고 없음)
animation_data = cumulative_data.copy()
animation_data['rank'] = animation_data.groupby('시간대')['누적인원수'].rank(method='first', ascending=False)
animation_data = animation_data[animation_data['rank'] <= top_n].drop(columns='rank')

st.markdown("---")
st.info("▶️ 아래 그래프의 재생 버튼을 눌러 시간대별 **누적** 순위 변화를 확인하세요!")

# 차트
fig = px.bar(
    animation_data,
    x="누적인원수",
    y="역명(호선)",
    orientation="h",
    color="역명(호선)",
    animation_frame="시간대",
    animation_group="역명(호선)",
    text="누적인원수",
    title=f"시간대별 누적 {analysis_type} 인원 TOP {top_n} 레이싱 차트"
)

# 축/레이아웃
fig.update_layout(
    xaxis_title="누적 인원수",
    yaxis_title="지하철역",
    showlegend=False,
    height=640,
)
fig.update_traces(texttemplate='%{x:,.0f}', textposition='outside')

# x축 최대치 여유
max_value = animation_data['누적인원수'].max() if not animation_data.empty else 0
fig.update_xaxes(range=[0, max_value * 1.2 if max_value > 0 else 1])

# 애니메이션 속도 안전 적용
try:
    if getattr(fig.layout, "updatemenus", None) and len(fig.layout.updatemenus) > 0:
        btn_args = fig.layout.updatemenus[0].buttons[0].args[1]
        if "frame" in btn_args:
            btn_args["frame"]["duration"] = int(animation_speed)
        if "transition" in btn_args:
            btn_args["transition"]["duration"] = int(animation_speed * 0.3)

    if getattr(fig.layout, "sliders", None) and len(fig.layout.sliders) > 0:
        fig.layout.sliders[0]["transition"]["duration"] = int(animation_speed * 0.3)
except Exception:
    pass  # 일부 Plotly 버전에서 구조가 다를 수 있어 조용히 무시

st.plotly_chart(fig, use_container_width=True)
