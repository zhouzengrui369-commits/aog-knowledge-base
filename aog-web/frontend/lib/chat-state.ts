import type { ChatReference, ChatSection } from "@/lib/types";

export type ChatPhase =
  | "queued"
  | "retrieving"
  | "generating"
  | "done"
  | "error"
  | "cancelled";

export interface ChatMessageState {
  id: string;
  role: "user" | "assistant";
  text: string;
  phase?: ChatPhase;
  sections?: ChatSection[];
  references?: ChatReference[];
  model?: string;
  error?: string;
  truncated?: boolean;
  slow?: boolean;
  firstTokenMs?: number | null;
  latencyMs?: number | null;
  // R3 commit 8 (NJX 8/4 15:36 拍板): assistant 消息存原 user query, 给前端 query 卡片用
  query?: string;
}

export interface ChatSessionSnapshot {
  schema: 1;
  sessionId: string;
  savedAt: number;
  messages: ChatMessageState[];
  lastQuestion: string;
  lastVisitedReferenceId?: string | null;
}

export interface StorageLike {
  length: number;
  key(index: number): string | null;
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export const CHAT_SESSION_PREFIX = "aog_chat_session_v1:";
export const CHAT_SESSION_TTL_MS = 2 * 60 * 60 * 1000;

const TERMINAL = new Set<ChatPhase>(["done", "error", "cancelled"]);
const TRANSITIONS: Record<ChatPhase, ChatPhase[]> = {
  queued: ["retrieving", "error", "cancelled"],
  retrieving: ["generating", "error", "cancelled"],
  generating: ["done", "error", "cancelled"],
  done: [],
  error: [],
  cancelled: [],
};

export function isActivePhase(phase?: ChatPhase): boolean {
  return phase === "queued" || phase === "retrieving" || phase === "generating";
}

export function transitionChatPhase(current: ChatPhase, next: ChatPhase): ChatPhase {
  if (current === next) return current;
  if (!TRANSITIONS[current].includes(next)) {
    throw new Error(`invalid chat phase transition: ${current} -> ${next}`);
  }
  return next;
}

export function applyIntermediateReferences(
  message: ChatMessageState,
  references: ChatReference[],
  model?: string
): ChatMessageState {
  if (message.role !== "assistant") return message;
  // References are an intermediate retrieval result. They never create a
  // terminal phase and never imply that answer generation completed.
  return { ...message, references, model, slow: message.slow ?? false };
}

export function sessionStorageKey(sessionId: string): string {
  return `${CHAT_SESSION_PREFIX}${sessionId}`;
}

function serializableMessage(message: ChatMessageState): ChatMessageState {
  const phase = message.phase;
  if (phase && isActivePhase(phase)) {
    return {
      ...message,
      phase: "error",
      slow: false,
      error: "页面刷新中断了本次生成，请重试。",
    };
  }
  return {
    ...message,
    slow: false,
  };
}

export function saveChatSession(
  storage: StorageLike,
  snapshot: Omit<ChatSessionSnapshot, "schema" | "savedAt">,
  now = Date.now()
): void {
  const value: ChatSessionSnapshot = {
    schema: 1,
    sessionId: snapshot.sessionId,
    savedAt: now,
    messages: snapshot.messages.map(serializableMessage),
    lastQuestion: snapshot.lastQuestion,
    lastVisitedReferenceId: snapshot.lastVisitedReferenceId ?? null,
  };
  storage.setItem(sessionStorageKey(snapshot.sessionId), JSON.stringify(value));
}

export function loadChatSession(
  storage: StorageLike,
  sessionId: string,
  now = Date.now()
): ChatSessionSnapshot | null {
  const key = sessionStorageKey(sessionId);
  const raw = storage.getItem(key);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<ChatSessionSnapshot>;
    if (
      parsed.schema !== 1 ||
      parsed.sessionId !== sessionId ||
      typeof parsed.savedAt !== "number" ||
      !Array.isArray(parsed.messages)
    ) {
      storage.removeItem(key);
      return null;
    }
    if (now - parsed.savedAt > CHAT_SESSION_TTL_MS || now < parsed.savedAt) {
      storage.removeItem(key);
      return null;
    }
    const messages = parsed.messages.map((message) => serializableMessage(message));
    return {
      schema: 1,
      sessionId,
      savedAt: parsed.savedAt,
      messages,
      lastQuestion: String(parsed.lastQuestion || ""),
      lastVisitedReferenceId: parsed.lastVisitedReferenceId || null,
    };
  } catch {
    storage.removeItem(key);
    return null;
  }
}

export function clearChatSession(storage: StorageLike, sessionId: string): void {
  storage.removeItem(sessionStorageKey(sessionId));
}

export function clearAllChatSessions(storage: StorageLike): void {
  const keys: string[] = [];
  for (let index = 0; index < storage.length; index += 1) {
    const key = storage.key(index);
    if (key?.startsWith(CHAT_SESSION_PREFIX)) keys.push(key);
  }
  keys.forEach((key) => storage.removeItem(key));
}

export function isTerminalPhase(phase?: ChatPhase): boolean {
  return Boolean(phase && TERMINAL.has(phase));
}
