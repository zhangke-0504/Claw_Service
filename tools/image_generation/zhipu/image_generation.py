import time
from typing import Dict, Any
from pathlib import Path

import requests


class GLMImageClient:
    """
    智谱 GLM Image 异步生图客户端
    """

    BASE_URL = "https://open.bigmodel.cn/api/paas/v4"

    def __init__(
        self,
        api_key: str,
        model: str = "glm-image",
        timeout: int = 60,
    ):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    @property
    def headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    # ----------------------------
    # 创建生图任务
    # ----------------------------
    def generate(
        self,
        prompt: str,
        size: str = "1280x1280",
        quality: str = "hd",
        watermark_enabled: bool = True,
    ) -> Dict[str, Any]:

        url = f"{self.BASE_URL}/async/images/generations"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "size": size,
            "quality": quality,
            "watermark_enabled": watermark_enabled,
        }

        response = requests.post(
            url,
            headers=self.headers,
            json=payload,
            timeout=self.timeout,
        )

        response.raise_for_status()

        return response.json()

    # ----------------------------
    # 查询任务结果
    # ----------------------------
    def get_result(
        self,
        task_id: str,
    ) -> Dict[str, Any]:

        url = f"{self.BASE_URL}/async-result/{task_id}"

        response = requests.get(
            url,
            headers=self.headers,
            timeout=self.timeout,
        )

        response.raise_for_status()

        return response.json()


if __name__ == "__main__":

    # Load API key from config/zhipu/config.yaml (project root relative)
    config_path = Path(__file__).resolve().parents[3] / "config" / "zhipu" / "config.yaml"

    api_key = None
    try:
        import yaml

        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
            if isinstance(cfg, dict):
                api_key = cfg.get("API_KEY")
    except Exception:
        # fallback: simple line-based parser if PyYAML isn't available
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("API_KEY:"):
                        api_key = line.split(":", 1)[1].strip()
                        break
        except FileNotFoundError:
            raise RuntimeError(f"Config file not found: {config_path}")

    if not api_key:
        raise RuntimeError(f"API_KEY not found in config file: {config_path}")

    client = GLMImageClient(api_key)

    # # 1. 创建任务
    # task = client.generate(
    #     prompt="一只可爱的小猫咪，坐在阳光明媚的窗台上，背景是蓝天白云。",
    #     size="1280x1280",
    # )

    # task_id = task["id"]
    task_id = "20260714215525bde66878eaed4922"

    print("=" * 60)
    print("任务创建成功")
    print("Task ID:", task_id)
    print("=" * 60)

    # 2. 开始轮询
    while True:

        result = client.get_result(task_id)

        status = result.get("task_status", "")

        print(f"当前状态：{status}")

        if status == "SUCCESS":

            print("\n生图完成！")

            # 图片生成接口返回 data 字段
            images = result.get("data", [])

            if images:
                print("图片URL：")
                for item in images:
                    print(item.get("url"))

            # 有些接口会返回 image_result，也兼容一下
            image_result = result.get("image_result", [])
            if image_result:
                print("图片URL：")
                for item in image_result:
                    print(item.get("url"))

            break

        elif status == "FAIL":
            print("生成失败")
            print(result)
            break

        else:
            print("继续等待 2 秒...")
            time.sleep(2)