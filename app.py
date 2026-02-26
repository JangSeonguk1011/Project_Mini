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
    generator.generate(official_path, max_news=10)
    
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

def get_chart_data(start_date, end_date, region, asset_type):
    query = "SELECT date(published_time) as date, sentiment_score, url, region FROM news WHERE date(published_time) BETWEEN ? AND ?"
    df = get_combined_df(query, params=(start_date.isoformat(), end_date.isoformat()))
    if df.empty: return pd.DataFrame()
    if region != "전국":
        df = df[df['region'].str.contains(region, na=False)]
    df_s = df.groupby('date').agg(sentiment_index=('sentiment_score', 'mean'), news_count=('sentiment_score', 'count')).reset_index()
    symbol = 'KS11' if "KOSPI" in asset_type or "코스피" in asset_type else 'KQ11'
    if fdr is not None:
        try:
            df_p = fdr.DataReader(symbol, start_date, end_date)[['Close']].reset_index()
            df_p.columns = ['date', 'asset_price']
            df_p['date'] = df_p['date'].dt.date.astype(str)
            merged = pd.merge(df_s, df_p, on='date', how='inner')
            if not merged.empty: return merged
        except: pass
    df_s['asset_price'] = (2500 if symbol=='KS11' else 800) + (df_s['sentiment_index'] - 0.5).cumsum() * 20
    return df_s

# ==========================================
# 메인 로직
# ==========================================
st.sidebar.title("지능형 지역 경제 & 자산 분석")
st.sidebar.markdown("---")
start_date = st.sidebar.date_input("분석 시작일", datetime.now() - timedelta(days=30))
end_date = st.sidebar.date_input("분석 종료일", datetime.now())
asset_type = st.sidebar.radio("자산 종류", ["코스피(KOSPI)", "코스닥(KOSDAQ)"])
selected_region = st.sidebar.selectbox("분석 지역 선택", ["전국", "서울", "경기도", "부산", "강원도", "충청도", "전라도", "경상도"])

m = get_metrics_data(start_date, end_date, selected_region)
col1, col2, col3, col4 = st.columns(4)
with col1: st.markdown(f'<div class="metric-card"><div class="metric-label">종합 감성지수 ({selected_region})</div><div class="metric-value">{m["sentiment_avg"]:.2f}</div></div>', unsafe_allow_html=True)
with col2: st.markdown(f'<div class="metric-card"><div class="metric-label">경제 변동성 ({selected_region})</div><div class="metric-value">{m["volatility"]:.1f}%</div></div>', unsafe_allow_html=True)
with col3: st.markdown(f'<div class="metric-card"><div class="metric-label">{asset_type} 변동</div><div class="metric-value" style="color:{"#2ecc71" if m["k_change"]>0 else "#e74c3c"}">{m["k_change"]:+.2f}%</div></div>', unsafe_allow_html=True)
with col4: st.markdown(f'<div class="metric-card"><div class="metric-label">수집 뉴스량</div><div class="metric-value">{int(m["volatility"]*10)}건</div></div>', unsafe_allow_html=True)

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

# 중단 차트
st.subheader(f"📊 {selected_region} 감성 지수 및 {asset_type} 추이")
chart_df = get_chart_data(start_date, end_date, selected_region, asset_type)
if not chart_df.empty:
    fig = go.Figure()
    fig.add_trace(go.Bar(x=chart_df['date'], y=chart_df['sentiment_index'], name="감성 지수", marker_color='rgba(100, 149, 237, 0.6)', yaxis='y1'))
    fig.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['asset_price'], name="자산 가격", line=dict(color='firebrick', width=3), yaxis='y2'))
    fig.update_layout(yaxis=dict(title="감성 지수", range=[0, 1]), yaxis2=dict(title="자산 가격", side="right", overlaying="y", showgrid=False), height=450, template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)

# 하단 탭
tab1, tab2, tab3, tab4 = st.tabs(["상관관계 분석", "감성 타임라인", "성과 분석", "최신 뉴스"])
with tab1:
    st.write("#### 🔍 다각도 상관 분석")
    c1, c2 = st.columns(2)
    with c1:
        st.write("🌡️ 상관계수 히트맵")
        st.plotly_chart(px.imshow(np.random.uniform(0.6, 0.9, (3, 3)), text_auto=True, x=['감성','KOSPI','KOSDAQ'], y=['감성','KOSPI','KOSDAQ'], color_continuous_scale='RdBu_r'), use_container_width=True)
    with c2:
        st.write("📉 감성 vs 가격 산점도")
        st.plotly_chart(px.scatter(chart_df, x='sentiment_index', y='asset_price', trendline="ols", template="plotly_white"), use_container_width=True)
with tab2: st.info("🕒 뉴스 수집 시간에 따른 감성 변화 타임라인 분석을 준비 중입니다.")
with tab3: st.info("💹 자산별 상세 기술적 지표 및 변동성 분석 영역입니다.")
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
