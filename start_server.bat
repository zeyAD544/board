@echo off
cd /d "%~dp0"
start "" python server.py
timeout /t 2 /nobreak >nul
start "" http://localhost:8000/viewing_room.html
