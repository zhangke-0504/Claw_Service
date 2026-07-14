# claw_service
与openclaw通信的微服务

## openclaw网关拉起命令
 openclaw gateway --verbose --ws-log compact

## 环境配置

### 创建环境
uv venv --python 3.13
uv init
uv sync

### 环境更新和新环境拉取更新
本地环境更新示例
uv add 'volcengine-python-sdk[ark]==5.0.13'
uv lock
uv sync --locked

新环境更新
uv lock --upgrade
uv sync

### 激活虚拟环境：

```bash
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate
```

## 从 `openclaw.json` 获取 config/openclaw 关键参数

OpenClaw 的运行配置通常保存在用户目录下的 `openclaw.json`（例如 `%USERPROFILE%\.openclaw\openclaw.json`）。下面列出常用字段和示例取法，方便填入本项目 `config/openclaw/config.yaml` 或用在脚本中。

- Gateway 认证 Token
	- JSON 路径：`gateway.auth.token`
	- PowerShell：
		```powershell
		(Get-Content "$env:USERPROFILE\.openclaw\openclaw.json" -Raw | ConvertFrom-Json).gateway.auth.token
		```
	- Python：
		```python
		import json, os
		p = os.path.join(os.path.expanduser('~'), '.openclaw', 'openclaw.json')
		data = json.load(open(p, 'r', encoding='utf-8'))
		print(data['gateway']['auth']['token'])
		```

- Gateway 监听端口 / 绑定地址（用于构建 WebSocket URL）
	- JSON 路径：`gateway.port`、`gateway.bind`
	- 例：`port=18789`, `bind=loopback` → WebSocket URL 为 `ws://localhost:18789`

- 默认 Agent / 默认模型
	- JSON 路径（默认模型）：`agents.defaults.model.primary`
	- JSON 路径（workspace）：`agents.defaults.workspace`
	- Python 示例：
		```python
		print(data['agents']['defaults']['model']['primary'])
		print(data['agents']['defaults']['workspace'])
		```

- Session 作用域
	- JSON 路径：`session.dmScope`（例如 `per-channel-peer` 或 `per-sender`）

说明：
- `sessionKey` 由 OpenClaw 在调用 `sessions.create` 时返回（本服务会向前端透传）。
- `idempotencyKey` 不是由 OpenClaw 返回的，通常由调用方（前端或本服务）生成 UUID，并且每次 `chat.send` 请求应使用不同的值。

### 示例配置文件

下面是放在 `config/openclaw/config.yaml` 的示例：

```yaml
GATEWAY_URL: ws://localhost:18789
GATEWAY_TOKEN: xxxxxxxxxxxxxxxxxxxxxxxxxx
```

以及 `device.json` 的示例格式（通常放在 `config/openclaw/device.json`）：

```json
{
	"deviceId": "xxxxxxxxxxxxxxxxxx",
	"publicKey": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
	"privateKey": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}
```

说明：将上述 `GATEWAY_TOKEN` 与 `GATEWAY_URL` 填入 `config/openclaw/config.yaml`，服务启动后会使用这些值连接本地 OpenClaw Gateway；`device.json` 是可选的设备身份信息文件，用于某些受管节点或签名功能。
