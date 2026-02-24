"""
전남일보 크롤러
전라도 지역 경제 뉴스 수집
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from base_crawler import BaseCrawler
from typing import List, Dict, Optional
from datetime import datetime
import re


class JeollaCrawler(BaseCrawler):
    """전남일보 경제섹션 크롤러"""

    def __init__(self):
        config = {
            'use_selenium': False,
        }

        super().__init__(
            newspaper_name='전남일보',
            region='전라도',
            base_url='https://www.jldnews.co.kr',
            config=config
        )

    def get_article_urls(self) -> List[str]:
        url = f'{self.base_url}/news/articleList.html?sc_sub_section_code=S2N24&view_type=sm'
        soup = self.fetch_page(url)
        if not soup:
            return []

        urls = []
        for item in soup.select('.altlist-webzine-item'):
            dt_tag = item.select_one('dt')
            link_elem = dt_tag.select_one('a') if dt_tag else item.select_one('a[href*="articleView"]')
            if not link_elem:
                continue
            href = link_elem.get('href')
            if not href:
                continue
            full_url = href if href.startswith('http') else self.base_url + href
            if full_url not in urls:
                urls.append(full_url)

        return urls

    def parse_article(self, url: str) -> Optional[Dict]:
        soup = self.fetch_page(url)
        if not soup:
            return None

        try:
            # 제목 추출: 여러 선택자 시도
            title_elem = soup.select_one('h1') or \
                        soup.select_one('h2.headline') or \
                        soup.select_one('div.article-title')
            title = title_elem.get_text(strip=True) if title_elem else ''

            # 본문 추출: 여러 선택자 시도
            content_div = soup.select_one('#article-view-content-div') or \
                         soup.select_one('div.article-content') or \
                         soup.select_one('div.content-body') or \
                         soup.select_one('article')
            
            content = ''
            if content_div:
                for elem in content_div.select('script, style, .ad'):
                    elem.decompose()
                content = content_div.get_text(separator=' ', strip=True)
            
            # 본문이 없으면 p 태그들 수집
            if not content:
                paragraphs = soup.select('p')
                content_parts = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20]
                content = ' '.join(content_parts)

            page_text = soup.get_text(strip=True)
            date_str = ''
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', page_text)
            if date_match:
                date_str = date_match.group(1)

            writer = ''
            writer_match = re.search(r'([가-힣]{2,4})\s*기자', page_text)
            if writer_match:
                writer = writer_match.group(1)

            if not title or not content:
                self.logger.warning(f"제목 또는 본문 없음: {url}")
                return None

            return {
                'title': title,
                'content': content,
                'url': url,
                'date': date_str,
                'writer': writer,
                'source': self.newspaper_name,
                'collected_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            self.logger.error(f"파싱 실패 ({url}): {e}")
            return None