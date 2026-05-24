import { describe, expect, it } from "vitest";
import { puedeVerControlRoomInterno } from "./control-room";

describe("puedeVerControlRoomInterno", () => {
  it("permite el email interno de Celestino", () => {
    expect(puedeVerControlRoomInterno("celestinojbm@gmail.com")).toBe(true);
  });

  it("normaliza espacios y mayúsculas", () => {
    expect(puedeVerControlRoomInterno("  CELESTINOJBM@GMAIL.COM ")).toBe(true);
  });

  it("bloquea usuarios sin allowlist", () => {
    expect(puedeVerControlRoomInterno("cliente@example.com")).toBe(false);
    expect(puedeVerControlRoomInterno(null)).toBe(false);
  });
});
