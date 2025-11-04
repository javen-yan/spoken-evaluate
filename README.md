# spoken-evaluate

面向“标准读音 + 用户录音”场景的端到端口语评测服务原型，包括 FastAPI 后端、React 前端演示页面以及一个极简 JS SDK。

## 架构概览

- **后端**：`backend/` 使用 FastAPI，结合 `librosa` 与 `pydub` 进行音频处理，并自动从有道词典下载参考音频，通过 DTW 对比 MFCC 特征输出多维评分；如服务器安装了 OpenAI Whisper，还会返回自动识别文本。
- **前端**：`frontend/` 基于 React + Vite，填写参考文本、录制或上传用户音频（Web Audio API），提交后展示单词/句子两种模式下的评分细节。
- **SDK**：`sdk/js/index.js` 提供一个 `SpokenEvaluateClient`，便于浏览器或 Node.js 环境直接调用评测接口。

目录结构：

```
backend/           FastAPI 应用源码
frontend/          React 演示前端
sdk/js/            轻量级 JavaScript SDK
```

## 环境准备

### Python 后端

1. 创建并激活虚拟环境（如果已有 `.venv` 请复用）：

   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate
   ```

2. 安装依赖（使用阿里云镜像）：

   ```bash
   pip install -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt
   ```

3. 启动服务：

   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

   可通过环境变量调整行为：

   - `SPOKEN_EVALUATE_SAMPLE_RATE`：重采样目标采样率，默认 16000。
   - `SPOKEN_EVALUATE_WHISPER_MODEL`：Whisper 模型体量（如 `tiny`/`base`/`small`）。
   - `SPOKEN_EVALUATE_LANGUAGE`：指定识别语言，默认自动识别。
   - `SPOKEN_EVALUATE_CORS`：允许运行的前端域名，多个以逗号分隔，默认 `*`。
   - 设置 `DISABLE_WHISPER=1` 可在无 Whisper 包时跳过识别过程。

### React 前端

1. 切换到工程目录并使用 `nvm` 选择兼容 Node 版本（推荐 Node 18+）：

   ```bash
   cd frontend
   nvm use 18
   ```

2. 配置 npm 使用阿里云镜像并安装依赖：

   ```bash
   npm config set registry https://registry.npmmirror.com
   npm install
   ```

3. 运行开发服务：

   ```bash
   npm run dev
   ```

   默认监听 `http://localhost:5173`。若后端不在同一域，可在 `.env` 中设置 `VITE_API_BASE_URL`（例如 `http://localhost:8000`）。

### JavaScript SDK

在浏览器中直接引入：

```javascript
import { SpokenEvaluateClient } from "./sdk/js/index.js";

const client = new SpokenEvaluateClient({ baseUrl: "http://localhost:8000" });
const result = await client.evaluate({
  referenceText: "Hello",
  userAudio: userFile,
  evaluationMode: "WORD",
  voiceType: 2,
});
```

在 Node.js 环境下，可借助 `undici` 提供 `fetch`/`FormData` 支持：

```javascript
import { fetch, FormData, File } from "undici";
import SpokenEvaluateClient from "./sdk/js/index.js";

const client = new SpokenEvaluateClient({
  baseUrl: "http://localhost:8000",
  fetch: (url, options) => fetch(url, { ...options, FormData, File }),
});
```

## API 说明

- `POST /api/evaluate`
  - 请求：`multipart/form-data`
    - `reference_text`：标准文本（必填）
    - `user_audio`：用户录音（必填）
    - `evaluation_mode`：评测模式（`WORD` 或 `SENTENCE`，必填）
    - `voice_type`：有道语音类型（`1`=英式，`2`=美式，默认 `2`）
  - 响应：`EvaluationResponse`
    - `mode`：本次评测模式
    - `word_result`：当 `mode=WORD` 时返回，包含 `character_scores`、`mfcc_score`、`energy_score`、`pitch_score`、`composite_score`、`overall_score`
    - `sentence_result`：当 `mode=SENTENCE` 时返回，包含 `word_scores`、`pronunciation_score`、`fluency_score`、`word_total_score`、`overall_score`
    - `transcript`：如启用 Whisper，则包含识别文本与估算置信度

## 后续方向

- 引入更细粒度的强制对齐算法（如 MFA/CTC）以获得准确的字母发音边界。
- 增加多模态特征（能量包络、基频）与自适应权重策略，提升评分鲁棒性。
- 扩展 SDK，提供 TypeScript 类型定义与构建产物，便于 npm 分发。
