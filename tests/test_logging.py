# tests/test_logging.py — Verifica formato JSON y redaction de PII.

import json
import logging
import io
import pytest

from agent.logging_config import (
    enmascarar_telefono,
    redactar_pii,
    truncar_mensaje,
    JsonFormatter,
)


# ── Patrones individuales ────────────────────────────────────────────────────

class TestEnmascararTelefono:
    def test_e164_con_signo(self):
        assert enmascarar_telefono("+14076936023") == "+1407****6023"

    def test_e164_sin_signo(self):
        # 12 dígitos: cabeza 2 + medio enmascarado + cola 4.
        assert enmascarar_telefono("521234567890") == "5212****7890"

    def test_no_toca_numeros_cortos(self):
        # 6 dígitos no se enmascara (no parece teléfono).
        assert enmascarar_telefono("código 123456") == "código 123456"

    def test_idempotencia(self):
        # Aplicar dos veces no debe romper el formato enmascarado.
        primera = enmascarar_telefono("+14076936023")
        segunda = enmascarar_telefono(primera)
        assert primera == segunda


class TestRedactarPII:
    def test_email(self):
        out = redactar_pii("Contacto foo@bar.com")
        assert "foo@bar.com" not in out
        assert "***@bar.com" in out

    def test_email_corto_preserva_inicial(self):
        out = redactar_pii("a@x.io")
        assert "a***@x.io" == out

    def test_bearer_token(self):
        out = redactar_pii("Authorization: Bearer abc123def456ghi789")
        assert "abc123def456ghi789" not in out
        assert "[REDACTED]" in out

    def test_stripe_session_id(self):
        out = redactar_pii("session cs_live_a1b2c3d4e5f6g7h8i9j0k1l2m3 ok")
        assert "cs_live_a1b2c3d4e5f6g7h8i9j0k1l2m3" not in out
        assert "[REDACTED_KEY]" in out

    def test_anthropic_key(self):
        out = redactar_pii("key=sk-ant-api03-AAAA-BBBB-CCCC-DDDD-EEEE-FFFFGGGG")
        assert "sk-ant-api03" not in out
        assert "[REDACTED_KEY]" in out

    def test_openai_key(self):
        out = redactar_pii("OPENAI_API_KEY=sk-AAABBBCCCDDD123456789012345")
        assert "sk-AAABBBCCC" not in out
        assert "[REDACTED_KEY]" in out

    def test_whsec(self):
        out = redactar_pii("STRIPE_WEBHOOK_SECRET=whsec_AAAABBBBCCCC1234567890")
        assert "whsec_AAAABBBB" not in out
        assert "[REDACTED_KEY]" in out

    def test_telefono_y_email_juntos(self):
        out = redactar_pii("Usuario +14076936023 (foo@bar.com)")
        assert "+14076936023" not in out
        assert "foo@bar.com" not in out
        assert "+1407****6023" in out
        assert "***@bar.com" in out

    def test_input_vacio(self):
        assert redactar_pii("") == ""
        assert redactar_pii(None) is None

    def test_idempotencia(self):
        s = "Auth Bearer ABC123abc456def789 + email foo@bar.com + tel +14076936023"
        primero = redactar_pii(s)
        segundo = redactar_pii(primero)
        assert primero == segundo


class TestTruncarMensaje:
    def test_corto_no_trunca(self):
        assert truncar_mensaje("hola") == "hola"

    def test_largo_trunca(self):
        out = truncar_mensaje("a" * 100, max_len=40)
        assert len(out) == 43  # 40 + "..."
        assert out.endswith("...")


# ── JsonFormatter ────────────────────────────────────────────────────────────

def _hacer_record(level: int, mensaje: str, **extras) -> logging.LogRecord:
    record = logging.LogRecord(
        name="dona.test",
        level=level,
        pathname=__file__,
        lineno=1,
        msg=mensaje,
        args=(),
        exc_info=None,
    )
    for k, v in extras.items():
        setattr(record, k, v)
    return record


class TestJsonFormatter:
    def setup_method(self):
        self.fmt = JsonFormatter()

    def test_formato_es_json_parseable(self):
        out = self.fmt.format(_hacer_record(logging.INFO, "hola"))
        parsed = json.loads(out)
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "dona.test"
        assert parsed["msg"] == "hola"
        assert "ts" in parsed

    def test_redacta_telefono_en_info(self):
        out = self.fmt.format(_hacer_record(
            logging.INFO, "Procesando mensaje de +14076936023"
        ))
        parsed = json.loads(out)
        assert "+14076936023" not in parsed["msg"]
        assert "+1407****6023" in parsed["msg"]

    def test_redacta_email_en_warning(self):
        out = self.fmt.format(_hacer_record(
            logging.WARNING, "Login fallido para usuario foo@bar.com"
        ))
        parsed = json.loads(out)
        assert "foo@bar.com" not in parsed["msg"]
        assert "***@bar.com" in parsed["msg"]

    def test_redacta_bearer_en_error(self):
        out = self.fmt.format(_hacer_record(
            logging.ERROR, "Token invalido: Bearer abc123def456ghi789"
        ))
        parsed = json.loads(out)
        assert "abc123def456ghi789" not in parsed["msg"]
        assert "[REDACTED]" in parsed["msg"]

    def test_no_redacta_en_debug(self):
        # DEBUG mantiene PII intacta para diagnóstico.
        out = self.fmt.format(_hacer_record(
            logging.DEBUG, "DEBUG raw +14076936023 foo@bar.com"
        ))
        parsed = json.loads(out)
        assert "+14076936023" in parsed["msg"]
        assert "foo@bar.com" in parsed["msg"]

    def test_campo_extra_telefono_redactado_en_info(self):
        out = self.fmt.format(_hacer_record(
            logging.INFO, "evento", telefono="+14076936023", ruta="/webhook"
        ))
        parsed = json.loads(out)
        assert parsed["telefono"] == "+1407****6023"
        assert parsed["ruta"] == "/webhook"

    def test_campo_extra_telefono_no_redactado_en_debug(self):
        out = self.fmt.format(_hacer_record(
            logging.DEBUG, "evento", telefono="+14076936023"
        ))
        parsed = json.loads(out)
        assert parsed["telefono"] == "+14076936023"

    def test_exception_preservada(self):
        try:
            raise ValueError("boom")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        record = logging.LogRecord(
            name="dona.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="error procesando",
            args=(),
            exc_info=exc_info,
        )
        out = self.fmt.format(record)
        parsed = json.loads(out)
        assert "exception" in parsed
        assert "ValueError: boom" in parsed["exception"]
        assert "Traceback" in parsed["exception"]


# ── Smoke test: pipeline completo via logging real ───────────────────────────

class TestPipelineLoggingProduccion:
    """Configura un logger ad-hoc con JsonFormatter y verifica que la salida
    real (sin tocar la config global) cumple el contrato."""

    def test_pipeline_redacta_y_emite_json(self):
        buffer = io.StringIO()
        handler = logging.StreamHandler(buffer)
        handler.setFormatter(JsonFormatter())
        handler.setLevel(logging.INFO)

        logger = logging.getLogger("dona.pipeline_test")
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False

        logger.info(
            "Webhook stripe procesado: customer=cus_AaBbCcDdEeFf112233 "
            "telefono=+14076936023 email=foo@bar.com"
        )

        salida = buffer.getvalue().strip()
        parsed = json.loads(salida)
        assert "+14076936023" not in parsed["msg"]
        assert "foo@bar.com" not in parsed["msg"]
        assert "cus_AaBbCcDdEeFf112233" not in parsed["msg"]
        assert "[REDACTED_KEY]" in parsed["msg"]
        assert "+1407****6023" in parsed["msg"]
