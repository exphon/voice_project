# DJ Voice Manage - Development Workflow

## 브랜치 구조

- **main**: 프로덕션 서버 (port 8010)
- **develop**: 개발 브랜치 (port 8011)

## 사용법

### 1. 프로덕션 서버 시작/중지

```bash
# 시작 (백그라운드 실행, 터미널 닫아도 계속 실행)
./run.sh

# 중지
./stop.sh

# 로그 확인
tail -f server_production.log
```

**URL**: http://210.125.93.241:8010

---

### 2. 개발 작업 시작

```bash
# develop 브랜치로 전환 (자동으로 확인됨)
git checkout develop

# 개발 서버 실행 (포그라운드, Ctrl+C로 종료)
./run_dev.sh
```

**URL**: http://210.125.93.241:8011

**특징**:
- 프로덕션 서버(8010)와 동시 실행 가능
- 코드 변경 시 자동 리로드
- Ctrl+C로 즉시 중지 가능

---

### 3. 개발 완료 후 배포

```bash
# develop 브랜치에서 작업 커밋
git add .
git commit -m "Feature: 새로운 기능 추가"

# 배포 스크립트 실행
./deploy.sh
```

**deploy.sh가 자동으로 수행하는 작업**:
1. develop 브랜치 변경사항 확인
2. main 브랜치로 병합
3. 데이터베이스 마이그레이션 실행
4. 프로덕션 서버 재시작
5. develop 브랜치로 복귀

---

## 일반적인 작업 흐름

```bash
# 1. 개발 브랜치로 이동
git checkout develop

# 2. 개발 서버 실행 (8011 포트)
./run_dev.sh

# 3. 코드 수정 및 테스트...
# 브라우저에서 http://210.125.93.241:8011 로 테스트

# 4. 변경사항 커밋
git add .
git commit -m "설명"

# 5. 배포
./deploy.sh
```

---

## 서버 상태 확인

```bash
# 실행 중인 서버 확인
ps aux | grep "manage.py runserver"

# 포트 사용 확인
lsof -i:8010  # 프로덕션
lsof -i:8011  # 개발

# 프로덕션 로그 실시간 모니터링
tail -f server_production.log
```

---

## 긴급 롤백

문제가 발생한 경우 이전 상태로 되돌리기:

```bash
# main 브랜치에서
git checkout main
git log  # 커밋 히스토리 확인
git reset --hard <이전_커밋_해시>

# 프로덕션 서버 재시작
./stop.sh
./run.sh
```

---

## 주의사항

1. **항상 develop 브랜치에서 개발**하세요
2. **main 브랜치는 직접 수정하지 마세요** (deploy.sh를 통해서만 업데이트)
3. 데이터베이스 변경이 있으면 `python3 manage.py makemigrations` 후 커밋
4. 중요한 변경사항은 테스트 후 배포하세요

---

## 파일 설명

- `run.sh`: 프로덕션 서버 시작 (8010 포트, 백그라운드)
- `run_dev.sh`: 개발 서버 시작 (8011 포트, 포그라운드)
- `stop.sh`: 프로덕션 서버 중지
- `deploy.sh`: develop → main 배포 자동화
- `server_production.log`: 프로덕션 서버 로그
- `server_production.pid`: 프로덕션 서버 프로세스 ID
