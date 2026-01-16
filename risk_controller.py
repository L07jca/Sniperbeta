import pandas as pd
import os

# NOTA AUDITORÍA: Se elimina la importación rota a 'calcular_lambdas_automaticas'
# para evitar el ImportError. El resto de la lógica de seguridad se mantiene.

DATA_FILE = "data/results.csv"
BANKROLL_INICIAL = 20000.0

# =============================================================================
# CARGA HISTÓRICO SEGURA
# =============================================================================
def cargar_historico():
    if not os.path.exists(DATA_FILE):
        return pd.DataFrame()

    try:
        df = pd.read_csv(DATA_FILE, engine="python", on_bad_lines="skip")
    except Exception:
        return pd.DataFrame()

    # Columnas esperadas mínimas para evitar KeyErrors
    columnas_default = {
        "stake": 0.0,
        "odds": 0.0,
        "result": None,
        "profit": 0.0,
        "market": "",
        "tipo": "",
        "line": 0.0
    }

    for c, v in columnas_default.items():
        if c not in df.columns:
            df[c] = v

    return df


# =============================================================================
# EVALUAR ESTADO GLOBAL DEL SISTEMA (FASE 6)
# =============================================================================
def evaluar_estado_sistema():
    """
    Analiza el rendimiento reciente para determinar si el sistema
    debe entrar en modo BLOQUEO o RECUPERACIÓN.
    """
    df = cargar_historico()

    estado = {
        "estado": "NORMAL",
        "drawdown": 0.0,
        "roi_rolling": 0.0,
        "recovery_streak": 0,
        "z": 1.0,
        "kelly_factor": 1.0,
        "bankroll": BANKROLL_INICIAL
    }

    if df.empty:
        return estado

    # ==========================
    # CÁLCULO DE BANKROLL ACTUAL
    # ==========================
    # Si tenemos un archivo bankroll.csv fiable, lo ideal sería leerlo de ahí.
    # Aquí lo reconstruimos sumando el profit al inicial como fallback robusto.
    profit_acumulado = df["profit"].sum()
    bankroll_actual = BANKROLL_INICIAL + profit_acumulado
    estado["bankroll"] = bankroll_actual

    # ==========================
    # DRAWDOWN
    # ==========================
    # Reconstrucción de curva de equidad
    df["cumulative_profit"] = df["profit"].cumsum()
    df["equity"] = BANKROLL_INICIAL + df["cumulative_profit"]
    
    peak = df["equity"].cummax()
    drawdown = (peak - df["equity"]) / peak
    
    # El drawdown actual es el último valor de la serie
    current_drawdown = drawdown.iloc[-1] if not drawdown.empty else 0.0
    estado["drawdown"] = current_drawdown

    # ==========================
    # ROI ROLLING (Últimos 20 picks)
    # ==========================
    last20 = df.tail(20)
    stake_sum = last20["stake"].sum()
    if stake_sum > 0:
        estado["roi_rolling"] = last20["profit"].sum() / stake_sum

    # ==========================
    # STREAK DE PÉRDIDAS (Racha actual)
    # ==========================
    # Contamos cuántos -1 seguidos hay al final
    streak = 0
    if not df.empty:
        results = df["result"].tolist()
        for r in reversed(results):
            if r == -1:
                streak += 1
            else:
                break
    estado["recovery_streak"] = streak

    # ==========================
    # REGLAS DE ESTADO (SEMÁFORO)
    # ==========================
    # 1. BLOQUEO DURO: Drawdown > 25% o ROI muy negativo
    if estado["drawdown"] > 0.25 or estado["roi_rolling"] < -0.15:
        estado["estado"] = "BLOQUEADO"
        estado["z"] = None
        estado["kelly_factor"] = 0.0

    # 2. MODO RECUPERACIÓN: Racha de 3 pérdidas seguidas
    elif streak >= 3:
        estado["estado"] = "RECUPERACIÓN"
        estado["z"] = 1.3        # Exigimos más certeza (Z más alto)
        estado["kelly_factor"] = 0.5 # Apostamos la mitad

    # 3. NORMAL
    else:
        estado["estado"] = "NORMAL"
        estado["z"] = 1.0
        estado["kelly_factor"] = 1.0

    return estado