import subprocess
from pathlib import Path

def run():
    proto_path = Path("backend/grpc/scanner.proto").resolve()
    out_dir = Path("backend/grpc/generated").resolve()

    out_dir.mkdir(exist_ok=True)

    cmd = [
        "python", "-m", "grpc_tools.protoc",
        "-I", str(proto_path.parent),
        "--python_out", str(out_dir),
        "--grpc_python_out", str(out_dir),
        str(proto_path)
    ]

    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)

    print("✔ Protobufs generated at:", out_dir)
