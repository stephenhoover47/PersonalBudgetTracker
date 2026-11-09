import { describe, it, expect } from "vitest";
import { cents, dollars } from "./money";
describe("exact USD conversion", () => {
  it("preserves cents and signed inflows", () => {
    expect(cents("10.01")).toBe(1001);
    expect(cents("-0.10")).toBe(-10);
    expect(cents("1.2")).toBe(120);
    expect(dollars(1001)).toBe("$10.01");
  });
  it("rejects precision loss and malformed values", () => {
    for (const value of ["1.001", "NaN", "1e3", "", "--1", "10000001"])
      expect(() => cents(value)).toThrow();
  });
});
