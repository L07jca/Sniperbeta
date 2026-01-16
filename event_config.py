# =============================================================================
# EVENT_CONFIG.PY — CONFIGURACIÓN POR TIPO DE EVENTO (FASE H1)
# Ajuste quirúrgico post-backtest
# =============================================================================

from dataclasses import dataclass


@dataclass(frozen=True)
class EventConfig:
    name: str
    cv_expected: float
    edge_min: float          # Edge mínimo por evento (calibración fina)
    usar_cv: bool
    usar_threshold: bool


# -----------------------------------------------------------------------------
# DEFINICIÓN DE EVENTOS SOPORTADOS (CALIBRADOS)
# -----------------------------------------------------------------------------
EVENTS = {

    # ⚽ GOLES — evento raro, alta varianza
    "goals": EventConfig(
        name="Goles",
        cv_expected=0.55,
        edge_min=0.02,
        usar_cv=True,
        usar_threshold=True
    ),

    # 🎯 REMATES TOTALES — alto conteo, mercado eficiente
    "shots": EventConfig(
        name="Remates",
        cv_expected=0.85,
        edge_min=0.025,
        usar_cv=False,
        usar_threshold=True
    ),

    # 🧤 REMATES A PUERTA — conteo medio-alto
    # ⬅️ AJUSTE FASE H1: edge_min reducido
    "shots_on_target": EventConfig(
        name="Remates a Puerta",
        cv_expected=0.95,
        edge_min=0.020,        # ⬅️ CLAVE FASE H1
        usar_cv=False,
        usar_threshold=True
    ),

    # 🚩 CÓRNERS — ruido táctico + árbitro
    "corners": EventConfig(
        name="Córners",
        cv_expected=0.80,
        edge_min=0.03,
        usar_cv=False,
        usar_threshold=True
    ),

    # 🟨 TARJETAS — evento discreto, varianza contextual
    "cards": EventConfig(
        name="Tarjetas",
        cv_expected=0.90,
        edge_min=0.03,
        usar_cv=False,
        usar_threshold=True
    ),

    # 🤕 FALTAS — mercado blando pero ruidoso
    "fouls": EventConfig(
        name="Faltas",
        cv_expected=0.75,
        edge_min=0.025,
        usar_cv=False,
        usar_threshold=True
    ),
}


# -----------------------------------------------------------------------------
# UTILIDAD
# -----------------------------------------------------------------------------
def get_event_config(event_type: str) -> EventConfig:
    if event_type not in EVENTS:
        raise ValueError(f"Tipo de evento no soportado: {event_type}")
    return EVENTS[event_type]
