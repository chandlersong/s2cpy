#!/usr/bin/env python3
"""
跨平台编译 protobuf 文件到指定位置（不依赖操作系统）
"""
import sys
from pathlib import Path
from grpc_tools import protoc


def fix_imports(out_dir):
    """修复生成的 grpc 文件中的导入语句"""
    grpc_file = out_dir / "message_pb2_grpc.py"

    if not grpc_file.exists():
        return

    content = grpc_file.read_text()

    # 修复导入：from . import message_pb2 或 import message_pb2
    # 改为：from . import message_pb2
    original_import = "import message_pb2 as message__pb2"
    fixed_import = "from . import message_pb2 as message__pb2"

    if original_import in content:
        content = content.replace(original_import, fixed_import)
        grpc_file.write_text(content)
        print(f"✅ 已修复 {grpc_file.name} 中的导入语句")


def compile_proto():
    """编译所有 .proto 文件"""

    # 定义路径
    proto_dir = Path("src/proto")
    out_dir = Path("src/s2cpy/generated")

    # 创建输出目录
    out_dir.mkdir(parents=True, exist_ok=True)

    # 找到所有 .proto 文件
    proto_files = list(proto_dir.glob("*.proto"))

    if not proto_files:
        print("❌ 未找到 .proto 文件")
        sys.exit(1)

    print(f"📦 找到 {len(proto_files)} 个 proto 文件:")
    for proto_file in proto_files:
        print(f"   - {proto_file}")

    # 转换路径为字符串（跨平台兼容）
    proto_files_str = [str(f) for f in proto_files]
    proto_dir_str = str(proto_dir)
    out_dir_str = str(out_dir)

    print(f"\n🔨 开始编译...")
    print(f"   输入目录: {proto_dir_str}")
    print(f"   输出目录: {out_dir_str}")

    # 调用 protoc 编译
    result = protoc.main([
        'grpc_tools.protoc',
        f'-I{proto_dir_str}',
        f'--python_out={out_dir_str}',
        f'--grpc_python_out={out_dir_str}',
        *proto_files_str
    ])

    if result == 0:
        # 创建 __init__.py 以便导入
        init_file = out_dir / "__init__.py"
        init_file.touch()

        # 修复导入语句
        fix_imports(out_dir)

        print(f"\n✅ 编译成功！")
        print(f"   生成的文件:")
        for py_file in out_dir.glob("*.py"):
            print(f"   - {py_file}")
    else:
        print(f"\n❌ 编译失败，返回码: {result}")
        sys.exit(1)


if __name__ == '__main__':
    compile_proto()
