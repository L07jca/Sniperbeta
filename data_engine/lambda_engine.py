# =============================================================================
# LAMBDA_ENGINE.PY — MOTOR INTELIGENTE V9.0 (FULL STACK / BUNDESLIGA EDITION)
# -----------------------------------------------------------------------------
# AUTOR: Franco Tirador (Cyborg Edition)
# FECHA: Enero 2026
#
# DESCRIPCIÓN:
# Motor de cálculo de esperanza matemática (Lambdas) para modelos de Poisson.
# Implementa una arquitectura de 4 capas para refinar la predicción pura
# basada en estadísticas históricas.
#
# ARQUITECTURA DE CAPAS:
# 1. CAPA BASE: Modelo Multiplicativo (Dixon-Coles Standard).
#    - Fórmula: (Ataque_Local * Defensa_Visitante) / Media_Liga.
#
# 2. CAPA CONTEXTUAL: Strength of Schedule (SoS).
#    - Ajuste por calidad de rivales pasados (factor multiplicativo).
#
# 3. CAPA ADAPTATIVA: Regresión por Volatilidad (CV).
#    - Si un equipo es inestable (CV alto), se penaliza su promedio hacia la media.
#
# 4. CAPA DE CALIBRACIÓN V9 (NUEVO): Dampening Estructural.
#    - Ajuste fino basado en la correlación real (R²) de cada métrica.
#    - Diferencia el impacto de la defensa en Goles (Alto) vs Tarjetas (Nulo).
# =============================================================================

import math

def construir_lambdas(
    local_af: dict,
    local_ec: dict,
    visit_af: dict,
    visit_ec: dict,
    media_liga: float = None,
    sos_factors: dict = None,
    tipo_evento: str = "default"  # <--- ARGUMENTO CLAVE PARA V9
):
    """
    Construye las Lambdas de Poisson (Esperanza Matemática) aplicando 4 capas de refinamiento.

    Args:
        local_af (dict): Stats Ataque Local {'lambda': float, 'cv': float, 'n': int, ...}
        local_ec (dict): Stats Defensa Local (En Contra)
        visit_af (dict): Stats Ataque Visitante
        visit_ec (dict): Stats Defensa Visitante (En Contra)
        media_liga (float): Promedio global de la liga para este evento.
        sos_factors (dict): Factores de fuerza de calendario (opcional).
        tipo_evento (str): Nombre del evento ('Goles', 'Remates', etc.) para calibración V9.

    Returns:
        dict: Diccionario con lambdas finales y metadatos del cálculo.
              {
                  "lambda_local": float,
                  "lambda_visitante": float,
                  "lambda_total": float,
                  "n": int,
                  "metodo": str,
                  ...
              }
    """

    # =========================================================================
    # 0. VALIDACIÓN DE INTEGRIDAD Y SEGURIDAD (SAFETY FIRST)
    # =========================================================================
    # Verificamos que los inputs sean diccionarios válidos para evitar crashes.
    inputs = [local_af, local_ec, visit_af, visit_ec]

    # Chequeo de tipos básicos
    if not all(isinstance(m, dict) for m in inputs):
        # Retorno de emergencia controlado (evita pantalla roja en Streamlit)
        return {
            "lambda_local": 0.0,
            "lambda_visitante": 0.0,
            "lambda_total": 0.0,
            "n": 0,
            "metodo": "ERROR_INPUT_TYPE"
        }

    # Validación de datos mínimos: Buscamos la clave 'lambda' (media).
    # Si falta, asumimos 0.0 para no romper el flujo, pero marcamos el error implícito.
    # Esto permite que el sistema funcione incluso con datos parciales.
    if not all("lambda" in m for m in inputs):
        # Podríamos lanzar error, pero en producción preferimos continuidad con fallback.
        pass 

    # Determinamos el tamaño de muestra efectivo (el eslabón más débil).
    # Esto sirve para saber qué tanta confianza tener en el dato aguas abajo.
    n_values = [m.get("n", 0) for m in inputs]
    n_efectivo = min(n_values) if n_values else 0

    # Inicializamos logs de auditoría interna del cálculo
    ajuste_aplicado = []
    metodo_usado = "LINEAL" 

    # =========================================================================
    # 1. EXTRACCIÓN DE DATOS BASE
    # =========================================================================
    # Extraemos las medias (lambdas) puras de los diccionarios con defaults seguros.
    l_local_af = float(local_af.get("lambda", 0.0))
    l_local_ec = float(local_ec.get("lambda", 0.0))
    l_visit_af = float(visit_af.get("lambda", 0.0))
    l_visit_ec = float(visit_ec.get("lambda", 0.0))
    
    # Extraemos el Coeficiente de Variación (CV) para la capa adaptativa.
    # Si no existe, asumimos 0.0 (estabilidad perfecta).
    cv_local_af = float(local_af.get("cv", 0.0))
    cv_visit_af = float(visit_af.get("cv", 0.0))
    
    # Establecemos una media de referencia segura.
    # Si media_liga es None o 0, usamos 2.5 como estándar de la industria (Goles).
    media_ref = media_liga if (media_liga is not None and media_liga > 0) else 2.5

    # =========================================================================
    # 2. CAPA BASE: MODELO MULTIPLICATIVO (DIXON-COLES)
    # =========================================================================
    # Esta es la base teórica: La fuerza de ataque se cruza con la debilidad defensiva
    # y se normaliza por la media de la liga.
    # Fórmula: (Fuerza_Ataque * Debilidad_Defensa) / Media_Liga
    
    if media_liga and media_liga > 0:
        try:
            # Cálculo Lambda Local
            # Ejemplo: Si Local ataca 2.0 y Visit defiende 1.5 (Media 1.0) -> (2*1.5)/1 = 3.0
            raw_lambda_local = (l_local_af * l_visit_ec) / media_liga
            
            # Cálculo Lambda Visitante
            raw_lambda_visit = (l_visit_af * l_local_ec) / media_liga
            
            metodo_usado = "MULTIPLICATIVO"
        except ZeroDivisionError:
            # Fallback a promedio simple si media_liga es 0 (improbable pero posible)
            raw_lambda_local = (l_local_af + l_visit_ec) / 2
            raw_lambda_visit = (l_visit_af + l_local_ec) / 2
            metodo_usado = "LINEAL (Div0)"
    else:
        # Fallback Lineal (Promedio aditivo) si no tenemos media de liga
        # Esto sucede a veces en las primeras jornadas o si falla el ETL.
        raw_lambda_local = (l_local_af + l_visit_ec) / 2
        raw_lambda_visit = (l_visit_af + l_local_ec) / 2
        metodo_usado = "LINEAL (Sin Media)"

    # =========================================================================
    # 3. CAPA CONTEXTUAL: STRENGTH OF SCHEDULE (SoS)
    # =========================================================================
    # Ajusta la fuerza base según la calidad de los rivales enfrentados previamente.
    # Si el equipo metió muchos goles contra rivales fáciles, SoS < 1.0 (bajamos la estimación).
    # Si metió goles contra defensas de hierro, SoS > 1.0 (subimos la estimación).
    
    lambda_local_sos = raw_lambda_local
    lambda_visit_sos = raw_lambda_visit

    if sos_factors:
        # Obtenemos factores con default 1.0 (Neutro)
        sos_l = sos_factors.get("local_attack", 1.0)
        sos_v = sos_factors.get("visit_attack", 1.0)
        
        # Aplicamos ajuste
        lambda_local_sos *= sos_l
        lambda_visit_sos *= sos_v
        
        # Registramos si hubo cambio significativo para auditoría
        if sos_l != 1.0 or sos_v != 1.0:
            ajuste_aplicado.append("SoS")

    # =========================================================================
    # 4. CAPA ADAPTATIVA: REGRESIÓN A LA MEDIA (VOLATILIDAD)
    # =========================================================================
    # Si un equipo tiene un CV muy alto (es muy irregular), desconfiamos de su promedio
    # y lo "regresamos" matemáticamente hacia la media de la liga (Shrinkage).
    # Esto previene que una racha de suerte infle artificialmente la predicción.
    
    def aplicar_regresion_volatilidad(valor, cv, media_global):
        """
        Aplica 'Shrinkage' hacia la media global si la volatilidad es alta.
        """
        # Umbrales configurables
        CV_THRESHOLD_CAUTION = 0.50  # Si CV > 0.50, empezamos a ajustar
        MAX_DAMPENING = 0.30         # Máximo ajuste del 30% hacia la media
        
        # Si es estable, no tocamos nada
        if cv <= CV_THRESHOLD_CAUTION:
            return valor, False
            
        # Calculamos factor de regresión lineal basado en exceso de CV
        exceso_cv = cv - CV_THRESHOLD_CAUTION
        dampening_factor = min(exceso_cv * 0.5, MAX_DAMPENING)
        
        # Fórmula: (Valor * (1 - w)) + (Media * w)
        # Asumimos que la media esperada de un equipo es media_global / 2 (reparto equitativo)
        media_esperada_equipo = media_global / 2
        
        valor_ajustado = (valor * (1 - dampening_factor)) + (media_esperada_equipo * dampening_factor)
        
        return valor_ajustado, True

    # Aplicamos regresión a ambos bandos
    lambda_local_adapt, reg_l = aplicar_regresion_volatilidad(lambda_local_sos, cv_local_af, media_ref)
    lambda_visit_adapt, reg_v = aplicar_regresion_volatilidad(lambda_visit_sos, cv_visit_af, media_ref)

    if reg_l or reg_v:
        ajuste_aplicado.append("VOLATILIDAD(CV)")

    # =========================================================================
    # 5. CAPA DE CALIBRACIÓN V9 (DAMPENING ESTRUCTURAL) — [NUEVO]
    # =========================================================================
    # Ajuste fino basado en la correlación real de métricas (Auditado Bundesliga 24/25).
    # Diferencia entre eventos de "Suerte/Arbitro" (Tarjetas) vs "Física" (Tiros).
    
    final_lambda_local = lambda_local_adapt
    final_lambda_visit = lambda_visit_adapt

    # --- DICCIONARIO DE CALIBRACIÓN V9 (EXPANDIDO) ---
    # Contiene variaciones de nombres (inglés/español) para evitar errores de mapeo.
    # Estos coeficientes representan el % de influencia real de la defensa en el evento.
    dampening_config = {
        # GOLES: Alta dependencia defensiva (R2 ~ 0.50)
        "Goles": 0.50, 
        "goals": 0.50,
        "Total Goles": 0.50,

        # REMATES: Volumen alto, la defensa influye pero menos (R2 ~ 0.24)
        "Remates": 0.24, 
        "Remates (Shots)": 0.24, 
        "shots": 0.24,
        "Tiros": 0.24,

        # REMATES A PUERTA: Precisión técnica (R2 ~ 0.29)
        "Remates a Puerta": 0.29, 
        "shots_on_target": 0.29,
        "SoT": 0.29,

        # CÓRNERS: Ruido táctico (R2 ~ 0.15)
        "Córners": 0.15, 
        "corners": 0.15,

        # FALTAS: Estilo propio, poca influencia rival (R2 ~ 0.05)
        "Faltas": 0.05, 
        "fouls": 0.05,

        # TARJETAS: Arbitraje y disciplina propia (R2 ~ 0.05)
        "Tarjetas": 0.05, 
        "Tarjetas Amarillas": 0.05,
        "cards": 0.05,
        "yellow_cards": 0.05,

        # DEFAULT: Valor seguro para mercados desconocidos
        "default": 0.15
    }

    # --- DETECCIÓN INTELIGENTE DEL TIPO DE EVENTO ---
    # Intentamos matchear el string 'tipo_evento' con las claves del config.
    key_found = "default"
    
    if tipo_evento in dampening_config:
        key_found = tipo_evento
    else:
        # Búsqueda heurística por texto (Fuzzy matching simple)
        evt_lower = str(tipo_evento).lower()
        if "gol" in evt_lower: key_found = "Goles"
        elif "shot" in evt_lower or "remate" in evt_lower:
            if "target" in evt_lower or "puerta" in evt_lower: 
                key_found = "Remates a Puerta"
            else: 
                key_found = "Remates"
        elif "corner" in evt_lower: key_found = "Córners"
        elif "card" in evt_lower or "tarjeta" in evt_lower: key_found = "Tarjetas"
        elif "foul" in evt_lower or "falta" in evt_lower: key_found = "Faltas"

    # Obtenemos el coeficiente V9 final
    target_dampening = dampening_config.get(key_found, 0.15)

    # --- APLICACIÓN DEL ALGORITMO V9 ---
    if media_liga and media_liga > 0:
        avg_conceded = media_liga / 2
        
        # Calculamos qué tan buena/mala es la defensa del rival comparada con la media
        # Si la defensa es NORMAL, factor ~ 1.0 -> No hay cambio.
        # Si la defensa es MUY MALA (concede mucho), factor > 1.0 -> Aumenta lambda.
        # Si la defensa es MUY BUENA (concede poco), factor < 1.0 -> Reduce lambda.
        
        f_def_visit = l_visit_ec / avg_conceded if avg_conceded > 0 else 1.0
        f_def_local = l_local_ec / avg_conceded if avg_conceded > 0 else 1.0

        # Aplicamos el "Freno" (Dampening) al factor defensivo
        # Fórmula: Factor_Ajustado = (Factor_Real - 1) * Coeficiente + 1
        # Si target_dampening es bajo (ej. 0.05), el adj se acerca a 1.0 (neutraliza defensa).
        
        adj_visit = (f_def_visit - 1) * target_dampening + 1
        adj_local = (f_def_local - 1) * target_dampening + 1
        
        # --- CLAMPS DE SEGURIDAD (V9) ---
        # Evitamos que una defensa rota distorsione la proyección al infinito.
        # Goles permite un rango un poco más amplio (1.35) que otros eventos.
        
        max_clamp = 1.35 if "Gol" in key_found else 1.25
        min_clamp = 0.80
        
        adj_visit = max(min_clamp, min(adj_visit, max_clamp))
        adj_local = max(min_clamp, min(adj_local, max_clamp))
        
        # Aplicamos el ajuste V9 sobre las lambdas (Modulación Final)
        final_lambda_local = final_lambda_local * adj_visit
        final_lambda_visit = final_lambda_visit * adj_local
        
        # Registramos en el log si el ajuste fue significativo para la auditoría
        if abs(adj_visit - 1.0) > 0.01 or abs(adj_local - 1.0) > 0.01:
            ajuste_aplicado.append(f"V9({target_dampening})")

    # =========================================================================
    # 6. RETORNO FINAL
    # =========================================================================
    # Construimos el string de método para mostrar en el frontend (transparencia).
    if ajuste_aplicado:
        metodo_usado += f" + [{'|'.join(ajuste_aplicado)}]"

    return {
        "lambda_local": round(final_lambda_local, 4),
        "lambda_visitante": round(final_lambda_visit, 4),
        "lambda_total": round(final_lambda_local + final_lambda_visit, 4),
        "n": n_efectivo,
        "metodo": metodo_usado,
        # Datos extra para debug y auditoría forense
        "raw_local_base": round(raw_lambda_local, 4),
        "raw_visit_base": round(raw_lambda_visit, 4),
        "cv_local": round(cv_local_af, 2),
        "cv_visit": round(cv_visit_af, 2),
        "v9_coeff": target_dampening
    }
