import {describe, it, expect} from "vitest";
import {displayDate, displayMonth, shiftMonth} from "./dates";
describe("calendar dates", () => {
  it("crosses year boundaries in both directions", () => {
    expect(shiftMonth("2026-12", 1)).toBe("2027-01");
    expect(shiftMonth("2027-01", -1)).toBe("2026-12");
  });
  it("formats date-only values without timezone shifts", () => {
    expect(displayDate("2026-11-01")).toBe("Nov 1, 2026");
    expect(displayMonth("2027-01")).toBe("Jan 2027");
  });
});
