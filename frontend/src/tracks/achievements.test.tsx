import { fireEvent, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { tokenStore } from "../auth/tokenStore";
import { json, mockApi } from "../test/mockApi";
import { renderApp } from "../test/renderApp";

vi.mock("../components/TrackMap", () => ({ TrackMap: () => <div data-testid="map" /> }));

const ME_ID = "11111111-1111-1111-1111-111111111111";
const T = "22222222-2222-2222-2222-222222222222";
const ROOT = "55555555-5555-5555-5555-555555555555";
const AUTHOR = { id: "a", name: "Алексей П.", avatar_url: null };
const ME = { id: ME_ID, name: "Анна", avatar_url: null };
const SESSION = () =>
  json({ access_token: "t", token_type: "bearer", expires_in: 900, user_id: ME_ID });
const profile =
  (fresh = 0) =>
  () =>
    json({
      ...ME,
      city: null,
      about: null,
      stats: { runs: 3, total_distance_m: 15000, records: {} },
      email: "a@example.com",
      role: "runner",
      home: null,
      hide_radius_m: null,
      new_attempts: fresh,
    });

function row(place: number, runner: typeof ME, time: number, extra: Record<string, unknown> = {}) {
  return {
    place,
    runner,
    track_id: `t${place}`,
    time_s: time,
    pace_s_per_km: time / 5.2,
    date: null,
    beat: false,
    is_author: false,
    is_root: false,
    runs: 1,
    is_viewer: false,
    ...extra,
  };
}

function result(outcome: "beat" | "slower", diff: number, place: number, runners: number) {
  const mine = 1450 + diff;
  return {
    outcome,
    route: { id: ROOT, title: "Набережная до маяка", author: AUTHOR },
    result_time_s: mine,
    root_time_s: 1450,
    diff_s: diff,
    place,
    runners,
    best_time_s: 1421,
    gap_to_best_s: Math.max(0, mine - 1421),
    by_author: false,
    rows: [
      row(1, { id: "i", name: "Ирина К.", avatar_url: null }, 1421, { beat: true }),
      row(2, ME, mine, { is_viewer: true, beat: outcome === "beat" }),
      row(3, { id: "d", name: "Дмитрий С.", avatar_url: null }, 1438, { beat: true }),
      row(4, AUTHOR, 1450, { is_root: true, is_author: true }),
    ].slice(0, runners),
    achievements:
      outcome === "beat" ? [{ code: "outperformed", title: "Превзошёл", icon: "bolt" }] : [],
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  tokenStore.set(null);
});

describe("Экран результата", () => {
  it("превзошёл: ачивка, −18 с, время против автора, место, соседи", async () => {
    mockApi({
      "POST /auth/refresh": SESSION,
      "GET /me": profile(),
      [`GET /tracks/${T}/result`]: () => json(result("beat", -18, 2, 4)),
    });
    renderApp(`/tracks/${T}/result`);
    expect(await screen.findByText(/Ачивка «Превзошёл»/)).toBeInTheDocument();
    expect(screen.getByText("−18 с")).toBeInTheDocument();
    expect(screen.getByText("23:52 против 24:10 у Алексей П.")).toBeInTheDocument();
    expect(screen.getByText("на маршруте «Набережная до маяка»")).toBeInTheDocument();
    expect(screen.getByText("Место в группе: 2 из 4")).toBeInTheDocument();
    expect(screen.getByText("Вы · новое место")).toBeInTheDocument();
    const places = [...document.querySelectorAll(".group-row__place")].map((e) => e.textContent);
    expect(places).toEqual([...places].sort());
    expect(
      screen.getByText(/До лучшего результата в группе 11 с — лучший 23:41/),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Поделиться" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Вся группа маршрута" })).toHaveAttribute(
      "href",
      `/tracks/${ROOT}`,
    );
  });

  it("медленнее: «Попытка засчитана», +34 с, место из числа бегунов", async () => {
    mockApi({
      "POST /auth/refresh": SESSION,
      "GET /me": profile(),
      [`GET /tracks/${T}/result`]: () => json(result("slower", 34, 2, 4)),
    });
    renderApp(`/tracks/${T}/result`);
    expect(await screen.findByText("Попытка засчитана")).toBeInTheDocument();
    expect(screen.getByText("+34 с")).toBeInTheDocument();
    expect(screen.getByText("столько не хватило до автора")).toBeInTheDocument();
    expect(screen.queryByText(/Ачивка/)).not.toBeInTheDocument();
  });

  it("«Поделиться» копирует ссылку, если нет системного меню", async () => {
    const writeText = vi.fn(async () => undefined);
    vi.stubGlobal("navigator", { ...navigator, share: undefined, clipboard: { writeText } });
    mockApi({
      "POST /auth/refresh": SESSION,
      "GET /me": profile(),
      [`GET /tracks/${T}/result`]: () => json(result("beat", -18, 1, 2)),
    });
    renderApp(`/tracks/${T}/result`);
    fireEvent.click(await screen.findByRole("button", { name: "Поделиться" }));
    expect(await screen.findByRole("button", { name: "Ссылка скопирована" })).toBeInTheDocument();
    expect(writeText).toHaveBeenCalledWith(expect.stringContaining(`/tracks/${T}`));
  });
});

describe("После публикации попытки", () => {
  it("открывает экран результата", async () => {
    const base = {
      id: T,
      status: "draft",
      reject_reason: null,
      reject_message: null,
      visibility: "private",
      title: "Вечерняя набережная",
      started_at: null,
      distance_m: 5200,
      total_time_s: 1432,
      avg_pace_s_per_km: 275,
      category: "5",
      created_at: "2026-11-12T09:00:00Z",
      description: null,
      moving_time_s: 1432,
      elevation_gain_m: null,
      has_elevation: false,
      splits: [],
      author: ME,
      geometry: null,
      photos: [],
      is_owner: true,
      owner: { full_geometry: null, hidden_zone: null, fully_hidden: false },
      km_marks: [],
      match: {
        root: { id: ROOT, title: "Набережная до маяка", author: AUTHOR },
        state: "pending",
        result_time_s: 1432,
        diff_s: -18,
        beat: true,
        equal: false,
        by_author: false,
        trimmed: false,
        segment_distance_m: 5200,
        hidden_time_s: 0,
      },
      attempt_of: null,
      group_runners: 0,
      achievements: [],
      new_attempts: 0,
      is_attempt: false,
    };
    mockApi({
      "POST /auth/refresh": SESSION,
      "GET /me": profile(),
      [`GET /tracks/${T}`]: () => json(base),
      [`PATCH /tracks/${T}`]: () =>
        json({
          ...base,
          status: "published",
          visibility: "public",
          attempt_of: { id: ROOT, title: "Набережная до маяка", author: AUTHOR },
        }),
      [`GET /tracks/${T}/result`]: () => json(result("beat", -18, 2, 4)),
    });
    renderApp(`/tracks/${T}/edit`);
    fireEvent.click(await screen.findByRole("button", { name: "Опубликовать" }));
    expect(await screen.findByText("−18 с")).toBeInTheDocument();
  });
});

describe("Счётчик и витрина", () => {
  it("значок новых попыток на «Профиль» и витрина ачивок", async () => {
    mockApi({
      "POST /auth/refresh": SESSION,
      "GET /me": profile(2),
      "GET /me/tracks": () =>
        json([
          {
            id: ROOT,
            status: "published",
            reject_reason: null,
            reject_message: null,
            visibility: "public",
            title: "Мой маршрут",
            started_at: null,
            distance_m: 5000,
            total_time_s: 1500,
            avg_pace_s_per_km: 300,
            category: "5",
            created_at: "2026-11-01T00:00:00Z",
            new_attempts: 2,
            is_attempt: false,
          },
          {
            id: T,
            status: "published",
            reject_reason: null,
            reject_message: null,
            visibility: "public",
            title: "Чужая пятёрка",
            started_at: null,
            distance_m: 5000,
            total_time_s: 1400,
            avg_pace_s_per_km: 280,
            category: "5",
            created_at: "2026-11-02T00:00:00Z",
            new_attempts: 0,
            is_attempt: true,
          },
        ]),
      [`GET /users/${ME_ID}/achievements`]: () =>
        json([
          {
            code: "outperformed",
            title: "Превзошёл",
            description: "Пробежал чужой маршрут быстрее автора",
            icon: "bolt",
            count: 2,
            items: [
              { track_id: T, title: "Чужая пятёрка", awarded_at: "2026-11-02T00:00:00Z" },
              { track_id: "x", title: "Ещё одна", awarded_at: "2026-11-03T00:00:00Z" },
            ],
          },
        ]),
    });
    renderApp("/me");
    expect((await screen.findAllByLabelText("2 новые попытки")).length).toBeGreaterThan(0);
    expect(screen.getByText("+2 новые")).toBeInTheDocument();
    expect(screen.queryByText("Чужая пятёрка")).not.toBeInTheDocument(); // попытки — в своей вкладке
    fireEvent.click(screen.getByRole("tab", { name: "Мои попытки" }));
    expect(await screen.findByText("Чужая пятёрка")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Ачивки" }));
    expect(await screen.findByText("×2")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ещё одна" })).toHaveAttribute("href", "/tracks/x");
  });
});
