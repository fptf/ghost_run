import { fireEvent, screen, waitFor } from "@testing-library/react";
import { useEffect } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { tokenStore } from "../auth/tokenStore";
import { json, mockApi, NO_SESSION } from "../test/mockApi";
import { renderApp } from "../test/renderApp";
import type { SearchMapProps } from "./SearchMap";

const mapProps: { last: SearchMapProps | null } = { last: null };

vi.mock("./SearchMap", () => ({
  SearchMap: (props: SearchMapProps) => {
    mapProps.last = props;
    useEffect(() => {
      props.onViewChange({
        bbox: [131.8, 43.05, 131.97, 43.18],
        zoom: props.initialView.z,
        center: { lat: props.initialView.lat, lon: props.initialView.lon },
      });
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);
    return <div data-testid="map" />;
  },
}));
vi.mock("../components/TrackMap", () => ({ TrackMap: () => <div data-testid="track-map" /> }));

const TRACK = "33333333-3333-3333-3333-333333333333";
const AUTHOR = { id: "44444444-4444-4444-4444-444444444444", name: "Алексей П.", avatar_url: null };

function item(id: string, title: string, runners = 1) {
  return {
    id,
    title,
    distance_m: 5200,
    total_time_s: 24 * 60 + 10,
    avg_pace_s_per_km: 279,
    category: "5",
    started_at: "2026-11-02T07:00:00Z",
    author: AUTHOR,
    runners_count: runners,
    attempts_count: runners - 1,
    start: [131.9, 43.1],
  };
}

function searchResponse(
  items = [item(TRACK, "Набережная до маяка", 9), item("t2", "Круг по парку")],
) {
  return json({
    total: items.length,
    items,
    mode: "lines",
    clusters: [],
    lines: items.map((i) => ({
      id: i.id,
      coordinates: [
        [131.9, 43.1],
        [131.91, 43.11],
      ],
    })),
  });
}

function detail() {
  return {
    id: TRACK,
    status: "published",
    reject_reason: null,
    reject_message: null,
    visibility: "public",
    title: "Набережная до маяка",
    started_at: "2026-11-02T07:00:00Z",
    distance_m: 5200,
    total_time_s: 1450,
    avg_pace_s_per_km: 279,
    category: "5",
    created_at: "2026-11-02T08:00:00Z",
    description: null,
    moving_time_s: 1450,
    elevation_gain_m: 38,
    has_elevation: true,
    splits: [1, 2, 3, 4, 5].map((idx) => ({ idx, distance_m: 1000, time_s: 270 + idx })),
    author: AUTHOR,
    geometry: {
      type: "LineString",
      coordinates: [
        [131.9, 43.1],
        [131.91, 43.11],
      ],
    },
    photos: [],
    is_owner: false,
    owner: null,
    km_marks: [{ km: 1, lon: 131.905, lat: 43.105 }],
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  tokenStore.set(null);
  mapProps.last = null;
});

function searchCalls(fetchMock: ReturnType<typeof mockApi>["fetchMock"]): URL[] {
  return fetchMock.mock.calls
    .map(([input]) => new URL(input instanceof Request ? input.url : String(input)))
    .filter((u) => u.pathname.endsWith("/tracks/search"));
}

describe("Главная: поиск по карте", () => {
  it("по умолчанию — Владивосток, список маршрутов в области", async () => {
    mockApi({ "POST /auth/refresh": NO_SESSION, "GET /tracks/search": () => searchResponse() });
    renderApp("/");
    expect(await screen.findByText("Набережная до маяка")).toBeInTheDocument();
    expect(screen.getByText("2 маршрута в области")).toBeInTheDocument();
    expect(screen.getByText("9 бегунов в группе")).toBeInTheDocument();
    expect(screen.getByText("Пока только автор")).toBeInTheDocument();
    expect(screen.getAllByText("5,2 км · 24:10 · 4:39 /км").length).toBe(2);
    expect(mapProps.last?.initialView).toEqual({ lat: 43.1155, lon: 131.8855, z: 12 });
  });

  it("категория 5 км уходит в запрос и в адрес страницы", async () => {
    const { fetchMock } = mockApi({
      "POST /auth/refresh": NO_SESSION,
      "GET /tracks/search": () => searchResponse(),
    });
    renderApp("/");
    await screen.findByText("Набережная до маяка");
    fireEvent.click(screen.getByRole("button", { name: "5 км" }));
    await waitFor(() =>
      expect(searchCalls(fetchMock).at(-1)?.searchParams.get("category")).toBe("5"),
    );
    expect(screen.getByRole("button", { name: "5 км" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("от 3 до 7,5 км")).toBeInTheDocument();
    const last = searchCalls(fetchMock).at(-1) as URL;
    expect(last.searchParams.get("bbox")).toBe("131.80000,43.05000,131.97000,43.18000");
  });

  it("восстанавливает область и фильтры из адреса", async () => {
    const { fetchMock } = mockApi({
      "POST /auth/refresh": NO_SESSION,
      "GET /tracks/search": () => searchResponse(),
    });
    renderApp("/?lat=43.2&lon=131.95&z=14&cat=10&pmin=270&sort=pace");
    await screen.findByText("Набережная до маяка");
    expect(mapProps.last?.initialView).toEqual({ lat: 43.2, lon: 131.95, z: 14 });
    const last = searchCalls(fetchMock).at(-1) as URL;
    expect(last.searchParams.get("category")).toBe("10");
    expect(last.searchParams.get("pace_min_s")).toBe("270");
    expect(last.searchParams.get("sort")).toBe("pace");
    expect(screen.getByRole("combobox", { name: "Сортировка" })).toHaveValue("pace");
  });

  it("текстовый поиск ищет без области карты", async () => {
    const { fetchMock } = mockApi({
      "POST /auth/refresh": NO_SESSION,
      "GET /tracks/search": () => searchResponse([item(TRACK, "Набережная до маяка")]),
    });
    renderApp("/");
    await screen.findByText("Набережная до маяка");
    const box = screen.getByRole("searchbox", { name: "Маршрут, автор или город" });
    fireEvent.change(box, { target: { value: "Алексей" } });
    fireEvent.submit(box);
    await waitFor(() =>
      expect(searchCalls(fetchMock).at(-1)?.searchParams.get("q")).toBe("Алексей"),
    );
    expect(searchCalls(fetchMock).at(-1)?.searchParams.has("bbox")).toBe(false);
    expect(await screen.findByText("Найден 1 маршрут")).toBeInTheDocument();
  });

  it("клик по маршруту открывает карточку с GPX и местом под группу", async () => {
    mockApi({
      "POST /auth/refresh": NO_SESSION,
      "GET /tracks/search": () => searchResponse(),
      [`GET /tracks/${TRACK}`]: () => json(detail()),
    });
    renderApp("/");
    fireEvent.click(await screen.findByText("Набережная до маяка"));
    expect(await screen.findByRole("heading", { name: "Набережная до маяка" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Скачать GPX" })).toBeInTheDocument();
    expect(screen.getByText("Группа маршрута")).toBeInTheDocument();
    expect(mapProps.last?.selectedId).toBe(TRACK);
    fireEvent.click(screen.getByRole("button", { name: /К списку маршрутов/ }));
    expect(await screen.findByText("Круг по парку")).toBeInTheDocument();
  });

  it("«Показать на карте» выделяет трек и подгоняет карту", async () => {
    mockApi({
      "POST /auth/refresh": NO_SESSION,
      "GET /tracks/search": () => searchResponse(),
      [`GET /tracks/${TRACK}`]: () => json(detail()),
    });
    renderApp(`/?track=${TRACK}&fit=1`);
    await screen.findByRole("heading", { name: "Набережная до маяка" });
    await waitFor(() => expect(mapProps.last?.fitKey).toBe(1));
    expect(mapProps.last?.selectedId).toBe(TRACK);
    expect(mapProps.last?.selectedLine).toEqual(detail().geometry.coordinates);
  });
});

describe("Карточка трека", () => {
  it("скачивает GPX и ведёт на карту", async () => {
    const { fetchMock } = mockApi({
      "POST /auth/refresh": NO_SESSION,
      [`GET /tracks/${TRACK}`]: () => json(detail()),
      [`GET /tracks/${TRACK}/gpx`]: () =>
        new Response("<gpx/>", { headers: { "Content-Type": "application/gpx+xml" } }),
      "GET /tracks/search": () => searchResponse(),
    });
    URL.createObjectURL = vi.fn(() => "blob:gpx");
    URL.revokeObjectURL = vi.fn();
    renderApp(`/tracks/${TRACK}`);
    fireEvent.click(await screen.findByRole("button", { name: "Скачать GPX" }));
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([r]) => String((r as Request).url).endsWith("/gpx"))).toBe(
        true,
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Показать на карте" }));
    expect(await screen.findByRole("heading", { name: "Карта маршрутов" })).toBeInTheDocument();
  });
});
