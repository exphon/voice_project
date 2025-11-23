#!/bin/bash

# Production server script for dj_voice_manage
# Runs on port 8010 in background with nohup

cd /var/www/html/dj_voice_manage || exit 1

# Kill existing process on port 8010
echo "Stopping existing production server..."
lsof -ti:8010 | xargs kill -9 2>/dev/null
sleep 1

# Start production server
echo "Starting production server (port 8010)..."
nohup python3 manage.py runserver 210.125.93.241:8010 > server_production.log 2>&1 &
PID=$!

# Save PID
echo $PID > server_production.pid

echo "✓ Production server started!"
echo "  PID: $PID"
echo "  URL: http://210.125.93.241:8010"
echo "  Log: tail -f /var/www/html/dj_voice_manage/server_production.log"
echo ""
