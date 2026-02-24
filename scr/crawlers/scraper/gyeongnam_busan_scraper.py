import requests
from bs4 import BeautifulSoup
import time
import re
import random
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from utils import get_logger, get_common_headers, common_parse_date, save_to_csv, fetch_article_details, clean_text

# 로거 설정
logger = get_logger("gyeongnam_busan")

def process_article(item, session, headers, limit_date):
    """개별 기사 파싱 및 상세 페이지 본문 수집"""
    try:
        # 1. 날짜 추출 및 검사 (YYYY-MM-DD)
        date_tag = item.select_one('p.date')
        if not date_tag: return None
        
        date_text = date_tag.get_text(strip=True)
        # "2026-02-23 [17:01]" -> "2026-02-23" 정제
        match = re.search(r'\d{4}-\d{2}-\d{2}', date_text)
        if not match: return None
        
        formatted_date = common_parse_date(match.group())
        
        # 365일 기준일보다 오래된 기사면 수집 중단 신호 반환
        if formatted_date < limit_date: 
            return "OLDER"

        # 2. 링크 추출
        link_tag = item.select_one('p.title a') or item.select_one('a')
        if not link_tag or not link_tag.get('href'): return None
        
        article_url = link_tag['href']
        if not article_url.startswith('http'):
            article_url = "https://www.busan.com" + article_url

        # 3. 상세 정보 수집 (PRD 명세: Sub Title, Content)
        # utils.fetch_article_details 사용
        details = fetch_article_details(article_url, {
            'sub_title': ['p.subtitle', 'div.sub_title', 'h3.read_sub_tit'],
            'content': ['#article-view-content-div', '.article_content', 'div.view_con', '.article-body']
        }, headers, logger, session=session)

        if not details.get('content'): return None

        # 4. 이미지 및 요약 (목록 페이지 추출)
        img_tag = item.select_one('div.thumb img')
        image_url = img_tag['src'] if img_tag else ""
        
        desc_tag = item.select_one('p.body')
        description = desc_tag.get_text(strip=True) if desc_tag else ""

        # 통합 데이터 스키마 규격 준수
        return {
            'date': formatted_date,
            'press': '부산일보',
            'region': 'gyeongnam',
            'title': link_tag.get_text(strip=True),
            'sub_title': details.get('sub_title', ''),
            'description': description,
            'content': details.get('content', ''),
            'article_url': article_url,
            'image_url': image_url
        }
    except Exception as e:
        logger.debug(f"Error processing item: {e}")
        return None

def scrape_busan_economy(years=1):
    """최근 1년(365일) 데이터 수집"""
    news_data = []
    # 1년 전 날짜 계산
    limit_date = (datetime.now() - timedelta(days=365 * years)).strftime('%Y-%m-%d')
    headers = get_common_headers()
    
    # POST 요청을 위한 폼 데이터 (분석된 경제해양 섹션 전용 페이로드)
    base_payload = {
        "control_type": "A",
        "paging_yn": "Y",
        "dataset_filename": "2018/12/31/259_513_1_article_list.json",
        "view_page_type": "1",
        "directory_type": "news",
        "html_idx": "259"
    }

    logger.info(f"Busan 365일 수집 시작 (기준일: {limit_date})")

    with requests.Session() as session:
        session.headers.update(headers)
        page = 1
        seen_urls = set()

        while page <= 1000: # 1년치를 위해 최대 페이지 상한 확대
            paging_url = "https://www.busan.com/commonFunc/frontPaging.php"
            payload = base_payload.copy()
            payload["page"] = str(page)
            
            try:
                # 봇 차단 회피를 위한 랜덤 지연
                time.sleep(random.uniform(0.5, 1.0))
                
                # POST 방식으로 HTML 조각 데이터 요청
                response = session.post(paging_url, data=payload, timeout=20)
                if response.status_code != 200:
                    logger.error(f"Page {page} 요청 실패: {response.status_code}")
                    break
                
                soup = BeautifulSoup(response.text, 'html.parser')
                items = soup.select('li')
                
                if not items:
                    logger.info(f"Page {page}: 기사가 더 이상 없습니다.")
                    break

                logger.info(f"Page {page}: {len(items)}개 분석 시도 중...")
                page_data = []
                reached_limit = False
                
                # 병렬 수집 (속도 향상을 위해 max_workers 유지)
                with ThreadPoolExecutor(max_workers=8) as executor:
                    results = list(executor.map(lambda it: process_article(it, session, headers, limit_date), items))
                    
                    for res in results:
                        if res == "OLDER":
                            reached_limit = True
                        elif res and isinstance(res, dict):
                            if res['article_url'] not in seen_urls:
                                page_data.append(res)
                                seen_urls.add(res['article_url'])
                
                news_data.extend(page_data)
                logger.info(f"Page {page} 수집 완료: {len(page_data)}개 추가 (누적: {len(news_data)})")
                
                # 1년 기한 초과 기사 발견 시 루프 종료
                if reached_limit:
                    logger.info("수집 기준 날짜(1년) 도달로 종료합니다.")
                    break
                
                page += 1

            except Exception as e:
                logger.error(f"Error on Page {page}: {e}")
                break
                
    return news_data

if __name__ == "__main__":
    # 1년치 수집 실행
    final_results = scrape_busan_economy(years=1)
    if final_results:
        # PRD 표준 파일명 적용
        save_to_csv(final_results, "data/raw_gyeongnam_busan.csv", logger)
        logger.info(f"최종 {len(final_results)}건의 부산/경남 경제 뉴스를 저장했습니다.")
    else:
        logger.error("수집된 데이터가 없습니다.")