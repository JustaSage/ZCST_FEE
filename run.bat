@echo off
chcp 65001 >nul
echo 正在启动 ZCST 水电费查询工具...
echo.

:: 尝试使用 uv（推荐方式，自动使用 .venv 虚拟环境）
where uv >nul 2>&1
if %errorlevel% == 0 (
    uv run python main.py
    goto end
)

:: uv 不可用，尝试激活 .venv 虚拟环境
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    python main.py
    call .venv\Scripts\deactivate.bat
    goto end
)

:: 两者都不可用，尝试直接运行 python
echo [警告] 未找到 uv 或 .venv，尝试直接运行...
echo        如果出现 ModuleNotFoundError，请先执行：
echo        pip install -r requirements.txt
echo.
python main.py

:end
pause
