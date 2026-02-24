import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from utils import get_logger, get_common_headers, common_parse_date, save_to_csv, fetch_article_details, fetch_url

# 로거 설정
logger = get_logger("gyeongbuk_imaeil")

def process_article(item, base_url, session, headers, limit_date):
    """개별 기사 처리"""
    try:
        # 날짜 추출
        date_tag = item.select_one('p.date')
        if not date_tag: return None
        
        formatted_date = common_parse_date(date_tag.get_text(strip=True))
        if formatted_date < limit_date: return "OLDER"

        title_tag = item.select_one('p.title a')
        if not title_tag: return None
        
        article_url = title_tag['href']
        if not article_url.startswith('http'):
            article_url = base_url + article_url
        
        # 상세 정보 수집 (Sub Title, Content)
        details = fetch_article_details(article_url, {
            'sub_title': ['div.sub_title', 'p.sub_title'],
            'content': ['div.article_content', 'div.news_cnt']
        }, headers, logger, session=session)

        # 요약 정보
        desc_tag = item.select_one('p.body')
        description = desc_tag.get_text(strip=True) if desc_tag else ""

        # 이미지
        img_tag = item.select_one('div.thumb img')
        image_url = img_tag['src'] if img_tag else ""

        return {
            'date': formatted_date,
            'press': '매일신문',
            'region': 'gyeongbuk',
            'title': title_tag.get_text(strip=True),
            'sub_title': details.get('sub_title', ''),
            'description': description,
            'content': details.get('content', ''),
            'article_url': article_url,
            'image_url': image_url
        }
    except Exception as e:
        logger.debug(f"Error processing item: {e}")
        return None

def scrape_imaeil_economy(days=365):
    base_url = "https://www.imaeil.com"
    news_data = []
    headers = get_common_headers()
    limit_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    logger.info(f"Starting Imaeil parallel collection until {limit_date}...")

    with requests.Session() as session:
        session.headers.update(headers)
        page = 1
        while page <= 500:
            target_url = f"{base_url}/economy?page={page}"
            try:
                response = fetch_url(target_url, headers, logger, session=session)
                if not response or response.status_code != 200: break
                
                soup = BeautifulSoup(response.text, 'html.parser')
                # 헤드라인과 일반 목록 모두 포함
                items = soup.select('div.hdl_002 li') + soup.select('div.arl_018 li')
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
    results = scrape_imaeil_economy(days=365)
    save_to_csv(results, "data/raw_gyeongbuk_imaeil.csv", logger)
