"""
데이터 전송 위치(권역) 통계

앱은 거주 지역을 권역 단위(수도권/강원권/충청권/전라권/경상권/제주권)로 저장하므로
권역 이름으로 집계하고, 지도 표시용으로 각 권역의 대략적인 중심 좌표를 붙입니다.
"""

from collections import defaultdict

from .models import AudioRecord

# 권역 중심 좌표 (지도 표시용 근사값)
REGION_COORDINATES = {
    '수도권': {'lat': 37.45, 'lng': 127.00},
    '강원권': {'lat': 37.75, 'lng': 128.30},
    '충청권': {'lat': 36.60, 'lng': 127.20},
    '전라권': {'lat': 35.30, 'lng': 127.00},
    '경상권': {'lat': 35.90, 'lng': 128.60},
    '제주권': {'lat': 33.40, 'lng': 126.55},
}

# 표기 변형 및 시·도 이름 → 권역
REGION_ALIASES = {
    '강원도': '강원권', '강원': '강원권',
    '전라도': '전라권', '전북': '전라권', '전남': '전라권', '광주': '전라권',
    '경기권': '수도권', '서울': '수도권', '경기': '수도권', '인천': '수도권',
    '충북': '충청권', '충남': '충청권', '대전': '충청권', '세종': '충청권', '충청도': '충청권',
    '경북': '경상권', '경남': '경상권', '대구': '경상권', '울산': '경상권', '부산': '경상권', '경상도': '경상권',
    '제주': '제주권', '제주도': '제주권',
}


def normalize_region(value):
    value = (value or '').strip()
    return REGION_ALIASES.get(value, value)


def build_upload_location_data():
    """권역별 업로드(파일) 수와 좌표 목록을 업로드 수 내림차순으로 반환"""
    upload_locations = defaultdict(int)
    for region, category_data in AudioRecord.objects.values_list('region', 'category_specific_data'):
        # region 컬럼 우선, 비어 있으면 category_specific_data의 region 사용
        if not region and isinstance(category_data, dict):
            region = category_data.get('region')
        region = normalize_region(region)
        if region in REGION_COORDINATES:
            upload_locations[region] += 1

    upload_location_data = [
        {'region': region, 'count': count, **REGION_COORDINATES[region]}
        for region, count in upload_locations.items()
    ]
    upload_location_data.sort(key=lambda x: x['count'], reverse=True)
    return upload_location_data
