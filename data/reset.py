import sqlite3

conn = sqlite3.connect("data/news.db")
cursor = conn.cursor()

cursor.execute("""
    UPDATE news
    SET is_processed = 0,
        sentiment_score = 0
""")

conn.commit()
conn.close()

print("초기화 완료")