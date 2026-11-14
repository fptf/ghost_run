import { fireEvent, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { tokenStore } from "../auth/tokenStore";
import { json, mockApi } from "../test/mockApi";
import { renderApp } from "../test/renderApp";

const ME = {
  id: "11111111-1111-1111-1111-111111111111",
  name: "Анна",
  avatar_url: null,
  city: null,
  about: null,
  stats: { runs: 0, total_distance_m: 0, records: {} },
  email: "a@example.com",
  role: "runner",
  home: null,
  hide_radius_m: null,
  new_attempts: 0,
};
const SESSION = () =>
  json({ access_token: "t", token_type: "bearer", expires_in: 900, user_id: ME.id });

afterEach(() => {
  vi.unstubAllGlobals();
  tokenStore.set(null);
});

describe("Настройки профиля", () => {
  it("после сохранения форма закрывается и открывается профиль", async () => {
    mockApi({
      "POST /auth/refresh": SESSION,
      "GET /me": () => json(ME),
      "GET /me/tracks": () => json([]),
      "PATCH /me": () => json({ ...ME, city: "Владивосток" }),
    });
    renderApp("/settings");
    fireEvent.change(await screen.findByLabelText("Город"), { target: { value: "Владивосток" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Сохранено");
    expect(screen.queryByLabelText("Город")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Анна" })).toBeInTheDocument();
  });

  it("«Назад» уходит из настроек без сохранения", async () => {
    const { calls } = mockApi({
      "POST /auth/refresh": SESSION,
      "GET /me": () => json(ME),
      "GET /me/tracks": () => json([]),
    });
    renderApp("/settings");
    fireEvent.change(await screen.findByLabelText("Город"), { target: { value: "Москва" } });
    fireEvent.click(screen.getByRole("button", { name: "Назад" }));
    expect(await screen.findByRole("heading", { name: "Анна" })).toBeInTheDocument();
    expect(calls).not.toContain("PATCH /me");
  });

  it("ошибка сохранения показывается, форма остаётся", async () => {
    mockApi({
      "POST /auth/refresh": SESSION,
      "GET /me": () => json(ME),
      "PATCH /me": () => json({ detail: "Слишком длинное имя" }, 400),
    });
    renderApp("/settings");
    fireEvent.click(await screen.findByRole("button", { name: "Сохранить" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Слишком длинное имя");
    expect(screen.getByLabelText("Город")).toBeInTheDocument();
  });

  it("неудачное удаление аккаунта сообщает об ошибке и не выходит", async () => {
    mockApi({
      "POST /auth/refresh": SESSION,
      "GET /me": () => json(ME),
      "DELETE /me": () => new Response(null, { status: 500 }),
    });
    renderApp("/settings");
    fireEvent.click(await screen.findByRole("button", { name: "Удалить аккаунт" }));
    fireEvent.click(screen.getByRole("button", { name: "Да, удалить навсегда" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Не удалось удалить аккаунт");
    expect(tokenStore.get()).toBe("t");
  });
});
