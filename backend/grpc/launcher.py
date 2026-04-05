"""
backend/grpc/launcher.py — Combined gRPC + MJPEG preview launcher
=================================================================

Starts the gRPC scanner server and the MJPEG HTTP preview server in a single
process using threads.

Registered as a Poetry script:
    poetry run neganuki-server

Full options:
    poetry run neganuki-server --help
"""

import argparse
import logging
import signal
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
log = logging.getLogger("Launcher")


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Neganuki scanner — gRPC server + MJPEG preview",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    grpc = p.add_argument_group("gRPC server")
    grpc.add_argument("--host", default="0.0.0.0", help="gRPC bind host")
    grpc.add_argument("--port", type=int, default=50051, help="gRPC bind port")
    grpc.add_argument("--output-dir", default="./output", help="Output directory for scans")
    grpc.add_argument("--motor-pins", default="17,18,27,22",
                      help="GPIO pins IN1-IN4 (comma-separated)")
    grpc.add_argument("--motor-delay", type=float, default=0.002,
                      help="Delay between motor steps (seconds)")

    http = p.add_argument_group("MJPEG preview")
    http.add_argument("--no-preview", action="store_true",
                      help="Disable the MJPEG HTTP preview server")
    http.add_argument("--http-port", type=int, default=8080,
                      help="HTTP port for the MJPEG preview stream")
    http.add_argument("--preview-fps", type=int, default=10,
                      help="Preview stream FPS")
    http.add_argument("--preview-quality", type=int, default=75,
                      help="Preview JPEG quality (1-100)")
    return p


def _start_grpc_server(controller, host: str, port: int) -> "GRPCServer":
    """Import, create and start the gRPC server. Returns the server instance."""
    from backend.grpc.server import GRPCServer  # local import to avoid circular issues

    # server.py uses [::] notation for IPv6 dual-stack; wrap plain IPs accordingly.
    bind = host if host.startswith("[") else f"{host}"
    srv = GRPCServer(controller, host=bind, port=port)
    srv.start()
    log.info("gRPC server listening on %s:%d", host, port)
    return srv


def _start_mjpeg_server(grpc_port: int, http_port: int, fps: int, quality: int) -> ThreadingHTTPServer:
    """Import the MJPEG machinery, start the background gRPC reader, and return the HTTPServer."""
    # Import shared state and classes from the standalone mjpeg_preview module.
    # We add the clients directory to sys.path temporarily.
    clients_dir = Path(__file__).resolve().parents[2] / "clients" / "neganuki-terminal"
    if str(clients_dir) not in sys.path:
        sys.path.insert(0, str(clients_dir))

    import mjpeg_preview as mp  # type: ignore[import]

    reader_thread = threading.Thread(
        target=mp._grpc_reader,
        # max_retries=0 → infinite retries when running embedded (launcher manages lifetime)
        args=("localhost", grpc_port, fps, quality, 0),
        daemon=True,
        name="mjpeg-grpc-reader",
    )
    reader_thread.start()

    server = ThreadingHTTPServer(("0.0.0.0", http_port), mp.MJPEGHandler)
    server.daemon_threads = True
    log.info("MJPEG preview server at http://0.0.0.0:%d/", http_port)
    return server


def main() -> None:
    args = _build_arg_parser().parse_args()

    # ── 1. Pipeline controller ────────────────────────────────────────────────
    try:
        from backend.pipeline.controller import PipelineController
    except ImportError as exc:
        log.error("Could not import PipelineController: %s", exc)
        log.error("Run: poetry run generate-protos")
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    motor_pins = tuple(map(int, args.motor_pins.split(",")))

    log.info("Initializing scanner components…")
    try:
        controller = PipelineController(
            output_dir=str(output_dir),
            camera_config={"resolution": (4056, 3040)},
            motor_pins={"pins": motor_pins, "delay": args.motor_delay},
            max_frames=100,
            detect_film_end=True,
        )
        log.info("✓ Pipeline controller ready")
    except Exception as exc:
        log.error("Failed to initialize pipeline: %s", exc)
        sys.exit(1)

    # ── 2. gRPC server ────────────────────────────────────────────────────────
    try:
        grpc_server = _start_grpc_server(controller, args.host, args.port)
    except Exception as exc:
        log.error("Failed to start gRPC server: %s", exc)
        sys.exit(1)

    # ── 3. MJPEG preview server ───────────────────────────────────────────────
    http_server: ThreadingHTTPServer | None = None
    if not args.no_preview:
        # Give gRPC server a moment to be ready before the reader connects.
        time.sleep(0.5)
        try:
            http_server = _start_mjpeg_server(
                grpc_port=args.port,
                http_port=args.http_port,
                fps=args.preview_fps,
                quality=args.preview_quality,
            )
            http_thread = threading.Thread(
                target=http_server.serve_forever,
                daemon=True,
                name="mjpeg-http",
            )
            http_thread.start()
            log.info("Open preview in browser: http://<pi-ip>:%d/", args.http_port)
        except Exception as exc:
            log.warning("MJPEG preview server failed to start: %s", exc)

    # ── 4. Run until Ctrl-C / SIGTERM ─────────────────────────────────────────
    stop_event = threading.Event()

    def _shutdown(signum, frame):
        log.info("Shutting down…")
        stop_event.set()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    log.info("Scanner ready. Press Ctrl-C to stop.")
    stop_event.wait()

    grpc_server.stop(grace=3)
    if http_server is not None:
        http_server.shutdown()
    log.info("Bye.")


if __name__ == "__main__":
    main()
