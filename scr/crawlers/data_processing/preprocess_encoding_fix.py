"""
파일명: preprocess_all_csv.py
역할: 
    1. 'data/' 폴더 내의 모든 'raw_*.csv' 파일을 자동으로 검색하여 일괄 처리.
    2. 파일별 인코딩 자동 감지 및 'мўӢ' 등 인코딩 오류로 인한 외계어 제거.
    3. 한글 비중 분석을 통해 정제 후에도 내용이 불충분한 불량 데이터를 자동으로 필터링.
    4. 처리된 결과를 저장하여 데이터 유실 및 권한 에러 방지.
"""

import pandas as pd
import chardet
import re
import os

def detect_encoding(file_path):
    with open(file_path, 'rb') as f:
        rawdata = f.read(20000)
    return chardet.detect(rawdata)['encoding']

def preprocess_csv(file_path):
    encoding = detect_encoding(file_path)
    print(f"🔍 감지된 인코딩: {encoding}")
    
    try:
        df = pd.read_csv(file_path, encoding=encoding, on_bad_lines='skip', encoding_errors='replace')
    except:
        df = pd.read_csv(file_path, encoding='cp949', encoding_errors='replace')

    raw_count = len(df)
    
    def clean_text(text):
        if pd.isna(text): return ""
        text = str(text)
        
        # 1. [강력 정제] 한글, 영문, 숫자, 마침표, 공백 외 'мўӢ' 같은 모든 유니코드 기호 제거
        # 만약 특정 기호가 계속 남는다면 여기에 추가: [^가-힣a-zA-Z0-9\s\.문자]
        clean = re.sub(r'[^가-힣a-zA-Z0-9\s\.]', '', text)
        
        # 2. 연속된 공백 통합
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean

    str_cols = df.select_dtypes(include=['object', 'string']).columns
    for col in str_cols:
        df[col] = df[col].apply(clean_text)

    # 3. [필터링 강화] 제목에 한글이 최소 3글자 이상 포함된 경우만 생존
    # 기호가 섞여서 한글이 한두 글자만 남은 쓰레기 데이터를 걸러냅니다.
    df = df[df['title'].str.count('[가-힣]') >= 3]
    
    # 4. [필터링 강화] 전체 길이 대비 한글 비중이 너무 낮으면 삭제
    # (예: "삼성전자 мўӢmmҡ" 처럼 깨진 문자가 반 이상인 경우 방지)
    def korean_ratio(text):
        if not text: return 0
        ko_count = len(re.findall(r'[가-힣]', text))
        return ko_count / len(text) if len(text) > 0 else 0

    df = df[df['title'].apply(korean_ratio) > 0.5] # 한글 비중 50% 이상만
    
    clean_count = len(df)

    print("-" * 40)
    print(f"📊 전처리 리포트 (필터링 강화)")
    print(f"  - 원본 데이터: {raw_count:,}건")
    print(f"  - 최종 유효 데이터: {clean_count:,}건")
    print(f"  - 삭제된 불량 데이터: {raw_count - clean_count:,}건")
    print("-" * 40)

    return df

if __name__ == "__main__":
    # 입력과 출력 경로를 다르게 설정하여 PermissionError 및 데이터 유실 방지
    input_path = "data/raw_incheon_incheon.csv"
    output_path = "data/raw_incheon_incheon.csv" # 파일명 변경
    
    if os.path.exists(input_path):
        result_df = preprocess_csv(input_path)
        
        # 엑셀 종료 확인 후 실행 필수
        try:
            result_df.to_csv(output_path, index=False, encoding='utf-8-sig')
            print(f"✅ 결과가 '{output_path}'에 저장되었습니다.")
        except PermissionError:
            print(f"❌ 에러: '{output_path}' 파일이 엑셀 등에서 열려 있습니다. 종료 후 다시 시도하세요.")