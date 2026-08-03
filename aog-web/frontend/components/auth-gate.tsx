"use client";

import * as React from "react";
import { AlertTriangle, Loader2, Lock, ShieldCheck } from "lucide-react";
import { clearAllChatSessions } from "@/lib/chat-state";
import styles from "./auth-gate.module.css";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000").replace(/\/api\/?$/, "");
const SESSION_MARKER = "aog_session_verified";
export const AUTH_SESSION_ID_KEY = "aog_auth_session_id";
export const AUTH_SESSION_EVENT = "aog:auth-session";

interface AuthSessionEventDetail {
  sessionId: string | null;
  reason: "verified" | "login" | "logout" | "expired" | "invalid" | "missing";
}

function createSessionId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `session-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function emitAuthSession(detail: AuthSessionEventDetail) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent<AuthSessionEventDetail>(AUTH_SESSION_EVENT, { detail }));
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.sessionStorage.getItem(SESSION_MARKER) === "true" ? "httpOnly-cookie" : null;
}

export function getAuthSessionId(): string | null {
  if (typeof window === "undefined") return null;
  return window.sessionStorage.getItem(AUTH_SESSION_ID_KEY);
}

function markVerified(
  value: boolean,
  options: { rotate?: boolean; reason?: AuthSessionEventDetail["reason"] } = {}
) {
  if (typeof window === "undefined") return;
  if (value) {
    if (options.rotate) clearAllChatSessions(window.sessionStorage);
    window.sessionStorage.setItem(SESSION_MARKER, "true");
    let sessionId = options.rotate ? null : window.sessionStorage.getItem(AUTH_SESSION_ID_KEY);
    if (!sessionId) {
      sessionId = createSessionId();
      window.sessionStorage.setItem(AUTH_SESSION_ID_KEY, sessionId);
    }
    emitAuthSession({ sessionId, reason: options.reason || "verified" });
  } else {
    clearAllChatSessions(window.sessionStorage);
    window.sessionStorage.removeItem(SESSION_MARKER);
    window.sessionStorage.removeItem(AUTH_SESSION_ID_KEY);
    emitAuthSession({ sessionId: null, reason: options.reason || "invalid" });
  }
}

export default function AuthGate({ children }: { children: React.ReactNode }) {
  if (process.env.NEXT_PUBLIC_DISABLE_AUTH === "1") return <>{children}</>;

  const [status, setStatus] = React.useState<"checking" | "unauth" | "authed" | "offline">("checking");
  const [password, setPassword] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const passwordRef = React.useRef<HTMLInputElement>(null);

  const verify = React.useCallback(async () => {
    setStatus("checking");
    try {
      const response = await fetch(`${API_BASE}/api/auth/verify`, {
        credentials: "include",
        cache: "no-store",
      });
      const body = response.ok ? await response.json() : null;
      if (body?.valid) {
        markVerified(true, { reason: "verified" });
        setStatus("authed");
      } else {
        const reason = body?.reason === "expired" ? "expired" : body?.reason === "missing" ? "missing" : "invalid";
        markVerified(false, { reason });
        setStatus("unauth");
      }
    } catch {
      // A transient network failure preserves both the httpOnly cookie and the
      // session namespace. It does not expose or duplicate credentials.
      setStatus("offline");
    }
  }, []);

  React.useEffect(() => {
    verify();
  }, [verify]);

  React.useEffect(() => {
    const logout = async () => {
      try {
        await fetch(`${API_BASE}/api/auth/logout`, {
          method: "POST",
          credentials: "include",
        });
      } finally {
        markVerified(false, { reason: "logout" });
        setStatus("unauth");
      }
    };
    window.addEventListener("aog:logout", logout);
    return () => window.removeEventListener("aog:logout", logout);
  }, []);

  React.useEffect(() => {
    if (status === "unauth") {
      const timer = window.setTimeout(() => passwordRef.current?.focus(), 50);
      return () => window.clearTimeout(timer);
    }
  }, [status]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!password || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/auth/login`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      if (response.status === 401) {
        setError("密码错误，请重试");
        setPassword("");
        return;
      }
      if (!response.ok) {
        setError(`登录失败（HTTP ${response.status}）`);
        return;
      }
      // A successful login rotates the namespace so a prior identity/session
      // can never recover its chat context.
      markVerified(true, { rotate: true, reason: "login" });
      setPassword("");
      setStatus("authed");
    } catch {
      setError("无法连接服务，请检查网络后重试");
    } finally {
      setSubmitting(false);
    }
  }

  if (status === "authed") return <>{children}</>;

  if (status === "checking") {
    return (
      <div className={styles.checkingWrap}>
        <Loader2 className={styles.spin} size={20} />
        <span className={styles.checkingText}>正在校验登录态…</span>
      </div>
    );
  }

  if (status === "offline") {
    return (
      <div className={styles.gate}>
        <div className={styles.card}>
          <AlertTriangle size={28} className={styles.icon} />
          <h1 className={styles.title}>暂时无法连接 AOG 服务</h1>
          <p className={styles.subtitle}>登录凭据和当前会话命名空间未被清除，服务恢复后可直接重试。</p>
          <button type="button" className={styles.submit} onClick={verify}>重新连接</button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.gate}>
      <div className={styles.card}>
        <div className={styles.iconWrap}><Lock size={28} className={styles.icon} /></div>
        <h1 className={styles.title}>AOG 应急保障知识库</h1>
        <p className={styles.subtitle}>请输入访问密码继续</p>
        <form onSubmit={submit} className={styles.form}>
          <input
            ref={passwordRef}
            type="password"
            value={password}
            onChange={(event) => { setPassword(event.target.value); setError(null); }}
            placeholder="访问密码"
            className={styles.input}
            disabled={submitting}
            autoComplete="current-password"
            aria-label="访问密码"
          />
          {error && <div className={styles.error} role="alert"><AlertTriangle size={14} />{error}</div>}
          <button type="submit" className={styles.submit} disabled={!password || submitting}>
            {submitting ? <Loader2 size={16} className={styles.spin} /> : <ShieldCheck size={16} />}
            <span>{submitting ? "登录中…" : "登录"}</span>
          </button>
        </form>
        <p className={styles.hint}>登录态使用 httpOnly Cookie 保存；登出、过期或新身份登录时会清理本标签页的 AI 会话。</p>
      </div>
    </div>
  );
}
