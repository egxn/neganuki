import subprocess
from pathlib import Path
import re

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

    # Fix import in generated grpc file
    grpc_file = out_dir / "scanner_pb2_grpc.py"
    if grpc_file.exists():
        content = grpc_file.read_text()
        # Replace "import scanner_pb2" with "from . import scanner_pb2"
        content = re.sub(
            r'^import scanner_pb2 as',
            'from . import scanner_pb2 as',
            content,
            flags=re.MULTILINE
        )
        grpc_file.write_text(content)
        print("✔ Fixed import in scanner_pb2_grpc.py")

    print("✔ Protobufs generated at:", out_dir)
