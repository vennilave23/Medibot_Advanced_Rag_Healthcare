"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import type { Role } from "@/lib/api";

export interface Session {
  username: string;
  role: Role;
  token: string;
}

interface SessionContextValue {
  session: Session | null;
  isLoading: boolean;
  login: (session: Session) => void;
  logout: () => void;
}

const SessionContext = createContext<SessionContextValue | undefined>(undefined);
const STORAGE_KEY = "medibot_session";

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // One-time hydration from localStorage on mount: `window` doesn't exist during SSR,
    // so this can't run as a lazy useState initializer -- it has to wait for the client
    // effect phase. That's the case react-hooks/set-state-in-effect's generic "don't derive
    // state in an effect" advice doesn't cover: syncing from an external store exactly once.
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (raw) setSession(JSON.parse(raw) as Session);
    } catch {
      // localStorage unavailable (private browsing, etc.) -- just start logged out
    } finally {
      setIsLoading(false);
    }
  }, []);

  function login(newSession: Session) {
    setSession(newSession);
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(newSession));
    } catch {
      // non-fatal: session still works for this tab via React state
    }
  }

  function logout() {
    setSession(null);
    try {
      window.localStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }
  }

  return (
    <SessionContext.Provider value={{ session, isLoading, login, logout }}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used within a SessionProvider");
  return ctx;
}
