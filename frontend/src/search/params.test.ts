import { describe, expect, it } from "vitest";

import { readFilters, readView, VLADIVOSTOK, writeParams } from "./params";

describe("состояние карты в адресе", () => {
  it("без параметров — Владивосток и пустые фильтры", () => {
    const p = new URLSearchParams("");
    expect(readView(p)).toEqual(VLADIVOSTOK);
    expect(readFilters(p).cat).toBeNull();
    expect(readFilters(p).sort).toBe("popular");
  });

  it("восстанавливает вид и фильтры", () => {
    const p = new URLSearchParams("lat=55.75&lon=37.6&z=13&cat=10&pmin=270&att=1&sort=pace&q=парк");
    expect(readView(p)).toEqual({ lat: 55.75, lon: 37.6, z: 13 });
    const f = readFilters(p);
    expect([f.cat, f.pmin, f.att, f.sort, f.q]).toEqual(["10", 270, true, "pace", "парк"]);
  });

  it("пишет и убирает параметры, не трогая остальные", () => {
    const next = writeParams(new URLSearchParams("track=abc&cat=5"), {
      cat: null,
      dmin: 8,
      sort: "popular",
    });
    expect(next.get("track")).toBe("abc");
    expect(next.has("cat")).toBe(false);
    expect(next.get("dmin")).toBe("8");
    expect(next.has("sort")).toBe(false);
  });
});
