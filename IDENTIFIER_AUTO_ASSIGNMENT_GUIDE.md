# 🎯 Identifier 충돌 및 생년월일 불일치 자동 처리

## 핵심 기능

**서버가 다음 두 가지를 자동으로 처리합니다:**

1. **Identifier 충돌**: 서로 다른 사람이 같은 ID 사용 → 새 ID 자동 할당
2. **생년월일 불일치**: 같은 사람인데 생년월일 다름 → 기존 값으로 자동 수정

## 처리 방식

### 케이스 1: 같은 사람, 다른 생년월일 (데이터 입력 오류)

```
업로드: identifier=C12345, name=홍길동, birthDate=2020-01-15
기존: identifier=C12345, name=홍길동, birthDate=2020-01-01
        ↓
판단: 같은 사람이지만 생년월일이 다름 (입력 오류)
        ↓
처리: 생년월일을 2020-01-01로 자동 수정
        ↓
응답: birth_date_corrected=true
```

### 케이스 2: 다른 사람, 같은 ID (충돌)

```
업로드: identifier=C12345, name=김철수, birthDate=2021-05-20
기존: identifier=C12345, name=홍길동, birthDate=2020-01-01
        ↓
판단: 다른 사람인데 ID가 같음 (충돌)
        ↓
처리: 새 ID C54321 자동 할당
        ↓
응답: identifier_auto_assigned=true
```

## React Native 구현 (매우 간단)

### 최소 구현

```javascript
const uploadAudio = async (audioFile, metadata) => {
  const formData = new FormData();
  formData.append('file', audioFile);
  formData.append('metadata_json', JSON.stringify(metadata));

  const response = await axios.post(
    `http://210.125.93.241:8010/api/${metadata.category}/upload/`,
    formData
  );
  
  // ✅ identifier가 자동 할당된 경우 로컬 업데이트
  if (response.data.identifier_auto_assigned) {
    await AsyncStorage.setItem(
      'current_participant_id',
      response.data.new_identifier
    );
  }
  
  return response.data;
};
```

### 권장 구현 (알림 포함)

```javascript
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Alert } from 'react-native';

const uploadAudio = async (audioFile, metadata) => {
  const formData = new FormData();
  formData.append('file', audioFile);
  formData.append('metadata_json', JSON.stringify(metadata));

  try {
    const response = await axios.post(
      `http://210.125.93.241:8010/api/${metadata.category}/upload/`,
      formData
    );
    
    const data = response.data;
    
    // identifier 자동 할당 처리
    if (data.identifier_auto_assigned) {
      console.log('⚠️ Identifier 자동 할당:', data.warning);
      
      // 로컬 저장소 업데이트
      await updateLocalIdentifier(
        data.original_identifier,
        data.new_identifier,
        metadata
      );
      
      // 사용자에게 알림 (선택사항)
      Alert.alert(
        'ID 변경',
        `충돌로 인해 새로운 ID가 할당되었습니다.\n${data.original_identifier} → ${data.new_identifier}`,
        [{ text: '확인' }]
      );
    }
    
    return { success: true, data };
    
  } catch (error) {
    console.error('업로드 실패:', error);
    throw error;
  }
};

// 로컬 저장소 업데이트 함수
const updateLocalIdentifier = async (oldId, newId, metadata) => {
  try {
    // 기존 데이터 삭제
    await AsyncStorage.removeItem(`participant_${oldId}`);
    
    // 새 identifier로 저장
    await AsyncStorage.setItem(
      `participant_${newId}`,
      JSON.stringify({
        identifier: newId,
        category: metadata.category,
        name: metadata.name,
        birthDate: metadata.birthDate,
        updatedAt: new Date().toISOString(),
        note: `자동 할당 (원본: ${oldId})`
      })
    );
    
    console.log(`✅ 로컬 업데이트: ${oldId} → ${newId}`);
  } catch (error) {
    console.error('로컬 업데이트 실패:', error);
  }
};
```

## 응답 형식

### 1. 정상 업로드 (문제 없음)

```json
{
  "message": "업로드 성공",
  "file_path": "/media/audio/child/C12345/audio.wav",
  "audio_id": 12345,
  "identifier": "C12345"
}
```

### 2. 생년월일 자동 수정 (같은 사람, 입력 오류)

```json
{
  "message": "업로드 성공",
  "file_path": "/media/audio/child/C12345/audio.wav",
  "audio_id": 12346,
  "identifier": "C12345",
  "birth_date_corrected": true,
  "corrected_birth_date": "2020-01-01",
  "info": "ℹ️ 동일 인물(홍길동)의 생년월일이 '2020-01-01'로 자동 수정되었습니다. 데이터 일관성을 위해 기존 레코드와 동일한 생년월일을 사용합니다."
}
```

### 3. Identifier 자동 할당 (다른 사람, 충돌)

```json
{
  "message": "업로드 성공",
  "file_path": "/media/audio/child/C54321/audio.wav",
  "audio_id": 12347,
  "identifier": "C54321",
  "identifier_auto_assigned": true,
  "original_identifier": "C12345",
  "new_identifier": "C54321",
  "warning": "⚠️ 원본 identifier 'C12345'는 다른 화자가 사용 중입니다. 서버가 자동으로 'C54321'를 할당했습니다. 앱의 로컬 저장소를 업데이트해주세요."
}
```

## 장점

### ✅ React Native 개발자에게

1. **에러 처리 불필요**: try-catch로 충돌 에러 처리할 필요 없음
2. **재시도 로직 불필요**: 서버가 자동으로 처리
3. **간단한 구현**: 응답 확인 후 로컬만 업데이트
4. **데이터 손실 없음**: 충돌이 있어도 항상 성공

### ✅ 서버 관리자에게

1. **데이터 정합성 보장**: 충돌이 절대 발생하지 않음
2. **자동 로깅**: 충돌 발생 시 서버 로그에 기록
3. **백업 방어선**: 모델 레벨에서도 검증

## 테스트

### cURL 테스트

```bash
# 충돌 테스트 (C20946은 이미 사용 중)
curl -X POST \
  -F "file=@test.wav" \
  -F "metadata_json={\"identifier\":\"C20946\",\"birthDate\":\"2024-01-01\",\"name\":\"테스트\"}" \
  http://210.125.93.241:8010/api/child/upload/

# 예상: 자동으로 새 identifier 할당
```

### 테스트 스크립트

```bash
python3 test_identifier_auto_assignment.py
```

## 현재 데이터베이스 상태

- 총 identifier: 354개
- 충돌 identifier: 5개 (자동 처리로 인해 향후 0개)

## 추가 API (선택사항)

미리 identifier를 발급받고 싶다면:

```
GET /api/generate-identifier/?category=child
```

응답:
```json
{
  "success": true,
  "identifier": "C54321",
  "category": "child",
  "prefix": "C"
}
```

## 참고 문서

- 상세 가이드: [IDENTIFIER_CONFLICT_GUIDE.md](IDENTIFIER_CONFLICT_GUIDE.md)
- 충돌 검사: `python3 check_identifier_duplicates.py`
- 생년월일 검사: `python3 check_identifier_birth_dates.py`
