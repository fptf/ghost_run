import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { tokenStore } from "./auth/tokenStore";
import { mockApi, NO_SESSION } from "./test/mockApi";
import { renderApp } from "./test/renderApp";

vi.mock("./search/SearchMap", () => ({ SearchMap: () => <div data-testid="map" /> }));

afterEach(() => {
  vi.unstubAllGlobals();
  tokenStore.set(null);
});

describe("App smoke", () => {
  it("главная — карта маршрутов с фильтром дистанции и навигацией", async () => {
    mockApi({ "POST /auth/refresh": NO_SESSION });
    renderApp("/");
    expect(await screen.findByRole("heading", { name: "Карта маршрутов" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Дистанция" })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /Карта/ }).length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "Бегуны" })).toBeInTheDocument();
  });

  it("показывает 404 для неизвестного маршрута", async () => {
    mockApi({ "POST /auth/refresh": NO_SESSION });
    renderApp("/nope");
    expect(await screen.findByRole("heading", { name: "Страница не найдена" })).toBeInTheDocument();
  });
});
