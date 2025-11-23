#!/bin/bash

# Development server script for dj_voice_manage
# Runs on port 8011 (allows simultaneous testing with production)

cd /var/www/html/dj_voice_manage || exit 1

# Ensure we're on develop branch
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "develop" ]; then
    echo "⚠️  Warning: You are on branch '$CURRENT_BRANCH', not 'develop'"
    echo "Switch to develop branch? (y/n)"
    read -r response
    if [ "$response" = "y" ]; then
        git checkout develop
    else
        echo "Exiting..."
        exit 1
    fi
fi

# Kill existing process on port 8011
echo "Stopping existing development server..."
lsof -ti:8011 | xargs kill -9 2>/dev/null
sleep 1

echo "Starting development server (port 8011)..."
echo "  Branch: develop"
echo "  URL: http://210.125.93.241:8011"
echo "  Press Ctrl+C to stop"
echo ""

# Run in foreground for easier debugging
python3 manage.py runserver 210.125.93.241:8011
