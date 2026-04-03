# 데이터 정합성 검사 및 수정 도구

## 🔍 검사 스크립트

### 1. 생년월일 불일치 검사 및 수정
**파일**: `fix_birth_date_inconsistency.py`

동일한 identifier + 이름을 가진 사람인데 생년월일이 다른 경우를 찾아 수정합니다.

```bash
# 검사만 수행
python3 fix_birth_date_inconsistency.py

# 수정 시뮬레이션 (실제 수정 안 함)
python3 fix_birth_date_inconsistency.py --fix

# 실제 수정 적용 (확인 메시지 표시)
python3 fix_birth_date_inconsistency.py --apply

# 자동 적용 (확인 없이)
python3 fix_birth_date_inconsistency.py --apply -y
```

**검사 항목**:
- 동일 identifier + 이름 = 같은 사람
- 생년월일이 다르면 = 데이터 입력 오류
- 가장 많이 사용된 생년월일로 자동 수정

**예시**:
```
Identifier: C27508, 이름: 윤근우
- 2014-06-16 (4개 레코드) ← 정답으로 선택
- 2014-06-26 (1개 레코드) ← 이것을 수정
```

---

### 2. Identifier 충돌 검사
**파일**: `check_identifier_duplicates.py`

동일한 identifier를 가진 서로 다른 사람(생년월일이 다른)을 찾습니다.

```bash
python3 check_identifier_duplicates.py
```

**검사 항목**:
- 동일 identifier + 다른 생년월일 = 서로 다른 사람
- 새로운 identifier 생성 제안

**예시**:
```
⚠️ Identifier: S43354
- 김현주 (1974-02-10)
- 김현미 (1973-07-11)
→ 서로 다른 사람이 같은 ID 사용!
```

---

### 3. 생년월일 일치 여부 검사
**파일**: `check_identifier_birth_dates.py`

동일한 identifier를 가진 모든 레코드의 생년월일이 일치하는지 검사합니다.

```bash
python3 check_identifier_birth_dates.py
```

**검사 항목**:
- 동일 identifier의 모든 레코드
- 생년월일 일치 여부
- 업로드 날짜 및 수정 날짜 표시

---

## 📊 검사 결과 요약

### 현재 데이터베이스 상태

| 항목 | 수량 | 상태 |
|------|------|------|
| 총 identifier | 354개 | - |
| 생년월일 불일치 (같은 사람) | 3명 | 🔧 수정 필요 |
| Identifier 충돌 (다른 사람) | 5건 | ⚠️ 확인 필요 |

### 발견된 문제

#### 1. 생년월일 불일치 (데이터 입력 오류)

1. **C20946 - 송하성**
   - 2020-01-01 (56개) ← 정답
   - 2021-11-08 (1개) ← 오류

2. **C27508 - 윤근우**
   - 2014-06-16 (4개) ← 정답
   - 2014-06-26 (1개) ← 오류

3. **S77778 - 유정희**
   - 1970-09-15 (53개) ← 정답
   - 1965-09-15, 1965-01-01, 1970-09-09, 1970-09-24 (각 1개) ← 오류

#### 2. Identifier 충돌 (서로 다른 사람)

1. **9** - 서유하(2019-09-07) vs 황서우(2021-08-28)
2. **C20946** - 송하성 (위 생년월일 문제와 동일)
3. **C27508** - 윤근우 (위 생년월일 문제와 동일)
4. **S43354** - 김현미(1973-07-11) vs 김현주(1974-02-10)
5. **S77778** - 유정희 (위 생년월일 문제와 동일)

---

## 🔧 자동 수정 메커니즘

### 서버 업로드 시 자동 처리

#### 케이스 1: 같은 사람, 다른 생년월일
```
업로드: identifier=C27508, name=윤근우, birthDate=2014-06-26
기존: identifier=C27508, name=윤근우, birthDate=2014-06-16
        ↓
서버가 자동으로 2014-06-16으로 수정
        ↓
응답: birth_date_corrected=true
```

#### 케이스 2: 다른 사람, 같은 identifier
```
업로드: identifier=S43354, name=김OO, birthDate=1975-01-01
기존: identifier=S43354, name=김현주, birthDate=1974-02-10
        ↓
서버가 자동으로 새 identifier 생성 (예: S12345)
        ↓
응답: identifier_auto_assigned=true, new_identifier=S12345
```

---

## 📝 권장 작업 순서

### 1단계: 기존 데이터 정리

```bash
# 1. 생년월일 불일치 검사
python3 fix_birth_date_inconsistency.py

# 2. 수정 내용 확인 (dry run)
python3 fix_birth_date_inconsistency.py --fix

# 3. 실제 수정 적용
python3 fix_birth_date_inconsistency.py --apply
```

### 2단계: 충돌 확인

```bash
# Identifier 충돌 검사
python3 check_identifier_duplicates.py
```

### 3단계: 최종 검증

```bash
# 전체 일치 여부 검사
python3 check_identifier_birth_dates.py
```

---

## 🚀 향후 방지 메커니즘

### 서버 측 (자동 처리)

1. **업로드 시 자동 검증**
   - 동일 identifier + 이름 + 다른 생년월일 → 기존 값으로 자동 수정
   - 동일 identifier + 다른 사람 → 새 identifier 자동 할당

2. **모델 레벨 검증**
   - `AudioRecord.save()` 메서드에서 이중 체크
   - 잘못된 데이터 저장 방지

### React Native 앱 측 (로컬 업데이트)

```javascript
// 서버 응답 처리
if (response.data.birth_date_corrected) {
  // 생년월일 수정됨 → 로컬 저장소 업데이트
  await AsyncStorage.setItem('birth_date', response.data.corrected_birth_date);
}

if (response.data.identifier_auto_assigned) {
  // Identifier 변경됨 → 로컬 저장소 업데이트
  await AsyncStorage.setItem('identifier', response.data.new_identifier);
}
```

---

## 📚 관련 문서

- [IDENTIFIER_AUTO_ASSIGNMENT_GUIDE.md](IDENTIFIER_AUTO_ASSIGNMENT_GUIDE.md) - 자동 할당 상세 가이드
- [IDENTIFIER_CONFLICT_GUIDE.md](IDENTIFIER_CONFLICT_GUIDE.md) - 충돌 처리 전체 가이드

---

## 💡 FAQ

### Q1: 생년월일이 틀린 것 같은데 어떻게 하나요?
**A**: 가장 많이 사용된 생년월일이 정답으로 간주됩니다. 수동으로 수정하려면 Django admin에서 수정하세요.

### Q2: 새 identifier는 어떻게 생성되나요?
**A**: 카테고리 접두사(C/S/A) + 5자리 랜덤 숫자로 생성됩니다. 중복 체크 후 할당됩니다.

### Q3: 자동 수정을 되돌릴 수 있나요?
**A**: 데이터베이스 백업이 있다면 가능합니다. 수정 전 백업을 권장합니다.

### Q4: 업로드 시 항상 자동 처리되나요?
**A**: 네, 서버가 자동으로 감지하고 처리합니다. React Native 앱은 응답만 확인하면 됩니다.
