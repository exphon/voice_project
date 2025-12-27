#!/bin/bash
# 대시보드 캐시 자동 갱신 크론잡 설정 가이드
#
# 이 스크립트는 매일 새벽 3시에 대시보드 캐시를 자동으로 갱신합니다.
# 
# 크론잡 설정 방법:
# 1. crontab 편집: crontab -e
# 2. 아래 라인을 추가:
#
# 매일 새벽 3시에 실행
0 3 * * * cd /var/www/html/dj_voice_manage && /home/tyoon/anaconda3/envs/aligner/bin/python manage.py refresh_dashboard_cache >> /var/www/html/dj_voice_manage/cache_refresh.log 2>&1

# 또는 이 스크립트를 직접 실행하는 방식:
# 0 3 * * * /var/www/html/dj_voice_manage/refresh_cache_cron.sh

# 크론잡 확인: crontab -l
# 로그 확인: tail -f /var/www/html/dj_voice_manage/cache_refresh.log

# 수동 실행 방법:
cd /var/www/html/dj_voice_manage
/home/tyoon/anaconda3/envs/aligner/bin/python manage.py refresh_dashboard_cache
