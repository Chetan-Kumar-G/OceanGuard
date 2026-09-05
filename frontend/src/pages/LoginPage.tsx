import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ApiError, requestPasswordReset } from "../api/client";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation() as { state?: { from?: string } };
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [resetMessage, setResetMessage] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email, password);
      navigate(location.state?.from ?? "/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? "Incorrect email or password." : "Could not reach the server.");
    } finally {
      setBusy(false);
    }
  }

  async function onForgotPassword() {
    if (!email) {
      setError("Enter your email above first, then click “Forgot password”.");
      return;
    }
    setBusy(true);
    try {
      const res = await requestPasswordReset(email);
      setResetMessage(
        res.dev_reset_token
          ? `Dev mode (no email service configured): reset token is ${res.dev_reset_token}`
          : res.message,
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={onSubmit}>
        <h1>🛢️ OceanGuard AI</h1>
        <p className="muted">Sign in to the investigator dashboard.</p>

        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
        </label>
        <label>
          Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} />
        </label>

        {error && <p className="flag flag-warn">{error}</p>}
        {resetMessage && <p className="flag flag-ok small">{resetMessage}</p>}

        <button type="submit" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
        <button type="button" className="link-button" onClick={onForgotPassword} disabled={busy}>
          Forgot password?
        </button>

        <p className="muted small">
          No account? <Link to="/register">Register</Link>
        </p>
        <p className="muted small">
          Reporting something as a false positive?{" "}
          <Link to="/appeal">Submit a dispute</Link> — no account needed.
        </p>
      </form>
    </div>
  );
}
