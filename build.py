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
HIDDEN_IMPORTS = [
    # selenium — 运行时动态导入的子模块
    "selenium.webdriver.chrome.webdriver",
    "selenium.webdriver.chrome.service",
    "selenium.webdriver.chrome.options",
    "selenium.webdriver.chromium.webdriver",
    "selenium.webdriver.remote.webdriver",
    "selenium.webdriver.remote.command",
    "selenium.webdriver.common.by",
    "selenium.webdriver.common.keys",
    "selenium.webdriver.common.action_chains",
    "selenium.webdriver.support.ui",
    "selenium.webdriver.support.expected_conditions",
    "selenium.webdriver.support.wait",
    # webdriver_manager — 动态加载的平台驱动
    "webdriver_manager.chrome",
    "webdriver_manager.core.driver_cache",
    "webdriver_manager.core.download_manager",
    "webdriver_manager.core.file_manager",
    "webdriver_manager.core.logger",
    "webdriver_manager.core.manager",
    "webdriver_manager.core.os_manager",
    "webdriver_manager.drivers.chrome",
]

args = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",
    "--name", APP_NAME,
    "--distpath", DIST_DIR,
    "--workpath", "build",
    "--specpath", "build",
    "--noconfirm",
    "--clean",
]
for hi in HIDDEN_IMPORTS:
    args += ["--hidden-import", hi]
args += [ENTRY]

# 控制台程序（需要交互输入账号/密码）
args += ["--console"]

print(f"[build] Platform: {platform.system()} {platform.machine()}")
print(f"[build] Command: {' '.join(args)}")
print()

result = subprocess.run(args, check=False)
if result.returncode != 0:
    print(f"\n[build] FAILED (exit {result.returncode})")
    sys.exit(result.returncode)

output = Path(DIST_DIR) / (APP_NAME + (".exe" if platform.system() == "Windows" else ""))
print(f"\n[build] OK: {output.resolve()}")
