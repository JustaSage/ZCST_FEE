"""
ZCST 水电费直连链接获取（纯 API，无浏览器）
============================================
可嵌入到其他程序中调用：
    from api_login import get_fee_url
    url = get_fee_url("学号", "密码")

返回 xqh5.17wanxiao.com 最终落地页 URL；失败时抛出异常。
"""

import re
from urllib.parse import urljoin

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CAS_REST_URL = "https://sos.zcst.edu.cn/v1/tickets"
SERVICE_URL = (
    "https://hub.17wanxiao.com/bsacs/light.action"
    "?flag=cassso_zhkjxysdZ&ecardFunc=index"
)


def _session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 12; Pixel 6) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/100.0.0.0 Mobile Safari/537.36 iPortal/30"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    })
    s.verify = False
    return s


def _get_tgt(session, username, password):
    r = session.post(
        CAS_REST_URL,
        data={"username": username, "password": password},
        timeout=30,
        allow_redirects=False,
    )
    if r.status_code != 201:
        raise RuntimeError(f"CAS TGT 获取失败: HTTP {r.status_code} {r.text[:200]}")
    tgt = r.headers.get("Location", "").replace("http://", "https://")
    if not tgt:
        raise RuntimeError("CAS 未返回 TGT URL")
    return tgt


def _get_st(session, tgt_url, service_url):
    r = session.post(tgt_url, data={"service": service_url}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Service Ticket 获取失败: HTTP {r.status_code} {r.text[:200]}")
    st = r.text.strip()
    if not st.startswith("ST-"):
        raise RuntimeError(f"Service Ticket 格式异常: {st}")
    return st


def _get_hub_data(session, service_url, st):
    r = session.get(f"{service_url}&ticket={st}", timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"hub 页面访问失败: HTTP {r.status_code}")
    m = re.search(r"data[:\s]*['\"]([^'\"]+)['\"]", r.text)
    if not m:
        raise RuntimeError("未在 hub 页面中提取到 data 参数")
    return r.url, m.group(1)


def _get_auth_url(session, hub_url, data_encoded):
    session.headers.update({
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "https://hub.17wanxiao.com",
        "Referer": hub_url,
    })
    r = session.post(urljoin(hub_url, "/bsacs/redirect.action"), data=data_encoded, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"redirect.action 请求失败: HTTP {r.status_code} {r.text[:200]}")
    result = r.json()
    if result.get("error") or not result.get("result_"):
        raise RuntimeError(f"redirect.action 业务失败: {result}")
    auth_url = result.get("url")
    if not auth_url:
        raise RuntimeError("redirect.action 未返回 url")
    return auth_url


def _get_final_url(session, auth_url):
    r = session.get(auth_url, timeout=60)
    final_url = r.url
    if "xqh5.17wanxiao.com" in final_url and "params=" in final_url:
        return final_url
    raise RuntimeError(f"未到达最终落地页: {final_url}")


def get_fee_url(username, password):
    """
    输入统一认证账号密码，返回水电费直连链接。
    失败时抛出 RuntimeError。
    """
    session = _session()
    tgt_url = _get_tgt(session, username, password)
    st = _get_st(session, tgt_url, SERVICE_URL)
    hub_url, data = _get_hub_data(session, SERVICE_URL, st)
    auth_url = _get_auth_url(session, hub_url, data)
    return _get_final_url(session, auth_url)


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="ZCST 水电费直连链接获取")
    parser.add_argument("-u", "--username", required=True, help="统一认证账号")
    parser.add_argument("-p", "--password", required=True, help="统一认证密码")
    args = parser.parse_args()

    try:
        print(get_fee_url(args.username, args.password))
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
