import { describe, expect, it } from "vitest";

import { formatDuration, formatKm, formatPace } from "./format";

describe("format", () => {
  it("время", () => {
    expect(formatDuration(28 * 60 + 40)).toBe("28:40");
    expect(formatDuration(3723)).toBe("1:02:03");
    expect(formatDuration(null)).toBe("—");
  });
  it("темп", () => {
    expect(formatPace(282)).toBe("4:42");
    expect(formatPace(0)).toBe("—");
  });
  it("километры", () => {
    expect(formatKm(6100)).toBe("6,1");
  });
});
