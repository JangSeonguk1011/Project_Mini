"""
데이터베이스 관리 모듈
크롤링된 뉴스를 SQLite에 저장
"""

import sqlite3
import logging
from datetime import datetime
from typing import List, Dict
import os

logger = logging.getLogger('DatabaseManager')

class DatabaseManager:
    """SQLite 데이터베이스 관리"""
    
    def __init__(self, db_path: str = 'data/news.db'):
        """
        Args:
            db_path: 데이터베이스 파일 경로
        """
        if os.path.isabs(db_path):
            self.db_path = db_path
        else:
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            self.db_path = os.path.join(project_root, db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        logger.info(f"✓ 데이터베이스 경로: {self.db_path}")
        self._create_tables()
    
    def _create_tables(self):
        """테이블 생성"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 뉴스 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT,
                url TEXT UNIQUE,
                date TEXT,
                writer TEXT,
                source TEXT,
                newspaper TEXT,
                region TEXT,
                collected_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 지역 통계 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS region_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                region TEXT,
                newspaper TEXT,
                article_count INTEGER,
                last_crawled TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"✓ 데이터베이스 초기화: {self.db_path}")
    
    def insert_articles(self, articles: List[Dict]) -> int:
        """
        뉴스 기사 삽입
        
        Args:
            articles: 기사 딕셔너리 리스트
        
        Returns:
            삽입된 기사 수
        """
        if not articles:
            logger.warning("삽입할 기사가 없습니다.")
            return 0
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        inserted_count = 0
        for article in articles:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO news 
                    (title, content, url, date, writer, source, newspaper, region, collected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    article.get('title'),
                    article.get('content'),
                    article.get('url'),
                    article.get('date'),
                    article.get('writer'),
                    article.get('source'),
                    article.get('newspaper'),
                    article.get('region'),
                    article.get('collected_at')
                ))
                
                if cursor.rowcount > 0:
                    inserted_count += 1
            
            except sqlite3.IntegrityError:
                logger.debug(f"중복 URL 건너뛰기: {article.get('url')}")
            except Exception as e:
                logger.error(f"삽입 실패: {e}")
        
        conn.commit()
        conn.close()
        
        logger.info(f"✓ 데이터베이스에 {inserted_count}개 기사 저장")
        return inserted_count
    
    def update_region_stats(self, region: str, newspaper: str, count: int):
        """지역별 통계 업데이트"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO region_stats (region, newspaper, article_count, last_crawled)
            VALUES (?, ?, ?, ?)
        ''', (region, newspaper, count, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        
        conn.commit()
        conn.close()
    
    def get_total_count(self) -> int:
        """전체 기사 수 조회"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM news')
        count = cursor.fetchone()[0]
        
        conn.close()
        return count
    
    def get_articles_by_region(self, region: str) -> List[Dict]:
        """지역별 기사 조회"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM news 
            WHERE region = ? 
            ORDER BY collected_at DESC
        ''', (region,))
        
        articles = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return articles
    
    def print_stats(self):
        """통계 출력"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 전체 통계
        cursor.execute('SELECT COUNT(*) FROM news')
        total = cursor.fetchone()[0]
        
        # 지역별 통계
        cursor.execute('''
            SELECT region, COUNT(*) as count 
            FROM news 
            GROUP BY region 
            ORDER BY count DESC
        ''')
        region_stats = cursor.fetchall()
        
        # 신문사별 통계
        cursor.execute('''
            SELECT source, COUNT(*) as count 
            FROM news 
            GROUP BY source 
            ORDER BY count DESC
        ''')
        source_stats = cursor.fetchall()
        
        conn.close()
        
        logger.info(f"\n{'='*70}")
        logger.info("📊 데이터베이스 통계")
        logger.info(f"{'='*70}")
        logger.info(f"\n전체 기사: {total}개")
        
        logger.info(f"\n📍 지역별:")
        for region, count in region_stats:
            logger.info(f"  {region}: {count}개")
        
        logger.info(f"\n📰 신문사별:")
        for source, count in source_stats:
            logger.info(f"  {source}: {count}개")
        
        logger.info(f"{'='*70}\n")
