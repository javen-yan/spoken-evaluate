import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

const formatNumber = (value, fractionDigits = 2) =>
  typeof value === "number" ? value.toFixed(fractionDigits) : "-";

function LetterScoreList({ scores }) {
  if (!scores?.length) {
    return <p>暂无字母级评分，请确认参考文本是否填写正确。</p>;
  }

  return (
    <div className="letter-list">
      {scores.map((item) => (
        <div className="letter-item" key={`${item.symbol}-${item.frame_start}`}>
          <span className="symbol">{item.symbol}</span>
          <span>{formatNumber(item.score, 1)}</span>
        </div>
      ))}
    </div>
  );
}

export default function App() {
  const [referenceText, setReferenceText] = useState("Hello");
  const [referenceAudio, setReferenceAudio] = useState(null);
  const [userAudio, setUserAudio] = useState(null);
  const [result, setResult] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [isRecording, setIsRecording] = useState(false);

  const mediaRecorderRef = useRef(null);
  const recordingChunks = useRef([]);

  useEffect(() => {
    return () => {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
        mediaRecorderRef.current.stop();
      }
    };
  }, []);

  const handleReferenceAudioChange = (event) => {
    const [file] = event.target.files;
    setReferenceAudio(file || null);
  };

  const handleUserAudioChange = (event) => {
    const [file] = event.target.files;
    setUserAudio(file || null);
  };

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      recordingChunks.current = [];

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          recordingChunks.current.push(event.data);
        }
      };

      recorder.onstop = () => {
        const blob = new Blob(recordingChunks.current, { type: "audio/webm" });
        const file = new File([blob], "user-recording.webm", { type: "audio/webm" });
        setUserAudio(file);
        stream.getTracks().forEach((track) => track.stop());
        setIsRecording(false);
      };

      recorder.start();
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
      setError("");
    } catch (err) {
      console.error(err);
      setError("启动录音失败，请检查浏览器麦克风权限。");
    }
  }, []);

  const stopRecording = useCallback(() => {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.stop();
    }
  }, []);

  const handleSubmit = useCallback(
    async (event) => {
      event?.preventDefault();
      if (!referenceAudio) {
        setError("请先上传参考音频文件。");
        return;
      }
      if (!userAudio) {
        setError("请录制或上传用户音频文件。");
        return;
      }

      setIsSubmitting(true);
      setError("");

      try {
        const formData = new FormData();
        formData.append("reference_text", referenceText.trim() || "Hello");
        formData.append("reference_audio", referenceAudio);
        formData.append("user_audio", userAudio);

        const endpoint = `${API_BASE_URL}/api/evaluate`.replace("//api", "/api");
        const response = await fetch(endpoint, {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          const detail = await response.json().catch(() => null);
          throw new Error(detail?.detail || "评测请求失败，请稍后重试。");
        }

        const payload = await response.json();
        setResult(payload);
      } catch (err) {
        console.error(err);
        setError(err.message || "网络请求异常。");
      } finally {
        setIsSubmitting(false);
      }
    },
    [referenceAudio, referenceText, userAudio]
  );

  const reset = () => {
    setReferenceText("Hello");
    setReferenceAudio(null);
    setUserAudio(null);
    setResult(null);
    setError("");
  };

  const metricsView = useMemo(() => {
    if (!result?.metrics) return null;
    const { dtw_distance, energy_ratio, duration_ratio, articulation_score } = result.metrics;

    return (
      <div className="metrics-grid">
        <div className="metric-item">
          <h4>DTW 距离</h4>
          <span>{formatNumber(dtw_distance)}</span>
        </div>
        <div className="metric-item">
          <h4>音量比</h4>
          <span>{formatNumber(energy_ratio)}</span>
        </div>
        <div className="metric-item">
          <h4>时长比</h4>
          <span>{formatNumber(duration_ratio)}</span>
        </div>
        <div className="metric-item">
          <h4>咬字分</h4>
          <span>{formatNumber(articulation_score, 1)}</span>
        </div>
      </div>
    );
  }, [result]);

  return (
    <div className="app">
      <h1>口语评测演示</h1>
      <p>上传标准读音并录制自己的读音，系统会通过 DTW + MFCC 对比给出评分。</p>

      <form className="card" onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="reference-text">参考文本</label>
          <textarea
            id="reference-text"
            rows={2}
            value={referenceText}
            onChange={(event) => setReferenceText(event.target.value)}
            placeholder="请输入标准读音对应的文本"
          />
        </div>

        <div className="field">
          <label htmlFor="reference-audio">参考音频</label>
          <input
            id="reference-audio"
            type="file"
            accept="audio/*"
            onChange={handleReferenceAudioChange}
          />
          {referenceAudio && <span>已选择：{referenceAudio.name}</span>}
        </div>

        <div className="field">
          <label htmlFor="user-audio">用户音频</label>
          <input id="user-audio" type="file" accept="audio/*" onChange={handleUserAudioChange} />
          {userAudio && <span>已选择：{userAudio.name}</span>}
        </div>

        <div className="actions">
          {!isRecording ? (
            <button type="button" onClick={startRecording} className="secondary">
              🎙️ 开始录音
            </button>
          ) : (
            <button type="button" onClick={stopRecording} className="secondary">
              ⏹️ 停止录音
            </button>
          )}

          <button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "评测中..." : "开始评测"}
          </button>

          <button type="button" className="secondary" onClick={reset}>
            重置
          </button>
        </div>

        {error && <p style={{ color: "#dc2626" }}>{error}</p>}
      </form>

      {result && (
        <div className="card result-card">
          <div>
            <span className="score">{formatNumber(result.overall_score, 1)}</span>
            <div>综合评分（0-100）</div>
            <div>归一化分数：{formatNumber(result.normalized_score, 3)}</div>
          </div>

          <div>
            <h2>逐字评分</h2>
            <LetterScoreList scores={result.letter_scores} />
          </div>

          <div>
            <h2>评估指标</h2>
            {metricsView}
          </div>

          {result.transcript?.text ? (
            <div>
              <h2>语音识别</h2>
              <p>{result.transcript.text}</p>
              {typeof result.transcript.confidence === "number" && (
                <small>置信度：{formatNumber(result.transcript.confidence, 2)}</small>
              )}
            </div>
          ) : (
            <small>若服务器未安装 Whisper，将跳过自动识别。</small>
          )}
        </div>
      )}
    </div>
  );
}
