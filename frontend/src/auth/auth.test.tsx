import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { json, mockApi, NO_SESSION } from "../test/mockApi";
import { renderApp } from "../test/renderApp";
import { safeNext } from "./next";
import { tokenStore } from "./tokenStore";

const ME = {
  id: "11111111-1111-1111-1111-111111111111",
  name: "Бегун",
  avatar_url: null,
  city: null,
  about: null,
  stats: { runs: 0, total_distance_m: 0, records: {} },
  email: "dev@example.com",
  role: "runner",
  home: null,
  hide_radius_m: null,
  new_attempts: 0,
};

afterEach(() => {
  vi.unstubAllGlobals();
  tokenStore.set(null);
});

describe("Return After Sign-in", () => {
  it("Guest starts upload: после входа гость попадает на экран загрузки", async () => {
    const { calls } = mockApi({
      "POST /auth/refresh": NO_SESSION,
      "GET /auth/config": () => json({ google_client_id: null, dev_login_enabled: true }),
      "POST /auth/dev-login": () =>
        json({ access_token: "token-1", token_type: "bearer", expires_in: 900, user_id: ME.id }),
    });
    renderApp("/");

    fireEvent.click(await screen.findByRole("button", { name: "Загрузить трек" }));
    expect(await screen.findByRole("heading", { name: "Вход" })).toBeInTheDocument();

    fireEvent.change(await screen.findByLabelText("Email"), {
      target: { value: "dev@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Имя"), { target: { value: "Бегун" } });
    fireEvent.click(screen.getByRole("button", { name: "Войти" }));

    expect(await screen.findByRole("heading", { name: "Загрузка трека" })).toBeInTheDocument();
    expect(calls).toContain("POST /auth/dev-login");
  });

  it("не уводит на внешний сайт через next", () => {
    expect(safeNext("/upload")).toBe("/upload");
    expect(safeNext("//evil.example.com")).toBe("/");
    expect(safeNext("https://evil.example.com")).toBe("/");
    expect(safeNext("/\\evil.example.com")).toBe("/");
    expect(safeNext(null)).toBe("/");
  });
});

describe("Сессия", () => {
  it("восстанавливает сессию по refresh-cookie и открывает защищённую страницу", async () => {
    mockApi({
      "POST /auth/refresh": () =>
        json({ access_token: "token-2", token_type: "bearer", expires_in: 900, user_id: ME.id }),
      "GET /me": (req) =>
        req.headers.get("Authorization") === "Bearer token-2"
          ? json(ME)
          : json({ detail: "Требуется вход" }, 401),
    });
    renderApp("/me");
    expect(await screen.findByRole("heading", { name: "Бегун" })).toBeInTheDocument();
    expect(screen.getByText("Вы ещё не загрузили ни одного трека.")).toBeInTheDocument();
  });

  it("после 401 обновляет токен и повторяет запрос", async () => {
    let refreshes = 0;
    mockApi({
      "POST /auth/refresh": () => {
        refreshes += 1;
        return json({
          access_token: `token-${refreshes}`,
          token_type: "bearer",
          expires_in: 900,
          user_id: ME.id,
        });
      },
      "GET /me": (req) =>
        req.headers.get("Authorization") === "Bearer token-2"
          ? json(ME)
          : json({ detail: "expired" }, 401),
    });
    renderApp("/me");
    expect(await screen.findByRole("heading", { name: "Бегун" })).toBeInTheDocument();
    await waitFor(() => expect(refreshes).toBe(2));
  });
});

describe("Настройки", () => {
  it("показывает причину отказа сервера для радиуса вне диапазона", async () => {
    mockApi({
      "POST /auth/refresh": () =>
        json({ access_token: "t", token_type: "bearer", expires_in: 900, user_id: ME.id }),
      "GET /me": () => json(ME),
      "PATCH /me": () => json({ detail: "Радиус скрытой зоны должен быть от 200 до 500 м" }, 422),
    });
    renderApp("/settings");
    fireEvent.change(await screen.findByLabelText("Широта"), { target: { value: "55.75" } });
    fireEvent.change(screen.getByLabelText("Долгота"), { target: { value: "37.61" } });
    fireEvent.change(screen.getByLabelText(/Радиус/), { target: { value: "100" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    expect(
      await screen.findByText("Радиус скрытой зоны должен быть от 200 до 500 м"),
    ).toBeInTheDocument();
  });
});
