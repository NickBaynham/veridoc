import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

const DEMO_USER_KEY = "verifiedsignal_demo_user";

export interface DemoUser {
  email: string;
  name: string;
}

interface DemoAuthState {
  user: DemoUser | null;
  login: (email: string, _password: string) => void;
  logout: () => void;
}

const DemoAuthContext = createContext<DemoAuthState | null>(null);

function readStoredUser(): DemoUser | null {
  try {
    const raw = sessionStorage.getItem(DEMO_USER_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object") return null;
    const email = (parsed as { email?: string }).email;
    const name = (parsed as { name?: string }).name;
    if (typeof email !== "string" || typeof name !== "string") return null;
    return { email, name };
  } catch {
    return null;
  }
}

export function DemoAuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<DemoUser | null>(() =>
    typeof sessionStorage !== "undefined" ? readStoredUser() : null,
  );

  useEffect(() => {
    if (user) {
      sessionStorage.setItem(DEMO_USER_KEY, JSON.stringify(user));
    } else {
      sessionStorage.removeItem(DEMO_USER_KEY);
    }
  }, [user]);

  const login = useCallback((email: string, _password: string) => {
    const safe = email.trim() || "demo@verifiedsignal.io";
    setUser({
      email: safe,
      name: safe.split("@")[0].replace(/\./g, " "),
    });
  }, []);

  const logout = useCallback(() => setUser(null), []);

  const value = useMemo(
    () => ({
      user,
      login,
      logout,
    }),
    [user, login, logout],
  );

  return <DemoAuthContext.Provider value={value}>{children}</DemoAuthContext.Provider>;
}

export function useDemoAuth(): DemoAuthState {
  const ctx = useContext(DemoAuthContext);
  if (!ctx) {
    throw new Error("useDemoAuth must be used within DemoAuthProvider");
  }
  return ctx;
}
