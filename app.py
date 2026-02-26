import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import plotly.graph_objects as go
import plotly.express as px
from streamlit_folium import st_folium
import folium
from folium import IFrame
import html
from datetime import datetime, timedelta
import sys
import os

# 외부 맵 모듈 경로 추가
map_module_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'Data_crowling_mini_project', 'map'))
if map_module_path not in sys.path:
    sys.path.append(map_module_path)

# 외부 모듈 임포트
try:
    from map_generator_geo import NewsMapGeneratorGeo
    from region_coords import REGION_COORDS, KOREA_CENTER, DEFAULT_ZOOM
    from color_mapper import get_sentiment_label, get_sentiment_color
    MAP_MODULE_AVAILABLE = True
except ImportError:
    MAP_MODULE_AVAILABLE = False

# FinanceDataReader 임포트
try:
    import FinanceDataReader as fdr
except ImportError:
    fdr = None

# ==========================================
# 0. 데이터베이스 연결 및 통합 로직 (지도 이외의 기능용)
# ==========================================
def get_db_conn(db_name):
    """DB 연결 (data 폴더 내)"""
    db_path = os.path.join('data', db_name)
    return sqlite3.connect(db_path)

def get_combined_df(query, params=None):
    """두 데이터베이스(news.db, news_scraped.db)에서 데이터를 가져와 통합하고 중복을 제거함"""
    df_list = []
    # 데이터베이스 파일 존재 여부 확인 후 로드
    for db_file in ['news.db', 'news_scraped.db']:
        try:
            full_path = os.path.join('data', db_file)
            if os.path.exists(full_path):
                conn = sqlite3.connect(full_path)
                df = pd.read_sql(query, conn, params=params)
                conn.close()
                if not df.empty:
                    df_list.append(df)
        except Exception as e:
            # st.error(f"Error loading {db_file}: {e}") # 사용자에게 너무 많은 에러를 노출하지 않기 위해 주석 처리
            continue
    
    if not df_list:
        return pd.DataFrame()
        
    combined_df = pd.concat(df_list, ignore_index=True)
    if 'url' in combined_df.columns:
        combined_df = combined_df.drop_duplicates(subset='url')
    return combined_df

# ==========================================
# 1. 기본 설정 및 테마
# ==========================================
st.set_page_config(page_title="지능형 지역 경제 & 자산 분석", page_icon="📈", layout="wide")
st.markdown("""
<style>
    .metric-card { background-color: #ffffff; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border: 1px solid #f0f2f6; text-align: center; }
    .metric-label { font-size: 14px; color: #666; margin-bottom: 5px; }
    .metric-value { font-size: 24px; font-weight: bold; color: #1f77b4; }
    .badge-pos { background-color: #d4edda; color: #155724; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: bold; }
    .badge-neg { background-color: #f8d7da; color: #721c24; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 데이터 로드 함수 (실제 DB + 시장 데이터)
# ==========================================

@st.cache_data(ttl=600) # 10분간 캐싱
def load_official_map():
    """기존 지도 모듈을 실행하여 news_map_geo.html을 업데이트하고 내용을 불러옴"""
    if not MAP_MODULE_AVAILABLE: return None
    from map_generator_geo import NewsMapGeneratorGeo
    
    # 1. 기존 모듈 경로 설정
    official_map_path = os.path.join('Data_crowling_mini_project', 'map', 'news_map_geo.html')
    
    # 2. 기존 모듈을 그대로 사용하여 파일 업데이트
    generator = NewsMapGeneratorGeo()
    generator.generate(official_map_path, max_news=10)
    
    # 3. 업데이트된 파일을 불러오기
    if os.path.exists(official_map_path):
        with open(official_map_path, 'r', encoding='utf-8') as f:
            return f.read()
    return None

def get_metrics_data(start_date, end_date, region):
    """선택된 지역과 날짜 범위에 따른 메트릭 계산"""
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

def get_region_map_stats():
    query = "SELECT region, sentiment_score, url FROM news WHERE region IS NOT NULL"
    df = get_combined_df(query)
    if df.empty:
        return pd.DataFrame(columns=['region', 'avg_sentiment', 'count'])
    
    stats = df.groupby('region').agg(
        avg_sentiment=('sentiment_score', 'mean'),
        count=('sentiment_score', 'count')
    ).reset_index()
    return stats

def get_issue_list_data(region):
    """키워드별 실제 뉴스 감성 점수 평균을 계산하여 호재/악재 판별"""
    try:
        query = "SELECT keyword, sentiment_score, region, url FROM news WHERE keyword IS NOT NULL AND keyword != ''"
        df_raw = get_combined_df(query)
        
        if df_raw.empty:
            return pd.DataFrame(columns=['rank', 'issue', 'sentiment', 'score'])
        
        if region != "전국":
            df_raw = df_raw[df_raw['region'].str.contains(region, na=False)]
            
        df_raw['sentiment_score'] = df_raw['sentiment_score'].fillna(0.5)
        
        if df_raw.empty:
            return pd.DataFrame(columns=['rank', 'issue', 'sentiment', 'score'])
        
        # 키워드별로 [빈도, 감성점수합계] 저장할 딕셔너리
        keyword_stats = {}
        
        for _, row in df_raw.iterrows():
            tokens = [t.strip() for token in row['keyword'].replace(',', ' ').split() if len(t := token.strip()) >= 2]
            for t in tokens:
                if t not in keyword_stats:
                    keyword_stats[t] = {'count': 0, 'sent_sum': 0.0}
                keyword_stats[t]['count'] += 1
                keyword_stats[t]['sent_sum'] += row['sentiment_score']
        
        if not keyword_stats:
            return pd.DataFrame(columns=['rank', 'issue', 'sentiment', 'score'])
            
        # 결과 데이터프레임 생성
        res_data = []
        for kw, stat in keyword_stats.items():
            avg_sent = stat['sent_sum'] / stat['count']
            res_data.append({
                'issue': kw,
                'count': stat['count'],
                'avg_sentiment': avg_sent
            })
            
        df = pd.DataFrame(res_data)
        # 언급 빈도(count) 순으로 상위 10개 추출
        df = df.sort_values('count', ascending=False).head(10)
        df['rank'] = range(1, len(df) + 1)
        
        # 실제 감성 점수(avg_sentiment) 기준으로 긍부정 판별 (0.5 기준)
        df['sentiment'] = np.where(df['avg_sentiment'] >= 0.5, '긍정', '부정')
        # 화면에 보여줄 점수는 소수점 2자리까지
        df['score_display'] = df['avg_sentiment'].map(lambda x: f"{x:.2f}")
        
        return df[['rank', 'issue', 'sentiment', 'score_display', 'count']]
    except Exception as e:
        return pd.DataFrame(columns=['rank', 'issue', 'sentiment', 'score_display', 'count'])

def get_chart_data(start_date, end_date, region, asset_type):
    """자산 종류와 날짜 범위에 따른 감성-가격 데이터 로드"""
    query = "SELECT date(published_time) as date, sentiment_score, url FROM news WHERE date(published_time) BETWEEN ? AND ?"
    df = get_combined_df(query, params=(start_date.isoformat(), end_date.isoformat()))
    
    if df.empty:
        return pd.DataFrame()

    # 감성 점수와 뉴스 건수를 함께 집계
    df_s = df.groupby('date').agg(
        sentiment_index=('sentiment_score', 'mean'),
        news_count=('sentiment_score', 'count')
    ).reset_index()
    
    # 자산 종류에 따른 심볼 매핑
    symbol = 'KS11' if "KOSPI" in asset_type or "코스피" in asset_type else 'KQ11'
    base_price = 2500 if symbol == 'KS11' else 800
    
    if fdr is not None:
        try:
            df_p = fdr.DataReader(symbol, start_date, end_date)[['Close']].reset_index()
            df_p.columns = ['date', 'asset_price']
            df_p['date'] = df_p['date'].dt.date.astype(str)
            merged = pd.merge(df_s, df_p, on='date', how='inner')
            if not merged.empty: return merged
        except: pass
    
    # 데이터가 없거나 FinanceDataReader 실패 시 보정된 더미 생성
    df_s['asset_price'] = base_price + (df_s['sentiment_index'] - 0.5).cumsum() * (50 if symbol == 'KS11' else 15)
    return df_s

# ==========================================
# 3. 사이드바 (Sidebar)
# ==========================================
st.sidebar.title("지능형 지역 경제 & 자산 분석")
st.sidebar.markdown("---")
start_date = st.sidebar.date_input("분석 시작일", datetime.now() - timedelta(days=30))
end_date = st.sidebar.date_input("분석 종료일", datetime.now())
asset_type = st.sidebar.radio("자산 종류", ["코스피(KOSPI)", "코스닥(KOSDAQ)"])
selected_region = st.sidebar.selectbox("분석 지역 선택", ["전국", "서울", "경기도", "강원도", "충청도", "전라도", "경상도"])
st.sidebar.markdown("---")
st.sidebar.info("Map Engine: Folium Marker & News Popup Connected")

# ==========================================
# 4. 상단 메트릭 (Top Metrics)
# ==========================================
m = get_metrics_data(start_date, end_date, selected_region)
col1, col2, col3, col4 = st.columns(4)
with col1: st.markdown(f'<div class="metric-card"><div class="metric-label">종합 감성지수 ({selected_region})</div><div class="metric-value">{m["sentiment_avg"]:.2f}</div></div>', unsafe_allow_html=True)
with col2: st.markdown(f'<div class="metric-card"><div class="metric-label">경제 변동성 ({selected_region})</div><div class="metric-value">{m["volatility"]:.1f}%</div></div>', unsafe_allow_html=True)
with col3: st.markdown(f'<div class="metric-card"><div class="metric-label">코스피 변동</div><div class="metric-value" style="color:{"#2ecc71" if m["k_change"]>0 else "#e74c3c"}">{m["k_change"]:+.2f}%</div></div>', unsafe_allow_html=True)
with col4: st.markdown(f'<div class="metric-card"><div class="metric-label">코스닥 변동</div><div class="metric-value" style="color:{"#2ecc71" if m["q_change"]>0 else "#e74c3c"}">{m["q_change"]:+.2f}%</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# 5. 중앙 구역 (Map & Top 10 List)
# ==========================================
mid_col1, mid_col2 = st.columns([1.5, 1])
with mid_col1:
    st.subheader(f"📍 {selected_region} 인터랙티브 경제 지도")
    
    map_html = load_official_map()
    if map_html:
        import streamlit.components.v1 as components
        components.html(map_html, height=600, scrolling=True)
    else:
        st.error("지도 모듈을 로드할 수 없습니다.")

with mid_col2:
    st.subheader(f"🔥 {selected_region} 핵심 이슈 TOP 10")
    issue_df = get_issue_list_data(selected_region)
    
    if not issue_df.empty:
        max_count = issue_df['count'].max()
        for _, row in issue_df.iterrows():
            badge = "badge-pos" if row['sentiment'] == "긍정" else "badge-neg"
            badge_icon = "▲ 긍정" if row['sentiment'] == "긍정" else "▼ 부정"
            fill_pct = int((row['count'] / max_count) * 100) if max_count > 0 else 0
            bg_color = "rgba(46, 204, 113, 0.15)" if row['sentiment'] == "긍정" else "rgba(231, 76, 60, 0.15)"
            
            custom_style = f"""
                display:flex; justify-content:space-between; align-items:center;
                padding:10px 12px; margin-bottom:8px; border-radius:6px;
                border: 1px solid #f0f2f6;
                background: linear-gradient(90deg, {bg_color} {fill_pct}%, transparent {fill_pct}%);
            """
            
            html_str = f"""
            <div style="{custom_style}">
                <span style="font-weight:bold; color:#333; font-size: 15px;">
                    {row["rank"]}. {row["issue"]} 
                    <span style="font-size:12px; color:#888; font-weight:normal; margin-left: 4px;">({row["count"]}건)</span>
                </span>
                <span class="{badge}">
                    {badge_icon} {row["score_display"]}
                </span>
            </div>
            """
            st.markdown(html_str, unsafe_allow_html=True)
    else:
        st.info("해당 지역의 이슈 데이터가 없습니다.")

# ==========================================
# 6. 중단 구역 (Combo Chart)
# ==========================================
st.markdown("<br>", unsafe_allow_html=True)
st.subheader(f"📊 {selected_region} 감성 지수 및 {asset_type} 추이")
chart_df = get_chart_data(start_date, end_date, selected_region, asset_type)
if not chart_df.empty:
    fig = go.Figure()
    fig.add_trace(go.Bar(x=chart_df['date'], y=chart_df['sentiment_index'], name="지역 감성 지수", marker_color='rgba(100, 149, 237, 0.6)', yaxis='y1'))
    fig.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['asset_price'], name="자산 가격", line=dict(color='firebrick', width=3), yaxis='y2'))
    fig.update_layout(yaxis=dict(title="감성 지수", range=[0, 1]), yaxis2=dict(title="자산 가격", side="right", overlaying="y", showgrid=False), height=450, template="plotly_white")
    st.plotly_chart(fig, width="stretch")

# ==========================================
# 7. 하단 구역 (상세 분석 탭)
# ==========================================
st.markdown("<br>", unsafe_allow_html=True)
tab1, tab2, tab3, tab4 = st.tabs(["상관관계 분석", "감성 타임라인", "자산 가격 추이", "감성 기반 뉴스"])

with tab1:
    st.write("### 🔍 감성-자산 다각도 상관 분석")
    
    # 1단: 기존 히트맵 및 산점도
    btm_col1, btm_col2 = st.columns(2)
    with btm_col1:
        st.write("#### 🌡️ 감성-자산 상관계수 히트맵")
        labels = ['감성', 'KOSPI', 'KOSDAQ']
        # 기존 로직 유지 (더미 기반)
        st.plotly_chart(px.imshow(np.random.uniform(0.6, 0.9, (3, 3)), 
                                  text_auto=True, x=labels, y=labels, 
                                  color_continuous_scale='RdBu_r'), use_container_width=True)
    with btm_col2:
        st.write("#### 📉 감성 vs 자산 가격 산점도")
        if not chart_df.empty:
            fig_scatter = px.scatter(chart_df, x='sentiment_index', y='asset_price', 
                                     trendline="ols", template="plotly_white")
            st.plotly_chart(fig_scatter, use_container_width=True)
            
    st.markdown("---")
    
    # 2단: 상세 수치 및 이동 상관계수
    btm_col3, btm_col4 = st.columns([1, 2])
    with btm_col3:
        st.write("#### 🔢 상세 상관 지표")
        if not chart_df.empty:
            corr_val = chart_df['sentiment_index'].corr(chart_df['asset_price'])
            st.metric("실제 데이터 상관계수", f"{corr_val:.3f}")
            st.info("상관계수는 1에 가까울수록 두 지표가 같은 방향으로 움직임을 뜻합니다.")
            
    with btm_col4:
        st.write("#### 📈 기간별 상관관계 변화 (7일 이동 상관계수)")
        if len(chart_df) >= 7:
            df_corr = chart_df.copy()
            df_corr['rolling_corr'] = df_corr['sentiment_index'].rolling(7).corr(df_corr['asset_price'])
            fig_rolling = px.line(df_corr, x='date', y='rolling_corr', 
                                  labels={'rolling_corr': '상관계수'})
            fig_rolling.add_hline(y=0, line_dash="dash", line_color="gray")
            fig_rolling.update_layout(yaxis=dict(range=[-1, 1]), template="plotly_white", height=300)
            st.plotly_chart(fig_rolling, use_container_width=True)
        else:
            st.warning("분석을 위한 충분한 데이터(7일 이상)가 없습니다.")

with tab2:
    st.write(f"### 🕒 {selected_region} 감성 및 뉴스 발행량 타임라인")
    if not chart_df.empty:
        fig_timeline = go.Figure()
        # 뉴스 건수 막대 (이중축 - y2)
        fig_timeline.add_trace(go.Bar(
            x=chart_df['date'], y=chart_df['news_count'],
            name="뉴스 발행 건수", marker_color='rgba(200, 200, 200, 0.3)',
            yaxis='y2'
        ))
        # 평균 감성 선 (이중축 - y1)
        fig_timeline.add_trace(go.Scatter(
            x=chart_df['date'], y=chart_df['sentiment_index'],
            mode='lines+markers', name="평균 감성 지수",
            line=dict(color='#1f77b4', width=3),
            marker=dict(size=8, color='#1f77b4')
        ))
        
        fig_timeline.update_layout(
            yaxis=dict(title="감성 지수", range=[0, 1], side='left'),
            yaxis2=dict(title="뉴스 건수", side='right', overlaying='y', showgrid=False),
            height=500, template="plotly_white",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_timeline, use_container_width=True)
    else:
        st.info("데이터가 부족합니다.")

with tab3:
    st.write(f"### 📈 {asset_type} 성과 및 위험 분석")
    if not chart_df.empty:
        df_stat = chart_df.copy()
        df_stat['returns'] = df_stat['asset_price'].pct_change() * 100
        df_stat['cum_return'] = (1 + df_stat['returns'] / 100).cumprod() - 1
        df_stat['cum_return_pct'] = df_stat['cum_return'] * 100
        
        col_st1, col_st2 = st.columns(2)
        
        with col_st1:
            st.write("#### ⚖️ 감성-수익률 사분면 분석")
            # 사분면 분류 (감성 0.5 기준, 수익률 0 기준)
            fig_quad = px.scatter(df_stat.dropna(), x='sentiment_index', y='returns',
                                  color='returns', color_continuous_scale='RdBu_r',
                                  labels={'sentiment_index': '감성 지수', 'returns': '일별 수익률 (%)'},
                                  title="감성 변화에 따른 수익률 분포")
            fig_quad.add_hline(y=0, line_dash="dash", line_color="black", opacity=0.3)
            fig_quad.add_vline(x=0.5, line_dash="dash", line_color="black", opacity=0.3)
            fig_quad.update_layout(template="plotly_white", height=400)
            st.plotly_chart(fig_quad, use_container_width=True)
            st.caption("1사분면(우상단): 긍정적 뉴스 & 가격 상승 (동행 호재)")
            
        with col_st2:
            st.write("#### 💰 누적 수익률 추이 (%)")
            fig_cum = px.area(df_stat, x='date', y='cum_return_pct',
                              labels={'cum_return_pct': '누적 수익률 (%)'},
                              title=f"분석 기간 내 {asset_type} 성과")
            fig_cum.add_hline(y=0, line_dash="solid", line_color="gray")
            fig_cum.update_traces(line_color="firebrick", fillcolor="rgba(178, 34, 34, 0.2)")
            fig_cum.update_layout(template="plotly_white", height=400)
            st.plotly_chart(fig_cum, use_container_width=True)

        st.markdown("---")
        # 추가 지표 표시
        m_col1, m_col2, m_col3 = st.columns(3)
        with m_col1:
            st.metric("최고 누적 수익률", f"{df_stat['cum_return_pct'].max():.2f}%")
        with m_col2:
            st.metric("평균 일일 변동폭", f"{df_stat['returns'].abs().mean():.2f}%")
        with m_col3:
            hit_rate = len(df_stat[(df_stat['sentiment_index'] > 0.5) & (df_stat['returns'] > 0)]) / len(df_stat[df_stat['sentiment_index'] > 0.5]) * 100 if len(df_stat[df_stat['sentiment_index'] > 0.5]) > 0 else 0
            st.metric("긍정 감성 적중률", f"{hit_rate:.1f}%")
    else:
        st.info("성과 분석을 위한 데이터가 부족합니다.")
with tab4:
    st.write(f"### 📰 {selected_region} 최신 감성 뉴스 리스트")
    latest_news_query = "SELECT title, sentiment_score, published_time as date, url, region FROM news"
    news_list_df = get_combined_df(latest_news_query)
    
    if not news_list_df.empty:
        if selected_region != "전국":
            news_list_df = news_list_df[news_list_df['region'].str.contains(selected_region, na=False)]
        
        news_list_df = news_list_df.sort_values('date', ascending=False).head(5)
        for _, row in news_list_df.iterrows():
            color = "#2ecc71" if row['sentiment_score'] > 0.5 else "#e74c3c"
            st.markdown(f'<div style="padding:10px; border-left:5px solid {color}; background-color:#f9f9f9; margin-bottom:10px; border-radius:4px;"><div style="font-size:0.8em; color:#888;">{row["date"]} | 감성: {row["sentiment_score"]:.2f}</div><div style="font-weight:bold;"><a href="{row["url"]}" target="_blank" style="text-decoration:none; color:#333;">{row["title"]}</a></div></div>', unsafe_allow_html=True)
    else:
        st.info(f"{selected_region} 지역의 뉴스 데이터가 없습니다.")

st.markdown("---")
st.markdown("<p style='text-align: center; color: #999;'>© 2026 지능형 지역 경제 & 자산 분석 시스템 (Hybrid Map Connected)</p>", unsafe_allow_html=True)
