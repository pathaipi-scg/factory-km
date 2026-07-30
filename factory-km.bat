@echo off

cd /d D:\AI\factory-km
call .venv\Scripts\activate.bat

start "Factory-KM FastAPI" /b .venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

:loop
call :wait_for_fastapi
if errorlevel 1 exit /b 1

node server.js

echo webchat stopped. Restart in 10 seconds...
timeout /t 10

goto loop

:wait_for_fastapi
set /a fastapi_attempts=0

:check_fastapi_health
powershell -NoProfile -Command "try { $response = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/health -ErrorAction Stop; if ($response.StatusCode -eq 200) { exit 0 } } catch {} exit 1" >nul 2>&1
if not errorlevel 1 exit /b 0

set /a fastapi_attempts+=1
if %fastapi_attempts% GEQ 30 (
  echo ERROR: FastAPI did not become healthy at http://127.0.0.1:8000/health within 30 seconds.
  exit /b 1
)

timeout /t 1 /nobreak >nul
goto check_fastapi_health
