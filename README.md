# ZCST 水电费查询工具

模拟 MyZCST APP 客户端行为，完成统一认证登录后拉取应用列表并打开水电费页面。

## 原理

通过反编译 MyZCST APK 得到的接口信息：

1. **初始化**: `POST /mobile/initClientConfig21_1.mo` → 获取 IDS 服务器地址
2. **登录**: 弹出浏览器加载统一认证页面 `/_web/appWebLogin.jsp`，用户手动完成验证码登录
3. **获取用户**: `POST /_ids_mobile/loginedUser15` → 获取当前用户信息
4. **拉取应用**: 多个 API 并行查询（`queryIndexApps`, `getDefaultInstallApps`, `queryApp` 等）
5. **打开水电**: 调用 `POST /mobile/openApp20.mo` 获取签名，拼接 `iportal.*` 参数后访问目标 URL

## 环境要求

- Python 3.12+
- Chrome 或 Firefox 浏览器

## 安装与运行（Windows）

### 方式一：使用 uv（推荐）

[uv](https://docs.astral.sh/uv/) 会自动管理 Python 版本和虚拟环境：

```powershell
# 1. 安装 uv（若未安装）
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 2. 在项目目录安装依赖
cd ZCST_FEE
uv sync

# 3. 运行
uv run python main.py
```

或者直接双击 `run.bat` 文件。

### 方式二：使用 pip

```powershell
cd ZCST_FEE
pip install -r requirements.txt
python main.py
```

> **注意**：如果使用 VS Code，请确保在右下角选择 `.venv` 中的 Python 解释器（`.venv\Scripts\python.exe`），而不是系统 Python，否则会因找不到依赖包而报错。

## 使用步骤

## 使用步骤

程序会：
1. 自动获取服务端配置
2. **弹出浏览器窗口** → 显示统一认证页面（含验证码）
3. 用户在浏览器中输入账号、密码、验证码，完成登录
4. 程序自动捕获 Cookie，关闭浏览器
5. 拉取所有应用列表，搜索水电相关应用
6. 用户选择目标应用后，获取签名并打开页面
7. 页面内容保存到 `fee_page.html`

## Cookie 缓存

登录成功后 Cookie 会保存到 `cookies.json`，下次运行时自动尝试复用，避免重复登录。
如果 Cookie 过期，删除 `cookies.json` 重新登录即可。

## 文件说明

| 文件 | 用途 |
|------|------|
| `main.py` | 主程序 |
| `run.bat` | Windows 一键启动脚本 |
| `requirements.txt` | Python 依赖（pip 用） |
| `pyproject.toml` | 项目配置（uv 用） |
| `cookies.json` | (运行后生成) 登录 Cookie 缓存 |
| `fee_page.html` | (运行后生成) 水电费页面 HTML |
