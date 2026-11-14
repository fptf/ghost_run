import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { tokenStore } from "../auth/tokenStore";
import { json, mockApi } from "../test/mockApi";
import { renderApp } from "../test/renderApp";

vi.mock("../components/TrackMap", () => ({
  TrackMap: ({ label }: { label: string }) => <div role="img" aria-label={label} />,
}));

const TRACK_ID = "22222222-2222-2222-2222-222222222222";
const USER_ID = "11111111-1111-1111-1111-111111111111";

const SESSION = () =>
  json({ access_token: "t", token_type: "bearer", expires_in: 900, user_id: USER_ID });
const ME = () =>
  json({
    id: USER_ID,
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
  });

function track(overrides: Record<string, unknown> = {}) {
  return {
    id: TRACK_ID,
    status: "draft",
    reject_reason: null,
    reject_message: null,
    visibility: "private",
    title: "Пробежка 26 октября",
    started_at: "2026-10-26T10:00:00Z",
    distance_m: 6100,
    total_time_s: 28 * 60 + 40,
    avg_pace_s_per_km: 282,
    category: "5",
    created_at: "2026-10-26T10:40:00Z",
    description: null,
    moving_time_s: 1700,
    elevation_gain_m: 41,
    has_elevation: true,
    splits: [1, 2, 3, 4, 5, 6].map((idx) => ({ idx, distance_m: 1000, time_s: 300 + idx })),
    author: { id: USER_ID, name: "Анна", avatar_url: null },
    geometry: {
      type: "LineString",
      coordinates: [
        [76.9, 42.9],
        [76.91, 42.91],
      ],
    },
    photos: [],
    is_owner: true,
    owner: {
      full_geometry: {
        type: "LineString",
        coordinates: [
          [76.9, 42.9],
          [76.91, 42.91],
        ],
      },
      hidden_zone: { lat: 42.9, lon: 76.9, radius_m: 300 },
      fully_hidden: false,
    },
    km_marks: [],
    match: null,
    attempt_of: null,
    group_runners: 0,
    achievements: [],
    ...overrides,
  };
}

function pickFile(name = "run.gpx") {
  const input = screen.getByLabelText("Выбрать файл");
  const file = new File(["<gpx></gpx>"], name, { type: "application/gpx+xml" });
  fireEvent.change(input, { target: { files: [file] } });
}

afterEach(() => {
  vi.unstubAllGlobals();
  tokenStore.set(null);
});

describe("Загрузка трека", () => {
  it("показывает шаги обработки и открывает превью, когда трек готов", async () => {
    let polls = 0;
    mockApi({
      "POST /auth/refresh": SESSION,
      "GET /me": ME,
      "POST /tracks": () => json(track({ status: "processing" }), 202),
      [`GET /tracks/${TRACK_ID}`]: () => {
        polls += 1;
        return json(polls < 2 ? track({ status: "processing" }) : track());
      },
    });
    renderApp("/upload");
    await screen.findByText("Перетащите файл сюда");
    pickFile();

    expect(await screen.findByText("Считаем дистанцию, темп и сплиты")).toBeInTheDocument();
    expect(screen.getByText(/Можно закрыть экран/)).toBeInTheDocument();

    expect(
      await screen.findByRole("heading", { name: "Новый трек" }, { timeout: 3000 }),
    ).toBeInTheDocument();
    expect(screen.getByText("6,1 км")).toBeInTheDocument();
    expect(screen.getByText("28:40")).toBeInTheDocument();
    expect(screen.getByText("4:42")).toBeInTheDocument();
    expect(
      screen.getByText("Скрыто 300 м вокруг дома — другие этого не увидят"),
    ).toBeInTheDocument();
  });

  it("показывает причину отказа и предлагает загрузить другой файл", async () => {
    mockApi({
      "POST /auth/refresh": SESSION,
      "GET /me": ME,
      "POST /tracks": () => json(track({ status: "processing" }), 202),
      [`GET /tracks/${TRACK_ID}`]: () =>
        json(
          track({
            status: "rejected",
            reject_reason: "too_fast",
            reject_message: "похоже на транспорт",
          }),
        ),
    });
    renderApp("/upload");
    await screen.findByText("Перетащите файл сюда");
    pickFile();

    expect(await screen.findByRole("alert")).toHaveTextContent("похоже на транспорт");
    fireEvent.click(screen.getByRole("button", { name: "Загрузить другой файл" }));
    expect(await screen.findByText("Перетащите файл сюда")).toBeInTheDocument();
  });

  it("сообщает, что файл слишком большой, ещё до обработки", async () => {
    mockApi({
      "POST /auth/refresh": SESSION,
      "GET /me": ME,
      "POST /tracks": () => json({ code: "too_large", detail: "файл больше 20 МБ" }, 413),
    });
    renderApp("/upload");
    await screen.findByText("Перетащите файл сюда");
    pickFile();
    expect(await screen.findByRole("alert")).toHaveTextContent("файл больше 20 МБ");
  });

  it("на повторную загрузку даёт ссылку на существующий трек", async () => {
    mockApi({
      "POST /auth/refresh": SESSION,
      "GET /me": ME,
      "POST /tracks": () =>
        json({ code: "duplicate", detail: "Этот трек уже есть", track_id: TRACK_ID }, 409),
    });
    renderApp("/upload");
    await screen.findByText("Перетащите файл сюда");
    pickFile();
    expect(await screen.findByRole("alert")).toHaveTextContent("Этот трек уже есть");
    expect(screen.getByRole("link", { name: "Открыть трек" })).toHaveAttribute(
      "href",
      `/tracks/${TRACK_ID}`,
    );
  });
});

describe("Превью", () => {
  it("публикует трек с выбранной видимостью", async () => {
    let patched: unknown = null;
    mockApi({
      "POST /auth/refresh": SESSION,
      "GET /me": ME,
      [`GET /tracks/${TRACK_ID}`]: () => json(track()),
      [`PATCH /tracks/${TRACK_ID}`]: async (req) => {
        patched = await req.json();
        return json(track({ status: "published", visibility: "link", title: "Набережная" }));
      },
    });
    renderApp(`/tracks/${TRACK_ID}/edit`);
    fireEvent.click(await screen.findByRole("radio", { name: "По ссылке" }));
    fireEvent.change(screen.getByLabelText("Название"), { target: { value: "Набережная" } });
    fireEvent.click(screen.getByRole("button", { name: "Опубликовать" }));

    // Форма закрывается — открывается просмотр трека.
    expect(await screen.findByText("Трек опубликован")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Опубликовать" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Редактировать" })).toHaveAttribute(
      "href",
      `/tracks/${TRACK_ID}/edit`,
    );
    expect(patched).toMatchObject({ title: "Набережная", visibility: "link", publish: true });
  });

  it("трек целиком в скрытой зоне можно сделать только приватным", async () => {
    mockApi({
      "POST /auth/refresh": SESSION,
      "GET /me": ME,
      [`GET /tracks/${TRACK_ID}`]: () =>
        json(
          track({
            geometry: null,
            owner: { full_geometry: null, hidden_zone: null, fully_hidden: true },
          }),
        ),
    });
    renderApp(`/tracks/${TRACK_ID}/edit`);
    expect(await screen.findByRole("radio", { name: "Публичный" })).toBeDisabled();
    expect(screen.getByRole("radio", { name: "Приватный" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    expect(screen.getByText(/только как приватный/)).toBeInTheDocument();
  });

  it("чужой трек показывается без формы и с автором", async () => {
    mockApi({
      "POST /auth/refresh": () => json({ detail: "Нет сессии" }, 401),
      [`GET /tracks/${TRACK_ID}`]: () =>
        json(
          track({
            status: "published",
            visibility: "public",
            is_owner: false,
            owner: null,
            title: "Набережная",
          }),
        ),
    });
    renderApp(`/tracks/${TRACK_ID}`);
    expect(await screen.findByRole("heading", { name: "Набережная" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Анна/ })).toHaveAttribute("href", `/users/${USER_ID}`);
    expect(screen.queryByRole("button", { name: "Опубликовать" })).not.toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText(/вокруг дома/)).not.toBeInTheDocument());
  });
});

describe("Ошибки на форме трека", () => {
  const PHOTO_ID = "33333333-3333-3333-3333-333333333333";

  it("сохранение с ошибкой оставляет форму и показывает причину", async () => {
    mockApi({
      "POST /auth/refresh": SESSION,
      "GET /me": ME,
      [`GET /tracks/${TRACK_ID}`]: () => json(track()),
      [`PATCH /tracks/${TRACK_ID}`]: () => json({ detail: "Название занято" }, 400),
    });
    renderApp(`/tracks/${TRACK_ID}/edit`);
    fireEvent.click(await screen.findByRole("button", { name: "Опубликовать" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Название занято");
    expect(screen.getByLabelText("Название")).toBeInTheDocument();
  });

  it("сбой загрузки и удаления фото показывается ошибкой", async () => {
    mockApi({
      "POST /auth/refresh": SESSION,
      "GET /me": ME,
      [`GET /tracks/${TRACK_ID}`]: () => json(track({ photos: [{ id: PHOTO_ID }] })),
      [`POST /tracks/${TRACK_ID}/photos`]: () => json({ detail: "Слишком большое фото" }, 413),
      [`DELETE /tracks/${TRACK_ID}/photos/${PHOTO_ID}`]: () => json({ detail: "boom" }, 500),
    });
    renderApp(`/tracks/${TRACK_ID}/edit`);
    const input = await screen.findByLabelText("+ Фото, до 5");
    fireEvent.change(input, {
      target: { files: [new File(["x"], "a.jpg", { type: "image/jpeg" })] },
    });
    expect(await screen.findByRole("alert")).toHaveTextContent("Слишком большое фото");

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const req = input instanceof Request ? input : new Request(input, init);
        if (req.method === "DELETE") return new Response(null, { status: 500 });
        return json(track({ photos: [{ id: PHOTO_ID }] }));
      }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Удалить фото" }));
    expect(await screen.findByText("Не удалось удалить фото")).toBeInTheDocument();
  });

  it("неудачное удаление трека не уводит со страницы", async () => {
    const { calls } = mockApi({
      "POST /auth/refresh": SESSION,
      "GET /me": ME,
      [`GET /tracks/${TRACK_ID}`]: () => json(track({ status: "published" })),
      [`DELETE /tracks/${TRACK_ID}`]: () => new Response(null, { status: 500 }),
    });
    renderApp(`/tracks/${TRACK_ID}/edit`);
    fireEvent.click(await screen.findByRole("button", { name: "Удалить трек" }));
    fireEvent.click(screen.getByRole("button", { name: "Да, удалить" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Не удалось удалить трек");
    expect(screen.getByLabelText("Название")).toBeInTheDocument();
    expect(calls).toContain(`DELETE /tracks/${TRACK_ID}`);
  });
});

describe("Навигация трека", () => {
  it("с формы можно уйти кнопкой «Назад» — на просмотр трека", async () => {
    mockApi({
      "POST /auth/refresh": SESSION,
      "GET /me": ME,
      [`GET /tracks/${TRACK_ID}`]: () => json(track({ status: "published", visibility: "public" })),
    });
    renderApp(`/tracks/${TRACK_ID}/edit`);
    expect(
      await screen.findByRole("heading", { name: "Редактирование трека" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Назад" }));
    expect(await screen.findByRole("link", { name: "Редактировать" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Название")).not.toBeInTheDocument();
  });

  it("черновик на просмотре предлагает опубликовать", async () => {
    mockApi({
      "POST /auth/refresh": SESSION,
      "GET /me": ME,
      [`GET /tracks/${TRACK_ID}`]: () => json(track()),
    });
    renderApp(`/tracks/${TRACK_ID}`);
    expect(await screen.findByText("Черновик — трек видите только вы.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Опубликовать" })).toHaveAttribute(
      "href",
      `/tracks/${TRACK_ID}/edit`,
    );
  });

  it("график темпа подписывает значения", async () => {
    mockApi({
      "POST /auth/refresh": SESSION,
      "GET /me": ME,
      [`GET /tracks/${TRACK_ID}`]: () => json(track({ status: "published", visibility: "public" })),
    });
    renderApp(`/tracks/${TRACK_ID}`);
    expect(await screen.findByText("5:01")).toBeInTheDocument(); // 1 км: 301 с
    expect(screen.getByText("5:06")).toBeInTheDocument(); // 6 км: 306 с
  });
});
