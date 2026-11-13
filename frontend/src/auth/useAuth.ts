import { createContext, useContext } from "react";

export type AuthStatus = "loading" | "guest" | "authenticated";

export interface AuthValue {
  status: AuthStatus;
  signIn: (accessToken: string) => void;
  signOut: () => Promise<void>;
  /** Сбросить сессию локально (например, после удаления аккаунта). */
  forget: () => void;
}

export const AuthContext = createContext<AuthValue | null>(null);

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth outside AuthProvider");
  return value;
}
