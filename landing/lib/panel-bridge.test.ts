// landing/lib/panel-bridge.test.ts
// Tests del bridge GitHub/Render del panel de ingeniería. Foco: helpers
// puros, best-effort por sección (una API caída no tumba el panel) y que
// los tokens nunca aparezcan en el payload resultante.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  totalDesdeLinkHeader,
  duracionSegundos,
  primeraLinea,
  mapRenderDeploy,
  fetchPanelData,
} from "./panel-bridge";

const ENV_ORIGINAL = { ...process.env };

beforeEach(() => {
  process.env.PANEL_GITHUB_TOKEN = "gh-token-test";
  process.env.RENDER_API_KEY = "render-key-test";
  delete process.env.GITHUB_TOKEN;
  delete process.env.PANEL_GITHUB_REPO;
});

afterEach(() => {
  vi.restoreAllMocks();
  process.env = { ...ENV_ORIGINAL };
});

// ── Helpers puros ──────────────────────────────────────────────────────────

describe("totalDesdeLinkHeader", () => {
  it("extrae el total del rel=last (per_page=1 → página = total)", () => {
    const link =
      '<https://api.github.com/repositories/1/commits?per_page=1&page=2>; rel="next", ' +
      '<https://api.github.com/repositories/1/commits?per_page=1&page=347>; rel="last"';
    expect(totalDesdeLinkHeader(link, 1)).toBe(347);
  });

  it("devuelve fallback sin header (repo con 1 commit)", () => {
    expect(totalDesdeLinkHeader(null, 1)).toBe(1);
  });

  it("devuelve fallback si no hay rel=last", () => {
    const link = '<https://api.github.com/x?page=3>; rel="next"';
    expect(totalDesdeLinkHeader(link, 5)).toBe(5);
  });
});

describe("duracionSegundos", () => {
  it("calcula la duración entre timestamps ISO", () => {
    expect(
      duracionSegundos("2026-06-10T10:00:00Z", "2026-06-10T10:03:30Z"),
    ).toBe(210);
  });

  it("null si falta alguno", () => {
    expect(duracionSegundos(null, "2026-06-10T10:00:00Z")).toBeNull();
    expect(duracionSegundos("2026-06-10T10:00:00Z", undefined)).toBeNull();
  });

  it("null si fin < inicio o timestamps inválidos", () => {
    expect(
      duracionSegundos("2026-06-10T10:00:00Z", "2026-06-10T09:00:00Z"),
    ).toBeNull();
    expect(duracionSegundos("no-es-fecha", "2026-06-10T10:00:00Z")).toBeNull();
  });
});

describe("primeraLinea", () => {
  it("toma solo la primera línea del mensaje", () => {
    expect(primeraLinea("feat: algo\n\ncuerpo largo")).toBe("feat: algo");
  });

  it("trunca mensajes largos con elipsis", () => {
    const largo = "a".repeat(200);
    const r = primeraLinea(largo, 50);
    expect(r.length).toBe(50);
    expect(r.endsWith("…")).toBe(true);
  });
});

describe("mapRenderDeploy", () => {
  const deploy = {
    id: "dep-123",
    status: "live",
    createdAt: "2026-06-10T10:00:00Z",
    finishedAt: "2026-06-10T10:05:00Z",
    commit: { id: "659977cabcdef", message: "Merge pull request #75" },
  };

  it("normaliza el formato con wrapper de cursor [{deploy: {...}}]", () => {
    const r = mapRenderDeploy({ deploy });
    expect(r?.estado).toBe("live");
    expect(r?.commit_corto).toBe("659977c");
    expect(r?.duracion_segundos).toBe(300);
  });

  it("normaliza el formato plano (sin wrapper)", () => {
    const r = mapRenderDeploy(deploy);
    expect(r?.estado).toBe("live");
  });

  it("null si no hay status", () => {
    expect(mapRenderDeploy({} as never)).toBeNull();
  });
});

// ── fetchPanelData (fetch mockeado) ────────────────────────────────────────

/** Response-like mínimo para el mock de fetch. */
function respuesta(data: unknown, link: string | null = null) {
  return {
    ok: true,
    status: 200,
    json: async () => data,
    headers: { get: (k: string) => (k === "link" ? link : null) },
  };
}

/** Mock de fetch que rutea por URL las APIs de GitHub y Render. */
function mockApisOk() {
  return vi.fn(async (url: string) => {
    const u = String(url);
    if (u.includes("api.render.com")) {
      return respuesta([
        {
          deploy: {
            id: "dep-1",
            status: "live",
            createdAt: "2026-06-10T10:00:00Z",
            finishedAt: "2026-06-10T10:04:00Z",
            commit: { id: "659977cff", message: "Merge #75" },
          },
        },
      ]);
    }
    // OJO: chequear per_page=12 ANTES que per_page=1 (substring).
    if (u.includes("/commits?per_page=12")) {
      return respuesta([
        {
          sha: "c575878abcdef",
          html_url: "https://github.com/x/commit/c575878",
          commit: {
            message: "feat(automation): ejecutor HIGH\n\ncuerpo",
            author: { name: "celestino", date: "2026-06-09T12:00:00Z" },
          },
        },
      ]);
    }
    if (u.includes("/commits?per_page=1")) {
      return respuesta(
        [{ sha: "x", html_url: "", commit: { message: "m", author: {} } }],
        '<https://api.github.com/x?per_page=1&page=512>; rel="last"',
      );
    }
    if (u.includes("/branches")) {
      return respuesta([{}, {}, {}]);
    }
    if (u.includes("state=open")) {
      return respuesta([
        {
          number: 76,
          title: "Scheduler lock",
          draft: false,
          html_url: "https://github.com/x/pull/76",
          created_at: "2026-06-10T08:00:00Z",
          merged_at: null,
          head: { ref: "security/phase0-scheduler-lock" },
          user: { login: "celestinojbm" },
        },
      ]);
    }
    if (u.includes("state=closed")) {
      return respuesta([
        {
          number: 75,
          title: "Gate central",
          draft: false,
          html_url: "https://github.com/x/pull/75",
          created_at: "2026-06-09T08:00:00Z",
          merged_at: "2026-06-10T09:00:00Z",
          head: { ref: "security/phase0-gate-envio" },
          user: { login: "celestinojbm" },
        },
        {
          number: 60,
          title: "Cerrado sin merge",
          draft: false,
          html_url: "https://github.com/x/pull/60",
          created_at: "2026-06-01T08:00:00Z",
          merged_at: null,
          head: { ref: "vieja" },
          user: { login: "celestinojbm" },
        },
      ]);
    }
    if (u.includes("/stats/participation")) {
      return respuesta({ all: Array.from({ length: 52 }, (_, i) => i) });
    }
    if (u.includes("/actions/runs")) {
      return respuesta({
        workflow_runs: [
          {
            id: 1,
            name: "Suite completa (pytest)",
            head_branch: "main",
            status: "completed",
            conclusion: "success",
            run_started_at: "2026-06-10T10:00:00Z",
            updated_at: "2026-06-10T10:03:00Z",
            html_url: "https://github.com/x/actions/runs/1",
          },
        ],
      });
    }
    // GET /repos/{repo} (info del repo)
    return respuesta({ open_issues_count: 4 });
  });
}

describe("fetchPanelData — camino feliz", () => {
  it("arma el panel completo con todas las secciones", async () => {
    vi.stubGlobal("fetch", mockApisOk());
    const data = await fetchPanelData();

    expect(data.errores).toEqual([]);
    expect(data.repo?.total_commits).toBe(512);
    expect(data.repo?.prs_abiertos).toBe(1);
    // open_issues_count (4) incluye el PR abierto → issues reales = 3
    expect(data.repo?.issues_abiertos).toBe(3);
    expect(data.repo?.ramas).toBe(3);
    expect(data.velocity).toHaveLength(12);
    expect(data.velocity?.[11]).toBe(51);
    expect(data.ci?.[0].conclusion).toBe("success");
    expect(data.ci?.[0].duracion_segundos).toBe(180);
    expect(data.deploys?.web?.estado).toBe("live");
    expect(data.deploys?.worker?.estado).toBe("live");
    expect(data.prs_abiertos?.[0].numero).toBe(76);
    // Solo PRs con merged_at cuentan como mergeados
    expect(data.prs_merged?.map((p) => p.numero)).toEqual([75]);
    expect(data.commits?.[0].sha_corto).toBe("c575878");
    expect(data.commits?.[0].mensaje).toBe(
      "feat(automation): ejecutor HIGH",
    );
  });

  it("manda el token de GitHub en Authorization y nunca en el payload", async () => {
    const fetchMock = mockApisOk();
    vi.stubGlobal("fetch", fetchMock);
    const data = await fetchPanelData();

    const llamadaGitHub = fetchMock.mock.calls.find(([u]) =>
      String(u).includes("api.github.com"),
    );
    expect(llamadaGitHub).toBeDefined();
    const headers = (llamadaGitHub![1] as { headers: Record<string, string> })
      .headers;
    expect(headers.Authorization).toBe("Bearer gh-token-test");

    // El payload serializado no contiene ningún token.
    const json = JSON.stringify(data);
    expect(json).not.toContain("gh-token-test");
    expect(json).not.toContain("render-key-test");
  });
});

describe("fetchPanelData — best-effort", () => {
  it("sin tokens configurados: todo null + errores anotados, sin lanzar", async () => {
    delete process.env.PANEL_GITHUB_TOKEN;
    delete process.env.RENDER_API_KEY;
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const data = await fetchPanelData();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(data.repo).toBeNull();
    expect(data.deploys).toBeNull();
    expect(data.errores.length).toBeGreaterThan(0);
  });

  it("GitHub caído no tumba Render (y viceversa queda anotado)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (String(url).includes("api.render.com")) {
          return respuesta([
            {
              deploy: {
                status: "live",
                createdAt: "2026-06-10T10:00:00Z",
                finishedAt: null,
                commit: { id: "abc1234ff", message: "m" },
              },
            },
          ]);
        }
        return { ok: false, status: 500, json: async () => ({}), headers: { get: () => null } };
      }),
    );

    const data = await fetchPanelData();
    expect(data.repo).toBeNull();
    expect(data.ci).toBeNull();
    expect(data.deploys?.web?.estado).toBe("live");
    expect(data.errores.some((e) => e.includes("HTTP 500"))).toBe(true);
  });

  it("participation en 202 (sin body computado) deja velocity en null", async () => {
    const base = mockApisOk();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (String(url).includes("/stats/participation")) {
          return respuesta({}); // GitHub computando: body vacío
        }
        return base(url);
      }),
    );
    const data = await fetchPanelData();
    expect(data.velocity).toBeNull();
    expect(data.repo?.total_commits).toBe(512);
  });
});
