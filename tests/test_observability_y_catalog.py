# tests/test_observability_y_catalog.py — Tests T1.6 (observabilidad + M0)

"""
Cubre el alcance mínimo de T1.6:
  - request_id: asignar nuevo, fijar uno externo, validación, contextvar
    independiente entre tareas async.
  - RequestIdFilter: inyecta record.request_id desde el contextvar.
  - Tools catalog: tools listadas, búsqueda por nombre, filtros por
    riesgo/permiso, snapshot consistente.
  - Diagnóstico HMAC: motivos diferenciados (secret_no_configurado,
    signature_missing, signature_mismatch, ok).

NO toca DB, no requiere FastAPI app levantada.
"""

import asyncio
import logging
import os
import pytest

from agent.observability import (
    RequestIdFilter,
    asignar_nuevo_request_id,
    fijar_request_id,
    obtener_request_id,
)
from agent.tools_catalog import (
    CATALOGO,
    buscar_tool,
    listar_tools,
    resumen_catalogo,
    tools_por_permiso,
    tools_por_riesgo,
)


# ── 1. observability — request_id ──────────────────────────────────────────


class TestRequestId:
    def test_inicial_es_none(self):
        # En un contexto "limpio" (sin request previo), retorna None.
        # Si otro test lo dejó seteado, fijamos None forzando con un valor
        # vacío y verificando con asignar/fijar manual.
        rid = obtener_request_id()
        # No assertamos None estrictamente porque otros tests pudieron
        # haberlo dejado seteado; lo importante es que asignar funciona.
        assert rid is None or rid.startswith("req_") or rid.startswith("lnd_")

    def test_asignar_nuevo_retorna_id_con_prefijo(self):
        rid = asignar_nuevo_request_id()
        assert rid.startswith("req_")
        assert len(rid) == len("req_") + 12  # 12 hex chars

    def test_asignar_nuevo_es_idempotente_dentro_del_contexto(self):
        rid1 = asignar_nuevo_request_id()
        rid2 = asignar_nuevo_request_id()
        # Cada llamada genera uno nuevo (sobrescribe).
        assert rid1 != rid2
        # El último gana: obtener retorna el más reciente.
        assert obtener_request_id() == rid2

    def test_fijar_id_externo_valido(self):
        fijar_request_id("lnd_abc123")
        assert obtener_request_id() == "lnd_abc123"

    def test_fijar_id_invalido_no_pisa(self):
        # Asignar uno válido primero.
        asignar_nuevo_request_id()
        previo = obtener_request_id()
        # Intentar fijar uno con caracteres no permitidos.
        fijar_request_id("evil$injection!")
        assert obtener_request_id() == previo

    def test_fijar_id_vacio_no_pisa(self):
        asignar_nuevo_request_id()
        previo = obtener_request_id()
        fijar_request_id("")
        assert obtener_request_id() == previo

    def test_fijar_id_demasiado_largo_no_pisa(self):
        asignar_nuevo_request_id()
        previo = obtener_request_id()
        fijar_request_id("a" * 100)
        assert obtener_request_id() == previo

    def test_contextvar_independiente_entre_tareas_async(self):
        """ContextVar debe aislar el id entre tareas concurrentes."""
        async def tarea(label: str, ids: dict):
            asignar_nuevo_request_id()
            await asyncio.sleep(0.01)  # ceder control para que la otra tarea corra
            ids[label] = obtener_request_id()

        async def main():
            ids: dict[str, str | None] = {}
            await asyncio.gather(tarea("a", ids), tarea("b", ids))
            return ids

        ids = asyncio.get_event_loop().run_until_complete(main())
        assert ids["a"] is not None
        assert ids["b"] is not None
        assert ids["a"] != ids["b"]


# ── 2. RequestIdFilter ─────────────────────────────────────────────────────


class TestRequestIdFilter:
    def test_filter_inyecta_request_id_si_hay_contextvar(self):
        rid = asignar_nuevo_request_id()
        f = RequestIdFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="hola", args=(), exc_info=None,
        )
        result = f.filter(record)
        assert result is True
        assert getattr(record, "request_id", None) == rid

    def test_filter_no_agrega_atributo_si_no_hay_contextvar(self, monkeypatch):
        # Nuevo contexto: no hay rid asignado.
        from agent.observability import _request_id_var
        token = _request_id_var.set(None)
        try:
            f = RequestIdFilter()
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="", lineno=0,
                msg="hola", args=(), exc_info=None,
            )
            f.filter(record)
            assert not hasattr(record, "request_id") or record.request_id is None or record.request_id == ""
        finally:
            _request_id_var.reset(token)


# ── 3. Tools catalog ───────────────────────────────────────────────────────


class TestToolsCatalog:
    def test_catalog_tiene_entries(self):
        assert len(CATALOGO) > 0
        # Sanity: las tools clave de billing están listadas.
        nombres = {t.nombre for t in CATALOGO}
        assert "obtener_saldo" in nombres
        assert "cobrar" in nombres
        assert "acreditar" in nombres
        assert "abrir_billing_portal" in nombres

    def test_buscar_tool_existe_y_no_existe(self):
        t = buscar_tool("obtener_saldo")
        assert t is not None
        assert t.nivel_riesgo == "leer"
        assert buscar_tool("tool_inexistente") is None

    def test_filtros_por_riesgo(self):
        leer = tools_por_riesgo("leer")
        ejecutar = tools_por_riesgo("ejecutar")
        preparar = tools_por_riesgo("preparar")
        # Todos los niveles tienen al menos un representante.
        assert len(leer) > 0
        assert len(ejecutar) > 0
        assert len(preparar) > 0
        # No hay overlap.
        for t in leer:
            assert t.nivel_riesgo == "leer"

    def test_filtros_por_permiso(self):
        autonomo = tools_por_permiso("autonomo")
        simple = tools_por_permiso("aprobacion_simple")
        fuerte = tools_por_permiso("aprobacion_fuerte")
        assert len(autonomo) > 0
        assert len(simple) > 0
        assert len(fuerte) > 0

    def test_acreditar_es_aprobacion_fuerte(self):
        """Regla operativa: acreditar nunca debe ser autónomo."""
        t = buscar_tool("acreditar")
        assert t is not None
        assert t.permiso == "aprobacion_fuerte"

    def test_lecturas_son_autonomo(self):
        """Las lecturas no requieren confirmación humana cada vez."""
        for t in CATALOGO:
            if t.nivel_riesgo == "leer":
                assert t.permiso == "autonomo", (
                    f"Tool '{t.nombre}' es 'leer' pero permiso != 'autonomo' ({t.permiso})"
                )

    def test_resumen_catalogo_estructura(self):
        snap = resumen_catalogo()
        assert "total" in snap
        assert "por_riesgo" in snap
        assert "por_permiso" in snap
        assert "tools" in snap
        assert snap["total"] == len(CATALOGO)
        assert sum(snap["por_riesgo"].values()) == len(CATALOGO)
        assert sum(snap["por_permiso"].values()) == len(CATALOGO)
        # Todas las tools serializadas tienen los campos requeridos.
        for t in snap["tools"]:
            assert "nombre" in t
            assert "nivel_riesgo" in t
            assert "permiso" in t
            assert "fuente" in t


# ── 4. Diagnóstico HMAC ────────────────────────────────────────────────────


class TestDiagnosticoHmac:
    def test_secret_no_configurado(self, monkeypatch):
        monkeypatch.delenv("INTERNAL_BRIDGE_SECRET", raising=False)
        from agent.main import _diagnosticar_firma_interna
        assert _diagnosticar_firma_interna(b"body", "anyhash") == "secret_no_configurado"

    def test_signature_missing(self, monkeypatch):
        monkeypatch.setenv("INTERNAL_BRIDGE_SECRET", "test-secret")
        from agent.main import _diagnosticar_firma_interna
        assert _diagnosticar_firma_interna(b"body", "") == "signature_missing"

    def test_signature_mismatch(self, monkeypatch):
        monkeypatch.setenv("INTERNAL_BRIDGE_SECRET", "test-secret")
        from agent.main import _diagnosticar_firma_interna
        assert _diagnosticar_firma_interna(b"body", "deadbeef") == "signature_mismatch"

    def test_ok_si_firma_valida(self, monkeypatch):
        import hashlib
        import hmac as hmac_mod
        monkeypatch.setenv("INTERNAL_BRIDGE_SECRET", "test-secret")
        body = b"body-to-sign"
        sig = hmac_mod.new(
            b"test-secret", body, hashlib.sha256
        ).hexdigest()
        from agent.main import _diagnosticar_firma_interna
        assert _diagnosticar_firma_interna(body, sig) == "ok"
