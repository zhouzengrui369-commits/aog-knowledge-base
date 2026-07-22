"use client";

/**
 * AuthGate - Sprint A 本地优先 (sprint-a-auth)
 *
 * 用法: 在 app/layout.tsx 包整个 SPA:
 *   <body>
 *     <AuthGate>{children}</AuthGate>
 *   </body>
 *
 * 行为:
 * - 读 localStorage.aog_token, 有则 verify; 失败清 token
 * - 未登录显示密码输入页 (居中卡片)
 * - 输密码 → POST /api/auth/login → 存 token → 渲染 children
 * - 成功登录后用 token 写到 fetch header (lib/api.ts 后续要 enforce 时调 getToken)
 * - 24h JWT 过期由后端 /api/auth/verify 在每次 mount + 路由切换时校验
 *
 * MVP 简化: 密码明文比 + 单 viewer 角色. 生产前改 hash + role-based.
 */
import * as React from "react";
import { Loader2, Lock, ShieldCheck, AlertTriangle } from "lucide-react";
import styles from "./auth-gate.module.css";

const TOKEN_KEY = "aog_token";
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

// === token helpers (供 lib/api.ts 后续 reuse) ===
export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* quota / privacy mode - swallow */
  }
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* swallow */
  }
}

export default function AuthGate({ children }: { children: React.ReactNode }) {
  const [token, setTokenState] = React.useState<string | null>(null);
  // status: "checking" (mount 时 verify) | "unauth" | "authed"
  const [status, setStatus] = React.useState<"checking" | "unauth" | "authed">(
    "checking",
  );
  const [password, setPassword] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const passwordRef = React.useRef<HTMLInputElement | null>(null);

  // 暴露 token 给 lib/api.ts (MVP 不强制, 等 NJX 后续要 enforce)
  React.useEffect(() => {
    if (token) {
      setToken(token);
    } else {
      clearToken();
    }
  }, [token]);

  // mount: 有 token 就 verify
  React.useEffect(() => {
    const t = getToken();
    if (!t) {
      setStatus("unauth");
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`${API_BASE}/api/auth/verify`, {
          headers: { Authorization: `Bearer ${t}` },
        });
        if (cancelled) return;
        if (r.ok) {
          const j = await r.json();
          if (j?.ok && j?.valid) {
            setTokenState(t);
            setStatus("authed");
            return;
          }
        }
        // invalid → 清 token, 进 unauth
        clearToken();
        setStatus("unauth");
      } catch (err) {
        // 网络失败 / 后端未起 — 让用户重新输密码, 视作未登录
        if (cancelled) return;
        console.warn("[auth-gate] verify failed:", err);
        clearToken();
        setStatus("unauth");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // unauth 时 auto focus
  React.useEffect(() => {
    if (status === "unauth") {
      // microtask 等渲染
      const t = setTimeout(() => passwordRef.current?.focus(), 50);
      return () => clearTimeout(t);
    }
  }, [status]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!password || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const r = await fetch(`${API_BASE}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      if (r.status === 401) {
        setError("密码错误，请重试");
        setPassword("");
        passwordRef.current?.focus();
        return;
      }
      if (!r.ok) {
        setError(`登录失败 (HTTP ${r.status})`);
        return;
      }
      const j = await r.json();
      if (!j?.ok || !j?.token) {
        setError("登录响应异常，请稍后再试");
        return;
      }
      setTokenState(j.token);
      setStatus("authed");
      setPassword("");
    } catch (err) {
      console.warn("[auth-gate] login failed:", err);
      setError(
        err instanceof Error
          ? `无法连接服务: ${err.message}`
          : "无法连接服务",
      );
    } finally {
      setSubmitting(false);
    }
  }

  // === 渲染 ===
  if (status === "checking") {
    return (
      <div className={styles.checkingWrap}>
        <Loader2 className={styles.spin} size={20} />
        <span className={styles.checkingText}>正在校验登录态…</span>
      </div>
    );
  }

  if (status === "unauth") {
    return (
      <div className={styles.gate}>
        <div className={styles.card}>
          <div className={styles.iconWrap}>
            <Lock size={28} className={styles.icon} />
          </div>
          <h1 className={styles.title}>AOG 应急保障知识库</h1>
          <p className={styles.subtitle}>请输入访问密码继续</p>

          <form onSubmit={handleSubmit} className={styles.form}>
            <input
              ref={passwordRef}
              type="password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                if (error) setError(null);
              }}
              placeholder="访问密码"
              className={styles.input}
              disabled={submitting}
              autoComplete="current-password"
              spellCheck={false}
              aria-label="访问密码"
            />

            {error && (
              <div className={styles.error} role="alert">
                <AlertTriangle size={14} />
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              className={styles.submit}
              disabled={!password || submitting}
            >
              {submitting ? (
                <>
                  <Loader2 size={16} className={styles.spin} />
                  <span>登录中…</span>
                </>
              ) : (
                <>
                  <ShieldCheck size={16} />
                  <span>登录</span>
                </>
              )}
            </button>
          </form>

          <p className={styles.hint}>
            24 小时有效期内自动保持登录态
          </p>
        </div>
      </div>
    );
  }

  // authed
  return <>{children}</>;
}
