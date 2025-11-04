/* eslint-disable no-undef */
/**
 * Minimal JavaScript SDK for the spoken evaluation backend.
 */

const ensureFetch = (customFetch) => {
  if (customFetch) return customFetch;
  if (typeof fetch !== "undefined") return fetch;
  throw new Error("当前运行环境缺少 fetch，请在 Node.js 中引入 undici 或 node-fetch。");
};

export class SpokenEvaluateClient {
  /**
   * @param {{ baseUrl?: string, fetch?: typeof fetch }} [options]
   */
  constructor(options = {}) {
    this.baseUrl = (options.baseUrl || "").replace(/\/$/, "");
    this.fetch = ensureFetch(options.fetch);
  }

  /**
   * @param {{ referenceText: string, referenceAudio: File | Blob, userAudio: File | Blob }} payload
   */
  async evaluate(payload) {
    const { referenceText, referenceAudio, userAudio } = payload;

    if (!referenceAudio) {
      throw new Error("缺少 referenceAudio 文件");
    }
    if (!userAudio) {
      throw new Error("缺少 userAudio 文件");
    }

    const formData = new FormData();
    formData.append("reference_text", referenceText || "");
    formData.append("reference_audio", referenceAudio);
    formData.append("user_audio", userAudio);

    const url = `${this.baseUrl}/api/evaluate`.replace("//api", "/api");
    const response = await this.fetch(url, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      let detail = "请求失败";
      try {
        const payload = await response.json();
        detail = payload?.detail || detail;
      } catch (err) {
        // ignore JSON parse error
      }
      throw new Error(detail);
    }

    return response.json();
  }
}

export default SpokenEvaluateClient;
