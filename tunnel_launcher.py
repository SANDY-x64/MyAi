"""
MyAI Cloudflare Live Tunnel Manager
Launches uvicorn and establishes a public HTTPS Cloudflare Tunnel.
Extracts the live URL and saves it to tunnel_url.txt.
"""

import subprocess
import re
import time
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CLOUDFLARED_PATH = Path(r"C:\Users\Sandeep\tools\cloudflared.exe")

def run_tunnel():
    print("[1] Starting unified FastAPI server...")
    server_cmd = [
        str(BASE_DIR / ".venv" / "Scripts" / "python.exe"),
        "-m", "uvicorn", "backend.main:app",
        "--host", "127.0.0.1", "--port", "8000"
    ]
    server_proc = subprocess.Popen(server_cmd, cwd=str(BASE_DIR))

    time.sleep(2)

    print("[2] Starting Cloudflare Tunnel...")
    cf_cmd = [
        str(CLOUDFLARED_PATH),
        "tunnel", "--url", "http://127.0.0.1:8000"
    ]
    cf_proc = subprocess.Popen(
        cf_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    tunnel_url = None
    url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")

    for line in cf_proc.stdout:
        print(line, end="")
        match = url_pattern.search(line)
        if match:
            tunnel_url = match.group(0)
            print(f"\n=======================================================")
            print(f"🎉 LIVE CLOUDFLARE PUBLIC URL: {tunnel_url}")
            print(f"=======================================================\n")
            with open(BASE_DIR / "tunnel_url.txt", "w", encoding="utf-8") as f:
                f.write(tunnel_url.strip())
            break

    # Keep running
    try:
        cf_proc.wait()
    except KeyboardInterrupt:
        cf_proc.terminate()
        server_proc.terminate()

if __name__ == "__main__":
    run_tunnel()
