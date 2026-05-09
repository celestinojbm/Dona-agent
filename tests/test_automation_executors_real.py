# tests/test_automation_executors_real.py — T2.1.C · Ejecutores reales

"""
Verifica que los ejecutores T2.1.C:
  - Usan LLM cuando está disponible (mock)
  - Caen a fallback determinístico cuando LLM falla
  - Sanitizan inputs (perfil) y outputs
  - Truncan strings al límite de cada formato
  - HIGH siguen sin ejecutor → execution.ejecutar_accion los rechaza
  - CRITICAL siguen bloqueados
  - Audit log incluye modo (llm|fallback) sin PII
  - construir_contexto_perfil omite campos vacíos y trunca

NO se hacen llamadas reales al LLM · usamos monkeypatch.
"""

import importlib
import json
import pytest

import agent.memory


@pytest.fixture
async def db(tmp_path, monkeypatch):
    db_path = tmp_path / "exec_real.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")
    import agent.business.models as _bm
    import agent.automation.models as _am
    import agent.automation.audit as _au
    import agent.automation.action_center as _ac
    import agent.automation.prompts as _pr
    import agent.automation.execution as _ex
    importlib.reload(agent.memory)
    importlib.reload(_bm)
    importlib.reload(_am)
    importlib.reload(_au)
    importlib.reload(_ac)
    importlib.reload(_pr)
    importlib.reload(_ex)
    await agent.memory.inicializar_db()
    return _ex, _ac, _pr


PERFIL_DEMO = {
    "nombre_negocio": "Pastelería Demo",
    "industria": "comida",
    "moneda": "MXN",
    "meta_mensual": 50000.0,
    "oferta_principal": "Pasteles para eventos",
    "cliente_ideal": "Familias en CDMX",
    "objetivo_mes": "10 ventas nuevas",
    "canales_actuales": "WhatsApp, Instagram",
    "bloqueo_actual": "Tiempo para responder",
    "tareas_delegar": "seguimiento clientes",
}


def _patch_llm_returns(monkeypatch, value: str | None):
    """Mockea agent.llm.completar_con_sistema en el namespace del ejecutor."""
    import agent.automation.execution as _ex

    async def fake_completar(*args, **kwargs):
        return value

    # _llm_completar importa dentro de la función · monkeypatch del módulo
    # agent.llm directamente.
    import agent.llm
    monkeypatch.setattr(agent.llm, "completar_con_sistema", fake_completar)


# ─── construir_contexto_perfil · sanitización ───────────────────────────────


class TestContextoSanitizado:
    def test_perfil_vacio_retorna_placeholder(self, db):
        _, _, pr = db
        s = pr.construir_contexto_perfil(None)
        assert "no disponible" in s.lower() or "perfil" in s.lower()

    def test_omite_campos_vacios(self, db):
        _, _, pr = db
        s = pr.construir_contexto_perfil({
            "nombre_negocio": "Mi Tienda",
            "industria": "retail",
            "oferta_principal": "",  # debe omitirse
            "cliente_ideal": None,  # debe omitirse
            "moneda": "MXN",
        })
        assert "Mi Tienda" in s
        assert "retail" in s
        assert "MXN" in s
        # Campos vacíos NO aparecen
        assert "Oferta principal" not in s
        assert "Cliente ideal" not in s

    def test_trunca_campos_largos(self, db):
        _, _, pr = db
        big = "x" * 1000
        s = pr.construir_contexto_perfil({
            "nombre_negocio": "Test",
            "oferta_principal": big,
        })
        # Cap de 400 chars por campo
        assert "x" * 401 not in s


# ─── Ejecutores con LLM mock ───────────────────────────────────────────────


class TestEjecutorPlanSemanal:
    @pytest.mark.asyncio
    async def test_llm_devuelve_markdown(self, db, monkeypatch):
        ex, ac, _ = db
        _patch_llm_returns(monkeypatch, "# Plan semanal\n## Lunes\n- A\n- B")
        a = await ac.crear_accion(
            telefono="5551",
            tipo_accion="generar_plan_semanal",
            titulo="Plan semanal",
        )
        r = await ex.ejecutar_accion(a)
        assert r["estado_final"] == "completed"
        assert r["result"]["modo"] == "llm"
        assert "Plan semanal" in r["result"]["output_md"]

    @pytest.mark.asyncio
    async def test_llm_falla_usa_fallback(self, db, monkeypatch):
        ex, ac, _ = db
        _patch_llm_returns(monkeypatch, None)  # LLM retorna None
        a = await ac.crear_accion(
            telefono="5552",
            tipo_accion="generar_plan_semanal",
            titulo="Plan",
        )
        r = await ex.ejecutar_accion(a)
        assert r["estado_final"] == "completed"
        assert r["result"]["modo"] == "fallback"
        # Fallback útil: no es solo "(placeholder)"
        assert "(placeholder" not in r["result"]["output_md"]
        assert "Plan semanal" in r["result"]["output_md"]


class TestEjecutorCalendarioContenido:
    @pytest.mark.asyncio
    async def test_llm_devuelve_json_array(self, db, monkeypatch):
        ex, ac, _ = db
        json_resp = json.dumps([
            {"dia": i + 1, "titulo": f"T{i}", "copy_corto": "C",
             "formato": "post", "canal_sugerido": "whatsapp"}
            for i in range(7)
        ])
        _patch_llm_returns(monkeypatch, json_resp)
        a = await ac.crear_accion(
            telefono="5553",
            tipo_accion="generar_calendario_contenido",
            titulo="Cal",
        )
        r = await ex.ejecutar_accion(a)
        assert r["result"]["modo"] == "llm"
        assert len(r["result"]["calendario"]) == 7

    @pytest.mark.asyncio
    async def test_llm_devuelve_json_con_fences(self, db, monkeypatch):
        """LLM con ```json ... ``` se parsea correctamente."""
        ex, ac, _ = db
        json_resp = (
            "```json\n"
            + json.dumps([{"dia": 1, "titulo": "X", "copy_corto": "C",
                           "formato": "post", "canal_sugerido": "ig"}])
            + "\n```"
        )
        _patch_llm_returns(monkeypatch, json_resp)
        a = await ac.crear_accion(
            telefono="5554",
            tipo_accion="generar_calendario_contenido",
            titulo="Cal",
        )
        r = await ex.ejecutar_accion(a)
        assert r["result"]["modo"] == "llm"
        assert r["result"]["calendario"][0]["titulo"] == "X"

    @pytest.mark.asyncio
    async def test_llm_basura_usa_fallback(self, db, monkeypatch):
        ex, ac, _ = db
        _patch_llm_returns(monkeypatch, "esto no es JSON")
        a = await ac.crear_accion(
            telefono="5555",
            tipo_accion="generar_calendario_contenido",
            titulo="Cal",
        )
        r = await ex.ejecutar_accion(a)
        assert r["result"]["modo"] == "fallback"
        assert len(r["result"]["calendario"]) == 7


class TestEjecutorChecklistVentas:
    @pytest.mark.asyncio
    async def test_llm_parsea_lista_markdown(self, db, monkeypatch):
        ex, ac, _ = db
        _patch_llm_returns(monkeypatch,
            "- [ ] Revisar leads\n- [ ] Cobrar facturas\n- [ ] Subir post")
        a = await ac.crear_accion(
            telefono="5556",
            tipo_accion="generar_checklist_ventas",
            titulo="Check",
        )
        r = await ex.ejecutar_accion(a)
        assert r["result"]["modo"] == "llm"
        assert len(r["result"]["checklist"]) >= 3
        assert "Revisar leads" in r["result"]["checklist"][0]

    @pytest.mark.asyncio
    async def test_fallback_tiene_8_items(self, db, monkeypatch):
        ex, ac, _ = db
        _patch_llm_returns(monkeypatch, None)
        a = await ac.crear_accion(
            telefono="5557",
            tipo_accion="generar_checklist_ventas",
            titulo="Check",
        )
        r = await ex.ejecutar_accion(a)
        assert r["result"]["modo"] == "fallback"
        assert len(r["result"]["checklist"]) >= 8


class TestEjecutorAnalizarDiagnostico:
    @pytest.mark.asyncio
    async def test_llm_json_valido(self, db, monkeypatch):
        ex, ac, _ = db
        from agent.business.models import PerfilNegocio
        from datetime import datetime
        # Crear perfil completo
        async with agent.memory.async_session() as session:
            session.add(PerfilNegocio(
                telefono="5558", nombre_negocio="X", industria="otro",
                moneda="USD", meta_mensual=0,
                oferta_principal="A", cliente_ideal="B", objetivo_mes="C",
                canales_actuales="D", bloqueo_actual="E", tareas_delegar="F",
                creado=datetime.utcnow(), actualizado=datetime.utcnow(),
                onboarding_paso=None,
            ))
            await session.commit()
        _patch_llm_returns(monkeypatch, json.dumps({
            "completitud_pct": 100,
            "fortalezas": ["X1", "X2"],
            "oportunidades_clave": ["Y1"],
            "riesgos": ["Z1"],
            "recomendacion_inicial": "Generar plan semanal",
        }))
        a = await ac.crear_accion(
            telefono="5558",
            tipo_accion="analizar_diagnostico",
            titulo="Análisis",
        )
        r = await ex.ejecutar_accion(a)
        assert r["result"]["modo"] == "llm"
        assert r["result"]["completitud_pct"] == 100
        assert len(r["result"]["fortalezas"]) == 2

    @pytest.mark.asyncio
    async def test_fallback_calcula_completitud_local(self, db, monkeypatch):
        ex, ac, _ = db
        _patch_llm_returns(monkeypatch, None)
        a = await ac.crear_accion(
            telefono="5559",
            tipo_accion="analizar_diagnostico",
            titulo="Análisis",
        )
        r = await ex.ejecutar_accion(a)
        assert r["result"]["modo"] == "fallback"
        # Sin perfil · completitud 0
        assert r["result"]["completitud_pct"] == 0
        assert r["result"]["recomendacion_inicial"]


class TestEjecutorIdeaOferta:
    @pytest.mark.asyncio
    async def test_fallback_devuelve_3_alternativas(self, db, monkeypatch):
        ex, ac, _ = db
        _patch_llm_returns(monkeypatch, None)
        a = await ac.crear_accion(
            telefono="5560",
            tipo_accion="generar_idea_oferta",
            titulo="Idea",
        )
        r = await ex.ejecutar_accion(a)
        assert r["result"]["modo"] == "fallback"
        assert len(r["result"]["alternativas"]) == 3
        for alt in r["result"]["alternativas"]:
            assert alt["titulo"]
            assert alt["descripcion"]


# ─── MEDIUM · preparan, NO envían ──────────────────────────────────────────


class TestEjecutorPreparMensajeWhatsApp:
    @pytest.mark.asyncio
    async def test_requiere_aprobacion_y_no_envia(self, db, monkeypatch):
        ex, ac, _ = db
        _patch_llm_returns(monkeypatch, "Hola {NOMBRE}, soy de tu negocio.")
        a = await ac.crear_accion(
            telefono="5570",
            tipo_accion="preparar_mensaje_whatsapp",
            titulo="Borrador",
        )
        # MEDIUM · estado inicial needs_approval
        assert a["estado"] == "needs_approval"
        # Sin aprobar, no se ejecuta
        r = await ex.ejecutar_accion(a)
        assert r["estado_final"] == "failed"

    @pytest.mark.asyncio
    async def test_aprobado_ejecuta_dry_run(self, db, monkeypatch):
        ex, ac, _ = db
        _patch_llm_returns(monkeypatch, "Hola {NOMBRE}, soy de tu negocio.")
        a = await ac.crear_accion(
            telefono="5571",
            tipo_accion="preparar_mensaje_whatsapp",
            titulo="Borrador",
        )
        await ac.aprobar_accion(a["id"])
        listed = await ac.listar_acciones("5571")
        approved = [x for x in listed if x["id"] == a["id"]][0]
        r = await ex.ejecutar_accion(approved)
        assert r["estado_final"] == "completed"
        # estado_envio explícito · NUNCA enviado
        assert r["result"]["estado_envio"] == "pending_user_review"
        assert "borrador" in r["result"]
        assert r["result"].get("aviso", "").lower().find("revisa") >= 0


class TestEjecutorPreparPublicacionRedes:
    @pytest.mark.asyncio
    async def test_aprobado_devuelve_borrador_no_publica(self, db, monkeypatch):
        ex, ac, _ = db
        _patch_llm_returns(monkeypatch, json.dumps({
            "copy": "Una pequeña reflexión.",
            "hashtags": ["pyme", "negocio"],
            "formato_recomendado": "post",
            "call_to_action": "Cuéntame.",
        }))
        a = await ac.crear_accion(
            telefono="5572",
            tipo_accion="preparar_publicacion_redes",
            titulo="Post",
        )
        await ac.aprobar_accion(a["id"])
        listed = await ac.listar_acciones("5572")
        approved = [x for x in listed if x["id"] == a["id"]][0]
        r = await ex.ejecutar_accion(approved)
        assert r["estado_final"] == "completed"
        assert r["result"]["estado_publicacion"] == "pending_user_review"


class TestEjecutorPreparEmailSeguimiento:
    @pytest.mark.asyncio
    async def test_genera_asunto_y_cuerpo(self, db, monkeypatch):
        ex, ac, _ = db
        _patch_llm_returns(monkeypatch, json.dumps({
            "asunto": "Saludando",
            "cuerpo": "Hola {NOMBRE}, todo bien?",
        }))
        a = await ac.crear_accion(
            telefono="5573",
            tipo_accion="preparar_email_seguimiento",
            titulo="Email",
        )
        await ac.aprobar_accion(a["id"])
        listed = await ac.listar_acciones("5573")
        approved = [x for x in listed if x["id"] == a["id"]][0]
        r = await ex.ejecutar_accion(approved)
        assert r["estado_final"] == "completed"
        assert r["result"]["asunto"] == "Saludando"
        assert r["result"]["estado_envio"] == "pending_user_review"


class TestEjecutorPreparCampanaWhatsApp:
    @pytest.mark.asyncio
    async def test_genera_3_mensajes(self, db, monkeypatch):
        ex, ac, _ = db
        _patch_llm_returns(monkeypatch, json.dumps([
            {"dia": 1, "titulo": "Anuncio", "mensaje": "M1"},
            {"dia": 3, "titulo": "Recordatorio", "mensaje": "M2"},
            {"dia": 5, "titulo": "Último día", "mensaje": "M3"},
        ]))
        a = await ac.crear_accion(
            telefono="5574",
            tipo_accion="preparar_campana_whatsapp",
            titulo="Camp",
        )
        await ac.aprobar_accion(a["id"])
        listed = await ac.listar_acciones("5574")
        approved = [x for x in listed if x["id"] == a["id"]][0]
        r = await ex.ejecutar_accion(approved)
        assert r["estado_final"] == "completed"
        assert len(r["result"]["mensajes"]) == 3
        assert r["result"]["estado_envio"] == "pending_user_review"


class TestEjecutorBorradorCopyOferta:
    @pytest.mark.asyncio
    async def test_genera_copy_a_b(self, db, monkeypatch):
        ex, ac, _ = db
        _patch_llm_returns(monkeypatch, json.dumps({
            "titulo_corto": "Oferta",
            "copy_largo": "Texto largo",
            "variantes": ["A", "B"],
        }))
        a = await ac.crear_accion(
            telefono="5575",
            tipo_accion="borrador_copy_oferta",
            titulo="Copy",
        )
        await ac.aprobar_accion(a["id"])
        listed = await ac.listar_acciones("5575")
        approved = [x for x in listed if x["id"] == a["id"]][0]
        r = await ex.ejecutar_accion(approved)
        assert r["estado_final"] == "completed"
        assert len(r["result"]["variantes"]) == 2


# ─── Guardrails: HIGH y CRITICAL no ejecutan ──────────────────────────────


class TestGuardrailsHigh:
    @pytest.mark.asyncio
    async def test_high_aprobado_sigue_sin_ejecutor(self, db, monkeypatch):
        """enviar_mensaje_whatsapp es HIGH · NO debe tener ejecutor.
        T2.1.C explícitamente NO conecta envío real."""
        ex, ac, _ = db
        _patch_llm_returns(monkeypatch, "esto no debería usarse")
        a = await ac.crear_accion(
            telefono="5580",
            tipo_accion="enviar_mensaje_whatsapp",
            titulo="Send",
        )
        await ac.aprobar_accion(a["id"])
        listed = await ac.listar_acciones("5580")
        approved = [x for x in listed if x["id"] == a["id"]][0]
        r = await ex.ejecutar_accion(approved)
        assert r["estado_final"] == "failed"
        assert "ejecutor" in r["error"].lower() or "futuro" in r["error"].lower()

    @pytest.mark.asyncio
    async def test_publicar_red_social_sin_ejecutor(self, db, monkeypatch):
        ex, ac, _ = db
        _patch_llm_returns(monkeypatch, "esto no debería usarse")
        a = await ac.crear_accion(
            telefono="5581",
            tipo_accion="publicar_red_social",
            titulo="Pub",
        )
        await ac.aprobar_accion(a["id"])
        listed = await ac.listar_acciones("5581")
        approved = [x for x in listed if x["id"] == a["id"]][0]
        r = await ex.ejecutar_accion(approved)
        assert r["estado_final"] == "failed"

    @pytest.mark.asyncio
    async def test_contactar_lead_sin_ejecutor(self, db, monkeypatch):
        ex, ac, _ = db
        _patch_llm_returns(monkeypatch, "x")
        a = await ac.crear_accion(
            telefono="5582",
            tipo_accion="contactar_lead",
            titulo="Lead",
        )
        await ac.aprobar_accion(a["id"])
        listed = await ac.listar_acciones("5582")
        approved = [x for x in listed if x["id"] == a["id"]][0]
        r = await ex.ejecutar_accion(approved)
        assert r["estado_final"] == "failed"


class TestGuardrailsCritical:
    @pytest.mark.asyncio
    async def test_critical_bloqueado_aun_aprobado(self, db, monkeypatch):
        ex, ac, _ = db
        _patch_llm_returns(monkeypatch, "x")
        a = await ac.crear_accion(
            telefono="5590",
            tipo_accion="envio_masivo_clientes",
            titulo="Mass",
        )
        await ac.aprobar_accion(a["id"])
        listed = await ac.listar_acciones("5590")
        approved = [x for x in listed if x["id"] == a["id"]][0]
        r = await ex.ejecutar_accion(approved)
        assert r["estado_final"] == "failed"
        assert "critical" in r["error"].lower() or "bloqueada" in r["error"].lower()


# ─── No referencias a providers reales en ejecutores T2.1.C ───────────────


class TestEjecutoresNoUsanProvidersReales:
    """Garantiza que los ejecutores T2.1.C NO importan ni llaman a Whapi/
    Twilio/Stripe/HTTP clients de providers externos. Solo agent.llm."""

    def test_no_provider_imports_en_ejecutores(self):
        import inspect
        from agent.automation import execution as _ex
        for name in (
            "_ejecutor_plan_semanal",
            "_ejecutor_calendario_contenido",
            "_ejecutor_checklist_ventas",
            "_ejecutor_analizar_diagnostico",
            "_ejecutor_generar_idea_oferta",
            "_ejecutor_preparar_mensaje_whatsapp",
            "_ejecutor_preparar_campana_whatsapp",
            "_ejecutor_preparar_publicacion_redes",
            "_ejecutor_preparar_email_seguimiento",
            "_ejecutor_borrador_copy_oferta",
        ):
            fn = getattr(_ex, name)
            src = inspect.getsource(fn).lower()
            for forbidden in (
                "whapi", "twilio", "stripe.", "providers",
                "send_message(", "enviar_mensaje(",
                "publish_", "post_to_facebook", "post_to_instagram",
            ):
                assert forbidden not in src, \
                    f"Ejecutor {name} contiene referencia prohibida: {forbidden}"


# ─── Audit log incluye modo (llm|fallback) sin PII ────────────────────────


class TestAuditLogModoYProviderEnPayload:
    @pytest.mark.asyncio
    async def test_audit_action_completed_tiene_modo(self, db, monkeypatch):
        ex, ac, _ = db
        _patch_llm_returns(monkeypatch, "# Plan\n## Lunes\n- A")
        a = await ac.crear_accion(
            telefono="5215559999999",
            tipo_accion="generar_plan_semanal",
            titulo="Plan",
        )
        await ex.ejecutar_accion(a)
        from agent.automation.models import AuditLogAutomatizacion
        from sqlalchemy import select
        async with agent.memory.async_session() as session:
            r = await session.execute(
                select(AuditLogAutomatizacion).where(
                    AuditLogAutomatizacion.evento == "action_completed"
                )
            )
            logs = list(r.scalars().all())
        # Hay 2 events action_completed: uno desde marcar_completada
        # (action_center) y uno desde el ejecutor (con modo). Buscamos
        # el que tiene modo en el payload.
        with_modo = [
            (log, json.loads(log.payload_summary))
            for log in logs
            if "modo" in (log.payload_summary or "")
        ]
        assert with_modo, "Se esperaba al menos un audit con 'modo' en payload"
        log, summary = with_modo[-1]
        # telefono completo NUNCA en audit
        assert "5215559999999" not in log.telefono_short
        assert "5215559999999" not in log.payload_summary
        # Payload tiene modo
        assert summary.get("modo") == "llm"
        assert summary.get("provider") == "llm"
