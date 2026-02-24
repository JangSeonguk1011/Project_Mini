import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from utils import get_logger, get_common_headers, common_parse_date, save_to_csv, fetch_article_details, fetch_url

# 로거 설정
logger = get_logger("national_hankyung")

def process_article(item, session, headers, limit_date):
    """개별 기사 처리 및 상세 페이지 수집"""
    try:
        # 1. 날짜 추출 및 검사 (txt-date 클래스 활용)
        date_tag = item.select_one('.txt-date')
        if not date_tag:
            return None
        
        date_text = date_tag.get_text(strip=True)
        formatted_date = common_parse_date(date_text)
        
        if formatted_date < limit_date:
            return "OLDER"

        # 2. 링크 및 제목 추출
        title_link = item.select_one('.news-tit a')
        if not title_link:
            return None
        
        article_url = title_link['href']
        if not article_url.startswith('http'):
            article_url = "https://www.hankyung.com" + article_url
        
        # 3. 상세 정보 수집 (PRD 명세 반영: Sub Title, Content)
        # 한국경제 특화 셀렉터: 본문(div#articletxt), 부제(strong.subTitle_s2)
        details = fetch_article_details(article_url, {
            'sub_title': [
                'strong.subTitle_s2', 
                'h2.sub_title', 
                'div.article-sub-title'
            ],
            'content': [
                'div#articletxt',         # 한국경제 표준 본문 영역
                'div.article-body', 
                'div#article-view-content-div'
            ]
        }, headers, logger, session=session)

        # 4. 이미지 및 요약 정보 추출 (제공해주신 구조 반영)
        # 이미지: figure.thumb 내부의 img 태그 src 속성
        img_tag = item.select_one('figure.thumb img')
        image_url = img_tag['src'] if img_tag else ""

        # 요약: p.lead 클래스
        desc_tag = item.select_one('p.lead')
        description = desc_tag.get_text(strip=True) if desc_tag else ""

        # 통합 데이터 스키마 9개 컬럼 준수
        return {
            'date': formatted_date,
            'press': '한국경제',
            'region': 'national',
            'title': title_link.get_text(strip=True),
            'sub_title': details.get('sub_title', ''),
            'description': description,
            'content': details.get('content', ''),
            'article_url': article_url,
            'image_url': image_url
        }
    except Exception as e:
        logger.debug(f"Error processing article: {e}")
        return None

def scrape_hankyung_category(category_url, limit_date, session, headers):
    """특정 카테고리(정책/거시/외환 등)의 기사들을 수집"""
    cat_data = []
    page = 1
    total_seen_urls = set()

    while page <= 100: # 카테고리당 최대 페이지 제한
        target_url = f"{category_url}?page={page}"
        try:
            response = fetch_url(target_url, headers, logger, session=session)
            if not response or response.status_code != 200:
                break
            
            soup = BeautifulSoup(response.text, 'html.parser')
            # 기사 리스트 아이템 추출
            items = soup.select('ul.news-list > li')
            
            if not items:
                break
            
            logger.info(f"Processing {category_url.split('/')[-1]} - Page {page}...")
            reached_limit = False
            
            # 병렬 처리를 통해 본문 수집 속도 향상
            with ThreadPoolExecutor(max_workers=8) as executor:
                results = list(executor.map(lambda it: process_article(it, session, headers, limit_date), items))
                
                for res in results:
                    if res == "OLDER":
                        reached_limit = True
                    elif res and isinstance(res, dict):
                        if res['article_url'] not in total_seen_urls:
                            cat_data.append(res)
                            total_seen_urls.add(res['article_url'])
            
            if reached_limit:
                break
            page += 1
            time.sleep(0.3)
        except Exception as e:
            logger.error(f"Error on page {page} of {category_url}: {e}")
            break
            
    return cat_data

def main():
    # 수집 대상 한국경제 하위 섹션 URL 리스트
    categories = [
        "https://www.hankyung.com/economy/economic-policy",
        "https://www.hankyung.com/economy/macro",
        "https://www.hankyung.com/economy/forex",
        "https://www.hankyung.com/economy/tax",
        "https://www.hankyung.com/economy/job-welfare"
    ]
    
    all_news_data = []
    headers = get_common_headers()
    limit_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    
    with requests.Session() as session:
        session.headers.update(headers)
        
        for url in categories:
            logger.info(f"Category 수집 시작: {url.split('/')[-1]}")
            category_data = scrape_hankyung_category(url, limit_date, session, headers)
            all_news_data.extend(category_data)
            logger.info(f"Category 완료: {len(category_data)}건 수집됨")

    if all_news_data:
        # PRD 통합 데이터 스키마 규칙에 따라 CSV 저장
        save_to_csv(all_news_data, "data/raw_national_hankyung.csv", logger)
        logger.info(f"전체 수집 완료: 총 {len(all_news_data)}건 저장됨.")
    else:
        logger.warning("수집된 데이터가 없습니다.")

if __name__ == "__main__":
    main()