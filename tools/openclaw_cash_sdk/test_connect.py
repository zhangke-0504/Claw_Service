import asyncio
import json
from pathlib import Path

import websockets
import yaml


def load_openclaw_config() -> dict:
    config_path = Path(__file__).resolve().parents[2] / "config" / "openclaw" / "config.yaml"
    return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}


async def recv_response(ws, request_id: str) -> dict:
    while True:
        message = json.loads(await ws.recv())
        if message.get("type") == "event":
            print(f"收到事件: {message.get('event')}")
            continue
        if message.get("type") == "res" and message.get("id") == request_id:
            return message


async def main() -> None:
    config = load_openclaw_config()
    token = config.get("GATEWAY_TOKEN") or config.get("gateway_token")
    ws_url = config.get("GATEWAY_URL") or config.get("gateway_url") or "ws://localhost:18789"

    if not token:
        raise RuntimeError("config/openclaw/config.yaml is missing GATEWAY_TOKEN")

    async with websockets.connect(ws_url) as ws:
        challenge = json.loads(await ws.recv())
        assert challenge["event"] == "connect.challenge"

        connect_msg = {
            "type": "req",
            "id": "1",
            "method": "connect",
            "params": {
                "minProtocol": 4,
                "maxProtocol": 4,
                "client": {
                    "id": "cli",
                    "version": "1.0.0",
                    "platform": "windows",
                    "mode": "cli",
                },
                "role": "operator",
                "scopes": ["operator.read", "operator.write"],
                "auth": {"token": token},
                "locale": "zh-CN",
            },
        }
        await ws.send(json.dumps(connect_msg, ensure_ascii=False))

        response = await recv_response(ws, "1")
        print(f"connect 响应: {json.dumps(response, indent=2, ensure_ascii=False)}")
        if response.get("type") != "res" or response.get("ok") is not True:
            raise RuntimeError(f"connect failed: {json.dumps(response, ensure_ascii=False)}")

        payload = response.get("payload") or {}
        if payload.get("type") != "hello-ok":
            raise RuntimeError(f"unexpected connect payload: {json.dumps(payload, ensure_ascii=False)}")

        print(f"连接成功! connId: {payload['server']['connId']}")

        request = {
            "type": "req",
            "id": "2",
            "method": "sessions.list",
            "params": {},
        }
        await ws.send(json.dumps(request, ensure_ascii=False))
        result = await recv_response(ws, "2")
        print(f"会话列表: {json.dumps(result, indent=2, ensure_ascii=False)}")


if __name__ == "__main__":
    asyncio.run(main())