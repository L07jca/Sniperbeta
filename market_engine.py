# =============================================================================
# MARKET_ENGINE.PY — FASE 13.1
# Normalización y transformación de lambdas por mercado
# =============================================================================

def calcular_lambda_mercado(
    lambda_local: float,
    lambda_visitante: float,
    mercado: str
):
    """
    Devuelve lambda efectiva según el mercado seleccionado.
    """

    mercado = mercado.lower()

    if "total partido" in mercado:
        return lambda_local + lambda_visitante

    if "total local" in mercado or "local" in mercado:
        return lambda_local

    if "total visitante" in mercado or "visitante" in mercado:
        return lambda_visitante

    raise ValueError(f"Mercado no soportado: {mercado}")
