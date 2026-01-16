# =============================================================================
# GENERATOR.PY — GENERADOR SEMI-AUTOMÁTICO DE PICKS (FASE 6.1)
# =============================================================================
import pandas as pd
import os
from datetime import datetime

# CORRECCIÓN AUDITORÍA: Usamos la función estándar del modelo
from model import calcular_valor_poisson

PENDING_FILE = "data/pending_picks.csv"


# -----------------------------------------------------------------------------
# UTILIDAD — INICIALIZAR CSV DE PENDIENTES
# -----------------------------------------------------------------------------
def _init_pending_csv():
    os.makedirs("data", exist_ok=True)

    columns = [
        "timestamp",
        "market",
        "tipo",
        "line",
        "odds_est",
        "P_model",
        "Odds_min",
        "EV",
        "Stake_U",
        "Aceptado",
        "Razones_Rechazo",
        "Modo"
    ]

    if not os.path.exists(PENDING_FILE):
        pd.DataFrame(columns=columns).to_csv(PENDING_FILE, index=False)


# -----------------------------------------------------------------------------
# GENERADOR PRINCIPAL
# -----------------------------------------------------------------------------
def generar_picks_candidatos(
    lambdas: dict,
    mercados: list,
    tipos: list,
    lineas: list,
    odds_estimadas: dict,
    n: int,
    rho: float,
    bankroll: float,
    unidad: float,
    modo: str = "PRODUCCIÓN",
    drawdown: float = 0.0
):
    """
    Itera sobre combinaciones de mercado/línea y genera candidatos.
    """
    _init_pending_csv()
    
    try:
        df_pending = pd.read_csv(PENDING_FILE)
    except Exception:
        df_pending = pd.DataFrame()

    nuevos_picks = []

    lambda_local = lambdas["lambda_local"]
    lambda_visit = lambdas["lambda_visitante"]

    for mercado in mercados:
        for tipo in tipos:
            for linea in lineas:
                
                # Odds estimadas (dummy o reales)
                odds = odds_estimadas.get(f"{mercado}_{linea}", 2.0)

                # LLAMADA AL MODELO (Core Poisson)
                resultado = calcular_valor_poisson(
                    lambda_local=lambda_local,
                    lambda_visitante=lambda_visit,
                    event_type=tipo,
                    linea=linea,
                    odds=odds,
                    mercado=mercado,
                    rho=rho,
                    bankroll=bankroll,
                    unidad=unidad,
                    modo=modo,
                    drawdown=drawdown
                )

                # -------------------------
                # FILTRO DURO (REGLA DE ORO)
                # -------------------------
                if (
                    resultado["Aceptado"] is True
                    and odds >= resultado["Odds_min"]
                    and resultado["EV"] > 0
                ):
                    nuevos_picks.append({
                        "timestamp": datetime.utcnow().isoformat(timespec="seconds"),
                        "market": mercado,
                        "tipo": tipo,
                        "line": linea,
                        "odds_est": odds,
                        "P_model": resultado["P_model"],
                        "Odds_min": resultado["Odds_min"],
                        "EV": resultado["EV"],
                        "Stake_U": resultado["Stake_U"],
                        "Aceptado": True,
                        "Razones_Rechazo": "",
                        "Modo": modo
                    })

    if nuevos_picks:
        df_pending = pd.concat(
            [df_pending, pd.DataFrame(nuevos_picks)],
            ignore_index=True
        )
        df_pending.to_csv(PENDING_FILE, index=False)

    return pd.DataFrame(nuevos_picks)