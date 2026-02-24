import pandas as pd
import chardet
import re
import os

def detect_encoding(file_path):
    """파일의 일부를 읽어 인코딩을 최대한 정확하게 감지"""
    with open(file_path, 'rb') as f:
        rawdata = f.read(50000)  # 감지 정확도를 위해 읽기 범위 확대
    result = chardet.detect(rawdata)
    encoding = result['encoding']
    confidence = result['confidence']
    return encoding, confidence

def fix_broken_korean(text):
    """
    이미 깨진 상태로 로드된 문자열을 복구 시도 (ftfy 라이브러리 역할을 일부 수행)
    인코딩 꼬임(Mojibake) 현상을 해결하기 위한 로직
    """
    if pd.isna(text) or not isinstance(text, str): return text
    
    try:
        # UTF-8 데이터를 ISO-8859-1로 잘못 읽었을 경우 다시 되돌림
        return text.encode('latin-1').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        try:
            # CP949 데이터를 latin-1로 잘못 읽었을 경우
            return text.encode('latin-1').decode('cp949')
        except:
            return text

def preprocess_csv(file_path):
    encoding, confidence = detect_encoding(file_path)
    print(f"🔍 감지된 인코딩: {encoding} (신뢰도: {confidence:.2f})")
    
    # 1. 일차적으로 감지된 인코딩으로 로드 시도
    try:
        # 인코딩 에러 발생 시 삭제하지 않고 'replace'하여 최대한 읽어옴
        df = pd.read_csv(file_path, encoding=encoding, on_bad_lines='skip')
    except:
        # 실패 시 한국어 윈도우 표준인 cp949 시도
        df = pd.read_csv(file_path, encoding='cp949', encoding_errors='replace')

    raw_count = len(df)
    
    # 2. 문자열 컬럼 복구 로직 적용
    str_cols = df.select_dtypes(include=['object', 'string']).columns
    for col in str_cols:
        # 제거(re.sub) 대신 복구(fix_broken_korean) 적용
        df[col] = df[col].apply(fix_broken_korean)
        
        # 복구 후에도 남은 불필요한 특수 제어 문자만 최소한으로 정리
        df[col] = df[col].apply(lambda x: re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', str(x)) if pd.notna(x) else x)

    # 3. [검증] 복구 후 한글 비중 분석 (삭제 기준 완화)
    def korean_ratio(text):
        if not text or pd.isna(text): return 0
        ko_count = len(re.findall(r'[가-힣]', str(text)))
        return ko_count / len(str(text)) if len(str(text)) > 0 else 0

    # 복구가 불가능한 완전한 쓰레기 데이터만 최소한으로 필터링 (비중 50% -> 10%로 완화)
    # 복구 로직을 거쳤으므로 웬만한 데이터는 살아남습니다.
    df = df[df['title'].apply(korean_ratio) > 0.1] 
    
    clean_count = len(df)

    print("-" * 40)
    print(f"📊 복구 및 전처리 리포트")
    print(f"  - 원본 데이터: {raw_count:,}건")
    print(f"  - 복구 및 유지 데이터: {clean_count:,}건")
    print(f"  - 삭제된 불복구 데이터: {raw_count - clean_count:,}건")
    print("-" * 40)

    return df

if __name__ == "__main__":
    # 처리할 파일 경로
    input_path = "data/scraped/raw_incheon_incheon.csv"
    output_path = "data/scraped/raw_incheon_incheon.csv" 
    
    if os.path.exists(input_path):
        result_df = preprocess_csv(input_path)
        
        try:
            # 저장 시에는 가장 범용적인 utf-8-sig (엑셀 호환) 사용
            result_df.to_csv(output_path, index=False, encoding='utf-8-sig')
            print(f"✅ 복구 완료된 결과가 '{output_path}'에 저장되었습니다.")
        except PermissionError:
            print(f"❌ 에러: 파일이 열려 있습니다. 종료 후 다시 시도하세요.")