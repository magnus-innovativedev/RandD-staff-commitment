@echo off
start msedge --app=https://randd-staff-commitment.onrender.com
if %ERRORLEVEL% NEQ 0 (
    start chrome --app=https://randd-staff-commitment.onrender.com
)

