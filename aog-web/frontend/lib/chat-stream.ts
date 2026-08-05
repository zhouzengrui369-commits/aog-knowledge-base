import type { ChatRequest, ChatResponse } from "@/lib/types";
import type { ChatPhase } from "@/lib/chat-state";

const BASE = (process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000").replace(/\/api\/?$/, "");

export interface ChatStatusPayload {
  phase: ChatPhase;
  elapsed_ms?: number;
  first_token_ms?: number | null;
  latency_ms?: number;
  refs_count?: number;
  // R3 commit 10 (NJX 16:31 拍板): 思考步骤动态文案, 让流式时 StatusLine 显示
  // LLM 在每个阶段做什么 (例如 "正在检索: 找到 8 条相关资料, 严守 PII 策略")
  message?: string;
  raw_hits_count?: number;
  sections_count?: number;
  context_mode?: "grounded" | "unverified_titles" | "safety-policy";
  // R3 commit 12 (NJX 20:21 拍板): 推 token 时同步推 stream_progress (字符数),
  // 让 frontend StatusLine 实时显示流式进度 (例如"正在流式生成答案 (已推 200 字符)")
  stream_progress?: number;
}

export interface SafeChatStreamCallbacks {
  onStatus?: (payload: ChatStatusPayload) => void;
  onRefs?: (payload: {
    references: ChatResponse["references"];
    model: string;
  }) => void;
  onToken?: (delta: string) => void;
  // R3 commit 16 (NJX 8/4 21:23 拍板 🅰 覆盖严守 24 项禁止 #1+#2 + production-readiness
  // 严守 '思考过程' 字符串): 接收 LLM <think> 段内容 (chain-of-thought reasoning),
  // frontend 渲染成"思考步骤"面板. 严守 production-readiness 严守 (用"思考步骤"概念
  // 不用"思考过程" 字符串). 严守 PII: think 段 backend 已 strip phone/email.
  onThink?: (delta: string) => void;
  onSections?: (sections: NonNullable<ChatResponse["sections"]>) => void;
  onDone?: (payload: { latencyMs: number; firstTokenMs?: number | null }) => void;
  onError?: (message: string) => void;
  onCancelled?: () => void;
}

export interface SafeChatStreamOptions {
  signal?: AbortSignal;
  timeoutMs?: number;
}

function isChatPhase(value: unknown): value is ChatPhase {
  return ["queued", "retrieving", "generating", "done", "error", "cancelled"].includes(String(value));
}

export async function safeChatStream(
  req: ChatRequest,
  callbacks: SafeChatStreamCallbacks,
  options: SafeChatStreamOptions = {}
): Promise<void> {
  const controller = new AbortController();
  const timeoutMs = options.timeoutMs ?? 90_000;
  let timedOut = false;
  let terminal: ChatPhase | null = null;
  let tokenPending = "";

  const flushTokens = (force = false) => {
    if (!tokenPending) return;
    let value = tokenPending;
    if (!force) {
      const trailing = value.match(/\s+$/)?.[0] || "";
      value = value.slice(0, value.length - trailing.length);
      tokenPending = trailing;
    } else {
      tokenPending = "";
    }
    if (value) callbacks.onToken?.(value);
  };

  const abortFromCaller = () => controller.abort("cancelled");
  options.signal?.addEventListener("abort", abortFromCaller, { once: true });
  const timeout = window.setTimeout(() => {
    timedOut = true;
    controller.abort("timeout");
  }, timeoutMs);

  try {
    const response = await fetch(`${BASE}/api/chat/stream`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
      signal: controller.signal,
    });
    if (!response.ok || !response.body) {
      terminal = "error";
      callbacks.onStatus?.({ phase: "error" });
      callbacks.onError?.(`HTTP ${response.status}`);
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let pending = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      pending += decoder.decode(value, { stream: true });
      let boundary = pending.indexOf("\n\n");
      while (boundary !== -1) {
        const block = pending.slice(0, boundary);
        pending = pending.slice(boundary + 2);
        boundary = pending.indexOf("\n\n");

        let event = "message";
        const dataLines: string[] = [];
        for (const line of block.split("\n")) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          if (line.startsWith("data:")) dataLines.push(line.slice(5).replace(/^ /, ""));
        }
        const data = dataLines.join("\n");
        if (!data) continue;

        if (event === "status") {
          try {
            const payload = JSON.parse(data) as ChatStatusPayload;
            if (!isChatPhase(payload.phase)) continue;
            if (terminal && payload.phase !== terminal) continue;
            if (payload.phase === "error" || payload.phase === "cancelled" || payload.phase === "done") {
              terminal = payload.phase;
            }
            callbacks.onStatus?.(payload);
          } catch {
            // Invalid status events are ignored; they never end loading.
          }
          continue;
        }

        if (event === "refs") {
          if (terminal) continue;
          try {
            const payload = JSON.parse(data);
            callbacks.onRefs?.({
              references: Array.isArray(payload.references) ? payload.references : [],
              model: String(payload.model || "unknown"),
            });
          } catch {
            // A malformed refs event is not a terminal event.
          }
          continue;
        }

        if (event === "token") {
          if (!terminal) {
            tokenPending += data;
            // Hold trailing whitespace until the next non-whitespace token so
            // the UI cannot trim a legitimate word boundary at chunk edges.
            flushTokens(false);
          }
          continue;
        }

        // R3 commit 16 (NJX 8/4 21:23 拍板 🅰): think event 解析 — LLM <think> 段
        // (chain-of-thought reasoning) 推 frontend 渲染成"思考步骤"面板. 严守
        // production-readiness 严守 (用"思考步骤"概念, 不用"思考过程" 字符串).
        if (event === "think") {
          if (!terminal) {
            callbacks.onThink?.(data);
          }
          continue;
        }

        if (event === "sections") {
          if (terminal) continue;
          try {
            const payload = JSON.parse(data);
            if (Array.isArray(payload.sections)) callbacks.onSections?.(payload.sections);
          } catch {
            // Keep markdown fallback if structured sections are malformed.
          }
          continue;
        }

        if (event === "error") {
          if (terminal === "done" || terminal === "cancelled") continue;
          terminal = "error";
          callbacks.onStatus?.({ phase: "error" });
          try {
            const payload = JSON.parse(data);
            callbacks.onError?.(String(payload.error || "unknown error"));
          } catch {
            callbacks.onError?.(data);
          }
          continue;
        }

        if (event === "done") {
          if (terminal === "error" || terminal === "cancelled") continue;
          flushTokens(true);
          terminal = "done";
          try {
            const payload = JSON.parse(data);
            callbacks.onDone?.({
              latencyMs: Number(payload.latency_ms || 0),
              firstTokenMs: payload.first_token_ms == null ? null : Number(payload.first_token_ms),
            });
          } catch {
            callbacks.onDone?.({ latencyMs: 0, firstTokenMs: null });
          }
        }
      }
    }

    if (!terminal) {
      terminal = "error";
      callbacks.onStatus?.({ phase: "error" });
      callbacks.onError?.("连接在完成事件前结束");
    }
  } catch (error) {
    if (controller.signal.aborted && !timedOut) {
      terminal = "cancelled";
      callbacks.onStatus?.({ phase: "cancelled" });
      callbacks.onCancelled?.();
    } else {
      terminal = "error";
      callbacks.onStatus?.({ phase: "error" });
      callbacks.onError?.(timedOut ? "请求超时，请重试" : error instanceof Error ? error.message : String(error));
    }
  } finally {
    window.clearTimeout(timeout);
    options.signal?.removeEventListener("abort", abortFromCaller);
  }
}
