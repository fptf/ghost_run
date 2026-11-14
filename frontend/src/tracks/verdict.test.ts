import { describe, expect, it } from "vitest";

import { errorDetail } from "../api/errors";
import i18n from "../i18n";
import { verdictText } from "./verdict";

const t = i18n.t.bind(i18n);

describe("verdictText", () => {
  it("быстрее, медленнее и вровень по разнице с порогом в секунду", () => {
    expect(verdictText(t, -18)).toBe("на 18 с быстрее автора");
    expect(verdictText(t, 65)).toBe("на 1:05 медленнее автора");
    expect(verdictText(t, 0.6)).toBe("вровень с автором");
    expect(verdictText(t, null)).toBe("вровень с автором");
  });

  it("признак равенства от сервера главнее порога", () => {
    expect(verdictText(t, 3, true)).toBe("вровень с автором");
    expect(verdictText(t, -3, false)).toBe("на 3 с быстрее автора");
  });
});

describe("errorDetail", () => {
  it("берёт строковый detail, иначе запасной текст", () => {
    expect(errorDetail({ detail: "Слишком большой файл" }, "ошибка")).toBe("Слишком большой файл");
    expect(errorDetail({ detail: [{ msg: "x" }] }, "ошибка")).toBe("ошибка");
    expect(errorDetail(undefined, "ошибка")).toBe("ошибка");
  });
});
