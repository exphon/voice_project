# React Native 앱에서 참가자 정보 가져오기 가이드

## � 중요 업데이트

**✅ 2025-10-11 업데이트:**
- **모든 카테고리 지원**: `/api/participant/{id}/` 엔드포인트 추가
- **카테고리 제약 없음**: child, auditory, senior, atypical, normal 모두 조회 가능
- **하위 호환성 유지**: 기존 `/api/child/participant/{id}/` 계속 사용 가능

---

## �📱 빠른 시작

### 1. 기본 사용법

```javascript
// 참가자 ID로 데이터 가져오기 (모든 카테고리 지원)
const participantId = "C27508";  // 또는 "A46670" (auditory), "S12345" (senior) 등
const apiUrl = `http://210.125.93.241:8010/api/participant/${participantId}/`;

fetch(apiUrl)
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      console.log('참가자 정보:', data.data);
    }
  })
  .catch(error => console.error('오류:', error));
```

---

## 🚀 실전 예제

### Axios 사용 (권장)

```bash
# 설치
npm install axios
```

```javascript
import axios from 'axios';

const API_BASE_URL = 'http://210.125.93.241:8010';

// 참가자 정보 가져오기 (모든 카테고리 지원: child, auditory, senior, atypical, normal)
export const getParticipantInfo = async (identifier) => {
  try {
    const response = await axios.get(
      `${API_BASE_URL}/api/participant/${identifier}/`
    );
    
    if (response.data.success) {
      return response.data.data;
    } else {
      throw new Error(response.data.error);
    }
  } catch (error) {
    console.error('참가자 정보 조회 실패:', error.message);
    throw error;
  }
};

// 사용 예시
const loadParticipant = async () => {
  try {
    const participant = await getParticipantInfo('C27508');  // child
    // const participant = await getParticipantInfo('A46670');  // auditory
    // const participant = await getParticipantInfo('S12345');  // senior
    
    console.log('ID:', participant.identifier);
    console.log('이름:', participant.name);
    console.log('나이:', participant.age);
    console.log('성별:', participant.gender);
    console.log('생년월일:', participant.birth_date);
    console.log('녹음 수:', participant.total_recordings);
    
    // 녹음 파일 목록
    participant.recordings.forEach((recording, index) => {
      console.log(`녹음 ${index + 1}:`, recording.transcript);
    });
    
    return participant;
  } catch (error) {
    console.error('데이터 로딩 실패:', error);
  }
};
```

---

## 📊 응답 데이터 구조

```javascript
{
  "success": true,
  "data": {
    "identifier": "C27508",           // 참가자 고유 ID
    "name": "윤근우",                  // 참가자 이름
    "category": "child",               // 카테고리
    "gender": "남",                    // 성별
    "age": "11",                       // 나이
    "birth_date": "2014-06-16",       // 생년월일 (YYYY-MM-DD)
    "total_recordings": 2,             // 총 녹음 개수
    "latest_recording_date": "...",    // 최근 녹음 날짜
    
    "recordings": [                    // 녹음 파일 목록
      {
        "id": 1428,
        "audio_file": "/media/audio/...",
        "transcript": "아",
        "status": "completed",
        "created_at": "2025-10-10T16:11:42...",
        "snr_mean": null
      }
    ],
    
    "statistics": {                    // 통계
      "total": 2,
      "completed": 1,
      "pending": 0,
      "processing": 0,
      "failed": 0
    }
  }
}
```

---

## 🎨 React Native 컴포넌트 예제

### 참가자 프로필 화면

```javascript
import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ActivityIndicator, FlatList } from 'react-native';
import axios from 'axios';

const ParticipantProfile = ({ participantId }) => {
  const [participant, setParticipant] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadParticipantData();
  }, [participantId]);

  const loadParticipantData = async () => {
    try {
      setLoading(true);
      const response = await axios.get(
        `http://210.125.93.241:8010/api/child/participant/${participantId}/`
      );
      
      if (response.data.success) {
        setParticipant(response.data.data);
      } else {
        setError(response.data.error);
      }
    } catch (err) {
      setError('데이터를 불러올 수 없습니다.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <ActivityIndicator size="large" color="#0000ff" />;
  }

  if (error) {
    return <Text style={styles.error}>{error}</Text>;
  }

  if (!participant) {
    return <Text>참가자를 찾을 수 없습니다.</Text>;
  }

  return (
    <View style={styles.container}>
      {/* 기본 정보 */}
      <View style={styles.infoSection}>
        <Text style={styles.title}>{participant.name || participant.identifier}</Text>
        <Text style={styles.info}>ID: {participant.identifier}</Text>
        <Text style={styles.info}>성별: {participant.gender}</Text>
        <Text style={styles.info}>나이: {participant.age}세</Text>
        <Text style={styles.info}>생년월일: {participant.birth_date}</Text>
        <Text style={styles.info}>총 녹음 수: {participant.total_recordings}개</Text>
      </View>

      {/* 통계 */}
      <View style={styles.statsSection}>
        <Text style={styles.subtitle}>녹음 상태</Text>
        <Text>완료: {participant.statistics.completed}</Text>
        <Text>대기: {participant.statistics.pending}</Text>
        <Text>처리중: {participant.statistics.processing}</Text>
      </View>

      {/* 녹음 목록 */}
      <Text style={styles.subtitle}>녹음 목록</Text>
      <FlatList
        data={participant.recordings}
        keyExtractor={(item) => item.id.toString()}
        renderItem={({ item }) => (
          <View style={styles.recordingItem}>
            <Text style={styles.recordingId}>#{item.id}</Text>
            <Text>{item.transcript || '전사 내용 없음'}</Text>
            <Text style={styles.status}>{item.status}</Text>
          </View>
        )}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 20,
    backgroundColor: '#fff',
  },
  infoSection: {
    marginBottom: 20,
    padding: 15,
    backgroundColor: '#f5f5f5',
    borderRadius: 10,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    marginBottom: 10,
  },
  subtitle: {
    fontSize: 18,
    fontWeight: 'bold',
    marginTop: 15,
    marginBottom: 10,
  },
  info: {
    fontSize: 16,
    marginBottom: 5,
  },
  statsSection: {
    marginBottom: 20,
    padding: 15,
    backgroundColor: '#e3f2fd',
    borderRadius: 10,
  },
  recordingItem: {
    padding: 15,
    marginBottom: 10,
    backgroundColor: '#f9f9f9',
    borderRadius: 8,
    borderLeftWidth: 4,
    borderLeftColor: '#4CAF50',
  },
  recordingId: {
    fontWeight: 'bold',
    color: '#666',
  },
  status: {
    marginTop: 5,
    color: '#2196F3',
    fontStyle: 'italic',
  },
  error: {
    color: 'red',
    textAlign: 'center',
    fontSize: 16,
    padding: 20,
  },
});

export default ParticipantProfile;
```

---

## 🎯 실제 사용 시나리오

### 1. 앱 시작 시 참가자 목록 로드

```javascript
// API에서 모든 참가자 조회 (참가자 ID 목록 필요)
const participantIds = ['C27508', 'C27509', 'C27510'];

const loadAllParticipants = async () => {
  const participants = await Promise.all(
    participantIds.map(id => getParticipantInfo(id))
  );
  return participants;
};
```

### 2. 검색 기능

```javascript
const searchParticipant = async (searchId) => {
  try {
    const result = await getParticipantInfo(searchId);
    console.log('검색 결과:', result);
    return result;
  } catch (error) {
    console.log('참가자를 찾을 수 없습니다.');
    return null;
  }
};
```

### 3. 녹음 파일 재생

```javascript
import { Audio } from 'expo-av';

const playRecording = async (audioUrl) => {
  try {
    const fullUrl = `http://210.125.93.241:8010${audioUrl}`;
    const { sound } = await Audio.Sound.createAsync({ uri: fullUrl });
    await sound.playAsync();
  } catch (error) {
    console.error('재생 오류:', error);
  }
};

// 사용
participant.recordings.forEach((recording) => {
  if (recording.audio_file) {
    playRecording(recording.audio_file);
  }
});
```

---

## 🔧 API 서비스 클래스 (추천)

```javascript
// services/api.js
import axios from 'axios';

const API_BASE_URL = 'http://210.125.93.241:8010';

class VoiceAPI {
  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 10000,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  // 참가자 정보 조회
  async getParticipant(identifier) {
    try {
      const response = await this.client.get(
        `/api/participant/${identifier}/`
      );
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  // 에러 처리
  handleError(error) {
    if (error.response) {
      // 서버 응답 있음
      return new Error(error.response.data.error || '서버 오류');
    } else if (error.request) {
      // 요청은 보냈으나 응답 없음
      return new Error('서버에 연결할 수 없습니다.');
    } else {
      // 요청 설정 중 오류
      return new Error(error.message);
    }
  }
}

export default new VoiceAPI();
```

### 사용 예시

```javascript
import VoiceAPI from './services/api';

const MyComponent = () => {
  const loadData = async () => {
    try {
      const result = await VoiceAPI.getParticipant('C27508');
      
      if (result.success) {
        console.log('데이터:', result.data);
      }
    } catch (error) {
      console.error('오류:', error.message);
    }
  };

  return (
    // ... 컴포넌트 JSX
  );
};
```

---

## 🛡️ 에러 처리

```javascript
const getParticipantWithErrorHandling = async (identifier) => {
  try {
    const response = await axios.get(
      `http://210.125.93.241:8010/api/participant/${identifier}/`
    );
    
    if (response.data.success) {
      return {
        success: true,
        data: response.data.data
      };
    } else {
      return {
        success: false,
        error: response.data.error
      };
    }
  } catch (error) {
    if (error.response) {
      // 서버가 응답했지만 오류 상태
      return {
        success: false,
        error: `서버 오류: ${error.response.status}`
      };
    } else if (error.request) {
      // 요청은 보냈지만 응답 없음
      return {
        success: false,
        error: '네트워크 오류: 서버 응답 없음'
      };
    } else {
      // 요청 설정 중 오류
      return {
        success: false,
        error: `요청 오류: ${error.message}`
      };
    }
  }
};
```

---

## 📱 TypeScript 버전

```typescript
// types.ts
interface Recording {
  id: number;
  audio_file: string;
  transcript: string | null;
  status: string;
  created_at: string;
  snr_mean: number | null;
}

interface Statistics {
  total: number;
  completed: number;
  pending: number;
  processing: number;
  failed: number;
}

interface ParticipantData {
  identifier: string;
  name: string | null;
  category: string;
  gender: string;
  age: string;
  birth_date: string;
  total_recordings: number;
  latest_recording_date: string;
  recordings: Recording[];
  statistics: Statistics;
  category_data?: any;
}

interface APIResponse {
  success: boolean;
  data?: ParticipantData;
  error?: string;
}

// api.ts
import axios from 'axios';

const API_BASE_URL = 'http://210.125.93.241:8010';

export const getParticipantInfo = async (
  identifier: string
): Promise<ParticipantData> => {
  const response = await axios.get<APIResponse>(
    `${API_BASE_URL}/api/participant/${identifier}/`
  );
  
  if (response.data.success && response.data.data) {
    return response.data.data;
  } else {
    throw new Error(response.data.error || '데이터를 불러올 수 없습니다.');
  }
};
```

---

## 🎬 완전한 예제 앱

```javascript
// App.js
import React, { useState } from 'react';
import {
  View,
  TextInput,
  Button,
  Text,
  ScrollView,
  StyleSheet,
  Alert,
} from 'react-native';
import axios from 'axios';

const App = () => {
  const [participantId, setParticipantId] = useState('C27508');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const response = await axios.get(
        `http://210.125.93.241:8010/api/participant/${participantId}/`
      );
      
      if (response.data.success) {
        setData(response.data.data);
      } else {
        Alert.alert('오류', response.data.error);
      }
    } catch (error) {
      Alert.alert('오류', '데이터를 불러올 수 없습니다.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.header}>참가자 정보 조회</Text>
      
      <TextInput
        style={styles.input}
        value={participantId}
        onChangeText={setParticipantId}
        placeholder="참가자 ID 입력"
      />
      
      <Button 
        title={loading ? "로딩 중..." : "조회하기"} 
        onPress={fetchData}
        disabled={loading}
      />

      {data && (
        <View style={styles.resultContainer}>
          <Text style={styles.label}>이름: {data.name || '없음'}</Text>
          <Text style={styles.label}>ID: {data.identifier}</Text>
          <Text style={styles.label}>성별: {data.gender}</Text>
          <Text style={styles.label}>나이: {data.age}세</Text>
          <Text style={styles.label}>생년월일: {data.birth_date}</Text>
          <Text style={styles.label}>녹음 수: {data.total_recordings}개</Text>
          
          <Text style={styles.subtitle}>녹음 목록:</Text>
          {data.recordings.map((rec, index) => (
            <View key={rec.id} style={styles.recording}>
              <Text>녹음 {index + 1}: {rec.transcript || '없음'}</Text>
              <Text style={styles.small}>상태: {rec.status}</Text>
            </View>
          ))}
        </View>
      )}
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 20,
    backgroundColor: '#fff',
  },
  header: {
    fontSize: 24,
    fontWeight: 'bold',
    marginBottom: 20,
    textAlign: 'center',
  },
  input: {
    borderWidth: 1,
    borderColor: '#ddd',
    padding: 10,
    marginBottom: 10,
    borderRadius: 5,
  },
  resultContainer: {
    marginTop: 20,
    padding: 15,
    backgroundColor: '#f5f5f5',
    borderRadius: 10,
  },
  label: {
    fontSize: 16,
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 18,
    fontWeight: 'bold',
    marginTop: 15,
    marginBottom: 10,
  },
  recording: {
    padding: 10,
    marginBottom: 8,
    backgroundColor: '#fff',
    borderRadius: 5,
  },
  small: {
    fontSize: 12,
    color: '#666',
    marginTop: 4,
  },
});

export default App;
```

---

## 🌐 API 엔드포인트 정리

| 메서드 | URL | 설명 |
|--------|-----|------|
| GET | `/api/participant/{identifier}/` | 특정 참가자 정보 조회 (모든 카테고리) |
| GET | `/api/child/participant/{identifier}/` | 특정 참가자 정보 조회 (하위 호환성, child 전용) |

**예시:**
```
# 범용 (권장) - 모든 카테고리 지원
http://210.125.93.241:8010/api/participant/C27508/  # child
http://210.125.93.241:8010/api/participant/A46670/  # auditory
http://210.125.93.241:8010/api/participant/S12345/  # senior

# 하위 호환성 (child만)
http://210.125.93.241:8010/api/child/participant/C27508/
```

**참가자 ID 형식:**
- `C#####`: Child (아동)
- `A#####`: Auditory (청각 장애)
- `S#####`: Senior (노인)

---

## ✅ 체크리스트

개발 시작 전 확인사항:

- [ ] axios 또는 fetch 설치 확인
- [ ] 네트워크 권한 설정 (iOS: Info.plist, Android: AndroidManifest.xml)
- [ ] API 서버 주소 확인 (http://210.125.93.241:8010)
- [ ] 참가자 ID 형식 확인 (예: C27508)
- [ ] 에러 처리 로직 구현
- [ ] 로딩 상태 UI 구현

---

## 📞 문제 해결

**Q: "Network request failed" 오류가 발생해요**
- A: iOS에서는 Info.plist에 NSAppTransportSecurity 설정 필요
- Android에서는 network_security_config.xml 설정 필요

**Q: 한글이 깨져요**
- A: 응답 데이터가 이미 UTF-8로 인코딩되어 있으므로 별도 처리 불필요

**Q: 참가자를 찾을 수 없다고 나와요**
- A: identifier 값이 정확한지 확인 (대소문자 구분)

---

**작성일**: 2025-10-11  
**API 버전**: 1.0  
**서버**: http://210.125.93.241:8010
