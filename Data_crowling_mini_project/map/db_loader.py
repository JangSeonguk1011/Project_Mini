"""
데이터베이스 로더
news.db에서 뉴스 데이터를 가져옵니다
"""

import sqlite3
import os
from typing import List, Dict, Optional


class NewsDBLoader:
    """뉴스 데이터베이스 로더 (news.db & news_scraped.db 통합)"""
    
    def __init__(self, db_path: str = None):
        """
        Args:
            db_path: 기본 데이터베이스 경로 (제공되지 않으면 기본 위치 사용)
        """
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        
        # news.db만 사용
        self.db_paths = [os.path.join(project_root, 'data', 'news.db')]
        self.db_paths = [p for p in self.db_paths if os.path.exists(p)]
        
        if not self.db_paths:
            raise FileNotFoundError("데이터베이스 파일을 찾을 수 없습니다.")

    def _get_combined_query(self, query: str, params: tuple = ()) -> List[Dict]:
        """여러 DB에서 쿼리 실행 후 URL 기준으로 중복 제거"""
        all_data = []
        for path in self.db_paths:
            try:
                conn = sqlite3.connect(path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                all_data.extend([dict(row) for row in cursor.fetchall()])
                conn.close()
            except Exception:
                continue
        
        # URL 기준 중복 제거 (최신 데이터 우선 유지)
        unique_news = {}
        for item in all_data:
            url = item.get('url')
            if url not in unique_news:
                unique_news[url] = item
            else:
                # published_time이 더 최신인 것을 유지 (문자열 비교)
                if str(item.get('published_time', '')) > str(unique_news[url].get('published_time', '')):
                    unique_news[url] = item
        
        return list(unique_news.values())

    def get_all_news(self) -> List[Dict]:
        query = '''
            SELECT id, title, content, region, sentiment_score, 
                   published_time, url, keyword, collected_at
            FROM news
            ORDER BY published_time DESC
        '''
        return self._get_combined_query(query)
    
    def get_news_by_region(self, region: str) -> List[Dict]:
        query = '''
            SELECT id, title, content, region, sentiment_score, 
                   published_time, url, keyword, collected_at
            FROM news
            WHERE region LIKE ?
            ORDER BY published_time DESC
        '''
        # region이 포함된 경우 검색 (%서울%)
        return self._get_combined_query(query, (f'%{region}%',))
    
    def get_region_stats(self) -> Dict[str, Dict]:
        all_news = self.get_all_news()
        import pandas as pd
        df = pd.DataFrame(all_news)
        
        if df.empty: return {}
        
        # region이 None인 경우 제외
        df = df[df['region'].notnull()]
        
        stats = {}
        # 주요 지역별로 집계 (단순 GroupBy 대신 지역명 포함 여부로 체크)
        regions = ['서울', '경기도', '강원도', '충청도', '경상도', '전라도', '부산']
        for r in regions:
            r_df = df[df['region'].str.contains(r, na=False)]
            if not r_df.empty:
                stats[r] = {
                    'count': len(r_df),
                    'avg_sentiment': r_df['sentiment_score'].mean() or 0.0,
                    'positive_count': len(r_df[r_df['sentiment_score'] > 0.5]),
                    'negative_count': len(r_df[r_df['sentiment_score'] < 0.5])
                }
        return stats
    
    def get_latest_news_by_region(self, region: str, limit: int = 5) -> List[Dict]:
        news = self.get_news_by_region(region)
        # 이미 정렬되어 있으므로 limit만 적용
        return news[:limit]

    def get_keywords_by_regions(self, regions: List[str]) -> List[str]:
        """
        여러 지역의 키워드 목록 가져오기 (모든 DB에서 병합)
        Args:
            regions: 지역명 리스트
        Returns:
            키워드 문자열 리스트
        """
        if not regions:
            return []

        keywords = []
        for db_path in self.db_paths:
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                placeholders = ",".join(["?"] * len(regions))
                query = f"""
                    SELECT keyword
                    FROM news
                    WHERE region IN ({placeholders})
                      AND keyword IS NOT NULL
                      AND TRIM(keyword) != ''
                """
                cursor.execute(query, regions)
                keywords.extend([row[0] for row in cursor.fetchall()])
                conn.close()
            except Exception:
                continue
        return keywords


if __name__ == '__main__':
    # 테스트
    loader = NewsDBLoader()
    
    print("=== 전체 뉴스 개수 ===")
    all_news = loader.get_all_news()
    print(f"총 {len(all_news)}개 뉴스")
    
    print("\n=== 지역별 통계 ===")
    stats = loader.get_region_stats()
    for region, stat in stats.items():
        print(f"{region}: {stat['count']}개 (평균 감성: {stat['avg_sentiment']:.2f})")
    
    print("\n=== 서울 최신 뉴스 3개 ===")
    seoul_news = loader.get_latest_news_by_region('서울', 3)
    for news in seoul_news:
        print(f"- {news['title'][:50]}... (감성: {news['sentiment_score']})")
