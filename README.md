# spoken-evaluate


## 想法

我想做一个口语评测的服务

输入部分
- 提供标准读音
- 提供用户录制音频

分析用户读音和标准读音的标准度， 然后分别识别字母读音的分数

例子：
  比如 Hello， H / e / l / l / o 分别多少分， 总共得分多少

## 设计框架

- 后端: Python (FastAPI)
- 音频处理: librosa, pydub
- 语音识别: OpenAI Whisper (自适应 cpu/gpu)
- 发音评估: 动态时间规整(DTW) + 声学特征分析
- 前端: React + Web Audio API
- SDK： 提供 jssdk 方便前端集成
