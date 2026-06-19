#!/usr/bin/env python
"""自动生成 protobuf 代码"""
import subprocess
import sys
from pathlib import Path

def generate():
    proto_dir = Path("proto")
    output_dir = Path("src/s2cpy/generate")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("🔄 正在生成 gRPC Python 代码...")

    cmd = [
        sys.executable, "-m", "grpc_tools.protoc",
        f"-I{proto_dir}",
        f"--python_out={output_dir}",
        f"--pyi_out={output_dir}",
        f"--grpc_python_out={output_dir}",
    ] + [str(f) for f in proto_dir.glob("*.proto")]

    try:
        subprocess.check_call(cmd)
        print("✅ 生成成功！文件位于 src/my_grpc_app/_proto/")
    except subprocess.CalledProcessError as e:
        print("❌ 生成失败:", e)
        sys.exit(1)

if __name__ == "__main__":
    generate()