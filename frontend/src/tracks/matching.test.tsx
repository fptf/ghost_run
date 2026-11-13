import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { tokenStore } from "../auth/tokenStore";
import { json, mockApi } from "../test/mockApi";
import { renderApp } from "../test/renderApp";

vi.mock("../components/TrackMap", () => ({
  TrackMap: (props: { label: string; check?: { deviation: unknown } | null }) => (
    <div
      role="img"
      aria-label={props.label}
      data-deviation={props.check?.deviation ? "yes" : "no"}
    />
  ),
}));

const ME_ID = "11111111-1111-1111-1111-111111111111";
const ROOT = "55555555-5555-5555-5555-555555555555";
const MINE = "66666666-6666-6666-6666-666666666666";
const AUTHOR = { id: "77777777-7777-7777-7777-777777777777", name: "Алексей П.", avatar_url: null };
const ME = { id: ME_ID, name: "Анна", avatar_url: null };

const SESSION = () =>
  json({ access_token: "t", token_type: "bearer", expires_in: 900, user_id: ME_ID });
const PROFILE = () =>
  json({
    ...ME,
    city: null,
    about: null,
    stats: { runs: 0, total_distance_m: 0, records: {} },
    email: "a@example.com",
    role: "runner",
    home: null,
    hide_radius_m: null,
    new_attempts: 0,
  });

function track(id: string, over: Record<string, unknown> = {}) {
  return {
    id,
    status: "draft",
    reject_reason: null,
    reject_message: null,
    visibility: "private",
    title: "Вечерняя набережная",
    started_at: "2026-11-12T08:00:00Z",
    distance_m: 6100,
    total_time_s: 1720,
    avg_pace_s_per_km: 282,
    category: "5",
    created_at: "2026-11-12T09:00:00Z",
    description: null,
    moving_time_s: 1700,
    elevation_gain_m: 41,
    has_elevation: true,
    splits: [],
    author: ME,
    geometry: {
      type: "LineString",
      coordinates: [
        [131.9, 43.1],
        [131.91, 43.11],
      ],
    },
    photos: [],
    is_owner: true,
    owner: { full_geometry: null, hidden_zone: null, fully_hidden: false },
    km_marks: [],
    match: null,
    attempt_of: null,
    group_runners: 0,
    ...over,
  };
}

const MATCH = {
  root: { id: ROOT, title: "Набережная до маяка", author: AUTHOR },
  state: "pending",
  result_time_s: 23 * 60 + 52,
  diff_s: -18,
  beat: true,
  equal: false,
  by_author: false,
  trimmed: true,
  segment_distance_m: 5200,
  hidden_time_s: 0,
};

afterEach(() => {
  vi.unstubAllGlobals();
  tokenStore.set(null);
});

describe("Плашка совпадения в превью", () => {
  it("показывает маршрут, время и разницу; «Не засчитывать» отвязывает", async () => {
    let detached: unknown = null;
    let state = "pending";
    mockApi({
      "POST /auth/refresh": SESSION,
      "GET /me": PROFILE,
      [`GET /tracks/${MINE}`]: () => json(track(MINE, { match: { ...MATCH, state } })),
      [`PATCH /tracks/${MINE}`]: async (req) => {
        detached = await req.json();
        state = "detached";
        return json(track(MINE, { match: { ...MATCH, state } }));
      },
    });
    renderApp(`/tracks/${MINE}/edit`);
    expect(await screen.findByText("Совпало с маршрутом")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Набережная до маяка" })).toHaveAttribute(
      "href",
      `/tracks/${ROOT}`,
    );
    expect(screen.getByText(/на 18 с быстрее автора/)).toBeInTheDocument();
    expect(screen.getByText(/После публикации попытка встанет в группу/)).toBeInTheDocument();
    expect(screen.getByText(/вырезан участок маршрута 5,2 км/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Не засчитывать" }));
    expect(await screen.findByText(/Не засчитывается в группе маршрута/)).toBeInTheDocument();
    expect(detached).toMatchObject({ detach: true });
  });

  it("исчезает при выборе приватной видимости", async () => {
    mockApi({
      "POST /auth/refresh": SESSION,
      "GET /me": PROFILE,
      [`GET /tracks/${MINE}`]: () => json(track(MINE, { match: MATCH })),
    });
    renderApp(`/tracks/${MINE}/edit`);
    expect(await screen.findByText("Совпало с маршрутом")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: "Приватный" }));
    expect(screen.queryByText("Совпало с маршрутом")).not.toBeInTheDocument();
  });
});

describe("Таблица группы", () => {
  it("лучший результат каждого бегуна, отметки и «Вы»", async () => {
    mockApi({
      "POST /auth/refresh": SESSION,
      "GET /me": PROFILE,
      [`GET /tracks/${ROOT}`]: () =>
        json(
          track(ROOT, {
            status: "published",
            visibility: "public",
            is_owner: false,
            owner: null,
            author: AUTHOR,
            title: "Набережная до маяка",
          }),
        ),
      [`GET /tracks/${ROOT}/group`]: () =>
        json({
          root: { id: ROOT, title: "Набережная до маяка", author: AUTHOR },
          root_distance_m: 5200,
          runners: 3,
          rows: [
            {
              place: 1,
              runner: { id: "i", name: "Ирина К.", avatar_url: null },
              track_id: "t1",
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
              track_id: ROOT,
              time_s: 1450,
              pace_s_per_km: 279,
              date: null,
              beat: false,
              is_author: true,
              is_root: true,
              runs: 1,
              is_viewer: false,
            },
            {
              place: 3,
              runner: ME,
              track_id: MINE,
              time_s: 1530,
              pace_s_per_km: 294,
              date: null,
              beat: false,
              is_author: false,
              is_root: false,
              runs: 2,
              is_viewer: true,
            },
          ],
        }),
    });
    renderApp(`/tracks/${ROOT}`);
    expect(await screen.findByText("Ирина К.")).toBeInTheDocument();
    expect(screen.getByText("3 бегуна")).toBeInTheDocument();
    expect(screen.getByText("превзошёл")).toBeInTheDocument();
    expect(screen.getByText("автор")).toBeInTheDocument();
    expect(screen.getByText("Вы")).toBeInTheDocument();
    expect(screen.getByText("лучшая из 2 попыток")).toBeInTheDocument();
    expect(screen.getByText("23:41")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Проверить мою пробежку" })).toHaveAttribute(
      "href",
      `/tracks/${ROOT}/check`,
    );
  });
});

describe("Проверить мою пробежку", () => {
  it("называет невыполненное правило и место схода", async () => {
    let asked: unknown = null;
    mockApi({
      "POST /auth/refresh": SESSION,
      "GET /me": PROFILE,
      [`GET /tracks/${ROOT}`]: () =>
        json(
          track(ROOT, {
            status: "published",
            visibility: "public",
            is_owner: false,
            owner: null,
            author: AUTHOR,
            title: "Набережная до маяка",
          }),
        ),
      "GET /me/tracks": () =>
        json([{ ...track(MINE, { status: "published" }), title: "Вечерняя набережная" }]),
      [`POST /tracks/${ROOT}/check`]: async (req) => {
        asked = await req.json();
        return json({
          matched: false,
          route: { id: ROOT, title: "Набережная до маяка", author: AUTHOR },
          track_id: MINE,
          track_title: "Вечерняя набережная",
          track_started_at: "2026-11-12T08:00:00Z",
          rules: [
            { code: "start", ok: true, value: 12, required: 50 },
            { code: "finish", ok: true, value: 8, required: 50 },
            { code: "corridor", ok: false, value: 0.81, required: 0.9 },
            { code: "direction", ok: true, value: 0.97, required: 0.9 },
            { code: "length", ok: false, value: 0.88, required: 0.03 },
          ],
          deviation: { lon: 131.9, lat: 43.1, km: 2.4 },
          result_time_s: null,
          diff_s: null,
          route_line: {
            type: "LineString",
            coordinates: [
              [131.9, 43.1],
              [131.91, 43.11],
            ],
          },
          corridor: { type: "Polygon", coordinates: [] },
          track_line: {
            type: "LineString",
            coordinates: [
              [131.9, 43.1],
              [131.905, 43.102],
            ],
          },
        });
      },
    });
    renderApp(`/tracks/${ROOT}/check`);
    fireEvent.click(await screen.findByText("Вечерняя набережная"));
    expect(await screen.findByRole("heading", { name: "Маршрут не совпал" })).toBeInTheDocument();
    expect(asked).toEqual({ track_id: MINE });
    expect(
      screen.getByText(
        "«Вечерняя набережная», 12 ноября. На 3-м км вы ушли с маршрута — отмечено на карте.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("В коридоре 81% маршрута, нужно не меньше 90%")).toBeInTheDocument();
    expect(screen.getByText("Старт в пределах 50 м (у вас 12 м)")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /коридор 30 м/ })).toHaveAttribute(
      "data-deviation",
      "yes",
    );
    fireEvent.click(screen.getByRole("button", { name: "Выбрать другую пробежку" }));
    await waitFor(() => expect(screen.getByText("Выберите свою пробежку")).toBeInTheDocument());
  });
});

describe("Проверка: обратное направление", () => {
  it("называет обратную сторону, а не сход с маршрута", async () => {
    mockApi({
      "POST /auth/refresh": SESSION,
      "GET /me": PROFILE,
      [`GET /tracks/${ROOT}`]: () =>
        json(
          track(ROOT, {
            status: "published",
            visibility: "public",
            is_owner: false,
            owner: null,
            author: AUTHOR,
          }),
        ),
      "GET /me/tracks": () => json([{ ...track(MINE, { status: "draft" }), title: "Обратно" }]),
      [`POST /tracks/${ROOT}/check`]: () =>
        json({
          matched: false,
          route: { id: ROOT, title: "Трёшка", author: AUTHOR },
          track_id: MINE,
          track_title: "Обратно",
          track_started_at: "2026-10-28T08:00:00Z",
          rules: [
            { code: "start", ok: true, value: 5, required: 50 },
            { code: "finish", ok: true, value: 1, required: 50 },
            { code: "corridor", ok: false, value: 0.68, required: 0.9 },
            { code: "direction", ok: false, value: 0.05, required: 0.9 },
            { code: "length", ok: true, value: 0.98, required: 0.03 },
          ],
          deviation: { lon: 131.9, lat: 43.1, km: 0.4 },
          result_time_s: null,
          diff_s: null,
          route_line: null,
          corridor: null,
          track_line: null,
        }),
    });
    renderApp(`/tracks/${ROOT}/check`);
    fireEvent.click(await screen.findByText("Обратно"));
    expect(await screen.findByText(/пробежан в обратную сторону/)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /коридор 30 м/ })).toHaveAttribute(
      "data-deviation",
      "no",
    );
  });
});
