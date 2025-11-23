#!/bin/bash

# Deploy changes from develop to production

cd /var/www/html/dj_voice_manage || exit 1

echo "==================================="
echo "Deployment Script - dj_voice_manage"
echo "==================================="
echo ""

# Check current branch
CURRENT_BRANCH=$(git branch --show-current)
echo "Current branch: $CURRENT_BRANCH"

if [ "$CURRENT_BRANCH" != "develop" ]; then
    echo "⚠️  You must be on 'develop' branch to deploy"
    exit 1
fi

# Show changes
echo ""
echo "Changes to be deployed:"
git diff main --stat

echo ""
echo "Continue with deployment? (y/n)"
read -r response

if [ "$response" != "y" ]; then
    echo "Deployment cancelled"
    exit 0
fi

# Commit any uncommitted changes in develop
if [ -n "$(git status --porcelain)" ]; then
    echo ""
    echo "Uncommitted changes found. Commit message:"
    read -r commit_msg
    git add -A
    git commit -m "$commit_msg"
fi

# Switch to main and merge
echo ""
echo "Switching to main branch..."
git checkout main

echo "Merging develop into main..."
git merge develop

if [ $? -ne 0 ]; then
    echo "❌ Merge conflict detected! Resolve conflicts and try again."
    exit 1
fi

echo ""
echo "Running database migrations..."
python3 manage.py migrate

echo ""
echo "Restarting production server..."
./stop.sh
sleep 2
./run.sh

echo ""
echo "✓ Deployment complete!"
echo "  Production: http://210.125.93.241:8010"
echo ""
echo "Switching back to develop branch..."
git checkout develop

echo ""
echo "Done! You can continue development on 'develop' branch."
