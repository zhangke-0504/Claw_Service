import asyncio
import json
from pathlib import Path

import websockets
import yaml
import logging


def load_openclaw_config() -> dict:
    config_path = (
        Path(__file__).resolve().parents[2]
        / "config"
        / "openclaw"
        / "config.yaml"
    )
    return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}


class OpenClawGatewayClient:
    def __init__(self):
        config = load_openclaw_config()

        self.token = (
            config.get("GATEWAY_TOKEN")
            or config.get("gateway_token")
        )

        self.ws_url = (
            config.get("GATEWAY_URL")
            or config.get("gateway_url")
            or "ws://localhost:18789"
        )

        self.ws = None
        self.request_id = 1
        self.logger = logging.getLogger("openclaw.gateway.client")
        self._reader_task = None
        self._pending_responses = {}
        self._events = asyncio.Queue()

    async def _reader(self):
        """
        后台持续读取 Gateway 返回的消息。

        根据消息类型自动进行分发：
        - event：放入事件队列，供业务层消费。
        - res：根据请求 ID 唤醒对应等待中的 Future。
        """
        while True:
            try:
                raw = await self.ws.recv()
            except asyncio.CancelledError:
                raise
            except Exception:
                break

            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                # 收到非 JSON 数据，记录日志后忽略
                self.logger.warning("收到非 JSON 数据帧：%r", raw)
                continue

            if message.get("type") == "event":
                self.logger.info("收到事件：%s", message.get("event"))
                await self._events.put(message)
                continue

            if message.get("type") == "res":
                # 将请求 ID 统一转换为字符串，以便与 `_request` 和 `connect`
                # 方法中创建的键保持一致（这两个方法使用的是字符串类型的 ID）。
                # 某些 Gateway 实现可能会返回数字类型的 ID。
                request_id = message.get("id")
                if request_id is None:
                    continue
                request_id = str(request_id)
                future = self._pending_responses.pop(request_id, None)
                if future and not future.done():
                    future.set_result(message)

    async def _request(self, method: str, params: dict) -> dict:
        """
        发送 RPC 请求，并等待对应响应返回。
        """
        request_id = str(self.request_id)
        self.request_id += 1

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending_responses[request_id] = future

        request = {
            "type": "req",
            "id": request_id,
            "method": method,
            "params": params,
        }

        try:
            await self.ws.send(json.dumps(request, ensure_ascii=False))
            return await future
        finally:
            self._pending_responses.pop(request_id, None)

    async def next_event(self) -> dict:
        """
        阻塞等待并返回下一条 Gateway 推送的事件。
        """
        return await self._events.get()

    async def connect(self):
        """
        建立 WebSocket 连接，并完成 Gateway 握手认证。
        """
        if not self.token:
            raise RuntimeError(
                "config/openclaw/config.yaml 中缺少 GATEWAY_TOKEN 配置"
            )

        try:
            self.ws = await websockets.connect(self.ws_url)
        except Exception as e:
            raise RuntimeError(f"连接 Gateway 失败：{e}")

        # 等待 Gateway 返回 challenge 消息
        challenge_raw = await self.ws.recv()

        try:
            challenge = json.loads(challenge_raw)
        except json.JSONDecodeError:
            raise RuntimeError(f"Gateway 返回了非法 Challenge：{challenge_raw}")

        if challenge.get("event") != "connect.challenge":
            raise RuntimeError(f"收到未知握手事件：{challenge}")

        request_id = str(self.request_id)
        self.request_id += 1

        # 启动后台消息读取协程
        self._reader_task = asyncio.create_task(self._reader())

        connect_msg = {
            "type": "req",
            "id": request_id,
            "method": "connect",
            "params": {
                "minProtocol": 4,
                "maxProtocol": 4,
                "client": {
                    # 与官方 Demo 保持完全一致
                    "id": "cli",
                    "version": "1.0.0",
                    "platform": "windows",
                    "mode": "cli",
                },
                "role": "operator",
                "scopes": [
                    "operator.read",
                    "operator.write",
                ],
                "auth": {
                    "token": self.token,
                },
                "locale": "zh-CN",
            },
        }

        response_future = asyncio.get_running_loop().create_future()
        self._pending_responses[request_id] = response_future

        await self.ws.send(json.dumps(connect_msg, ensure_ascii=False))

        # 等待 connect 请求返回结果
        response = await response_future
        self._pending_responses.pop(request_id, None)

        print(
            json.dumps(
                response,
                indent=2,
                ensure_ascii=False,
            )
        )

        if (
            response.get("type") != "res"
            or response.get("ok") is not True
        ):
            raise RuntimeError(response)

        payload = response.get("payload") or {}

        if payload.get("type") != "hello-ok":
            raise RuntimeError(payload)

        print(
            f"连接成功！connId: {payload['server']['connId']}"
        )

        return response

    async def call(
        self,
        method: str,
        params: dict | None = None,
    ):
        """
        调用 Gateway RPC 接口。

        Args:
            method: RPC 方法名。
            params: 请求参数，可为空。

        Returns:
            Gateway 返回的响应字典。
        """
        if not self.ws:
            raise RuntimeError("WebSocket 尚未连接")

        return await self._request(method, params or {})

    async def create_session(
        self,
        agent_id: str = "main",
        params: dict | None = None,
    ) -> str:
        """
        创建一个新的 Session，并返回 Session Key。

        本方法会调用 sessions.create 接口，并尝试兼容官方可能存在的
        多种返回结构，从响应中自动提取可用的 Session Key。

        如果最终仍无法找到 Session Key，则抛出 RuntimeError。
        """
        body = {
            "agentId": agent_id,
        }

        if params:
            body.update(params)

        resp = await self.call("sessions.create", body)

        payload = resp.get("payload") or {}

        # Session Key 可能出现的位置（兼容不同版本返回格式）
        candidates = [
            payload.get("sessionKey"),
            payload.get("key"),
            (payload.get("session") or {}).get("key"),
            resp.get("sessionKey"),
            resp.get("key"),
        ]

        for candidate in candidates:
            if isinstance(candidate, str) and candidate:
                return candidate

        # 最后递归遍历整个响应结构，尝试寻找名为 key 的字段
        def find_key(obj):
            if isinstance(obj, dict):
                if "key" in obj and isinstance(obj["key"], str):
                    return obj["key"]

                for value in obj.values():
                    result = find_key(value)
                    if result:
                        return result

            return None

        session_key = find_key(payload) or find_key(resp)

        if session_key:
            return session_key

        raise RuntimeError(f"无法从响应中找到 Session Key：{resp}")

    async def close(self):
        """
        关闭后台任务并断开 WebSocket 连接。
        """
        if self._reader_task:
            self._reader_task.cancel()
            await asyncio.gather(
                self._reader_task,
                return_exceptions=True,
            )
            self._reader_task = None

        if self.ws:
            await self.ws.close()


async def main():
    client = OpenClawGatewayClient()

    await client.connect()

    sessions = await client.call("sessions.list")

    print(
        json.dumps(
            sessions,
            indent=2,
            ensure_ascii=False,
        )
    )

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())