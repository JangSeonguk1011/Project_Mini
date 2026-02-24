"""
강원도민일보 크롤러
강원도 지역 경제 뉴스 수집
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from base_crawler import BaseCrawler
from typing import List, Dict, Optional
from datetime import datetime
import re

class GangwonDominIlboCrawler(BaseCrawler):
    """강원도민일보 경제섹션 크롤러"""
    
    def __init__(self):
        config = {
            'use_selenium': False,  # BeautifulSoup로 충분
        }
        
        super().__init__(
            newspaper_name='강원도민일보',
            region='강원도',
            base_url='https://www.kado.net',
            config=config
        )
    
    def get_article_urls(self) -> List[str]:
        """
        강원도민일보 경제섹션 URL 추출
        실제 URL: https://www.kado.net/news/articleList.html?sc_section_code=S1N2
        """
        # 경제 섹션 URL (sc_section_code=S1N2)
        url = f'{self.base_url}/news/articleList.html?sc_section_code=S1N2'
        soup = self.fetch_page(url)
        
        if not soup:
            self.logger.warning("경제 섹션 페이지 가져오기 실패")
            return []
        
        urls = []
        
        # h2 태그 안의 링크 찾기 (기사 목록)
        article_headings = soup.select('h2')
        
        for heading in article_headings[:50]:  # 최대 50개
            link_elem = heading.select_one('a')
            if link_elem and link_elem.get('href'):
                href = link_elem['href']
                
                # 전체 URL 구성
                if href.startswith('http'):
                    full_url = href
                elif href.startswith('/'):
                    full_url = self.base_url + href
                else:
                    full_url = self.base_url + '/' + href
                
                # articleView가 포함된 URL만 (실제 기사)
                if 'articleView' in full_url:
                    urls.append(full_url)
                    self.logger.info(f"기사 URL 수집: {full_url}")
        
        self.logger.info(f"총 {len(urls)}개 기사 URL 수집 완료")
        return urls
    
    def parse_article(self, url: str) -> Optional[Dict]:
        """개별 기사 파싱"""
        soup = self.fetch_page(url)
        if not soup:
            return None
        
        try:
            # 제목 추출 (h1 태그)
            title_elem = soup.select_one('h1')
            title = title_elem.get_text(strip=True) if title_elem else ''
            
            # 본문 추출 - #article-view-content-div 내부의 텍스트
            content = ''
            
            # 실제 본문이 있는 div 찾기
            content_div = soup.select_one('#article-view-content-div, .article-veiw-body')
            
            if content_div:
                # 본문 텍스트 추출
                content = content_div.get_text(separator=' ', strip=True)
            else:
                # fallback: p 태그들 수집
                content_parts = []
                for p in soup.select('p'):
                    text = p.get_text(strip=True)
                    if text and len(text) > 20:
                        content_parts.append(text)
                content = ' '.join(content_parts)
            
            # 날짜+시간 추출 (예: "입력 2026.02.23 15:30" 또는 "입력 2026.02.23")
            published_time = ''
            date_pattern = soup.find(text=re.compile(r'입력\s*\d{4}\.\d{2}\.\d{2}'))
            if date_pattern:
                # 시간 포함 패턴 먼저 시도
                datetime_match = re.search(r'(\d{4})\.(\d{2})\.(\d{2})\s+(\d{1,2}):(\d{2})', date_pattern)
                if datetime_match:
                    published_time = f"{datetime_match.group(1)}-{datetime_match.group(2)}-{datetime_match.group(3)} {datetime_match.group(4).zfill(2)}:{datetime_match.group(5)}"
                else:
                    # 날짜만 있는 경우
                    date_match = re.search(r'(\d{4})\.(\d{2})\.(\d{2})', date_pattern)
                    if date_match:
                        published_time = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
            
            # 기자 이름 추출
            writer = ''
            writer_elem = soup.select_one('.author, .writer')
            if writer_elem:
                writer = writer_elem.get_text(strip=True)
            else:
                # 본문 끝에서 "OOO 기자" 패턴 찾기
                writer_pattern = soup.find(text=re.compile(r'[가-힣]{2,4}\s*기자'))
                if writer_pattern:
                    writer_match = re.search(r'([가-힣]{2,4})\s*기자', writer_pattern)
                    if writer_match:
                        writer = writer_match.group(1)
            
            if not title or not content:
                self.logger.warning(f"제목 또는 본문 없음: {url}")
                return None
            
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
