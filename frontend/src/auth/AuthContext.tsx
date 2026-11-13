import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { api } from "../api/client";
import { refreshAccessToken, tokenStore } from "./tokenStore";
import { AuthContext } from "./useAuth";
import type { AuthStatus } from "./useAuth";

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<AuthStatus>("loading");

  useEffect(() => {
    const unsubscribe = tokenStore.subscribe((token) =>
      setStatus(token ? "authenticated" : "guest"),
    );
    // Восстанавливаем сессию по refresh-cookie.
    void refreshAccessToken();
    return () => {
      unsubscribe();
    };
  }, []);

  const signIn = useCallback((accessToken: string) => tokenStore.set(accessToken), []);

  const forget = useCallback(() => {
    tokenStore.set(null);
    queryClient.removeQueries({ queryKey: ["me"] });
  }, [queryClient]);

  const signOut = useCallback(async () => {
    await api.POST("/auth/logout");
    forget();
  }, [forget]);

  const value = useMemo(
    () => ({ status, signIn, signOut, forget }),
    [status, signIn, signOut, forget],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
