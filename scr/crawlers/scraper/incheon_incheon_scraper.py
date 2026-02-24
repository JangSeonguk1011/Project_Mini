import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from utils import get_logger, get_common_headers, common_parse_date, save_to_csv, fetch_article_details, fetch_url

# 로거 설정
logger = get_logger("incheon_incheon")

def process_article(item, base_url, session, headers, limit_date):
    """개별 기사 처리 (세션 사용)"""
    try:
        date_tag = item.select_one('span.byline em:last-child') or item.select_one('.date')
        if not date_tag: return None
        
        formatted_date = common_parse_date(date_tag.get_text(strip=True))
        if formatted_date < limit_date: return "OLDER"

        title_tag = item.select_one('h2.titles a') or item.select_one('.titles a')
        if not title_tag: return None
        
        article_url = title_tag['href']
        if not article_url.startswith('http'): article_url = base_url + article_url
        
        # 상세 정보 수집 (세션 공유 및 재시도 로직 적용)
        details = fetch_article_details(article_url, {
            'sub_title': ['h2.subheading', 'div.sub-title', '.sub-title'],
            'content': ['div#article-view-content-div', 'div.article-view-content-div', '.article-body', '#articleBody']
        }, headers, logger, session=session)

        description = item.select_one('p.lead').get_text(strip=True) if item.select_one('p.lead') else ""
        if not description and details['content']:
            description = details['content'][:150] + "..."

        return {
            'date': formatted_date,
            'press': '인천일보',
            'region': 'incheon',
            'title': title_tag.get_text(strip=True),
            'sub_title': details['sub_title'],
            'description': description,
            'content': details['content'],
            'article_url': article_url,
            'image_url': item.select_one('img')['src'] if item.select_one('img') else ""
        }
    except:
        return None

def scrape_incheon_ilbo(years=1):
    base_url = "https://www.incheonilbo.com"
    target_url_base = f"{base_url}/news/articleList.html?sc_section_code=S1N4&view_type=sm"
    news_data = []
    headers = get_common_headers()
    limit_date = (datetime.now() - timedelta(days=365 * years)).strftime('%Y-%m-%d')
    logger.info(f"Starting Incheon parallel collection until {limit_date}...")

    with requests.Session() as session:
        session.headers.update(headers)
        page = 1
        while page <= 1000:
            target_url = f"{target_url_base}&page={page}"
            try:
                # 목록 페이지 요청 시 fetch_url 사용
                response = fetch_url(target_url, headers, logger, session=session)
                if not response or response.status_code != 200: break
                
                # 인코딩 강제 설정 (한글 깨짐 방지)
                response.encoding = 'utf-8'
                
                soup = BeautifulSoup(response.text, 'html.parser')
                items = soup.select('section#section-list ul.type2 > li') or soup.select('.list-block li')
                if not items: break
                
                logger.info(f"Page {page}: Processing {len(items)} items...")
                page_data = []
                reached_limit = False
                
                with ThreadPoolExecutor(max_workers=10) as executor:
                    results = list(executor.map(lambda it: process_article(it, base_url, session, headers, limit_date), items))
                    for res in results:
                        if res == "OLDER": reached_limit = True
                        elif res and isinstance(res, dict):
                            if not any(d['article_url'] == res['article_url'] for d in news_data):
                                page_data.append(res)
                
                news_data.extend(page_data)
                logger.info(f"Page {page} added {len(page_data)} items. Total: {len(news_data)}")
                
                if reached_limit: break
                page += 1
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"Error on Page {page}: {e}")
                break
                
    return news_data

if __name__ == "__main__":
    results = scrape_incheon_ilbo(years=1)
    save_to_csv(results, "data/raw_incheon_incheon.csv", logger)
