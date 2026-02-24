import requests
from bs4 import BeautifulSoup
import time
import re
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from utils import get_logger, get_common_headers, common_parse_date, save_to_csv, fetch_url, clean_text

# 로거 설정
logger = get_logger("gyeongnam_gnen")

def process_article(item, base_url, session, headers, limit_date):
    """개별 기사 처리 및 상세 페이지 본문 정밀 수집"""
    try:
        # 1. 날짜 추출 및 검사
        date_tag = item.select_one('span.byline em.date')
        if not date_tag: return None
        
        formatted_date = common_parse_date(date_tag.get_text(strip=True))
        if formatted_date < limit_date: 
            return "OLDER"

        # 2. 링크 추출
        title_link = item.select_one('h4.titles a')
        if not title_link: return None
        
        article_url = title_link['href']
        if not article_url.startswith('http'):
            article_url = base_url.rstrip('/') + article_url
        
        # 3. 상세 페이지 접속
        response = fetch_url(article_url, headers, logger, session=session)
        if not response or response.status_code != 200: return None
        soup_detail = BeautifulSoup(response.text, 'html.parser')

        # 4. 부제목(Sub Title) 추출
        # HTML 구조: h4.subheading user-point
        sub_title_tag = soup_detail.select_one('h4.subheading')
        sub_title = sub_title_tag.get_text(strip=True) if sub_title_tag else ""

        # 5. 본문(Content) 정밀 추출
        # 영역: article#article-view-content-div
        content_container = soup_detail.select_one('article#article-view-content-div')
        if not content_container: return None

        # [중요] 본문 데이터 정제 (노이즈 제거)
        # subheading(부제), press(기자정보), figure(이미지/캡션) 등 제거
        for noise in content_container.select('h4.subheading, div.press, figure, script, style, .article-footer'):
            noise.decompose()
        
        # 순수 텍스트 추출 및 정제
        raw_content = content_container.get_text(" ", strip=True)
        content = clean_text(raw_content)

        # 6. 이미지 및 요약 (목록 페이지 추출)
        img_tag = item.select_one('a.thumb img')
        image_url = img_tag['src'] if img_tag else ""
        if image_url and not image_url.startswith('http'):
            image_url = base_url.rstrip('/') + image_url
            
        desc_tag = item.select_one('p.lead a')
        description = desc_tag.get_text(strip=True) if desc_tag else ""

        return {
            'date': formatted_date,
            'press': '경남경제',
            'region': 'gyeongnam',
            'title': title_link.get_text(strip=True),
            'sub_title': sub_title,
            'description': description,
            'content': content,
            'article_url': article_url,
            'image_url': image_url
        }
    except Exception as e:
        logger.debug(f"Error processing item: {e}")
        return None

def scrape_gnen_economy(days=7):
    """최근 n일(기본 7일) 데이터 수집"""
    base_url = "https://www.gnen.net"
    news_data = []
    headers = get_common_headers()
    limit_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    logger.info(f"경남경제 일주일 수집 시작 (기준일: {limit_date})")

    with requests.Session() as session:
        session.headers.update(headers)
        page = 1
        seen_urls = set()

        while page <= 1000:
            target_url = f"{base_url}/news/articleList.html?page={page}&sc_section_code=S1N2&view_type=sm"
            
            try:
                response = session.get(target_url, timeout=15)
                if response.status_code != 200: break
                
                soup = BeautifulSoup(response.text, 'html.parser')
                items = soup.select('section#section-list ul.type > li')
                
                if not items: break

                logger.info(f"Page {page}: {len(items)}개 분석 중...")
                page_data = []
                reached_limit = False
                
                with ThreadPoolExecutor(max_workers=5) as executor:
                    results = list(executor.map(lambda it: process_article(it, base_url, session, headers, limit_date), items))
                    
                    for res in results:
                        if res == "OLDER": 
                            reached_limit = True
                        elif res and isinstance(res, dict):
                            if res['article_url'] not in seen_urls:
                                page_data.append(res)
                                seen_urls.add(res['article_url'])
                
                news_data.extend(page_data)
                logger.info(f"Page {page} 완료: {len(page_data)}개 추가 (누적: {len(news_data)})")
                
                if reached_limit: break
                page += 1
                time.sleep(0.5)

            except Exception as e:
                logger.error(f"Error on Page {page}: {e}")
                break
                
    return news_data

if __name__ == "__main__":
    results = scrape_gnen_economy(days=365)
    if results:
        save_to_csv(results, "data/raw_gyeongnam_gnen.csv", logger)