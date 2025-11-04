import React, { useCallback, useEffect, useRef, useState } from "react";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

const formatNumber = (value, fractionDigits = 2) =>
  typeof value === "number" ? value.toFixed(fractionDigits) : "-";

function CharacterScoreList({ scores }) {
  if (!scores?.length) {
    return <p>暂无字符级评分，请确认参考文本是否填写正确。</p>;
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

function WordScoreList({ scores }) {
  if (!scores?.length) {
    return <p>暂无单词级评分，请确认文本是否填写正确。</p>;
  }

  return (
    <div className="letter-list">
      {scores.map((item) => (
        <div className="letter-item" key={`${item.word}-${item.frame_start}`}>
          <span className="symbol">{item.word}</span>
          <span>{formatNumber(item.score, 1)}</span>
        </div>
      ))}
    </div>
  );
}

export default function App() {
  const [referenceText, setReferenceText] = useState("Hello");
  const [userAudio, setUserAudio] = useState(null);
  const [evaluationMode, setEvaluationMode] = useState("WORD");
  const [voiceType, setVoiceType] = useState(2);
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
      if (!userAudio) {
        setError("请录制或上传用户音频文件。");
        return;
      }

      setIsSubmitting(true);
      setError("");

      try {
        const formData = new FormData();
        formData.append("reference_text", referenceText.trim() || "Hello");
        formData.append("user_audio", userAudio);
        formData.append("evaluation_mode", evaluationMode);
        formData.append("voice_type", String(voiceType));

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
    [evaluationMode, referenceText, userAudio, voiceType]
  );

  const reset = () => {
    setReferenceText("Hello");
    setUserAudio(null);
    setEvaluationMode("WORD");
    setVoiceType(2);
    setResult(null);
    setError("");
  };

  return (
    <div className="app">
      <h1>口语评测演示</h1>
      <p>填写参考文本并录制自己的读音，系统将自动从有道获取标准音频进行比对。</p>

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
          <label htmlFor="evaluation-mode">评测模式</label>
          <select
            id="evaluation-mode"
            value={evaluationMode}
            onChange={(event) => setEvaluationMode(event.target.value)}
          >
            <option value="WORD">单词模式</option>
            <option value="SENTENCE">句子模式</option>
          </select>
        </div>

        <div className="field">
          <label htmlFor="voice-type">标准发音类型</label>
          <select
            id="voice-type"
            value={voiceType}
            onChange={(event) => setVoiceType(Number(event.target.value))}
          >
            <option value={1}>英式发音 (type=1)</option>
            <option value={2}>美式发音 (type=2)</option>
          </select>
          <small>从有道字典获取标准音频所使用的发音类型。</small>
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
          {result.mode === "WORD" && result.word_result && (
            <>
              <div>
                <span className="score">{formatNumber(result.word_result.overall_score, 1)}</span>
                <div>整体单词评分（0-100）</div>
              </div>
              <div>
                <h2>逐字评分</h2>
                <CharacterScoreList scores={result.word_result.character_scores} />
              </div>
              <div className="metrics-grid">
                <div className="metric-item">
                  <h4>综合得分</h4>
                  <span>{formatNumber(result.word_result.composite_score, 1)}</span>
                </div>
                <div className="metric-item">
                  <h4>MFCC 得分</h4>
                  <span>{formatNumber(result.word_result.mfcc_score, 1)}</span>
                </div>
                <div className="metric-item">
                  <h4>能量得分</h4>
                  <span>{formatNumber(result.word_result.energy_score, 1)}</span>
                </div>
                <div className="metric-item">
                  <h4>音高得分</h4>
                  <span>{formatNumber(result.word_result.pitch_score, 1)}</span>
                </div>
              </div>
            </>
          )}

          {result.mode === "SENTENCE" && result.sentence_result && (
            <>
              <div>
                <span className="score">{formatNumber(result.sentence_result.overall_score, 1)}</span>
                <div>整体句子评分（0-100）</div>
              </div>
              <div>
                <h2>单词级评分</h2>
                <WordScoreList scores={result.sentence_result.word_scores} />
              </div>
              <div className="metrics-grid">
                <div className="metric-item">
                  <h4>发音得分</h4>
                  <span>{formatNumber(result.sentence_result.pronunciation_score, 1)}</span>
                </div>
                <div className="metric-item">
                  <h4>流利度得分</h4>
                  <span>{formatNumber(result.sentence_result.fluency_score, 1)}</span>
                </div>
                <div className="metric-item">
                  <h4>单词总分</h4>
                  <span>{formatNumber(result.sentence_result.word_total_score, 1)}</span>
                </div>
              </div>
            </>
          )}

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
