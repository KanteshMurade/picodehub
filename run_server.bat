@echo off
title TECHNOSANKALP SOLUTIONS - RASPBERRY PI WORKSHOP SERVER
echo =========================================================
echo   TECHNOSANKALP SOLUTIONS - WORKSHOP & WORKBENCH SERVER   
echo =========================================================
echo Catalog URL:   http://localhost:5000/
echo Workbench URL: http://localhost:5000/ide
echo =========================================================

if exist "C:\Program Files\KiCad\9.0\bin\python.exe" (
  "C:\Program Files\KiCad\9.0\bin\python.exe" app.py
) else (
  python app.py
)

pause
