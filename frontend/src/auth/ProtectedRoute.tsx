import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext";

export default function ProtectedRoute({ children, requireRole }: { children: ReactNode; requireRole?: "admin" }) {
  const { user, ready } = useAuth();

  if (!ready) return <div className="auth-loading">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (requireRole && user.role !== requireRole) return <Navigate to="/" replace />;
  return <>{children}</>;
}
