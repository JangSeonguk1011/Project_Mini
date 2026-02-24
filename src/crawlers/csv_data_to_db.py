import os
import sqlite3
import pandas as pd
import glob
import logging
from datetime import datetime, timedelta
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

# 같은 위치의 database_manager에서 함수 가져오기
try:
    from database_manager import extract_keyword
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from database_manager import extract_keyword

# 로그 설정
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/csv_data_to_db_processor.log", encoding='utf-8'), 
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("CsvDataToDB")

class DataToDBProcessor:
    def __init__(self, db_path="data/news.db", max_workers=4):
        self.db_path = db_path
        self.max_workers = max_workers
        self.region_map = {
            'gangwon': '강원도', 'gyeonggi': '경기도', 'gyeongsang': '경상도',
            'gyeongnam': '경남', 'gyeongbuk': '경북', 'jeolla': '전라도', 'jeonnam': '전남',
            'chungcheong': '충청도', 'seoul': '서울', 'incheon': '인천',
            'daegu': '대구', 'busan': '부산', 'ulsan': '울산',
            'gwangju': '광주', 'daejeon': '대전', 'sejong': '세종',
            'jeju': '제주', 'national': '전국'
        }
        self._init_db()

    def _init_db(self):
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

    def process_row(self, row):
        """행 데이터 처리 및 튜플 반환 (날짜 형식 수정)"""
        url = row.get('article_url', row.get('url', ''))
        if not url or pd.isna(url): return None
        
        title = str(row.get('title', '')) if pd.notna(row.get('title')) else ""
        content = str(row.get('content', '')) if pd.notna(row.get('content')) else ""
        
        if not title: return None

        # [수정] CSV의 date 값을 그대로 가져오되, 시간 정보 없이 YYYY-MM-DD 형식만 유지
        pub_time = row.get('date')
        if pd.isna(pub_time):
            pub_time = datetime.now().strftime('%Y-%m-%d')
        elif hasattr(pub_time, 'strftime'):
            pub_time = pub_time.strftime('%Y-%m-%d')
        else:
            # 문자열인 경우 앞에서 10자(YYYY-MM-DD)만 추출
            pub_time = str(pub_time)[:10]

        raw_region = row.get('region', 'unknown')
        region = self.region_map.get(str(raw_region).lower(), str(raw_region))
        
        keywords = extract_keyword(title, content)
        # 수집 시간은 구분을 위해 시간까지 포함 유지
        collected_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        return (title, content, region, None, 0, pub_time, url, keywords, collected_at)

    def get_existing_urls(self, conn):
        cursor = conn.cursor()
        cursor.execute("SELECT url FROM news")
        return {row[0] for row in cursor.fetchall()}

    def process_csv_files(self, start_date=None):
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

        csv_files = glob.glob("data/filtered/filtered_raw_*.csv")
        if not csv_files:
            logger.warning("처리할 filtered_raw_*.csv 파일이 없습니다.")
            return

        conn = sqlite3.connect(self.db_path)
        existing_urls = self.get_existing_urls(conn)
        
        for file_path in csv_files:
            logger.info(f"파일 처리 시작: {file_path}")
            try:
                df = pd.read_csv(file_path, encoding='utf-8-sig')
                if 'date' not in df.columns:
                    logger.error(f"스킵: {file_path} ('date' 컬럼 없음)")
                    continue

                url_col = 'article_url' if 'article_url' in df.columns else 'url'
                
                # 날짜 필터링을 위해 잠시 datetime 객체로 변환
                df['temp_date'] = pd.to_datetime(df['date'], errors='coerce')
                df = df.dropna(subset=['temp_date'])
                
                df_filtered = df[df['temp_date'] >= pd.to_datetime(start_date)]
                df_to_process = df_filtered[~df_filtered[url_col].isin(existing_urls)]
                
                if df_to_process.empty:
                    logger.info(f"신규 데이터 없음: {file_path}")
                    continue

                results = []
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    futures = [executor.submit(self.process_row, row) for _, row in df_to_process.iterrows()]
                    for future in tqdm(as_completed(futures), total=len(futures), desc=f"{os.path.basename(file_path)} 분석"):
                        try:
                            res = future.result()
                            if res: results.append(res)
                        except Exception as e:
                            logger.error(f"행 처리 중 에러: {e}")
                
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
    processor.process_csv_files()