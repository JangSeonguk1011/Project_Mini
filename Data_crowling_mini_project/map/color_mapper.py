"""
감성 점수 색상 매핑
sentiment_score에 따라 마커 색상 결정
"""

from typing import Tuple


def get_sentiment_color(sentiment_score: float) -> str:
    """
    감성 점수에 따른 색상 반환
    
    Args:
        sentiment_score: 감성 점수
            > 0: 긍정 (파란색/초록색 계열)
            < 0: 부정 (빨간색 계열)
            = 0: 중립 (회색)
    
    Returns:
        Folium 마커 색상 문자열
    """
    if sentiment_score is None or sentiment_score == 0:
        return 'gray'  # 중립 또는 데이터 없음
    elif sentiment_score > 0.8:
        return 'blue'  # 매우 강한 긍정
    elif sentiment_score > 0:
        return 'lightgreen'  # 약한 긍정 (연한 파랑 -> 연한 초록으로 수정)
    elif sentiment_score < -0.5:
        return 'red'  # 강한 부정
    else:
        return 'lightred'  # 약한 부정


def get_sentiment_icon(sentiment_score: float) -> str:
    """
    감성 점수에 따른 아이콘 반환
    
    Args:
        sentiment_score: 감성 점수
    
    Returns:
        Bootstrap 아이콘 이름
    """
    if sentiment_score is None or sentiment_score == 0:
        return 'info-sign'
    elif sentiment_score > 0:
        return 'arrow-up'  # 긍정
    else:
        return 'arrow-down'  # 부정


def get_region_color_by_avg(avg_sentiment: float) -> str:
    """
    지역 평균 감성에 따른 색상 (CircleMarker 및 GeoJSON용)
    
    Args:
        avg_sentiment: 평균 감성 점수
    
    Returns:
        색상 코드 (HEX)
    """
    if avg_sentiment is None or avg_sentiment == 0:
        return '#FFFFFF'  # 흰색
    elif avg_sentiment > 0.8:
        return '#0066CC'  # 매우 강한 파랑
    elif avg_sentiment > 0:
        return '#81C784'  # 연한 초록 (연한 파랑 -> 연한 초록 #81C784로 수정)
    elif avg_sentiment < -0.3:
        return '#CC0000'  # 진한 빨강
    else:
        return '#FF6666'  # 연한 빨강


def get_sentiment_label(sentiment_score: float) -> str:
    """
    감성 점수를 텍스트로 변환
    
    Args:
        sentiment_score: 감성 점수
    
    Returns:
        감성 레이블 문자열
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
    범례용 색상 정보 반환
    
    Returns:
        {label: color} 딕셔너리
    """
    return {
        '매우 긍정적 (> 0.8)': 'blue',
        '긍정적 (0 ~ 0.8)': 'lightgreen', # 연한 초록으로 수정
        '중립 (0)': 'white',
        '부정적 (-0.5 ~ 0)': 'lightred',
        '매우 부정적 (< -0.5)': 'red',
    }


if __name__ == '__main__':
    # 테스트 데이터
    test_scores = [0.8, 0.3, 0, -0.3, -0.8, None]
    
    print("=== 감성 점수별 색상 매핑 ===")
    for score in test_scores:
        color = get_sentiment_color(score)
        label = get_sentiment_label(score)
        icon = get_sentiment_icon(score)
        
        # score가 None일 경우 정렬 포맷(:>5)에서 에러가 발생하므로 str()로 변환하여 출력
        score_str = str(score)
        print(f"점수: {score_str:>5} → 색상: {color:>10}, 레이블: {label:>15}, 아이콘: {icon}")
    
    print("\n=== 범례 ===")
    for label, color in get_color_legend().items():
        print(f"{label}: {color}")