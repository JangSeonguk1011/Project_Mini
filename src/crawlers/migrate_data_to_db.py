import os
import re
import logging
from typing import Dict
from datetime import datetime
from database_manager import DatabaseManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('DataMigration')

class DataMigrator:

    def __init__(self):
        self.articles_dir = os.path.join(
            os.path.dirname(__file__), '..', '..', 'data', 'articles'
        )
        self.db_manager = DatabaseManager()

    def extract_article_data(self, file_path: str) -> Dict:
        """파일에서 기사 데이터 추출 (감성분석 없음)"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            title_match = re.search(r'^제목:\s*(.+?)$', content, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else ""

            region_match = re.search(r'^지역:\s*(.+?)$', content, re.MULTILINE)
            region = region_match.group(1).strip() if region_match else ""

            published_match = re.search(r'^발행일:\s*(.+?)$', content, re.MULTILINE)
            published_time = published_match.group(1).strip() if published_match else ""

            if not published_time:
                collected_match = re.search(r'^수집일시:\s*(.+?)$', content, re.MULTILINE)
                published_time = collected_match.group(1).strip() if collected_match else ""

            url_match = re.search(r'^URL:\s*(.+?)$', content, re.MULTILINE)
            url = url_match.group(1).strip() if url_match else ""

            body_start = content.find('본문:')
            body_end = content.rfind('=' * 30)

            body = ""
            if body_start != -1:
                body = content[body_start + len('본문:'):body_end].strip()
                body = re.sub(r'신용회복위원회.*$', '', body, flags=re.DOTALL).strip()

            return {
                'title': title,
                'content': body,
                'region': region,
                'sentiment_score': 0,  # 분석 전
                'is_processed': 0,        # analyzer가 처리
                'published_time': published_time,
                'url': url,
               
            }

        except Exception as e:
            logger.error(f"파일 처리 실패 {file_path}: {e}")
            return None

    def migrate_articles(self):
        total_articles = 0
        migrated_articles = 0

        for region_folder in os.listdir(self.articles_dir):
            region_path = os.path.join(self.articles_dir, region_folder)

            if not os.path.isdir(region_path):
                continue

            logger.info(f"\n📂 처리 중: {region_folder}")
            articles_batch = []

            for file_name in os.listdir(region_path):
                if not file_name.endswith('.txt'):
                    continue

                file_path = os.path.join(region_path, file_name)
                total_articles += 1

                article_data = self.extract_article_data(file_path)

                if article_data and article_data['title'] and article_data['url']:
                    articles_batch.append(article_data)
                    migrated_articles += 1
                else:
                    logger.warning(f"  ✗ 데이터 추출 실패: {file_name}")

            if articles_batch:
                inserted = self.db_manager.insert_articles(articles_batch)
                logger.info(f"✓ {region_folder}: {inserted}개 저장 완료")

        logger.info(f"\n{'='*70}")
        logger.info("📊 마이그레이션 완료 (감성분석 미수행)")
        logger.info(f"총 처리 파일: {total_articles}개")
        logger.info(f"성공적으로 마이그레이션: {migrated_articles}개")
        logger.info("모든 데이터 is_processed = 0 상태")
        logger.info(f"{'='*70}\n")

        self.db_manager.print_stats()

def main():
    logger.info("🚀 데이터 마이그레이션 시작...")
    migrator = DataMigrator()
    migrator.migrate_articles()


if __name__ == '__main__':
    main()