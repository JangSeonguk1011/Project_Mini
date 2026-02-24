import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
# utils에서 필요한 함수들을 임포트합니다.
from utils import get_logger, get_common_headers, common_parse_date, save_to_csv, fetch_article_details, fetch_url

# 로거 설정 (서울 지역 - 서울신문)
logger = get_logger("seoul_seoul")

def process_article(item, base_url, session, headers, limit_date):
    """개별 기사 처리 및 상세 페이지 본문 수집"""
    try:
        # 1. 날짜 추출 (목록 페이지의 ArticleInfo span.body14)
        date_tag = item.select_one('div.ArticleInfo span.body14')
        if not date_tag: return None
        
        formatted_date = common_parse_date(date_tag.get_text(strip=True))
        
        # 6개월(180일) 기준일보다 오래된 기사면 중단 신호 반환
        if formatted_date < limit_date: 
            return "OLDER"

        # 2. 제목 및 링크 추출
        title_tag = item.select_one('div.articleTitle h2.h28')
        link_tag = item.select_one('div.articleTitle a')
        if not title_tag or not link_tag: return None
        
        article_url = link_tag['href']
        if not article_url.startswith('http'):
            article_url = base_url.rstrip('/') + article_url
        
        # 3. 상세 정보 수집 (PRD 명세: Sub Title, Content)
        # 서울신문 상세 페이지 본문 ID: #articleContent
        details = fetch_article_details(article_url, {
            'sub_title': [
                'strong.subTitle_s2', 
                'div.subtitle', 
                '.view_subtitle', 
                'h3.read_sub_tit'
            ],
            'content': [
                'div#articleContent',     # 서울신문 표준 본문 ID
                'div.viewContent', 
                '.article_view',
                '#articleBody'
            ]
        }, headers, logger, session=session)

        # 4. 이미지 주소 보정
        img_tag = item.select_one('div.articleImage img')
        image_url = ""
        if img_tag and img_tag.get('src'):
            image_url = img_tag['src']
            if not image_url.startswith('http'):
                image_url = base_url.rstrip('/') + image_url

        # 통합 데이터 스키마 규격 준수
        return {
            'date': formatted_date,
            'press': '서울신문',
            'region': 'seoul',
            'title': title_tag.get_text(strip=True),
            'sub_title': details.get('sub_title', ''),
            'description': item.select_one('div.body16.color600').get_text(strip=True) if item.select_one('div.body16.color600') else "",
            'content': details.get('content', ''),
            'article_url': article_url,
            'image_url': image_url
        }
    except Exception as e:
        logger.debug(f"Error processing item: {e}")
        return None

def scrape_seoul_economy(months=6):
    """최근 6개월(180일) 데이터 수집"""
    base_url = "https://www.seoul.co.kr"
    news_data = []
    headers = get_common_headers()
    
    # 6개월 기준 날짜 계산 (180일)
    limit_date = (datetime.now() - timedelta(days=30 * months)).strftime('%Y-%m-%d')
    logger.info(f"Starting Seoul collection until {limit_date} (Last {months} months)...")

    with requests.Session() as session:
        session.headers.update(headers)
        page = 1
        seen_urls = set()
        
        while page <= 500: # 서울신문 페이지네이션 한계 고려
            target_url = f"{base_url}/newsList/economy?page={page}"
            try:
                response = fetch_url(target_url, headers, logger, session=session)
                if not response or response.status_code != 200: break
                
                soup = BeautifulSoup(response.text, 'html.parser')
                items = soup.select('li.newsBox_row1')
                
                if not items: 
                    logger.info("No more items found. Ending.")
                    break
                
                logger.info(f"Page {page}: Processing {len(items)} items...")
                page_data = []
                reached_limit = False
                
                # 병렬 처리 (스레드 10개)
                with ThreadPoolExecutor(max_workers=10) as executor:
                    results = list(executor.map(lambda it: process_article(it, base_url, session, headers, limit_date), items))
                    
                    for res in results:
                        if res == "OLDER":
                            reached_limit = True
                        elif res and isinstance(res, dict):
                            if res['article_url'] not in seen_urls:
                                page_data.append(res)
                                seen_urls.add(res['article_url'])
                
                news_data.extend(page_data)
                logger.info(f"Page {page}: Added {len(page_data)} articles. Total: {len(news_data)}")
                
                # 6개월 기한 초과 기사 발견 시 루프 종료
                if reached_limit:
                    logger.info("Reached 6-month limit date. Collection complete.")
                    break
                
                page += 1
                time.sleep(0.1) # 서버 부하 조절
                
            except Exception as e:
                logger.error(f"Error on Page {page}: {e}")
                break
                
    return news_data

if __name__ == "__main__":
    # 6개월 수집 실행
    results = scrape_seoul_economy(months=6)
    if results:
        save_to_csv(results, "data/raw_seoul_seoul.csv", logger)
        logger.info(f"Successfully saved {len(results)} articles for Seoul Shinmun.")