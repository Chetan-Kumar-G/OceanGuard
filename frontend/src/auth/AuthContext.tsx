import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { getMe, login as apiLogin, register as apiRegister, setAuthToken } from "../api/client";
import type { UserOut } from "../api/types";

const STORAGE_KEY = "oceanguard_token";

interface AuthContextValue {
  user: UserOut | null;
  token: string | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(STORAGE_KEY));
  const [user, setUser] = useState<UserOut | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setAuthToken(token);
    if (!token) {
      setUser(null);
      setReady(true);
      return;
    }
    getMe()
      .then(setUser)
      .catch(() => {
        // stored token is invalid/expired
        setToken(null);
        localStorage.removeItem(STORAGE_KEY);
        setUser(null);
      })
      .finally(() => setReady(true));
  }, [token]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await apiLogin(email, password);
    localStorage.setItem(STORAGE_KEY, res.access_token);
    setToken(res.access_token);
    setUser(res.user);
  }, []);

  const register = useCallback(async (email: string, password: string, displayName: string) => {
    const res = await apiRegister(email, password, displayName);
    localStorage.setItem(STORAGE_KEY, res.access_token);
    setToken(res.access_token);
    setUser(res.user);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setToken(null);
    setUser(null);
  }, []);

  const value = useMemo(() => ({ user, token, ready, login, register, logout }), [user, token, ready, login, register, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
