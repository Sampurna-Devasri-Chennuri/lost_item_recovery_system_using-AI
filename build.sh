#!/usr/bin/env bash
# Render Build Script for AI-Based Lost-Item Recovery System
set -o errexit

echo "=================================================="
echo " Starting Build: Installing Dependencies"
echo "=================================================="
pip install --upgrade pip
pip install -r requirements.txt

echo "=================================================="
echo " Preparing Django Application"
echo "=================================================="
cd campusLostAndFound

echo "--> Collecting static files..."
python manage.py collectstatic --no-input

echo "--> Applying database migrations..."
python manage.py migrate

echo "=================================================="
echo " Build Succeeded!"
echo "=================================================="
