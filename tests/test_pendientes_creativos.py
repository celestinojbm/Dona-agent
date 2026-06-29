# tests/test_pendientes_creativos.py — Helper centralizado de pendientes creativos

"""
Cubre `agent/creativos/pendientes.py`, el módulo que garantiza la regla
**un solo pendiente activo por teléfono** del flujo preparar→confirmar
(ver CLAUDE.md §3.1). El módulo orquesta los 6 módulos creativos (imagen, voz,
documento/pdf, video, video_avatar, bg_remove): consulta `obtener_pendiente`
y dispara `cancelar_X` en cada uno.

Estos tests fijan el COMPORTAMIENTO ACTUAL contra los módulos reales (no se
mockea el código bajo prueba): se siembra un pendiente vivo insertando un stub
mínimo en el `_PENDIENTES` de cada módulo. El stub solo necesita `expirado()`
porque `obtener_pendiente` lo consulta y `cancelar_X` simplemente hace pop.

Aislamiento: la fixture limpia los 6 dicts `_PENDIENTES` antes y después de
cada test para que el estado in-memory no se filtre entre casos.
"""

import pytest

from agent.creativos import (
    bg_remove,
    imagen,
    pdf,
    pendientes,
    video,
    video_avatar,
    voz,
)

# Orden de precedencia tal como lo recorre `_tipo_pendiente_activo` /
# `cancelar_otros_pendientes` en el código (imagen primero, bg_remove último).
_MODULOS = [imagen, voz, pdf, video, video_avatar, bg_remove]

TEL = "whatsapp:+15557770000"
OTRO_TEL = "whatsapp:+15558880000"


class _StubPendiente:
    """Pendiente mínimo: `obtener_pendiente` consulta `expirado()` y
    `cancelar_X` solo hace pop, así que esto basta para simular uno vivo."""

    def expirado(self) -> bool:
        return False


@pytest.fixture(autouse=True)
def _limpiar_pendientes():
    """Garantiza dicts `_PENDIENTES` vacíos antes y después de cada test."""
    for m in _MODULOS:
        m._PENDIENTES.clear()
    yield
    for m in _MODULOS:
        m._PENDIENTES.clear()


def _sembrar(modulo, telefono=TEL):
    """Inserta un pendiente vivo en el módulo dado."""
    modulo._PENDIENTES[telefono] = _StubPendiente()


# ── Estado vacío ─────────────────────────────────────────────────────────────

class TestSinPendientes:
    def test_hay_pendiente_activo_falso_sin_nada(self):
        assert pendientes.hay_pendiente_activo(TEL) is False

    def test_tipo_pendiente_activo_none_sin_nada(self):
        assert pendientes._tipo_pendiente_activo(TEL) is None

    def test_cancelar_otros_none_sin_nada(self):
        assert pendientes.cancelar_otros_pendientes(TEL) is None

    def test_cancelar_todos_none_sin_nada(self):
        assert pendientes.cancelar_todos(TEL) is None


# ── Detección de un único pendiente por tipo ─────────────────────────────────

class TestDeteccionPorTipo:
    @pytest.mark.parametrize(
        "modulo, tipo_esperado",
        [
            (imagen, "imagen"),
            (voz, "voz"),
            (pdf, "documento"),
            (video, "video"),
            (video_avatar, "video_avatar"),
            (bg_remove, "bg_remove"),
        ],
    )
    def test_tipo_pendiente_activo_detecta_cada_tipo(self, modulo, tipo_esperado):
        _sembrar(modulo)
        assert pendientes._tipo_pendiente_activo(TEL) == tipo_esperado
        assert pendientes.hay_pendiente_activo(TEL) is True


# ── Etiquetas legibles devueltas al cancelar ─────────────────────────────────

class TestEtiquetasAlCancelar:
    @pytest.mark.parametrize(
        "modulo, etiqueta_esperada",
        [
            (imagen, "imagen"),
            (voz, "nota de voz"),
            (pdf, "documento"),
            (video, "video"),
            (video_avatar, "video con avatar"),
            (bg_remove, "quitar fondo"),
        ],
    )
    def test_cancelar_otros_devuelve_etiqueta_legible(self, modulo, etiqueta_esperada):
        _sembrar(modulo)
        assert pendientes.cancelar_otros_pendientes(TEL) == etiqueta_esperada
        # Tras cancelar no queda nada vivo.
        assert pendientes.hay_pendiente_activo(TEL) is False


# ── Precedencia cuando hay varios vivos ──────────────────────────────────────

class TestPrecedencia:
    def test_imagen_gana_sobre_voz(self):
        _sembrar(imagen)
        _sembrar(voz)
        assert pendientes._tipo_pendiente_activo(TEL) == "imagen"

    def test_orden_precedencia_completo(self):
        """Con los 6 vivos, `_tipo_pendiente_activo` reporta el primero en el
        orden de chequeo (imagen)."""
        for m in _MODULOS:
            _sembrar(m)
        assert pendientes._tipo_pendiente_activo(TEL) == "imagen"

    def test_cancelar_otros_con_todos_devuelve_ultimo_en_orden(self):
        """`cancelar_otros_pendientes` sobreescribe `tipo_cancelado` mientras
        recorre; con los 6 vivos el último cancelado es bg_remove → "quitar
        fondo". Se fija este comportamiento actual."""
        for m in _MODULOS:
            _sembrar(m)
        assert pendientes.cancelar_otros_pendientes(TEL) == "quitar fondo"
        assert pendientes.hay_pendiente_activo(TEL) is False


# ── Parámetro `excepto` ──────────────────────────────────────────────────────

class TestExcepto:
    def test_excepto_preserva_su_tipo(self):
        """Con imagen viva y `excepto="imagen"`, la imagen sobrevive y no se
        reporta como cancelada."""
        _sembrar(imagen)
        assert pendientes.cancelar_otros_pendientes(TEL, excepto="imagen") is None
        assert imagen.obtener_pendiente(TEL) is not None
        assert pendientes._tipo_pendiente_activo(TEL) == "imagen"

    def test_excepto_cancela_los_demas_y_conserva_el_propio(self):
        """Con los 6 vivos y `excepto="imagen"`: imagen sobrevive, los demás se
        cancelan, y la etiqueta devuelta es la del último otro cancelado."""
        for m in _MODULOS:
            _sembrar(m)
        etiqueta = pendientes.cancelar_otros_pendientes(TEL, excepto="imagen")
        assert etiqueta == "quitar fondo"  # bg_remove, último en el recorrido
        assert imagen.obtener_pendiente(TEL) is not None
        assert pendientes._tipo_pendiente_activo(TEL) == "imagen"


# ── cancelar_todos ───────────────────────────────────────────────────────────

class TestCancelarTodos:
    def test_cancelar_todos_limpia_todo(self):
        for m in _MODULOS:
            _sembrar(m)
        etiqueta = pendientes.cancelar_todos(TEL)
        assert etiqueta == "quitar fondo"  # delega en cancelar_otros (excepto="")
        assert pendientes.hay_pendiente_activo(TEL) is False

    def test_cancelar_todos_un_solo_tipo(self):
        _sembrar(video_avatar)
        assert pendientes.cancelar_todos(TEL) == "video con avatar"
        assert pendientes.hay_pendiente_activo(TEL) is False


# ── Aislamiento entre teléfonos ──────────────────────────────────────────────

class TestAislamientoPorTelefono:
    def test_cancelar_no_afecta_otro_telefono(self):
        _sembrar(imagen, telefono=TEL)
        _sembrar(voz, telefono=OTRO_TEL)
        pendientes.cancelar_todos(TEL)
        assert pendientes.hay_pendiente_activo(TEL) is False
        assert pendientes.hay_pendiente_activo(OTRO_TEL) is True
        assert pendientes._tipo_pendiente_activo(OTRO_TEL) == "voz"
