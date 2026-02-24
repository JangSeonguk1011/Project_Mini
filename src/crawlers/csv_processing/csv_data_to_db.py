import os
import re
import glob
import sqlite3
import pandas as pd
import logging
from datetime import datetime, timedelta
from konlpy.tag import Okt
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

# 로그 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("logs/csv_data_to_db_processor.log", encoding='utf-8'), logging.StreamHandler()]
)
logger = logging.getLogger("CsvDataToDB")

class DataToDBProcessor:
    def __init__(self, db_path="data/news.db", max_workers=4):
        self.db_path = db_path
        self.max_workers = max_workers
        self.okt = Okt()
        
        # 지역명 매핑
        self.region_map = {
            'gangwon': '강원도', 'gyeonggi': '경기도', 'gyeongsang': '경상도',
            'gyeongnam': '경상도', 'gyeongbuk': '경상도', 'jeolla': '전라도',
            'chungcheong': '충청도', 'seoul': '서울', 'incheon': '인천',
            'daegu': '대구', 'busan': '부산', 'ulsan': '울산',
            'gwangju': '광주', 'daejeon': '대전', 'sejong': '세종',
            'jeju': '제주', 'national': '전국'
        }

        # 불용어 설정
        self.stopwords = set([
            '기자', '뉴스', '배포', '무단', '금지', '전재', '오늘', '어제', '내일', '이번', '지난', 
            '때문', '대한', '관련', '통해', '위해', '경우', '사진', '밝혔다', '말했다', '최근', 
            '지역', '투데이', '확대', '이미지', '보기', '기사', '오전', '오후', '시간', '지난해', '경인일보',
            '전국', '서울', '인천', '경기', '충청', '대전', '세종', '부산', '울산', '경남', '경북', '대구', '광주', '전라', '강원', '제주'
        ])

        self._init_db()

    def _init_db(self):
        """데이터베이스 및 테이블 초기화"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
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
        conn.commit()
        conn.close()

    def delete_old_data_auto(self, days=30):
        """현재 날짜 기준 N일 이전의 데이터 삭제"""
        target_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # DB의 published_time과 계산된 target_date 비교 삭제
        cursor.execute("DELETE FROM news WHERE date(published_time) < date(?)", (target_date,))
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        logger.info(f"✓ 현재 기준 {days}일 이전({target_date} 미만) DB 데이터 {deleted_count}건 삭제 완료")
        return target_date

    def extract_keywords(self, text, top_n=5):
        """본문 키워드 추출"""
        if not text or pd.isna(text): return ""
        clean_text = re.sub(r'[^가-힣\s]', ' ', str(text))
        nouns = self.okt.nouns(clean_text)
        
        filtered_nouns = [n for n in nouns if n not in self.stopwords and len(n) > 1 and '일보' not in n and '신문' not in n]
        
        from collections import Counter
        counts = Counter(filtered_nouns)
        top_keywords = [item[0] for item in counts.most_common(top_n)]
        return ", ".join(top_keywords)

    def process_row(self, row):
        """행 데이터 처리 및 튜플 반환"""
        url = row.get('article_url', row.get('url', ''))
        if not url: return None
        
        # CSV의 'date' 컬럼을 published_time으로 매핑
        pub_time = row.get('date', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        # 날짜 데이터가 Timestamp 형태일 경우 문자열로 변환
        if hasattr(pub_time, 'strftime'):
            pub_time = pub_time.strftime('%Y-%m-%d %H:%M:%S')

        title = row.get('title', '')
        content = row.get('content', '')
        raw_region = row.get('region', 'unknown')
        region = self.region_map.get(raw_region.lower(), raw_region)
        
        keywords = self.extract_keywords(content)
        collected_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        return (title, content, region, None, 0, pub_time, url, keywords, collected_at)

    def get_existing_urls(self, conn):
        """DB에 이미 존재하는 URL 목록 조회"""
        cursor = conn.cursor()
        cursor.execute("SELECT url FROM news")
        return {row[0] for row in cursor.fetchall()}

    def process_csv_files(self, start_date=None):
        """CSV 파일을 읽어 start_date 이후 데이터만 저장"""
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

        csv_files = glob.glob("data/raw_*.csv")
        if not csv_files:
            logger.warning("처리할 raw_*.csv 파일이 없습니다.")
            return

        conn = sqlite3.connect(self.db_path)
        existing_urls = self.get_existing_urls(conn)
        
        for file_path in csv_files:
            logger.info(f"파일 처리 시작: {file_path}")
            try:
                df = pd.read_csv(file_path, encoding='utf-8-sig')
                
                # 'date' 컬럼 확인
                if 'date' not in df.columns:
                    logger.error(f"스킵: {file_path} ('date' 컬럼을 찾을 수 없음)")
                    continue

                # URL 컬럼 확인
                url_col = 'article_url' if 'article_url' in df.columns else 'url'
                
                # 1. 날짜 형식 변환 및 필터링
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
                df = df.dropna(subset=['date'])
                
                # 2. 30일 이내 데이터만 선택
                df_filtered = df[df['date'] >= pd.to_datetime(start_date)]
                
                # 3. 중복 URL 제외
                df_to_process = df_filtered[~df_filtered[url_col].isin(existing_urls)]
                
                if df_to_process.empty:
                    logger.info(f"신규 데이터 없음: {file_path}")
                    continue

                results = []
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    futures = [executor.submit(self.process_row, row) for _, row in df_to_process.iterrows()]
                    
                    for future in tqdm(as_completed(futures), total=len(futures), desc=f"{os.path.basename(file_path)} 분석 중"):
                        res = future.result()
                        if res:
                            results.append(res)
                
                if results:
                    cursor = conn.cursor()
                    cursor.executemany('''
                        INSERT OR IGNORE INTO news (title, content, region, sentiment_score, is_processed, published_time, url, keyword, collected_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', results)
                    conn.commit()
                    existing_urls.update([r[6] for r in results])
                    logger.info(f"저장 완료: {file_path} ({len(results)}건)")
                
            except Exception as e:
                logger.error(f"파일 에러 ({file_path}): {e}")

        conn.close()

if __name__ == "__main__":
    processor = DataToDBProcessor(max_workers=8)
    
    # 30일 이전 데이터 삭제 및 기준 날짜 반환
    limit_date = processor.delete_old_data_auto(days=30)
    
    # 해당 날짜 이후 데이터만 저장
    processor.process_csv_files(start_date=limit_date)