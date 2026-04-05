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
import mimetypes
import os
import signal
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
_output_dir: Path = Path("./output")        # directory to list/serve for download

BOUNDARY = b"--mjpegboundary"

# ── Shared gRPC control stub (for unary control RPCs) ────────────────────────

_grpc_channel = None                        # persistent channel for control calls
_ctrl_stub: scanner_pb2_grpc.ScannerServiceStub | None = None
_ctrl_lock = threading.Lock()               # protects _ctrl_stub access

# ── gRPC streaming thread ─────────────────────────────────────────────────────


def _grpc_reader(grpc_host: str, grpc_port: int, fps: int, quality: int,
                 max_retries: int = 5) -> None:
    """Continuously pull frames from the gRPC server and store the latest one.

    Exits the process if the server cannot be reached after *max_retries*
    consecutive failed attempts (i.e. the main server was shut down).
    Successful frames reset the retry counter.
    """
    import os
    global _latest_frame
    address = f"{grpc_host}:{grpc_port}"
    consecutive_failures = 0

    while True:
        log.info("Connecting to gRPC server at %s … (attempt %d/%d)",
                 address, consecutive_failures + 1, max_retries)
        try:
            channel = grpc.insecure_channel(address)
            stub = scanner_pb2_grpc.ScannerServiceStub(channel)
            request = scanner_pb2.PreviewRequest(fps=fps, quality=quality)
            frames_received = 0
            for frame in stub.StreamPreview(request):
                if frame.image_data:
                    with _lock:
                        _latest_frame = bytes(frame.image_data)
                    _frame_event.set()
                    _frame_event.clear()
                    frames_received += 1
                    if frames_received == 1:
                        # Reset counter once we get at least one good frame.
                        consecutive_failures = 0
        except grpc.RpcError as exc:
            log.warning("gRPC stream lost (%s). Retrying in 2 s …", exc.details())
            consecutive_failures += 1
        except Exception as exc:
            log.warning("Unexpected error in gRPC reader: %s. Retrying in 2 s …", exc)
            consecutive_failures += 1
        finally:
            try:
                channel.close()
            except Exception:
                pass

        if consecutive_failures >= max_retries:
            log.error(
                "Could not reach gRPC server after %d attempts. "
                "Main server appears to be down — shutting down MJPEG preview.",
                max_retries,
            )
            os.kill(os.getpid(), signal.SIGTERM)
            return

        time.sleep(2)


# ── HTTP handler ──────────────────────────────────────────────────────────────

# HTML is served from index.html alongside this script.
_HTML_FILE = Path(__file__).parent / "index.html"

_PLACEHOLDER_HTML = b"""<!DOCTYPE html><html><body><p>index.html not found.</p></body></html>"""


def _load_index_html() -> bytes:
    """Read index.html from disk each request (supports live editing)."""
    try:
        return _HTML_FILE.read_bytes()
    except OSError:
        log.warning("index.html not found at %s", _HTML_FILE)
        return _PLACEHOLDER_HTML



class MJPEGHandler(BaseHTTPRequestHandler):
    """HTTP handler — serves the HTML page, MJPEG stream, and control API."""

    def log_message(self, fmt, *args):  # noqa: N802
        pass

    # ── Routing ───────────────────────────────────────────────────────────────

    def do_GET(self):  # noqa: N802
        if self.path in ("/", "/index.html"):
            self._send_index()
        elif self.path == "/stream":
            self._send_mjpeg_stream()
        elif self.path == "/files":
            self._send_file_list()
        elif self.path == "/api/status":
            self._api_get_status()
        elif self.path == "/api/presets":
            self._api_list_presets()
        elif self.path == "/api/camera":
            self._api_get_camera()
        elif self.path.startswith("/download/"):
            self._send_file(self.path[len("/download/"):])
        else:
            self.send_error(404, "Not found")

    def do_POST(self):  # noqa: N802
        if self.path == "/api/capture":
            self._api_capture()
        elif self.path == "/api/motor":
            self._api_motor()
        elif self.path == "/api/camera/controls":
            self._api_camera_controls()
        elif self.path == "/api/camera/preset":
            self._api_camera_preset()
        else:
            self.send_error(404, "Not found")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _read_json_body(self):
        import json
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        return json.loads(raw)

    def _send_json(self, data: str, status: int = 200):
        body = data.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json_ok(self, **kwargs):
        import json
        kwargs.setdefault("success", True)
        self._send_json(json.dumps(kwargs))

    def _json_err(self, message: str, status: int = 200):
        import json
        self._send_json(json.dumps({"success": False, "message": message}), status)

    def _stub(self):
        with _ctrl_lock:
            return _ctrl_stub

    # ── GET API ───────────────────────────────────────────────────────────────

    def _api_get_status(self):
        import json
        stub = self._stub()
        if stub is None:
            self._json_err("gRPC control stub not initialised")
            return
        try:
            resp = stub.GetStatus(scanner_pb2.StatusRequest(), timeout=3)
            self._send_json(json.dumps({
                "success": True,
                "state": resp.state,
                "frame_count": resp.frame_count,
                "message": resp.message,
            }))
        except grpc.RpcError as e:
            self._json_err(e.details())

    def _api_list_presets(self):
        import json
        stub = self._stub()
        if stub is None:
            self._json_err("gRPC control stub not initialised")
            return
        try:
            resp = stub.ListCameraPresets(scanner_pb2.Empty(), timeout=3)
            self._send_json(json.dumps({
                "success": True,
                "preset_names": list(resp.preset_names),
            }))
        except grpc.RpcError as e:
            self._json_err(e.details())

    def _api_get_camera(self):
        import json
        stub = self._stub()
        if stub is None:
            self._json_err("gRPC control stub not initialised")
            return
        try:
            resp = stub.GetCameraPreset(scanner_pb2.Empty(), timeout=3)
            self._send_json(json.dumps({
                "success": True,
                "preset_name": resp.preset_name,
                "controls": dict(resp.controls),
            }))
        except grpc.RpcError as e:
            self._json_err(e.details())

    # ── POST API ──────────────────────────────────────────────────────────────

    def _api_capture(self):
        stub = self._stub()
        if stub is None:
            self._json_err("gRPC control stub not initialised")
            return
        try:
            body = self._read_json_body()
            raw = bool(body.get("raw", False))
            resp = stub.CaptureFrame(scanner_pb2.FrameCaptureRequest(raw=raw), timeout=15)
            self._json_ok(path=resp.path, message=resp.message)
        except grpc.RpcError as e:
            self._json_err(e.details())

    def _api_motor(self):
        stub = self._stub()
        if stub is None:
            self._json_err("gRPC control stub not initialised")
            return
        try:
            body = self._read_json_body()
            steps = int(body.get("steps", 0))
            resp = stub.MoveMotor(scanner_pb2.MotorMoveRequest(steps=steps), timeout=30)
            self._json_ok(message=resp.message)
        except (ValueError, TypeError):
            self._json_err("'steps' must be an integer")
        except grpc.RpcError as e:
            self._json_err(e.details())

    def _api_camera_controls(self):
        stub = self._stub()
        if stub is None:
            self._json_err("gRPC control stub not initialised")
            return
        try:
            body = self._read_json_body()
            req = scanner_pb2.CameraControlsRequest(
                ae_enable=bool(body.get("ae_enable", True)),
                exposure_time=int(body.get("exposure_time", 10000)),
                awb_enable=bool(body.get("awb_enable", True)),
                r_gain=float(body.get("r_gain", 1.4)),
                b_gain=float(body.get("b_gain", 1.9)),
                brightness=float(body.get("brightness", 0.0)),
                contrast=float(body.get("contrast", 1.0)),
                sharpness=float(body.get("sharpness", 1.0)),
                saturation=float(body.get("saturation", 1.0)),
            )
            resp = stub.SetCameraControls(req, timeout=5)
            self._json_ok(message=resp.message)
        except (ValueError, TypeError) as e:
            self._json_err(str(e))
        except grpc.RpcError as e:
            self._json_err(e.details())

    def _api_camera_preset(self):
        stub = self._stub()
        if stub is None:
            self._json_err("gRPC control stub not initialised")
            return
        try:
            body = self._read_json_body()
            name = str(body.get("preset_name", "")).strip()
            if not name:
                self._json_err("'preset_name' is required")
                return
            resp = stub.SetCameraPreset(scanner_pb2.SetPresetRequest(preset_name=name), timeout=5)
            self._json_ok(message=resp.message)
        except grpc.RpcError as e:
            self._json_err(e.details())

    # ── Static file serving ───────────────────────────────────────────────────

    def _send_file_list(self):
        import json
        entries = []
        if _output_dir.is_dir():
            for f in sorted(_output_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
                if f.is_file():
                    size = f.stat().st_size
                    if size >= 1_048_576:
                        size_str = f"{size / 1_048_576:.1f} MB"
                    elif size >= 1024:
                        size_str = f"{size / 1024:.0f} KB"
                    else:
                        size_str = f"{size} B"
                    entries.append({"name": f.name, "size": size_str})
        self._send_json(json.dumps(entries))

    def _send_file(self, filename: str):
        from urllib.parse import unquote
        filename = unquote(filename)
        # Prevent path traversal.
        file_path = (_output_dir / filename).resolve()
        if not str(file_path).startswith(str(_output_dir.resolve())):
            self.send_error(403, "Forbidden")
            return
        if not file_path.is_file():
            self.send_error(404, "Not found")
            return
        mime, _ = mimetypes.guess_type(str(file_path))
        mime = mime or "application/octet-stream"
        size = file_path.stat().st_size
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(size))
        self.send_header("Content-Disposition", f'attachment; filename="{file_path.name}"')
        self.end_headers()
        with open(file_path, "rb") as fh:
            while chunk := fh.read(65536):
                self.wfile.write(chunk)

    def _send_index(self):
        body = _load_index_html()
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
    parser.add_argument("--output-dir", default="./output",
                        help="Directory to list and serve for download (default: ./output)")
    args = parser.parse_args()

    global _output_dir, _ctrl_stub, _grpc_channel
    _output_dir = Path(args.output_dir).expanduser().resolve()
    log.info("Serving files from %s", _output_dir)

    # Shared gRPC channel + stub used by the HTTP control endpoints.
    address = f"{args.grpc_host}:{args.grpc_port}"
    _grpc_channel = grpc.insecure_channel(address)
    with _ctrl_lock:
        _ctrl_stub = scanner_pb2_grpc.ScannerServiceStub(_grpc_channel)
    log.info("Control gRPC stub connected to %s", address)

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
