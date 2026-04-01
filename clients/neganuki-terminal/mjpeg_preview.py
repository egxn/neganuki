"""
mjpeg_preview.py — MJPEG HTTP server for live camera preview
=============================================================

Pulls frames from the gRPC StreamPreview endpoint and serves them as an
MJPEG stream that any browser can display:

    http://<pi-ip>:8080/

Usage (on the Raspberry Pi):
    poetry run python clients/neganuki-terminal/mjpeg_preview.py
    poetry run python clients/neganuki-terminal/mjpeg_preview.py --grpc-host localhost --grpc-port 50051 --http-port 8080 --fps 10

Then open http://192.168.1.13:8080/ in your browser.
No extra dependencies — uses only stdlib http.server + threading.
"""

import argparse
import logging
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import grpc

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    from backend.grpc.generated import scanner_pb2, scanner_pb2_grpc
except ImportError:
    print("ERROR: Generated protobuf files not found. Run: poetry run generate-protos")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
log = logging.getLogger("MJPEGPreview")

# ── Shared frame buffer ───────────────────────────────────────────────────────

_lock = threading.Lock()
_latest_frame: bytes | None = None          # raw JPEG bytes
_frame_event = threading.Event()            # signals that a new frame arrived

BOUNDARY = b"--mjpegboundary"

# ── gRPC streaming thread ─────────────────────────────────────────────────────


def _grpc_reader(grpc_host: str, grpc_port: int, fps: int, quality: int) -> None:
    """Continuously pull frames from the gRPC server and store the latest one."""
    global _latest_frame
    address = f"{grpc_host}:{grpc_port}"

    while True:
        log.info("Connecting to gRPC server at %s …", address)
        try:
            channel = grpc.insecure_channel(address)
            stub = scanner_pb2_grpc.ScannerServiceStub(channel)
            request = scanner_pb2.PreviewRequest(fps=fps, quality=quality)
            for frame in stub.StreamPreview(request):
                if frame.image_data:
                    with _lock:
                        _latest_frame = bytes(frame.image_data)
                    _frame_event.set()
                    _frame_event.clear()
        except grpc.RpcError as exc:
            log.warning("gRPC stream lost (%s). Retrying in 2 s …", exc.details())
        except Exception as exc:
            log.warning("Unexpected error in gRPC reader: %s. Retrying in 2 s …", exc)
        finally:
            try:
                channel.close()
            except Exception:
                pass
        time.sleep(2)


# ── HTTP handler ──────────────────────────────────────────────────────────────

# Minimal HTML page — the <img> src points to the MJPEG stream endpoint.
_INDEX_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Neganuki live preview</title>
  <style>
    body { margin: 0; background: #111; display: flex; flex-direction: column;
           align-items: center; justify-content: center; min-height: 100vh; }
    h1   { color: #eee; font-family: sans-serif; margin-bottom: 1rem; }
    img  { max-width: 100%; border: 2px solid #444; border-radius: 4px; }
    p    { color: #888; font-family: sans-serif; font-size: 0.85rem; }
  </style>
</head>
<body>
  <h1>Neganuki — live preview</h1>
  <img src="/stream" alt="live preview">
  <p>Refresh the page if the stream does not start.</p>
</body>
</html>
"""


class MJPEGHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler — serves the HTML page and the MJPEG stream."""

    # Suppress per-request log noise from BaseHTTPRequestHandler.
    def log_message(self, fmt, *args):  # noqa: N802
        pass

    def do_GET(self):  # noqa: N802
        if self.path in ("/", "/index.html"):
            self._send_index()
        elif self.path == "/stream":
            self._send_mjpeg_stream()
        else:
            self.send_error(404, "Not found")

    def _send_index(self):
        body = _INDEX_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_mjpeg_stream(self):
        self.send_response(200)
        self.send_header(
            "Content-Type",
            f"multipart/x-mixed-replace; boundary={BOUNDARY.decode()}",
        )
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        log.info("Client %s connected to MJPEG stream", self.client_address[0])
        try:
            while True:
                # Wait up to 5 s for a new frame; send the latest one either way.
                _frame_event.wait(timeout=5)
                with _lock:
                    jpeg = _latest_frame

                if jpeg is None:
                    # No frame yet — send a 1×1 grey placeholder so the browser
                    # keeps the connection alive.
                    jpeg = _GREY_JPEG

                header = (
                    BOUNDARY
                    + b"\r\nContent-Type: image/jpeg\r\n"
                    + f"Content-Length: {len(jpeg)}\r\n\r\n".encode()
                )
                self.wfile.write(header + jpeg + b"\r\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            log.info("Client %s disconnected", self.client_address[0])
        except Exception as exc:
            log.warning("Stream error: %s", exc)


# 1×1 grey JPEG used as placeholder before the first real frame arrives.
_GREY_JPEG = bytes([
    0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
    0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
    0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
    0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
    0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
    0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
    0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
    0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
    0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
    0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
    0x09, 0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
    0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D,
    0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
    0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08,
    0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72,
    0x82, 0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x25, 0x26, 0x27, 0x28,
    0x29, 0x2A, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45,
    0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59,
    0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75,
    0x76, 0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
    0x8A, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3, 0xA4,
    0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6, 0xB7,
    0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9, 0xCA,
    0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE1, 0xE2, 0xE3,
    0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4, 0xF5,
    0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01, 0x00,
    0x00, 0x3F, 0x00, 0xFB, 0xD5, 0xFF, 0xD9,
])


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Neganuki MJPEG preview server")
    parser.add_argument("--grpc-host", default="localhost",
                        help="gRPC server host (default: localhost)")
    parser.add_argument("--grpc-port", type=int, default=50051,
                        help="gRPC server port (default: 50051)")
    parser.add_argument("--http-port", type=int, default=8080,
                        help="HTTP port to serve on (default: 8080)")
    parser.add_argument("--fps", type=int, default=10,
                        help="Requested preview FPS (default: 10)")
    parser.add_argument("--quality", type=int, default=75,
                        help="JPEG quality 1-100 (default: 75)")
    args = parser.parse_args()

    # Start gRPC reader in a background daemon thread.
    t = threading.Thread(
        target=_grpc_reader,
        args=(args.grpc_host, args.grpc_port, args.fps, args.quality),
        daemon=True,
        name="grpc-reader",
    )
    t.start()

    server = HTTPServer(("0.0.0.0", args.http_port), MJPEGHandler)
    log.info("MJPEG preview server running at http://0.0.0.0:%d/", args.http_port)
    log.info("Open in browser: http://<pi-ip>:%d/", args.http_port)
    log.info("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Stopped.")


if __name__ == "__main__":
    main()
