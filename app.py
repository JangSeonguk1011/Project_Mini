
import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import plotly.graph_objects as go
import plotly.express as px
import html
from datetime import datetime, timedelta
import sys
import os

# 1. 외부 지도 모듈 경로 설정
map_module_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'Data_crowling_mini_project', 'map'))
if map_module_path not in sys.path:
    sys.path.append(map_module_path)

# 2. 지도 모듈 임포트
try:
    from map_generator_geo import NewsMapGeneratorGeo
    MAP_MODULE_AVAILABLE = True
except ImportError:
    MAP_MODULE_AVAILABLE = False

# 3. 데이터 로드 및 시각화 유틸리티
@st.cache_data(ttl=600)
def load_official_map():
    """기존 지도 모듈을 사용하여 원본 news_map_geo.html 업데이트 및 로드"""
    if not MAP_MODULE_AVAILABLE: return None
    official_path = os.path.join(map_module_path, 'news_map_geo.html')
    
    # 원본 모듈을 그대로 실행하여 파일 업데이트 (통합 DB는 db_loader.py에서 처리됨)
    generator = NewsMapGeneratorGeo()
    generator.generate(official_path)
    
    if os.path.exists(official_path):
        with open(official_path, 'r', encoding='utf-8') as f:
            return f.read()
    return None

try:
    import FinanceDataReader as fdr
except ImportError:
    fdr = None

def get_combined_df(query, params=None):
    """news.db와 news_scraped.db 통합 로드"""
    df_list = []
    for db_file in ['news.db', 'news_scraped.db']:
        try:
            full_path = os.path.join('data', db_file)
            if os.path.exists(full_path):
                conn = sqlite3.connect(full_path)
                df = pd.read_sql(query, conn, params=params)
                conn.close()
                if not df.empty: df_list.append(df)
        except: continue
    if not df_list: return pd.DataFrame()
    combined_df = pd.concat(df_list, ignore_index=True)
    if 'url' in combined_df.columns:
        combined_df = combined_df.drop_duplicates(subset='url')
    return combined_df

# ==========================================
# UI 기본 설정 및 스타일
# ==========================================
st.set_page_config(page_title="지능형 지역 경제 모니터링 및 자산 영향 분석 대시보드", page_icon="📈", layout="wide")
st.markdown("""
<style>
    .main-title { background: linear-gradient(90deg, #1f77b4, #2ecc71); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 3rem; font-weight: 800; margin-bottom: 1rem; }
    .sub-title { color: #666; font-size: 1.2rem; margin-bottom: 2rem; border-bottom: 2px solid #f0f2f6; padding-bottom: 10px; }
    .metric-card { background-color: #ffffff; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border: 1px solid #f0f2f6; text-align: center; }
    .metric-label { font-size: 14px; color: #666; margin-bottom: 5px; }
    .metric-value { font-size: 24px; font-weight: bold; color: #1f77b4; }
    .badge-pos { background-color: #d4edda; color: #155724; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: bold; }
    .badge-neg { background-color: #f8d7da; color: #721c24; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">지능형 지역 경제 모니터링 및 자산 영향 분석 대시보드</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">실시간 뉴스 감성 분석과 자산 영향 분석 통합 대시보드</div>', unsafe_allow_html=True)

# ==========================================
# 데이터 분석 함수
# ==========================================
def get_metrics_data(start_date, end_date, region):
    query = "SELECT sentiment_score, url, region FROM news WHERE date(published_time) BETWEEN ? AND ?"
    df = get_combined_df(query, params=(start_date.isoformat(), end_date.isoformat()))
    if region != "전국" and not df.empty:
        df = df[df['region'].str.contains(region, na=False)]
    avg_s = df['sentiment_score'].mean() if not df.empty and df['sentiment_score'].notnull().any() else 0.5
    cnt = len(df)
    k_change, q_change = 0.0, 0.0
    if fdr is not None:
        try:
            k = fdr.DataReader('KS11', start_date, end_date)['Close']
            q = fdr.DataReader('KQ11', start_date, end_date)['Close']
            k_change = ((k.iloc[-1] / k.iloc[0]) - 1) * 100
            q_change = ((q.iloc[-1] / q.iloc[0]) - 1) * 100
        except: pass
    return {'sentiment_avg': avg_s, 'volatility': cnt / 10.0, 'k_change': k_change, 'q_change': q_change}

def get_issue_list_data(region):
    try:
        query = "SELECT keyword, sentiment_score, region, url FROM news WHERE keyword IS NOT NULL AND keyword != ''"
        df_raw = get_combined_df(query)
        if df_raw.empty: return pd.DataFrame()
        if region != "전국":
            df_raw = df_raw[df_raw['region'].str.contains(region, na=False)]
        df_raw['sentiment_score'] = df_raw['sentiment_score'].fillna(0.5)
        keyword_stats = {}
        for _, row in df_raw.iterrows():
            tokens = [t.strip() for token in row['keyword'].replace(',', ' ').split() if len(t := token.strip()) >= 2]
            for t in tokens:
                if t not in keyword_stats: keyword_stats[t] = {'count': 0, 'sent_sum': 0.0}
                keyword_stats[t]['count'] += 1
                keyword_stats[t]['sent_sum'] += row['sentiment_score']
        if not keyword_stats: return pd.DataFrame()
        res_data = [{'issue': kw, 'count': stat['count'], 'avg_sentiment': stat['sent_sum']/stat['count']} for kw, stat in keyword_stats.items()]
        df = pd.DataFrame(res_data).sort_values('count', ascending=False).head(10)
        df['rank'] = range(1, len(df) + 1)
        df['sentiment'] = np.where(df['avg_sentiment'] >= 0.5, '긍정', '부정')
        df['score_display'] = df['avg_sentiment'].map(lambda x: f"{x:.2f}")
        return df
    except: return pd.DataFrame()

# [주석] 사용자가 선택한 상위 지역명(전라도, 경상도 등)을 하위 행정구역(전남, 전북 등)과 매칭하여 통합 필터링합니다.
def get_chart_data(start_date, end_date, region, asset_type="코스피(KOSPI)"):
    # [주석] 1. DB에서 해당 기간의 뉴스 감성 데이터 로드
    query = "SELECT date(published_time) as date, sentiment_score, region FROM news WHERE date(published_time) BETWEEN ? AND ?"
    df = get_combined_df(query, params=(start_date.isoformat(), end_date.isoformat()))
   
    if df.empty:
        return pd.DataFrame()


    # [주석] 2. 지역 통합 필터링 (전라도, 경상도 등)
    region_map = {
        "전라도": ["전남", "전북", "전라"],
        "경상도": ["경남", "경북", "경상"],
        "충청도": ["충남", "충북", "충청"],
        "경기도": ["경기"]
    }


    if region != "전국":
        if region in region_map:
            search_keywords = "|".join(region_map[region])
            df = df[df['region'].str.contains(search_keywords, na=False)]
        else:
            df = df[df['region'].str.contains(region, na=False)]
   
    if df.empty:
        return pd.DataFrame()


    # [주석] 3. 일별 감성 지수 평균 계산
    df_s = df.groupby('date')['sentiment_score'].mean().reset_index()
    df_s.columns = ['date', 'sentiment_index']
   
    # [주석] 4. 주가 데이터 병합 및 주말 보정
    if fdr is not None:
        try:
            symbol = 'KQ11' if "코스닥" in asset_type else 'KS11'
            df_p = fdr.DataReader(symbol, start_date, end_date)[['Close']].reset_index()
            df_p.columns = ['date', 'asset_price']
            df_p['date'] = df_p['date'].dt.date.astype(str)
           
            # [주석] 핵심 1: 'left' 병합을 사용하여 주가가 없는 주말 뉴스 데이터도 보존합니다.
            merged_df = pd.merge(df_s, df_p, on='date', how='left')
           
            # [주석] 핵심 2: 주말/휴일의 빈 주가(NaN)를 직전 영업일 가격으로 채웁니다 (Forward Fill).
            # 이렇게 하면 선 그래프가 끊기지 않고 이어집니다.
            merged_df['asset_price'] = merged_df['asset_price'].fillna(method='ffill')
           
            # [주석] 만약 첫날이 주말이라 이전 데이터가 없다면 다음날 데이터로 채웁니다 (Backward Fill).
            merged_df['asset_price'] = merged_df['asset_price'].fillna(method='bfill')
           
            return merged_df
        except Exception as e:
            print(f"Error merging data: {e}")
            return df_s
   
    return df_s


# ==========================================
# 메인 로직
# ==========================================
st.sidebar.title("지능형 지역 경제 & 자산 분석")
st.sidebar.markdown("---")
start_date = st.sidebar.date_input("분석 시작일", datetime.now() - timedelta(days=30))
end_date = st.sidebar.date_input("분석 종료일", datetime.now())
asset_type = st.sidebar.radio("자산 종류", ["코스피(KOSPI)", "코스닥(KOSDAQ)"])
selected_region = st.sidebar.selectbox("분석 지역 선택", ["전국", "서울", "경기도", "강원도", "충청도", "전라도", "경상도"])

m = get_metrics_data(start_date, end_date, selected_region)
col1, col2, col3, col4 = st.columns(4)

with col1: 
    st.markdown(f'<div class="metric-card"><div class="metric-label">종합 감성지수 ({selected_region})</div><div class="metric-value">{m["sentiment_avg"]:.2f}</div></div>', unsafe_allow_html=True)
with col2: 
    st.markdown(f'<div class="metric-card"><div class="metric-label">경제 변동성 ({selected_region})</div><div class="metric-value">{m["volatility"]:.1f}%</div></div>', unsafe_allow_html=True)
with col3: 
    # 코스피(KOSPI) 변동률 고정 (k_change 사용)
    st.markdown(f'<div class="metric-card"><div class="metric-label">코스피(KOSPI) 변동</div><div class="metric-value" style="color:{"#2ecc71" if m["k_change"]>0 else "#e74c3c"}">{m["k_change"]:+.2f}%</div></div>', unsafe_allow_html=True)
with col4: 
    # 수집 뉴스량 대신 코스닥(KOSDAQ) 변동률로 변경 (q_change 사용)
    st.markdown(f'<div class="metric-card"><div class="metric-label">코스닥(KOSDAQ) 변동</div><div class="metric-value" style="color:{"#2ecc71" if m["q_change"]>0 else "#e74c3c"}">{m["q_change"]:+.2f}%</div></div>', unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

# 중앙 구역
mid_col1, mid_col2 = st.columns([1.5, 1])
with mid_col1:
    st.subheader(f"📍 인터랙티브 경제 지도")
    map_html_content = load_official_map()
    if map_html_content:
        import streamlit.components.v1 as components
        components.html(map_html_content, height=600, scrolling=True)
    else: st.error("지도 모듈 파일을 불러올 수 없습니다.")

with mid_col2:
    st.subheader(f"🔥 {selected_region} 핵심 이슈 TOP 10")
    issue_df = get_issue_list_data(selected_region)
    if not issue_df.empty:
        max_count = issue_df['count'].max()
        for _, row in issue_df.iterrows():
            badge = "badge-pos" if row['sentiment'] == "긍정" else "badge-neg"
            badge_icon = "▲ 긍정" if row['sentiment'] == "긍정" else "▼ 부정"
            fill_pct = int((row['count'] / max_count) * 100)
            bg_color = "rgba(46, 204, 113, 0.15)" if row['sentiment'] == "긍정" else "rgba(231, 76, 60, 0.15)"
            st.markdown(f'<div style="display:flex; justify-content:space-between; align-items:center; padding:10px 12px; margin-bottom:8px; border-radius:6px; border: 1px solid #f0f2f6; background: linear-gradient(90deg, {bg_color} {fill_pct}%, transparent {fill_pct}%);"><span style="font-weight:bold; color:#333;">{row["rank"]}. {row["issue"]} <span style="font-size:12px; color:#888;">({row["count"]}건)</span></span><span class="{badge}">{badge_icon} {row["score_display"]}</span></div>', unsafe_allow_html=True)
    else: st.info("이슈 데이터가 없습니다.")

# ==============================
# 6. 중단 구역 (Combo Chart)
# ==============================
st.markdown("<br>", unsafe_allow_html=True)
st.subheader(f"📊 {selected_region} 감성 지수 및 자산 가격 추이")

chart_df = get_chart_data(start_date, end_date, selected_region, asset_type)

if not chart_df.empty:
    fig = go.Figure()

    # 🔥 음수만 절댓값 처리 (그래프 표시용)
    display_values = chart_df['sentiment_index'].apply(
        lambda x: abs(x) if pd.notnull(x) and x < 0 else x
    )

    # 🔥 색상 조건 (음수=빨강, 양수=파랑)
    colors = chart_df['sentiment_index'].apply(
        lambda x: 'rgba(231,76,60,0.7)' if pd.notnull(x) and x < 0 
        else 'rgba(100,149,237,0.6)'
    )

    # -------------------------------
    # 감성 지수 막대 (음수 처리 포함)
    # -------------------------------

    real_values = chart_df['sentiment_index']

    # 그래프에 표시될 값
    display_values = np.where(real_values < 0, np.abs(real_values), real_values)

    # 색상 설정
    colors = np.where(real_values < 0,
                      'rgba(231, 76, 60, 0.8)',   # 음수 → 빨강
                      'rgba(100, 149, 237, 0.6)') # 양수 → 파랑

    fig.add_trace(go.Bar(
        x=chart_df['date'],
        y=display_values,  # 🔥 여기 절댓값 들어감
        name=f"{selected_region} 감성 지수",
        marker_color=colors,
        yaxis='y1',
            customdata=real_values,  # 🔥 실제값 저장
        hovertemplate=
            "날짜: %{x}<br>" +
            "실제 감성: %{customdata:.3f}<br>" +
            "표시값: %{y:.3f}<extra></extra>"
    ))


    # ✅ 자산 가격 선 그래프
    fig.add_trace(go.Scatter(
        x=chart_df['date'],
        y=chart_df['asset_price'],
        name=asset_type,
        line=dict(color='firebrick', width=3),
        yaxis='y2'
    ))

    # ✅ 레이아웃 유지 (0~1 고정)
    fig.update_layout(
        yaxis=dict(title="감성 지수 (0~1)", range=[0, 1]),
        yaxis2=dict(
            title=f"{asset_type} 가격",
            side="right",
            overlaying="y",
            showgrid=False
        ),
        height=450,
        template="plotly_white",
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    st.plotly_chart(fig, use_container_width=True)

else:
    st.warning(f"⚠️ {selected_region} 지역의 해당 기간 내 분석 데이터가 존재하지 않습니다.")

# 하단 탭
tab1, tab2, tab3, tab4 = st.tabs(["상관관계 분석", "감성 타임라인", "성과 분석", "최신 뉴스"])
with tab1:
    btm_col1, btm_col2 = st.columns(2)
    
    if not chart_df.empty:
        try:
            # [주석] 3x3 히트맵을 위해 KOSPI와 KOSDAQ 데이터를 실시간으로 가져옵니다.
            k_df = fdr.DataReader('KS11', start_date, end_date)[['Close']].rename(columns={'Close': 'KOSPI'})
            q_df = fdr.DataReader('KQ11', start_date, end_date)[['Close']].rename(columns={'Close': 'KOSDAQ'})
            
            # 날짜 형식 맞추기
            k_df.index = k_df.index.date.astype(str)
            q_df.index = q_df.index.date.astype(str)
            
            # [주석] 감성 지수와 두 지수 데이터를 날짜 기준으로 병합합니다.
            total_corr_df = chart_df[['date', 'sentiment_index']].merge(k_df, left_on='date', right_index=True)
            total_corr_df = total_corr_df.merge(q_df, left_on='date', right_index=True)
            
            # [주석] 항목 이름을 요청하신 대로 '감성', 'KOSPI', 'KOSDAQ'으로 설정합니다.
            # 컬럼명을 변경하여 히트맵 라벨에 바로 적용되도록 합니다.
            corr_input = total_corr_df[['sentiment_index', 'KOSPI', 'KOSDAQ']].rename(
                columns={'sentiment_index': '감성'}
            )
            
            # 실제 상관계수 계산 (3x3 행렬 생성)
            matrix = corr_input.corr()
            labels = ['감성', 'KOSPI', 'KOSDAQ']
            
            with btm_col1:
                st.write("### 🔍 감성-자산 상관계수 히트맵")
                # [주석] 데이터 연동은 유지하되, 항목 레이블을 이전과 동일하게 배치합니다.
                fig_heatmap = px.imshow(
                    matrix,
                    text_auto=".2f", # 소수점 둘째자리까지 표시
                    x=labels, 
                    y=labels,
                    color_continuous_scale='RdBu_r', # 붉은색(+)과 푸른색(-) 대비
                    range_color=[-1, 1] # 범위 고정
                )
                # 차트 레이아웃 최적화
                fig_heatmap.update_layout(width=None, height=400, margin=dict(l=20, r=20, t=20, b=20))
                st.plotly_chart(fig_heatmap, use_container_width=True)
                
            with btm_col2:
                # [주석] 오른쪽은 선택된 자산에 따른 산점도를 유지합니다.
                target_col = 'KOSPI' if 'KOSPI' in asset_type else 'KOSDAQ'
                st.write(f"### 📉 감성 vs {target_col} 수익률 산점도")
                
                fig_scatter = px.scatter(
                    total_corr_df,
                    x='sentiment_index',
                    y=target_col,
                    trendline="ols",
                    template="plotly_white",
                    labels={'sentiment_index': '뉴스 감성 지수', target_col: f'{target_col} 가격'}
                )
                st.plotly_chart(fig_scatter, use_container_width=True)
                
        except Exception as e:
            st.warning(f"데이터 연동 중 일부 지수 데이터를 불러오지 못했습니다: {e}")
            # 데이터 부족 시 안내
            st.info("FinanceDataReader를 통해 KOSPI/KOSDAQ 데이터를 가져오는 중입니다. 잠시만 기다려주세요.")
    else:
        st.info("상관관계 분석을 위한 데이터가 충분하지 않습니다.")
with tab2:
    st.write(f"### 📅 {selected_region} 일별 감성 캘린더")
   
    if not chart_df.empty:
        # [주석] 캘린더 구조 생성을 위한 날짜 처리
        cal_df = chart_df.copy()
        cal_df['date'] = pd.to_datetime(cal_df['date'])
        cal_df['day'] = cal_df['date'].dt.day
        cal_df['week'] = cal_df['date'].dt.isocalendar().week
        cal_df['weekday'] = cal_df['date'].dt.weekday # 0:월 ~ 6:일
       
        # [주석] 피벗 테이블 생성 및 데이터 없는 요일(NaN) 채우기
        z_raw = cal_df.pivot_table(index='week', columns='weekday', values='sentiment_index')
        t_raw = cal_df.pivot_table(index='week', columns='weekday', values='day')
       
        # [주석] ValueError 방지: 항상 0~6(월~일)까지 7개의 컬럼을 유지하도록 재정렬합니다.
        z_data = z_raw.reindex(columns=range(7))
        t_data = t_raw.reindex(columns=range(7))
       
        weekdays = ['월', '화', '수', '목', '금', '토', '일']
       
        # [주석] 캘린더 히트맵 시각화
        fig_cal = px.imshow(
            z_data, x=weekdays, y=z_data.index,
            color_continuous_scale='RdBu_r', range_color=[0, 1],
            aspect="auto", labels=dict(color="감성")
        )
        fig_cal.update_traces(
            text=t_data, texttemplate="%{text}", # 칸 안에 날짜 표시
            hovertemplate="<b>%{x}요일</b><br>감성 점수: %{z:.2f}<extra></extra>",
            textfont=dict(size=14, color="black")
        )
        fig_cal.update_layout(xaxis_title="", yaxis_title="주차", height=400, template="plotly_white")
        st.plotly_chart(fig_cal, use_container_width=True)
       
        # [주석] 캘린더 하단 상세 리포트 및 뉴스 연동
        st.markdown("---")
        st.write("🔍 **날짜별 상세 감성 뉴스 리포트**")
       
        sorted_dates = sorted(chart_df['date'].unique())
        s_date = st.select_slider("날짜 선택", options=sorted_dates, value=sorted_dates[-1])
       
        # [주석] 선택된 날짜의 실제 뉴스 리스트를 DB에서 가져옵니다.
        # 이전에 통합한 지역 필터링(전라도-전남/전북 등)이 적용된 get_combined_df를 호출합니다.
        day_news = get_combined_df("SELECT title, sentiment_score, url, region FROM news WHERE date(published_time) = ?", params=(str(s_date),))
       
        # [주석] 지역 필터링 적용
        if selected_region != "전국":
            day_news = day_news[day_news['region'].str.contains(selected_region, na=False)]
           
        col_res1, col_res2 = st.columns([1, 2])
        day_avg = chart_df[chart_df['date'] == s_date]['sentiment_index'].values[0]
       
        with col_res1:
            res_status = "🚀 긍정" if day_avg > 0.55 else "📉 부정" if day_avg < 0.45 else "☁️ 중립"
            st.metric(label=f"{s_date} 종합", value=res_status, delta=f"{day_avg:.2f}")
            st.progress(day_avg)
           
        with col_res2:
            if not day_news.empty:
                st.write(f"📄 **해당 날짜 주요 기사 (최대 5건)**")
                for _, row in day_news.sort_values('sentiment_score', ascending=False).head(5).iterrows():
                    icon = "🟢" if row['sentiment_score'] > 0.5 else "🔴"
                    st.markdown(f"{icon} [{row['title']}]({row['url']}) `({row['sentiment_score']:.2f})`")
            else:
                st.info("상세 뉴스 내역이 없습니다.")
    else:
        st.warning("데이터가 부족하여 캘린더를 표시할 수 없습니다.")
with tab3:
    st.write(f"### 💹 {asset_type} 기술적 지표 및 변동성 분석")
    if fdr is not None:
        try:
            # 1. 이동평균선을 구하려면 과거 데이터가 더 필요하므로 시작일을 60일 더 앞으로 당겨서 가져옵니다.
            tech_start = start_date - timedelta(days=60)
            symbol = 'KS11' if "KOSPI" in asset_type or "코스피" in asset_type else 'KQ11'
            df_tech = fdr.DataReader(symbol, tech_start, end_date).reset_index()
            
            if not df_tech.empty:
                # 2. 기술적 지표 계산 (Pandas 활용)
                df_tech['MA20'] = df_tech['Close'].rolling(window=20).mean() # 20일 이동평균선
                df_tech['StdDev'] = df_tech['Close'].rolling(window=20).std() # 20일 표준편차
                df_tech['Upper_Band'] = df_tech['MA20'] + (df_tech['StdDev'] * 2) # 볼린저 밴드 상단
                df_tech['Lower_Band'] = df_tech['MA20'] - (df_tech['StdDev'] * 2) # 볼린저 밴드 하단
                
                # 3. 화면에 그릴 때는 사용자가 선택한 기간만 잘라서 보여줍니다.
                df_tech['Date_str'] = df_tech['Date'].dt.date.astype(str)
                mask = (df_tech['Date'].dt.date >= start_date) & (df_tech['Date'].dt.date <= end_date)
                df_plot = df_tech.loc[mask]
                
                # 4. 차트 그리기
                fig_tech = go.Figure()
                
                # 종가 선
                fig_tech.add_trace(go.Scatter(x=df_plot['Date_str'], y=df_plot['Close'], name='실제 주가(종가)', line=dict(color='#2c3e50', width=2)))
                # 20일 이동평균선
                fig_tech.add_trace(go.Scatter(x=df_plot['Date_str'], y=df_plot['MA20'], name='20일 추세선(MA20)', line=dict(color='#f39c12', width=2)))
                # 볼린저 밴드 (상단~하단 색칠)
                fig_tech.add_trace(go.Scatter(x=df_plot['Date_str'], y=df_plot['Upper_Band'], name='변동성 상단', line=dict(color='rgba(52, 152, 219, 0.6)', dash='dash')))
                fig_tech.add_trace(go.Scatter(x=df_plot['Date_str'], y=df_plot['Lower_Band'], name='변동성 하단', fill='tonexty', fillcolor='rgba(52, 152, 219, 0.15)', line=dict(color='rgba(52, 152, 219, 0.6)', dash='dash')))
                if not chart_df.empty:
                   fig_tech.add_trace(go.Scatter(
                        x=chart_df['date'], 
                        y=chart_df['sentiment_index'], 
                        name="지역 감성 지수", 
                        line=dict(color='#8e44ad', width=2.5, dash='dot', shape='spline'), # 보라색 점선, 부드러운 곡선 처리
                        yaxis='y2'
                    ))

                # 👇 [수정할 부분!] 오른쪽 Y축(y2) 설정을 추가하고 범례 위치를 깔끔하게 맞춥니다.
                fig_tech.update_layout(
                    height=500, 
                    template="plotly_white", 
                    hovermode="x unified",
                    xaxis=dict(range=[start_date, end_date]), # 사이드바 날짜 고정
                    yaxis=dict(title=f"{asset_type} 가격"), # 왼쪽 Y축 (주가)
                    yaxis2=dict(title="감성 지수", overlaying="y", side="right", range=[0, 1], showgrid=False), # 오른쪽 Y축 (감성)
                    legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1)
                )
                st.plotly_chart(fig_tech, use_container_width=True)
                
                # 5. 실제 역사적 변동성(Historical Volatility) 계산 (연율화)
                daily_returns = df_plot['Close'].pct_change().dropna()
                historical_volatility = daily_returns.std() * np.sqrt(252) * 100
                
                st.info(f"💡 **분석 포인트:** 현재 선택하신 기간 동안 {asset_type}의 실제 주가 변동성(연환산)은 약 **{historical_volatility:.2f}%** 입니다. 볼린저 밴드(파란 영역)가 넓어질수록 시장의 불안정성(변동폭)이 커짐을 의미합니다.")
                
        except Exception as e:
            st.error("기술적 지표를 계산하는 중 오류가 발생했습니다.")
    else:
        st.warning("FinanceDataReader 라이브러리가 설치되어 있지 않아 분석을 실행할 수 없습니다.")
with tab4:
    st.write(f"#### 📰 {selected_region} 최신 감성 뉴스")
    news_q = "SELECT title, sentiment_score, published_time as date, url, region FROM news"
    n_df = get_combined_df(news_q)
    if not n_df.empty:
        if selected_region != "전국": n_df = n_df[n_df['region'].str.contains(selected_region, na=False)]
        for _, row in n_df.sort_values('date', ascending=False).head(5).iterrows():
            st.markdown(f'<div style="padding:10px; border-left:5px solid {"#2ecc71" if row["sentiment_score"]>0.5 else "#e74c3c"}; background-color:#f9f9f9; margin-bottom:10px; border-radius:4px;"><div style="font-size:0.8em; color:#888;">{row["date"]} | 감성: {row["sentiment_score"]:.2f}</div><div style="font-weight:bold;"><a href="{row["url"]}" target="_blank" style="text-decoration:none; color:#333;">{row["title"]}</a></div></div>', unsafe_allow_html=True)
st.markdown("---")
st.markdown("<p style='text-align: center; color: #999;'>© 2026 지능형 지역 경제 & 자산 분석 시스템</p>", unsafe_allow_html=True)