@echo off
setlocal

REM Get the current script directory
set "LAUNCH_DIR=%~dp0"

REM Define persistent storage for extracted LNbits
set "PERSISTENT_DIR=%LOCALAPPDATA%\LNbits"

REM Remove existing LNbits directory before extraction
if exist "%PERSISTENT_DIR%" (
    echo Removing existing LNbits directory...
    rmdir /s /q "%PERSISTENT_DIR%"
)

REM Ensure the persistent directory exists
mkdir "%PERSISTENT_DIR%"

REM Extract LNbits from the package
echo Extracting LNbits to disk for better performance...
xcopy /E /I "%LAUNCH_DIR%lnbits" "%PERSISTENT_DIR%"

REM Ensure LNbits is executable
icacls "%PERSISTENT_DIR%\dist\lnbits.exe" /grant %USERNAME%:RX

REM Ensure the database and extensions directories exist
mkdir "%PERSISTENT_DIR%\database"
mkdir "%PERSISTENT_DIR%\extensions"

REM Set environment variables
set "LNBITS_DATA_FOLDER=%PERSISTENT_DIR%\database"
set "LNBITS_EXTENSIONS_PATH=%PERSISTENT_DIR%\extensions"
set "LNBITS_ADMIN_UI=true"

REM Define the LNbits URL
set "URL=http://0.0.0.0:5000"

REM Start LNbits
start "" "%PERSISTENT_DIR%\dist\lnbits.exe"
set LNBITS_PID=%ERRORLEVEL%

REM Wait a bit before showing the message
timeout /t 3 >nul

REM Show a pop-up message using PowerShell
powershell -Command "& {Add-Type -AssemblyName System.Windows.Forms; $result = [System.Windows.Forms.MessageBox]::Show('LNbits is running.`n`nClick OK to close it.', 'LNbits', 'OK', [System.Windows.Forms.MessageBoxIcon]::Information); exit 0}"

REM Stop LNbits when the user closes the dialog
taskkill /F /IM lnbits.exe
exit