"""
파일명: economic_keyword_extractor.py
역할: 
    1. 'data/' 폴더 내의 모든 지역별 뉴스 CSV 파일을 로드 및 통합.
    2. KoNLPy(Okt)를 활용하여 기사 제목 및 본문에서 핵심 명사를 추출.
    3. 메모리 부족(OOM) 방지를 위해 단일 프로세스 기반 순차 처리 및 본문 길이 제한(600자) 적용.
    4. 불용어 처리를 통해 '기자', '무단전재' 및 '서울', '부산' 등 지역명 키워드 제거.
    5. '전체 통합 키워드(TOP 100)'와 '10개 표준 지역별 키워드(TOP 20)'를 CSV로 각각 저장.
"""

import os
import re
import glob
import logging
import pandas as pd
from datetime import datetime
from collections import Counter
from konlpy.tag import Okt
from tqdm import tqdm

# Java 환경 설정
os.environ['JAVA_HOME'] = r'C:\Program Files\Java\jdk-20'

def setup_logger():
    log_dir = "logs"
    if not os.path.exists(log_dir): os.makedirs(log_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"keyword_extraction_{timestamp}.log")
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.FileHandler(log_file, encoding='utf-8'), logging.StreamHandler()]
    )
    return logging.getLogger("keyword_extractor")

def get_stopwords():
    # 1. 일반적인 경제 뉴스 노이즈 단어
    general_stopwords = [
        '기자', '뉴스', '배포', '무단', '금지', '전재', '오늘', '어제', '내일', '이번', '지난', 
        '때문', '대한', '관련', '통해', '위해', '경우', '사진', '밝혔다', '말했다', '최근', 
        '지역', '투데이', '확대', '이미지', '보기', '기사', '오전', '오후', '시간', '지난해'
    ]
    
    # 2. 10개 표준 지역명 구성 단어 (개별 분리)
    # 분석 결과에 '부산', '서울' 등 지역 이름이 키워드로 나오는 것을 방지하기 위함입니다.
    # 2. 10개 표준 지역 구성을 위한 상세 지명 (약어 및 행정구역 포함)
    # 기사 본문에서 지명이 키워드로 잡히는 것을 방지합니다.
    region_stopwords = [
        '전국', '서울', '서울시', 
        '경기', '경기도', '인천', '인천시', '인천광역시',
        '충청', '충청도', '충남', '충북', '대전', '대전시', '대전광역시', '세종', '세종시',
        '부산', '부산시', '부산광역시', '경남', '경남도', '울산', '울산시', '울산광역시',
        '대구', '대구시', '대구광역시', '경북', '경북도', '경상',
        '광주', '광주시', '광주광역시', '전라', '전라도', '전남', '전북', 
        '강원', '강원도', '제주', '제주시', '제주도'
    ]
    
    # 두 리스트를 합쳐서 반환
    return list(set(general_stopwords + region_stopwords))

def extract_keywords_safe():
    logger = setup_logger()
    logger.info("--- 핵심 분석 가동: CSV 데이터 통합 및 지역별 키워드 전수 조사 시작 ---")
    
    # 1. 데이터 로드
    all_files = glob.glob("data/raw_*.csv")
    if not all_files:
        logger.error("데이터 파일이 없습니다.")
        return

    df = pd.concat([pd.read_csv(f, encoding='utf-8-sig') for f in all_files], ignore_index=True)
    df['full_text'] = df['title'].fillna('') + " " + df['content'].fillna('')
    logger.info(f"총 {len(df)}건 로드 완료.")

    # 2. 분석기 및 결과 저장소 초기화
    okt = Okt()
    stopwords = get_stopwords()
    all_region_noun_pairs = []
    
    start_time = datetime.now()

    # 3. 순차 처리 (메모리 안정성 확보)
    # tqdm을 적용하여 기사 한 건 한 건의 진행 상황을 확인
    for _, row in tqdm(df.iterrows(), total=len(df), desc="키워드 분석 중"):
        try:
            region = row['region']
            # 본문이 너무 길면 분석이 무거워지므로 앞부분 600자만 사용 (속도 최적화)
            text_snippet = str(row['full_text'])[:600]
            
            clean_text = re.sub(r'[^가-힣\s]', '', text_snippet)
            nouns = [n for n in okt.nouns(clean_text) if n not in stopwords and len(n) > 1]
            
            for noun in nouns:
                all_region_noun_pairs.append((region, noun))
        except Exception as e:
            continue

    # 4. 결과 집계 및 저장
    if not all_region_noun_pairs:
        logger.error("추출된 명사가 없습니다.")
        return

    rel_df = pd.DataFrame(all_region_noun_pairs, columns=['region', 'keyword'])

    # --- [파일 1] 전체 통합 키워드 ---
    total_counts = Counter(rel_df['keyword'])
    total_df = pd.DataFrame(total_counts.most_common(100), columns=['keyword', 'frequency'])
    total_df.to_csv("data/economic_keywords_total.csv", index=False, encoding='utf-8-sig')
    logger.info("✅ 전체 통합 저장 완료: data/economic_keywords_total.csv")

    # --- [파일 2] 지역별 키워드 (삭제되지 않도록 명시적 처리) ---
    regional_summary = []
    for region, group in rel_df.groupby('region'):
        counts = Counter(group['keyword'])
        for word, freq in counts.most_common(20):
            regional_summary.append({'region': region, 'keyword': word, 'frequency': freq})
    
    regional_df = pd.DataFrame(regional_summary)
    regional_df.to_csv("data/economic_keywords_regional.csv", index=False, encoding='utf-8-sig')
    logger.info("✅ 지역별 키워드 저장 완료: data/economic_keywords_regional.csv")

    duration = datetime.now() - start_time
    logger.info(f"최종 소요 시간: {duration}")

if __name__ == "__main__":
    extract_keywords_safe()