import os
import glob
import pandas as pd
import logging
from datetime import datetime, timedelta

# 로그 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/csv_date_filter.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("CsvFilter")

class CsvDateFilter:
    def __init__(self):
        self.region_map = {
            'gangwon': '강원도', 'gyeonggi': '경기도', 'gyeongsang': '경상도',
            'gyeongnam': '경상도', 'gyeongbuk': '경상도', 'jeolla': '전라도',
            'chungcheong': '충청도', 'seoul': '서울', 'incheon': '인천',
            'daegu': '대구', 'busan': '부산', 'ulsan': '울산',
            'gwangju': '광주', 'daejeon': '대전', 'sejong': '세종',
            'jeju': '제주', 'national': '전국'
        }

    def run(self, days=30, max_rows=300):
        # 기준 날짜 계산
        start_date = datetime.now() - timedelta(days=days)
        logger.info(f"필터링 기준: {start_date.strftime('%Y-%m-%d')} 이후 데이터 중 파일당 최대 {max_rows}건 유지")

        csv_files = glob.glob("data/scraped/raw_*.csv")
        output_dir = "data/filtered"
        os.makedirs(output_dir, exist_ok=True)

        for file_path in csv_files:
            file_name = os.path.basename(file_path)
            try:
                # 1. 파일 읽기 (인코딩 대응)
                try:
                    df = pd.read_csv(file_path, encoding='utf-8-sig')
                except:
                    df = pd.read_csv(file_path, encoding='cp949')

                if 'date' not in df.columns:
                    logger.error(f"스킵: {file_name} ('date' 컬럼 없음)")
                    continue

                # 2. 날짜 전처리 및 필터링
                df['date_clean'] = df['date'].astype(str).str.replace(r'[^0-9]', '', regex=True)
                df['date_dt'] = pd.to_datetime(df['date_clean'], format='%Y%m%d', errors='coerce')
                
                # 최근 30일 데이터만 1차 추출
                df_filtered = df[df['date_dt'] >= start_date].copy()

                if df_filtered.empty:
                    logger.info(f"⏭️ 데이터 없음: {file_name}")
                    continue

                # 3. [추가] 300건 초과 시 최신순으로 자르기
                if len(df_filtered) > max_rows:
                    # 날짜 기준 내림차순 정렬 (최신이 위로)
                    df_filtered = df_filtered.sort_values(by='date_dt', ascending=False)
                    # 상위 300개만 선택
                    df_filtered = df_filtered.head(max_rows)
                    logger.info(f"✂️ {file_name}: {max_rows}건 초과로 최신순 커팅 완료")

                # 4. 가공 및 정리
                if 'region' in df_filtered.columns:
                    df_filtered['region_kor'] = df_filtered['region'].apply(
                        lambda x: self.region_map.get(str(x).lower(), x)
                    )

                df_filtered['date'] = df_filtered['date_dt'].dt.strftime('%Y-%m-%d')
                df_filtered = df_filtered.drop(columns=['date_clean', 'date_dt'])

                # 5. 저장
                save_path = os.path.join(output_dir, f"filtered_{file_name}")
                df_filtered.to_csv(save_path, index=False, encoding='utf-8-sig')
                logger.info(f"✅ 저장 완료: {save_path} ({len(df_filtered)}건)")

            except Exception as e:
                logger.error(f"에러 ({file_name}): {e}")

if __name__ == "__main__":
    filter_tool = CsvDateFilter()
    # 최근 30일 데이터 유지, 파일당 최대 300건으로 제한
    filter_tool.run(days=30, max_rows=300)