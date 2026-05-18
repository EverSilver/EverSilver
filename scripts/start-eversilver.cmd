@echo off
set BACKEND_URL=http://127.0.0.1:8088
set VITE_BACKEND_URL=http://127.0.0.1:8088
set EVERSILVER_API_BASE_URL=http://127.0.0.1:8088
start "" "%~dp0..\app\src-tauri\target\release\Eversilver.exe"
