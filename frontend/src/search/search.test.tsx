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
    is_new: runners === 1,
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

function groupResponse() {
  return json({
    root: { id: TRACK, title: "Набережная до маяка", author: AUTHOR },
    root_distance_m: 5200,
    runners: 2,
    rows: [
      {
        place: 1,
        runner: { id: "r1", name: "Ирина К.", avatar_url: null },
        track_id: "a1",
        time_s: 1421,
        pace_s_per_km: 273,
        date: null,
        beat: true,
        is_author: false,
        is_root: false,
        runs: 1,
        is_viewer: false,
      },
      {
        place: 2,
        runner: AUTHOR,
        track_id: TRACK,
        time_s: 1450,
        pace_s_per_km: 279,
        date: null,
        beat: false,
        is_author: true,
        is_root: true,
        runs: 1,
        is_viewer: false,
      },
    ],
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
    match: null,
    attempt_of: null,
    group_runners: 2,
    achievements: [],
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  tokenStore.set(null);
  mapProps.last = null;
  window.localStorage.clear();
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

  it("«Показать ещё» не просит у API больше 100 и прячется на пределе", async () => {
    const { fetchMock } = mockApi({
      "POST /auth/refresh": NO_SESSION,
      "GET /tracks/search": (req) => {
        const limit = Number(new URL(req.url).searchParams.get("limit"));
        if (limit > 100) return json({ detail: "limit" }, 422);
        const items = Array.from({ length: limit }, (_, i) => item(`t${i}`, `Маршрут ${i}`));
        return json({ total: 250, items, mode: "lines", clusters: [], lines: [] });
      },
    });
    renderApp("/");
    await screen.findByText("Маршрут 0");
    for (const expected of ["40", "60", "80", "100"]) {
      fireEvent.click(await screen.findByRole("button", { name: "Показать ещё" }));
      await waitFor(() =>
        expect(searchCalls(fetchMock).at(-1)?.searchParams.get("limit")).toBe(expected),
      );
    }
    expect(await screen.findByText("Маршрут 99")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Показать ещё" })).not.toBeInTheDocument();
    expect(searchCalls(fetchMock).every((u) => Number(u.searchParams.get("limit")) <= 100)).toBe(
      true,
    );
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
      [`GET /tracks/${TRACK}/group`]: groupResponse,
    });
    renderApp("/");
    fireEvent.click(await screen.findByText("Набережная до маяка"));
    expect(await screen.findByRole("heading", { name: "Набережная до маяка" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Скачать GPX" })).toBeInTheDocument();
    expect(await screen.findByText("Группа маршрута")).toBeInTheDocument();
    const irina = await screen.findByRole("link", { name: /Ирина К\./ });
    expect(irina).toHaveAttribute("href", "/tracks/a1");
    expect(irina.textContent).toContain("↗");
    expect(screen.getByText("превзошёл")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Проверить мою пробежку ↗" })).toHaveAttribute(
      "href",
      `/tracks/${TRACK}/check`,
    );
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

describe("Управление главной", () => {
  it("«Новые» — быстрый переключатель, уходит в запрос, новые помечены", async () => {
    const { fetchMock } = mockApi({
      "POST /auth/refresh": NO_SESSION,
      "GET /tracks/search": () => searchResponse(),
    });
    renderApp("/");
    await screen.findByText("Круг по парку");
    expect(screen.getByText("новый")).toBeInTheDocument(); // Круг по парку — новый
    fireEvent.click(screen.getByRole("button", { name: "Новые" }));
    await waitFor(() =>
      expect(searchCalls(fetchMock).at(-1)?.searchParams.get("is_new")).toBe("true"),
    );
    expect(screen.getByRole("button", { name: "Новые" })).toHaveAttribute("aria-pressed", "true");
  });

  it("«Сбросить» очищает фильтры, поиск и возвращает карту в исходную область", async () => {
    window.localStorage.setItem("runners.nearbyAnswer", "declined");
    const { fetchMock } = mockApi({
      "POST /auth/refresh": NO_SESSION,
      "GET /tracks/search": () => searchResponse(),
    });
    renderApp("/?lat=43.3&lon=132.1&z=10&cat=10&fresh=1&att=1&pmin=270&sort=pace");
    await screen.findByText("Набережная до маяка");
    fireEvent.click(screen.getByRole("button", { name: "Сбросить" }));
    await waitFor(() => {
      const last = searchCalls(fetchMock).at(-1) as URL;
      expect(last.searchParams.has("category")).toBe(false);
      expect(last.searchParams.has("is_new")).toBe(false);
      expect(last.searchParams.has("pace_min_s")).toBe(false);
      expect(last.searchParams.get("sort")).toBe("popular");
    });
    expect(mapProps.last?.flyTo).toMatchObject({ lat: 43.1155, lon: 131.8855, z: 12 });
    expect(screen.getByRole("button", { name: "10 км" })).toHaveAttribute("aria-pressed", "false");
  });

  it("список скрывается и показывается явной кнопкой", async () => {
    mockApi({ "POST /auth/refresh": NO_SESSION, "GET /tracks/search": () => searchResponse() });
    renderApp("/");
    await screen.findByText("Набережная до маяка");
    const toggle = screen.getByRole("button", { name: /Показать список/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(toggle);
    expect(screen.getByRole("button", { name: /Скрыть список/ })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });

  it("при первом заходе спрашивает про треки рядом; согласие переводит карту к бегуну", async () => {
    vi.stubGlobal("navigator", {
      ...navigator,
      geolocation: {
        getCurrentPosition: (ok: PositionCallback) =>
          ok({ coords: { latitude: 43.02, longitude: 131.89 } } as GeolocationPosition),
      },
    });
    mockApi({ "POST /auth/refresh": NO_SESSION, "GET /tracks/search": () => searchResponse() });
    renderApp("/");
    expect(
      await screen.findByRole("dialog", { name: "Показать треки рядом с вами?" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Показать" }));
    await waitFor(() =>
      expect(mapProps.last?.flyTo).toMatchObject({ lat: 43.02, lon: 131.89, z: 13 }),
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(window.localStorage.getItem("runners.nearbyAnswer")).toBe("accepted");
    expect(JSON.parse(window.localStorage.getItem("runners.homeView") ?? "{}")).toMatchObject({
      lat: 43.02,
    });
  });

  it("отказ запоминается: вопрос больше не показывается, карта во Владивостоке", async () => {
    mockApi({ "POST /auth/refresh": NO_SESSION, "GET /tracks/search": () => searchResponse() });
    const first = renderApp("/");
    fireEvent.click(await screen.findByRole("button", { name: "Не сейчас" }));
    expect(window.localStorage.getItem("runners.nearbyAnswer")).toBe("declined");
    first.unmount();
    renderApp("/");
    await screen.findByText("Набережная до маяка");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(mapProps.last?.initialView).toEqual({ lat: 43.1155, lon: 131.8855, z: 12 });
  });

  it("по ссылке с областью карты вопрос не задаётся", async () => {
    mockApi({ "POST /auth/refresh": NO_SESSION, "GET /tracks/search": () => searchResponse() });
    renderApp("/?lat=43.2&lon=131.95&z=14");
    await screen.findByText("Набережная до маяка");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

describe("Понятная навигация и фильтры", () => {
  it("Panel or page: «›» у пунктов списка, «↗» у ссылок на страницу", async () => {
    mockApi({
      "POST /auth/refresh": NO_SESSION,
      "GET /tracks/search": () => searchResponse(),
      [`GET /tracks/${TRACK}`]: () => json(detail()),
      [`GET /tracks/${TRACK}/group`]: groupResponse,
    });
    renderApp("/");
    const item = await screen.findByRole("button", { name: /Набережная до маяка/ });
    expect(item).toHaveAttribute("title", "Откроется здесь, рядом с картой");
    expect(item.textContent).toContain("›");
    fireEvent.click(item);
    expect(await screen.findByRole("link", { name: "Страница трека ↗" })).toHaveAttribute(
      "href",
      `/tracks/${TRACK}`,
    );
  });

  it("Custom resets category: «Своя» сбрасывает категорию и наоборот", async () => {
    const { fetchMock } = mockApi({
      "POST /auth/refresh": NO_SESSION,
      "GET /tracks/search": () => searchResponse(),
    });
    renderApp("/?cat=5");
    await screen.findByText("Набережная до маяка");
    expect(screen.getByRole("button", { name: "5 км" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "Своя" }));
    expect(screen.getByRole("button", { name: "5 км" })).toHaveAttribute("aria-pressed", "false");
    await waitFor(() =>
      expect(searchCalls(fetchMock).at(-1)?.searchParams.has("category")).toBe(false),
    );
    fireEvent.change(screen.getByLabelText("От, км"), { target: { value: "8" } });
    await waitFor(() =>
      expect(searchCalls(fetchMock).at(-1)?.searchParams.get("dist_min_km")).toBe("8"),
    );
    fireEvent.click(screen.getByRole("button", { name: "10 км" }));
    await waitFor(() => {
      const last = searchCalls(fetchMock).at(-1) as URL;
      expect(last.searchParams.get("category")).toBe("10");
      expect(last.searchParams.has("dist_min_km")).toBe(false);
    });
    expect(screen.queryByLabelText("От, км")).not.toBeInTheDocument();
  });

  it("Collapse filters: сворачиваются в строку со сводкой и разворачиваются", async () => {
    mockApi({ "POST /auth/refresh": NO_SESSION, "GET /tracks/search": () => searchResponse() });
    renderApp("/?cat=10&fresh=1");
    await screen.findByText("Набережная до маяка");
    fireEvent.click(screen.getByRole("button", { name: /Скрыть фильтры/ }));
    const compact = screen.getByRole("button", { name: /Фильтры/ });
    expect(compact).toHaveAttribute("aria-expanded", "false");
    expect(compact.textContent).toContain("10 км · +1");
    fireEvent.click(compact);
    expect(screen.getByRole("button", { name: /Фильтры/ })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });
});

describe("Выбор из списка", () => {
  it("подгоняет карту под трек; без выбора из списка рамка не меняется", async () => {
    mockApi({
      "POST /auth/refresh": NO_SESSION,
      "GET /tracks/search": () => searchResponse(),
      [`GET /tracks/${TRACK}`]: () => json(detail()),
      [`GET /tracks/${TRACK}/group`]: groupResponse,
    });
    renderApp("/");
    await screen.findByText("Набережная до маяка");
    expect(mapProps.last?.fitKey).toBe(0);
    fireEvent.click(screen.getByRole("button", { name: /Набережная до маяка/ }));
    await waitFor(() => expect(mapProps.last?.fitKey).toBeGreaterThan(0));
  });
});
