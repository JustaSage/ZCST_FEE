"""
ZCST 移动门户 - 统一认证登录 & 水电费查询工具
================================================
通过模拟 MyZCST APP 客户端行为:
1. 初始化客户端配置 (获取 IDS 服务器地址)
2. 弹出浏览器窗口让用户完成统一认证登录 (含验证码)
3. 捕获 TGT Cookie 后跟随 CAS 跳转获取智能水电直连链接
"""

import getpass
import hashlib
import os
import sys
import time
import uuid
from urllib.parse import urlencode, urlparse

# Windows 终端 UTF-8 输出保障（避免非 UTF-8 代码页下中文/Unicode 符号乱码）
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import requests

# ============================================================
# 配置常量 (从反编译 APK 中提取)
# ============================================================
BASE_URL = "https://my.zcst.edu.cn"
SSO_DOMAIN = "sos.zcst.edu.cn"       # 统一认证 SSO Cookie 域名 (硬编码于 OauthLoginActivity)
SSO_LOGIN_URL = "https://sos.zcst.edu.cn/login"  # SSO 登录地址
APP_VERSION = "1.3.7"
CLIENT_TYPE = "android"
DEVICE_KEY = hashlib.md5(uuid.uuid4().hex.encode()).hexdigest()

# 目标应用: 智能水电 (id=1520)
TARGET_APP_URL = (
    "https://sos.zcst.edu.cn/login"
    "?service=https%3A%2F%2Fhub.17wanxiao.com%2Fbsacs%2Flight.action"
    "%3Fflag%3Dcassso_zhkjxysdZ%26ecardFunc%3Dindex"
)



def create_session():
    """创建 HTTP 会话, 模拟 APP 的 SeuHttpClient"""
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Linux; Android 12; Pixel 6) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/100.0.0.0 Mobile Safari/537.36 iPortal/30",
    })
    s.verify = False
    # 抑制 InsecureRequestWarning
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    return s


def init_client_config(session):
    """
    Step 1: 初始化客户端配置
    对应 InitUtil.initClientConfig() → POST /mobile/initClientConfig21_1.mo
    返回服务端地址、UI 配置等
    """
    print("[1/5] 初始化客户端配置...")
    url = f"{BASE_URL}/mobile/initClientConfig21_1.mo"
    data = {
        "deviceKey": DEVICE_KEY,
        "version": APP_VERSION,
        "clientType": CLIENT_TYPE,
        "isFirst": 1,
        "os": "12",
        "mobileType": "Pixel 6",
    }
    for attempt in range(2):
        try:
            resp = session.post(url, data=data, timeout=30)
            resp.raise_for_status()
            result = resp.json()
            break
        except Exception as e:
            if attempt == 0:
                print(f"  [!] 第1次请求失败, 重试中...")
                time.sleep(2)
            else:
                print(f"  [!] 初始化请求失败: {e}")
                return None

    if str(result.get("result")) != "1":
        print(f"  [!] 初始化失败: {result.get('failReason', '未知错误')}")
        return None

    config_data = result.get("data", {})
    config = config_data.get("config", config_data)

    # 提取关键服务器地址 (对应 SeuMobileUtil.analyzeClientConfig)
    server_info = {
        "host": config.get("host", ""),
        "mi_host": config.get("mi_host", config.get("MI_Host", "")),
        "mi_ssl": config.get("mi_sll", config.get("mi_ssl", "")),
        "login_url": config.get("loginUrl", ""),
        "redirect_url": config.get("redirectUrl", ""),
        "ids_host": config.get("ids_host", config.get("ucpsrv_host", "")),
        "ucp_host": config.get("ucp_host", ""),
        "login_type": config.get("loginType", ""),
        "app_url": config.get("appUrl", BASE_URL),
    }

    print(f"  [✓] 配置获取成功")
    for k, v in server_info.items():
        if v:
            print(f"      {k}: {v}")

    return server_info


def login_via_browser(session, server_info, username, password):
    """
    Step 2: 通过浏览器自动填充账号密码完成统一认证登录
    账号密码登录无需验证码。
    """
    print("\n[2/3] 启动浏览器进行统一认证 (自动填充账号密码)...")

    mi_host = server_info.get("mi_host", "")
    mi_ssl = server_info.get("mi_ssl", "")
    ids_base = mi_ssl or mi_host or BASE_URL

    # 构造登录 URL
    cas_login_url = f"{ids_base}/_web/appWebLogin.jsp"
    params = {
        "serialNo": DEVICE_KEY,
        "os": CLIENT_TYPE,
        "deviceName": "Pixel 6",
        "name": "Pixel 6",
        "apnsKey": "",
        "miApnsKey": "",
        "_p": "YXM9MTAwMDAwMCZwPTEmbT1OJg__",
    }
    full_login_url = f"{cas_login_url}?{urlencode(params)}"
    print(f"  登录页面: {cas_login_url}")

    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager

    options = ChromeOptions()
    options.add_argument("--window-size=500,750")   # 竖屏, 与 APP WebView 保持一致
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Linux; Android 12; Pixel 6) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/100.0.0.0 Mobile Safari/537.36 iPortal/30"
    )
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--allow-running-insecure-content")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])

    try:
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        print(f"  [!] 无法启动浏览器: {e}")
        sys.exit(1)

    print("  [✓] 浏览器已启动, 正在加载登录页面...")
    driver.get(full_login_url)

    # 等待 Angular 渲染完成 (出现任意 input 即论为完成)
    wait = WebDriverWait(driver, 20)
    auto_fill_ok = False
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input")))
        time.sleep(0.8)  # 等待动画/渲染稳定

        # 切换到「用户名密码」 Tab，如果当前不是该 Tab
        try:
            tab_selectors = [
                "[class*='tab-item']", "[class*='login-tab']",
                "[class*='way-item']", "[class*='login-way']",
                "[class*='method']", "li[class*='tab']",
            ]
            for sel in tab_selectors:
                tabs = driver.find_elements(By.CSS_SELECTOR, sel)
                for tab in tabs:
                    txt = tab.text
                    if "用户名" in txt or "密码" in txt or "账号" in txt:
                        tab.click()
                        time.sleep(0.5)
                        break
        except Exception:
            pass  # 默认已是账号密码 Tab

        # 查找用户名输入框
        username_input = None
        for sel in [
            "input[placeholder*='账号']",
            "input[placeholder*='用户名']",
            "input[placeholder*='学号']",
            "input[placeholder*='工号']",
            "input[name='username']",
            "input#username",
            "input[autocomplete='username']",
            "input[type='text']:not([readonly]):not([disabled])",
        ]:
            try:
                el = driver.find_element(By.CSS_SELECTOR, sel)
                if el.is_displayed():
                    username_input = el
                    break
            except Exception:
                continue

        if username_input is None:
            raise RuntimeError("未找到用户名输入框")

        # 查找密码输入框
        password_input = None
        for sel in [
            "input[type='password']",
            "input[placeholder*='密码']",
        ]:
            try:
                el = driver.find_element(By.CSS_SELECTOR, sel)
                if el.is_displayed():
                    password_input = el
                    break
            except Exception:
                continue

        if password_input is None:
            raise RuntimeError("未找到密码输入框")

        # 填入凭据
        username_input.clear()
        username_input.send_keys(username)
        time.sleep(0.3)
        password_input.clear()
        password_input.send_keys(password)
        time.sleep(0.3)
        print("  [✓] 账号密码已填充")

        # 查找登录按鈕
        submit_btn = None
        for sel in [
            "button[type='submit']",
            "input[type='submit']",
            "button[class*='login']",
            "button[class*='submit']",
            "button[class*='btn-primary']",
            ".login-btn",
            ".submit-btn",
        ]:
            try:
                el = driver.find_element(By.CSS_SELECTOR, sel)
                if el.is_displayed():
                    submit_btn = el
                    break
            except Exception:
                continue

        if submit_btn is None:
            # XPath 备用: 找包含「登录」文字的按鈕
            for btn in driver.find_elements(By.XPATH, "//button[contains(text(),'登录')]"):
                if btn.is_displayed():
                    submit_btn = btn
                    break

        if submit_btn is None:
            raise RuntimeError("未找到登录按鈕")

        submit_btn.click()
        print("  [✓] 已提交登录表单, 等待认证结果...")
        auto_fill_ok = True

    except Exception as e:
        print(f"  [!] 自动填充失败: {e}")
        print("  请在浏览器中手动完成登录 (选择【用户名密码】登录方式)...")

    # 登录成功检测循环
    # 流程: appWebLogin.jsp 重定向到 sos.zcst.edu.cn/login → 用户认证 → 跳回 mucp域
    # 关键: 检测从 SSO 页跳回即为登录成功
    login_success = False
    # 自动填充成功后最多等 60 秒; 手动模式等 300 秒
    max_wait = 60 if auto_fill_ok else 300
    start_time = time.time()

    # 等待页面初始加载 (自动填充后页面已在加载中, 穉少等待)
    time.sleep(1)

    # 追踪是否访问过 SSO 页面 (sos.zcst.edu.cn)
    # 自动填充阶段已经在 SSO 页面上操作, 无需再等待进入 SSO 域
    visited_sso = auto_fill_ok
    sso_hosts = {SSO_DOMAIN, "sos.zcst.edu.cn"}

    while time.time() - start_time < max_wait:
        try:
            _ = driver.title
        except Exception:
            print("  [!] 浏览器已关闭")
            break

        current_url = driver.current_url
        current_host = urlparse(current_url).netloc
        current_path = urlparse(current_url).path

        # 记录是否到达过 SSO 页面
        if current_host in sso_hosts:
            visited_sso = True

        # 判断登录成功:
        # 核心条件: 曾经到 SSO 页面, 现在又回到了 appWebLogin.jsp
        #   (说明 SSO 认证完成, 页面跳回来了)
        if visited_sso and current_host not in sso_hosts:
            # 回到了 mucp 域名, 等一小会让页面执行 JS
            time.sleep(2)
            login_success = True
            break

        # 备用条件: 出现 CASTGC 等 SSO 认证成功 cookie
        try:
            page_cookies = driver.get_cookies()
            cookie_names = {c["name"] for c in page_cookies}
            sso_indicators = {"CASTGC", "TGC", "MOD_AUTH_CAS",
                              "iPlanetDirectoryPro", "SAAS_U"}
            if cookie_names & sso_indicators:
                login_success = True
                break
        except Exception:
            pass

        # 备用条件: JS Bridge 回调被触发
        try:
            result = driver.execute_script(
                "return window._loginResult || null;")
            if result:
                login_success = True
                break
        except Exception:
            pass

        # 持续注入 JS Bridge (页面跳转后会丢失)
        try:
            driver.execute_script("""
                if (!window.myLoginJsCall) {
                    window.myLoginJsCall = {
                        closeWindow: function(result, cookies) {
                            window._loginResult = {result: result, cookies: cookies};
                        }
                    };
                }
            """)
        except Exception:
            pass

        time.sleep(1)
    if not login_success:
        print("  [!] 登录超时或被取消")
        try:
            driver.quit()
        except Exception:
            pass
        return None

    # 提取所有 Cookie 到 requests session
    print("  [✓] 检测到登录成功, 正在提取 Cookie...")
    selenium_cookies = driver.get_cookies()

    # 访问 SSO 域名 (sos.zcst.edu.cn) 获取统一认证 Cookie
    # OauthLoginActivity 硬编码从 https://sos.zcst.edu.cn/login 提取 Cookie
    try:
        driver.get(SSO_LOGIN_URL)
        time.sleep(2)
        selenium_cookies.extend(driver.get_cookies())
    except Exception:
        pass

    # 访问门户地址获取更多 Cookie
    try:
        driver.get(BASE_URL)
        time.sleep(2)
        selenium_cookies.extend(driver.get_cookies())
    except Exception:
        pass

    # 访问 IDS 服务器获取相关 Cookie
    if mi_host:
        try:
            driver.get(mi_host)
            time.sleep(1)
            selenium_cookies.extend(driver.get_cookies())
        except Exception:
            pass

    # 去重并转移 Cookie 到 requests session
    # 注意: 浏览器保持开启, 供后续 open_fee_page 跟随 CAS 重定向
    seen = set()
    for cookie in selenium_cookies:
        key = (cookie["name"], cookie.get("domain", ""))
        if key in seen:
            continue
        seen.add(key)
        session.cookies.set(
            cookie["name"],
            cookie["value"],
            domain=cookie.get("domain", ""),
            path=cookie.get("path", "/"),
        )

    print(f"  [✓] 已获取 {len(seen)} 个 Cookie")
    return driver  # 返回 driver (浏览器保持开启)



def open_fee_page(session, driver):
    """
    Step 3: 用浏览器跟随 CAS 跳转, 获取智能水电直连链接
    原理: 浏览器持有登录后的 TGT Cookie, 导航到 TARGET_APP_URL
      → CAS 自动签发 service ticket
      → 重定向到 hub.17wanxiao.com → xqh5.17wanxiao.com/...#/?params=...
      该最终 URL 可直接在任意浏览器打开
    """
    print("\n[3/3] 跳转到智能水电页面...")
    print(f"  入口: {TARGET_APP_URL[:60]}...")

    direct_url = None
    try:
        driver.get(TARGET_APP_URL)
        # 跳转分两段:
        #   1. sos.zcst.edu.cn → hub.17wanxiao.com/...?ticket=ST-xxx  (CAS ticket, 一次性)
        #   2. hub.17wanxiao.com → xqh5.17wanxiao.com/...#/?params=... (加密参数, 可复用)
        # 必须等到第 2 段完成才获取 URL, 最多等 40 秒
        for _ in range(40):
            current = driver.current_url
            if "params=" in current or "xqh5.17wanxiao.com" in current:
                time.sleep(1)  # 等 JS 渲染完整 hash
                direct_url = driver.current_url
                break
            time.sleep(1)
        if not direct_url:
            current = driver.current_url
            print(f"  [!] 未到达最终落地页, 当前停在: {current}")
            if "17wanxiao.com" in current:
                direct_url = current
    except Exception as e:
        print(f"  [!] 浏览器跳转失败: {e}")
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    # 输出结果
    print()
    print("  " + "─" * 52)
    if direct_url and ("xqh5.17wanxiao.com" in direct_url or "params=" in direct_url):
        print(f"  ✅ 直连链接 (可直接在浏览器打开):")
        print(f"  {direct_url}")
    elif direct_url and "17wanxiao.com" in direct_url:
        print(f"  ✅ 最终链接:")
        print(f"  {direct_url}")
    else:
        print(f"  ⚠️  未到达最终落地页 (CAS 认证 Cookie 可能已过期, 请重新运行登录)")
        print(f"  中转链接:")
        print(f"  {TARGET_APP_URL}")
    print("  " + "─" * 52)

    return direct_url or TARGET_APP_URL


# ============================================================
# 主流程
# ============================================================
def main():
    print("=" * 56)
    print("   ZCST 移动门户 - 水电费查询工具")
    print("   (模拟 MyZCST APP 客户端)")
    print("=" * 56)
    print()
    # 提前收集登录凭据 (登录前就输入, 无需在浏览器页面操作)
    print("请输入统一认证登录信息 (账号密码无需验证码):")
    username = input("  账号 (学号/工号): ").strip()
    password = getpass.getpass("  密码: ")
    if not username or not password:
        print("[!] 账号或密码不能为空")
        sys.exit(1)
    print()
    session = create_session()

    # Step 1: 初始化配置
    server_info = init_client_config(session)
    if not server_info:
        print("  [!] 无法获取服务端配置, 程序退出")
        sys.exit(1)

    # Step 2: 浏览器登录
    login_driver = login_via_browser(session, server_info, username, password)
    if not login_driver:
        print("\n[!] 登录失败, 程序退出")
        sys.exit(1)

    # Step 3: 跳转到智能水电页面
    full_url = open_fee_page(session, login_driver)

    print("\n" + "=" * 56)
    print("  完成!")
    if full_url:
        is_direct = full_url and "17wanxiao.com" in full_url
        if is_direct:
            print(f"\n  直连链接 (无需统一认证, 可直接在浏览器打开):")
        else:
            print(f"\n  链接 (若打不开请先确保已登录 {BASE_URL}):")
        print(f"  {full_url}")
    print("=" * 56)


if __name__ == "__main__":
    main()
