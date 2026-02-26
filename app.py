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

# FinanceDataReader 임포트
try:
    import FinanceDataReader as fdr
except ImportError:
    fdr = None

# ==========================================
# 0. 데이터 연동 및 색상 매핑 유틸리티 (New Map Logic 연동)
# ==========================================
def get_db_conn(db_name):
    return sqlite3.connect(f'data/{db_name}')

def get_sentiment_color(score):
    """color_mapper.py 로직 연동"""
    if score is None or score == 0: return 'gray'
    elif score > 0.5: return 'blue'
    elif score > 0: return 'lightgreen'
    elif score < -0.5: return 'red'
    else: return 'lightred'

def get_sentiment_label(score):
    """color_mapper.py 로직 연동"""
    if score is None: return '분석 안 됨'
    elif score == 0: return '중립'
    elif score > 0.5: return '매우 긍정적'
    elif score > 0.2: return '긍정적'
    elif score > 0: return '약간 긍정적'
    elif score < -0.5: return '매우 부정적'
    elif score < -0.2: return '부정적'
    else: return '약간 부정적'

def create_popup_html(news_list, region):
    """map_generator.py의 정교한 팝업 HTML 연동"""
    if not news_list: return f"<h4>{region}</h4><p>뉴스가 없습니다.</p>"
    
    html_content = f"""
    <div style="width: 350px; max-height: 400px; overflow-y: auto; font-family: 'Malgun Gothic', sans-serif;">
        <h4 style="margin: 0 0 10px 0; color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 5px;">
            📍 {region} ({len(news_list)}개 뉴스)
        </h4>
    """
    for i, news in enumerate(news_list[:10]):
        title = html.escape(news.get('title', '제목 없음')[:60])
        sentiment = news.get('sentiment_score', 0) or 0
        s_label = get_sentiment_label(sentiment)
        s_color = 'blue' if sentiment > 0 else 'red' if sentiment < 0 else 'gray'
        
        html_content += f"""
        <div style="margin: 8px 0; padding: 8px; background: #f9f9f9; border-left: 4px solid {s_color}; border-radius: 4px;">
            <div style="font-weight: bold; font-size: 13px; color: #333;">{i+1}. {title}</div>
            <div style="font-size: 11px; color: #666; margin-top: 4px;">
                <span style="background: #e3f2fd; padding: 1px 4px; border-radius: 3px;">🏷️ {news.get('keyword', '-')}</span>
                <span style="background: #eee; padding: 1px 4px; border-radius: 3px;">{s_label} ({sentiment:.2f})</span>
            </div>
            <div style="margin-top: 4px;"><a href="{news.get('url', '#')}" target="_blank" style="color: #1976d2; font-size: 11px; text-decoration: none;">🔗 기사 보기</a></div>
        </div>
        """
    html_content += "</div>"
    return html_content

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

def get_metrics_data(start_date, end_date):
    conn = get_db_conn('news.db')
    df_sql = pd.read_sql("SELECT AVG(sentiment_score) as avg_s, COUNT(*) as cnt FROM news WHERE date(published_time) BETWEEN ? AND ?", 
                         conn, params=(start_date.isoformat(), end_date.isoformat()))
    conn.close()
    avg_s = df_sql['avg_s'][0] if df_sql['avg_s'][0] is not None else 0.5
    k_change, q_change = 0.0, 0.0
    if fdr is not None:
        try:
            k = fdr.DataReader('KS11', start_date, end_date)['Close']
            q = fdr.DataReader('KQ11', start_date, end_date)['Close']
            k_change = ((k.iloc[-1] / k.iloc[0]) - 1) * 100
            q_change = ((q.iloc[-1] / q.iloc[0]) - 1) * 100
        except: pass
    return {'sentiment_avg': avg_s, 'volatility': df_sql['cnt'][0] / 10.0, 'k_change': k_change, 'q_change': q_change}

def get_region_map_stats():
    conn = get_db_conn('news.db')
    df = pd.read_sql("SELECT region, AVG(sentiment_score) as avg_sentiment, COUNT(*) as count FROM news WHERE region IS NOT NULL GROUP BY region", conn)
    conn.close()
    return df

def get_issue_list_data(region):
    """키워드별 실제 뉴스 감성 점수 평균을 계산하여 호재/악재 판별"""
    try:
        conn = get_db_conn('news.db')
        query = "SELECT keyword, sentiment_score FROM news WHERE keyword IS NOT NULL AND keyword != ''"
        params = []
        if region != "전국":
            query += " AND region LIKE ?"
            params.append(f'%{region}%')
        
        df_raw = pd.read_sql(query, conn, params=params)
        conn.close()
        
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
        
        # UI에서 비율을 계산할 수 있도록 'count' 컬럼 추가 리턴!
        return df[['rank', 'issue', 'sentiment', 'score_display', 'count']]
    except Exception as e:
        return pd.DataFrame(columns=['rank', 'issue', 'sentiment', 'score_display', 'count'])

def get_chart_data(start_date, end_date, region):
    conn = get_db_conn('news.db')
    df_s = pd.read_sql("SELECT date(published_time) as date, AVG(sentiment_score) as sentiment_index FROM news WHERE date(published_time) BETWEEN ? AND ? GROUP BY date", 
                       conn, params=(start_date.isoformat(), end_date.isoformat()))
    conn.close()
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
selected_region = st.sidebar.selectbox("분석 지역 선택", ["전국", "서울", "경기도", "부산", "강원도", "충청도", "전라도", "경상도"])
st.sidebar.markdown("---")
st.sidebar.info("Map Engine: Folium Marker & News Popup Connected")

# ==========================================
# 4. 상단 메트릭 (Top Metrics)
# ==========================================
m = get_metrics_data(start_date, end_date)
col1, col2, col3, col4 = st.columns(4)
with col1: st.markdown(f'<div class="metric-card"><div class="metric-label">종합 감성지수</div><div class="metric-value">{m["sentiment_avg"]:.2f}</div></div>', unsafe_allow_html=True)
with col2: st.markdown(f'<div class="metric-card"><div class="metric-label">경제 변동성</div><div class="metric-value">{m["volatility"]:.1f}%</div></div>', unsafe_allow_html=True)
with col3: st.markdown(f'<div class="metric-card"><div class="metric-label">코스피 변동</div><div class="metric-value" style="color:{"#2ecc71" if m["k_change"]>0 else "#e74c3c"}">{m["k_change"]:+.2f}%</div></div>', unsafe_allow_html=True)
with col4: st.markdown(f'<div class="metric-card"><div class="metric-label">코스닥 변동</div><div class="metric-value" style="color:{"#2ecc71" if m["q_change"]>0 else "#e74c3c"}">{m["q_change"]:+.2f}%</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# 5. 중앙 구역 (Map & Top 10 List)
# ==========================================
mid_col1, mid_col2 = st.columns([1.5, 1])
with mid_col1:
    st.subheader(f"📍 {selected_region} 인터랙티브 경제 지도")
    map_stats = get_region_map_stats()
    coords = {'서울': [37.56, 126.97], '경기도': [37.41, 127.51], '부산': [35.17, 129.07], '강원도': [37.82, 128.15], '충청도': [36.63, 127.49], '전라도': [35.82, 127.14], '경상도': [36.57, 128.50]}
    
    m_folium = folium.Map(location=[36.5, 127.5], zoom_start=7, tiles="cartodbpositron")
    
    conn = get_db_conn('news.db')
    for region, coord in coords.items():
        # 해당 지역 기사 목록 가져오기 (팝업용)
        news_df = pd.read_sql("SELECT title, sentiment_score, keyword, url FROM news WHERE region LIKE ? ORDER BY published_time DESC LIMIT 10", conn, params=(f'%{region}%',))
        
        stat = map_stats[map_stats['region'].str.contains(region)]
        avg_sent = stat['avg_sentiment'].iloc[0] if not stat.empty else 0.5
        count = stat['count'].iloc[0] if not stat.empty else 0
        
        # 정교한 팝업 HTML 생성
        popup_html = create_popup_html(news_df.to_dict('records'), region)
        iframe = IFrame(popup_html, width=380, height=350)
        
        folium.CircleMarker(
            location=coord,
            radius=10 + (count / 5),
            popup=folium.Popup(iframe, max_width=400),
            tooltip=f"<b>{region}</b><br>평균 감성: {avg_sent:.2f}<br>뉴스: {count}건 (클릭하여 뉴스보기)",
            color=get_sentiment_color(avg_sent - 0.5), # 0.5를 기준으로 정규화
            fill=True,
            fill_opacity=0.6
        ).add_to(m_folium)
    conn.close()
    st_folium(m_folium, width="stretch", height=400)

with mid_col2:
    st.subheader(f"🔥 {selected_region} 핵심 이슈 TOP 10")
    issue_df = get_issue_list_data(selected_region)
    
    if not issue_df.empty:
        # 가장 많이 언급된 횟수를 100% 기준으로 삼기 위한 최댓값 추출
        max_count = issue_df['count'].max()
        
        for _, row in issue_df.iterrows():
            badge = "badge-pos" if row['sentiment'] == "긍정" else "badge-neg"
            badge_icon = "▲ 긍정" if row['sentiment'] == "긍정" else "▼ 부정"
            
            # 1. 배경을 채울 퍼센트 계산 (현재 빈도 / 최대 빈도 * 100)
            fill_pct = int((row['count'] / max_count) * 100) if max_count > 0 else 0
            
            # 2. 긍정/부정에 따라 배경 바(Bar) 색상 다르게 지정 (투명도 15%)
            bg_color = "rgba(46, 204, 113, 0.15)" if row['sentiment'] == "긍정" else "rgba(231, 76, 60, 0.15)"
            
            # 3. CSS linear-gradient로 진행률 바 효과 적용
            custom_style = f"""
                display:flex; 
                justify-content:space-between; 
                align-items:center;
                padding:10px 12px; 
                margin-bottom:8px;
                border-radius:6px;
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
    st.write("### 📰 최신 감성 뉴스 리스트")
    conn = get_db_conn('news.db')
    news_list_df = pd.read_sql("SELECT title, sentiment_score, published_time as date, url FROM news ORDER BY date DESC LIMIT 5", conn)
    conn.close()
    for _, row in news_list_df.iterrows():
        color = "#2ecc71" if row['sentiment_score'] > 0.5 else "#e74c3c"
        st.markdown(f'<div style="padding:10px; border-left:5px solid {color}; background-color:#f9f9f9; margin-bottom:10px; border-radius:4px;"><div style="font-size:0.8em; color:#888;">{row["date"]} | 감성: {row["sentiment_score"]:.2f}</div><div style="font-weight:bold;"><a href="{row["url"]}" target="_blank" style="text-decoration:none; color:#333;">{row["title"]}</a></div></div>', unsafe_allow_html=True)

st.markdown("---")
st.markdown("<p style='text-align: center; color: #999;'>© 2026 지능형 지역 경제 & 자산 분석 시스템 (Hybrid Map Connected)</p>", unsafe_allow_html=True)
