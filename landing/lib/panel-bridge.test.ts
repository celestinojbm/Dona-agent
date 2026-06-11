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
  serieDiaria,
  actividadPorDia,
  topLenguajes,
  promedioHorasMerge,
  fetchPanelData,
  type SemanaActividad,
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

describe("serieDiaria", () => {
  // Dos semanas: la segunda es "la actual" con días futuros en cero.
  const lunes9jun = Date.UTC(2026, 5, 9) / 1000; // no real, solo offsets
  const semanas: SemanaActividad[] = [
    { week: lunes9jun - 7 * 86_400, days: [1, 2, 3, 4, 5, 6, 7], total: 28 },
    { week: lunes9jun, days: [8, 9, 0, 0, 0, 0, 0], total: 17 },
  ];

  it("aplana semanas en días y descarta los futuros", () => {
    // "ahora" = segundo día de la semana actual al mediodía.
    const ahora = (lunes9jun + 1 * 86_400) * 1000 + 12 * 3_600_000;
    const serie = serieDiaria(semanas, ahora, 30);
    // 7 días de la semana vieja + 2 de la actual (días 3..7 son futuros).
    expect(serie).toHaveLength(9);
    expect(serie[serie.length - 1].commits).toBe(9);
    expect(serie[0].commits).toBe(1);
  });

  it("recorta a los últimos n puntos", () => {
    const ahora = (lunes9jun + 6 * 86_400) * 1000;
    const serie = serieDiaria(semanas, ahora, 5);
    expect(serie).toHaveLength(5);
  });

  it("ignora semanas sin days (respuesta 202 parcial)", () => {
    const rotas = [{ week: lunes9jun, total: 0 } as SemanaActividad];
    expect(serieDiaria(rotas, lunes9jun * 1000 + 1)).toHaveLength(0);
  });
});

describe("actividadPorDia", () => {
  it("agrega commits por día y reordena a [Lun..Dom]", () => {
    // punch_card: [dia(0=domingo), hora, commits]
    const filas = [
      [0, 10, 5], // domingo
      [0, 11, 2], // domingo
      [1, 9, 7], // lunes
      [6, 22, 3], // sábado
    ];
    const r = actividadPorDia(filas);
    // [Lun, Mar, Mié, Jue, Vie, Sáb, Dom]
    expect(r).toEqual([7, 0, 0, 0, 0, 3, 7]);
  });

  it("null con entrada vacía o ausente (202 de GitHub)", () => {
    expect(actividadPorDia([])).toBeNull();
    expect(actividadPorDia(null)).toBeNull();
    expect(actividadPorDia(undefined)).toBeNull();
  });
});

describe("topLenguajes", () => {
  it("calcula porcentajes y agrupa el resto en Otros", () => {
    const r = topLenguajes(
      { Python: 700, TypeScript: 200, CSS: 50, HTML: 30, Shell: 15, Vim: 5 },
      3,
    );
    expect(r?.[0]).toEqual({ nombre: "Python", porcentaje: 70 });
    expect(r?.[1].nombre).toBe("TypeScript");
    expect(r?.[3].nombre).toBe("Otros");
    expect(r?.[3].porcentaje).toBe(5);
    // Los porcentajes suman ~100.
    const suma = r!.reduce((a, l) => a + l.porcentaje, 0);
    expect(Math.abs(suma - 100)).toBeLessThan(0.5);
  });

  it("null sin datos", () => {
    expect(topLenguajes(null)).toBeNull();
    expect(topLenguajes({})).toBeNull();
  });
});

describe("promedioHorasMerge", () => {
  it("promedia horas apertura→merge sobre toda la muestra", () => {
    const prs = [
      { created_at: "2026-06-09T08:00:00Z", merged_at: "2026-06-10T09:00:00Z" }, // 25h
      { created_at: "2026-06-08T08:00:00Z", merged_at: "2026-06-08T11:00:00Z" }, // 3h
      { created_at: "2026-06-01T08:00:00Z", merged_at: null }, // cerrado sin merge: fuera
    ];
    expect(promedioHorasMerge(prs)).toBe(14);
  });

  it("null sin PRs mergeados", () => {
    expect(promedioHorasMerge([])).toBeNull();
    expect(
      promedioHorasMerge([{ created_at: "2026-06-01T08:00:00Z", merged_at: null }]),
    ).toBeNull();
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
  // El segundo parámetro va tipado para que `mock.calls` sea una tupla de
  // largo 2 y el test de headers compile con tsc --noEmit.
  return vi.fn(async (url: string, init?: { headers: Record<string, string> }) => {
    void init;
    const u = String(url);
    if (u.includes("/search/issues")) {
      return respuesta({ total_count: 5 });
    }
    if (u.includes("api.render.com")) {
      return respuesta([
        {
          deploy: {
            id: "dep-2",
            status: "live",
            createdAt: "2026-06-10T10:00:00Z",
            finishedAt: "2026-06-10T10:04:00Z",
            commit: { id: "659977cff", message: "Merge #75" },
          },
        },
        {
          deploy: {
            id: "dep-1",
            status: "deactivated",
            createdAt: "2026-06-09T10:00:00Z",
            finishedAt: "2026-06-09T10:01:30Z",
            commit: { id: "aaa977cff", message: "Merge #74" },
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
      return respuesta([{ name: "main" }, { name: "dev" }, { name: "feat/x" }]);
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
    if (u.includes("/stats/commit_activity")) {
      // 52 semanas; total = índice para poder asertar slice(-12).
      const base = Math.floor(Date.now() / 1000) - 52 * 7 * 86_400;
      return respuesta(
        Array.from({ length: 52 }, (_, i) => ({
          week: base + i * 7 * 86_400,
          days: [i, 0, 0, 0, 0, 0, 0],
          total: i,
        })),
      );
    }
    if (u.includes("/stats/punch_card")) {
      return respuesta([
        [0, 10, 4],
        [1, 9, 6],
      ]);
    }
    if (u.includes("/languages")) {
      return respuesta({ Python: 800, TypeScript: 200 });
    }
    if (u.match(/\/actions\/runs\/\d+\/jobs/)) {
      return respuesta({
        jobs: [
          {
            steps: [
              {
                name: "Set up job",
                status: "completed",
                conclusion: "success",
                started_at: "2026-06-10T10:00:00Z",
                completed_at: "2026-06-10T10:00:05Z",
              },
              {
                name: "Correr pytest",
                status: "completed",
                conclusion: "success",
                started_at: "2026-06-10T10:00:05Z",
                completed_at: "2026-06-10T10:02:35Z",
              },
            ],
          },
        ],
      });
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
    expect(data.repo?.nombres_ramas).toContain("main");
    // velocity = totales de las últimas 12 semanas (índices 40..51)
    expect(data.velocity).toHaveLength(12);
    expect(data.velocity?.[11]).toBe(51);
    // serie diaria presente y sin días futuros
    expect(data.velocity_diaria?.length).toBeGreaterThan(0);
    expect(data.velocity_diaria!.length).toBeLessThanOrEqual(30);
    // actividad por día [Lun..Dom]: lunes=6, domingo=4
    expect(data.actividad_semanal).toEqual([6, 0, 0, 0, 0, 0, 4]);
    expect(data.lenguajes?.[0]).toEqual({ nombre: "Python", porcentaje: 80 });
    expect(data.ci?.[0].conclusion).toBe("success");
    expect(data.ci?.[0].duracion_segundos).toBe(180);
    expect(data.ci_pasos?.[1].nombre).toBe("Correr pytest");
    expect(data.ci_pasos?.[1].duracion_segundos).toBe(150);
    expect(data.deploys?.web?.actual?.estado).toBe("live");
    // duraciones viejo→nuevo: [90s (dep-1), 240s (dep-2)]
    expect(data.deploys?.web?.duraciones).toEqual([90, 240]);
    expect(data.prs_abiertos?.[0].numero).toBe(76);
    // Solo PRs con merged_at cuentan como mergeados
    expect(data.prs_merged?.map((p) => p.numero)).toEqual([75]);
    // Conteo 7d exacto desde la Search API
    expect(data.prs_merged_7d).toBe(5);
    // PR 75: abierto 06-09T08, mergeado 06-10T09 → 25h de promedio
    expect(data.merge_horas_prom).toBe(25);
    expect(data.commits?.[0].sha_corto).toBe("c575878");
    expect(data.commits?.[0].mensaje).toBe("feat(automation): ejecutor HIGH");
  });

  it("manda el token de GitHub en Authorization y nunca en el payload", async () => {
    const fetchMock = mockApisOk();
    vi.stubGlobal("fetch", fetchMock);
    const data = await fetchPanelData();

    const llamadaGitHub = fetchMock.mock.calls.find(([u]) =>
      String(u).includes("api.github.com"),
    );
    expect(llamadaGitHub).toBeDefined();
    const headers = llamadaGitHub![1]?.headers;
    expect(headers?.Authorization).toBe("Bearer gh-token-test");

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
    expect(data.lenguajes).toBeNull();
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
        return {
          ok: false,
          status: 500,
          json: async () => ({}),
          headers: { get: () => null },
        };
      }),
    );

    const data = await fetchPanelData();
    expect(data.repo).toBeNull();
    expect(data.ci).toBeNull();
    expect(data.deploys?.web?.actual?.estado).toBe("live");
    expect(data.errores.some((e) => e.includes("HTTP 500"))).toBe(true);
  });

  it("stats en 202 (sin body computado) dejan velocity/actividad en null", async () => {
    const base = mockApisOk();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        const u = String(url);
        if (u.includes("/stats/commit_activity") || u.includes("/stats/punch_card")) {
          return respuesta({}); // GitHub computando: body vacío
        }
        return base(url);
      }),
    );
    const data = await fetchPanelData();
    expect(data.velocity).toBeNull();
    expect(data.velocity_diaria).toBeNull();
    expect(data.actividad_semanal).toBeNull();
    expect(data.repo?.total_commits).toBe(512);
  });

  it("fallo en los jobs del último run no tumba la sección CI", async () => {
    const base = mockApisOk();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (String(url).match(/\/actions\/runs\/\d+\/jobs/)) {
          return {
            ok: false,
            status: 500,
            json: async () => ({}),
            headers: { get: () => null },
          };
        }
        return base(url);
      }),
    );
    const data = await fetchPanelData();
    expect(data.ci?.[0].conclusion).toBe("success");
    expect(data.ci_pasos).toBeNull();
    // El fallo de steps no cuenta como error de sección (decorativo).
    expect(data.errores).toEqual([]);
  });
});
