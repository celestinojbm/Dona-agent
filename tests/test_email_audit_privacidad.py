# tests/test_email_audit_privacidad.py — PR 1 · Audit whitelist + privacy

import json

import pytest

from agent.automation.email_audit import metadata_audit_email
from tests.helpers_email_pr1 import (
    fila_por_id,
    filas_audit,
    filas_email,
    preparar,
    preparar_db_email,
)

TEL_A = "14155550100"
TEL_B = "5215550200"

# Marcadores distintivos: si alguno aparece en audit/logs/descripcion, hay fuga.
DEST = "fuga.destinatario@ejemplo.com"
ASUNTO = "ASUNTO_MARCADOR_FUGA_QX"
CUERPO = "CUERPO_MARCADOR_FUGA_ZW con datos privados del negocio"


@pytest.fixture
async def db(tmp_path, monkeypatch):
    return await preparar_db_email(tmp_path, monkeypatch)


class TestWhitelistCerrada:
    def test_kwargs_desconocidos_producen_typeerror(self):
        for clave in ("destinatario", "asunto", "cuerpo", "token", "preview", "foo"):
            with pytest.raises(TypeError):
                metadata_audit_email(**{clave: "x"})

    def test_solo_emite_campos_provistos(self):
        m = metadata_audit_email(action_id=7, reason_code="expired")
        assert m == {"action_id": 7, "reason_code": "expired"}
        # Valores falsy legítimos SÍ se emiten (sentinel, no truthiness)
        m2 = metadata_audit_email(longitud_cuerpo=0, es_reemplazo=False)
        assert m2 == {"longitud_cuerpo": 0, "es_reemplazo": False}

    def test_serializa_datetimes(self):
        from datetime import datetime

        m = metadata_audit_email(created_at=datetime(2026, 7, 17, 12, 0, 0))
        assert m["created_at"] == "2026-07-17T12:00:00"

    def test_no_acepta_posicionales(self):
        with pytest.raises(TypeError):
            metadata_audit_email(1)  # keyword-only


class TestSinFugasDePII:
    @pytest.mark.asyncio
    async def test_flujo_completo_sin_pii_en_audit(self, db, caplog):
        from agent.automation.email_actions import (
            cancelar_envio_correo,
            confirmar_envio_correo,
        )

        with caplog.at_level("DEBUG", logger="dona"):
            r = await preparar(
                TEL_A, "wamid-400", cuerpo=CUERPO, destinatario=DEST, asunto=ASUNTO
            )
            token = r["token"]
            await confirmar_envio_correo(TEL_A, token)
            # conflicto por fingerprint distinto (genera su propio evento)
            await preparar(TEL_A, "wamid-400", cuerpo=CUERPO + " editado",
                           destinatario=DEST, asunto=ASUNTO)
            await cancelar_envio_correo(TEL_A, token)

        # Audit log: ni contenido, ni token, ni teléfono completo
        auditoria = await filas_audit()
        assert auditoria, "el flujo debe dejar audit trail"
        for fila in auditoria:
            for marcador in (DEST, ASUNTO, CUERPO, token):
                assert marcador not in (fila.payload_summary or "")
            assert TEL_A not in (fila.telefono_short or "")

        # Logs de stdout: mismos marcadores ausentes
        logs = "\n".join(rec.getMessage() for rec in caplog.records)
        for marcador in (DEST, ASUNTO, CUERPO, token):
            assert marcador not in logs

        # Columnas visibles de la acción: sin contenido
        for accion in await filas_email(TEL_A):
            for col in (accion.titulo, accion.descripcion,
                        accion.razon_recomendacion, accion.error_message,
                        accion.result_json):
                for marcador in (DEST, ASUNTO, CUERPO, token):
                    assert marcador not in (col or "")

    @pytest.mark.asyncio
    async def test_eventos_email_usan_whitelist(self, db):
        """Cada evento email del audit solo contiene claves aprobadas."""
        from agent.automation.email_actions import confirmar_envio_correo

        claves_aprobadas = {
            "action_id", "tipo_accion", "estado", "reason_code", "error_code",
            "payload_fingerprint", "longitud_cuerpo", "tiene_thread",
            "preparation_request_hash", "created_at", "expires_at", "es_reemplazo",
        }
        r = await preparar(TEL_A, "wamid-401")
        await confirmar_envio_correo(TEL_A, r["token"])
        eventos_email = [
            f for f in await filas_audit() if f.evento.startswith("email_")
        ]
        assert eventos_email
        for fila in eventos_email:
            payload = json.loads(fila.payload_summary)
            assert set(payload.keys()) <= claves_aprobadas, (
                f"{fila.evento} contiene claves fuera de whitelist: "
                f"{set(payload.keys()) - claves_aprobadas}"
            )


class TestPayloadCifradoEnDB:
    @pytest.mark.asyncio
    async def test_payload_json_no_contiene_plaintext(self, db):
        r = await preparar(
            TEL_A, "wamid-410", cuerpo=CUERPO, destinatario=DEST, asunto=ASUNTO
        )
        fila = await fila_por_id(r["action_id"])
        envelope = json.loads(fila.payload_json)
        assert envelope["alg"] == "fernet"
        for marcador in (DEST, ASUNTO, CUERPO):
            assert marcador not in fila.payload_json


class TestPrivacyExportDelete:
    @pytest.mark.asyncio
    async def test_export_owner_scoped_con_contenido_descifrado(self, db):
        await preparar(TEL_A, "wamid-420", cuerpo=CUERPO, destinatario=DEST)
        await preparar(TEL_B, "wamid-421", cuerpo="contenido de B",
                       destinatario="b@ejemplo.com")
        export = await db.exportar_datos_usuario(TEL_A)
        acciones = export["acciones_automatizacion"]
        assert len(acciones) == 1
        # El propietario ve SU contenido descifrado mientras siga retenido
        assert acciones[0]["payload"]["cuerpo"] == CUERPO
        assert acciones[0]["payload"]["destinatario"] == DEST
        # Cero datos del otro owner en el export completo
        assert "contenido de B" not in json.dumps(export, ensure_ascii=False)
        assert "b@ejemplo.com" not in json.dumps(export, ensure_ascii=False)

    @pytest.mark.asyncio
    async def test_export_distingue_payload_purgado(self, db):
        from agent.automation.email_actions import cancelar_envio_correo

        r = await preparar(TEL_A, "wamid-422", cuerpo=CUERPO)
        await cancelar_envio_correo(TEL_A, r["token"])
        export = await db.exportar_datos_usuario(TEL_A)
        acciones = export["acciones_automatizacion"]
        assert acciones[0]["payload"] == {"purgado": True}
        # El contenido purgado NO se reconstruye
        assert CUERPO not in json.dumps(export, ensure_ascii=False)

    @pytest.mark.asyncio
    async def test_delete_elimina_acciones_sin_ciphertext_huerfano(self, db):
        await preparar(TEL_A, "wamid-423", cuerpo=CUERPO)
        await preparar(TEL_B, "wamid-424", cuerpo="contenido de B")
        conteos = await db.borrar_datos_usuario(TEL_A)
        assert conteos["acciones_automatizacion"] == 1
        assert await filas_email(TEL_A) == []
        # El otro owner queda intacto
        assert len(await filas_email(TEL_B)) == 1
