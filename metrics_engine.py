# =============================================================================
# METRICS_ENGINE.PY — MÉTRICAS AVANZADAS (FASE 8.4.2)
# SOLO LECTURA — NO INTERFIERE CON EL MODELO
# =============================================================================

import pandas as pd
import os
import numpy as np

DATA_FILE = "data/results.csv"


# =============================================================================
# CARGA SEGURA
# =============================================================================
def cargar_resultados():
    if not os.path.exists(DATA_FILE):
        return pd.DataFrame()

    try:
        df = pd.read_csv(DATA_FILE, engine="python", on_bad_lines="skip")
    except Exception:
        return pd.DataFrame()

    required = {"stake", "odds", "result"}

    if not required.issubset(df.columns):
        return pd.DataFrame()

    df = df.dropna(subset=["stake", "odds", "result"])

    return df


# =============================================================================
# MÉTRICAS PRINCIPALES
# =============================================================================
def calcular_metricas_avanzadas():
    df = cargar_resultados()

    if df.empty or len(df) < 5:
        return None

    df = df.copy()

    # --------------------------
    # PROFIT
    # --------------------------
    df["profit"] = np.where(
        df["result"] == 1,
        df["stake"] * (df["odds"] - 1),
        np.where(df["result"] == -1, -df["stake"], 0)
    )

    stake_total = df["stake"].sum()
    profit_total = df["profit"].sum()
    n_picks = len(df)

    # --------------------------
    # ROI
    # --------------------------
    roi_total = profit_total / stake_total if stake_total > 0 else 0.0

    last20 = df.tail(20)
    roi_20 = (
        last20["profit"].sum() / last20["stake"].sum()
        if last20["stake"].sum() > 0
        else 0.0
    )

    # --------------------------
    # YIELD
    # --------------------------
    yield_total = roi_total  # mismo concepto en apuestas

    # --------------------------
    # SHARPE SIMPLIFICADO
    # --------------------------
    returns = df["profit"] / df["stake"]
    sharpe = (
        returns.mean() / returns.std()
        if returns.std() > 0
        else 0.0
    )

    return {
        "roi_total": round(roi_total, 4),
        "roi_20": round(roi_20, 4),
        "yield": round(yield_total, 4),
        "sharpe": round(sharpe, 3),
        "profit_total": round(profit_total, 2),
        "stake_total": round(stake_total, 2),
        "n_picks": n_picks
    }
