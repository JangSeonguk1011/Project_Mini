"""
경기일보 크롤러
경기도 지역 경제 뉴스 수집
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from base_crawler import BaseCrawler
from typing import List, Dict, Optional
from datetime import datetime

class GyeonggiIlboCrawler(BaseCrawler):
    """경기일보 경제섹션 크롤러"""
    
    def __init__(self):
        config = {
            'article_selector': 'h3 a',  # 기사 목록의 제목 링크
            'title_selector': 'h1',
            'link_selector': 'a',
            'content_selector': 'div.article-body',  # 실제 기사 본문 컨테이너
            'date_selector': 'span.date',
        }
        
        super().__init__(
            newspaper_name='경기일보',
            region='경기도',
            base_url='https://www.kyeonggi.com',
            config=config
        )
    
    def get_article_urls(self) -> List[str]:
        """
        경기일보 경제섹션 URL 추출
        """
        # 경제 섹션 URL
        url = f'{self.base_url}/list/25'
        soup = self.fetch_page(url)
        
        if not soup:
            return []
        
        urls = []
        # h3 태그 안의 a 태그에서 기사 링크 추출
        articles = soup.select('h3 a[href*="/article/"]')
        
        for article in articles[:50]:
            href = article.get('href')
            if href:
                full_url = href if href.startswith('http') else self.base_url + href
                urls.append(full_url)
        
        return urls
    
    def parse_article(self, url: str) -> Optional[Dict]:
        """개별 기사 파싱"""
        soup = self.fetch_page(url)
        if not soup:
            return None
        import re
        
        soup = self.fetch_page(url)
        if not soup:
            return None
        
        try:
            # 제목 추출
            title_elem = soup.select_one('h1')
            title = title_elem.get_text(strip=True) if title_elem else ''
            
            # 본문 추출: 여러 p 태그로 구성된 본문을 모두 추출
            content = ''
            # 기사 본문이 여러 p 태그로 구성되어 있음
            # 본문이 위치한 컨테이너를 찾아서 그 안의 모든 텍스트를 추출
            body_paragraphs = soup.select('body p')
            if body_paragraphs:
                # 광고나 관련 기사, 저작권 정보를 제외한 본문만 추출
                content_parts = []
                # 하단 저작권 정보 필터링을 위한 노이즈 키워드
                noise_keywords = [
                    '등록번호', '등록일', '발행인', '편집·인쇄인', '사업자등록번호',
                    '통신판매업', '본사 :', '인천본사', '서울본사', '세종본사',
                    '저작권법', '무단 전재', 'Copyright', 'rights reserved',
                    '경기일보B/D', '전화 :', '경기일보의 모든 콘텐츠'
                ]
                
                for p in body_paragraphs:
                    text = p.get_text(separator=' ', strip=True)
                    
                    # 노이즈 키워드가 포함된 텍스트는 제외
                    is_noise = any(keyword in text for keyword in noise_keywords)
                    if is_noise:
                        continue
                    
                    # 짧은 텍스트나 광고성 텍스트 제외
                    if len(text) > 20 and not text.startswith('▶') and not text.startswith('●'):
                        content_parts.append(text)
                content = ' '.join(content_parts)
            
            # 날짜+시간 추출: "승인 2026-02-23 15:39" 형태
            date_text = soup.get_text()
            published_time = ''
            
            # 시간 포함 패턴 먼저 시도
            datetime_match = re.search(r'승인\s*(\d{4})[-./](\d{2})[-./](\d{2})\s+(\d{1,2}):(\d{2})', date_text)
            if datetime_match:
                published_time = f"{datetime_match.group(1)}-{datetime_match.group(2)}-{datetime_match.group(3)} {datetime_match.group(4).zfill(2)}:{datetime_match.group(5)}"
            else:
                # 날짜만 있는 경우
                date_match = re.search(r'승인\s*(\d{4}-\d{2}-\d{2})', date_text)
                if date_match:
                    published_time = date_match.group(1)
            
            # 기자 이름 추출: "김경희 기자" 형태
            writer = ''
            writer_match = re.search(r'([가-힣]{2,4})\s*기자', date_text)
            if writer_match:
                writer = writer_match.group(1)
            
            # published_time에는 날짜만 저장
            pub_date = published_time.split()[0] if ' ' in published_time else published_time
            
            return {
                'title': title,
                'content': content,
                'url': url,
                'date': pub_date,
                'published_time': pub_date,
                'writer': writer,
                'source': self.newspaper_name,
                'collected_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            self.logger.error(f"파싱 실패 ({url}): {e}")
            return None
