import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { tokenStore } from "./auth/tokenStore";
import { HEALTH_OK, json, mockApi, NO_SESSION } from "./test/mockApi";
import { renderApp } from "./test/renderApp";

afterEach(() => {
  vi.unstubAllGlobals();
  tokenStore.set(null);
});

describe("App smoke", () => {
  it("рендерит главную на русском и показывает здоровый сервер", async () => {
    mockApi({ "GET /health": HEALTH_OK, "POST /auth/refresh": NO_SESSION });
    renderApp("/");
    expect(screen.getByRole("heading", { name: "Бегуны" })).toBeInTheDocument();
    expect(await screen.findByText("всё работает")).toBeInTheDocument();
  });

  it("показывает проблему, если /health отвечает 503", async () => {
    mockApi({
      "GET /health": () =>
        json({ status: "error", checks: { db: "error", redis: "ok", s3: "ok" } }, 503),
      "POST /auth/refresh": NO_SESSION,
    });
    renderApp("/");
    expect(await screen.findByText("есть проблемы")).toBeInTheDocument();
  });

  it("показывает 404 для неизвестного маршрута", () => {
    mockApi({ "POST /auth/refresh": NO_SESSION });
    renderApp("/nope");
    expect(screen.getByRole("heading", { name: "Страница не найдена" })).toBeInTheDocument();
  });
});
