"""
Folium 지도 생성기 (GeoJSON 행정구역 경계선 버전) - 부정 비율 기준 업데이트
뉴스 데이터를 인터랙티브 지도에 시각화하며, 부정 기사 비율에 따라 색상을 결정합니다.
"""

import os
import json
import folium
from folium import IFrame, GeoJson
from folium.features import DivIcon
from typing import List, Dict
import html

from db_loader import NewsDBLoader
from region_coords import KOREA_CENTER, DEFAULT_ZOOM, REGION_COORDS
from color_mapper import get_sentiment_label, get_region_color_by_avg # color_mapper.py도 비율 기준으로 수정되어 있어야 함
from region_mapper import get_db_region


class NewsMapGeneratorGeo:
    """GeoJSON 기반 뉴스 지도 생성기 (부정 비율 기준)"""
    
    REGION_CONSOLIDATION = {
        '서울': ['서울'],
        '경기도': ['경기도', '인천'],
        '강원도': ['강원도'],
        '충청도': ['충청도'],
        '경상도': ['경상도', '경남', '경북'],
        '전라도': ['전라도', '전남']
    }

    ECON_KEYWORDS = [
        '경제', '증시', '주가', '코스피', '코스닥', '환율', '금리', '물가', '인플레이션',
        '금융', '은행', '대출', '채권', '시장', '투자', '기업', '산업', '경기', '성장',
        '수출', '수입', '무역', '부동산', '주택', '아파트', '매출', '실적', '영업이익',
        '적자', '흑자', '세금', '재정'
    ]
    
    def __init__(self, db_path: str = None, geojson_path: str = None):
        self.loader = NewsDBLoader(db_path)
        if geojson_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            geojson_path = os.path.join(os.path.dirname(current_dir), 'skorea-provinces-geo.json')
        
        self.geojson_path = geojson_path
        self.geojson_data = None
        self.map = None
        
    def load_geojson(self):
        try:
            with open(self.geojson_path, 'r', encoding='utf-8') as f:
                self.geojson_data = json.load(f)
            return True
        except Exception as e:
            print(f"❌ GeoJSON 로드 실패: {e}")
            return False
    
    def create_map(self):
        self.map = folium.Map(
            location=KOREA_CENTER,
            zoom_start=DEFAULT_ZOOM,
            tiles='OpenStreetMap',
            control_scale=True
        )
        return self.map
    
    def get_region_statistics(self):
        """부정 기사 비율(%)을 포함한 통계 계산"""
        db_stats = self.loader.get_region_stats()
        consolidated_stats = {}
        
        for main_region, db_regions in self.REGION_CONSOLIDATION.items():
            total_count = 0
            total_positive = 0
            total_negative = 0
            
            for db_region in db_regions:
                if db_region in db_stats:
                    stat = db_stats[db_region]
                    total_count += stat['count']
                    total_positive += stat['positive_count']
                    total_negative += stat['negative_count']
            
            # 부정 기사 비율 계산 (%)
            neg_ratio = (total_negative / total_count * 100) if total_count > 0 else 0.0
            
            consolidated_stats[main_region] = {
                'count': total_count,
                'neg_ratio': neg_ratio,
                'positive_count': total_positive,
                'negative_count': total_negative
            }
        return consolidated_stats

    def _split_keywords(self, keyword_text: str) -> List[str]:
        if not keyword_text: return []
        separators = [',', '|', '/', ';']
        normalized = keyword_text
        for sep in separators: normalized = normalized.replace(sep, ',')
        raw_tokens = [token.strip() for token in normalized.replace('\n', ',').split(',')]
        tokens = []
        for token in raw_tokens:
            if not token: continue
            for sub in token.split():
                sub = sub.strip()
                if sub: tokens.append(sub)
        return tokens

    def _is_economic_keyword(self, token: str) -> bool:
        return any(econ in token for econ in self.ECON_KEYWORDS)

    def create_popup_html(self, db_region: str, stat: Dict, max_news: int = 5):
        """첫 번째 사진의 가로형 UI를 유지한 팝업 HTML"""
        news_list = self.loader.get_latest_news_by_region(db_region, limit=max_news)
        
        # 부정 비율에 따른 텍스트 색상 결정
        ratio_color = '#f44336' if stat['neg_ratio'] > 51 else '#2196F3' if stat['neg_ratio'] < 50 else '#666'
        
        html_content = f"""
        <div style="width: 700px; padding: 15px; font-family: 'Malgun Gothic', sans-serif; box-sizing: border-box;">
            <h3 style="margin-top: 0; margin-bottom: 10px; color: #fff; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                       padding: 12px 15px; border-radius: 5px; text-align: center;">
                📍 {db_region} 지역 뉴스
            </h3>
            
            <div style="background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); padding: 12px; margin-bottom: 15px; 
                        border-radius: 5px; display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; text-align: center;">
                <div>
                    <div style="font-size: 0.8em; color: #666; font-weight: bold;">📰 뉴스</div>
                    <div style="font-size: 1.3em; color: #2196F3; font-weight: bold;">{stat['count']}개</div>
                </div>
                <div>
                    <div style="font-size: 0.8em; color: #666; font-weight: bold;">😊 긍정</div>
                    <div style="font-size: 1.3em; color: #4CAF50; font-weight: bold;">{stat['positive_count']}개</div>
                </div>
                <div>
                    <div style="font-size: 0.8em; color: #666; font-weight: bold;">😔 부정</div>
                    <div style="font-size: 1.3em; color: #f44336; font-weight: bold;">{stat['negative_count']}개</div>
                </div>
            </div>
            
            <div style="background-color: #f0f4f8; padding: 10px; margin-bottom: 15px; border-left: 4px solid #667eea; border-radius: 3px;">
                <span style="font-size: 0.9em; color: #666;">부정 기사 비율: </span>
                <span style="font-weight: bold; font-size: 1.1em; color: {ratio_color};">
                    {stat['neg_ratio']:.1f}%
                </span>
                <span style="font-size: 0.85em; color: #999;">({'부정 위험' if stat['neg_ratio'] > 51 else '긍정 우세' if stat['neg_ratio'] < 50 else '중립'})</span>
            </div>
            
            <div style="border-top: 2px solid #ddd; padding-top: 10px;">
                <h4 style="margin: 10px 0; color: #333; font-size: 0.95em;">📋 뉴스 목록</h4>
                <div style="max-height: 350px; overflow-y: auto;">
        """
        
        for news in news_list:
            title = html.escape(news.get('title', '제목 없음'))
            sentiment = news.get('sentiment_score') or 0.0
            url = news.get('url', '#')
            
            s_color = '#0D47A1' if sentiment > 0.5 else '#81C784' if sentiment > 0 else '#B71C1C' if sentiment < -0.5 else '#f44336' if sentiment < 0 else '#9E9E9E'
            s_emoji = '😊😊' if sentiment > 0.5 else '😊' if sentiment > 0 else '😔😔' if sentiment < -0.5 else '😔' if sentiment < 0 else '😐'

            html_content += f"""
            <div style="margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid #eee;">
                <div style="margin-bottom: 6px;">
                    <span style="color: #1976D2; font-size: 0.9em; font-weight: 500;">
                        • <a href="{url}" target="_blank" style="color: #1976D2; text-decoration: none;">{title}</a>
                    </span>
                </div>
                <div style="font-size: 0.8em; margin-left: 12px;">
                    <span style="background-color: {s_color}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.85em;">
                        {s_emoji} {sentiment:+.2f}
                    </span>
                </div>
            </div>
            """
        
        html_content += """</div></div></div>"""
        return html_content

    def add_region_labels(self):
        """지역명 라벨 세로 출력 방지 스타일 적용"""
        for region, coord in REGION_COORDS.items():
            label_html = f"""
            <div style="font-size: 14px; font-weight: 800; color: #000; white-space: nowrap;
                        text-shadow: -1px -1px 0 #FFF, 1px -1px 0 #FFF, -1px 1px 0 #FFF, 1px 1px 0 #FFF;
                        pointer-events: none; display: block; width: auto;">
                {region}
            </div>
            """
            folium.Marker(
                location=coord,
                icon=DivIcon(html=label_html, icon_size=(100, 20), icon_anchor=(50, 10)),
                interactive=False
            ).add_to(self.map)
    
    def add_geojson_layer(self, max_news: int = 10):
        if not self.geojson_data: return
        
        region_stats = self.get_region_statistics()
        EXCLUDED_REGIONS = ['Jeju', 'Dokdo', 'Ulleung-gun']
        
        for feature in self.geojson_data['features']:
            geojson_region = feature['properties'].get('NAME_1')
            if geojson_region in EXCLUDED_REGIONS: continue
            
            db_region = get_db_region(geojson_region)
            stat = region_stats.get(db_region, {'count': 0, 'neg_ratio': 0, 'positive_count': 0, 'negative_count': 0})
            
            # 색상 결정 (부정 비율 기준)
            if stat['count'] == 0:
                fill_color = '#CCCCCC'
            else:
                fill_color = get_region_color_by_avg(stat['neg_ratio']) # 비율 인자 전달
            
            feature_collection = {'type': 'FeatureCollection', 'features': [feature]}
            
            style_fn = lambda x, c=fill_color: {'fillColor': c, 'fillOpacity': 0.6, 'color': '#333', 'weight': 1.5}
            highlight_fn = lambda x: {'fillOpacity': 0.8, 'weight': 3, 'color': '#FF5722'}
            
            popup_html = self.create_popup_html(db_region, stat, max_news) if db_region and stat['count'] > 0 else f"<div style='padding:10px;'><b>{geojson_region}</b><br/>데이터 없음</div>"
            popup = folium.Popup(IFrame(html=popup_html, width=730, height=500), max_width=750)
            
            GeoJson(
                feature_collection,
                style_function=style_fn,
                highlight_function=highlight_fn,
                popup=popup
            ).add_to(self.map)
    
    def add_legend(self):
        """부정 비율 기준으로 범례 수정"""
        legend_html = '''
        <div style="position: fixed; bottom: 50px; right: 50px; width: 220px; 
                    background-color: white; border: 2px solid grey; border-radius: 5px;
                    z-index: 9999; font-size: 14px; padding: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.3);">
            <p style="margin: 0 0 10px 0; font-weight: bold; font-size: 16px;">🚩 부정 기사 비율 기준</p>
            <p style="margin: 5px 0;"><span style="background-color: #FF0000; width: 20px; height: 15px; display: inline-block; margin-right: 5px;"></span>부정 위험 (51% 초과)</p>
            <p style="margin: 5px 0;"><span style="background-color: #FFFFFF; border: 1px solid #ccc; width: 20px; height: 15px; display: inline-block; margin-right: 5px;"></span>중립 지역 (50% ~ 51%)</p>
            <p style="margin: 5px 0;"><span style="background-color: #0000FF; width: 20px; height: 15px; display: inline-block; margin-right: 5px;"></span>긍정 우세 (50% 미만)</p>
            <p style="margin: 5px 0;"><span style="background-color: #CCCCCC; width: 20px; height: 15px; display: inline-block; margin-right: 5px;"></span>데이터 부족</p>
        </div>
        '''
        self.map.get_root().html.add_child(folium.Element(legend_html))
    
    def generate(self, output_file: str = 'news_map_geo.html', max_news: int = 10):
        self.load_geojson()
        self.create_map()
        self.add_geojson_layer(max_news=max_news)
        self.add_region_labels()
        self.add_legend()
        self.map.save(output_file)
        self.add_side_panel_with_events(output_file)

    def add_side_panel_with_events(self, html_file: str):
        """사이드 패널(키워드 창) 복구 및 마우스 이벤트 로직"""
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        stats = self.get_region_statistics()
        region_data = {}
        for main_region in self.REGION_CONSOLIDATION.keys():
            if main_region in stats and stats[main_region]['count'] > 0:
                latest_news = self.loader.get_latest_news_by_region(main_region, limit=5)
                news_items = []
                for news in latest_news:
                    economic_keywords = []
                    k_str = news.get('keyword', '-')
                    if k_str and k_str != '-':
                        for token in self._split_keywords(k_str):
                            if self._is_economic_keyword(token) and len(economic_keywords) < 5:
                                economic_keywords.append(token)
                    news_items.append({'title': news.get('title', '제목 없음'), 'keywords': economic_keywords})
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
        
        <div id="info-panel">
            <h3>📍 강원도 주요 뉴스 & 키워드</h3>
            <p style="color: #999; font-size: 12px;">지역을 선택하면 상세 키워드가 표시됩니다.</p>
        </div>
        
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
                        }}
                    }});
                }}
            }};
        </script>
        """
        html_content = html_content.replace('</body>', custom_code + '</body>')
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)


if __name__ == '__main__':
    generator = NewsMapGeneratorGeo()
    generator.generate('news_map_geo.html', max_news=10)