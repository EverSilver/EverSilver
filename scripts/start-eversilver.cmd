@echo off
REM Launcher for Eversilver. Chat is wired to OpenFang via
REM config.inference_url (http://62.171.154.39:4200/v1). DO NOT set
REM BACKEND_URL or EVERSILVER_API_BASE_URL here -- they steer the
REM EversilverBackendProvider arm and if pointed at a wrong host they
REM override the chat-factory and chat fails with ECONNREFUSED.
start "" "%~dp0..\app\src-tauri\target\release\Eversilver.exe"
