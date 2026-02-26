"""
Folium 지도 생성기 (GeoJSON 행정구역 경계선 버전)
뉴스 데이터를 인터랙티브 지도에 시각화하며, 실제 행정구역 경계선을 표시합니다
"""

import os
import json
import folium
from folium import IFrame, GeoJson, GeoJsonTooltip, GeoJsonPopup
from folium.features import DivIcon
from typing import List, Dict
import html

from db_loader import NewsDBLoader
from region_coords import KOREA_CENTER, DEFAULT_ZOOM, REGION_COORDS
from color_mapper import get_sentiment_label, get_region_color_by_avg
from region_mapper import get_geojson_regions, get_db_region


class NewsMapGeneratorGeo:
    """GeoJSON 기반 뉴스 지도 생성기"""
    
    # DB 지역들을 6개 주요 지역으로 통합하는 매핑
    REGION_CONSOLIDATION = {
        '서울': ['서울'],
        '경기도': ['경기도', '인천'],
        '강원도': ['강원도'],
        '충청도': ['충청도'],
        '경상도': ['경상도', '경남', '경북'],
        '전라도': ['전라도', '전남']
    }

    # 경제 관련 키워드 목록
    ECON_KEYWORDS = [
        '경제', '증시', '주가', '코스피', '코스닥', '환율', '금리', '물가', '인플레이션',
        '금융', '은행', '대출', '채권', '시장', '투자', '기업', '산업', '경기', '성장',
        '수출', '수입', '무역', '부동산', '주택', '아파트', '매출', '실적', '영업이익',
        '적자', '흑자', '세금', '재정'
    ]
    
    def __init__(self, db_path: str = None, geojson_path: str = None):
        """
        Args:
            db_path: 데이터베이스 경로
            geojson_path: GeoJSON 파일 경로
        """
        self.loader = NewsDBLoader(db_path)
        
        # GeoJSON 파일 경로 설정
        if geojson_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            geojson_path = os.path.join(os.path.dirname(current_dir), 'skorea-provinces-geo.json')
        
        self.geojson_path = geojson_path
        self.geojson_data = None
        self.map = None
        
    def load_geojson(self):
        """GeoJSON 파일 로드"""
        try:
            with open(self.geojson_path, 'r', encoding='utf-8') as f:
                self.geojson_data = json.load(f)
            print(f"✅ GeoJSON 로드 완료: {len(self.geojson_data.get('features', []))}개 지역")
            return True
        except Exception as e:
            print(f"❌ GeoJSON 로드 실패: {e}")
            return False
    
    def create_map(self):
        """기본 지도 생성"""
        self.map = folium.Map(
            location=KOREA_CENTER,
            zoom_start=DEFAULT_ZOOM,
            tiles='OpenStreetMap',
            control_scale=True
        )
        return self.map
    
    def get_region_statistics(self):
        """각 지역의 통계 계산 - DB 지역들을 6개 주요 지역으로 통합"""
        db_stats = self.loader.get_region_stats()
        consolidated_stats = {}
        
        # 6개 주요 지역으로 통합
        for main_region, db_regions in self.REGION_CONSOLIDATION.items():
            total_count = 0
            total_sentiment = 0.0
            total_positive = 0
            total_negative = 0
            weight_sum = 0
            
            # 해당 주요 지역에 속하는 모든 DB 지역 통합
            for db_region in db_regions:
                if db_region in db_stats:
                    stat = db_stats[db_region]
                    count = stat['count']
                    total_count += count
                    total_positive += stat['positive_count']
                    total_negative += stat['negative_count']
                    
                    # 가중 평균 감성 계산 (뉴스 개수로 가중)
                    if count > 0:
                        total_sentiment += stat['avg_sentiment'] * count
                        weight_sum += count
            
            # 평균 계산
            avg_sentiment = (total_sentiment / weight_sum) if weight_sum > 0 else 0.0
            
            consolidated_stats[main_region] = {
                'count': total_count,
                'avg_sentiment': avg_sentiment,
                'positive_count': total_positive,
                'negative_count': total_negative
            }
        
        return consolidated_stats

    def _split_keywords(self, keyword_text: str) -> List[str]:
        """키워드 문자열을 리스트로 분리"""
        if not keyword_text:
            return []

        separators = [',', '|', '/', ';']
        normalized = keyword_text
        for sep in separators:
            normalized = normalized.replace(sep, ',')

        raw_tokens = [token.strip() for token in normalized.replace('\n', ',').split(',')]
        tokens = []
        for token in raw_tokens:
            if not token:
                continue
            # 공백으로 나뉜 키워드도 분해
            for sub in token.split():
                sub = sub.strip()
                if sub:
                    tokens.append(sub)

        return tokens

    def _is_economic_keyword(self, token: str) -> bool:
        """경제 관련 키워드인지 판단"""
        for econ in self.ECON_KEYWORDS:
            if econ in token:
                return True
        return False

    def get_top_economic_keywords(self, db_region: str, limit: int = 5) -> List[str]:
        """지역별 경제 관련 키워드 상위 N개 추출"""
        from collections import Counter

        db_regions = self.REGION_CONSOLIDATION.get(db_region, [db_region])
        keyword_texts = self.loader.get_keywords_by_regions(db_regions)

        counter = Counter()
        for keyword_text in keyword_texts:
            for token in self._split_keywords(keyword_text):
                if self._is_economic_keyword(token):
                    counter[token] += 1

        if not counter:
            return []

        return [token for token, _ in counter.most_common(limit)]
    
    def get_top_keywords(self, db_region: str, limit: int = 10) -> List[str]:
        """지역별 전체 키워드 상위 N개 추출"""
        from collections import Counter

        db_regions = self.REGION_CONSOLIDATION.get(db_region, [db_region])
        keyword_texts = self.loader.get_keywords_by_regions(db_regions)

        counter = Counter()
        for keyword_text in keyword_texts:
            for token in self._split_keywords(keyword_text):
                if len(token) >= 2:  # 2글자 이상만
                    counter[token] += 1

        if not counter:
            return []

        return [token for token, _ in counter.most_common(limit)]
    
    def create_popup_html(self, db_region: str, stat: Dict, max_news: int = 5):
        """팝업 HTML 생성"""
        news_list = self.loader.get_latest_news_by_region(db_region, limit=max_news)
        
        html_content = f"""
        <div style="width: 700px; padding: 15px; font-family: 'Malgun Gothic', 'Arial', sans-serif; box-sizing: border-box; overflow: hidden;">
            <h3 style="margin-top: 0; margin-bottom: 10px; color: #fff; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                       padding: 12px 15px; border-radius: 5px; text-align: center; word-wrap: break-word; overflow-wrap: break-word;">
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
            
            <div style="background-color: #f0f4f8; padding: 10px; margin-bottom: 15px; border-left: 4px solid #667eea; border-radius: 3px; 
                        word-wrap: break-word; overflow-wrap: break-word;">
                <span style="font-size: 0.9em; color: #666;">평균 감성: </span>
                <span style="font-weight: bold; font-size: 1.1em; color: {'#4CAF50' if stat['avg_sentiment'] > 0 else '#f44336' if stat['avg_sentiment'] < 0 else '#999'};">
                    {stat['avg_sentiment']:+.3f}
                </span>
                <span style="font-size: 0.85em; color: #999;">({get_sentiment_label(stat['avg_sentiment'])})</span>
            </div>
            
            <div style="border-top: 2px solid #ddd; padding-top: 10px;">
                <h4 style="margin: 10px 0; color: #333; font-size: 0.95em;">📋 뉴스 목록</h4>
                <div style="max-height: 350px; overflow-y: auto;">
        """
        
        for i, news in enumerate(news_list, 1):
            title = html.escape(news.get('title', '제목 없음'))
            sentiment = news.get('sentiment_score') or 0.0
            url = news.get('url', '#')
            
            if sentiment > 0.5:
                sentiment_color = '#0D47A1'
                sentiment_emoji = '😊😊'
            elif sentiment > 0:
                sentiment_color = '#81C784'
                sentiment_emoji = '😊'
            elif sentiment < -0.5:
                sentiment_color = '#B71C1C'
                sentiment_emoji = '😔😔'
            elif sentiment < 0:
                sentiment_color = '#f44336'
                sentiment_emoji = '😔'
            else:
                sentiment_color = '#9E9E9E'
                sentiment_emoji = '😐'

            html_content += f"""
            <div style="margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid #eee;">
                <div style="margin-bottom: 6px; word-wrap: break-word; overflow-wrap: break-word;">
                    <span style="color: #1976D2; font-size: 0.9em; font-weight: 500;">
                        • <a href="{url}" target="_blank" style="color: #1976D2; text-decoration: none;">
                            {title}
                        </a>
                    </span>
                </div>
                <div style="font-size: 0.8em; margin-left: 12px;">
                    <span style="background-color: {sentiment_color}; color: white; padding: 3px 10px; border-radius: 12px; white-space: nowrap; font-size: 0.85em;">
                        {sentiment_emoji} {sentiment:+.2f}
                    </span>
                </div>
            </div>
            """
        
        if stat['count'] > max_news:
            html_content += f"""
            <div style="text-align: center; padding: 10px; color: #999; font-size: 0.85em; 
                        background-color: #f5f5f5; border-radius: 3px; margin-top: 10px;">
                ⬇️ <strong>+ {stat['count'] - max_news}개 더 많은 뉴스</strong>
            </div>
            """
        
        html_content += """</div></div></div>"""
        return html_content

    def add_region_labels(self):
        """지도에 지역명 라벨 고정 표시"""
        for region, coord in REGION_COORDS.items():
            label_html = f"""
            <div style="font-size: 15px; font-weight: 700; color: #111; white-space: nowrap;
                        text-shadow: 0 1px 2px rgba(255,255,255,0.9);
                        transform: translate(-50%, -50%); pointer-events: none;">
                {region}
            </div>
            """
            folium.Marker(
                location=coord,
                icon=DivIcon(html=label_html, icon_anchor=(0, 0)),
                interactive=False
            ).add_to(self.map)
    
    def add_geojson_layer(self, max_news: int = 10):
        """GeoJSON 레이어 추가"""
        if not self.geojson_data:
            return
        
        region_stats = self.get_region_statistics()
        EXCLUDED_REGIONS = ['Jeju']
        
        for feature in self.geojson_data['features']:
            geojson_region = feature['properties'].get('NAME_1')
            if geojson_region in EXCLUDED_REGIONS:
                continue
            db_region = get_db_region(geojson_region)
            
            if db_region is None or db_region not in region_stats:
                fill_color = '#CCCCCC'
                fill_opacity = 0.3
                stat = {'count': 0, 'avg_sentiment': 0, 'positive_count': 0, 'negative_count': 0}
            else:
                stat = region_stats[db_region]
                fill_color = get_region_color_by_avg(stat['avg_sentiment'])
                fill_opacity = 0.6
            
            feature_collection = {'type': 'FeatureCollection', 'features': [feature]}
            
            style_function = lambda x, color=fill_color, opacity=fill_opacity: {
                'fillColor': color, 'fillOpacity': opacity, 'color': '#333333', 'weight': 1.5, 'opacity': 0.8
            }
            
            highlight_function = lambda x: {'fillOpacity': 0.8, 'weight': 3, 'color': '#FF5722'}
            
            if db_region and stat['count'] > 0:
                popup_html = self.create_popup_html(db_region, stat, max_news)
                popup = folium.Popup(IFrame(html=popup_html, width=730, height=500), max_width=750)
            else:
                popup = folium.Popup(f"<div style='padding: 10px;'><b>{geojson_region}</b><br/>뉴스 데이터 없음</div>", max_width=200)
            
            GeoJson(
                feature_collection,
                style_function=style_function,
                highlight_function=highlight_function,
                popup=popup,
                name=geojson_region
            ).add_to(self.map)
    
    def add_legend(self):
        """범례 추가"""
        legend_html = '''
        <div style="position: fixed; bottom: 50px; right: 50px; width: 200px; 
                    background-color: white; border: 2px solid grey; border-radius: 5px;
                    z-index: 9999; font-size: 14px; padding: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.3);">
            <p style="margin: 0 0 10px 0; font-weight: bold; font-size: 16px;">📊 감성 지수</p>
            <p style="margin: 5px 0;"><span style="background-color: #0D47A1; width: 20px; height: 15px; display: inline-block; margin-right: 5px;"></span>매우 긍정적 (> 0.5)</p>
            <p style="margin: 5px 0;"><span style="background-color: #81C784; width: 20px; height: 15px; display: inline-block; margin-right: 5px;"></span>긍정적 (> 0)</p>
            <p style="margin: 5px 0;"><span style="background-color: #FFFFFF; border: 1px solid #ccc; width: 20px; height: 15px; display: inline-block; margin-right: 5px;"></span>중립 (= 0)</p>
            <p style="margin: 5px 0;"><span style="background-color: #FF5252; width: 20px; height: 15px; display: inline-block; margin-right: 5px;"></span>부정적 (< 0)</p>
            <p style="margin: 5px 0;"><span style="background-color: #B71C1C; width: 20px; height: 15px; display: inline-block; margin-right: 5px;"></span>매우 부정적 (< -0.5)</p>
        </div>
        '''
        self.map.get_root().html.add_child(folium.Element(legend_html))
    
    def generate(self, output_file: str = 'news_map_geo.html', max_news: int = 10):
        """지도 생성 및 저장"""
        self.load_geojson()
        self.create_map()
        self.add_geojson_layer(max_news=max_news)
        self.add_region_labels()
        self.add_legend()
        self.map.save(output_file)
        self.add_side_panel_with_events(output_file)
        print(f"✅ 완료! 파일 위치: {os.path.abspath(output_file)}")
    
    def add_side_panel_with_events(self, html_file: str):
        """HTML 파일에 사이드 패널 및 리셋 이벤트 추가"""
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        stats = self.get_region_statistics()
        region_data = {}
        for main_region in self.REGION_CONSOLIDATION.keys():
            if main_region in stats and stats[main_region]['count'] > 0:
                latest_news = self.loader.get_latest_news_by_region(main_region, limit=5)
                news_items = []
                for news in latest_news:
                    title = news.get('title', '제목 없음')
                    keyword_str = news.get('keyword', '-')
                    economic_keywords = []
                    if keyword_str and keyword_str != '-':
                        all_tokens = self._split_keywords(keyword_str)
                        for token in all_tokens:
                            if self._is_economic_keyword(token) and len(economic_keywords) < 5:
                                economic_keywords.append(token)
                    news_items.append({'title': title, 'keywords': economic_keywords})
                region_data[main_region] = news_items
        
        region_data_json = json.dumps(region_data, ensure_ascii=False)
        
        custom_code = f"""
        <style>
            .leaflet-tooltip {{ display: none !important; }}
            #map {{ margin-right: 450px; }}
            #info-panel {{
                position: fixed; right: 20px; top: 80px; width: 420px;
                max-height: 80vh; overflow-y: auto; background: white;
                border: 2px solid #E91E63; border-radius: 8px; padding: 15px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.2); z-index: 1000;
                font-family: '맑은고딕', sans-serif;
            }}
            #info-panel h3 {{ margin: 0 0 12px 0; color: #E91E63; border-bottom: 2px solid #E91E63; padding-bottom: 6px; font-size: 15px; }}
            .news-item {{ margin-bottom: 10px; padding-left: 8px; border-left: 3px solid #E91E63; }}
            .news-title {{ font-weight: 500; color: #333; font-size: 13px; line-height: 1.4; }}
            .news-keywords {{ font-size: 11px; color: #1976D2; }}
        </style>
        
        <div id="info-panel">
            <h3>📍 지역을 선택하세요</h3>
            <p style="color: #999; font-size: 12px;">지도에서 지역에 마우스를 올리거나 클릭하면 정보가 표시됩니다.</p>
        </div>
        
        <script>
            var regionNewsData = {region_data_json};
            var regionMapping = {{
                'Seoul': '서울', 'Gyeonggi-do': '경기도', 'Gangwon-do': '강원도',
                'Chungcheongnam-do': '충청도', 'Chungcheongbuk-do': '충청도',
                'Gyeongsangnam-do': '경상도', 'Gyeongsangbuk-do': '경상도',
                'Jeollanam-do': '전라도', 'Jeollabuk-do': '전라도',
                'Incheon': '경기도', 'Daejeon': '충청도', 'Daegu': '경상도',
                'Busan': '경상도', 'Ulsan': '경상도', 'Gwangju': '전라도'
            }};

            function resetPanel() {{
                var panel = document.getElementById('info-panel');
                panel.innerHTML = '<h3>📍 지역을 선택하세요</h3><p style="color: #999; font-size: 12px;">지도에서 지역에 마우스를 올리면 정보가 표시됩니다.</p>';
                panel.style.display = '';
            }}

            setTimeout(function() {{
                var mapInstance = null;
                for (var key in window) {{
                    if (key.startsWith('map_') && window[key] && typeof window[key].on === 'function') {{
                        mapInstance = window[key];
                        break;
                    }}
                }}

                if (mapInstance) {{
                    // 빈 공간 클릭 시 info-panel 다시 보이게
                    mapInstance.on('click', function(e) {{
                        var panel = document.getElementById('info-panel');
                        if (panel) {{
                            panel.style.display = 'block';
                            resetPanel();
                        }}
                    }});

                    mapInstance.eachLayer(function(layer) {{
                        if (layer.feature && layer.feature.properties && layer.feature.properties.NAME_1) {{
                            var geoJsonName = layer.feature.properties.NAME_1;

                            layer.on('mouseover', function(e) {{
                                var dbRegion = regionMapping[geoJsonName];
                                var panel = document.getElementById('info-panel');
                                if (panel) {{
                                    panel.style.display = 'block';
                                    showRegionInfo(dbRegion, regionNewsData[dbRegion]);
                                    console.log('info-panel show (mouseover):', dbRegion);
                                }}
                            }});

                            // 클릭 시 info-panel 숨기기
                            layer.on('click', function(e) {{
                                var panel = document.getElementById('info-panel');
                                if (panel) {{
                                    panel.style.display = 'none';
                                    console.log('info-panel hide (region click)');
                                }}
                            }});

                            // 마우스가 레이어를 벗어날 때 info-panel 다시 보이게 (선택)
                            layer.on('mouseout', function(e) {{
                                var panel = document.getElementById('info-panel');
                                if (panel) {{
                                    panel.style.display = 'none';
                                    console.log('info-panel hide (mouseout)');
                                }}
                            }});
                        }}
                    }});
                }}
            }}, 2000);

            function showRegionInfo(regionName, newsItems) {{
                var panel = document.getElementById('info-panel');
                var html = '<h3>📍 ' + regionName + ' 주요 뉴스 & 키워드</h3>';
                newsItems.forEach(function(news) {{
                    html += '<div class="news-item">';
                    html += '<div class="news-title">• ' + news.title + '</div>';
                    html += '<div class="news-keywords">🔍 키워드: ' + news.keywords.join(', ') + '</div>';
                    html += '</div>';
                }});
                panel.innerHTML = html;
            }}
        </script>
        """
        html_content = html_content.replace('</body>', custom_code + '</body>')
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)


if __name__ == '__main__':
    generator = NewsMapGeneratorGeo()
    generator.generate('news_map_geo.html', max_news=10)