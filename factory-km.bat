@echo off

cd /d D:\AI\factory-km
call .venv\Scripts\activate.bat

powershell -NoProfile -Command "try { $health = Invoke-RestMethod http://127.0.0.1:8000/health -ErrorAction Stop; $api = Invoke-RestMethod http://127.0.0.1:8000/openapi.json -ErrorAction Stop; $paths = $api.paths.PSObject.Properties.Name; if (($health.health -eq 'ok') -and $health.vaultRoot -and ($paths -contains '/api/km/upload') -and ($paths -contains '/api/km/not-trained') -and ($paths -contains '/api/km/train')) { exit 0 } } catch {} exit 1" >nul 2>&1
if not errorlevel 1 goto loop

call :port_8000_is_listening
if not errorlevel 1 (
  echo ERROR: Port 8000 is already used by a stale or incompatible FastAPI instance.
  echo Stop that process, then run factory-km.bat again.
  exit /b 1
)

start "Factory-KM FastAPI" /b .venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
call :wait_for_fastapi
if errorlevel 1 exit /b 1

:loop
call :wait_for_fastapi
if errorlevel 1 exit /b 1

call :node_3006_is_current
if not errorlevel 1 (
  echo Factory-KM Node is already healthy at http://127.0.0.1:3006
  exit /b 0
)

call :port_3006_is_listening
if not errorlevel 1 (
  echo ERROR: Port 3006 is used by an unknown or stale web server.
  echo Stop that process, then run factory-km.bat again.
  exit /b 1
)

node server.js

echo webchat stopped. Restart in 10 seconds...
timeout /t 10

goto loop

:node_3006_is_current
powershell -NoProfile -Command "try { $webRoot = (Get-Location).Path; $checks = @(@('http://127.0.0.1:3006/assets/js/ask_AI_multi.js', (Join-Path $webRoot 'assets\js\ask_AI_multi.js')), @('http://127.0.0.1:3006/assets/css/main.css', (Join-Path $webRoot 'assets\css\main.css'))); $client = New-Object Net.WebClient; try { foreach ($check in $checks) { $liveBytes = $client.DownloadData($check[0]); $localBytes = [IO.File]::ReadAllBytes($check[1]); $sha = [Security.Cryptography.SHA256]::Create(); try { $liveHash = [BitConverter]::ToString($sha.ComputeHash($liveBytes)); $localHash = [BitConverter]::ToString($sha.ComputeHash($localBytes)); if ($liveHash -ne $localHash) { exit 1 } } finally { $sha.Dispose() } } } finally { $client.Dispose() }; exit 0 } catch { exit 1 }" >nul 2>&1
exit /b %errorlevel%

:port_3006_is_listening
powershell -NoProfile -Command "$client = New-Object Net.Sockets.TcpClient; try { $client.Connect('127.0.0.1', 3006); exit 0 } catch { exit 1 } finally { $client.Dispose() }" >nul 2>&1
exit /b %errorlevel%

:port_8000_is_listening
powershell -NoProfile -Command "$client = New-Object Net.Sockets.TcpClient; try { $client.Connect('127.0.0.1', 8000); exit 0 } catch { exit 1 } finally { $client.Dispose() }" >nul 2>&1
exit /b %errorlevel%

:wait_for_fastapi
set /a fastapi_attempts=0

:check_fastapi_health
powershell -NoProfile -Command "try { $health = Invoke-RestMethod http://127.0.0.1:8000/health -ErrorAction Stop; $api = Invoke-RestMethod http://127.0.0.1:8000/openapi.json -ErrorAction Stop; $paths = $api.paths.PSObject.Properties.Name; if (($health.health -eq 'ok') -and $health.vaultRoot -and ($paths -contains '/api/km/upload') -and ($paths -contains '/api/km/not-trained') -and ($paths -contains '/api/km/train')) { exit 0 } } catch {} exit 1" >nul 2>&1
if not errorlevel 1 exit /b 0

set /a fastapi_attempts+=1
if %fastapi_attempts% GEQ 30 (
  echo ERROR: FastAPI did not become healthy at http://127.0.0.1:8000/health within 30 seconds.
  exit /b 1
)

timeout /t 1 /nobreak >nul
goto check_fastapi_health
