# risk_gate.py
from config import Config

def evaluar_pre_poisson(
    estado_sistema: dict,
    cv_max: float
):
    """
    Evalúa si el sistema permite ejecutar Poisson.
    Retorna (permitido: bool, razones: list[str])
    """

    razones = []

    # 1. Chequeo de Estado Global
    if estado_sistema["estado"] == "BLOQUEADO":
        razones.append("SISTEMA_BLOQUEADO")

    # 2. Chequeo de Salud Financiera
    if estado_sistema["drawdown"] >= 0.10:
        razones.append("DRAWDOWN_ALTO")

    if estado_sistema["kelly_factor"] < 0.5:
        razones.append("KELLY_COLAPSADO")

    if estado_sistema["roi_rolling"] < -0.10: # Tolerancia leve
        razones.append("ROI_ROLLING_NEGATIVO")

    # 3. PROTOCOLO DE ESTABILIDAD (NUEVO - FASE M)
    # Compara el CV actual del partido con el límite global configurado en Config.
    # El backtest demostró que CV > 0.85 es zona de pérdida en la mayoría de ligas.
    if cv_max > Config.MAX_CV_ALLOWED:
        razones.append(f"CV_CRITICO ({round(cv_max, 2)} > {Config.MAX_CV_ALLOWED})")

    permitido = len(razones) == 0

    return permitido, razones