#!/usr/bin/env python3
"""
Glass MP3 - Local Companion Server
Empfängt Download-Aufträge von der Chrome-Extension und wandelt YouTube-Videos blitzschnell mit yt-dlp & ffmpeg um.
"""

import sys
import os
import json
import shutil
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

# Versuche yt_dlp zu importieren
try:
    import yt_dlp
except ImportError:
    print("\n[FEHLER] yt-dlp ist noch nicht installiert!")
    print("Bitte führe aus: pip install --upgrade yt-dlp\n")
    sys.exit(1)

PORT = 48123

# Standard-Speicherordner ermitteln (Downloads)
def get_download_dir():
    home = Path.home()
    downloads = home / "Downloads"
    if downloads.exists():
        return downloads
    music = home / "Music"
    if music.exists():
        return music
    return home

DOWNLOAD_DIR = get_download_dir()

# FFmpeg-Suchpfade auf Windows absichern
def ensure_ffmpeg_in_path():
    if shutil.which("ffmpeg"):
        return True
    
    # Häufige Windows WinGet & Standardpfade
    possible_paths = [
        Path.home() / "AppData/Local/Microsoft/WinGet/Links",
        Path("C:/ffmpeg/bin"),
        Path("C:/Program Files/ffmpeg/bin"),
        Path("C:/ProgramData/chocolatey/bin"),
    ]
    
    # WinGet Packages-Ordner rekursiv durchsuchen
    winget_pkg = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
    if winget_pkg.exists():
        for p in winget_pkg.glob("**/ffmpeg.exe"):
            possible_paths.append(p.parent)

    for p in possible_paths:
        if (p / "ffmpeg.exe").exists() or (p / "ffmpeg").exists():
            os.environ["PATH"] = str(p) + os.pathsep + os.environ.get("PATH", "")
            return True

    return False

# Globaler Status für die Extension
current_job = {
    "status": "idle",  # "idle", "downloading", "converting", "finished", "error"
    "progress": 0,
    "title": "",
    "filename": "",
    "error": None
}
job_lock = threading.Lock()

def progress_hook(d):
    global current_job
    with job_lock:
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes', 0)
            pct = (downloaded / total * 100) if total > 0 else 0
            current_job['status'] = 'downloading'
            current_job['progress'] = min(90, max(5, pct))
            info = d.get('info_dict', {})
            if info and 'title' in info and not current_job['title']:
                current_job['title'] = info['title']
        elif d['status'] == 'finished':
            current_job['status'] = 'converting'
            current_job['progress'] = 92

def run_download_task(url, fmt, quality):
    global current_job
    try:
        with job_lock:
            current_job = {
                "status": "downloading",
                "progress": 5,
                "title": "",
                "filename": "",
                "error": None
            }

        # Dateinamen-Muster
        outtmpl = str(DOWNLOAD_DIR / "%(title)s.%(ext)s")

        if fmt == "mp4":
            # Video Download
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'outtmpl': outtmpl,
                'progress_hooks': [progress_hook],
                'quiet': True,
                'no_warnings': True
            }
        else:
            # MP3 Audio Download mit FFmpeg
            bitrate = str(quality) if quality in ["192", "256", "320"] else "320"
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': outtmpl,
                'postprocessors': [
                    {
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': bitrate,
                    },
                    {
                        'key': 'FFmpegMetadata',
                        'add_metadata': True,
                    }
                ],
                'progress_hooks': [progress_hook],
                'quiet': True,
                'no_warnings': True
            }

        print(f"\n[START] Lade: {url} ({fmt.upper()} - {quality}k)")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'Audio')
            
            # Ermittle den endgültigen Dateinamen
            ext = "mp4" if fmt == "mp4" else "mp3"
            final_name = f"{title}.{ext}"

        with job_lock:
            current_job['status'] = 'finished'
            current_job['progress'] = 100
            current_job['title'] = title
            current_job['filename'] = final_name
            current_job['error'] = None

        print(f"[ERFOLG] Gespeichert: {final_name} in {DOWNLOAD_DIR}")

    except Exception as e:
        err_msg = str(e)
        print(f"[FEHLER] {err_msg}")
        with job_lock:
            current_job['status'] = 'error'
            current_job['progress'] = 0
            current_job['error'] = err_msg

class CompanionHandler(BaseHTTPRequestHandler):
    def _send_cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors()
        self.end_headers()

    def do_GET(self):
        if self.path == '/ping' or self.path == '/health':
            self.send_response(200)
            self._send_cors()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            resp = {
                "status": "ok",
                "download_dir": str(DOWNLOAD_DIR),
                "ffmpeg": bool(shutil.which("ffmpeg"))
            }
            self.wfile.write(json.dumps(resp).encode('utf-8'))
        elif self.path == '/status':
            self.send_response(200)
            self._send_cors()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            with job_lock:
                self.wfile.write(json.dumps(current_job).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/download':
            content_len = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_len)
            try:
                data = json.loads(body.decode('utf-8'))
                url = data.get('url', '').strip()
                fmt = data.get('format', 'mp3')
                quality = data.get('quality', '320')

                if not url:
                    self.send_response(400)
                    self._send_cors()
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": False, "message": "Keine URL angegeben"}).encode('utf-8'))
                    return

                # Download in separatem Thread starten
                t = threading.Thread(target=run_download_task, args=(url, fmt, quality), daemon=True)
                t.start()

                self.send_response(200)
                self._send_cors()
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "message": "Download gestartet"}).encode('utf-8'))

            except Exception as e:
                self.send_response(500)
                self._send_cors()
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(e)}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Ruhige Logs (nur wichtige Ausgaben)
        pass

def main():
    has_ffmpeg = ensure_ffmpeg_in_path()

    print("=" * 60)
    print("   ✨ Glass MP3 - Lokaler Companion Server ✨")
    print("=" * 60)
    print(f" -> Status:          Bereit und wartet auf Downloads")
    print(f" -> Lokaler Port:    {PORT}")
    print(f" -> Speicherort:     {DOWNLOAD_DIR}")
    
    if has_ffmpeg:
        print(f" -> FFmpeg:          [OK] Gefunden ({shutil.which('ffmpeg')})")
    else:
        print(" -> FFmpeg:          [ACHTUNG] ffmpeg nicht im PATH gefunden!")
        print("    Tipp: Öffne PowerShell und führe 'winget install Gyan.FFmpeg' aus.")
    
    print("-" * 60)
    print("Lasse dieses Fenster einfach im Hintergrund offen.")
    print("Sobald du in Chrome auf 'Als MP3 laden' klickst, startet der Download hier!")
    print("=" * 60)

    server = HTTPServer(('127.0.0.1', PORT), CompanionHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer wird beendet...")
        server.server_close()

if __name__ == '__main__':
    main()
