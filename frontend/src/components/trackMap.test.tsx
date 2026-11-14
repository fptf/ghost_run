import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { tokenStore } from "../auth/tokenStore";
import { json, mockApi } from "../test/mockApi";
import { renderApp } from "../test/renderApp";
import { TrackMap } from "./TrackMap";

const maps = vi.hoisted(() => ({
  options: [] as { center?: [number, number]; zoom?: number }[],
  markers: [] as (string | null)[],
}));

vi.mock("maplibre-gl", () => {
  class Map {
    constructor(options: { center?: [number, number]; zoom?: number }) {
      maps.options.push(options);
    }
    addControl() {}
    on() {}
    once() {}
    resize() {}
    remove() {}
  }
  class Marker {
    constructor({ element }: { element: HTMLElement }) {
      maps.markers.push(element.getAttribute("aria-label"));
    }
    setLngLat() {
      return this;
    }
    addTo() {
      return this;
    }
  }
  class NavigationControl {
    readonly kind = "nav";
  }
  return { Map, Marker, NavigationControl, setWorkerUrl: () => undefined };
});

const ME_ID = "11111111-1111-1111-1111-111111111111";
const ROOT = "55555555-5555-5555-5555-555555555555";
const MINE = "66666666-6666-6666-6666-666666666666";
const LINE = [
  [131.9, 43.1],
  [131.91, 43.11],
];

function track(id: string, over: Record<string, unknown> = {}) {
  return {
    id,
    status: "published",
    reject_reason: null,
    reject_message: null,
    visibility: "public",
    title: "Набережная до маяка",
    started_at: "2026-11-12T08:00:00Z",
    distance_m: 5200,
    total_time_s: 1450,
    avg_pace_s_per_km: 279,
    category: "5",
    created_at: "2026-11-12T09:00:00Z",
    description: null,
    moving_time_s: 1450,
    elevation_gain_m: 30,
    has_elevation: true,
    splits: [],
    author: { id: ME_ID, name: "Анна", avatar_url: null },
    geometry: { type: "LineString", coordinates: LINE },
    photos: [],
    is_owner: false,
    owner: null,
    km_marks: [],
    match: null,
    attempt_of: null,
    group_runners: 0,
    achievements: [],
    attempt_root_id: null,
    is_attempt: false,
    ...over,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  tokenStore.set(null);
  maps.options.length = 0;
  maps.markers.length = 0;
});

describe("TrackMap", () => {
  it("подписи маркеров — из словаря", () => {
    render(
      <TrackMap
        line={LINE}
        label="карта"
        check={{ corridor: null, mine: null, deviation: { lon: 131.9, lat: 43.1 } }}
      />,
    );
    expect(maps.markers).toEqual(["Место схода", "Старт", "Финиш"]);
  });

  it("без линий открывается на исходной области главной карты, а не на Москве", () => {
    render(<TrackMap line={null} label="карта" />);
    expect(maps.options[0]).toMatchObject({ center: [131.8855, 43.1155], zoom: 12 });
  });

  it("на экране проверки карта не пересоздаётся при новых рендерах страницы", async () => {
    let runs = [track(MINE, { title: "Вечерняя набережная" })];
    mockApi({
      "POST /auth/refresh": () =>
        json({ access_token: "t", token_type: "bearer", expires_in: 900, user_id: ME_ID }),
      "GET /me": () => json({ id: ME_ID, name: "Анна" }),
      [`GET /tracks/${ROOT}`]: () => json(track(ROOT)),
      "GET /me/tracks": () => json(runs),
      [`POST /tracks/${ROOT}/check`]: () =>
        json({
          matched: true,
          route: { id: ROOT, title: "Набережная до маяка", author: { id: ME_ID, name: "Анна" } },
          track_id: MINE,
          track_title: "Вечерняя набережная",
          track_started_at: "2026-11-12T08:00:00Z",
          rules: [],
          deviation: null,
          result_time_s: 1400,
          diff_s: -50,
          route_line: { type: "LineString", coordinates: LINE },
          corridor: null,
          track_line: { type: "LineString", coordinates: LINE },
        }),
    });
    const { queryClient } = renderApp(`/tracks/${ROOT}/check`);
    fireEvent.click(await screen.findByText("Вечерняя набережная"));
    expect(await screen.findByRole("heading", { name: "Маршрут совпал" })).toBeInTheDocument();
    expect(maps.options).toHaveLength(1);

    // Список пробежек обновился — страница перерисовывается, карта остаётся той же.
    runs = [...runs, track("77777777-7777-7777-7777-777777777777", { title: "Утренняя" })];
    await act(() => queryClient.invalidateQueries({ queryKey: ["my-tracks"] }));
    await act(() => new Promise((r) => setTimeout(r, 20)));
    expect(maps.options).toHaveLength(1);
  });
});
