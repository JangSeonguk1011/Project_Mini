import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
import csv
import time
import re
from pathlib import Path

BASE_URL = "http://www.kwangju.co.kr"
SECTION_URL = BASE_URL + "/section.php?sid=5&page={}"

REGION = "jeonnam"
PRESS = "광주일보"

DATA_DIR = Path("data")
LOG_DIR = Path("logs")
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

TODAY_STR = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = LOG_DIR / f"{PRESS}_{TODAY_STR}.log"

MAX_PAGES = 500
DAYS_LIMIT = 365


def log(msg):
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def retry_request(session, url, retries=3):
    for i in range(retries):
        try:
            res = session.get(url, timeout=10)
            if res.status_code == 200:
                res.encoding = res.apparent_encoding
                return res
        except Exception:
            time.sleep(2 * (i + 1))
    return None


def clean_text(text):
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"/.*?기자.*", "", text)
    text = re.sub(r"Copyright.*", "", text)
    return text.strip()


def parse_date(text):
    nums = re.findall(r"\d+", text)
    if len(nums) >= 3:
        return datetime.strptime(
            f"{nums[0]}-{nums[1].zfill(2)}-{nums[2].zfill(2)}",
            "%Y-%m-%d"
        )
    return None


def extract_content(soup):
    # 🔥 실제 광주일보 본문 위치
    content_tag = soup.select_one("div#joinskmbox")

    if not content_tag:
        return ""

    # 광고 제거
    for tag in content_tag.select("script, style, iframe, ins, table, a"):
        tag.decompose()

    text = clean_text(content_tag.get_text(" ", strip=True))

    return text


def scrape():
    results = []
    limit_date = datetime.now() - timedelta(days=DAYS_LIMIT)

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Referer": BASE_URL
    })

    for page in range(1, MAX_PAGES + 1):
        url = SECTION_URL.format(page)
        log(f"{page}페이지 요청")

        res = retry_request(session, url)
        if not res:
            break

        soup = BeautifulSoup(res.text, "html.parser")
        items = soup.select("ul.section_list li")

        if not items:
            break

        for item in items:
            link = item.select_one("a")
            if not link:
                continue

            article_url = link["href"]
            if not article_url.startswith("http"):
                article_url = BASE_URL + article_url

            date_tag = item.select_one("span.newsdate")
            if not date_tag:
                continue

            article_date = parse_date(date_tag.text)
            if not article_date:
                continue

            if article_date < limit_date:
                return results

            title = item.select_one("div").get_text(strip=True)

            description_tag = item.select_one("p")
            description = description_tag.get_text(strip=True) if description_tag else ""

            img_tag = item.select_one("span.thumb img")
            image_url = ""
            if img_tag:
                image_url = img_tag.get("data-src") or img_tag.get("src") or ""
                if image_url and not image_url.startswith("http"):
                    image_url = BASE_URL + image_url

            detail_res = retry_request(session, article_url)
            if not detail_res:
                continue

            detail_soup = BeautifulSoup(detail_res.text, "html.parser")

            # 부제목
            sub_tag = detail_soup.select_one("div.rtitle2")
            sub_title = sub_tag.get_text(" ", strip=True) if sub_tag else ""

            content = extract_content(detail_soup)

            log(f"수집: {title[:30]} / 본문길이: {len(content)}")

            results.append({
                "date": article_date.strftime("%Y-%m-%d"),
                "press": PRESS,
                "region": REGION,
                "title": title,
                "sub_title": sub_title,
                "description": description,
                "content": content,
                "article_url": article_url,
                "image_url": image_url
            })

            time.sleep(0.3)

    return results


def save_csv(data):
    file_path = DATA_DIR / f"raw_{REGION}_{PRESS}.csv"

    try:
        with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "date",
                    "press",
                    "region",
                    "title",
                    "sub_title",
                    "description",
                    "content",
                    "article_url",
                    "image_url"
                ]
            )
            writer.writeheader()
            writer.writerows(data)
    except PermissionError:
        print("CSV 파일이 열려 있습니다. 파일을 닫고 다시 실행하세요.")


if __name__ == "__main__":
    data = scrape()
    save_csv(data)
    print("완료:", len(data))