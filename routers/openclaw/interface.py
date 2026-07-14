from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

import asyncio
import logging
from uuid import uuid4

from tools.openclaw_cash_sdk.gateway_client import OpenClawGatewayClient

router = APIRouter()
logger = logging.getLogger("app")


class TestResponse(BaseModel):
    message: str


@router.post("/test", response_model=TestResponse)
def test():
    logger.info("Demo /test called")
    return {"message": "Hello Manuscript!"}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    client = OpenClawGatewayClient()
    await client.connect()

    logger.info("OpenClaw Gateway connected.")

    # Session 与当前 WebSocket 会话一一对应，因此在 Gateway 连接成功后
    # 立即创建一个 Session，并将 Session Key 返回给前端。
    # 当前端首次调用 chat.send 时，如果没有主动传入 Session Key，
    # 服务端会自动使用这里创建的 Session。
    session_key = await client.create_session()
    await websocket.send_json(
        {
            "type": "connection.ready",
            "sessionKey": session_key,
        }
    )

    async def forward_gateway_events():
        """
        持续监听 Gateway 推送的事件，并转发给前端。
        """
        while True:
            event = await client.next_event()
            await websocket.send_json(event)

    event_task = asyncio.create_task(forward_gateway_events())

    try:
        while True:
            request = await websocket.receive_json()

            method = request.get("method")
            params = dict(request.get("params") or {})

            logger.info(f"Gateway Call: {method}")

            try:
                # chat.send 请求必须同时包含 sessionKey 和 idempotencyKey。
                # 如果前端没有提供 sessionKey，则自动使用当前 WebSocket
                # 对应的 Session；同时为每次请求生成新的幂等键。
                if method == "chat.send":
                    if not params.get("sessionKey"):
                        params["sessionKey"] = session_key
                        logger.info("自动使用 Session Key：%s", session_key)

                    # 每次请求都由服务端生成新的 idempotencyKey，
                    # 忽略前端传入的同名参数。
                    params["idempotencyKey"] = str(uuid4())
                    logger.debug(
                        "生成 idempotencyKey：%s",
                        params["idempotencyKey"],
                    )

                result = await client.call(
                    method=method,
                    params=params,
                )

                await websocket.send_json(result)

            except Exception as e:
                logger.exception("调用 Gateway 时发生异常")

                try:
                    await websocket.send_json(
                        {
                            "error": str(e),
                        }
                    )
                except Exception:
                    # 如果调用 Gateway 的过程中前端已经断开连接，
                    # 则无需继续发送错误信息，资源清理由 finally 统一完成。
                    break

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected.")
    except Exception:
        logger.exception("Unexpected error in websocket endpoint")

    finally:
        event_task.cancel()
        await asyncio.gather(
            event_task,
            return_exceptions=True,
        )
        await client.close()