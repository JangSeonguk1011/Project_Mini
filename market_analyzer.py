import pandas as pd
import numpy as np
import FinanceDataReader as fdr
import pyupbit
import sqlite3 # VS Code에서 가장 많이 쓰이는 내장 DB 라이브러리
from datetime import timedelta

# [1] 데이터베이스 연결 및 데이터 추출
# 프로젝트 폴더 내에 있는 db 파일 이름을 입력하세요 (예: news_data.db)
db_path = 'your_database_name.db' 

try:
    conn = sqlite3.connect(db_path)
    # 질문하신 변수명 그대로 적용 (published_time, sentiment_score 등)
    query = """
    SELECT published_time, sentiment_score, title, url 
    FROM news_table 
    WHERE is_processed = 1
    """
    df_news_raw = pd.read_sql(query, conn)
    conn.close()
    print("성공: DB에서 데이터를 불러왔습니다.")
except Exception as e:
    print(f"오류: DB 연결 실패 - {e}")

# [2] 분석용 데이터 가공 (주말 뉴스를 월요일로 통합)
df_analysis = df_news_raw[['published_time', 'sentiment_score']].copy()
df_analysis['published_time'] = pd.to_datetime(df_analysis['published_time'])

# 주말(토, 일) 날짜를 월요일로 조정하는 함수
def adjust_weekend_to_monday(dt):
    if dt.weekday() == 5:     # 토요일
        return dt + timedelta(days=2)
    elif dt.weekday() == 6:   # 일요일
        return dt + timedelta(days=1)
    return dt

# 날짜 조정 및 날짜별 평균 점수 산출
df_analysis['adjusted_date'] = df_analysis['published_time'].apply(adjust_weekend_to_monday).dt.date
df_news_daily = df_analysis.groupby('adjusted_date')['sentiment_score'].mean().reset_index()
df_news_daily.columns = ['time', 'sentiment_score']

# [3] 시장 데이터(KOSPI, KOSDAQ, 코인 10종) 가져오기
start_date = df_news_daily['time'].min().strftime('%Y%m%d')
end_date = df_news_daily['time'].max().strftime('%Y%m%d')

# 주식 데이터
kospi = fdr.DataReader('KS11', start_date, end_date)[['Close']].rename(columns={'Close': 'KOSPI'})
kosdaq = fdr.DataReader('KQ11', start_date, end_date)[['Close']].rename(columns={'Close': 'KOSDAQ'})

# 코인 데이터 (상위 10개)
tickers = pyupbit.get_tickers(fiat="KRW")[:10]
coin_list = []
for ticker in tickers:
    df_c = pyupbit.get_ohlcv(ticker, interval="day", count=100)
    if df_c is not None:
        df_c = df_c.loc[start_date:end_date, ['close']].rename(columns={'close': ticker})
        coin_list.append(df_c)
df_coins = pd.concat(coin_list, axis=1)

# [4] 데이터 통합 및 상관계수 산출
# 날짜 형식 통일
for df in [kospi, kosdaq, df_coins]:
    df.index = pd.to_datetime(df.index).date

df_market = pd.concat([kospi, kosdaq, df_coins], axis=1)
df_final = pd.merge(df_news_daily, df_market, left_on='time', right_index=True, how='inner')

# 수익률(변동폭) 기반 상관계수 산출
df_returns = df_final.set_index('time').pct_change().dropna()
correlations = df_returns.corr()['sentiment_score'].sort_values(ascending=False)

print("\n--- 분석 완료: 뉴스 감성과 자산 수익률 간 상관계수(r) ---")
print(correlations)