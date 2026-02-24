"""
경상뉴스 크롤러
경상도 지역 경제 뉴스 수집
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from base_crawler import BaseCrawler
from typing import List, Dict, Optional
from datetime import datetime
import re


class GyeongsangCrawler(BaseCrawler):
    """경상뉴스 경제섹션 크롤러"""

    def __init__(self):
        config = {
            'use_selenium': False,
        }

        super().__init__(
            newspaper_name='경상뉴스',
            region='경상도',
            base_url='http://m.ynews.kr',
            config=config
        )

    def get_article_urls(self) -> List[str]:
        url = f'{self.base_url}/list.php?part_idx=300'
        soup = self.fetch_page(url)
        if not soup:
            return []

        urls = []
        for link_elem in soup.select('.list_type1 li a[href*="view.php"]'):
            href = link_elem.get('href')
            if not href:
                continue
            full_url = href if href.startswith('http') else f'{self.base_url}/' + href.lstrip('/')
            if full_url not in urls:
                urls.append(full_url)

        return urls

    def parse_article(self, url: str) -> Optional[Dict]:
        soup = self.fetch_page(url)
        if not soup:
            return None

        try:
            # 제목 추출: 여러 선택자 시도 (h1, h2, span 등)
            title_elem = soup.select_one('h1') or \
                        soup.select_one('.view_top h2') or \
                        soup.select_one('span.title') or \
                        soup.select_one('div.title-wrap h2')
            title = title_elem.get_text(strip=True) if title_elem else ''
            
            # 제목이 없으면 첫 번째 큰 텍스트 찾기
            if not title:
                all_text = soup.get_text()
                # 개행으로 구분된 첫 줄에서 제목 추출
                lines = [line.strip() for line in all_text.split('\n') if len(line.strip()) > 5]
                if lines:
                    title = lines[0][:100]

            # 본문 추출: 여러 선택자 시도
            content_tag = soup.select_one('#view_con') or \
                soup.select_one('.view_con') or \
                soup.select_one('#contents .view_con') or \
                soup.select_one('.article_content') or \
                soup.select_one('div.view-content') or \
                soup.select_one('article')

            content = ''
            if content_tag:
                # 불필요한 요소 제거
                for s in content_tag.select('script, style, button, ins, .ad, .advertisement'):
                    s.decompose()
                content = content_tag.get_text(separator=' ', strip=True)
            
            # 본문이 없으면 모든 p/div 태그 수집
            if not content:
                paragraphs = soup.select('p, div.content')
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