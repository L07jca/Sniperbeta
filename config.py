# =============================================================================
# CONFIG.PY — FUENTE ÚNICA DE VERDAD (GLOBAL)
# Proyecto: Franco Tirador Poisson
# FASE N — Gestión de Banca Dinámica (1% Unit)
# =============================================================================

class Config:

    # -------------------------------------------------------------------------
    # IDENTIDAD DEL PROYECTO
    # -------------------------------------------------------------------------
    PROJECT_NAME = "Franco Tirador Poisson"
    VERSION = "4.6.0"   # Fase N (Dynamic Bankroll)
    MODE_PRODUCTION = "PRODUCCIÓN"
    MODE_LAB = "LABORATORIO"

    # -------------------------------------------------------------------------
    # CONTROL GLOBAL DE INCERTIDUMBRE
    # -------------------------------------------------------------------------
    # z controla cuántas desviaciones estándar exigimos
    DEFAULT_Z = 1.0                 # ≈ 68% CI (razonable para mercados líquidos)

    # m_base = margen mínimo "real" sobre el vig
    # ---------------------------------------------------------------------
    # 🔴 CORRECCIÓN AUDITORÍA — REGLA DEL USUARIO
    # Regla explícita: m = 0.10 (Filtro Duro Francotirador)
    # ---------------------------------------------------------------------
    DEFAULT_M = 0.10                

    # A partir de este n se activa z * SE
    N_THRESHOLD_DYNAMIC = 10

    # (informativo)
    CONFIDENCE_LEVEL = 0.6827

    # -------------------------------------------------------------------------
    # PROTOCOLO DE ESTABILIDAD (NUEVO - FASE M)
    # -------------------------------------------------------------------------
    # Límite de Coeficiente de Variación (CV) permitido.
    # El backtest mostró que CV > 1.0 genera pérdidas en 3 de 4 ligas.
    # Ajustamos a 0.85 para filtrar el caos extremo sin matar todo el volumen.
    MAX_CV_ALLOWED = 0.85

    # -------------------------------------------------------------------------
    # MONTE CARLO
    # -------------------------------------------------------------------------
    SMC_RUNS = 8000                 # suficiente estabilidad
    SMC_TOLERANCE = 0.05

    # -------------------------------------------------------------------------
    # DATA (GENÉRICO)
    # -------------------------------------------------------------------------
    MIN_MATCHES_DATA = 5

    # -------------------------------------------------------------------------
    # GESTIÓN DE BANCA DINÁMICA (NUEVO - FASE N)
    # -------------------------------------------------------------------------
    # Regla: 1 Unidad = 1% del Bankroll Actual (Modelo Casino)
    BANKROLL_UNIT_PCT = 0.01        # 1%
    
    # Kelly
    EV_MIN_GLOBAL = 0.00             # el edge mínimo vive por EVENTO
    KELLY_CAP = 0.05                 # 5% banca máx (5 Unidades)
    KELLY_FRACTION = 0.50            # Medio Kelly (profesional)

    # Valores Iniciales (Solo para arranque)
    BANKROLL_INITIAL = 20000.0
    UNIT_SIZE = 10.0 # (Fallback si no hay dinámica)

    # -------------------------------------------------------------------------
    # PRODUCCIÓN — POLÍTICA DE SEGURIDAD
    # -------------------------------------------------------------------------
    PRODUCTION_Z_FLOOR = 0.6
    
    # -------------------------------------------------------------------------
    # ⚠️ PENDIENTE DE CALIBRACIÓN FINA (NO TOCAR EN FASE E)
    # -------------------------------------------------------------------------
    # - Ajuste fino de:
    #   • DEFAULT_M
    #   • DEFAULT_Z
    #   • edge_min por evento
    # Se hará con backtest estadísticamente válido y bins calibrados.
    # -------------------------------------------------------------------------
