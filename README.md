# 📊 지능형 지역 경제 모니터링 및 자산 영향 분석 대시보드
> **Intelligent Regional Economy Monitoring & Asset Impact Analysis Dashboard**
>
> 본 프로젝트는 전국 단위의 거시 경제 흐름과 지역별 미시 경제 이슈를 통합 분석하고, 이를 주식·가상화폐 등 자산 지표와 연결하여 데이터 기반의 인사이트를 제공하는 플랫폼입니다.
---

## 👥 팀원 구성 및 역할 (Team)

| 이름 | 역할 | 주요 담당 업무 |
| :--- | :--- | :--- |
| **이채현** | 팀장 | 뉴스 크롤링 로직 개발, 인터랙티브 지도 UI 설계 및 개발 |
| **김보민** | 팀원 | 뉴스 크롤링 로직 개발, 인터랙티브 지도 UI 설계 및 개발 |
| **민병주** | 팀원 | 키워드 추출 로직 개발, 웹 대시보드 UI 및 시각화 구현 |
| **박미정** | 팀원 | 뉴스 스크래핑 로직 개발, 웹 대시보드 UI 및 시각화 구현 |
| **장성욱** | 팀원 | 감성 점수 로직, 금융 데이터 결합, 상관계수 산출 및 통계 분석 |
| **장헌준** | 팀원 | DB 구조 통일 및 마이그레이션, 감성 점수 및 금융 데이터 상관분석 |

---

## 🎯 프로젝트 목표 (Goals)

1.  **맞춤형 데이터 파이프라인**: 전국 및 지역별 주요 일간지(부산일보, 충청뉴스 등)의 실시간 경제 데이터 수집.
2.  **NLP 기반 감성 및 이슈 추출**: KoBERT 모델을 활용한 감성 지수(Positive/Negative) 산출 및 TOP 10 키워드 도출.
3.  **인터랙티브 시각화**: Folium 기반의 동적 지도를 통한 지역별 경제 모멘텀 가시화.
4.  **자산 영향력 상관분석**: 뉴스 감성 지수와 실제 자산(KOSPI, KOSDAQ) 가격 변동 간의 상관계수($r$) 분석.

---

## ✨ 핵심 기능 (Key Features)
### 1. 데이터 수집 및 정제
- **수집 대상 언론사 및 섹션**
  
| 권역 | 언론사 | 대상 섹션 및 URL (Target URL) |
| :--- | :--- | :--- |
| **전국** | **한국경제** | [경제정책](https://www.hankyung.com/economy/economic-policy), [거시경제](https://www.hankyung.com/economy/macro), [외환/금융](https://www.hankyung.com/economy/forex), [세제/부동산](https://www.hankyung.com/economy/tax), [고용복지](https://www.hankyung.com/economy/job-welfare) |
| **서울** | **서울신문** | [경제 섹션](https://seoul.co.kr/newsList/economy) |
| **경기** | **경인일보** | [경제 섹션 (Money)](https://www.kyeongin.com/money) |
| **인천** | **인천일보** | [경제 섹션](https://www.incheonilbo.com/news/articleList.html?sc_section_code=S1N4&view_type=sm) |
| **충청/대전** | **충청투데이** | [경제 섹션](https://www.cctoday.co.kr/news/articleList.html?sc_section_code=S1N4&view_type=sm) |
| **부산/경남** | **부산일보**<br>**경남경제** | [경제해양 섹션](https://www.busan.com/newsList/busan/0201000000)<br>[경제 섹션](https://www.gnen.net/news/articleList.html?sc_section_code=S1N2&view_type=sm) |
| **대구/경북** | **매일신문** | [경제 섹션](https://www.imaeil.com/economy) |
| **광주/전라** | **광주일보** | [경제 섹션](http://www.kwangju.co.kr/section.php?sid=5) |
| **강원** | **강원일보** | [경제 섹션](https://www.kwnews.co.kr/economy/all) |
| **제주** | **제주일보** | [경제 섹션](http://www.jejunews.com/news/articleList.html?sc_section_code=S1N5&view_type=sm) |
- **수집 기간**: 수집 시작일로부터 과거 1개월(30일) 분량
- **본문 정제**: css 셀렉터를 분석하여 광고, 기자명/이메일, 이미지 캡션, 저작권 공지 등을 제거한 순수 기사 내용만 추출

### 2. 지능형 분석 엔진
- **감성 분석**: BERT 기반의 KoBERT 모델을 활용하여 기사별 경제 체감 지수 산출.
- **EDA & 트렌드**: TF-IDF 및 WordCloud를 활용한 지역별 핵심 키워드 분석.
- **상관분석**: 뉴스 감성 지수와 주가 지수(**KOSPI, KOSDAQ**) 간의 시계열 상관성을 검토합니다. 특히, **피어슨 상관계수($r$)**를 산출하여 뉴스 데이터 기반의 경제 심리가 실제 자산 시장에 미치는 영향력을 정량적으로 검증하고 선행 지표로서의 유효성을 분석합니다.

### 3. 웹 대시보드 (Streamlit)
- **Regional View**: 대한민국 지도를 활용한 지역별 기사량 및 감성 분포 시각화.
- **Market Correlation Analyzer**: 감성 지수 vs 시장 지표 시계열 차트, 상관계수 히트맵(Heatmap), 회귀 분석 산점도 제공.

---

## 🛠 기술 스택 (Tech Stack)

### Language & Environment
- **Python 3.9+**, **Streamlit**

### AI & Data Engineering
- **PyTorch, Transformers (KoBERT)**
- **KoNLPy, Kiwipiepy** (Korean NLP)
- **Pandas, NumPy, Scikit-learn** (Analytics)
- **SQLite3** (Database)
- **Selenium, BeautifulSoup4** (Crawling)

### Visualization
- **Folium** (GIS Maps)
- **Plotly, Matplotlib, Seaborn** (Charts)
- **Pyvis** (Network Graphs)

---

## 📂 프로젝트 구조 (Structure)
```text
├── app.py                      # Streamlit 메인 대시보드
├── market_analyzer.py           # 시장 상관분석 및 통계 엔진
├── analyzer/                   # KoBERT 감성 분석 및 형태소 분석 모듈
├── src/
│   ├── crawlers/               # 12개 이상 신문사별 커스텀 크롤러
│   └── utils/                  # 텍스트 정제(clean_text) 및 파서
├── data/                       # DB, GeoJSON 및 자산 지표 데이터
└── docs/                       # PRD 및 가이드라인
```

---

## 🖼️ 대시보드 화면 (Dashboard)

### 1️⃣ 종합 경제 모니터링 (Main Dashboard)
- **전국 경제 현황 개요**: 지역별 통합 감성 지수(Sentiment Index)와 경제 변동성을 한눈에 파악합니다.
- **시장 지표 실시간 연동**: KOSPI/KOSDAQ 변동률과 뉴스 감성 지수의 흐름을 대조하여 거시 경제 환경을 모니터링합니다.
<img width="2560" height="1301" alt="메인 화면" src="https://github.com/user-attachments/assets/9757ae85-228c-47df-952d-2cdc4b831727" />

&nbsp;
### 2️⃣ 인터랙티브 지역별 지도 시각화 및 지역별 핵심 이슈(키워드) 확인 (Geospatial Analysis)
- **GIS 기반 감성 맵**: Folium 지도상에 지역별 뉴스 밀도와 긍/부정 지수를 컬러 맵으로 시각화하여 지역별 경제 온도를 직관적으로 표시합니다.
- **지역별 핵심 이슈(키워드) 분석**: **TF-IDF 및 형태소 분석**을 기반으로 지역별 핵심 경제 키워드를 도출합니다. '가덕도 신공항', '반도체 클러스터' 등 각 지역의 특수성이 반영된 핵심 이슈를 빈도 분석과 가중치 계산을 통해 추출합니다.
- **인터랙티브 데이터 드릴다운**: 지도상의 특정 지역 클릭 시 해당 권역의 긍/부정 뉴스 통계, 평균 감성 지수, 그리고 최신 뉴스 목록을 포함한 상세 분석 리포트를 팝업 형태로 즉각 제공하여 분석 결과의 근거를 명확히 제시합니다.
<img width="2560" height="1321" alt="지도 시각화 1" src="https://github.com/user-attachments/assets/e6ec4c71-b5ec-4e53-a60d-54536225336f" />
<img width="2560" height="1321" alt="지도 시각화 2" src="https://github.com/user-attachments/assets/de8abf24-edab-4d5e-91b9-26520e7e94ca" />

&nbsp;
### 3️⃣ 자산 상관관계 분석 (Market Correlation Analysis)
- **시계열 혼합 차트**: 뉴스 감성 지수 추이와 KOSPI/KOSDAQ 자산 가격의 흐름을 단일 차트에서 비교 분석하여 선행/동행 지표 여부를 검토합니다.
- **상관분석 도구**: 감성 지수와 자산 수익률 간의 **상관계수 히트맵(Heatmap)** 및 **회귀 분석 산점도(Scatter Plot)**를 통해 여론이 실제 시장에 미치는 영향력을 정량적으로 산출합니다.
<img width="2560" height="1325" alt="자산 분석 1" src="https://github.com/user-attachments/assets/53873276-2abe-4f16-90dd-e95aadde2846" />
<img width="2560" height="1340" alt="자산 분석 2" src="https://github.com/user-attachments/assets/d8df852a-6d10-4985-919c-0085350764b8" />
<img width="2560" height="1340" alt="자산 분석 3" src="https://github.com/user-attachments/assets/55a6b7d8-077c-4923-bbea-56191156a73a" />

&nbsp;
### 4️⃣ 지역별 감성 타임라인 캘린더 (Sentiment Timeline Calendar)
- **일별 감성 지수 트래킹**: 캘린더 UI를 활용하여 날짜별 지역 경제 감성 지수의 변화를 시계열적으로 추적합니다.
- **감성 강도 색상 매핑**: 해당 날짜의 평균 감성 점수에 따라 색상 농도를 차별화(긍정-청색, 부정-적색)하여 여론의 변곡점을 직관적으로 식별합니다.
- **주요 이벤트 연동 분석**: 특정 시점의 감성 지수 급등락을 확인하여 주요 경제 정책 발표나 지역별 매크로 이슈와의 상관관계를 분석할 수 있는 기초 데이터를 제공합니다.
<img width="1279" height="661" alt="감성 타임라인 캘린더" src="https://github.com/user-attachments/assets/c9c371eb-d407-4a99-8b40-7fdd2e19f5db" />


&nbsp;
### 5️⃣ 기술적 지표 및 변동성 분석 (Technical Analysis)
- **변동성 인사이트**: 지역 경제 모멘텀의 변동 폭과 주가 지수의 기술적 지표를 결합하여 시장의 과열 또는 침체 구간을 통계적으로 진단합니다.
- **데이터 기반 의사결정**: 표준편차 및 변동성 지표를 활용하여 각 권역별 경제적 건전성을 수치화하여 비교합니다.
<img width="2560" height="1330" alt="기술적 분석 1" src="https://github.com/user-attachments/assets/290e3970-e918-4a98-8e61-326d1e2e6a56" />
<img width="2560" height="1333" alt="기술적 분석 2" src="https://github.com/user-attachments/assets/4ae9209d-3ce5-4c5d-bb5c-e0683abb2962" />

&nbsp;
### 6️⃣ 지역별 최신 감성 뉴스 (Real-time News Feed)
- **맞춤형 뉴스 피드**: 긍/부정 점수가 라벨링된 지역별 최신 경제 기사를 실시간으로 피드백하여, 분석 결과의 근거가 되는 원본 데이터를 즉시 확인할 수 있습니다.
<img width="2560" height="1313" alt="뉴스 피드" src="https://github.com/user-attachments/assets/6423af7a-272f-4488-8d04-450fba5e8e25" />

---

## 📅 프로젝트 일정 (Schedule)
- **1일차**: 기획 확정 및 수집/분석 모듈 기초 개발
- **2일차**: 데이터 수집 완료 및 전처리, DB 구조화, 상관분석 모듈 개발
- **3일차**: 인터랙티브 지도 설계, Streamlit 레이아웃 구성, 통계 분석 수행
- **4일차**: 웹 UI 구현 완성, 코드 리팩토링 및 데이터 정합성 검증
- **5일차**: 최종 디버깅, 테스트 및 프로젝트 발표

---

## 🚀 기대 효과 및 활용 방안 (Impact)
- **지역 경제 인사이트**: 권역별 실물 경제 흐름을 데이터 기반으로 파악.
- **자동화 리포트**: 지역별 키워드 및 감성 지수를 활용한 정기 경제 동향 보고서 생성 가능.
- **확장성**: SNS/커뮤니티 데이터 연동 및 LLM(GPT-4/Gemini)을 활용한 기사 요약 서비스로 발전 가능.
