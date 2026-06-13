# ZCST 水电费直连链接获取（API 版）

珠海科技学院智能水电费直连链接获取，纯 API 实现，无需浏览器。

## 原理

1. 调用学校 CAS REST API `sos.zcst.edu.cn/v1/tickets` 获取 TGT
2. 用 TGT 换取针对 17wanxiao 智能水电的 Service Ticket
3. 访问 `hub.17wanxiao.com/bsacs/light.action?ticket=ST` 获取跳转参数
4. POST `redirect.action` 换取 OAuth 授权链接
5. 跟随重定向到达 `xqh5.17wanxiao.com/#/?params=...` 最终落地页

## 使用

### 命令行

```bash
python api_login.py -u <学号> -p "<密码>"
```

### 作为库

```python
from api_login import get_fee_url

url = get_fee_url("<学号>", "<密码>")
print(url)
```

失败时抛出 `RuntimeError`。

## 依赖

```bash
pip install requests
```

或使用 uv：

```bash
uv sync
```

## 文件

- `api_login.py`：核心代码，可命令行运行也可导入使用
