import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from utils import get_logger, get_common_headers, common_parse_date, save_to_csv, fetch_article_details, fetch_url

# 로거 설정
logger = get_logger("gangwon_kwnews")

def process_article(item, session, headers, limit_date):
    """개별 기사 처리"""
    try:
        # 날짜 추출
        date_tag = item.select_one('p.date')
        if not date_tag: return None
        
        # "2026-02-23 16:30:00" -> "2026-02-23"
        formatted_date = common_parse_date(date_tag.get_text(strip=True))
        if formatted_date < limit_date: return "OLDER"

        title_tag = item.select_one('p.title a')
        if not title_tag: return None
        
        article_url = title_tag['href']
        if not article_url.startswith('http'):
            article_url = "https://www.kwnews.co.kr" + article_url
        
        # 상세 페이지 HTML 가져오기 (이미지 추출용)
        response = fetch_url(article_url, headers, logger, session=session)
        image_url = ""
        details = {'sub_title': '', 'content': ''}
        
        if response and response.status_code == 200:
            soup_detail = BeautifulSoup(response.text, 'html.parser')
            
            # 1. 이미지 추출 (og:image 우선)
            img_meta = soup_detail.select_one('meta[property="og:image"]') or soup_detail.select_one('meta[name="og:image"]')
            if img_meta and img_meta.get('content'):
                image_url = img_meta['content']
                if not image_url.startswith('http'):
                    image_url = "https://www.kwnews.co.kr" + image_url
            
            # 2. 본문 및 부제목 추출 로직 (fetch_article_details의 soup_detail 활용 버전)
            # (기존 함수 재사용 대신 직접 soup을 사용하여 효율성 증대)
            st_sel = ['h3.read_sub_tit', '.subtitle', 'strong.read_sub_tit']
            for s in st_sel:
                tag = soup_detail.select_one(s)
                if tag:
                    details['sub_title'] = tag.get_text(" ", strip=True)
                    break
            
            c_sel = ['div#articlebody', 'div.article_view', '.article-body', '.article_content']
            for s in c_sel:
                tag = soup_detail.select_one(s)
                if tag:
                    for noise in tag.select('script, style, iframe, ins, .quizContainer, figcaption, .articleCopyright'):
                        noise.decompose()
                    from utils import clean_text
                    details['content'] = clean_text(tag.get_text(" ", strip=True))
                    break

        # 요약 정보 (목록 페이지 우선)
        desc_tag = item.select_one('p.body a')
        description = desc_tag.get_text(strip=True) if desc_tag else ""

        return {
            'date': formatted_date,
            'press': '강원일보',
            'region': 'gangwon',
            'title': title_tag.get_text(strip=True),
            'sub_title': details['sub_title'],
            'description': description,
            'content': details['content'],
            'article_url': article_url,
            'image_url': image_url
        }
    except Exception as e:
        logger.debug(f"Error processing item: {e}")
        return None

def scrape_kwnews_economy(days=365):
    base_url = "https://www.kwnews.co.kr"
    news_data = []
    headers = get_common_headers()
    limit_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    logger.info(f"Starting Gangwon parallel collection until {limit_date}...")

    with requests.Session() as session:
        session.headers.update(headers)
        page = 1
        while page <= 500:
            target_url = f"{base_url}/economy/all?page={page}"
            try:
                response = fetch_url(target_url, headers, logger, session=session)
                if not response or response.status_code != 200: break
                
                soup = BeautifulSoup(response.text, 'html.parser')
                items = soup.select('div.arl_023 > ul > li')
                if not items: break
                
                logger.info(f"Page {page}: Processing {len(items)} items...")
                page_data = []
                reached_limit = False
                
                with ThreadPoolExecutor(max_workers=10) as executor:
                    results = list(executor.map(lambda it: process_article(it, session, headers, limit_date), items))
                    
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
    results = scrape_kwnews_economy(days=365)
    save_to_csv(results, "data/raw_gangwon_kwnews.csv", logger)
