@echo off
echo.
echo ======================================================
echo   Spike AI Hackathon - Starting Server
echo ======================================================
echo.

REM Check if credentials.json exists
if not exist "credentials.json" (
    echo ERROR: credentials.json not found!
    echo Please place your Google credentials.json file in the project root.
    exit /b 1
)

echo [OK] credentials.json found
echo.

REM Check if .env file exists
if not exist ".env" (
    echo WARNING: No .env file found.
    echo Please create one from .env.example
    exit /b 1
)

echo [OK] .env file found
echo.

REM Start the server
echo Starting server on port 8080...
echo API will be available at: http://localhost:8080
echo Docs available at: http://localhost:8080/docs
echo.
echo Press Ctrl+C to stop the server
echo.

cd src
python -m uvicorn main:app --host 0.0.0.0 --port 8080 --reload
