"""
텍스트 파일 저장 모듈
크롤링된 원본 뉴스를 텍스트 파일로 저장
"""

import os
import logging
from typing import List, Dict
from datetime import datetime
import re

logger = logging.getLogger('TextFileSaver')

class TextFileSaver:
    """원본 뉴스를 텍스트 파일로 저장"""
    
    def __init__(self, base_dir: str = 'data/articles'):
        """
        Args:
            base_dir: 텍스트 파일 저장 기본 경로
        """
        # 프로젝트 루트 기준으로 경로 설정
        if os.path.isabs(base_dir):
            self.base_dir = base_dir
        else:
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            self.base_dir = os.path.join(project_root, base_dir)
        self._create_directories()
    
    def _create_directories(self):
        """지역별 디렉토리 생성"""
        regions = ['서울', '경기도', '강원도', '충청도', '경상도', '전라도']
        
        for region in regions:
            region_dir = os.path.join(self.base_dir, region)
            os.makedirs(region_dir, exist_ok=True)
        
        logger.info(f"✓ 텍스트 파일 저장 경로: {self.base_dir}")
    
    def _sanitize_filename(self, text: str) -> str:
        """
        파일명으로 사용 가능하도록 문자열 정제
        
        Args:
            text: 원본 텍스트
        
        Returns:
            정제된 텍스트
        """
        # 특수문자 제거
        text = re.sub(r'[<>:"/\\|?*]', '', text)
        # 공백을 언더스코어로
        text = text.replace(' ', '_')
        # 길이 제한 (최대 100자)
        if len(text) > 100:
            text = text[:100]
        return text
    
    def save_article(self, article: Dict) -> str:
        """
        개별 기사를 텍스트 파일로 저장
        
        Args:
            article: 기사 딕셔너리
        
        Returns:
            저장된 파일 경로
        """
        try:
            # 파일명 생성
            title = article.get('title', 'untitled')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{self._sanitize_filename(title)}.txt"
            
            # 지역별 경로
            region = article.get('region', 'unknown')
            region_dir = os.path.join(self.base_dir, region)
            os.makedirs(region_dir, exist_ok=True)
            
            filepath = os.path.join(region_dir, filename)
            
            # 텍스트 파일 작성
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("="*70 + "\n")
                f.write(f"제목: {article.get('title', 'N/A')}\n")
                f.write("="*70 + "\n\n")
                
                f.write(f"신문사: {article.get('source', 'N/A')}\n")
                f.write(f"지역: {article.get('region', 'N/A')}\n")
                f.write(f"발행일: {article.get('date', 'N/A')}\n")
                f.write(f"기자: {article.get('writer', 'N/A')}\n")
                f.write(f"URL: {article.get('url', 'N/A')}\n")
                f.write(f"수집일시: {article.get('collected_at', 'N/A')}\n")
                f.write("\n" + "-"*70 + "\n\n")
                
                f.write("본문:\n\n")
                f.write(article.get('content', 'N/A'))
                f.write("\n\n" + "="*70 + "\n")
            
            logger.debug(f"✓ 파일 저장: {filename}")
            return filepath
        
        except Exception as e:
            logger.error(f"✗ 파일 저장 실패: {e}")
            return None
    
    def save_articles(self, articles: List[Dict]) -> int:
        """
        여러 기사를 텍스트 파일로 저장
        
        Args:
            articles: 기사 딕셔너리 리스트
        
        Returns:
            저장된 파일 수
        """
        if not articles:
            logger.warning("저장할 기사가 없습니다.")
            return 0
        
        saved_count = 0
        for article in articles:
            filepath = self.save_article(article)
            if filepath:
                saved_count += 1
        
        logger.info(f"✓ {saved_count}개 기사를 텍스트 파일로 저장")
        return saved_count
    
    def create_index_file(self, articles: List[Dict]):
        """
        저장된 기사의 인덱스 파일 생성
        
        Args:
            articles: 기사 딕셔너리 리스트
        """
        index_path = os.path.join(self.base_dir, 'index.txt')
        
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write("="*70 + "\n")
            f.write("크롤링된 뉴스 기사 인덱스\n")
            f.write(f"생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"전체 기사 수: {len(articles)}개\n")
            f.write("="*70 + "\n\n")
            
            # 지역별 그룹화
            regions = {}
            for article in articles:
                region = article.get('region', 'unknown')
                if region not in regions:
                    regions[region] = []
                regions[region].append(article)
            
            for region, region_articles in regions.items():
                f.write(f"\n📍 {region} ({len(region_articles)}개)\n")
                f.write("-"*70 + "\n")
                
                for idx, article in enumerate(region_articles, 1):
                    f.write(f"{idx}. {article.get('title', 'N/A')}\n")
                    f.write(f"   신문: {article.get('source', 'N/A')} | ")
                    f.write(f"날짜: {article.get('date', 'N/A')}\n")
                    f.write(f"   URL: {article.get('url', 'N/A')}\n\n")
        
        logger.info(f"✓ 인덱스 파일 생성: {index_path}")
