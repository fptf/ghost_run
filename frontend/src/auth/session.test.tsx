import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "./AuthContext";
import { tokenStore } from "./tokenStore";
import { useAuth } from "./useAuth";

/** Сервер с одноразовым refresh-токеном: повтор старого — 401 (сессия отозвана). */
function rotatingServer() {
  let current = 1;
  let cookie = 1; // общая для всех вкладок cookie браузера
  const statuses: number[] = [];
  const fetchMock = vi.fn(async () => {
    const sent = cookie; // cookie берётся в момент отправки запроса
    await new Promise((r) => setTimeout(r, 5));
    if (sent !== current) {
      statuses.push(401);
      return new Response(JSON.stringify({ detail: "reuse" }), { status: 401 });
    }
    current += 1;
    cookie = current; // Set-Cookie с новым токеном
    statuses.push(200);
    return new Response(JSON.stringify({ access_token: `token-${current}` }), { status: 200 });
  });
  return { fetchMock, statuses };
}

/** Web Locks в пределах «браузера»: один замок на имя, колбэки по очереди. */
function fakeLocks() {
  const tails = new Map<string, Promise<unknown>>();
  const names: string[] = [];
  return {
    names,
    request(name: string, callback: () => Promise<unknown>) {
      names.push(name);
      const run = (tails.get(name) ?? Promise.resolve()).then(() => callback());
      tails.set(
        name,
        run.catch(() => undefined),
      );
      return run;
    },
  };
}

async function twoTabs() {
  vi.resetModules();
  const tab1 = await import("./tokenStore");
  vi.resetModules();
  const tab2 = await import("./tokenStore");
  return [tab1, tab2] as const;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
  tokenStore.set(null);
});

describe("Обновление токена в нескольких вкладках", () => {
  it("без блокировки две вкладки сжигают refresh-токен дважды", async () => {
    const { fetchMock, statuses } = rotatingServer();
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("navigator", { ...navigator, locks: undefined });
    const [tab1, tab2] = await twoTabs();
    await Promise.all([tab1.refreshAccessToken(), tab2.refreshAccessToken()]);
    expect(statuses).toEqual([200, 401]);
  });

  it("с Web Locks вкладки обновляют по очереди и обе получают токен", async () => {
    const { fetchMock, statuses } = rotatingServer();
    const locks = fakeLocks();
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("navigator", { ...navigator, locks });
    const [tab1, tab2] = await twoTabs();
    const tokens = await Promise.all([tab1.refreshAccessToken(), tab2.refreshAccessToken()]);
    expect(statuses).toEqual([200, 200]);
    expect(tokens).toEqual(["token-2", "token-3"]);
    expect(locks.names).toEqual(["auth-refresh", "auth-refresh"]);
  });

  it("внутри вкладки параллельные вызовы делят один запрос", async () => {
    const { fetchMock } = rotatingServer();
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("navigator", { ...navigator, locks: fakeLocks() });
    const [tab] = await twoTabs();
    await Promise.all([tab.refreshAccessToken(), tab.refreshAccessToken()]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("Выход", () => {
  it("очищает весь кэш запросов, а не только профиль", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ detail: "no" }), { status: 401 })),
    );
    const queryClient = new QueryClient();
    queryClient.setQueryData(["me"], { name: "Анна" });
    queryClient.setQueryData(["my-tracks"], [{ id: "t1" }]);
    queryClient.setQueryData(["track", "t1"], { id: "t1" });

    function SignOut() {
      const { forget } = useAuth();
      return (
        <button type="button" onClick={forget}>
          выйти
        </button>
      );
    }
    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <SignOut />
        </AuthProvider>
      </QueryClientProvider>,
    );
    await act(async () => screen.getByRole("button", { name: "выйти" }).click());
    expect(queryClient.getQueryCache().getAll()).toHaveLength(0);
    expect(tokenStore.get()).toBeNull();
  });
});
