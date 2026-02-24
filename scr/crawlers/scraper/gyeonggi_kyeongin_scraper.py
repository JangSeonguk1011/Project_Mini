import requests
from bs4 import BeautifulSoup
import time
import re
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from utils import get_logger, get_common_headers, common_parse_date, save_to_csv, fetch_url

logger = get_logger("gyeonggi_kyeongin")

def process_article(article_url, session, headers, limit_date_str):
    """개별 기사 상세 페이지 분석"""
    try:
        # 차단 방지를 위한 추가 헤더 설정
        headers.update({
            "Referer": "https://www.kyeongin.com/money",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
        })
        
        response = fetch_url(article_url, headers, logger, session=session)
        if not response or response.status_code != 200:
            return None
            
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')

        # 1. 날짜 추출
        date_tag = soup.select_one('meta[property="article:published_time"]') or \
                   soup.select_one('div.byline span.date') or \
                   soup.select_one('.article-date') or \
                   soup.select_one('.date')
        
        if not date_tag:
            return None
        
        raw_date = date_tag.get('content') if date_tag.name == 'meta' else date_tag.get_text(strip=True)
        article_date = common_parse_date(raw_date)
        
        if article_date < limit_date_str:
            return "OLDER"

        # 2. 이미지 추출 (og:image 활용)
        image_url = ""
        img_meta = soup.select_one('meta[property="og:image"]') or soup.select_one('meta[name="og:image"]')
        if img_meta and img_meta.get('content'):
            image_url = img_meta['content']
            if not image_url.startswith('http'):
                image_url = "https:" + image_url if image_url.startswith('//') else "https://www.kyeongin.com" + image_url

        # 3. 본문 추출 (제공된 HTML 구조 반영: #article-body)
        content_tag = soup.select_one('#article-body') or \
                      soup.select_one('.article-body') or \
                      soup.select_one('.art-content') or \
                      soup.select_one('#articleBody') or \
                      soup.select_one('.view-content') or \
                      soup.select_one('.content-area')
        
        if not content_tag:
            return None

        for noise in content_tag.select('script, style, iframe, ins, .article-copy, .byline, button, .ad-template'):
            noise.decompose()
            
        content = content_tag.get_text(" ", strip=True)
        content = re.split(r'/[가-힣]{2,4}\s*기자|기자\s*=|©|저작권자|무단전재', content)[0].strip()

        if len(content) < 40:
            return None

        # 4. 제목 추출
        title_tag = soup.select_one('h2.headline') or \
                    soup.select_one('h1.title') or \
                    soup.select_one('.art-title') or \
                    soup.select_one('title')
        
        title = title_tag.get_text(strip=True) if title_tag else "제목 없음"
        title = title.split(' - ')[0].split(' | ')[0].strip()

        return {
            'date': article_date,
            'press': '경인일보',
            'region': 'gyeonggi',
            'title': title,
            'sub_title': "",
            'description': content[:150].replace("\n", " ") + "...",
            'content': content,
            'article_url': article_url,
            'image_url': image_url
        }
    except Exception:
        return None

def scrape_kyeongin_money(years=1):
    base_url = "https://www.kyeongin.com"
    news_data = []
    headers = get_common_headers()
    
    limit_date_str = (datetime.now() - timedelta(days=365 * years)).strftime('%Y-%m-%d')
    logger.info(f"수집 기준일: {limit_date_str}")

    with requests.Session() as session:
        session.headers.update(headers)
        page = 1
        total_seen_urls = set()

        while page <= 100:
            target_url = f"{base_url}/money" if page == 1 else f"{base_url}/money?page={page}"
            
            try:
                response = session.get(target_url, timeout=15)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 기사 아이템들을 개별적으로 탐색
                items = soup.select('div.list-item') or soup.select('li')
                
                links_to_process = []
                for item in items:
                    # 1. 날짜 확인
                    date_span = item.select_one('span.date')
                    if date_span:
                        item_date = common_parse_date(date_span.get_text(strip=True))
                        if item_date < limit_date_str:
                            continue
                    
                    # 2. 링크 추출
                    a_tag = item.select_one('a[href*="/article/"]')
                    if not a_tag: continue
                    
                    href = a_tag.get('href', '')
                    if href.startswith('//'): full_url = 'https:' + href
                    elif href.startswith('/'): full_url = base_url + href
                    else: full_url = href
                    
                    if full_url not in total_seen_urls:
                        links_to_process.append(full_url)
                        total_seen_urls.add(full_url)
                
                # 중복 제거
                links_to_process = list(dict.fromkeys(links_to_process))
                
                if not links_to_process:
                    if page > 5: break
                    page += 1
                    continue

                logger.info(f"Page {page}: {len(links_to_process)}개 분석 시도...")
                page_data = []
                older_count = 0
                
                with ThreadPoolExecutor(max_workers=5) as executor:
                    results = list(executor.map(lambda url: process_article(url, session, headers, limit_date_str), links_to_process))
                    
                    for res in results:
                        if res == "OLDER":
                            older_count += 1
                        elif res:
                            page_data.append(res)

                news_data.extend(page_data)
                logger.info(f"Page {page} 결과: {len(page_data)}개 성공 (과거 제외: {older_count})")

                if len(links_to_process) > 0 and (older_count >= len(links_to_process) * 0.7):
                    logger.info("기준일 이전 기사에 도달했습니다. 수집을 종료합니다.")
                    break
                
                page += 1
                time.sleep(0.8)

            except Exception as e:
                logger.error(f"페이지 {page} 처리 중 에러: {e}")
                break
                
    return news_data

if __name__ == "__main__":
    results = scrape_kyeongin_money(years=1)
    save_to_csv(results, "data/raw_gyeonggi_kyeongin.csv", logger)
