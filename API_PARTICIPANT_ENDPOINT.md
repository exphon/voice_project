# Participant Metadata API

## 개요
고유 ID(identifier)를 사용하여 참가자의 메타데이터와 모든 녹음 정보를 조회하는 API 엔드포인트입니다.

## 엔드포인트

```
GET /api/child/participant/{identifier}/
```

## URL 파라미터

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| identifier | string | Yes | 참가자의 고유 ID |

## 응답 형식

### 성공 응답 (200 OK)

```json
{
  "success": true,
  "data": {
    "identifier": "CHILD001",
    "category": "child",
    "gender": "남",
    "age": 5,
    "age_in_months": 60,
    "birth_date": "2020-01-15",
    "total_recordings": 10,
    "latest_recording_date": "2025-10-11T10:30:00Z",
    "category_data": {
      "school": "해피유치원",
      "class": "5세반",
      "teacher": "김선생님"
    },
    "recordings": [
      {
        "id": 123,
        "audio_file": "/media/audio/child/CHILD001_001.wav",
        "transcript": "안녕하세요",
        "status": "completed",
        "created_at": "2025-10-11T10:30:00Z",
        "snr_mean": 25.5
      },
      {
        "id": 122,
        "audio_file": "/media/audio/child/CHILD001_002.wav",
        "transcript": "감사합니다",
        "status": "completed",
        "created_at": "2025-10-10T14:20:00Z",
        "snr_mean": 23.2
      }
    ],
    "statistics": {
      "total": 10,
      "completed": 8,
      "pending": 1,
      "processing": 1,
      "failed": 0
    }
  }
}
```

### 실패 응답 (404 Not Found)

참가자를 찾을 수 없는 경우:

```json
{
  "success": false,
  "error": "참가자를 찾을 수 없습니다: CHILD999"
}
```

### 오류 응답 (500 Internal Server Error)

서버 오류가 발생한 경우:

```json
{
  "success": false,
  "error": "오류 메시지"
}
```

## 응답 필드 설명

### 기본 메타데이터

| 필드 | 타입 | 설명 |
|------|------|------|
| identifier | string | 참가자 고유 ID |
| category | string | 카테고리 (child, senior, atypical, auditory, normal) |
| gender | string | 성별 (남/여) |
| age | integer | 나이 (연) |
| age_in_months | integer | 나이 (개월) - 아동의 경우 |
| birth_date | string (ISO 8601) | 생년월일 |
| total_recordings | integer | 총 녹음 개수 |
| latest_recording_date | string (ISO 8601) | 가장 최근 녹음 날짜 |

### category_data

카테고리별 특정 메타데이터. 카테고리에 따라 다른 필드를 포함할 수 있습니다.

**child (아동):**
- school: 학교/유치원명
- class: 반
- teacher: 담당 교사
- parent_contact: 부모 연락처
- notes: 특이사항

**senior (노인):**
- residence_type: 거주 형태
- medical_history: 병력
- caregiver_name: 보호자 이름

**atypical (음성 장애):**
- diagnosis: 진단명
- therapy_duration: 치료 기간
- therapist: 담당 치료사

### recordings

해당 참가자의 모든 녹음 파일 목록 (최신순):

| 필드 | 타입 | 설명 |
|------|------|------|
| id | integer | 녹음 레코드 ID |
| audio_file | string | 오디오 파일 URL |
| transcript | string | 전사 내용 (수동 전사 우선) |
| status | string | 상태 (pending/processing/completed/failed) |
| created_at | string (ISO 8601) | 녹음 날짜 |
| snr_mean | float | 평균 SNR 값 |

### statistics

녹음 파일 통계:

| 필드 | 타입 | 설명 |
|------|------|------|
| total | integer | 전체 녹음 수 |
| completed | integer | 완료된 녹음 수 |
| pending | integer | 대기 중인 녹음 수 |
| processing | integer | 처리 중인 녹음 수 |
| failed | integer | 실패한 녹음 수 |

## 사용 예시

### cURL

```bash
curl -X GET "http://210.125.93.241:8010/api/child/participant/CHILD001/"
```

### JavaScript (Fetch API)

```javascript
fetch('http://210.125.93.241:8010/api/child/participant/CHILD001/')
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      console.log('참가자 정보:', data.data);
      console.log('총 녹음 수:', data.data.total_recordings);
      console.log('녹음 목록:', data.data.recordings);
    } else {
      console.error('오류:', data.error);
    }
  })
  .catch(error => console.error('네트워크 오류:', error));
```

### React Native (Axios)

```javascript
import axios from 'axios';

const fetchParticipantData = async (identifier) => {
  try {
    const response = await axios.get(
      `http://210.125.93.241:8010/api/child/participant/${identifier}/`
    );
    
    if (response.data.success) {
      const { data } = response.data;
      console.log('참가자:', data.identifier);
      console.log('나이:', data.age);
      console.log('녹음 수:', data.total_recordings);
      
      // 녹음 목록 처리
      data.recordings.forEach(recording => {
        console.log(`녹음 ${recording.id}: ${recording.transcript}`);
      });
      
      return data;
    } else {
      throw new Error(response.data.error);
    }
  } catch (error) {
    console.error('API 오류:', error.message);
    throw error;
  }
};

// 사용
fetchParticipantData('CHILD001')
  .then(data => {
    // 데이터 처리
  })
  .catch(error => {
    // 오류 처리
  });
```

### Python (requests)

```python
import requests

def get_participant_metadata(identifier):
    url = f"http://210.125.93.241:8010/api/child/participant/{identifier}/"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        data = response.json()
        
        if data['success']:
            metadata = data['data']
            print(f"참가자: {metadata['identifier']}")
            print(f"나이: {metadata['age']}세")
            print(f"총 녹음 수: {metadata['total_recordings']}")
            
            print("\n녹음 목록:")
            for recording in metadata['recordings']:
                print(f"  - ID {recording['id']}: {recording['transcript']}")
            
            return metadata
        else:
            print(f"오류: {data['error']}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"네트워크 오류: {e}")
        return None

# 사용
participant_data = get_participant_metadata('CHILD001')
```

## 특징

1. **최신 메타데이터 사용**: 가장 최근 녹음의 메타데이터를 기준으로 참가자 정보 제공
2. **전체 녹음 목록**: 해당 참가자의 모든 녹음 파일 정보 포함
3. **통계 정보**: 녹음 상태별 개수 제공
4. **카테고리별 데이터**: 카테고리에 따른 특정 메타데이터 포함
5. **최신순 정렬**: 녹음 목록은 최신 녹음부터 정렬

## 주의사항

1. **대소문자 구분**: identifier는 대소문자를 구분합니다
2. **특수문자**: identifier에 특수문자가 포함된 경우 URL 인코딩 필요
3. **응답 크기**: 녹음이 많은 경우 응답 크기가 클 수 있음 (필요시 페이지네이션 고려)
4. **캐싱**: 자주 조회되는 데이터는 클라이언트에서 캐싱 권장

## 관련 엔드포인트

- `GET /api/child/info/` - 아동 정보 목록
- `GET /api/audio/{id}/` - 개별 오디오 파일 상세 정보
- `GET /identifier/{identifier}/` - 웹 인터페이스용 identifier 페이지

## 버전 정보

- **최초 작성**: 2025-10-11
- **API 버전**: 1.0
- **Django 버전**: 4.2.24

## 변경 이력

| 날짜 | 버전 | 변경 내용 |
|------|------|-----------|
| 2025-10-11 | 1.0 | 최초 API 구현 |
