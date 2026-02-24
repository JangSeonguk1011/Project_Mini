import sqlite3
import logging

# 로그 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("ResetProcessed")

def reset_is_processed(db_path="data/news.db"):
    try:
        # DB 연결
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 1인 데이터를 0으로 업데이트
        cursor.execute("UPDATE news SET is_processed = 0 WHERE is_processed = 1")
        
        # 변경된 행 수 확인
        affected_rows = cursor.rowcount
        conn.commit()
        
        logger.info(f"✅ 업데이트 완료: {affected_rows}건의 데이터가 is_processed=0으로 변경되었습니다.")

    except Exception as e:
        logger.error(f"❌ 오류 발생: {e}")
    
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    reset_is_processed()