import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import {
  obtenerControlRoomData,
  resumirAgentRuns,
} from "./control-room-data";

describe("control-room-data · agent-runs estáticos", () => {
  it("usa un import JSON local a landing compatible con build Next/Turbopack", () => {
    const source = readFileSync(join(process.cwd(), "lib/control-room-data.ts"), "utf-8");
    const docsIndex = readFileSync(join(process.cwd(), "..", "docs/ops/agent-runs/index.json"), "utf-8");
    const landingIndex = readFileSync(join(process.cwd(), "data/agent-runs-index.json"), "utf-8");

    expect(source).not.toContain("../../docs/ops/agent-runs/index.json");
    expect(source).toContain("../data/agent-runs-index.json");
    expect(JSON.parse(landingIndex)).toEqual(JSON.parse(docsIndex));
  });

  it("lee metadata versionada del índice docs/ops/agent-runs", () => {
    const data = obtenerControlRoomData();

    expect(data.source).toBe("docs/ops/agent-runs/index.json");
    expect(data.generatedAt).toBe("2026-05-24");
    expect(data.runs.length).toBeGreaterThanOrEqual(2);
    expect(data.runs.map((run) => run.pr)).toContain(48);
    expect(data.runs.map((run) => run.pr)).toContain(49);
  });

  it("resume cantidad de runs, riesgos y costos sin APIs vivas", () => {
    const summary = resumirAgentRuns(obtenerControlRoomData().runs);

    expect(summary.total).toBeGreaterThanOrEqual(2);
    expect(summary.porRiesgo.MEDIUM).toBeGreaterThanOrEqual(2);
    expect(summary.costosEstimados.length).toBeGreaterThan(0);
    expect(summary.proximaAccion).toMatch(/Control Room|HIGH/i);
  });

  it("mantiene datos no sensibles para render del Control Room", () => {
    const data = obtenerControlRoomData();
    const serializado = JSON.stringify(data);

    expect(serializado).not.toMatch(/gh[pousr]_/i);
    expect(serializado).not.toMatch(/BEGIN [A-Z ]*PRIVATE KEY/);
    expect(serializado).not.toMatch(/live[_-]credential|webhook[_-]secret/i);
  });
});
