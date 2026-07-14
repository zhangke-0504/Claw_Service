# Harness_QuickStart
Harness实战学习

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
