---
name: glm-image
description: 使用智谱 GLM Image 模型生成图片，并返回最终图片 URL。
---

# 技能名称

GLM Image 图片生成

# 使用场景

当用户有以下需求时使用本技能：

- 生成图片
- AI 绘图
- 根据描述生成图片
- 根据 Prompt 创作图片
- 海报设计
- 插画设计
- 壁纸生成
- Logo 设计
- 吉祥物设计
- 二次元图片生成
- 任何要求使用 GLM Image 生图的请求

例如：

- 帮我画一只猫
- 生成一张未来城市
- 给我设计一个 Logo
- 根据下面描述生成图片
- AI 帮我画一张海报

---

# 执行流程

## 第一步：提取用户参数

从用户输入中提取：

- prompt（必须）
- size（可选）

如果用户没有指定尺寸，则默认：

```
1280x1280
```

quality 固定：

```
hd
```

watermark_enabled 固定：

```
true
```

---

## 第二步：读取 API Key

先从 OpenClaw 根目录读取 API Key，不要基于当前工作目录或 `workspace/` 相对路径去拼接。

OpenClaw 根目录示例：

```
$env:USERPROFILE/.openclaw
```

优先读取下面的配置文件：

```
provider_config/zhipu/config.yaml
```

也就是：

```
$env:USERPROFILE/.openclaw/provider_config/zhipu/config.yaml
```

如果运行环境的当前目录已经是 OpenClaw 根目录，也可以读取：

```
provider_config/zhipu/config.yaml
```

如果当前目录位于 `workspace/` 下，则回退读取：

```
../provider_config/zhipu/config.yaml
```

读取字段：

```
API_KEY
```

推荐顺序：

1. `$env:USERPROFILE/.openclaw/provider_config/zhipu/config.yaml`
2. `provider_config/zhipu/config.yaml`
3. `../provider_config/zhipu/config.yaml`

只要任一候选路径读取成功且拿到 `API_KEY`，就继续执行。

如果某个候选路径不存在，不要立刻失败，应继续尝试下一个候选路径。

如果所有候选路径都未读取到 `API_KEY`，再返回失败信息，不要继续请求生图接口。

---

## 第三步：创建生图任务

调用工具：

```
POST
https://open.bigmodel.cn/api/paas/v4/async/images/generations
```

Header：

```
Authorization: Bearer {api_key}
Content-Type: application/json
```

Body：

```json
{
  "model": "glm-image",
  "prompt": "{prompt}",
  "size": "{size}",
  "quality": "hd",
  "watermark_enabled": true
}
```

从返回结果中读取：

```
id
```

作为：

```
task_id
```

---

## 第四步：轮询任务

每隔 2 秒调用一次：

```
GET
https://open.bigmodel.cn/api/paas/v4/async-result/{task_id}
```

直到：

```
task_status == SUCCESS
```

或：

```
task_status == FAIL
```

---

## 第五步：写入完整响应到临时文件

若轮询结果返回成功或失败响应，不要直接通过 stdout 管道传递完整 JSON。

必须先将接口返回的完整原始响应写入临时目录下的文件，例如：

```
tmp/download/glm-image-result.json
```

要求：

- 写入时必须保留完整原始响应内容，不允许截断。
- 不允许只打印长 URL 再从终端输出中复制。
- 这样做的目的是避免带签名的长 URL 在 stdout、process 输出或展示链路中被省略为 `…`，从而导致 `invalid signature`。

---

## 第六步：从临时文件读取并解析结果

若：

```
task_status == SUCCESS
```

先从临时文件中读取完整响应，再解析下面字段。

优先读取：

```
data
```

中的：

```
url
```

如果不存在，则读取：

```
image_result
```

中的：

```
url
```

如果存在多个图片 URL，则全部返回。

---

若：

```
task_status == FAIL
```

同样先从临时文件读取完整响应，再返回失败信息。

---

## 第七步：返回完整 URL 字符串

拿到完整 URL 后，不需要下载图片到本地，也不需要通过 `MEDIA:`、附件或富媒体方式展示图片。

最终只返回完整的原始图片 URL 字符串给用户。

要求：

- 返回给用户的必须是第六步从临时文件中读取出来的完整原始 URL。
- 不允许返回被截断、缩写、替换过的 URL。
- 不允许为了展示效果改用本地下载文件或富媒体卡片。
- 如果存在多个图片 URL，则将每个完整 URL 逐条返回。

原理：

skill 的职责仅是把完整 URL 准确返回给用户，不负责下载图片，也不负责展示图片。

---

# 返回格式

## 成功

```
图片生成成功

Prompt：
{prompt}

图片地址：

1.
{url1}

2.
{url2}
```

如果只有一张：

```
图片生成成功

Prompt：
{prompt}

图片地址：

{url}
```

只返回完整 URL 字符串，不输出 `MEDIA:`，不输出附件，不下载图片到本地。

---

## 失败

```
图片生成失败

任务状态：

FAIL

详细信息：

{返回内容}
```

---

# 注意事项

- 必须等待异步任务完成，不允许只返回 task_id。
- 必须轮询接口，不允许要求用户自行查询。
- 必须先从 `provider_config/zhipu/config.yaml` 读取 `API_KEY`，禁止在 skill 中硬编码 API key。
- 默认轮询间隔为 2 秒。
- 默认使用 `glm-image` 模型。
- 默认尺寸为 `1280x1280`。
- 默认 quality 为 `hd`。
- 默认开启水印。
- 为避免 stdout 截断，轮询得到的完整响应必须先写入 `tmp/download` 下的临时文件，再从文件读取并解析最终 URL，读取完之后需要将临时文件删除。
- 返回 URL 时必须逐字原样输出，不允许截断、缩写、省略号替换、Markdown 改写、URL 编码二次处理或添加额外标点。
- 尤其是查询参数中的 `Signature`、`Expires`、`UCloudPublicKey` 必须保持原样；任意字符变化都会导致 `invalid signature`。
- 最终只返回完整 URL 字符串给用户，不下载图片，不输出 `MEDIA:`，不走附件展示。