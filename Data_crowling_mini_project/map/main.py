"""
뉴스 지도 생성 메인 스크립트
GeoJSON 행정구역 경계선을 활용한 지도를 생성합니다
"""

import os
import sys
from map_generator_geo import NewsMapGeneratorGeo


def main():
    """메인 함수"""
    print("=" * 60)
    print("📍 뉴스 지도 생성기 (GeoJSON 행정구역 버전)")
    print("=" * 60)
    print()
    
    # 출력 파일 경로
    output_file = os.path.join(os.path.dirname(__file__), 'news_map_geo.html')
    
    try:
        # 지도 생성
        generator = NewsMapGeneratorGeo()
        generator.generate(output_file)
        
        print()
        print("=" * 60)
        print("✅ 완료!")
        print(f"📂 파일 위치: {output_file}")
        print()
        print("🌐 브라우저에서 열기:")
        print(f"   {output_file}")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()