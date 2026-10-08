import { FormEvent, useEffect, useRef, useState } from "react";

import AdminUsers from "./AdminUsers";
import AdminProjects from "./AdminProjects";
import { ApiError, clearAccessToken, restoreSession, signIn, signOut, updatePassword, WorkspaceUser } from "./api";

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "Something went wrong. Please try again.";
}

function passwordIsStrong(password: string): boolean {
  return password.length >= 12 && /[a-z]/.test(password) && /[A-Z]/.test(password)
    && /\d/.test(password) && /[^A-Za-z0-9]/.test(password);
}

export default function App() {
  const [user, setUser] = useState<WorkspaceUser | null>(null);
  const [checkingSession, setCheckingSession] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [adminView, setAdminView] = useState<"people" | "projects">("people");
  const startedRestore = useRef(false);

  useEffect(() => {
    if (startedRestore.current) return;
    startedRestore.current = true;
    restoreSession().then(setUser).catch(() => clearAccessToken()).finally(() => setCheckingSession(false));
  }, []);

  async function handleSignIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setError("");
    setNotice("");
    setBusy(true);
    try {
      setUser(await signIn(String(form.get("email")).trim(), String(form.get("password"))));
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function handlePasswordChange(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const currentPassword = String(form.get("current-password"));
    const newPassword = String(form.get("new-password"));
    const confirmation = String(form.get("confirm-password"));
    setError("");
    setNotice("");
    if (!passwordIsStrong(newPassword)) {
      setError("Use at least 12 characters with an uppercase letter, lowercase letter, number, and symbol.");
      return;
    }
    if (newPassword !== confirmation) {
      setError("The new password and confirmation do not match.");
      return;
    }

    setBusy(true);
    try {
      const message = await updatePassword(currentPassword, newPassword);
      clearAccessToken();
      setUser(null);
      setNotice(`${message} Use your new password to continue.`);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function handleSignOut() {
    setError("");
    setNotice("");
    setBusy(true);
    try {
      await signOut();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setUser(null);
      setBusy(false);
    }
  }

  if (checkingSession) {
    return <main className="page-shell"><section className="auth-card loading-card" aria-live="polite">
      <Brand /><div className="loading-line" /><p className="muted-copy">Checking your workspace session…</p>
    </section></main>;
  }

  if (!user) {
    return <main className="page-shell"><section className="auth-card" aria-labelledby="login-title">
      <Brand />
      <p className="eyebrow">Club workspace</p>
      <h1 id="login-title">Welcome back.</h1>
      <p className="description">Sign in with the account provided by your Invictus Grid administrator.</p>
      {notice && <div className="notice-banner" role="status">{notice}</div>}
      {error && <div className="error-banner" role="alert">{error}</div>}
      <form className="auth-form" onSubmit={handleSignIn}>
        <label htmlFor="email">Email address</label>
        <input id="email" name="email" type="email" autoComplete="username" placeholder="you@example.com" required disabled={busy} />
        <label htmlFor="password">Password</label>
        <input id="password" name="password" type="password" autoComplete="current-password" required disabled={busy} />
        <button className="primary-button" type="submit" disabled={busy}>
          {busy ? <><span className="button-spinner" /> Signing in…</> : "Sign in"}
        </button>
      </form>
      <p className="footnote">Accounts are created by an administrator. Public sign-up is disabled.</p>
    </section></main>;
  }

  if (user.must_change_password) {
    return <main className="page-shell"><section className="auth-card" aria-labelledby="password-title">
      <Brand />
      <p className="eyebrow">Secure your account</p>
      <h1 id="password-title">Set a new password.</h1>
      <p className="description">Your administrator provided a temporary password. Choose a new one before continuing.</p>
      {error && <div className="error-banner" role="alert">{error}</div>}
      <form className="auth-form" onSubmit={handlePasswordChange}>
        <label htmlFor="current-password">Current password</label>
        <input id="current-password" name="current-password" type="password" autoComplete="current-password" required disabled={busy} />
        <label htmlFor="new-password">New password</label>
        <input id="new-password" name="new-password" type="password" autoComplete="new-password" minLength={12} required disabled={busy} />
        <p className="field-hint">At least 12 characters, including upper and lowercase letters, a number, and a symbol.</p>
        <label htmlFor="confirm-password">Confirm new password</label>
        <input id="confirm-password" name="confirm-password" type="password" autoComplete="new-password" minLength={12} required disabled={busy} />
        <button className="primary-button" type="submit" disabled={busy}>
          {busy ? <><span className="button-spinner" /> Updating…</> : "Update password"}
        </button>
      </form>
      <button className="text-button" type="button" onClick={handleSignOut} disabled={busy}>Sign out</button>
    </section></main>;
  }

  if (user.role === "ADMIN") {
    return adminView === "people"
      ? <AdminUsers admin={user} onNavigate={setAdminView} onSignOut={handleSignOut} signingOut={busy} />
      : <AdminProjects admin={user} onNavigate={setAdminView} onSignOut={handleSignOut} signingOut={busy} />;
  }

  return <main className="page-shell"><section className="auth-card signed-in-card" aria-labelledby="signed-in-title">
    <div className="signed-in-topline"><Brand /><button className="text-button" type="button" onClick={handleSignOut} disabled={busy}>Sign out</button></div>
    <p className="eyebrow">{user.role.toLowerCase()} workspace</p>
    <h1 id="signed-in-title">You’re signed in, {user.full_name.split(" ")[0]}.</h1>
    <p className="description">Your account is ready. Project and task views will appear here as they are added.</p>
    <div className="account-summary">
      <span className="avatar" aria-hidden="true">{user.full_name.trim().charAt(0).toUpperCase()}</span>
      <span><strong>{user.full_name}</strong><small>{user.email}</small></span>
      <span className="role-tag">{user.role}</span>
    </div>
    {error && <div className="error-banner" role="alert">{error}</div>}
  </section></main>;
}

function Brand() {
  return <div className="brand-lockup" aria-label="Invictus Grid Workspace">
    <span className="brand-mark" aria-hidden="true">IG</span>
    <span className="brand-name">INVICTUS <b>GRID</b></span>
  </div>;
}
