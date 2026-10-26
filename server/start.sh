#!/usr/bin/env bash
cd "$(dirname "$0")"

echo "Prüfe yt-dlp..."
python3 -m pip install --upgrade --quiet yt-dlp

echo "Starte Server..."
python3 server.py
