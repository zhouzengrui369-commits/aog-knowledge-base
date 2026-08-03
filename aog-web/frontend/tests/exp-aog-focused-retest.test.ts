import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  applyIntermediateReferences,
  CHAT_SESSION_TTL_MS,
  clearAllChatSessions,
  loadChatSession,
  saveChatSession,
  sessionStorageKey,
  transitionChatPhase,
  type ChatMessageState,
  type StorageLike,
} from "@/lib/chat-state";

class MemoryStorage implements StorageLike {
  private values = new Map<string, string>();
  get length() { return this.values.size; }
  key(index: number) { return Array.from(this.values.keys())[index] ?? null; }
  getItem(key: string) { return this.values.get(key) ?? null; }
  setItem(key: string, value: string) { this.values.set(key, value); }
  removeItem(key: string) { this.values.delete(key); }
}

function source(path: string): string {
  return readFileSync(resolve(process.cwd(), path), "utf8");
}

describe("EXP-AOG-20260803 focused retest contracts", () => {
  it("implements the strict queued/retrieving/generating/done path", () => {
    expect(transitionChatPhase("queued", "retrieving")).toBe("retrieving");
    expect(transitionChatPhase("retrieving", "generating")).toBe("generating");
    expect(transitionChatPhase("generating", "done")).toBe("done");
  });

  it("keeps refs intermediate and never changes the phase to done", () => {
    const message: ChatMessageState = {
      id: "assistant-1",
      role: "assistant",
      text: "",
      phase: "retrieving",
      references: [],
    };
    const next = applyIntermediateReferences(message, [{
      id: "ref-1",
      title: "已核验来源",
      href: "/city/V-test",
      snippet: "fixture",
      score: 0.8,
      available: true,
      source_type: "city",
      verification_status: "VERIFIED",
    }], "minimax-test");
    expect(next.phase).toBe("retrieving");
    expect(next.references).toHaveLength(1);
  });

  it("makes error and cancelled terminal", () => {
    expect(() => transitionChatPhase("error", "done")).toThrow(/invalid chat phase transition/);
    expect(() => transitionChatPhase("cancelled", "done")).toThrow(/invalid chat phase transition/);
  });

  it("restores a completed same-session conversation and visited reference", () => {
    const storage = new MemoryStorage();
    saveChatSession(storage, {
      sessionId: "session-a",
      messages: [{ id: "a-1", role: "assistant", text: "done", phase: "done" }],
      lastQuestion: "question",
      lastVisitedReferenceId: "ref-1",
    }, 1000);
    const restored = loadChatSession(storage, "session-a", 2000);
    expect(restored?.messages[0].phase).toBe("done");
    expect(restored?.lastQuestion).toBe("question");
    expect(restored?.lastVisitedReferenceId).toBe("ref-1");
  });

  it("restores an in-flight message as interrupted, never as done", () => {
    const storage = new MemoryStorage();
    saveChatSession(storage, {
      sessionId: "session-a",
      messages: [{ id: "a-1", role: "assistant", text: "partial", phase: "generating" }],
      lastQuestion: "question",
    }, 1000);
    const restored = loadChatSession(storage, "session-a", 2000);
    expect(restored?.messages[0].phase).toBe("error");
    expect(restored?.messages[0].error).toContain("页面刷新中断");
  });

  it("expires session data and does not cross identity namespaces", () => {
    const storage = new MemoryStorage();
    saveChatSession(storage, {
      sessionId: "identity-a",
      messages: [{ id: "a-1", role: "assistant", text: "done", phase: "done" }],
      lastQuestion: "question",
    }, 1000);
    expect(loadChatSession(storage, "identity-b", 2000)).toBeNull();
    expect(loadChatSession(storage, "identity-a", 1000 + CHAT_SESSION_TTL_MS + 1)).toBeNull();
    expect(storage.getItem(sessionStorageKey("identity-a"))).toBeNull();
  });

  it("clears every chat namespace on logout or identity rotation", () => {
    const storage = new MemoryStorage();
    storage.setItem(sessionStorageKey("identity-a"), "{}");
    storage.setItem(sessionStorageKey("identity-b"), "{}");
    storage.setItem("unrelated", "preserve");
    clearAllChatSessions(storage);
    expect(storage.getItem(sessionStorageKey("identity-a"))).toBeNull();
    expect(storage.getItem(sessionStorageKey("identity-b"))).toBeNull();
    expect(storage.getItem("unrelated")).toBe("preserve");
  });

  it("keeps the send button accessible and exposes keyboard instructions", () => {
    const widget = source("components/chat-widget.tsx");
    expect(widget).toContain('aria-label="发送问题"');
    expect(widget).toContain("按 Enter");
    expect(widget).toContain("按 Space");
    expect(widget).toContain('aria-label="取消生成"');
    expect(widget).toContain("focus:ring-2");
  });

  it("renders unsupported references as non-clickable instead of raw routes", () => {
    const widget = source("components/chat-widget.tsx");
    expect(widget).toContain('aria-disabled="true"');
    expect(widget).toContain("来源暂不可打开");
    expect(widget).not.toContain("href={`/${reference.id}`}");
  });

  it("binds chat storage to login, expiry and logout auth events", () => {
    const gate = source("components/auth-gate.tsx");
    expect(gate).toContain("AUTH_SESSION_EVENT");
    expect(gate).toContain('reason: "login"');
    expect(gate).toContain('reason: "logout"');
    expect(gate).toContain('reason: "expired"');
    expect(gate).toContain("rotate: true");
  });

  it("guards terminal SSE state so late done cannot overwrite error/cancel", () => {
    const stream = source("lib/chat-stream.ts");
    expect(stream).toContain('terminal === "error" || terminal === "cancelled"');
    expect(stream).not.toContain("References are an intermediate retrieval result");
    const state = source("lib/chat-state.ts");
    expect(state).toContain("References are an intermediate retrieval result");
  });
});
