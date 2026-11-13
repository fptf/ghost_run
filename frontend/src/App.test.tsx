import { QueryClient } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

function renderAt(path: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App queryClient={queryClient} />
    </MemoryRouter>,
  );
}

function mockFetch(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(JSON.stringify(body), {
          status,
          headers: { "Content-Type": "application/json" },
        }),
    ),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("App smoke", () => {
  it("рендерит главную на русском и показывает здоровый сервер", async () => {
    mockFetch(200, { status: "ok", checks: { db: "ok", redis: "ok", s3: "ok" } });
    renderAt("/");
    expect(screen.getByRole("heading", { name: "Бегуны" })).toBeInTheDocument();
    expect(await screen.findByText("всё работает")).toBeInTheDocument();
  });

  it("показывает проблему, если /health отвечает 503", async () => {
    mockFetch(503, { status: "error", checks: { db: "error", redis: "ok", s3: "ok" } });
    renderAt("/");
    expect(await screen.findByText("есть проблемы")).toBeInTheDocument();
  });

  it("показывает 404 для неизвестного маршрута", () => {
    mockFetch(200, {});
    renderAt("/nope");
    expect(screen.getByRole("heading", { name: "Страница не найдена" })).toBeInTheDocument();
  });
});
