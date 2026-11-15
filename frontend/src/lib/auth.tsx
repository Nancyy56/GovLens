import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, setUnauthorizedHandler, tokenStore } from "./api";
import type { Principal, Role } from "./types";

const RANK: Record<Role, number> = { VIEWER: 0, EDITOR: 1, ADMIN: 2 };

interface AuthState {
  user: Principal | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  can: (role: Role) => boolean;
}
const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Principal | null>(null);
  const [loading, setLoading] = useState(true);

  const reset = useCallback(() => { tokenStore.clear(); setUser(null); }, []);
  useEffect(() => { setUnauthorizedHandler(reset); }, [reset]);

  useEffect(() => {
    // Restore the session. With auth disabled on the server, /auth/me works without a token.
    api.me().then(setUser).catch(() => setUser(null)).finally(() => setLoading(false));
  }, []);

  const value = useMemo<AuthState>(() => ({
    user, loading,
    login: async (username, password) => {
      const res = await api.login(username, password);
      tokenStore.set(res.access_token);
      setUser(await api.me());
    },
    logout: async () => { try { await api.logout(); } catch { /* already expired */ } reset(); },
    can: (role) => !!user && RANK[user.role] >= RANK[role],
  }), [user, loading, reset]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth must be used inside AuthProvider");
  return v;
}
