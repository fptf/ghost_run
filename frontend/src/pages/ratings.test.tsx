import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { tokenStore } from "../auth/tokenStore";
import { json, mockApi, NO_SESSION } from "../test/mockApi";
import { renderApp } from "../test/renderApp";

afterEach(() => {
  vi.unstubAllGlobals();
  tokenStore.set(null);
});

function item(place: number, title: string, value: number) {
  return {
    place,
    track_id: `t${place}`,
    title,
    distance_m: 9900,
    total_time_s: 3600,
    avg_pace_s_per_km: 364,
    author: { id: "a", name: "Олег Т.", avatar_url: null },
    runners: 4,
    downloads: 3,
    value,
    computed_at: "2026-11-14T00:00:00Z",
  };
}

describe("Рейтинги", () => {
  it("вкладки категорий: по умолчанию 5 км, переключение на 10 км уходит в запрос", async () => {
    const { fetchMock } = mockApi({
      "POST /auth/refresh": NO_SESSION,
      "GET /ratings": (req) => {
        const cat = new URL(req.url).searchParams.get("category");
        return json(
          cat === "10"
            ? [item(1, "Большая десятка", 26), item(2, "Десятка по набережной", 10)]
            : [],
        );
      },
    });
    renderApp("/ratings");
    expect(await screen.findByText("В этой категории пока нет маршрутов.")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "5 км" })).toHaveAttribute("aria-selected", "true");
    fireEvent.click(screen.getByRole("tab", { name: "10 км" }));
    expect(await screen.findByText("Большая десятка")).toBeInTheDocument();
    expect(screen.getByText("26")).toBeInTheDocument();
    expect(screen.getAllByText("4 бегуна · 3 скачивания").length).toBe(2);
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([r]) =>
            new URL(r instanceof Request ? r.url : String(r), "http://localhost").searchParams.get(
              "category",
            ) === "10",
        ),
      ).toBe(true),
    );
    expect(screen.getByRole("link", { name: /Большая десятка/ })).toHaveAttribute(
      "href",
      "/tracks/t1",
    );
  });

  it("«Рейтинги» есть в навигации", async () => {
    mockApi({ "POST /auth/refresh": NO_SESSION, "GET /ratings": () => json([]) });
    renderApp("/ratings");
    const links = await screen.findAllByRole("link", { name: /Рейтинги/ });
    expect(links.some((l) => l.getAttribute("href") === "/ratings")).toBe(true);
  });
});
