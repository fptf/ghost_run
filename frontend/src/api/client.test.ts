import { afterEach, describe, expect, it, vi } from "vitest";

const TRACK_ID = "22222222-2222-2222-2222-222222222222";
const TRACK = `/tracks/${TRACK_ID}`;

/** Свежая загрузка страницы: модули токена и клиента без восстановленной сессии. */
async function freshPage() {
  vi.resetModules();
  const { api } = await import("./client");
  return api;
}

function server(refreshStatus: number) {
  const calls: string[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const req = input instanceof Request ? input : new Request(input, init);
    const path = new URL(req.url).pathname.replace(/^\/api/, "");
    calls.push(`${req.method} ${path} ${req.headers.get("Authorization") ?? "-"}`);
    if (path === "/auth/refresh") {
      await new Promise((r) => setTimeout(r, 10)); // ответ приходит не сразу
      return refreshStatus === 200
        ? new Response(JSON.stringify({ access_token: "tok" }), { status: 200 })
        : new Response(JSON.stringify({ detail: "Нет сессии" }), { status: refreshStatus });
    }
    // Приватный трек для гостя выглядит отсутствующим.
    return req.headers.get("Authorization") === "Bearer tok"
      ? new Response(JSON.stringify({ id: "x" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      : new Response(JSON.stringify({ detail: "Not Found" }), { status: 404 });
  });
  vi.stubGlobal("fetch", fetchMock);
  return calls;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe("Восстановление сессии при загрузке страницы", () => {
  it("первый запрос ждёт начальный refresh и уходит с токеном", async () => {
    const calls = server(200);
    const api = await freshPage();
    const { data, response } = await api.GET("/tracks/{track_id}", {
      params: { path: { track_id: TRACK_ID } },
    });
    expect(response.status).toBe(200);
    expect(data).toMatchObject({ id: "x" });
    expect(calls).toEqual(["POST /auth/refresh -", `GET ${TRACK} Bearer tok`]);
  });

  it("гость ждёт один refresh на все запросы, без повторов", async () => {
    const calls = server(401);
    const api = await freshPage();
    const get = () =>
      api.GET("/tracks/{track_id}", {
        params: { path: { track_id: TRACK_ID } },
      });
    const [a, b] = await Promise.all([get(), get()]);
    expect(a.response.status).toBe(404);
    expect(b.response.status).toBe(404);
    await get();
    expect(calls.filter((c) => c.startsWith("POST /auth/refresh"))).toHaveLength(1);
    expect(calls.filter((c) => c.startsWith("GET"))).toEqual([
      `GET ${TRACK} -`,
      `GET ${TRACK} -`,
      `GET ${TRACK} -`,
    ]);
  });
});
