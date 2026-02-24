"""
데이터베이스 관리 모듈
크롤링된 뉴스를 SQLite에 저장
"""

import sqlite3
import logging
from datetime import datetime
from typing import List, Dict
import os
import re

logger = logging.getLogger('DatabaseManager')

# 불용어 리스트 (키워드 추출 시 제외할 단어)
STOPWORDS = {
    '이', '그', '저', '것', '수', '등', '및', '한', '에', '을', '를', '이', '가', '은', '는', '의', '로', '으로',
    '에서', '와', '과', '도', '만', '까지', '부터', '에게', '께', '더', '가장', '매우', '너무', '정말',
    '위해', '통해', '대한', '관한', '따른', '위한', '같은', '있는', '없는', '하는', '되는', '있다', '없다',
    '년', '월', '일', '시', '분', '초', '개', '명', '곳', '번', '차', '회', '대', '중', '내',
    '오전', '오후', '어제', '오늘', '내일', '이번', '지난', '다음', '올해', '작년', '내년',
    '-', '·', '…', '"', '"', ''', ''', '(', ')', '[', ']', '<', '>', '/', '\\', '|'
}

def extract_keyword(title: str, content: str = '') -> str:
    """
    기사 제목에서 핵심 키워드 추출
    
    Args:
        title: 기사 제목
        content: 기사 본문 (선택)
        
    Returns:
        쉼표로 구분된 키워드 문자열
    """
    if not title:
        return ''
    
    # 특수문자 제거 및 단어 분리
    import re
    
    # 제목 정제
    cleaned = re.sub(r'[^\w\s가-힣a-zA-Z0-9]', ' ', title)
    words = cleaned.split()
    
    # 키워드 추출 로직
    keywords = []
    for word in words:
        word = word.strip()
        # 너무 짧거나 불용어는 제외
        if len(word) >= 2 and word not in STOPWORDS:
            # 숫자만 있는 것도 제외
            if not word.isdigit():
                keywords.append(word)
    
    # 중복 제거하고 최대 5개까지만
    unique_keywords = []
    for kw in keywords:
        if kw not in unique_keywords:
            unique_keywords.append(kw)
        if len(unique_keywords) >= 5:
            break
    
    result = ', '.join(unique_keywords) if unique_keywords else '키워드 없음'
    logger.debug(f"키워드 추출: {title[:30]}... → {result}")
    return result

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
                region TEXT,
                sentiment_score REAL,
                is_processed INTEGER DEFAULT 0,
                published_time TEXT,
                url TEXT UNIQUE,
                keyword TEXT,
                collected_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # keyword 컬럼이 없는 기존 테이블에 추가
        try:
            cursor.execute("ALTER TABLE news ADD COLUMN keyword TEXT")
            logger.info("✓ keyword 컬럼 추가 완료")
        except sqlite3.OperationalError:
            pass  # 이미 존재하는 경우
        
        # collected_at 컬럼이 없는 기존 테이블에 추가
        try:
            cursor.execute("ALTER TABLE news ADD COLUMN collected_at TEXT")
            logger.info("✓ collected_at 컬럼 추가 완료")
        except sqlite3.OperationalError:
            pass  # 이미 존재하는 경우
        
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
                # 키워드 자동 추출
                keyword = extract_keyword(
                    article.get('title', ''),
                    article.get('content', '')
                )
                
                cursor.execute('''
                    INSERT OR IGNORE INTO news 
                    (title, content, region, sentiment_score, is_processed, published_time, keyword, collected_at, url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    article.get('title'),
                    article.get('content'),
                    article.get('region'),
                    article.get('sentiment_score', 0.0),
                    article.get('is_processed', 0),
                    article.get('published_time'),
                    keyword,
                    article.get('collected_at'),
                    article.get('url')
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
            ORDER BY published_time DESC
        ''', (region,))
        
        articles = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return articles
    
    def delete_old_articles(self, days: int = 30) -> int:
        """
        지정된 일수 이전의 기사 삭제
        
        Args:
            days: 보관 기간 (일)
        
        Returns:
            삭제된 기사 수
        """
        from datetime import timedelta
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 기준일 계산
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        # 삭제 전 개수 확인
        cursor.execute('SELECT COUNT(*) FROM news WHERE published_time < ?', (cutoff_date,))
        old_count = cursor.fetchone()[0]
        
        if old_count > 0:
            # 오래된 기사 삭제
            cursor.execute('DELETE FROM news WHERE published_time < ?', (cutoff_date,))
            conn.commit()
            logger.info(f"✓ {days}일 이전 기사 {old_count}개 삭제 (기준일: {cutoff_date})")
        else:
            logger.debug(f"삭제할 기사 없음 (기준일: {cutoff_date})")
        
        conn.close()
        return old_count
    
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
        
        conn.close()
        
        logger.info(f"\n{'='*70}")
        logger.info("📊 데이터베이스 통계")
        logger.info(f"{'='*70}")
        logger.info(f"\n전체 기사: {total}개")
        
        logger.info(f"\n📍 지역별:")
        for region, count in region_stats:
            logger.info(f"  {region}: {count}개")
        
        logger.info(f"{'='*70}\n")
