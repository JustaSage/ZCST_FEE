"""
ZCST 移动门户 - 统一认证登录 & 水电费查询工具
================================================
通过模拟 MyZCST APP 客户端行为:
1. 初始化客户端配置 (获取 IDS 服务器地址)
2. 弹出浏览器窗口让用户在统一认证页面完成登录(含验证码)
3. 捕获 SSO Cookie
4. 拉取下发的应用列表, 搜索水电相关应用
5. 打开水电费页面
"""

import hashlib
import json
import os
import sys
import time
import uuid
from urllib.parse import urlencode, urlparse

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

# 这些 URL 在 initClientConfig 之后可能被服务器覆盖
DEFAULT_IDS_HOST = ""       # 将从 initClientConfig 获取
DEFAULT_LOGIN_URL = ""      # 将从 initClientConfig 获取
DEFAULT_MI_HOST = ""        # 将从 initClientConfig 获取


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


def login_via_browser(session, server_info):
    """
    Step 2: 通过浏览器完成统一认证登录 (含验证码)
    弹出浏览器窗口, 用户手动完成登录后自动捕获 Cookie

    对应 OauthLoginActivity 中的 WebView 登录流程
    """
    print("\n[2/5] 启动浏览器进行统一认证...")

    # 确定登录页面 URL
    # APP 中: JluzhWeb_URL = URL_MIDS_SERVER + "/_web/appWebLogin.jsp"
    # mi_host / mi_ssl 是 IDS 移动接口服务器 (mucp.zcst.edu.cn), 用于拼接 /_web/appWebLogin.jsp
    # appWebLogin.jsp 会重定向到真正的统一认证 SSO 页面 (sos.zcst.edu.cn)
    # redirect_url (loginUrlPrefix) 是速迪平台通用参数, 不是实际认证域名
    mi_host = server_info.get("mi_host", "")
    mi_ssl = server_info.get("mi_ssl", "")

    # 优先使用 mi_ssl, 其次 mi_host (这两个是 IDS 服务地址)
    ids_base = mi_ssl or mi_host

    if not ids_base:
        print("  [!] 未获取到 IDS 服务器地址, 尝试使用默认地址...")
        ids_base = BASE_URL

    # 构造登录 URL (模拟 OauthLoginActivity)
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
    print(f"  即将打开浏览器, 请在页面中完成登录 (含验证码)...")
    print()

    # ---- 使用 Selenium 打开浏览器 ----
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        from selenium.webdriver.chrome.service import Service as ChromeService
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait
    except ImportError:
        print("  [!] 未安装 selenium, 请运行:")
        print("      pip install selenium webdriver-manager")
        sys.exit(1)

    # 尝试自动下载 ChromeDriver
    driver = None
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        service = ChromeService(ChromeDriverManager().install())
        options = ChromeOptions()
        options.add_argument("--window-size=500,750")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-features=DnsOverHttps")
        options.add_argument("--disable-async-dns")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--allow-running-insecure-content")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        driver = webdriver.Chrome(service=service, options=options)
    except Exception:
        # 回退: 直接尝试系统 Chrome
        try:
            options = ChromeOptions()
            options.add_argument("--window-size=500,750")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-software-rasterizer")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-features=DnsOverHttps")
            options.add_argument("--disable-async-dns")
            options.add_argument("--ignore-certificate-errors")
            options.add_argument("--allow-running-insecure-content")
            driver = webdriver.Chrome(options=options)
        except Exception:
            # 再回退: 尝试 Firefox
            try:
                from selenium.webdriver.firefox.options import Options as FirefoxOptions
                fox_options = FirefoxOptions()
                fox_options.add_argument("--width=500")
                fox_options.add_argument("--height=750")
                driver = webdriver.Firefox(options=fox_options)
            except Exception as e:
                print(f"  [!] 无法启动浏览器: {e}")
                print("  请确保已安装 Chrome 或 Firefox 浏览器")
                sys.exit(1)

    print("  [✓] 浏览器已启动, 正在加载登录页面...")
    driver.get(full_login_url)

    # 注入 JS Bridge 拦截器, 模拟 APP 的 myLoginJsCall 接口
    # APP 中 WebView 登录成功后 H5 页面会调用 myLoginJsCall.closeWindow(result, cookies)
    try:
        time.sleep(2)
        driver.execute_script("""
            window.myLoginJsCall = {
                closeWindow: function(result, cookies) {
                    window._loginResult = {result: result, cookies: cookies};
                }
            };
        """)
    except Exception:
        pass

    print()
    print("  ╔═══════════════════════════════════════════╗")
    print("  ║  请在浏览器中完成统一认证登录 (含验证码)  ║")
    print("  ║  登录成功后程序将自动继续                  ║")
    print("  ╚═══════════════════════════════════════════╝")
    print()

    # 等待登录完成
    # 完整流程:
    #   1. 加载 mucp.zcst.edu.cn/_web/appWebLogin.jsp
    #   2. 重定向到 sos.zcst.edu.cn/login (SSO 登录页)
    #   3. 用户完成认证 (含验证码)
    #   4. 重定向回 mucp.zcst.edu.cn/_web/appWebLogin.jsp (带登录结果)
    #   5. appWebLogin.jsp 通过 JS Bridge 调用 closeWindow(result, cookies)
    # 关键: 检测从 SSO 页面跳回 appWebLogin.jsp 即为登录成功
    login_success = False
    max_wait = 300  # 最多等待 5 分钟
    start_time = time.time()

    # 等待页面初始加载
    time.sleep(3)

    # 追踪是否访问过 SSO 页面 (sos.zcst.edu.cn)
    visited_sso = False
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


def get_user_info(session, server_info):
    """
    Step 3: 获取登录用户信息
    对应 Get_Logined_User_URL = URL_MIDS_SERVER + "/_ids_mobile/loginedUser15"
    """
    print("\n[3/5] 获取用户信息...")

    mi_host = server_info.get("mi_host", "")
    ids_host = server_info.get("ids_host", "")
    host = mi_host or ids_host or BASE_URL

    url = f"{host}/_ids_mobile/loginedUser15"
    try:
        resp = session.post(url, timeout=10)
        result = resp.json()
    except Exception as e:
        print(f"  [!] 获取用户信息失败: {e}")
        # 尝试备用路径
        try:
            url2 = f"{BASE_URL}/_ids_mobile/loginedUser15"
            resp = session.post(url2, timeout=10)
            result = resp.json()
        except Exception:
            return None

    if str(result.get("result")) != "1":
        print(f"  [!] 获取用户信息失败: {result}")
        return None

    user = result.get("data", {})
    user_info = {
        "userId": user.get("userId", ""),
        "username": user.get("username", ""),
        "loginName": user.get("loginName", ""),
        "uxid": user.get("uxid", ""),
    }
    print(f"  [✓] 用户: {user_info['username']} (ID: {user_info['userId']})")
    return user_info


def fetch_app_list(session, user_info):
    """
    Step 4: 拉取下发的应用列表, 寻找水电相关应用
    尝试多个 API:
      - /mobile/queryIndexApps.mo (首页应用)
      - /mobile/getDefaultInstallApps19_4.mo (默认安装应用)
      - /mobile/queryApp.mo (搜索应用)
      - /mobile/getAppRankList.mo (应用排行)
    """
    print("\n[4/5] 拉取应用列表, 搜索水电相关应用...")

    water_apps = []
    all_apps = []

    # 水电关键词
    keywords = ["水电", "水费", "电费", "缴费", "能源", "充值",
                "宿舍", "smartwater", "energy"]

    # ---- API 1: 首页应用列表 ----
    print("  [→] 查询首页应用...")
    try:
        resp = session.post(f"{BASE_URL}/mobile/queryIndexApps.mo", data={
            "beginIndex": 0,
            "pageSize": 100,
        }, timeout=10)
        data = resp.json()
        if str(data.get("result")) == "1":
            ranks = data.get("data", {})
            if isinstance(ranks, dict):
                ranks = ranks.get("ranks", [])
            for app in ranks:
                all_apps.append(app)
    except Exception as e:
        print(f"      失败: {e}")

    # ---- API 2: 默认安装应用 ----
    print("  [→] 查询默认安装应用...")
    try:
        resp = session.post(f"{BASE_URL}/mobile/getDefaultInstallApps19_4.mo", data={
            "mobileId": DEVICE_KEY,
            "mobileType": "Pixel 6",
            "os": "12",
            "clientType": CLIENT_TYPE,
            "version": APP_VERSION,
        }, timeout=10)
        data = resp.json()
        if str(data.get("result")) == "1":
            apps = data.get("data", [])
            if isinstance(apps, dict):
                apps = apps.get("defaultAppList", [])
            for app in apps:
                all_apps.append(app)
    except Exception as e:
        print(f"      失败: {e}")

    # ---- API 3: 搜索水电相关应用 ----
    for kw in ["水电", "缴费", "能源", "充值"]:
        print(f"  [→] 搜索关键词: '{kw}'...")
        try:
            resp = session.post(f"{BASE_URL}/mobile/queryApp.mo", data={
                "keyword": kw,
                "beginIndex": 0,
                "pageSize": 50,
            }, timeout=10)
            data = resp.json()
            if str(data.get("result")) == "1":
                apps = data.get("data", {})
                if isinstance(apps, dict):
                    apps = apps.get("ranks", apps.get("list", []))
                if isinstance(apps, list):
                    for app in apps:
                        all_apps.append(app)
        except Exception:
            pass

    # ---- API 4: 全部应用列表 ----
    print("  [→] 查询全部应用列表...")
    try:
        resp = session.post(f"{BASE_URL}/mobile/getAppRankList.mo", data={
            "beginIndex": 0,
            "pageSize": 200,
        }, timeout=10)
        data = resp.json()
        if str(data.get("result")) == "1":
            apps = data.get("data", {})
            if isinstance(apps, dict):
                apps = apps.get("ranks", apps.get("list", []))
            if isinstance(apps, list):
                for app in apps:
                    all_apps.append(app)
    except Exception as e:
        print(f"      失败: {e}")

    # ---- API 5: 带组件的应用列表 ----
    print("  [→] 查询组件应用列表...")
    try:
        resp = session.post(
            f"{BASE_URL}/mobile/queryHasComponentsAppList.mo",
            timeout=10,
        )
        data = resp.json()
        if str(data.get("result")) == "1":
            apps = data.get("data", [])
            if isinstance(apps, list):
                for app in apps:
                    all_apps.append(app)
    except Exception:
        pass

    # 去重
    seen_ids = set()
    unique_apps = []
    for app in all_apps:
        app_id = str(app.get("id", app.get("appId", app.get("orginAppId", ""))))
        if app_id and app_id not in seen_ids:
            seen_ids.add(app_id)
            unique_apps.append(app)

    print(f"\n  [✓] 共发现 {len(unique_apps)} 个应用")
    print()

    # 筛选水电相关应用
    for app in unique_apps:
        app_name = app.get("name", app.get("appName", ""))
        app_desc = app.get("description", "")
        app_keywords_str = app.get("keywords", "")
        combined = f"{app_name}{app_desc}{app_keywords_str}".lower()

        is_match = any(kw in combined for kw in keywords)
        if is_match:
            water_apps.append(app)

    # 打印所有应用列表
    print("  ─── 全部应用列表 ───")
    for i, app in enumerate(unique_apps):
        app_name = app.get("name", app.get("appName", ""))
        app_id = app.get("id", app.get("appId", ""))
        app_type = app.get("type", "?")
        main_url = app.get("mainUrl", "")
        marker = " ◀◀ 水电相关" if app in water_apps else ""
        print(f"  [{i+1:3d}] {app_name} (id={app_id}, type={app_type}){marker}")
        if main_url:
            print(f"        URL: {main_url}")

    if water_apps:
        print(f"\n  [✓] 找到 {len(water_apps)} 个水电相关应用:")
        for app in water_apps:
            app_name = app.get("name", app.get("appName", ""))
            print(f"      → {app_name}")
    else:
        print("\n  [!] 未找到明确的水电相关应用")
        print("      水电功能可能使用了其他名称, 请从上方列表中辨认")

    return unique_apps, water_apps


def open_fee_page(session, server_info, user_info, app, unique_apps, driver=None):
    """
    Step 5: 打开水电费页面
    对应 OpenLightAppUtil.normalOpenApp → openAppOnNet → buildSignUrlParam
    """
    print("\n[5/5] 打开水电费页面...")

    app_id = app.get("id", app.get("appId", ""))
    app_name = app.get("name", app.get("appName", ""))
    app_type = int(app.get("type", 4))
    main_url = app.get("mainUrl", "")
    auth_type = int(app.get("authType", app.get("auth", {}).get("authType", 0))
                     if not isinstance(app.get("authType", 0), int)
                     else app.get("authType", 0))

    print(f"  应用: {app_name} (id={app_id}, type={app_type})")
    print(f"  入口 URL: {main_url}")
    print(f"  认证类型: {auth_type}")

    if not main_url:
        print("  [!] 该应用没有 mainUrl, 可能是原生应用")
        return None

    # Step 5a: 调用 openApp 接口获取签名 (对应 Open_App_Method_Url)
    sign_params = {}
    if user_info:
        print("  [→] 获取应用访问签名...")
        try:
            resp = session.post(f"{BASE_URL}/mobile/openApp20.mo", data={
                "id": app_id,
                "userId": user_info["userId"],
                "uxid": user_info.get("uxid", ""),
                "isSign": "1",
            }, timeout=10)
            sign_data = resp.json()
            if str(sign_data.get("result")) == "1":
                vc = sign_data.get("data", {})
                for key in ["iportal.timestamp", "iportal.nonce",
                            "iportal.signature", "iportal.signature2",
                            "iportal.ip", "iportal.signature3",
                            "iportal.device", "iportal.group"]:
                    if key in vc:
                        sign_params[key] = vc[key]
                print(f"  [✓] 签名获取成功 ({len(sign_params)} 个参数)")
        except Exception as e:
            print(f"  [!] 签名获取失败: {e}")

    # Step 5b: 构造完整 URL (模拟 buildSignUrlParam)
    url_params = dict(sign_params)
    if user_info and auth_type in (0, 1, 3):
        url_params["iportal.uid"] = str(user_info["userId"])
        url_params["iportal.uname"] = user_info.get("username", "")
        url_params["iportal.uxid"] = user_info.get("uxid", "")

    if auth_type == 3:
        url_params["iportal.proxyUid"] = app.get("proxyUserName", "")
        url_params["iportal.proxyCredit"] = app.get("proxyPassword", "")

    separator = "&" if "?" in main_url else "?"
    full_url = f"{main_url}{separator}{urlencode(url_params)}" if url_params else main_url

    # Step 5c: 用浏览器跟随 CAS 重定向获取最终直连链接
    # 原理: 浏览器持有登录后的 TGT Cookie (在 sos.zcst.edu.cn 上)
    #   导航到 full_url → CAS 签发 service ticket
    #   → 重定向到 hub.17wanxiao.com/...?ticket=ST-xxx
    #   该 URL 可直接在任意浏览器打开, 无需统一认证
    direct_url = None
    print("\n  [→] 用浏览器跟随统一认证跳转, 获取直连链接...")

    if driver:
        try:
            driver.get(full_url)
            # 跳转分两段:
            #   1. sos.zcst.edu.cn → hub.17wanxiao.com/...?ticket=ST-xxx  (CAS ticket, 一次性)
            #   2. hub.17wanxiao.com → xqh5.17wanxiao.com/...#/?params=... (加密参数, 可复用)
            # 必须等到第 2 段完成才获取 URL, 否则 ticket 被消费后就无法使用
            # 最多等 40 秒
            for _ in range(40):
                current = driver.current_url
                # 已到达最终落地页: 含 params= 或在 xqh5 子域
                if "params=" in current or "xqh5.17wanxiao.com" in current:
                    time.sleep(1)  # 等 JS 渲染完整 hash
                    direct_url = driver.current_url
                    break
                time.sleep(1)
            if not direct_url:
                # 降级: 至少返回停留的 URL
                current = driver.current_url
                print(f"  [!] 未到达最终落地页, 当前停在: {current}")
                if "17wanxiao.com" in current:
                    direct_url = current  # hub URL (ticket 已消费, 仅记录)
        except Exception as e:
            print(f"  [!] 浏览器跳转失败: {e}")
        finally:
            try:
                driver.quit()
            except Exception:
                pass
    else:
        # 无浏览器 (使用缓存 Cookie 路径), 尝试 requests 跟随
        try:
            resp = session.get(full_url, timeout=20, allow_redirects=True)
            final_url = resp.url
            if "17wanxiao.com" in final_url:
                direct_url = final_url
            elif final_url != full_url:
                direct_url = final_url
            output_dir = os.path.dirname(os.path.abspath(__file__))
            html_path = os.path.join(output_dir, "fee_page.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(resp.text)
            print(f"  HTTP {resp.status_code}, 最终 URL: {final_url}")
        except Exception as e:
            print(f"  [!] 请求跟随失败: {e}")

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
        print(f"  ⚠️  无法自动获取直连链接 (CAS 认证 Cookie 可能缺失)")
        print(f"  中转链接 (统一认证后可访问):")
        print(f"  {full_url}")
    print("  " + "─" * 52)

    return direct_url or full_url


# 优先匹配的应用名称
PREFERRED_APP_NAMES = ["智能水电", "智慧水电", "水电费", "能源管理"]


def select_app_interactively(unique_apps, water_apps):
    """选择要打开的应用, 优先自动匹配智能水电"""
    # 优先从所有应用中精确匹配「智能水电」等已知名称
    for preferred in PREFERRED_APP_NAMES:
        for app in unique_apps:
            name = app.get("name", app.get("appName", ""))
            if name == preferred:
                print(f"\n  [✓] 自动选择应用: {name}")
                return app

    # 其次从水电相关应用中匹配
    if water_apps:
        if len(water_apps) == 1:
            name = water_apps[0].get('name', water_apps[0].get('appName', ''))
            print(f"\n  [✓] 自动选择应用: {name}")
            return water_apps[0]

        print("\n  找到多个水电相关应用, 请选择:")
        for i, app in enumerate(water_apps):
            name = app.get("name", app.get("appName", ""))
            print(f"    [{i+1}] {name}")
        while True:
            try:
                choice = int(input("  请输入编号: ")) - 1
                if 0 <= choice < len(water_apps):
                    return water_apps[choice]
            except (ValueError, EOFError):
                pass
            print("  无效输入, 请重试")

    # 没有匹配到, 让用户从全部列表选择
    if not unique_apps:
        print("\n  [!] 没有获取到任何应用")
        return None

    print("\n  未自动匹配到水电应用, 请从列表中选择 (输入序号, 0 退出):")
    while True:
        try:
            choice = int(input("  请输入应用序号: "))
            if choice == 0:
                return None
            if 1 <= choice <= len(unique_apps):
                return unique_apps[choice - 1]
        except (ValueError, EOFError):
            pass
        print(f"  请输入 1-{len(unique_apps)} 之间的数字, 或 0 退出")


def save_cookies(session, filepath):
    """保存 Cookie 到文件, 下次可复用"""
    cookies_list = []
    for cookie in session.cookies:
        cookies_list.append({
            "name": cookie.name,
            "value": cookie.value,
            "domain": cookie.domain,
            "path": cookie.path,
        })
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(cookies_list, f, ensure_ascii=False, indent=2)


def load_cookies(session, filepath):
    """从文件加载 Cookie"""
    if not os.path.exists(filepath):
        return False
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            cookies_list = json.load(f)
        for c in cookies_list:
            session.cookies.set(c["name"], c["value"],
                                domain=c.get("domain", ""),
                                path=c.get("path", "/"))
        return True
    except Exception:
        return False


# ============================================================
# 主流程
# ============================================================
def main():
    print("=" * 56)
    print("   ZCST 移动门户 - 水电费查询工具")
    print("   (模拟 MyZCST APP 客户端)")
    print("=" * 56)
    print()

    session = create_session()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cookie_file = os.path.join(script_dir, "cookies.json")

    # Step 1: 初始化配置
    server_info = init_client_config(session)
    if not server_info:
        print("  [!] 无法获取服务端配置, 使用已知默认值继续...")
        server_info = {
            "host": "https://zx.zcst.edu.cn",
            "mi_host": "https://mucp.zcst.edu.cn",
            "mi_ssl": "https://mucp.zcst.edu.cn",
            "login_url": "",
            "redirect_url": "",
            "ids_host": "https://mucp.zcst.edu.cn",
            "ucp_host": "https://mucp.zcst.edu.cn",
            "login_type": "WebView",
            "app_url": BASE_URL,
        }

    # 检查是否有缓存的 Cookie
    user_info = None
    if os.path.exists(cookie_file):
        print("\n  发现缓存的登录 Cookie, 尝试复用...")
        if load_cookies(session, cookie_file):
            user_info = get_user_info(session, server_info)
            if user_info:
                print("  [✓] Cookie 有效, 跳过登录")

    # Step 2: 如果没有有效会话, 进行浏览器登录
    login_driver = None
    if not user_info:
        login_driver = login_via_browser(session, server_info)
        if not login_driver:
            print("\n[!] 登录失败, 程序退出")
            sys.exit(1)

        # Step 3: 获取用户信息
        user_info = get_user_info(session, server_info)

        # 保存 Cookie 供下次使用
        save_cookies(session, cookie_file)
        print(f"  [✓] Cookie 已保存到 {cookie_file}")

    # Step 4: 拉取应用列表
    unique_apps, water_apps = fetch_app_list(session, user_info)

    # 自动选择应用 (无需交互)
    target_app = select_app_interactively(unique_apps, water_apps)
    if not target_app:
        if login_driver:
            try:
                login_driver.quit()
            except Exception:
                pass
        print("\n未找到目标应用, 程序退出")
        sys.exit(0)

    # Step 5: 打开水电页面 (传入 driver 以通过浏览器跟随 CAS 重定向)
    full_url = open_fee_page(session, server_info, user_info,
                             target_app, unique_apps, driver=login_driver)

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
