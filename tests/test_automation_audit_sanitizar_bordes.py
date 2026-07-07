# tests/test_automation_audit_sanitizar_bordes.py
#
# Bordes de la redacción del audit log (agent/automation/audit.py).
#
# CLAUDE.md §3.5: los datos que se persisten/loguean nunca deben llevar PII ni
# secretos. `sanitizar_payload` es el filtro que lo garantiza para el audit log
# de automatización. `test_automation_audit.py` cubre el camino feliz
# (descartar claves prohibidas, truncar strings largos, recursión en dicts y
# listas de dicts); estos tests fijan las RAMAS que quedaban sin cobertura:
#
#   - truncado de IDs vía _CLAVES_TRUNCAR (Stripe / subscription short ids)
#   - matcheo case-insensitive de claves prohibidas
#   - cap de 20 elementos en listas
#   - truncado de strings sueltos DENTRO de listas (sin sufijo '...')
#   - preservación de escalares no-string (int/bool/None) y de items no
#     dict/no-str dentro de listas
#   - las tres ramas de enmascarado de _short_telefono
#
# Son funciones puras: se prueban contra el comportamiento ACTUAL, sin tocar DB
# ni lógica de producción.

from agent.automation import audit


class TestClavesTruncar:
    def test_id_largo_se_trunca_a_12_mas_sufijo(self):
        # _CLAVES_TRUNCAR mantiene la clave pero recorta el valor a 12 chars.
        d = {"stripe_customer_id_short": "cus_" + "a" * 30}
        out = audit.sanitizar_payload(d)
        assert out["stripe_customer_id_short"] == "cus_aaaaaaaa..."
        # 12 chars de contenido + '...'
        assert len(out["stripe_customer_id_short"]) == 15

    def test_id_corto_se_mantiene_intacto(self):
        # Valor no mayor a _TRUNCATE_LEN (12) → sin recortar, sin sufijo.
        d = {"subscription_id_short": "sub_abc"}
        out = audit.sanitizar_payload(d)
        assert out["subscription_id_short"] == "sub_abc"

    def test_id_en_limite_exacto_no_se_trunca(self):
        # len == 12 no supera el umbral (usa > estricto).
        valor = "a" * 12
        out = audit.sanitizar_payload({"customer_id_short": valor})
        assert out["customer_id_short"] == valor

    def test_customer_id_completo_se_descarta_pero_short_se_trunca(self):
        # La clave prohibida se va; la _short sobrevive truncada.
        d = {"customer_id": "cus_secreto_completo", "customer_id_short": "cus_" + "z" * 20}
        out = audit.sanitizar_payload(d)
        assert "customer_id" not in out
        assert out["customer_id_short"] == "cus_zzzzzzzz..."


class TestCaseInsensitive:
    def test_claves_prohibidas_en_mayusculas_se_descartan(self):
        d = {"TELEFONO": "5215551234567", "Password": "x", "Api_Key": "k", "ok": "v"}
        out = audit.sanitizar_payload(d)
        assert "TELEFONO" not in out
        assert "Password" not in out
        assert "Api_Key" not in out
        assert out["ok"] == "v"


class TestListas:
    def test_lista_se_capa_a_20_items(self):
        d = {"items": [{"i": n} for n in range(25)]}
        out = audit.sanitizar_payload(d)
        assert len(out["items"]) == 20
        # Se conservan los primeros 20 (v[:20]), sanitizados.
        assert out["items"][0] == {"i": 0}
        assert out["items"][19] == {"i": 19}

    def test_string_suelto_en_lista_se_trunca_a_200_sin_sufijo(self):
        d = {"notas": ["b" * 500]}
        out = audit.sanitizar_payload(d)
        # A diferencia de un string top-level, aquí NO se agrega '...'.
        assert out["notas"][0] == "b" * 200
        assert len(out["notas"][0]) == 200
        assert not out["notas"][0].endswith("...")

    def test_escalares_no_dict_ni_str_en_lista_se_preservan(self):
        d = {"mezcla": [1, 2, True, None, 3.5]}
        out = audit.sanitizar_payload(d)
        assert out["mezcla"] == [1, 2, True, None, 3.5]

    def test_dict_dentro_de_lista_se_sanitiza(self):
        d = {"items": [{"telefono": "5215551234567", "tipo": "x"}]}
        out = audit.sanitizar_payload(d)
        assert "telefono" not in out["items"][0]
        assert out["items"][0]["tipo"] == "x"


class TestEscalaresTopLevel:
    def test_escalares_no_string_se_preservan(self):
        d = {"creditos": 5, "activo": True, "nada": None, "ratio": 1.5}
        out = audit.sanitizar_payload(d)
        assert out["creditos"] == 5
        assert out["activo"] is True
        assert out["nada"] is None
        assert out["ratio"] == 1.5

    def test_string_en_limite_200_no_se_trunca(self):
        d = {"campo": "a" * 200}
        out = audit.sanitizar_payload(d)
        assert out["campo"] == "a" * 200  # 200 no supera el umbral (> estricto)

    def test_string_201_se_trunca_con_sufijo(self):
        d = {"campo": "a" * 201}
        out = audit.sanitizar_payload(d)
        assert out["campo"] == "a" * 200 + "..."


class TestShortTelefono:
    def test_vacio_devuelve_estrellas(self):
        assert audit._short_telefono("") == "***"

    def test_none_devuelve_estrellas(self):
        # None es falsy → misma rama que vacío.
        assert audit._short_telefono(None) == "***"

    def test_corto_o_igual_a_6_devuelve_estrellas(self):
        assert audit._short_telefono("12345") == "***"   # len 5
        assert audit._short_telefono("123456") == "***"  # len 6, límite inclusivo

    def test_largo_se_enmascara_manteniendo_prefijo_y_sufijo(self):
        assert audit._short_telefono("5215551234567") == "52****4567"
        # 7 chars: primeros 2 + '****' + últimos 4.
        assert audit._short_telefono("1234567") == "12****4567"
