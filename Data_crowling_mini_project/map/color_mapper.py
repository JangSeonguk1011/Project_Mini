"""
감성 점수 및 부정 비율 색상 매핑
부정 기사 비율(%)에 따라 지도의 지역 색상을 결정하며, 
개별 기사의 감성 점수(Score) 레이블을 관리합니다.
"""

from typing import Optional, Dict


def get_sentiment_color(sentiment_score: float) -> str:
    """
    개별 뉴스 마커 또는 리스트용 색상 반환
    (팝업 내부 뉴스 목록 등에서 사용)
    """
    if sentiment_score is None or sentiment_score == 0:
        return 'gray'       # 중립 또는 데이터 없음
    elif sentiment_score > 0.5:
        return 'blue'       # 강한 긍정
    elif sentiment_score > 0:
        return 'lightblue'  # 약한 긍정
    elif sentiment_score < -0.5:
        return 'red'        # 강한 부정
    else:
        return 'lightred'   # 약한 부정


def get_sentiment_icon(sentiment_score: float) -> str:
    """
    감성 점수에 따른 아이콘 이름 반환
    """
    if sentiment_score is None or sentiment_score == 0:
        return 'info-sign'
    elif sentiment_score > 0:
        return 'arrow-up'    # 긍정
    else:
        return 'arrow-down'  # 부정


def get_region_color_by_avg(neg_ratio: float) -> str:
    """
    부정 기사 비율(%)에 따른 지역 구역 색상 결정 (GeoJSON용)
    지도 생성기에서 'stat[neg_ratio]'를 인자로 받습니다.
    
    Args:
        neg_ratio: 부정 기사 비율 (0 ~ 100)
    
    Returns:
        색상 코드 (HEX)
    """
    if neg_ratio is None:
        return '#CCCCCC'  # 데이터 없음 (회색)
    
    # [사용자 요청 기준 적용]
    if neg_ratio > 51:
        return '#FF0000'  # 부정 위험 (빨간색)
    elif neg_ratio < 50:
        return '#0000FF'  # 긍정 우세 (파란색)
    else:
        # 50% 이상 51% 이하 구간
        return '#FFFFFF'  # 중립 (흰색)


def get_sentiment_label(sentiment_score: float) -> str:
    """
    개별 감성 점수를 텍스트 레이블로 변환
    """
    if sentiment_score is None:
        return '분석 안 됨'
    elif sentiment_score == 0:
        return '중립'
    elif sentiment_score > 0.8:
        return '매우 긍정적'
    elif sentiment_score > 0.2:
        return '긍정적'
    elif sentiment_score > 0:
        return '약간 긍정적'
    elif sentiment_score < -0.5:
        return '매우 부정적'
    elif sentiment_score < -0.2:
        return '부정적'
    else:
        return '약간 부정적'


def get_color_legend() -> dict:
    """
    지도 우측 하단 범례 표시용 정보 (부정 비율 기준)
    """
    return {
        '부정 위험 (부정 비율 > 51%)': '#FF0000',
        '중립 지역 (50% ~ 51%)': '#FFFFFF',
        '긍정 우세 (부정 비율 < 50%)': '#0000FF',
        '데이터 없음': '#CCCCCC',
    }


if __name__ == '__main__':
    # 테스트 코드: 정상 작동 확인
    test_cases = [65.0, 50.5, 30.0, None]
    
    print("="*40)
    print(" [테스트] 부정 비율별 지역 색상 매핑")
    print("="*40)
    for ratio in test_cases:
        color = get_region_color_by_avg(ratio)
        label = "N/A" if ratio is None else f"{ratio}%"
        print(f"부정 비율: {label:>6}  =>  적용 색상: {color}")
    
    print("\n" + "="*40)
    print(" [범례 데이터 확인]")
    print("="*40)
    for title, hex_code in get_color_legend().items():
        print(f"{title}: {hex_code}")