@echo off
setlocal enabledelayedexpansion
title Glass MP3 - Starter & Auto-Setup
color 0b

echo ========================================================
echo          Glass MP3 - Ein-Klick Starter & Setup
echo ========================================================
echo.

:: 1. Pruefen ob Python installiert ist
echo [1/3] Pruefe Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python fehlt. Installiere automatisch via WinGet...
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    if %errorlevel% neq 0 (
        color 0c
        echo [FEHLER] WinGet konnte Python nicht automatisch installieren.
        echo Bitte installiere Python 3.12 kurz aus dem Microsoft Store:
        echo   1. Suche im Startmenue nach "Microsoft Store"
        echo   2. "Python 3.12" suchen und "Installieren" klicken.
        pause
        exit /b
    )
    echo Python erfolgreich installiert!
) else (
    echo [OK] Python ist bereit.
)

:: 2. Pruefen ob FFmpeg installiert ist
echo.
echo [2/3] Pruefe FFmpeg (fuer MP3-Konvertierung)...
where ffmpeg >nul 2>&1
if %errorlevel% neq 0 (
    if not exist "%LOCALAPPDATA%\Microsoft\WinGet\Links\ffmpeg.exe" (
        echo FFmpeg fehlt. Installiere automatisch via WinGet...
        winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
    )
)
echo [OK] FFmpeg ist bereit.

:: 3. yt-dlp aktualisieren
echo.
echo [3/3] Pruefe yt-dlp...
python -m pip install --upgrade --quiet yt-dlp
echo [OK] yt-dlp ist auf dem neuesten Stand.

:: 4. Server starten
echo.
echo ========================================================
echo  Server laeuft! Du kannst die Chrome Extension jetzt nutzen.
echo  (Lasse dieses Fenster einfach minimiert im Hintergrund offen)
echo ========================================================
echo.
python server.py

if %errorlevel% neq 0 (
    echo.
    echo [HINWEIS] Server wurde beendet.
    pause
)
