# Identifier 충돌 방지 가이드

## 문제 상황

동일한 identifier를 가진 서로 다른 사람(생년월일이 다른 경우)이 업로드되면 데이터 정합성에 문제가 발생합니다.

## 🎯 해결 방법: 서버 자동 처리 (권장)

### React Native 앱 업데이트 전까지 서버가 자동으로 처리

**서버가 identifier 충돌을 감지하면 자동으로 새 identifier를 생성하여 저장합니다.**

#### 동작 방식

1. **React Native → 서버**: 중복된 identifier로 업로드
2. **서버 검증**: 동일 identifier + 다른 생년월일 감지
3. **서버 자동 처리**: 
   - 새로운 사용 가능한 identifier 자동 생성
   - 새 identifier로 데이터 저장
   - 응답에 새 identifier 정보 포함
4. **React Native 수신**: 새 identifier를 받아 로컬 저장소 업데이트

#### 성공 응답 (자동 할당된 경우)

```json
{
  "message": "업로드 성공",
  "file_path": "/media/audio/child/C54321/audio.wav",
  "audio_id": 12345,
  "identifier": "C54321",
  "identifier_auto_assigned": true,
  "original_identifier": "C12345",
  "new_identifier": "C54321",
  "warning": "⚠️ 원본 identifier 'C12345'는 다른 화자가 사용 중입니다. 서버가 자동으로 'C54321'를 할당했습니다. 앱의 로컬 저장소를 업데이트해주세요."
}
```

#### 성공 응답 (정상 업로드)

```json
{
  "message": "업로드 성공",
  "file_path": "/media/audio/child/C12345/audio.wav",
  "audio_id": 12345,
  "identifier": "C12345"
}
```

## React Native 앱 구현 (간단함)

### 기본 업로드 + 자동 처리

```javascript
import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

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
    
    // ✅ identifier가 자동 할당된 경우 로컬 저장소 업데이트
    if (data.identifier_auto_assigned) {
      console.log('⚠️ Identifier 자동 할당:', data.warning);
      
      // 로컬 저장소의 identifier 업데이트
      await updateLocalIdentifier(
        data.original_identifier,
        data.new_identifier,
        metadata
      );
      
      // UI에 알림 표시 (선택사항)
      Alert.alert(
        'Identifier 변경',
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
        note: `자동 할당됨 (원본: ${oldId})`
      })
    );
    
    console.log(`✅ 로컬 저장소 업데이트: ${oldId} → ${newId}`);
  } catch (error) {
    console.error('로컬 저장소 업데이트 실패:', error);
  }
};
```

### 더 간단한 버전 (최소한의 코드)

```javascript
const uploadAudio = async (audioFile, metadata) => {
  const formData = new FormData();
  formData.append('file', audioFile);
  formData.append('metadata_json', JSON.stringify(metadata));

  const response = await axios.post(
    `http://210.125.93.241:8010/api/${metadata.category}/upload/`,
    formData
  );
  
  // 서버에서 할당한 identifier로 로컬 업데이트
  if (response.data.identifier_auto_assigned) {
    await AsyncStorage.setItem(
      'current_participant_id',
      response.data.new_identifier
    );
  }
  
  return response.data;
};
```

## 서버 측 방지 메커니즘

### 1. 자동 Identifier 할당 (views.py) ⭐ 주요 기능
- 업로드 시 identifier 충돌 자동 감지
- 충돌 발견 시 새로운 사용 가능한 identifier 자동 생성
- 새 identifier로 데이터 저장
- 응답에 변경 정보 포함하여 React Native가 로컬 업데이트 가능

### 2. 모델 레벨 검증 (models.py)
- `AudioRecord.save()` 메서드에서 이중 검증
- 동일 identifier + 다른 생년월일 저장 시 `ValidationError` 발생 (백업 방어선)

### 3. 검사 스크립트
```bash
python3 check_identifier_duplicates.py
```

## 추가 기능: 사전 Identifier 발급 (선택사항)
React Native 앱이 원한다면 업로드 전에 미리 identifier를 발급받을 수도 있습니다.
#### API 엔드포인트

```
GET /api/generate-identifier/?category=child
```

#### 응답

```json
{
  "success": true,
  "identifier": "C12345",
  "category": "child",
  "prefix": "C"
}
```

#### React Native 구현 예시

```javascript
// 새 참가자 등록 시
const registerNewParticipant = async (category = 'child') => {
  try {
    // 1. 서버에서 사용 가능한 identifier 발급
    const response = await axios.get(
      `http://210.125.93.241:8010/api/generate-identifier/?category=${category}`
    );
    
    if (response.data.success) {
      const newIdentifier = response.data.identifier;
      console.log('새 Identifier:', newIdentifier);
      
      // 2. 로컬에 저장 (AsyncStorage 등)
      await AsyncStorage.setItem(`participant_${newIdentifier}`, JSON.stringify({
        identifier: newIdentifier,
        category: category,
        createdAt: new Date().toISOString()
      }));
      
      return newIdentifier;
    }
  } catch (error) {
    console.error('Identifier 생성 실패:', error);
    // Fallback: 로컬에서 랜덤 생성 (권장하지 않음)
    return generateLocalIdentifier(category);
  }
};

// 사용 예시
const startNewSession = async () => {
  const identifier = await registerNewParticipant('child');
  
  setParticipantData({
    identifier: identifier,
    name: '',
    birthDate: '',
    gender: ''
  });
};
```

### 방법 3: Hybrid 접근 (권장)

1. **신규 참가자**: 서버에서 미리 identifier 발급
2. **기존 참가자**: 로컬 저장된 identifier 사용
3. **충돌 발생**: 자동으로 새 identifier 재발급

```javascript
class IdentifierManager {
  constructor() {
    this.cache = new Map();
  }

  // 신규 참가자용 identifier 발급
  async getNewIdentifier(category = 'child') {
    try {
      const response = await axios.get(
        `http://210.125.93.241:8010/api/generate-identifier/?category=${category}`
      );
      
      if (response.data.success) {
        const identifier = response.data.identifier;
        this.cache.set(identifier, { category, createdAt: Date.now() });
        await this.saveToStorage(identifier, category);
        return identifier;
      }
    } catch (error) {
      console.error('서버에서 identifier 발급 실패:', error);
      throw error;
    }
  }

  // 기존 참가자 identifier 로드
  async loadIdentifier(identifier) {
    const stored = await AsyncStorage.getItem(`participant_${identifier}`);
    if (stored) {
      const data = JSON.parse(stored);
      this.cache.set(identifier, data);
      return data;
    }
    return null;
  }

  // 충돌 처리
  async handleConflict(oldIdentifier, suggestedIdentifier, metadata) {
    console.log(`Identifier 충돌: ${oldIdentifier} -> ${suggestedIdentifier}`);
    
    // 로컬 저장소 업데이트
    await AsyncStorage.removeItem(`participant_${oldIdentifier}`);
    await this.saveToStorage(suggestedIdentifier, metadata.category);
    
    // 캐시 업데이트
    this.cache.delete(oldIdentifier);
    this.cache.set(suggestedIdentifier, { ...metadata, identifier: suggestedIdentifier });
    
    return suggestedIdentifier;
  }

  async saveToStorage(identifier, category) {
    await AsyncStorage.setItem(`participant_${identifier}`, JSON.stringify({
      identifier,
      category,
      updatedAt: new Date().toISOString()
    }));
  }
}

// 전역 인스턴스
const identifierManager = new IdentifierManager();

// 업로드 함수
const smartUpload = async (audioFile, metadata) => {
  const formData = new FormData();
  formData.append('file', audioFile);
  formData.append('metadata_json', JSON.stringify(metadata));

  try {
    const response = await axios.post(
      `http://210.125.93.241:8010/api/${metadata.category}/upload/`,
      formData
    );
    return { success: true, data: response.data };
    
  } catch (error) {
    if (error.response?.status === 400 && error.response?.data?.conflict) {
      const { suggested_identifier } = error.response.data;
      
      if (suggested_identifier) {
        // 자동으로 새 identifier 사용
        const newIdentifier = await identifierManager.handleConflict(
          metadata.identifier,
          suggested_identifier,
          metadata
        );
        
        // 재시도
        metadata.identifier = newIdentifier;
        return await smartUpload(audioFile, metadata);
      }
    }
    throw error;
  }
};
```

## 카테고리별 Identifier 접두사

| 카테고리 | 접두사 | 예시 | 설명 |
|---------|-------|------|------|
| child | C | C12345 | 아동 |
| senior | S | S12345 | 성인/노인 |
| auditory | A | A12345 | 청각 장애 |
| atypical | A | A12345 | 음성 장애 |
| normal | N | N12345 | 일반 |

## API 엔드포인트 정리

### 새 Identifier 생성
```
GET /api/generate-identifier/?category=child
```

**응답 예시:**
```json
{
  "success": true,
  "identifier": "C54321",
  "category": "child",
  "prefix": "C"
}
```

### 업로드 (충돌 검증 포함)
```
POST /api/child/upload/
```

**충돌 시 응답:**
```json
{
  "error": "동일한 identifier 'C12345'를 가진 다른 화자가 이미 존재합니다...",
  "conflict": true,
  "existing_identifier": "C12345",
  "existing_birth_date": "2020-01-01",
  "provided_birth_date": "2021-05-15",
  "suggested_identifier": "C54321"
}
```

## 권장 워크플로우

### 신규 참가자 등록
```
1. 사용자가 새 참가자 등록 시작
   ↓
2. 서버에 새 identifier 요청
   GET /api/generate-identifier/?category=child
   ↓
3. 받은 identifier를 로컬에 저장
   ↓
4. 이후 모든 녹음에 해당 identifier 사용
```

### 기존 참가자 녹음
```
1. 로컬에서 identifier 불러오기
   ↓
2. 녹음 + 메타데이터 업로드
   ↓
3. 충돌 발생 시 suggested_identifier 자동 적용
   ↓
4. 로컬 identifier 업데이트
```

## 테스트

### cURL 예시

```bash
# 1. 새 identifier 생성
curl "http://210.125.93.241:8010/api/generate-identifier/?category=child"

# 2. 업로드 (충돌 테스트)
curl -X POST \
  -F "file=@test.wav" \
  -F "metadata_json={\"identifier\":\"C12345\",\"birthDate\":\"2020-01-01\"}" \
  http://210.125.93.241:8010/api/child/upload/
```

## 주의사항

1. **Identifier는 한 번 발급되면 변경하지 않는 것이 원칙**
   - 충돌 시에만 예외적으로 새 ID 발급
   
2. **로컬 저장소와 서버 동기화**
   - 새 ID 발급 시 로컬 저장소도 업데이트
   
3. **오프라인 모드**
   - 오프라인 시 로컬 identifier 사용
   - 온라인 복귀 시 충돌 검증
   
4. **백업 및 복구**
   - Identifier 정보 백업 권장
   - 앱 재설치 시 복구 메커니즘 필요
