#!/usr/bin/env python3
"""iPhone camera ko Linux virtual webcam (v4l2loopback) me bridge karta hai."""
import http.server
import socket
import ssl
import struct
import subprocess
import sys
import threading
import zlib
from pathlib import Path

HERE = Path(__file__).parent
WWW = HERE / "www"
CERT = HERE / "cert.pem"
KEY = HERE / "key.pem"
DEVICE = "/dev/video10"
PORT = 8443
FPS = 15

MIME = {".html": "text/html", ".json": "application/manifest+json",
        ".js": "text/javascript", ".png": "image/png"}


def get_lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()


def make_png(w: int, h: int, rgb: tuple) -> bytes:
    """Flat-color PNG, bina Pillow ke (stdlib zlib se)."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    row = b"\x00" + bytes(rgb) * w
    idat = zlib.compress(row * h, 9)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def ensure_icon():
    icon = WWW / "icon.png"
    if not icon.exists():
        icon.write_bytes(make_png(180, 180, (30, 144, 255)))


def ensure_cert(ip: str):
    if CERT.exists() and KEY.exists():
        return
    subprocess.run([
        "openssl", "req", "-x509", "-newkey", "rsa:2048", "-days", "3650", "-nodes",
        "-keyout", str(KEY), "-out", str(CERT),
        "-subj", f"/CN={ip}", "-addext", f"subjectAltName=IP:{ip}",
    ], check=True, capture_output=True)


def start_ffmpeg() -> subprocess.Popen:
    if not Path(DEVICE).exists():
        sys.exit(f"{DEVICE} nahi mila. Pehle: sudo modprobe v4l2loopback video_nr=10 "
                  f'card_label="iPhone Cam" exclusive_caps=1')
    return subprocess.Popen(
        ["ffmpeg", "-loglevel", "error", "-f", "mjpeg", "-i", "-",
         "-vf", "format=yuyv422", "-r", str(FPS), "-f", "v4l2", DEVICE],
        stdin=subprocess.PIPE,
    )


class Handler(http.server.BaseHTTPRequestHandler):
    ffmpeg_proc: subprocess.Popen
    write_lock = threading.Lock()

    def log_message(self, fmt, *args):
        pass  # chatty default logging mute

    def do_GET(self):
        path = "/index.html" if self.path == "/" else self.path
        file = WWW / path.lstrip("/")
        if not file.is_file() or WWW not in file.resolve().parents:
            self.send_error(404)
            return
        data = file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(file.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path != "/frame":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        frame = self.rfile.read(length)
        with self.write_lock:
            try:
                self.ffmpeg_proc.stdin.write(frame)
                self.ffmpeg_proc.stdin.flush()
            except BrokenPipeError:
                self.send_response(500)
                self.end_headers()
                return
        self.send_response(204)
        self.end_headers()


def main():
    ip = get_lan_ip()
    ensure_icon()
    ensure_cert(ip)
    Handler.ffmpeg_proc = start_ffmpeg()

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(str(CERT), str(KEY))
    server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)

    print(f"iPhone par khol: https://{ip}:{PORT}/")
    print(f"Virtual cam device: {DEVICE} (Meet me 'iPhone Cam' select karo)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        Handler.ffmpeg_proc.stdin.close()
        Handler.ffmpeg_proc.terminate()


if __name__ == "__main__":
    main()
