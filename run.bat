@echo off
REM Matrix.se weekly scraper launcher (Ollama)
REM Kor scrape -> OCR -> HTML i ett svep.
REM Registrera detta i Windows Task Scheduler (se README.md)

setlocal

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM Konfiguration. Andra har om du vill byta modell eller server.
set "OCR_MODEL=openbmb/minicpm-v4.5"
REM Avkommentera for LM Studio istallet for Ollama:
REM set "OCR_BASE_URL=http://localhost:1234/v1"

echo === Steg 1/2: Skrapar och OCR:ar ===
python "%SCRIPT_DIR%matrix_scraper.py"
set "SCRAPE_EXIT=%ERRORLEVEL%"
if not "%SCRAPE_EXIT%"=="0" (
    echo.
    echo Scraper avslutad med fel %SCRAPE_EXIT% - hoppar over HTML-generering.
    exit /b %SCRAPE_EXIT%
)

echo.
echo === Steg 2/2: Genererar HTML-vy ===
python "%SCRIPT_DIR%view_prices.py"
set "VIEW_EXIT=%ERRORLEVEL%"

echo.
echo Klar. Scrape=%SCRAPE_EXIT%, HTML=%VIEW_EXIT%
echo Oppna prices.html med .\view.bat eller dubbelklicka pa filen.
exit /b %VIEW_EXIT%
