import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from utils import get_logger, get_common_headers, common_parse_date, save_to_csv, fetch_article_details, fetch_url

# 로거 설정
logger = get_logger("jeju_jeju")

def process_article(item, base_url, session, headers, limit_date):
    """개별 기사 처리"""
    try:
        # 날짜 추출
        date_tag = item.select_one('div.list-dated')
        if not date_tag: return None
        
        formatted_date = common_parse_date(date_tag.get_text(strip=True))
        if formatted_date < limit_date: return "OLDER"

        # 제목 및 링크 추출
        title_tag = item.select_one('div.list-titles a')
        if not title_tag: return None
        
        article_url = title_tag['href']
        if not article_url.startswith('http'):
            article_url = base_url + article_url
        
        # 상세 정보 수집 (Sub Title, Content)
        details = fetch_article_details(article_url, {
            'sub_title': ['div.user-snb h2', 'div.article-head-title'],
            'content': ['article#article-view-content-div', '#articleBody']
        }, headers, logger, session=session)

        # 요약 및 이미지
        description = details.get('content', '')[:150] + "..."

        return {
            'date': formatted_date,
            'press': '제주일보',
            'region': 'jeju',
            'title': title_tag.get_text(strip=True),
            'sub_title': details.get('sub_title', ''),
            'description': description,
            'content': details.get('content', ''),
            'article_url': article_url,
            'image_url': ""
        }
    except Exception as e:
        logger.debug(f"Error processing item: {e}")
        return None

def scrape_jeju_economy(days=365):
    base_url = "http://www.jejunews.com"
    news_data = []
    headers = get_common_headers()
    limit_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    logger.info(f"Starting Jeju parallel collection until {limit_date}...")

    with requests.Session() as session:
        session.headers.update(headers)
        page = 1
        while page <= 500:
            target_url = f"{base_url}/news/articleList.html?sc_section_code=S1N5&view_type=sm&page={page}"
            try:
                response = fetch_url(target_url, headers, logger, session=session)
                if not response or response.status_code != 200: break
                
                soup = BeautifulSoup(response.text, 'html.parser')
                items = soup.select('div.list-block')
                if not items: break
                
                logger.info(f"Page {page}: Processing {len(items)} items...")
                page_data = []
                reached_limit = False
                
                with ThreadPoolExecutor(max_workers=10) as executor:
                    results = list(executor.map(lambda it: process_article(it, base_url, session, headers, limit_date), items))
                    
                    for res in results:
                        if res == "OLDER":
                            reached_limit = True
                        elif res and isinstance(res, dict):
                            if not any(d['article_url'] == res['article_url'] for d in news_data):
                                page_data.append(res)
                
                news_data.extend(page_data)
                logger.info(f"Page {page}: Added {len(page_data)} articles. Total: {len(news_data)}")
                
                if reached_limit: break
                page += 1
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"Error on Page {page}: {e}")
                break
                
    return news_data

if __name__ == "__main__":
    results = scrape_jeju_economy(days=365)
    save_to_csv(results, "data/raw_jeju_jeju.csv", logger)
