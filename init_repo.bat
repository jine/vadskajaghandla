@echo off
REM Engangs-setup: initierar git-repot, gor forsta committen.
REM Kor en gang efter att du har klonat eller skapat filerna.
REM Avinstallera/ta bort denna fil efter en lyckad korning.

setlocal
cd /d "%~dp0"

where git >nul 2>&1
if errorlevel 1 (
    echo Git hittades inte i PATH. Installera fran https://git-scm.com/download/win
    exit /b 1
)

REM Stada ev. trasig .git fran tidigare forsok
if exist ".git" (
    echo Befintlig .git hittad - tar bort for fresh init...
    rmdir /s /q .git
)

echo === git init ===
git init -b main
if errorlevel 1 exit /b 1

REM Satt en lokal author om inget ar konfigurerat globalt
git config user.email >nul 2>&1
if errorlevel 1 (
    git config user.email "jim@inleed.se"
    git config user.name "Jim"
)

echo.
echo === git add ===
git add .
git status --short

echo.
echo === git commit ===
git commit -m "Initial commit: Matrix.se veckoannons-scraper med lokal OCR via Ollama"
if errorlevel 1 (
    echo.
    echo Commit misslyckades. Kontrollera git status ovan.
    exit /b 1
)

echo.
echo === git log ===
git log --oneline

echo.
echo Klart! Repot ar initierat. Du kan ta bort init_repo.bat nu om du vill.
echo.
echo Vill du pusha till GitHub/GitLab senare:
echo   git remote add origin https://github.com/dittnamn/vadskajaghandla.git
echo   git push -u origin main
endlocal
