# ZCST 水电费查询工具

[![Build & Release](https://github.com/JustaSage/ZCST_FEE/actions/workflows/release.yml/badge.svg)](https://github.com/JustaSage/ZCST_FEE/actions/workflows/release.yml)

通过模拟 MyZCST APP 客户端，自动完成统一认证登录（账号密码），并获取智能水电费直链。

## 下载

前往 [Releases](https://github.com/yourusername/ZCST_FEE/releases) 页面下载对应平台的可执行文件（无需安装 Python）：

| 平台    | 文件          |
|---------|---------------|
| Windows | `zcst-fee.exe` |
| Linux   | `zcst-fee`     |

> 运行时需要本机已安装 **Chrome 浏览器**（webdriver-manager 会自动下载匹配的 ChromeDriver）。

## 使用方式

```
./zcst-fee          # Linux
zcst-fee.exe        # Windows（双击或在终端运行）
```

程序启动后：

1. 提示输入**学号/工号**和**密码**（密码不回显）
2. 自动弹出 Chrome 窗口，模拟 APP WebView 访问统一认证页面
3. 自动填充账号密码并提交（账号密码登录无需验证码）
4. 检测到认证成功后提取 TGT Cookie
5. 跟随 CAS 跳转获取智能水电直连链接并打印到终端

## 原理

通过分析 我的珠科 APK 得到的接口：

1. `POST /mobile/initClientConfig21_1.mo` — 获取 IDS 服务器地址
2. Selenium 驱动 Chrome 访问 `/_web/appWebLogin.jsp` → 统一认证 SSO → 自动填充登录
3. 捕获 TGT Cookie 后导航到智能水电入口（`sos.zcst.edu.cn/login?service=…`）
4. 跟随 CAS Ticket 重定向最终到达 `xqh5.17wanxiao.com/…#/?params=…`

目标应用：**智能水电**（id=1520）

## 从源码运行

需要 Python 3.12+ 和 [uv](https://docs.astral.sh/uv/)。

```bash
# 安装 uv（Windows）
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 安装 uv（Linux/macOS）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装依赖并运行
uv sync
uv run python main.py
```

## 本地编译

```bash
uv sync --group build
uv run python build.py
# 输出: dist/zcst-fee.exe（Windows）或 dist/zcst-fee（Linux）
```

## 发布新版本

推送 `v` 开头的 tag 即可自动触发 GitHub Actions 编译并创建 Release：

```bash
git tag v1.0.0
git push origin v1.0.0
```

7. 页面内容保存到 `fee_page.html`

## 文件说明

| 文件 | 用途 |
|------|------|
| `main.py` | 主程序 |
| `run.bat` | Windows 一键启动脚本 |
| `requirements.txt` | Python 依赖（pip 用） |
| `pyproject.toml` | 项目配置（uv 用） |
| `cookies.json` | (运行后生成) 登录 Cookie 缓存 |
| `fee_page.html` | (运行后生成) 水电费页面 HTML |
