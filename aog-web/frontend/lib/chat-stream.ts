import type { ChatRequest, ChatResponse } from "@/lib/types";
import type { ChatPhase } from "@/lib/chat-state";

const BASE = (process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000").replace(/\/api\/?$/, "");

export interface ChatStatusPayload {
  phase: ChatPhase;
  elapsed_ms?: number;
  first_token_ms?: number | null;
  latency_ms?: number;
  refs_count?: number;
}

export interface SafeChatStreamCallbacks {
  onStatus?: (payload: ChatStatusPayload) => void;
  onRefs?: (payload: {
    references: ChatResponse["references"];
    model: string;
  }) => void;
  onToken?: (delta: string) => void;
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
