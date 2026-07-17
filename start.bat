@echo off
rem Sorena -- full assistant in one start: UI + face bridge + voice loop.
cd /d "%~dp0"

rem Serve the face UI (background, minimized). Port 8420 to stay off common dev ports.
start "sorena-web" /min uv run python -m http.server 8420 --directory web

rem Open the face in the default browser.
start "" http://localhost:8420/index.html

rem Voice loop + WebSocket bridge (foreground -- Ctrl+C here stops Sorena).
uv run python -m sorena.main

rem Clean up the web server when the voice loop exits.
taskkill /fi "WINDOWTITLE eq sorena-web*" /f >nul 2>&1
