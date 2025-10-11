# Django Assets API 가이드 (React Native용)

Django 서버에 저장된 오디오 문제 파일들에 접근하는 API 문서입니다.

## 📁 파일 구조

```
assets/
  questions/
    auditory/
      jamo/              # 자모음 훈련 파일 (130개)
        Q_100_ji.wav
        Q_101_jja.wav
        ...
      sentence_easy/     # 문장 훈련 파일 (240개)
        List_1/
          Q_1_01_HP.wav
          ...
        List_2/
        ...
```

## 🔌 API 엔드포인트

### 1. 전체 폴더 구조 조회

**요청:**
```
GET http://210.125.101.159:8001/voice/assets/list/
```

**응답:**
```json
{
  "success": true,
  "structure": {
    "auditory": {
      "jamo": {
        "count": 130,
        "url": "/assets/questions/auditory/jamo/"
      },
      "sentence_easy": {
        "count": 240,
        "url": "/assets/questions/auditory/sentence_easy/"
      }
    },
    "senior": {}
  },
  "base_url": "/assets/"
}
```

### 2. 특정 폴더의 파일 목록 조회

**요청:**
```
GET http://210.125.101.159:8001/voice/assets/list/{category}/{folder}/
```

**예시 1: jamo 폴더**
```
GET http://210.125.101.159:8001/voice/assets/list/auditory/jamo/
```

**응답:**
```json
{
  "success": true,
  "category": "auditory",
  "folder": "jamo",
  "count": 130,
  "files": [
    {
      "filename": "Q_100_ji.wav",
      "url": "/assets/questions/auditory/jamo/Q_100_ji.wav",
      "path": "questions/auditory/jamo/Q_100_ji.wav"
    },
    {
      "filename": "Q_101_jja.wav",
      "url": "/assets/questions/auditory/jamo/Q_101_jja.wav",
      "path": "questions/auditory/jamo/Q_101_jja.wav"
    }
  ]
}
```

**예시 2: sentence_easy 폴더 (하위 폴더 포함)**
```
GET http://210.125.101.159:8001/voice/assets/list/auditory/sentence_easy/
```

**응답:**
```json
{
  "success": true,
  "category": "auditory",
  "folder": "sentence_easy",
  "count": 240,
  "files": [
    {
      "filename": "Q_1_01_HP.wav",
      "subfolder": "List_1",
      "url": "/assets/questions/auditory/sentence_easy/List_1/Q_1_01_HP.wav",
      "path": "questions/auditory/sentence_easy/List_1/Q_1_01_HP.wav"
    }
  ]
}
```

### 3. 오디오 파일 직접 재생

**URL 패턴:**
```
http://210.125.101.159:8001/assets/questions/{category}/{folder}/{filename}
```

**예시:**
```
http://210.125.101.159:8001/assets/questions/auditory/jamo/Q_100_ji.wav
http://210.125.101.159:8001/assets/questions/auditory/sentence_easy/List_1/Q_1_01_HP.wav
```

## 📱 React Native 사용 예시

### 1. 파일 목록 가져오기

```javascript
// 전체 구조 조회
const getAssetsStructure = async () => {
  try {
    const response = await fetch('http://210.125.101.159:8001/voice/assets/list/');
    const data = await response.json();
    console.log('Available folders:', data.structure);
    return data;
  } catch (error) {
    console.error('Error fetching assets:', error);
  }
};

// 특정 폴더의 파일 목록
const getJamoFiles = async () => {
  try {
    const response = await fetch(
      'http://210.125.101.159:8001/voice/assets/list/auditory/jamo/'
    );
    const data = await response.json();
    console.log(`Found ${data.count} files`);
    return data.files;
  } catch (error) {
    console.error('Error fetching jamo files:', error);
  }
};
```

### 2. 오디오 재생하기

**expo-av 사용:**
```javascript
import { Audio } from 'expo-av';

const playAudioFile = async (audioUrl) => {
  try {
    const { sound } = await Audio.Sound.createAsync(
      { uri: `http://210.125.101.159:8001${audioUrl}` },
      { shouldPlay: true }
    );
    
    await sound.playAsync();
    
    // 재생 완료 후 정리
    sound.setOnPlaybackStatusUpdate((status) => {
      if (status.didJustFinish) {
        sound.unloadAsync();
      }
    });
  } catch (error) {
    console.error('Error playing audio:', error);
  }
};

// 사용 예시
const files = await getJamoFiles();
if (files && files.length > 0) {
  playAudioFile(files[0].url); // /assets/questions/auditory/jamo/Q_100_ji.wav
}
```

**react-native-sound 사용:**
```javascript
import Sound from 'react-native-sound';

const playAudioFile = (audioUrl) => {
  const baseUrl = 'http://210.125.101.159:8001';
  const fullUrl = `${baseUrl}${audioUrl}`;
  
  const sound = new Sound(fullUrl, '', (error) => {
    if (error) {
      console.error('Failed to load sound', error);
      return;
    }
    
    // 재생
    sound.play((success) => {
      if (success) {
        console.log('Playback finished');
      } else {
        console.log('Playback failed');
      }
      sound.release();
    });
  });
};
```

### 3. 완전한 컴포넌트 예시

```javascript
import React, { useState, useEffect } from 'react';
import { View, FlatList, TouchableOpacity, Text } from 'react-native';
import { Audio } from 'expo-av';

const AudioPlayer = () => {
  const [files, setFiles] = useState([]);
  const [playing, setPlaying] = useState(null);
  const [sound, setSound] = useState(null);
  
  const BASE_URL = 'http://210.125.101.159:8001';
  
  useEffect(() => {
    loadFiles();
    
    return () => {
      if (sound) {
        sound.unloadAsync();
      }
    };
  }, []);
  
  const loadFiles = async () => {
    try {
      const response = await fetch(`${BASE_URL}/voice/assets/list/auditory/jamo/`);
      const data = await response.json();
      if (data.success) {
        setFiles(data.files);
      }
    } catch (error) {
      console.error('Error loading files:', error);
    }
  };
  
  const playSound = async (file) => {
    try {
      // 이전 사운드 정리
      if (sound) {
        await sound.unloadAsync();
      }
      
      const { sound: newSound } = await Audio.Sound.createAsync(
        { uri: `${BASE_URL}${file.url}` },
        { shouldPlay: true }
      );
      
      setSound(newSound);
      setPlaying(file.filename);
      
      newSound.setOnPlaybackStatusUpdate((status) => {
        if (status.didJustFinish) {
          setPlaying(null);
        }
      });
    } catch (error) {
      console.error('Error playing sound:', error);
      setPlaying(null);
    }
  };
  
  return (
    <View style={{ flex: 1, padding: 20 }}>
      <Text style={{ fontSize: 18, fontWeight: 'bold', marginBottom: 10 }}>
        자모음 훈련 ({files.length}개)
      </Text>
      <FlatList
        data={files}
        keyExtractor={(item) => item.filename}
        renderItem={({ item }) => (
          <TouchableOpacity
            onPress={() => playSound(item)}
            style={{
              padding: 15,
              borderBottomWidth: 1,
              borderBottomColor: '#ccc',
              backgroundColor: playing === item.filename ? '#e0f7fa' : 'white',
            }}
          >
            <Text>{item.filename}</Text>
            {playing === item.filename && (
              <Text style={{ color: 'blue', fontSize: 12 }}>재생 중...</Text>
            )}
          </TouchableOpacity>
        )}
      />
    </View>
  );
};

export default AudioPlayer;
```

## 🔧 개발 서버 URL

- **로컬 테스트:** `http://localhost:8001`
- **외부 접근:** `http://210.125.101.159:8001`
- **포트:** 8001 (Django 개발 서버)

## ⚠️ 주의사항

1. **CORS 설정:** 이미 `CORS_ALLOW_ALL_ORIGINS = True`로 설정되어 있어 React Native 앱에서 접근 가능합니다.

2. **Audio 권한:** React Native 앱에서 오디오 재생을 위해 필요한 권한을 설정해야 합니다.
   ```json
   // app.json (Expo)
   {
     "expo": {
       "ios": {
         "infoPlist": {
           "UIBackgroundModes": ["audio"]
         }
       },
       "android": {
         "permissions": ["RECORD_AUDIO", "MODIFY_AUDIO_SETTINGS"]
       }
     }
   }
   ```

3. **네트워크 상태:** 오디오 파일 로드 시 네트워크 상태를 체크하고 적절한 에러 처리를 해야 합니다.

## 📊 사용 가능한 파일

- **자모음 훈련 (jamo):** 130개 파일
- **문장 훈련 (sentence_easy):** 240개 파일 (6개 List로 구성)

각 파일은 WAV 포맷으로 제공되며, 직접 URL로 접근하거나 API를 통해 목록을 가져올 수 있습니다.

---

## 📤 파일 업로드 API

### 지원 파일 형식

**오디오 파일:**
- `.wav`, `.mp3`, `.m4a`, `.flac`, `.mp4`, `.webm`, `.ogg`

**메타데이터 파일:**
- `.json` (오디오 파일과 동일한 이름으로 업로드 권장)

### 업로드 엔드포인트

```
POST http://210.125.101.159:8001/api/upload/
```

### 업로드 방법

#### 방법 1: 오디오 + JSON 파일 동시 업로드 (권장)

```javascript
const formData = new FormData();

// 오디오 파일
formData.append('file', {
  uri: audioUri,
  type: 'audio/wav',
  name: 'recording_001.wav'
});

// JSON 메타데이터 파일
formData.append('metadata_file', {
  uri: jsonUri,
  type: 'application/json',
  name: 'recording_001.json'
});

// 기타 필드
formData.append('category', 'child');
formData.append('identifier', 'SPK001');

fetch('http://210.125.101.159:8001/api/upload/', {
  method: 'POST',
  body: formData,
  // Content-Type 헤더는 자동 생성되도록 설정하지 마세요!
});
```

#### 방법 2: 오디오 + JSON 문자열

```javascript
const metadata = {
  metainfo_child: {
    name: '홍길동',
    gender: '남',
    age: 8,
    region: '서울',
    task_type: '자모음 훈련'
  }
};

const formData = new FormData();
formData.append('file', audioFile);
formData.append('metadata_json', JSON.stringify(metadata));
formData.append('category', 'child');
```

### JSON 메타데이터 구조

```json
{
  "metainfo_child": {
    "name": "이름",
    "gender": "남/여",
    "age": 8,
    "birthDate": "2017-01-15",
    "region": "서울",
    "place": "가정",
    "task_type": "자모음 훈련",
    "sentence_index": "Q_1",
    "sentence_text": "가"
  }
}
```

### 응답

**성공 (200):**
```json
{
  "message": "업로드 성공",
  "file_path": "/media/child/SPK001_20250101_120000.wav"
}
```

**실패 (400):**
```json
{
  "error": "파일이 없습니다.",
  "debug": {
    "files_keys": [],
    "hint": "FormData 구성을 확인하세요"
  }
}
```

### 파일 이름 규칙

업로드된 파일은 자동으로 다음 형식으로 저장됩니다:
```
{identifier}_{timestamp}.wav
예: SPK001_20250111_143022.wav
```

메타데이터 JSON 파일도 동일한 이름으로 저장하면 자동으로 연결됩니다:
```
SPK001_20250111_143022.wav
SPK001_20250111_143022.json
```

