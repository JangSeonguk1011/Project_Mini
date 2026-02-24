"""
서울신문 크롤러
서울 지역 경제 뉴스 수집
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_crawler import BaseCrawler
from typing import List, Dict, Optional
from datetime import datetime
import re

class SeoulShinmunCrawler(BaseCrawler):
    """서울신문 경제섹션 크롤러"""
    
    def __init__(self):
        config = {
            'article_selector': 'a',
            'title_selector': 'h1',
            'content_selector': 'div.article-body',
            'date_selector': 'span.date',
        }
        
        super().__init__(
            newspaper_name='서울신문',
            region='서울',
            base_url='https://www.seoul.co.kr',
            config=config
        )
    
    def get_article_urls(self) -> List[str]:
        """
        서울신문 경제섹션 URL 추출
        """
        # 서울신문 경제 섹션 URL
        url = f'{self.base_url}/newsList/economy/'
        soup = self.fetch_page(url)
        
        if not soup:
            return []
        
        urls = []
        # 경제 뉴스 기사 링크 추출
        articles = soup.select('a[href*="/news/economy/"]')
        
        for article in articles[:50]:  # 최대 50개
            href = article.get('href')
            if href and '/news/economy/' in href:
                full_url = href if href.startswith('http') else self.base_url + href
                if full_url not in urls:  # 중복 제거
                    urls.append(full_url)
        
        return urls
    
    def parse_article(self, url: str) -> Optional[Dict]:
        """개별 기사 파싱"""
        soup = self.fetch_page(url)
        if not soup:
            return None
        
        try:
            # 제목 추출
            title_elem = soup.select_one('h1')
            title = title_elem.get_text(strip=True) if title_elem else ''
            
            # 본문 추출 - viewContent 클래스에서 텍스트 수집
            content_div = soup.select_one('div.viewContent, div.viewContentWrap, div#articleContent')
            
            if content_div:
                # 불필요한 요소들 제거
                for unwanted in content_div.select('script, style, iframe, .ad, .advertisement, div[id*="ad"], div[id*="Ad"], div[class*="ad"], img, button'):
                    unwanted.decompose()
                
                # 텍스트 추출 (줄바꿈 보존)
                text = content_div.get_text(separator='\n', strip=True)
                
                # 줄 단위로 분리하여 필터링
                lines = text.split('\n')
                content_parts = []
                
                for line in lines:
                    line = line.strip()
                    # 의미있는 텍스트만 수집
                    if (len(line) > 20 and 
                        not any(keyword in line for keyword in [
                            '저작권', 'Copyright', '무단', '전재', '배포금지',
                            'googletag', 'display:', 'width:', 'margin:', 'padding:',
                            'MobileAd', 'function()', 'cmd.push', 'gpt-ad',
                            'src=', 'href=', 'class=', 'div>', '<img', '<div',
                            'window.', 'document.', '.jpg', '.png', '.webp',
                            '기사를', '듣나요', 'AI 음성'
                        ]) and
                        not line.startswith('/') and  # URL 경로 제외
                        not re.match(r'^[\d\s\-:]+$', line)):  # 숫자/날짜만 있는 줄 제외
                        content_parts.append(line)
                
                content = ' '.join(content_parts)
            else:
                # fallback: p 태그에서 추출
                content_paragraphs = soup.select('p')
                content_parts = [p.get_text(strip=True) for p in content_paragraphs if len(p.get_text(strip=True)) > 20]
                content = ' '.join(content_parts)
            
            # 전체 페이지 텍스트에서 날짜와 작성자 추출
            page_text = soup.get_text()
            
            # 날짜+시간 추출 (다양한 형식 지원)
            published_time = ''
            # YYYY-MM-DD HH:MM 또는 YYYY.MM.DD HH:MM 형식
            datetime_match = re.search(r'(\d{4})[-./](\d{2})[-./](\d{2})\s+(\d{1,2}):(\d{2})', page_text)
            if datetime_match:
                published_time = f"{datetime_match.group(1)}-{datetime_match.group(2)}-{datetime_match.group(3)} {datetime_match.group(4).zfill(2)}:{datetime_match.group(5)}"
            else:
                # 날짜만 있는 경우
                date_match = re.search(r'(\d{4})[-./](\d{2})[-./](\d{2})', page_text)
                if date_match:
                    published_time = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
            
            # 작성자 추출 ("XXX 기자" 패턴)
            writer = ''
            writer_match = re.search(r'([가-힣]{2,4})\s*기자', page_text)
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
