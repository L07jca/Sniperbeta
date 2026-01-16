import pandas as pd
import os
from datetime import datetime

RESULTS_FILE = "data/results.csv"
BANKROLL_FILE = "data/bankroll.csv"
# Este valor inicial solo se usa si no existe el archivo
BANKROLL_DEFAULT_INIT = 20000.0


# =============================================================================
# INIT
# =============================================================================
def _init_files():
    os.makedirs("data", exist_ok=True)

    if not os.path.exists(RESULTS_FILE):
        # AÑADIDO: Columna 'units' para rastrear el stake en fichas
        df = pd.DataFrame(columns=[
            "timestamp",
            "match",
            "market",
            "tipo",
            "line",
            "odds",
            "P_model",
            "EV",
            "stake",      # Dinero real ($)
            "units",      # Unidades (Fichas)
            "accepted",
            "result",
            "profit",
            "bankroll"
        ])
        df.to_csv(RESULTS_FILE, index=False)

    if not os.path.exists(BANKROLL_FILE):
        dfb = pd.DataFrame([{
            "timestamp": datetime.utcnow().isoformat(),
            "bankroll": BANKROLL_DEFAULT_INIT
        }])
        dfb.to_csv(BANKROLL_FILE, index=False)


def _get_current_bankroll():
    if not os.path.exists(BANKROLL_FILE):
        _init_files()
    dfb = pd.read_csv(BANKROLL_FILE)
    if dfb.empty:
        return BANKROLL_DEFAULT_INIT
    return float(dfb.iloc[-1]["bankroll"])


def _update_bankroll(new_bankroll):
    dfb = pd.read_csv(BANKROLL_FILE)
    dfb = pd.concat([
        dfb,
        pd.DataFrame([{
            "timestamp": datetime.utcnow().isoformat(),
            "bankroll": round(new_bankroll, 2)
        }])
    ], ignore_index=True)
    dfb.to_csv(BANKROLL_FILE, index=False)


# =============================================================================
# LOG PICK
# =============================================================================
def log_pick(
    match,
    market,
    tipo,
    line,
    odds,
    P_model,
    EV,
    stake,        # Dinero ($)
    accepted,
    units=0.0,    # Fichas (Nuevo parámetro opcional para compatibilidad)
    result=None
):
    """
    Registra un pick.
    Ahora soporta registro de 'units' (fichas) además de 'stake' ($).
    """

    _init_files()

    if stake <= 0 or odds <= 1:
        raise ValueError("Stake u odds inválidos")

    bankroll_actual = _get_current_bankroll()
    profit = 0.0
    # Si el pick entra como pendiente (result=None), no tocamos el bankroll aún.
    # Solo restamos si se marca como PERDIDO (-1) o sumamos si GANADO (1).
    # Pero al registrarlo, el bankroll "disponible" no cambia hasta liquidar.
    # (Para simplificar, guardamos el bankroll actual en el registro).
    
    bankroll_log = bankroll_actual

    # Si ya viene con resultado (ej. carga manual histórica), actualizamos bank
    if accepted and result is not None:
        if result == 1:
            profit = stake * (odds - 1)
        elif result == -1:
            profit = -stake
        else:
            profit = 0.0 # Push/Void

        bankroll_log = bankroll_actual + profit
        _update_bankroll(bankroll_log)

    new_row = {
        "timestamp": datetime.utcnow().isoformat(),
        "match": match,
        "market": market,
        "tipo": tipo,
        "line": line,
        "odds": odds,
        "P_model": round(P_model, 4),
        "EV": round(EV, 4),
        "stake": round(stake, 2),
        "units": round(units, 2),  # Guardamos las fichas
        "accepted": accepted,
        "result": result,
        "profit": round(profit, 2),
        "bankroll": round(bankroll_log, 2)
    }

    df = pd.read_csv(RESULTS_FILE)
    # Manejo de columnas nuevas en CSV viejo
    if "units" not in df.columns:
        df["units"] = 0.0
        
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(RESULTS_FILE, index=False)
    
# =============================================================================
# LIQUIDAR PICK
# =============================================================================
def liquidar_pick(index, result):
    """
    Liquida un pick pendiente por índice
    """

    _init_files()

    df = pd.read_csv(RESULTS_FILE)

    if index < 0 or index >= len(df):
        raise IndexError("Índice fuera de rango")

    if pd.notna(df.loc[index, "result"]):
        raise ValueError("Pick ya liquidado")

    stake = float(df.loc[index, "stake"])
    odds = float(df.loc[index, "odds"])

    bankroll_actual = _get_current_bankroll()

    if result == 1:
        profit = stake * (odds - 1)
    elif result == -1:
        profit = -stake
    else:
        profit = 0.0

    bankroll_nuevo = bankroll_actual + profit
    _update_bankroll(bankroll_nuevo)

    df.loc[index, "result"] = result
    df.loc[index, "profit"] = round(profit, 2)
    df.loc[index, "bankroll"] = round(bankroll_nuevo, 2)

    df.to_csv(RESULTS_FILE, index=False)