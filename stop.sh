#!/bin/bash

# Stop production server

cd /var/www/html/dj_voice_manage || exit 1

if [ -f server_production.pid ]; then
    PID=$(cat server_production.pid)
    if kill -0 $PID 2>/dev/null; then
        echo "Stopping production server (PID: $PID)..."
        kill $PID
        rm server_production.pid
        echo "✓ Production server stopped!"
    else
        echo "Server is not running (stale PID file)"
        rm server_production.pid
    fi
else
    echo "No PID file found. Trying to stop by port..."
    lsof -ti:8010 | xargs kill 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "✓ Server stopped"
    else
        echo "No server running on port 8010"
    fi
fi
