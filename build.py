"""
跨平台编译脚本
使用方式: python build.py
输出:
  Windows → dist/zcst-fee.exe
  Linux   → dist/zcst-fee
"""

import platform
import subprocess
import sys
from pathlib import Path

ENTRY = "main.py"
APP_NAME = "zcst-fee"
DIST_DIR = "dist"

# PyInstaller 通用参数
args = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",
    "--name", APP_NAME,
    "--distpath", DIST_DIR,
    "--workpath", "build",
    "--specpath", "build",
    "--noconfirm",
    "--clean",
    ENTRY,
]

if platform.system() == "Windows":
    # Windows: 控制台程序（需要控制台交互输入账号密码）
    args += ["--console"]
else:
    args += ["--console"]

print(f"[build] 平台: {platform.system()} {platform.machine()}")
print(f"[build] 命令: {' '.join(args)}")
print()

result = subprocess.run(args, check=False)
if result.returncode != 0:
    print(f"\n[build] ❌ 编译失败 (exit {result.returncode})")
    sys.exit(result.returncode)

output = Path(DIST_DIR) / (APP_NAME + (".exe" if platform.system() == "Windows" else ""))
print(f"\n[build] ✅ 编译成功: {output.resolve()}")
