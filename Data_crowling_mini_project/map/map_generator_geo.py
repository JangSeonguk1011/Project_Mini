import os
import json
import folium
import sqlite3
import pandas as pd
from folium import IFrame, GeoJson
from folium.features import DivIcon
from typing import List, Dict
import html

# 기존 유틸리티 임포트
from region_coords import KOREA_CENTER, DEFAULT_ZOOM, REGION_COORDS
from color_mapper import get_sentiment_label, get_region_color_by_avg 
from region_mapper import get_db_region

class NewsMapGeneratorGeo:
    """GeoJSON 기반 뉴스 지도 생성기 (DB 통합 & 사이드 패널 소스코드 반영)"""
    
    REGION_CONSOLIDATION = {
        '서울': ['서울'],
        '경기도': ['경기도', '인천'],
        '강원도': ['강원도'],
        '충청도': ['충청도', '대전', '세종'],
        '경상도': ['경상도', '경남', '경북', '부산', '대구', '울산'],
        '전라도': ['전라도', '전남', '전북', '광주']
    }

    def __init__(self, geojson_path: str = None):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        
        # DB 경로 설정
        self.db_main = os.path.join(project_root, 'data', 'news.db')
        self.db_scraped = os.path.join(project_root, 'data', 'news_scraped.db')
        
        self.geojson_path = geojson_path or os.path.join(project_root, 'skorea-provinces-geo.json')
        self.geojson_data = None
        self.map = None

    def _get_integrated_conn(self):
        """news.db와 news_scraped.db 통합 연결"""
        conn = sqlite3.connect(self.db_main)
        cursor = conn.cursor()
        if os.path.exists(self.db_scraped):
            cursor.execute(f"ATTACH DATABASE '{self.db_scraped}' AS scraped")
        return conn

    def get_region_statistics(self, start_date, end_date):
        # 날짜를 문자열로 변환 (YYYY-MM-DD)
        if hasattr(start_date, 'strftime'):
            start_date = start_date.strftime('%Y-%m-%d')
        if hasattr(end_date, 'strftime'):
            end_date = end_date.strftime('%Y-%m-%d')
        """통합 DB에서 지역별 통계 추출"""
        conn = self._get_integrated_conn()
        cursor = conn.cursor()
        cursor.execute("PRAGMA database_list")
        databases = [row[1] for row in cursor.fetchall()]
        
        subquery = "SELECT region, sentiment_score, published_time FROM main.news"
        if 'scraped' in databases:
            subquery += " UNION ALL SELECT region, sentiment_score, published_time FROM scraped.news"
        query = f'''
        SELECT region, COUNT(*) as count,
               SUM(CASE WHEN sentiment_score > 0 THEN 1 ELSE 0 END) as positive_count,
               SUM(CASE WHEN sentiment_score < 0 THEN 1 ELSE 0 END) as negative_count
        FROM ({subquery})
        WHERE DATE(published_time) BETWEEN ? AND ?
        GROUP BY region
        '''
        db_stats_df = pd.read_sql_query(query, conn, params=(start_date, end_date))
        conn.close()
        
        db_stats = db_stats_df.set_index('region').to_dict('index')
        consolidated_stats = {}
        
        for main_reg, sub_regs in self.REGION_CONSOLIDATION.items():
            t_cnt = t_pos = t_neg = 0
            for r in sub_regs:
                if r in db_stats:
                    s = db_stats[r]
                    t_cnt += s['count']; t_pos += s['positive_count']; t_neg += s['negative_count']
            
            consolidated_stats[main_reg] = {
                'count': t_cnt, 'neg_ratio': (t_neg / t_cnt * 100) if t_cnt > 0 else 0.0,
                'positive_count': t_pos, 'negative_count': t_neg
            }
        return consolidated_stats

    def get_latest_news_integrated(self, db_region: str, start_date, end_date, limit: int = 5):
        # 날짜를 문자열로 변환 (YYYY-MM-DD)
        if hasattr(start_date, 'strftime'):
            start_date = start_date.strftime('%Y-%m-%d')
        if hasattr(end_date, 'strftime'):
            end_date = end_date.strftime('%Y-%m-%d')
        """[rowid 에러 해결] 통합 DB에서 최신 뉴스 리스트 추출"""
        conn = self._get_integrated_conn()
        cursor = conn.cursor()
        cursor.execute("PRAGMA database_list")
        databases = [row[1] for row in cursor.fetchall()]
        
        sub_regions = self.REGION_CONSOLIDATION.get(db_region, [db_region])
        placeholders = ', '.join(['?'] * len(sub_regions))
        
        subquery = "SELECT title, sentiment_score, url, keyword, region, published_time FROM main.news"
        if 'scraped' in databases:
            subquery += " UNION ALL SELECT title, sentiment_score, url, keyword, region, published_time FROM scraped.news"
        query = f'''
        SELECT title, sentiment_score, url, keyword, published_time FROM ({subquery})
        WHERE region IN ({placeholders}) AND DATE(published_time) BETWEEN ? AND ?
        LIMIT ?
        '''
        df = pd.read_sql_query(query, conn, params=(*sub_regions, start_date, end_date, limit))
        conn.close()
        return df.to_dict('records')

    def create_popup_html(self, db_region: str, stat: Dict, start_date, end_date, max_news: int = 5):
        """가로형 3열 UI 팝업"""
        news_list = self.get_latest_news_integrated(db_region, start_date, end_date, limit=max_news)
        ratio_color = '#f44336' if stat['neg_ratio'] > 51 else '#2196F3'
        
        html_content = f"""
        <div style="width: 700px; padding: 15px; font-family: 'Malgun Gothic', sans-serif;">
            <h3 style="margin-bottom: 10px; color: #fff; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                       padding: 12px; border-radius: 5px; text-align: center;">📍 {db_region} 지역 뉴스</h3>
            <div style="background: #f8f9fa; padding: 15px; margin-bottom: 15px; border-radius: 5px; 
                        display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; text-align: center; border: 1px solid #ddd;">
                <div><div style="color: #666; font-size: 0.9em;">📰 뉴스</div><div style="font-size: 1.4em; color: #2196F3; font-weight: bold;">{stat['count']}개</div></div>
                <div><div style="color: #666; font-size: 0.9em;">😊 긍정</div><div style="font-size: 1.4em; color: #4CAF50; font-weight: bold;">{stat['positive_count']}개</div></div>
                <div><div style="color: #666; font-size: 0.9em;">😔 부정</div><div style="font-size: 1.4em; color: #f44336; font-weight: bold;">{stat['negative_count']}개</div></div>
            </div>
            <div style="margin-bottom: 15px; padding: 10px; background: #fff; border-left: 5px solid {ratio_color};">
                부정 기사 비율: <b style="color: {ratio_color};">{stat['neg_ratio']:.1f}%</b> ({'부정 위험' if stat['neg_ratio'] > 51 else '긍정 우세'})
            </div>
            <div style="max-height: 300px; overflow-y: auto;">
        """
        for news in news_list:
            s_val = news['sentiment_score'] or 0.0
            s_color = '#2196F3' if s_val > 0 else '#f44336'
            html_content += f"""
            <div style="margin-bottom: 10px; border-bottom: 1px solid #eee; padding-bottom: 5px;">
                <a href="{news['url']}" target="_blank" style="text-decoration: none; color: #333; font-size: 0.95em;">• {html.escape(news['title'])}</a>
                <div style="margin-top: 4px;"><span style="background: {s_color}; color: white; padding: 2px 6px; border-radius: 10px; font-size: 0.8em;">{s_val:+.2f}</span></div>
            </div>"""
        return html_content + "</div></div>"

    def add_region_labels(self):
        """지역명 가로 출력 고정"""
        for region, coord in REGION_COORDS.items():
            label_html = f'<div style="font-size: 13pt; font-weight: bold; color: black; white-space: nowrap; text-shadow: 2px 2px 2px white;">{region}</div>'
            folium.Marker(location=coord, icon=DivIcon(html=label_html, icon_size=(100, 20), icon_anchor=(50, 10)), interactive=False).add_to(self.map)

    def _split_keywords(self, text):
        if not text: return []
        return [t.strip() for t in text.replace('|', ',').split(',') if t.strip()]

    def add_legend(self):
        legend_html = '''
        <div style="position: fixed; bottom: 50px; right: 50px; width: 200px; background: white; border: 2px solid grey; z-index: 9999; padding: 10px; border-radius: 5px;">
            <p style="margin:0;"><b>🚩 부정 기사 비율</b></p>
            <p style="margin:5px 0;"><span style="background: red; width: 20px; height: 12px; display: inline-block;"></span> 위험 (51%+)</p>
            <p style="margin:5px 0;"><span style="background: blue; width: 20px; height: 12px; display: inline-block;"></span> 우세 (50%-)</p>
        </div>'''
        self.map.get_root().html.add_child(folium.Element(legend_html))

    def generate(self, start_date, end_date, output_file: str = 'news_map_geo.html'):
        with open(self.geojson_path, 'r', encoding='utf-8') as f:
            self.geojson_data = json.load(f)
        
        self.map = folium.Map(location=KOREA_CENTER, zoom_start=DEFAULT_ZOOM, tiles='OpenStreetMap')
        stats = self.get_region_statistics(start_date, end_date)
        
        for feature in self.geojson_data['features']:
            name = feature['properties'].get('NAME_1')
            if name in ['Jeju', 'Dokdo', 'Ulleung-gun']: continue
            db_region = get_db_region(name)
            stat = stats.get(db_region, {'count': 0, 'neg_ratio': 0, 'positive_count': 0, 'negative_count': 0})
            
            color = get_region_color_by_avg(stat['neg_ratio']) if stat['count'] > 0 else '#CCCCCC'
            popup_html = self.create_popup_html(db_region, stat, start_date, end_date)
            
            folium.GeoJson(
                feature, 
                style_function=lambda x, c=color: {'fillColor': c, 'fillOpacity': 0.6, 'color': 'black', 'weight': 1.2},
                popup=folium.Popup(IFrame(popup_html, width=730, height=520), max_width=750)
            ).add_to(self.map)

        self.add_region_labels()
        self.add_legend()
        self.map.save(output_file)
        self.add_side_panel_with_events(output_file, start_date, end_date)
        print(f"✅ 통합 완료: {os.path.abspath(output_file)}")

    # --- 요청하신 사이드 패널 소스코드 삽입 (통합 DB 리스트 연결 수정) ---
    def add_side_panel_with_events(self, html_file: str, start_date=None, end_date=None):
        """사이드 패널(키워드 창) 복구 및 마우스 이벤트 로직"""
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        stats = self.get_region_statistics(start_date, end_date)
        region_data = {}
        for main_region in self.REGION_CONSOLIDATION.keys():
            if main_region in stats and stats[main_region]['count'] > 0:
                # [수정] loader 대신 클래스 내 통합 뉴스 메서드 사용
                latest_news = self.get_latest_news_integrated(main_region, start_date, end_date, limit=5)
                news_items = []
                for news in latest_news:
                    keywords = []
                    k_str = news.get('keyword', '-')
                    if k_str and k_str != '-':
                        for token in self._split_keywords(k_str):
                            if len(keywords) < 5:
                                keywords.append(token)
                    news_items.append({'title': news.get('title', '제목 없음'), 'keywords': keywords})
                region_data[main_region] = news_items
        
        region_data_json = json.dumps(region_data, ensure_ascii=False)
        
        custom_code = f"""
        <style>
            #map {{ margin-right: 450px !important; }}
            #info-panel {{
                position: fixed; right: 20px; top: 80px; width: 420px;
                max-height: 85vh; overflow-y: auto; background: white;
                border: 2px solid #E91E63; border-radius: 8px; padding: 15px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.2); z-index: 1000;
                font-family: 'Malgun Gothic', sans-serif;
            }}
            #info-panel h3 {{ margin: 0 0 12px 0; color: #E91E63; border-bottom: 2px solid #E91E63; padding-bottom: 6px; font-size: 16px; }}
            .news-item {{ margin-bottom: 12px; padding-left: 10px; border-left: 3px solid #E91E63; }}
            .news-title {{ font-weight: bold; color: #333; font-size: 13px; line-height: 1.4; }}
            .news-keywords {{ font-size: 11px; color: #1976D2; margin-top: 4px; }}
        </style>
        
        <script>
            var regionNewsData = {region_data_json};
            var regionMapping = {{
                'Seoul': '서울', 'Gyeonggi-do': '경기도', 'Incheon': '경기도',
                'Gangwon-do': '강원도', 'Chungcheongnam-do': '충청도', 'Chungcheongbuk-do': '충청도',
                'Daejeon': '충청도', 'Gyeongsangnam-do': '경상도', 'Gyeongsangbuk-do': '경상도',
                'Busan': '경상도', 'Daegu': '경상도', 'Ulsan': '경상도',
                'Jeollanam-do': '전라도', 'Jeollabuk-do': '전라도', 'Gwangju': '전라도'
            }};

            function updatePanel(name) {{
                var dbName = regionMapping[name];
                var data = regionNewsData[dbName];
                var panel = document.getElementById('info-panel');
                if(!data) return;
                
                var html = '<h3>📍 ' + dbName + ' 주요 뉴스 & 키워드</h3>';
                data.forEach(function(item) {{
                    html += '<div class="news-item">';
                    html += '<div class="news-title">• ' + item.title + '</div>';
                    html += '<div class="news-keywords">🔍 키워드: ' + item.keywords.join(', ') + '</div>';
                    html += '</div>';
                }});
                panel.innerHTML = html;
                panel.style.display = 'block';
            }}

            window.onload = function() {{
                var mapElements = document.getElementsByClassName('folium-map');
                if (mapElements.length > 0) {{
                    var mapId = mapElements[0].id;
                    var mapInstance = window[mapId];
                    
                    mapInstance.eachLayer(function(layer) {{
                        if (layer.feature) {{
                            layer.on('mouseover', function(e) {{
                                updatePanel(e.target.feature.properties.NAME_1);
                            }});
                            layer.on('mouseout', function(e) {{
                                document.getElementById('info-panel').style.display = 'none';
                            }});
                        }}
                    }});
                }}
            }};
        </script>
        <div id="info-panel" style="display:none;"></div>
        """
        html_content = html_content.replace('</body>', custom_code + '</body>')
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

if __name__ == '__main__':
    generator = NewsMapGeneratorGeo()
    generator.generate()