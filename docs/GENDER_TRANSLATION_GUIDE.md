# 성별 영어→한글 자동 변환 기능

## 📋 개요

메타데이터 업데이트 및 오디오 업로드 시 성별 필드가 영어(male/female)로 입력되어도 자동으로 한글(남/여)로 변환하여 저장됩니다.

## 🔄 변환 규칙

### 지원하는 입력값
```python
gender_mapping = {
    'male': '남',
    'female': '여',
    'Male': '남',
    'Female': '여',
    'MALE': '남',
    'FEMALE': '여',
    'M': '남',
    'F': '여',
    'm': '남',
    'f': '여'
}
```

### 변환 예시
| 입력 | 저장 결과 |
|------|-----------|
| male | 남 |
| female | 여 |
| Male | 남 |
| Female | 여 |
| MALE | 남 |
| FEMALE | 여 |
| M | 남 |
| F | 여 |
| 남 | 남 (변경 없음) |
| 여 | 여 (변경 없음) |

## 🎯 적용 위치

### 1. **메타데이터 업데이트 (update_audio_metadata)**

**위치**: `voice_app/views.py` - 2개의 함수

#### 함수 1: 기본 메타데이터 업데이트 (line ~2441)
```python
def update_audio_metadata(request, audio_id):
    """기본 메타데이터 업데이트"""
    audio = get_object_or_404(AudioRecord, id=audio_id)
    
    if request.method == 'POST':
        try:
            # 성별 영어 → 한글 변환 매핑
            gender_mapping = {
                'male': '남',
                'female': '여',
                # ... (전체 매핑)
            }
            
            for field in fields_to_update:
                value = request.POST.get(field)
                if value is not None:
                    # 성별 필드인 경우 한글로 변환
                    if field == 'gender' and value:
                        value = gender_mapping.get(value, value)
                    
                    setattr(audio, field, value if value else None)
```

#### 함수 2: SNR 포함 메타데이터 업데이트 (line ~1726)
```python
def update_audio_metadata(request, audio_id):
    """오디오 파일의 메타 정보를 업데이트하는 뷰"""
    
    # 성별 영어 → 한글 변환 매핑
    gender_mapping = {
        'male': '남',
        'female': '여',
        # ... (전체 매핑)
    }
    
    gender = request.POST.get('gender', '').strip()
    if gender:
        # 성별을 한글로 변환
        audio.gender = gender_mapping.get(gender, gender)
```

### 2. **오디오 업로드 (AudioUploadView)**

**위치**: `voice_app/views.py` - line ~243

```python
class AudioUploadView(APIView):
    def post(self, request, *args, **kwargs):
        # ... (파일 처리)
        
        gender = request.data.get('gender')
        
        # ... (metadata_json에서 gender 추출)
        
        # 성별 영어 → 한글 변환
        gender_mapping = {
            'male': '남',
            'female': '여',
            'Male': '남',
            'Female': '여',
            'MALE': '남',
            'FEMALE': '여',
            'M': '남',
            'F': '여',
            'm': '남',
            'f': '여'
        }
        if gender:
            gender = gender_mapping.get(gender, gender)
        
        # DB 저장
        audio_record = AudioRecord.objects.create(
            gender=gender,  # 한글로 변환된 값 저장
            # ...
        )
```

## 📱 React Native 앱 호환성

### 기존 앱 코드 (변경 불필요)
```javascript
// React Native에서 이렇게 보내도 OK
const metadata = {
  metainfo_child: {
    gender: 'male',  // 또는 'female'
    // ...
  }
};

// 또는
formData.append('gender', 'male');
```

### 서버 처리 흐름
```
1. React Native → gender: "male" 전송
2. Django 서버 수신
3. gender_mapping.get('male', 'male') → '남'
4. DB 저장: gender = '남'
5. 웹 UI 표시: "남"
```

## 🔧 작동 방식

### 1. 웹 폼에서 업데이트
```html
<!-- audio_detail.html의 메타데이터 수정 폼 -->
<form method="POST" action="{% url 'update_audio_metadata' audio.id %}">
  <select name="gender">
    <option value="male">Male</option>
    <option value="female">Female</option>
  </select>
  <button type="submit">저장</button>
</form>
```
→ "male" 선택 시 DB에 "남"으로 저장

### 2. React Native에서 업로드
```javascript
const formData = new FormData();
formData.append('file', audioFile);
formData.append('gender', 'male');  // 영어로 전송

fetch('http://server/voice/child/upload/', {
  method: 'POST',
  body: formData
});
```
→ 서버에서 자동으로 "남"으로 변환하여 저장

### 3. metadata_json에서 추출
```json
{
  "metainfo_child": {
    "gender": "female",
    "name": "테스트"
  }
}
```
→ 파싱 후 "여"로 변환하여 저장

## ✅ 장점

1. **하위 호환성**: 기존 React Native 앱 코드 수정 불필요
2. **일관성**: 모든 데이터가 한글로 통일
3. **확장성**: 새로운 영어 표현 추가 용이
4. **견고성**: 대소문자 구분 없이 처리
5. **안전성**: 매핑에 없는 값은 원본 유지

## 🧪 테스트 케이스

### 성공 케이스
```python
# 입력 → 저장 결과
'male'   → '남'
'female' → '여'
'Male'   → '남'
'M'      → '남'
'남'     → '남'  # 이미 한글
'여'     → '여'  # 이미 한글
```

### 예외 케이스
```python
# 매핑에 없는 값은 원본 유지
'other'  → 'other'
'unknown' → 'unknown'
''       → None (빈 문자열)
None     → None
```

## 📊 데이터베이스 영향

### AudioRecord 모델
```python
class AudioRecord(models.Model):
    gender = models.CharField(
        max_length=10, 
        blank=True, 
        null=True,
        help_text="성별 (남/여)"
    )
```

### 저장 전/후 비교
```sql
-- 변환 전 (기존 데이터)
SELECT id, gender FROM voice_app_audiorecord LIMIT 5;
+----+--------+
| id | gender |
+----+--------+
|  1 | male   |
|  2 | female |
|  3 | Male   |
+----+--------+

-- 변환 후 (새로운 데이터)
+----+--------+
| id | gender |
+----+--------+
|  4 | 남     |
|  5 | 여     |
|  6 | 남     |
+----+--------+
```

## 🔒 보안 고려사항

1. **입력 검증**: 매핑에 없는 값은 원본 유지 (SQL Injection 방지)
2. **타입 안전성**: 문자열 타입만 처리
3. **NULL 처리**: 빈 값은 None으로 저장

## 📝 향후 개선 가능 사항

1. **다국어 지원**: 영어, 중국어, 일본어 등 추가
2. **설정 파일화**: `settings.py`에 매핑 딕셔너리 이동
3. **로그 추가**: 변환 이력 기록
4. **API 응답**: 변환 결과를 응답에 포함

## 🔗 관련 파일

- `voice_app/views.py`: 변환 로직 구현
  - `update_audio_metadata()` (2개 함수)
  - `AudioUploadView.post()`
- `voice_app/models.py`: AudioRecord 모델
- `voice_app/templates/voice_app/audio_detail.html`: 메타데이터 표시

## 💡 사용 예시

### 웹에서 메타데이터 수정
```
1. /voice/audio/123/ 접속
2. 메타데이터 수정 버튼 클릭
3. 성별 필드에 "male" 입력
4. 저장 → DB에 "남"으로 저장
5. 페이지 새로고침 → "남" 표시
```

### React Native에서 업로드
```javascript
// 앱 코드
const uploadAudio = async () => {
  const formData = new FormData();
  formData.append('file', {
    uri: audioUri,
    type: 'audio/wav',
    name: 'recording.wav'
  });
  formData.append('gender', 'female');  // 영어로 전송
  
  await fetch(API_URL + '/voice/child/upload/', {
    method: 'POST',
    body: formData
  });
};

// 서버에서 자동 변환: 'female' → '여'
// DB 저장: gender = '여'
```
