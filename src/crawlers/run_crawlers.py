"""
메인 실행 스크립트
전국 지역별 뉴스 크롤러 실행
"""

import sys
import os

# Windows에서 UTF-8 출력 설정
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import argparse
from crawler_manager import CrawlerManager


def main():
    """크롤러 실행"""
    parser = argparse.ArgumentParser(
        description='서울, 경기도, 강원도, 충청도, 경상도, 전라도 지역 뉴스 크롤러',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
사용 예시:
  # 모든 지역 크롤링 (각 신문 50개 기사)
  python run_crawlers.py --mode all --articles 50

  # 서울만 크롤링
  python run_crawlers.py --mode region --region 서울 --articles 30

  # 경기도만 크롤링
  python run_crawlers.py --mode region --region 경기도 --articles 30
        '''
    )

    parser.add_argument(
        '--mode',
        choices=['all', 'region'],
        default='all',
        help='크롤링 모드 (all: 전체 지역, region: 특정 지역)'
    )
    parser.add_argument(
        '--region',
        type=str,
        choices=['서울', '경기도', '강원도', '충청도', '경상도', '전라도'],
        default='서울',
        help='지역 선택 (서울, 경기도, 강원도, 충청도, 경상도, 전라도)'
    )
    parser.add_argument(
        '--articles',
        type=int,
        default=50,
        help='신문사당 최대 기사 수 (기본값: 50)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='../../data/regional_news.csv',
        help='출력 파일 경로 (기본값: ../../data/regional_news.csv)'
    )
    parser.add_argument(
        '--save-db',
        action='store_true',
        default=True,
        help='데이터베이스에 저장 (기본값: True)'
    )
    parser.add_argument(
        '--save-text',
        action='store_true',
        default=True,
        help='텍스트 파일로 저장 (기본값: True)'
    )

    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("🕷️  지역 경제 뉴스 크롤러")
    print("=" * 70)
    print(f"모드: {args.mode}")
    if args.mode == 'region':
        print(f"대상 지역: {args.region}")
    print(f"신문사당 기사 수: {args.articles}개")
    print(f"CSV 출력: {args.output}")
    print(f"데이터베이스 저장: {'예' if args.save_db else '아니오'}")
    print(f"텍스트 파일 저장: {'예' if args.save_text else '아니오'}")
    print("=" * 70 + "\n")

    # 크롤러 매니저 생성
    manager = CrawlerManager(
        use_database=args.save_db,
        save_text_files=args.save_text
    )
    manager.register_all_crawlers()

    # 크롤링 실행
    if args.mode == 'all':
        manager.run_all_crawlers(max_articles=args.articles)
    else:
        manager.run_by_region(args.region, max_articles=args.articles)

    # 결과 저장 (모든 포맷)
    manager.save_all(csv_filename=args.output)

    print("\n✅ 크롤링 완료!")


if __name__ == '__main__':
    main()
