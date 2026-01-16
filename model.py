# =============================================================================
# MODEL.PY — MOTOR HÍBRIDO POISSON / BINOMIAL NEGATIVA (V5.1 - FINAL SURGERY)
# -----------------------------------------------------------------------------
# Lógica Matemática:
# 1. Si Varianza > Media (Sobredispersión) -> Usa Binomial Negativa (nbinom)
# 2. Si Varianza <= Media (Estabilidad)    -> Usa Poisson (fallback)
# 3. Mantiene lógica de Threshold Dinámico y Proyección N30.
# =============================================================================

import numpy as np
from math import sqrt
from scipy import stats
from datetime import datetime
import os
import csv

from config import Config
from event_config import get_event_config

# =============================================================================
# Z DINÁMICO POR EVENTO
# =============================================================================
Z_BY_EVENT = {
    "goals": 1.0,
    "shots": 0.7,
    "shots_on_target": 0.6,
    "corners": 0.7,
    "cards": 0.7,
    "fouls": 0.7
}

# =============================================================================
# LOGGING
# =============================================================================
LOG_DIR = "logs"
MODEL_LOG_FILE = os.path.join(LOG_DIR, "model_logs.csv")


def log_model_execution(data: dict):
    os.makedirs(LOG_DIR, exist_ok=True)
    file_exists = os.path.isfile(MODEL_LOG_FILE)

    with open(MODEL_LOG_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=data.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(data)


# =============================================================================
# UTILIDADES MATEMÁTICAS (CORE V5.1)
# =============================================================================

def obtener_params_nbinom(mu, sigma2):
    """
    Convierte Media (mu) y Varianza (sigma2) a parámetros (n, p)
    para la distribución Binomial Negativa de Scipy.
    
    Relación:
      mu = n * (1 - p) / p
      sigma2 = n * (1 - p) / p^2
      
    Solución:
      p = mu / sigma2
      n = mu^2 / (sigma2 - mu)
    """
    if sigma2 <= mu:
        return None  # No hay sobredispersión, usar Poisson
    
    p = mu / sigma2
    n = (mu**2) / (sigma2 - mu)
    return n, p


def calcular_probabilidad_hibrida(lam, cv, linea, tipo):
    """
    Calcula probabilidad usando NegBin si hay sobredispersión, sino Poisson.
    """
    k = int(linea)
    sigma2 = (cv * lam) ** 2 if cv > 0 else lam # Estimación de varianza desde CV

    # Intentamos usar Binomial Negativa si hay caos (Var > Media)
    params = obtener_params_nbinom(lam, sigma2)

    if params:
        n_nb, p_nb = params
        # Scipy nbinom usa argumentos (n, p)
        dist = stats.nbinom(n_nb, p_nb)
    else:
        # Fallback a Poisson
        dist = stats.poisson(lam)

    if tipo == "over":
        return 1 - dist.cdf(k)
    else:
        return dist.cdf(k)


def simulacion_monte_carlo_hibrida(lam_l, lam_v, cv_l, cv_v, rho, linea, tipo, sims=8000):
    """
    Simulación Monte Carlo Bivariada que soporta Sobredispersión (NegBin).
    """
    # 1. Generamos correlación usando Gaussian Copula (Dixon-Coles base)
    cov = np.array([[1, rho], [rho, 1]])
    
    # Generamos Z normales correlacionados
    try:
        z = np.random.normal(size=(sims, 2))
        z = z @ np.linalg.cholesky(cov).T
    except Exception:
        z = np.random.normal(size=(sims, 2)) # Fallback sin correlación

    # Convertimos a uniformes correlacionados [0,1]
    u = stats.norm.cdf(z)

    # 2. Transformada Inversa (Inverse Transform Sampling)
    # Para Local
    sigma2_l = (cv_l * lam_l) ** 2 if cv_l > 0 else lam_l
    params_l = obtener_params_nbinom(lam_l, sigma2_l)
    
    if params_l:
        g_l = stats.nbinom(params_l[0], params_l[1]).ppf(u[:, 0])
    else:
        g_l = stats.poisson(lam_l).ppf(u[:, 0])

    # Para Visitante
    sigma2_v = (cv_v * lam_v) ** 2 if cv_v > 0 else lam_v
    params_v = obtener_params_nbinom(lam_v, sigma2_v)
    
    if params_v:
        g_v = stats.nbinom(params_v[0], params_v[1]).ppf(u[:, 1])
    else:
        g_v = stats.poisson(lam_v).ppf(u[:, 1])

    # 3. Suma y Evaluación
    total = g_l + g_v
    
    if tipo == "over":
        return float(np.mean(total > linea))
    else:
        return float(np.mean(total < linea))


# =============================================================================
# MODELO PRINCIPAL
# =============================================================================
def calcular_valor_poisson(
    lambdas: dict,
    n: int,
    tipo: str,
    linea: float,
    odds: float,
    mercado: str,
    event_type: str,
    rho: float = 0.0,
    bankroll: float = Config.BANKROLL_INITIAL,
    unidad: float = Config.UNIT_SIZE,
    modo: str = Config.MODE_PRODUCTION,
    z_system: float = Config.DEFAULT_Z,
    m_fixed: float = Config.DEFAULT_M,
    cvs: dict = None  # <--- NUEVO ARGUMENTO: Coeficientes de Variación
):
    """
    Motor Híbrido Poisson/NegBin — V5.1
    """

    # -------------------------------------------------------------------------
    # 1. CONFIGURACIÓN
    # -------------------------------------------------------------------------
    event_cfg = get_event_config(event_type)
    tipo = tipo.lower()
    mercado = mercado.lower()
    event_key = event_type.lower()

    # Selección Z por evento
    z_event = Z_BY_EVENT.get(event_key, z_system)
    if modo == Config.MODE_PRODUCTION:
        z_event = max(z_event, Config.PRODUCTION_Z_FLOOR)

    # Datos Base
    lambda_local = lambdas.get("Local AF", 0.0)
    lambda_visit = lambdas.get("Visitante AF", 0.0)
    
    # Datos de Volatilidad (Si no llegan, asumimos 0 -> Poisson Puro)
    cv_local = 0.0
    cv_visit = 0.0
    if cvs:
        cv_local = cvs.get("Local", 0.0)
        cv_visit = cvs.get("Visitante", 0.0)

    # -------------------------------------------------------------------------
    # 2. PROBABILIDAD DEL MODELO (HÍBRIDO)
    # -------------------------------------------------------------------------
    if "total partido" in mercado:
        P_model = simulacion_monte_carlo_hibrida(
            lambda_local, lambda_visit,
            cv_local, cv_visit,
            rho, linea, tipo,
            sims=Config.SMC_RUNS
        )
        lambda_usada = lambda_local + lambda_visit

    elif "local" in mercado:
        lambda_usada = lambda_local
        P_model = calcular_probabilidad_hibrida(lambda_usada, cv_local, linea, tipo)

    elif "visitante" in mercado:
        lambda_usada = lambda_visit
        P_model = calcular_probabilidad_hibrida(lambda_usada, cv_visit, linea, tipo)

    else:
        raise ValueError("Mercado no válido")

    # -------------------------------------------------------------------------
    # 3. EDGE
    # -------------------------------------------------------------------------
    P_market = 1 / odds if odds > 1 else 0.0
    edge = P_model - P_market

    # -------------------------------------------------------------------------
    # 4. UMBRAL DINÁMICO & PROYECCIÓN N30
    # -------------------------------------------------------------------------
    se_raw = sqrt(P_model * (1 - P_model) / n) if n > 0 else 0.0
    
    if 10 <= n < 30:
        factor_proyeccion = sqrt(n / 30.0)
        se_usado = se_raw * factor_proyeccion
        tipo_se = "PROJECTED_N30"
    else:
        se_usado = se_raw
        tipo_se = "RAW"

    m_base = m_fixed 

    if n < Config.N_THRESHOLD_DYNAMIC:
        threshold_dynamic = m_base
        reason_threshold = f"FIXED (n={n}, m={m_base})"
        se_reporte = se_raw
    else:
        threshold_dynamic = (z_event * se_usado) + m_base
        reason_threshold = f"{tipo_se} (z={z_event}*SE + m={m_base})"
        se_reporte = se_usado

    threshold_final = max(event_cfg.edge_min, threshold_dynamic)
    aceptado = edge >= threshold_final

    # -------------------------------------------------------------------------
    # 5. GESTIÓN DE CAPITAL (KELLY)
    # -------------------------------------------------------------------------
    kelly = 0.0
    if aceptado and odds > 1:
        kelly_raw = edge / (odds - 1)
        kelly = min(max(kelly_raw * Config.KELLY_FRACTION, 0), Config.KELLY_CAP)

    stake = bankroll * kelly
    unidades = stake / unidad if unidad > 0 else 0.0

    # -------------------------------------------------------------------------
    # 6. LOGGING & RETURN
    # -------------------------------------------------------------------------
    distribucion_usada = "NegBin" if (cv_local**2 * lambda_local > lambda_local) or (cv_visit**2 * lambda_visit > lambda_visit) else "Poisson"
    
    log_model_execution({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "event_type": event_type,
        "market": mercado,
        "tipo": tipo,
        "line": linea,
        "odds": odds,
        "n": n,
        "p_model": round(P_model, 6),
        "edge": round(edge, 6),
        "se": round(se_reporte, 6),
        "threshold": round(threshold_final, 6),
        "kelly": round(kelly, 6),
        "stake": round(stake, 2),
        "accepted": aceptado,
        "modo": modo,
        "distribucion": distribucion_usada
    })

    return {
        "Event_Type": event_type,
        "P_model": round(P_model, 4),
        "P_market": round(P_market, 4),
        "Edge": round(edge, 4),
        "Threshold_Dynamic": round(threshold_final, 4),
        "SE": round(se_reporte, 4),
        "Aceptado": aceptado,
        "Kelly": round(kelly, 4),
        "Stake_U": round(unidades, 2),
        "Modo": modo,
        "Reason": reason_threshold,
        "Model_Dist": distribucion_usada
    }


# =============================================================================
#  NUEVO (V8.0): CÁLCULO MATRICIAL 1X2 (COMPLEMENTO)
#  Este módulo se agrega al final del motor V5.1 sin tocar Monte Carlo.
# =============================================================================
def calcular_probabilidades_1x2(lambda_local, lambda_visit, max_goles=10):
    """
    V8.0: Calcula las probabilidades de Ganador (1), Empate (X), Visitante (2)
    usando una matriz de Poisson cruzada.
    """
    # Importamos stats aquí para asegurar que funcione sin tocar los imports de arriba
    from scipy import stats 
    
    # Generar probabilidades de 0 a max_goles para cada equipo
    probs_local = [stats.poisson.pmf(k, lambda_local) for k in range(max_goles + 1)]
    probs_visit = [stats.poisson.pmf(k, lambda_visit) for k in range(max_goles + 1)]

    p_local_win = 0.0
    p_draw = 0.0
    p_visit_win = 0.0

    # Cruzar probabilidades (Matriz)
    for i in range(len(probs_local)): # Goles Local
        for j in range(len(probs_visit)): # Goles Visitante
            prob_score = probs_local[i] * probs_visit[j]
            
            if i > j:
                p_local_win += prob_score
            elif i == j:
                p_draw += prob_score
            else:
                p_visit_win += prob_score

    # Normalizar para asegurar que sumen 1.0 (por el corte de max_goles)
    total = p_local_win + p_draw + p_visit_win
    if total > 0:
        p_local_win /= total
        p_draw /= total
        p_visit_win /= total

    return {
        "P_Home": p_local_win,
        "P_Draw": p_draw,
        "P_Away": p_visit_win
    }
