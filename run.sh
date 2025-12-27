#!/bin/bash

# Production server script for dj_voice_manage
# Runs on port 8010 in background with nohup

cd /var/www/html/dj_voice_manage || exit 1

# Hugging Face token for Pyannote speaker diarization
# IMPORTANT: Do not hard-code or commit tokens.
if [ -z "${HUGGINGFACE_TOKEN:-}" ]; then
	echo "ERROR: HUGGINGFACE_TOKEN is not set."
	echo "Set it in your shell environment (e.g. export HUGGINGFACE_TOKEN=...) and re-run."
	exit 1
fi
export HUGGINGFACE_TOKEN

# Kill existing Django processes
echo "Stopping existing Django server..."
pkill -f "manage.py runserver"
sleep 2

# Start production server
echo "Starting production server (port 8010)..."
nohup python manage.py runserver 0.0.0.0:8010 > django_server.log 2>&1 &
PID=$!

# Save PID
echo $PID > server_production.pid

echo "✓ Production server started!"
echo "  PID: $PID"
echo "  URL: http://210.125.93.241:8010"
echo "  Log: tail -f /var/www/html/dj_voice_manage/django_server.log"
echo "  Hugging Face Token: Loaded from env for Pyannote"
echo ""
