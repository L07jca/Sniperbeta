# health_engine.py
import pandas as pd
from pathlib import Path

RESULTS_FILE = Path("data/results.csv")
RECHAZOS_FILE = Path("data/rechazos_audit.csv")


def cargar_salud_sistema():
    """
    Analiza la salud técnica del sistema basándose en los resultados históricos.
    Devuelve un diccionario con estadísticas y un estado semáforo.
    """
    if not RESULTS_FILE.exists():
        # Estado por defecto si no hay datos
        return {
            "estado": "VERDE", 
            "total_picks": 0,
            "aceptados": 0,
            "rechazados": 0,
            "ratio_aceptacion": 0.0,
            "ratio_rechazo": 0.0
        }

    df = pd.read_csv(RESULTS_FILE)

    total = len(df)
    aceptados = len(df[df["accepted"] == True])
    rechazados = total - aceptados

    ratio_aceptacion = aceptados / total if total > 0 else 0
    ratio_rechazo = rechazados / total if total > 0 else 0

    # -------------------------------------------------------------------------
    # LÓGICA DE SEMÁFORO (TÉCNICO)
    # -------------------------------------------------------------------------
    # Si rechazamos más del 80% de lo que analizamos, algo pasa con los filtros.
    if total > 10 and ratio_rechazo > 0.80:
        estado_salud = "ROJO"
    elif total > 10 and ratio_rechazo > 0.50:
        estado_salud = "AMARILLO"
    else:
        estado_salud = "VERDE"

    return {
        "estado": estado_salud,
        "total_picks": total,
        "aceptados": aceptados,
        "rechazados": rechazados,
        "ratio_aceptacion": ratio_aceptacion,
        "ratio_rechazo": ratio_rechazo
    }


def cargar_rechazos_detalle():
    if not RECHAZOS_FILE.exists():
        return None

    df = pd.read_csv(RECHAZOS_FILE)

    resumen_fase = df["fase"].value_counts().to_dict()
    resumen_estado = df["estado_sistema"].value_counts().to_dict()

    causas = {}
    for razones in df["razones"]:
        for r in str(razones).split(";"):
            causas[r] = causas.get(r, 0) + 1

    return {
        "total_rechazos": len(df),
        "por_fase": resumen_fase,
        "por_estado": resumen_estado,
        "causas_top": causas
    }