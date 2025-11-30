#!/bin/bash
# Script to update git remote and pull latest changes

cd /home/julian/dev/tendly/tendly-admin

echo "Checking current remote..."
git remote -v

echo ""
echo "Fetching from origin..."
git fetch origin

echo ""
echo "Pulling latest changes from main..."
git pull origin main

echo ""
echo "Current status:"
git status

