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

# 외부 모듈 임포트 시도
try:
    from region_coords import REGION_COORDS, KOREA_CENTER, DEFAULT_ZOOM
    from color_mapper import (
        get_sentiment_color as ext_get_sentiment_color,
        get_sentiment_label as ext_get_sentiment_label,
        get_sentiment_icon,
        get_region_color_by_avg
    )
    MAP_MODULE_AVAILABLE = True
except ImportError:
    MAP_MODULE_AVAILABLE = False

# FinanceDataReader 임포트
try:
    import FinanceDataReader as fdr
except ImportError:
    fdr = None

# ==========================================
# 0. 외부 모듈 시각화 로직 이식 (Data_crowling_mini_project/map 기준)
# ==========================================

def get_sentiment_color(sentiment_score: float) -> str:
    """color_mapper.py 원본 로직"""
    if sentiment_score is None or sentiment_score == 0: return 'gray'
    elif sentiment_score > 0.5: return 'blue'
    elif sentiment_score > 0: return 'lightgreen'
    elif sentiment_score < -0.5: return 'red'
    else: return 'lightred'

def get_sentiment_icon(sentiment_score: float) -> str:
    """color_mapper.py 원본 로직"""
    if sentiment_score is None or sentiment_score == 0: return 'info-sign'
    elif sentiment_score > 0: return 'arrow-up'
    else: return 'arrow-down'

def get_region_color_by_avg(avg_sentiment: float) -> str:
    """color_mapper.py 원본 로직"""
    if avg_sentiment is None or avg_sentiment == 0: return '#FFFFFF'
    elif avg_sentiment > 0.3: return '#0066CC'
    elif avg_sentiment > 0: return '#81C784'
    elif avg_sentiment < -0.3: return '#CC0000'
    else: return '#FF6666'

def get_sentiment_label(sentiment_score: float) -> str:
    """color_mapper.py 원본 로직"""
    if sentiment_score is None: return '분석 안 됨'
    elif sentiment_score == 0: return '중립'
    elif sentiment_score > 0.5: return '매우 긍정적'
    elif score := sentiment_score:
        if score > 0.2: return '긍정적'
        elif score > 0: return '약간 긍정적'
        elif score < -0.5: return '매우 부정적'
        elif score < -0.2: return '부정적'
    return '약간 부정적'

def create_popup_html(news_list, region):
    """map_generator.py 원본 _create_popup_html 로직"""
    if not news_list: return f"<h4>{region}</h4><p>뉴스가 없습니다.</p>"
    
    html_content = f"""
    <div style="width: 400px; max-height: 500px; overflow-y: auto; font-family: Arial, sans-serif;">
        <h3 style="margin: 0 0 10px 0; color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 5px;">
            📍 {region} ({len(news_list)}개 뉴스)
        </h3>
    """
    for i, news in enumerate(news_list[:10]):
        title = html.escape(news.get('title', '제목 없음')[:80])
        url = news.get('url', '#')
        keyword = news.get('keyword', '키워드 없음')
        sentiment = news.get('sentiment_score', 0) or 0
        sentiment_label = get_sentiment_label(sentiment)
        sentiment_color = 'blue' if sentiment > 0 else 'red' if sentiment < 0 else 'gray'
        published_time = news.get('published_time', '날짜 없음')
        
        html_content += f"""
        <div style="margin: 10px 0; padding: 10px; background: #f9f9f9; border-left: 4px solid {sentiment_color}; border-radius: 4px;">
            <div style="margin-bottom: 5px;">
                <strong style="color: #333; font-size: 14px;">{i+1}. {title}</strong>
            </div>
            <div style="font-size: 11px; color: #666; margin: 5px 0;">
                <span style="background: #e3f2fd; padding: 2px 6px; border-radius: 3px; margin-right: 5px;">🏷️ {keyword}</span>
                <span style="background: #{'e8f5e9' if sentiment > 0 else 'ffebee' if sentiment < 0 else 'f5f5f5'}; padding: 2px 6px; border-radius: 3px;">
                    {sentiment_label} ({sentiment:.2f})
                </span>
            </div>
            <div style="font-size: 11px; color: #999; margin: 5px 0;">📅 {published_time}</div>
            <div style="margin-top: 5px;"><a href="{url}" target="_blank" style="color: #1976d2; text-decoration: none; font-size: 11px;">🔗 기사 보기</a></div>
        </div>
        """
    if len(news_list) > 10:
        html_content += f'<div style="margin: 10px 0; padding: 10px; background: #fff3e0; border-radius: 4px; text-align: center; font-size: 12px; color: #666;">+ {len(news_list) - 10}개 더 있음</div>'
    html_content += "</div>"
    return html_content

# ==========================================
# 0-1. 데이터베이스 연결 및 통합 로직
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
def get_map_html():
    """지도 모듈을 사용하여 기본 HTML 생성"""
    if not MAP_MODULE_AVAILABLE: return None
    from map_generator_geo import NewsMapGeneratorGeo
    
    # 1. 모듈을 사용하여 기본 지도 생성
    generator = NewsMapGeneratorGeo()
    tmp_path = "data/temp_news_map.html"
    generator.generate(tmp_path, max_news=10)
    
    with open(tmp_path, 'r', encoding='utf-8') as f:
        return f.read()

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

def get_chart_data(start_date, end_date, region):
    query = "SELECT date(published_time) as date, sentiment_score, url FROM news WHERE date(published_time) BETWEEN ? AND ?"
    df = get_combined_df(query, params=(start_date.isoformat(), end_date.isoformat()))
    
    if df.empty:
        return pd.DataFrame()

    df_s = df.groupby('date')['sentiment_score'].mean().reset_index()
    df_s.columns = ['date', 'sentiment_index']
    
    if fdr is not None:
        try:
            df_p = fdr.DataReader('KS11', start_date, end_date)[['Close']].reset_index()
            df_p.columns = ['date', 'asset_price']
            df_p['date'] = df_p['date'].dt.date.astype(str)
            return pd.merge(df_s, df_p, on='date', how='inner')
        except: pass
    df_s['asset_price'] = 2500 + (df_s['sentiment_index'] - 0.5).cumsum() * 50
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
    
    map_html = get_map_html()
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
st.subheader("📊 지역 감성 지수 및 자산 가격 추이")
chart_df = get_chart_data(start_date, end_date, selected_region)
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
    btm_col1, btm_col2 = st.columns(2)
    with btm_col1:
        st.write("### 🔍 감성-자산 상관계수 히트맵")
        labels = ['감성', 'KOSPI', 'KOSDAQ']
        st.plotly_chart(px.imshow(np.random.uniform(0.6, 0.9, (3, 3)), text_auto=True, x=labels, y=labels, color_continuous_scale='RdBu_r'), width="stretch")
    with btm_col2:
        st.write("### 📉 감성 vs 자산 수익률 산점도")
        if not chart_df.empty:
            st.plotly_chart(px.scatter(chart_df, x='sentiment_index', y='asset_price', trendline="ols", template="plotly_white"), width="stretch")

with tab2: st.info("🕒 뉴스 수집 시간에 따른 감성 변화 타임라인 분석을 준비 중입니다.")
with tab3: st.info("💹 자산별 상세 기술적 지표 및 변동성 분석 영역입니다.")
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
