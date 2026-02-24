"""
충청뉴스 크롤러
충청도 지역 경제 뉴스 수집
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from base_crawler import BaseCrawler
from typing import List, Dict, Optional
from datetime import datetime
import re


class ChungcheongCrawler(BaseCrawler):
    """충청뉴스 경제섹션 크롤러"""

    def __init__(self):
        config = {
            'use_selenium': False,
        }

        super().__init__(
            newspaper_name='충청뉴스',
            region='충청도',
            base_url='http://www.ccnnews.co.kr',
            config=config
        )

    def get_article_urls(self) -> List[str]:
        url = f'{self.base_url}/news/articleList.html?sc_section_code=S1N3&view_type=sm'
        soup = self.fetch_page(url)
        if not soup:
            return []

        urls = []
        for item in soup.select('div.list-block .list-titles a'):
            href = item.get('href')
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
            # 제목 추출: h1 태그
            title_elem = soup.select_one('h1')
            title = title_elem.get_text(strip=True) if title_elem else ''

            # 제목이 없으면 첫 번째 의미있는 텍스트
            if not title:
                all_text = soup.get_text()
                lines = [line.strip() for line in all_text.split('\n') if len(line.strip()) > 10 and len(line.strip()) < 150]
                if lines:
                    title = lines[0]

            # 본문 추출: 전체 텍스트에서 추출 (가장 안정적인 방법)
            page_text = soup.get_text()
            content = ''
            
            # 기자명 뒤 "]" 찾기
            import re
            match_end_pos = page_text.find('저작권자')
            if match_end_pos == -1:
                match_end_pos = page_text.find('Copyright ⓒ')
            
            if match_end_pos > 0:
                # 기사 본문 구간 찾기: 첫 [지역_신문=기자] 패턴 이후부터
                pattern_match = re.search(r'\[[^\]]*기자\]', page_text)
                if pattern_match:
                    start_pos = pattern_match.end()
                    content = page_text[start_pos:match_end_pos].strip()
                    # 공백 정리
                    content = ' '.join(content.split())
                    # 제한 없이 전체 본문 가져오기 (최대 50000자)
                    if len(content) > 50000:
                        content = content[:50000]

            # 본문이 여전히 없으면 모든 p 태그 시도
            if not content or len(content) < 30:
                p_tags = soup.select('p')
                if p_tags:
                    p_texts = []
                    for p in p_tags:
                        text = p.get_text(strip=True)
                        if len(text) > 50:  # 긴 텍스트만
                            p_texts.append(text)
                    if p_texts:
                        content = ' '.join(p_texts[:3])

            # 날짜 추출
            # 날짜+시간 추출
            published_time = ''
            datetime_match = re.search(r'(\d{4})[-./](\d{2})[-./](\d{2})\s+(\d{1,2}):(\d{2})', page_text)
            if datetime_match:
                published_time = f"{datetime_match.group(1)}-{datetime_match.group(2)}-{datetime_match.group(3)} {datetime_match.group(4).zfill(2)}:{datetime_match.group(5)}"
            else:
                date_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', page_text)
                if date_match:
                    published_time = date_match.group(0)

            # 기자 추출
            writer = ''
            writer_match = re.search(r'([가-힣]{2,4})\s*기자', page_text)
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
            return None