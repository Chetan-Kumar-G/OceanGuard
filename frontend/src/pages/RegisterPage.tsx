import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../api/client";

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await register(email, password, displayName);
      navigate("/", { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) setError("An account with this email already exists.");
      else if (err instanceof ApiError && err.status === 422) setError("Check your email and use a password of at least 8 characters.");
      else setError("Could not reach the server.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={onSubmit}>
        <h1>🛢️ OceanGuard AI</h1>
        <p className="muted">
          Create an investigator account. The very first account registered on a fresh deployment becomes an admin.
        </p>

        <label>
          Name
          <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} required autoFocus />
        </label>
        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label>
          Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} />
        </label>

        {error && <p className="flag flag-warn">{error}</p>}

        <button type="submit" disabled={busy}>
          {busy ? "Creating account…" : "Create account"}
        </button>
        <p className="muted small">
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </form>
    </div>
  );
}
