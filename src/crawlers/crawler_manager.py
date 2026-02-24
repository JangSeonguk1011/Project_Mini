"""
크롤러 매니저
여러 지역 크롤러를 통합 관리
"""

import pandas as pd
from typing import List, Dict
import logging

# 지역별 크롤러 임포트
from regional.seoul.seoul_shinmun import SeoulShinmunCrawler
from regional.gyeonggi.gyeonggi_ilbo import GyeonggiIlboCrawler
from regional.gangwon.gangwon_domin_ilbo import GangwonDominIlboCrawler
from regional.chungcheong.daejon_ilbo import ChungcheongCrawler
from regional.gyeongsang.busan_ilbo import GyeongsangCrawler
from regional.jeolla.jeonnam_ilbo import JeollaCrawler

# 데이터베이스 및 텍스트 파일 저장
from database_manager import DatabaseManager
from text_file_saver import TextFileSaver

logger = logging.getLogger('CrawlerManager')


class CrawlerManager:
    """지역별 크롤러를 통합 관리"""

    def __init__(self, use_database: bool = True, save_text_files: bool = True):
        """
        Args:
            use_database: 데이터베이스 사용 여부
            save_text_files: 텍스트 파일 저장 여부
        """
        self.crawlers = []
        self.all_articles = []
        self.region_stats = {}

        # 데이터베이스 매니저
        self.use_database = use_database
        if use_database:
            self.db_manager = DatabaseManager()

        # 텍스트 파일 저장
        self.save_text_files = save_text_files
        if save_text_files:
            self.text_saver = TextFileSaver()

    def register_crawler(self, crawler):
        """크롤러 등록"""
        self.crawlers.append(crawler)
        logger.info(f"✓ {crawler.newspaper_name} 크롤러 등록")

    def register_all_crawlers(self):
        """모든 지역 크롤러 기본 등록"""
        crawlers_list = [
            SeoulShinmunCrawler(),
            GyeonggiIlboCrawler(),
            GangwonDominIlboCrawler(),
            ChungcheongCrawler(),
            GyeongsangCrawler(),
            JeollaCrawler(),
        ]

        for crawler in crawlers_list:
            self.register_crawler(crawler)

    def run_by_region(self, region: str, max_articles: int = 50) -> List[Dict]:
        """
        특정 지역의 크롤러만 실행

        Args:
            region: 지역명 (예: '서울', '경기도', '강원도')
            max_articles: 신문사당 최대 기사 수
        """
        target_crawlers = [c for c in self.crawlers if c.region == region]

        logger.info(f"\n{'=' * 60}")
        logger.info(f"🕷️  [{region}] 크롤링 시작 ({len(target_crawlers)}개 신문)")
        logger.info(f"{'=' * 60}\n")

        for crawler in target_crawlers:
            articles = crawler.crawl(max_articles=max_articles)
            self.all_articles.extend(articles)

        return self.all_articles

    def run_all_crawlers(self, max_articles: int = 50) -> List[Dict]:
        """
        모든 지역의 모든 크롤러 실행

        Args:
            max_articles: 신문사당 최대 기사 수
        """
        logger.info(f"\n\n{'=' * 70}")
        logger.info("🕷️  [전체] 지역별 뉴스 크롤링 시작")
        logger.info(f"    - 크롤러 수: {len(self.crawlers)}개")
        logger.info(f"    - 신문사당 기사 수: {max_articles}개")
        logger.info(f"{'=' * 70}\n")

        for idx, crawler in enumerate(self.crawlers, 1):
            logger.info(f"[{idx}/{len(self.crawlers)}] {crawler.newspaper_name}({crawler.region})")
            articles = crawler.crawl(max_articles=max_articles)
            self.all_articles.extend(articles)

            # 지역별 통계
            self.region_stats[crawler.region] = self.region_stats.get(crawler.region, 0) + len(articles)

        logger.info(f"\n{'=' * 70}")
        logger.info(f"✓ 전체 크롤링 완료: {len(self.all_articles)}개 기사 수집")
        logger.info(f"{'=' * 70}\n")

        return self.all_articles

    def to_dataframe(self) -> pd.DataFrame:
        """모든 기사를 DataFrame으로 반환"""
        if not self.all_articles:
            return pd.DataFrame()
        return pd.DataFrame(self.all_articles).sort_values('date', ascending=False).reset_index(drop=True)

    def save_to_csv(self, filename: str = '../data/regional_news.csv'):
        """CSV 파일로 저장 (기존 데이터 유지하고 새로운 데이터 추가/업데이트)"""
        df = self.to_dataframe()
        if df.empty:
            logger.warning("저장할 데이터가 없습니다.")
            return

        import os
        import tempfile
        import shutil
        import gc
        
        # 절대 경로 계산 (크롤러는 src/crawlers/에 있음)
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        csv_path = os.path.join(project_root, 'data', 'regional_news.csv')
        
        # 기존 CSV 파일이 있으면 읽기
        if os.path.exists(csv_path):
            try:
                existing_df = pd.read_csv(csv_path, low_memory=False)
                logger.info(f"기존 CSV 파일 로드: {len(existing_df)}개 기사")
                
                # 새로운 데이터와 기존 데이터 합치기
                combined_df = pd.concat([df, existing_df], ignore_index=True)
                
                # URL 기준으로 중복 제거 (최신 데이터 우선)
                combined_df = combined_df.drop_duplicates(subset=['url'], keep='first')
                
                # 날짜 기준으로 정렬
                combined_df = combined_df.sort_values('date', ascending=False).reset_index(drop=True)
                
                logger.info(f"기존 + 새로운 데이터 병합: {len(combined_df)}개 기사 (중복 제거)")
                df = combined_df
                
                # 메모리 정리
                del existing_df
                gc.collect()
                
            except Exception as e:
                logger.warning(f"기존 CSV 파일 읽기 실패: {e}. 새로운 파일로 저장합니다.")
        
        # CSV 저장
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        
        # 임시 파일 경로
        temp_csv = csv_path + '.tmp'
        
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries:
            try:
                # 임시 파일에 먼저 저장
                df.to_csv(temp_csv, index=False, encoding='utf-8-sig')
                gc.collect()
                
                # 기존 파일 제거 시도
                if os.path.exists(csv_path):
                    try:
                        os.remove(csv_path)
                    except OSError as e:
                        logger.debug(f"기존 파일 제거 실패 (재시도): {e}")
                        retry_count += 1
                        if retry_count < max_retries:
                            import time
                            time.sleep(0.5)
                            continue
                        else:
                            # 파일을 못 제거해도 원본을 다른 이름으로 저장하고 새 내용으로 덮어쓰기
                            backup = csv_path + '.bak'
                            if os.path.exists(backup):
                                try:
                                    os.remove(backup)
                                except:
                                    pass
                            shutil.copy(csv_path, backup)
                            logger.debug(f"기존 파일을 {backup}으로 백업")
                
                # 임시 파일을 최종 위치로 이동
                if os.path.exists(temp_csv):
                    shutil.move(temp_csv, csv_path)
                    
                logger.info(f"\n✓ CSV 파일 저장 완료: {csv_path}")
                logger.info(f"  - 전체 기사: {len(df)}개")
                logger.info(f"  - 수집 지역: {sorted(df['region'].unique().tolist())}")
                logger.info(f"  - 수집 신문: {sorted(df['source'].unique().tolist())}")
                break
                
            except Exception as e:
                logger.debug(f"CSV 저장 시도 #{retry_count + 1} 실패: {e}")
                retry_count += 1
                if retry_count >= max_retries:
                    # 마지막 시도 - 임시 파일 경로에 저장
                    fallback_path = csv_path + '_latest.csv'
                    try:
                        df.to_csv(fallback_path, index=False, encoding='utf-8-sig')
                        logger.error(f"CSV 파일을 {fallback_path}에 저장했습니다")
                        logger.error(f"원본 파일 ({csv_path})이 다른 프로세스에서 사용 중입니다")
                        raise PermissionError(f"파일이 잠금 상태입니다. 대신 {fallback_path}에 저장되었습니다.") from e
                    except Exception as fallback_error:
                        logger.error(f"모든 저장 시도 실패: {fallback_error}")
                        raise
                else:
                    import time
                    time.sleep(0.5)

    def save_to_database(self):
        """데이터베이스에 저장"""
        if not self.use_database:
            logger.warning("데이터베이스가 활성화되지 않았습니다.")
            return

        if not self.all_articles:
            logger.warning("저장할 데이터가 없습니다.")
            return

        logger.info(f"\n{'=' * 70}")
        logger.info("💾 데이터베이스 저장 중...")
        logger.info(f"{'=' * 70}")

        # 기사 저장
        inserted = self.db_manager.insert_articles(self.all_articles)

        # 지역별 통계 업데이트
        for region, count in self.region_stats.items():
            newspapers = [a['newspaper'] for a in self.all_articles if a['region'] == region]
            for newspaper in set(newspapers):
                news_count = sum(1 for a in self.all_articles if a['region'] == region and a['newspaper'] == newspaper)
                self.db_manager.update_region_stats(region, newspaper, news_count)

        logger.info(f"✓ {inserted}개 기사 데이터베이스 저장 완료")
        
        # 30일 이전 기사 자동 삭제
        self.db_manager.delete_old_articles(days=30)

        # 통계 출력
        self.db_manager.print_stats()

    def save_as_text_files(self):
        """원본 뉴스를 텍스트 파일로 저장"""
        if not self.save_text_files:
            logger.warning("텍스트 파일 저장이 활성화되지 않았습니다.")
            return

        if not self.all_articles:
            logger.warning("저장할 데이터가 없습니다.")
            return

        logger.info(f"\n{'=' * 70}")
        logger.info("📄 텍스트 파일 저장 중...")
        logger.info(f"{'=' * 70}")

        # 개별 텍스트 파일 저장
        saved_count = self.text_saver.save_articles(self.all_articles)

        # 인덱스 파일 생성
        self.text_saver.create_index_file(self.all_articles)

        logger.info(f"✓ {saved_count}개 기사를 텍스트 파일로 저장 완료")

    def save_all(self, csv_filename: str = '../../data/regional_news.csv'):
        """
        모든 포맷으로 저장 (CSV + 데이터베이스 + 텍스트 파일)

        Args:
            csv_filename: CSV 파일 경로
        """
        logger.info(f"\n{'=' * 70}")
        logger.info("💾 데이터 저장 시작")
        logger.info(f"{'=' * 70}\n")

        # 1. CSV 저장
        self.save_to_csv(csv_filename)

        # 2. 데이터베이스 저장
        if self.use_database:
            self.save_to_database()

        # 3. 텍스트 파일 저장
        if self.save_text_files:
            self.save_as_text_files()

        logger.info(f"\n{'=' * 70}")
        logger.info("✅ 모든 데이터 저장 완료!")
        logger.info(f"{'=' * 70}\n")

    def print_stats(self):
        """수집 통계 출력"""
        df = self.to_dataframe()

        if df.empty:
            logger.warning("수집된 데이터가 없습니다.")
            return

        logger.info(f"\n{'=' * 70}")
        logger.info("📊 수집 통계")
        logger.info(f"{'=' * 70}")

        # 지역별 통계
        logger.info("\n📍 지역별 기사 수:")
        region_stats = df.groupby('region').size().sort_values(ascending=False)
        for region, count in region_stats.items():
            logger.info(f"  {region}: {count}개")

        # 신문사별 통계
        logger.info("\n📰 신문사별 기사 수:")
        newspaper_stats = df.groupby('source').size().sort_values(ascending=False)
        for source, count in newspaper_stats.items():
            logger.info(f"  {source}: {count}개")

        logger.info(f"\n{'=' * 70}\n")
