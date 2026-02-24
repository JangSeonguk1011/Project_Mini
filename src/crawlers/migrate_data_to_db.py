"""
기존 수집된 데이터를 새로운 데이터베이스 형식으로 마이그레이션
감성분석 및 처리 상태 적용
"""

import os
import re
import sys
import importlib.util
from pathlib import Path
from typing import Dict, List
import logging
from datetime import datetime
from database_manager import DatabaseManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('DataMigration')

# sentiment 모듈 동적 로드
def load_sentiment_analyzer():
    """sentiment 모듈 동적 로드"""
    try:
        sentiment_path = os.path.join(os.path.dirname(__file__), '..', '..', 'analyzer', 'sentiment.py')
        spec = importlib.util.spec_from_file_location("sentiment_module", sentiment_path)
        sentiment_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sentiment_module)
        return sentiment_module.NewsSentimentAnalyzer
    except Exception as e:
        logger.error(f"감성분석 모듈 로드 실패: {e}")
        return None

NewsSentimentAnalyzer = load_sentiment_analyzer()


class DataMigrator:
    """기존 데이터를 새로운 스키마로 마이그레이션"""
    
    def __init__(self):
        self.articles_dir = os.path.join(
            os.path.dirname(__file__), '..', '..', 'data', 'articles'
        )
        self.db_manager = DatabaseManager()
        self.region_mapping = {
            '경상도': '경상도',
            '충청도': '충청도',
            '전라도': '전라도',
            '강원도': '강원도',
            '경기도': '경기도',
            '서울': '서울',
        }
        
        # 감성분석기 초기화
        logger.info("🤖 감성분석 모델 로딩 중...")
        try:
            self.sentiment_analyzer = NewsSentimentAnalyzer()
            logger.info("✓ 감성분석 모델 로드 완료")
        except Exception as e:
            logger.error(f"감성분석 모델 로드 실패: {e}")
            self.sentiment_analyzer = None
    
    def extract_article_data(self, file_path: str) -> Dict:
        """파일에서 기사 데이터 추출 및 분석"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 제목 추출
            title_match = re.search(r'^제목:\s*(.+?)$', content, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else ""
            
            # 지역 추출
            region_match = re.search(r'^지역:\s*(.+?)$', content, re.MULTILINE)
            region = region_match.group(1).strip() if region_match else ""
            
            # 발행일 추출 (뉴스가 실제로 난 시간)
            published_match = re.search(r'^발행일:\s*(.+?)$', content, re.MULTILINE)
            published_time = published_match.group(1).strip() if published_match else ""
            
            # 발행일이 없으면 수집일시 사용
            if not published_time:
                collected_match = re.search(r'^수집일시:\s*(.+?)$', content, re.MULTILINE)
                published_time = collected_match.group(1).strip() if collected_match else ""
            
            # URL 추출
            url_match = re.search(r'^URL:\s*(.+?)$', content, re.MULTILINE)
            url = url_match.group(1).strip() if url_match else ""
            
            # 본문 추출
            body_start = content.find('본문:')
            body_end = content.rfind('=' * 30)
            
            body = ""
            if body_start != -1:
                body = content[body_start + 3:body_end].strip()
                # 본문 끝부분의 기자 정보 제거
                body = re.sub(r'신용회복위원회.*$', '', body, flags=re.DOTALL).strip()
                body = re.sub(r'[^\s\S]*$', '', body, flags=re.MULTILINE).strip()
            
            # 감성분석 수행
            sentiment_score = 0.0
            if self.sentiment_analyzer and body:
                try:
                    _, score = self.sentiment_analyzer.predict(body)
                    sentiment_score = float(score)
                except Exception as e:
                    logger.debug(f"감성분석 실패 {title[:30]}: {e}")
                    sentiment_score = 0.0
            
            return {
                'title': title,
                'content': body,
                'region': region,
                'sentiment_score': sentiment_score,
                'is_processed': 1,  # 마이그레이션된 데이터는 처리 완료로 표시
                'published_time': published_time,
                'url': url
            }
        
        except Exception as e:
            logger.error(f"파일 처리 실패 {file_path}: {e}")
            return None
    
    def migrate_articles(self):
        """모든 기사 데이터 마이그레이션"""
        total_articles = 0
        migrated_articles = 0
        
        # 지역별 폴더 순회
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
                    sentiment_label = "긍정" if article_data['sentiment_score'] > 0.6 else "부정" if article_data['sentiment_score'] < 0.4 else "중립"
                    logger.debug(f"  ✓ {article_data['title'][:40]}... [{sentiment_label} {article_data['sentiment_score']:.2f}]")
                else:
                    logger.warning(f"  ✗ 데이터 추출 실패: {file_name}")
            
            # 배치로 데이터베이스에 저장
            if articles_batch:
                inserted = self.db_manager.insert_articles(articles_batch)
                logger.info(f"✓ {region_folder}: {inserted}개 저장 완료 (감성분석 포함)\n")
        
        logger.info(f"\n{'='*70}")
        logger.info(f"📊 마이그레이션 완료")
        logger.info(f"{'='*70}")
        logger.info(f"총 처리 파일: {total_articles}개")
        logger.info(f"성공적으로 마이그레이션: {migrated_articles}개")
        logger.info(f"📊 감성분석: 모두 완료 (is_processed=1)")
        logger.info(f"데이터베이스 경로: {self.db_manager.db_path}")
        logger.info(f"{'='*70}\n")
        
        # 통계 출력
        self.db_manager.print_stats()


def main():
    """메인 실행 함수"""
    logger.info("🚀 데이터 마이그레이션 시작...")
    migrator = DataMigrator()
    migrator.migrate_articles()


if __name__ == '__main__':
    main()
