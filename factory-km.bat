@echo off

d:
cd D:\AI\factory-km
call .venv\Scripts\activate.bat

:loop
node server.js

echo webchat stopped. Restart in 10 seconds...
timeout /t 10

goto loop
