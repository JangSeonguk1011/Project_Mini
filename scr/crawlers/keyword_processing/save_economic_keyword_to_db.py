"""
파일명: save_economic_keyword_to_db.py 
역할: 
    1. 추출된 지역별 키워드 CSV(economic_keywords_regional.csv) 파일을 로드.
    2. 산재된 지역명(예: 부산, 경남, 울산)을 10개의 표준 지역 카테고리(예: 부산/경남)로 매핑 및 정규화.
    3. 통합된 지역 카테고리 내에서 키워드 빈도수를 재합산하고, 1위부터 20위까지의 순위(rank)를 재산출.
    4. SQLite 데이터베이스 내 'regional_economic_keywords' 테이블에 정형 데이터 저장.
    5. 저장 컬럼: id(PK), region, keyword, frequency, rank, analysis_date.
"""

import pandas as pd
import sqlite3
import os
from datetime import datetime

def normalize_and_save_to_db(csv_path="data/economic_keywords_regional.csv", db_path="data/economic_keyword_data.db"):
    """추출된 지역별 키워드를 10개 표준 카테고리로 정규화하여 DB 저장"""
    
    if not os.path.exists(csv_path):
        print(f"❌ 파일을 찾을 수 없습니다: {csv_path}")
        return

    # 1. 데이터 로드
    df = pd.read_csv(csv_path)

    # 2. 10개 표준 지역 카테고리 매핑 정의
    # 원본 데이터의 region 값을 사용자가 지정한 표준 명칭으로 변환합니다.
    region_map = {
        'total': '전국', 'national': '전국',
        'seoul': '서울',
        'gyeonggi': '경기',
        'incheon': '인천',
        'chungcheong': '충청/대전', 'daejeon': '충청/대전', 'sejong': '충청/대전',
        'busan': '부산/경남', 'gyeongnam': '부산/경남', 'ulsan': '부산/경남',
        'daegu': '대구/경북', 'gyeongbuk': '대구/경북',
        'gwangju': '광주/전라', 'jeolla': '광주/전라', 'jeonnam': '광주/전라', 'jeonbuk': '광주/전라',
        'gangwon': '강원',
        'jeju': '제주'
    }

    # 3. 지역명 정규화 적용
    df['region'] = df['region'].map(region_map).fillna(df['region'])

    # 4. 중복 지역 통합 및 빈도수 합산
    # (예: '충청'과 '대전'이 합쳐졌으므로 동일 키워드 빈도를 합산)
    df = df.groupby(['region', 'keyword'])['frequency'].sum().reset_index()

    # 5. 지역별 순위(rank) 계산
    # 빈도수 기준 내림차순 정렬 후 1위부터 순번 부여
    df = df.sort_values(by=['region', 'frequency'], ascending=[True, False])
    df['rank'] = df.groupby('region')['frequency'].rank(method='first', ascending=False).astype(int)

    # 6. 상위 20위까지만 필터링 (순위 데이터 최적화)
    df = df[df['rank'] <= 20]

    # 7. DB 연결 및 테이블 생성
    # 
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 요청하신 컬럼 구조로 테이블 생성 (id는 자동 증가 Primary Key)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS regional_economic_keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            region TEXT NOT NULL,
            keyword TEXT NOT NULL,
            frequency INTEGER NOT NULL,
            rank INTEGER NOT NULL,
            analysis_date DATE DEFAULT CURRENT_DATE
        )
    ''')

    # 8. 데이터 삽입 (기존 데이터 교체 또는 추가)
    # 기존 분석 데이터를 지우고 새로 넣으려면 replace, 누적하려면 append를 사용합니다.
    df.to_sql('regional_economic_keywords', conn, if_exists='replace', index=False)

    print(f"✅ DB 저장 완료: {db_path}")
    print(f"저장된 지역 수: {df['region'].nunique()}개")
    conn.close()

if __name__ == "__main__":
    normalize_and_save_to_db()