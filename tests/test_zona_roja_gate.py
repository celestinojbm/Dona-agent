"""Gate de zona roja (.github/workflows/zona-roja.yml).

Ejecuta el script `run:` real del workflow con bash contra un `gh` falso que
guarda el estado de la PR (archivos, etiquetas, commit statuses) en un JSON.
Así se prueba la lógica del gate sin GitHub: qué es rojo, cuándo vale la
etiqueta `human-reviewed` y cuándo caduca.

Regresión principal: la caducidad de la etiqueta dependía de que corriera la
ejecución de `synchronize`; con `cancel-in-progress` un evento posterior
(`edited` al actualizar la descripción) la cancelaba y la etiqueta vieja
aprobaba un diff que nadie revisó. Ahora la etiqueta solo vale con un sello
(commit status) sobre el SHA de cabeza actual.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parent.parent
WORKFLOW = RAIZ / ".github" / "workflows" / "zona-roja.yml"
DOC = RAIZ / "docs" / "ops" / "zonificacion-autonomia.md"

ETIQUETA = "human-reviewed"
CONTEXTO = "zona-roja/revision-humana"
REPO = "dueno/repo"
PR = "7"
SHA_A = "a" * 40
SHA_B = "b" * 40

pytestmark = pytest.mark.skipif(
    shutil.which("jq") is None or shutil.which("bash") is None,
    reason="el gate usa bash y jq (presentes en ubuntu-latest)",
)

# `gh` falso: solo las llamadas que usa el gate. Estado en $FAKE_GH_ESTADO.
_FAKE_GH = r'''
import json, os, subprocess, sys

ruta = os.environ["FAKE_GH_ESTADO"]
with open(ruta) as f:
    estado = json.load(f)

args = sys.argv[1:]
assert args and args[0] == "api", args
args = args[1:]
metodo, jq_expr, campos, path = "GET", None, {}, None
while args:
    a = args.pop(0)
    if a == "--paginate":
        continue
    if a == "-X":
        metodo = args.pop(0)
    elif a == "--jq":
        jq_expr = args.pop(0)
    elif a == "-f":
        k, v = args.pop(0).split("=", 1)
        campos[k] = v
    else:
        path = a
path = path.split("?", 1)[0]
estado.setdefault("llamadas", []).append([metodo, path])
pr = estado["pr"]
pref = "repos/" + estado["repo"] + "/"
assert path.startswith(pref), path
rel = path[len(pref):]
num = str(pr["number"])

def guardar():
    with open(ruta, "w") as f:
        json.dump(estado, f)

if metodo == "GET" and rel == "pulls/" + num:
    salida = pr
elif metodo == "GET" and rel == "pulls/" + num + "/files":
    salida = estado["files"]
elif metodo == "GET" and rel == "issues/" + num + "/labels":
    salida = [{"name": n} for n in estado["labels"]]
elif metodo == "DELETE" and rel.startswith("issues/" + num + "/labels/"):
    nombre = rel.rsplit("/", 1)[1]
    if nombre not in estado["labels"]:
        guardar()
        sys.exit(1)
    estado["labels"].remove(nombre)
    salida = []
elif metodo == "GET" and rel.startswith("commits/") and rel.endswith("/statuses"):
    salida = estado["statuses"].get(rel.split("/")[1], [])
elif metodo == "POST" and rel.startswith("statuses/"):
    sha = rel.split("/")[1]
    nuevo = dict(campos, creator={"login": estado.get("sellador", "github-actions[bot]")})
    estado["statuses"].setdefault(sha, []).insert(0, nuevo)  # el más nuevo primero
    salida = nuevo
else:
    sys.exit("llamada no soportada: %s %s" % (metodo, path))
guardar()

texto = json.dumps(salida)
if jq_expr is not None:
    texto = subprocess.run(["jq", "-r", jq_expr], input=texto, capture_output=True,
                           text=True, check=True).stdout
    sys.stdout.write(texto)
else:
    print(texto)
'''


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _paso() -> dict:
    (job,) = _workflow()["jobs"].values()
    (paso,) = job["steps"]
    return paso


def _archivo(nombre: str, *, status: str = "modified", patch: str | None = "@@ -1 +1 @@\n-x\n+y",
             previo: str | None = None) -> dict:
    a = {"filename": nombre, "status": status, "patch": patch}
    if previo:
        a["previous_filename"] = previo
    return a


class Gate:
    """Estado de una PR + ejecuciones sucesivas del gate sobre ese estado."""

    def __init__(self, tmp_path: Path, archivos: list[dict], *, labels=(), sha=SHA_A,
                 base="main", changed_files=None):
        self.dir = tmp_path
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        fake = tmp_path / "fake_gh.py"
        fake.write_text(_FAKE_GH, encoding="utf-8")
        gh = bin_dir / "gh"
        gh.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{fake}" "$@"\n', encoding="utf-8")
        gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
        self.bin_dir = bin_dir
        self.ejecuciones = 0
        self.ruta_estado = tmp_path / "estado.json"
        self.estado = {
            "repo": REPO,
            "pr": {"number": int(PR), "head": {"sha": sha}, "base": {"ref": base},
                   "changed_files": len(archivos) if changed_files is None else changed_files},
            "files": archivos,
            "labels": list(labels),
            "statuses": {},
        }
        self._guardar()

    def _guardar(self):
        self.ruta_estado.write_text(json.dumps(self.estado), encoding="utf-8")

    def _cargar(self):
        self.estado = json.loads(self.ruta_estado.read_text(encoding="utf-8"))

    # Mutaciones "humanas" o de GitHub entre ejecuciones.
    def push(self, sha: str):
        self._cargar()
        self.estado["pr"]["head"]["sha"] = sha
        self._guardar()

    def poner_etiqueta(self):
        self._cargar()
        if ETIQUETA not in self.estado["labels"]:
            self.estado["labels"].append(ETIQUETA)
        self._guardar()

    def cambiar_base(self, base: str):
        self._cargar()
        self.estado["pr"]["base"]["ref"] = base
        self._guardar()

    def forjar_status(self, sha: str, *, state="success", description="Revisión humana · base=main",
                      creador="github-actions[bot]"):
        self._cargar()
        self.estado["statuses"].setdefault(sha, []).insert(0, {
            "state": state, "context": CONTEXTO, "description": description,
            "creator": {"login": creador},
        })
        self._guardar()

    @property
    def etiquetas(self) -> list[str]:
        self._cargar()
        return self.estado["labels"]

    def sellos(self, sha: str) -> list[dict]:
        self._cargar()
        return [s for s in self.estado["statuses"].get(sha, []) if s["context"] == CONTEXTO]

    def correr(self, accion: str, *, sha_evento: str | None = None, etiqueta: str = "",
               emisor: str = "User", base_anterior: str = "") -> subprocess.CompletedProcess:
        self._cargar()
        self.ejecuciones += 1
        trabajo = self.dir / f"run-{self.ejecuciones}"
        trabajo.mkdir()
        env = {
            "PATH": f"{self.bin_dir}{os.pathsep}{os.environ['PATH']}",
            "HOME": str(self.dir),
            "FAKE_GH_ESTADO": str(self.ruta_estado),
            "GH_TOKEN": "falso",
            "REPO": REPO,
            "PR": PR,
            "ACCION": accion,
            "BASE_ANTERIOR": base_anterior,
            "SHA_EVENTO": sha_evento or self.estado["pr"]["head"]["sha"],
            "ETIQUETA_EVENTO": etiqueta,
            "TIPO_EMISOR": emisor,
        }
        return subprocess.run(["bash", "-e", "-c", _paso()["run"]], cwd=trabajo, env=env,
                              capture_output=True, text=True, timeout=60)


ROJO = _archivo("agent/billing.py")
VERDE = _archivo("agent/observability.py")


# ── Estructura del workflow ────────────────────────────────────────────────


class TestEstructura:
    def test_corre_con_pull_request_target(self):
        on = _workflow()[True]  # YAML 1.1: la clave `on` se lee como True
        assert list(on) == ["pull_request_target"]
        assert {"synchronize", "labeled", "edited"} <= set(on["pull_request_target"]["types"])

    def test_no_cancela_ejecuciones_en_curso(self):
        assert _workflow()["concurrency"]["cancel-in-progress"] is False

    def test_permisos_minimos(self):
        assert _workflow()["permissions"] == {
            "contents": "read", "pull-requests": "write", "statuses": "write",
        }

    def test_no_hace_checkout_ni_interpola_expresiones_en_el_script(self):
        (job,) = _workflow()["jobs"].values()
        assert all("uses" not in paso for paso in job["steps"])
        # Datos del evento (nombre de etiqueta, ramas) solo por env: nunca
        # `${{ }}` dentro del script (inyección de comandos).
        assert "${{" not in _paso()["run"]

    def test_lista_roja_coincide_con_la_doc(self):
        run = _paso()["run"]
        bloque = run.split("<<'EOF'\n", 1)[1].split("\nEOF", 1)[0]
        rojos = {linea.strip() for linea in bloque.splitlines() if linea.strip()}
        doc = DOC.read_text(encoding="utf-8")
        faltan = sorted(r for r in rojos if f"`{r}`" not in doc)
        assert not faltan, f"rutas rojas del workflow sin documentar en §3: {faltan}"


# ── Qué es rojo ────────────────────────────────────────────────────────────


class TestDeteccion:
    def test_pr_verde_pasa(self, tmp_path):
        r = Gate(tmp_path, [VERDE]).correr("opened")
        assert r.returncode == 0, r.stdout + r.stderr
        assert "no modifica archivos de la zona ROJA" in r.stdout

    @pytest.mark.parametrize("archivo", [
        ROJO,
        _archivo("agent/nuevo.py", status="renamed", previo="agent/billing.py"),
        _archivo(".github/workflows/tests.yml"),
        _archivo("pytest.ini"),
        _archivo("landing/app/api/automation/acciones/[id]/high-confirmar/route.ts"),
    ])
    def test_rojo_sin_etiqueta_falla(self, tmp_path, archivo):
        r = Gate(tmp_path, [archivo]).correr("opened")
        assert r.returncode == 1, r.stdout + r.stderr
        assert "zona ROJA" in r.stdout

    def test_workflow_auxiliar_verde_pasa(self, tmp_path):
        r = Gate(tmp_path, [_archivo(".github/workflows/agent-runs-validation.yml")]).correr("opened")
        assert r.returncode == 0, r.stdout + r.stderr

    def test_quitar_assert_en_test_protegido_es_rojo(self, tmp_path):
        a = _archivo("tests/test_billing.py", patch="@@ -1,2 +1,1 @@\n-    assert saldo == 10\n x = 1")
        assert Gate(tmp_path, [a]).correr("opened").returncode == 1

    def test_anadir_cobertura_a_test_protegido_es_verde(self, tmp_path):
        a = _archivo("tests/test_billing.py",
                     patch="@@ -1 +1,3 @@\n x = 1\n+def test_nuevo():\n+    assert 1 == 1")
        assert Gate(tmp_path, [a]).correr("opened").returncode == 0

    @pytest.mark.parametrize("linea", [
        "pytestmark = pytest.mark.skip",
        "@pytest.mark.skip(reason='luego')",
        "@pytest.mark.skipif(True, reason='x')",
        "@pytest.mark.xfail",
        "    pytest.skip('x')",
        "pytest.importorskip('modulo_inexistente')",
    ])
    def test_saltar_test_protegido_sin_quitar_asserts_es_rojo(self, tmp_path, linea):
        a = _archivo("tests/test_tcpa_stop.py", patch=f"@@ -1 +1,2 @@\n+{linea}\n x = 1")
        r = Gate(tmp_path, [a]).correr("opened")
        assert r.returncode == 1, r.stdout + r.stderr
        assert "tests/test_tcpa_stop.py" in r.stdout

    @pytest.mark.parametrize("linea", [
        "collect_ignore = ['test_billing.py']",
        "def pytest_collection_modifyitems(config, items):",
        "-    pytest.skip('solo en local')",
    ])
    def test_conftest_que_toca_la_recoleccion_es_rojo(self, tmp_path, linea):
        patch = f"@@ -1 +1 @@\n{linea}" if linea.startswith("-") else f"@@ -1 +1,2 @@\n+{linea}"
        a = _archivo("tests/conftest.py", patch=patch)
        assert Gate(tmp_path, [a]).correr("opened").returncode == 1

    def test_conftest_con_fixture_nueva_es_verde(self, tmp_path):
        a = _archivo("tests/conftest.py", patch="@@ -1 +1,3 @@\n+@pytest.fixture\n+def cliente():\n+    return 1")
        assert Gate(tmp_path, [a]).correr("opened").returncode == 0

    def test_lista_de_archivos_incompleta_falla_cerrado(self, tmp_path):
        # La API corta en 3000 archivos: lo no listado podría ser rojo.
        r = Gate(tmp_path, [VERDE], changed_files=3500).correr("opened")
        assert r.returncode == 1, r.stdout + r.stderr
        assert "lista de archivos incompleta" in r.stdout


# ── La etiqueta y su sello ─────────────────────────────────────────────────


class TestSello:
    def test_etiqueta_de_persona_sella_y_pasa(self, tmp_path):
        g = Gate(tmp_path, [ROJO], labels=[ETIQUETA])
        r = g.correr("labeled", etiqueta=ETIQUETA)
        assert r.returncode == 0, r.stdout + r.stderr
        (sello,) = g.sellos(SHA_A)
        assert sello["state"] == "success"
        assert sello["description"] == "Revisión humana · base=main"

    def test_tras_sellar_editar_la_pr_sigue_pasando(self, tmp_path):
        g = Gate(tmp_path, [ROJO], labels=[ETIQUETA])
        assert g.correr("labeled", etiqueta=ETIQUETA).returncode == 0
        r = g.correr("edited")
        assert r.returncode == 0, r.stdout + r.stderr
        assert ETIQUETA in g.etiquetas

    def test_push_caduca_aunque_no_corra_synchronize(self, tmp_path):
        """Regresión: push + edición inmediata de la descripción. La ejecución
        de `synchronize` se cancela; la de `edited` no debe aprobar el SHA
        nuevo con la etiqueta vieja."""
        g = Gate(tmp_path, [ROJO], labels=[ETIQUETA])
        assert g.correr("labeled", etiqueta=ETIQUETA).returncode == 0
        g.push(SHA_B)
        r = g.correr("edited")  # la de synchronize nunca corrió
        assert r.returncode == 1, r.stdout + r.stderr
        assert ETIQUETA not in g.etiquetas
        assert "no tiene sello" in r.stdout

    def test_push_caduca_en_synchronize(self, tmp_path):
        g = Gate(tmp_path, [ROJO], labels=[ETIQUETA])
        assert g.correr("labeled", etiqueta=ETIQUETA).returncode == 0
        g.push(SHA_B)
        assert g.correr("synchronize").returncode == 1
        assert ETIQUETA not in g.etiquetas

    def test_otra_etiqueta_tras_push_no_revalida(self, tmp_path):
        g = Gate(tmp_path, [ROJO], labels=[ETIQUETA])
        assert g.correr("labeled", etiqueta=ETIQUETA).returncode == 0
        g.push(SHA_B)
        assert g.correr("labeled", etiqueta="zona-gris").returncode == 1

    def test_volver_a_etiquetar_tras_push_sella_el_nuevo_sha(self, tmp_path):
        g = Gate(tmp_path, [ROJO], labels=[ETIQUETA])
        assert g.correr("labeled", etiqueta=ETIQUETA).returncode == 0
        g.push(SHA_B)
        assert g.correr("synchronize").returncode == 1
        g.poner_etiqueta()
        assert g.correr("labeled", etiqueta=ETIQUETA).returncode == 0
        assert g.correr("edited").returncode == 0

    def test_etiqueta_sin_sello_falla_y_se_retira(self, tmp_path):
        # Etiqueta puesta antes de este gate, o cuya ejecución de 'labeled' no corrió.
        g = Gate(tmp_path, [ROJO], labels=[ETIQUETA])
        assert g.correr("edited").returncode == 1
        assert ETIQUETA not in g.etiquetas

    @pytest.mark.parametrize("emisor", ["Bot", "Organization", ""])
    def test_etiqueta_puesta_por_bot_no_sella(self, tmp_path, emisor):
        g = Gate(tmp_path, [ROJO], labels=[ETIQUETA])
        r = g.correr("labeled", etiqueta=ETIQUETA, emisor=emisor)
        assert r.returncode == 1, r.stdout + r.stderr
        assert g.sellos(SHA_A) == []
        assert ETIQUETA not in g.etiquetas

    def test_push_entre_etiqueta_y_ejecucion_no_sella_el_sha_nuevo(self, tmp_path):
        # Se etiquetó viendo SHA_A; cuando corre el gate la cabeza ya es SHA_B.
        g = Gate(tmp_path, [ROJO], labels=[ETIQUETA], sha=SHA_B)
        r = g.correr("labeled", etiqueta=ETIQUETA, sha_evento=SHA_A)
        assert r.returncode == 1, r.stdout + r.stderr
        assert g.sellos(SHA_B) == []

    def test_cambio_de_base_invalida_el_sello(self, tmp_path):
        g = Gate(tmp_path, [ROJO], labels=[ETIQUETA])
        assert g.correr("labeled", etiqueta=ETIQUETA).returncode == 0
        g.cambiar_base("otra")
        assert g.correr("edited", base_anterior="main").returncode == 1
        assert ETIQUETA not in g.etiquetas
        assert g.sellos(SHA_A)[0]["state"] == "failure"

    def test_base_aflojada_con_sello_forjado_no_pasa_al_volver_a_main(self, tmp_path):
        """Ataque de #327: apuntar la PR a una rama con un gate aflojado que
        sella el SHA, y volver a main. El cambio de base invalida el sello."""
        g = Gate(tmp_path, [ROJO], labels=[ETIQUETA], base="evil")
        g.forjar_status(SHA_A)  # lo dejaría el gate aflojado de 'evil'
        g.cambiar_base("main")
        assert g.correr("edited", base_anterior="evil").returncode == 1
        assert g.correr("edited").returncode == 1

    def test_sello_de_otra_base_no_vale(self, tmp_path):
        g = Gate(tmp_path, [ROJO], labels=[ETIQUETA])
        g.forjar_status(SHA_A, description="Revisión humana · base=otra")
        assert g.correr("edited").returncode == 1

    def test_sello_de_otra_cuenta_no_vale(self, tmp_path):
        g = Gate(tmp_path, [ROJO], labels=[ETIQUETA])
        g.forjar_status(SHA_A, creador="celestino-o-un-agente")
        assert g.correr("edited").returncode == 1

    def test_manda_el_ultimo_estado_del_contexto(self, tmp_path):
        g = Gate(tmp_path, [ROJO], labels=[ETIQUETA])
        g.forjar_status(SHA_A)
        g.forjar_status(SHA_A, state="failure")
        assert g.correr("edited").returncode == 1

    def test_rojo_sin_etiqueta_no_sella(self, tmp_path):
        g = Gate(tmp_path, [ROJO])
        assert g.correr("labeled", etiqueta="otra").returncode == 1
        assert g.sellos(SHA_A) == []
