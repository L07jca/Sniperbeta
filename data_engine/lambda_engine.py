# =============================================================================
# LAMBDA_ENGINE.PY — MOTOR INTELIGENTE V9.0 (FULL STACK)
# -----------------------------------------------------------------------------
# 1. Modelo Base: Multiplicativo (Ataque * Defensa / Media)
# 2. Capa Contextual: Ajuste por Strength of Schedule (SoS)
# 3. Capa Adaptativa: Regresión a la media basada en Volatilidad (CV)
# 4. Capa Calibración V9: Ajuste fino por correlación de métricas (Bundesliga)
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
    Construye las Lambdas de Poisson aplicando 4 capas de refinamiento lógico.
    
    Args:
        local_af, local_ec: Estadísticas del Local (A favor/En contra)
            -> Espera dict con keys: {'lambda', 'cv', 'n', 'valido', ...}
        visit_af, visit_ec: Estadísticas del Visitante
        media_liga: Promedio global de la liga para este evento.
        sos_factors: Factores de fuerza de calendario (opcional).
        tipo_evento: Nombre del evento ('Goles', 'Remates', etc.) para calibración V9.
    """

    # -------------------------------------------------------------------------
    # 0. VALIDACIÓN DE INTEGRIDAD (SAFETY FIRST)
    # -------------------------------------------------------------------------
    inputs = [local_af, local_ec, visit_af, visit_ec]

    # Validación de tipos
    if not all(isinstance(m, dict) for m in inputs):
        raise ValueError("Error Crítico LambdaEngine: Los inputs deben ser diccionarios.")

    # Validación de datos mínimos requeridos
    # Permitimos continuar si 'lambda' existe, aunque 'valido' sea False (modo fallback)
    if not all("lambda" in m for m in inputs):
        raise ValueError("Error Crítico LambdaEngine: Estructura de datos incompleta (falta 'lambda').")

    # Extracción de N (tamaño de muestra efectivo)
    n_values = [m.get("n", 0) for m in inputs]
    n_efectivo = min(n_values) if n_values else 0

    ajuste_aplicado = []
    metodo_usado = "LINEAL" # Default si falla todo

    # -------------------------------------------------------------------------
    # 1. EXTRACCIÓN DE DATOS BASE
    # -------------------------------------------------------------------------
    l_local_af = float(local_af.get("lambda", 0.0))
    l_local_ec = float(local_ec.get("lambda", 0.0))
    l_visit_af = float(visit_af.get("lambda", 0.0))
    l_visit_ec = float(visit_ec.get("lambda", 0.0))
    
    # Extraemos CV (Coeficiente de Variación) para la capa adaptativa
    cv_local_af = float(local_af.get("cv", 0.0))
    cv_visit_af = float(visit_af.get("cv", 0.0))
    
    # Media de referencia segura
    media_ref = media_liga if (media_liga is not None and media_liga > 0) else 2.5

    # -------------------------------------------------------------------------
    # 2. CAPA BASE: MODELO MULTIPLICATIVO (DIXON-COLES STANDARD)
    # -------------------------------------------------------------------------
    # Exp_Local = (Ataque_Local * Defensa_Visitante) / Media_Liga
    
    if media_liga and media_liga > 0:
        try:
            raw_lambda_local = (l_local_af * l_visit_ec) / media_liga
            raw_lambda_visit = (l_visit_af * l_local_ec) / media_liga
            metodo_usado = "MULTIPLICATIVO"
        except ZeroDivisionError:
            # Fallback a promedio simple si media_liga es 0 (improbable)
            raw_lambda_local = (l_local_af + l_visit_ec) / 2
            raw_lambda_visit = (l_visit_af + l_local_ec) / 2
            metodo_usado = "LINEAL (Div0)"
    else:
        # Fallback Lineal
        raw_lambda_local = (l_local_af + l_visit_ec) / 2
        raw_lambda_visit = (l_visit_af + l_local_ec) / 2
        metodo_usado = "LINEAL (Sin Media)"

    # -------------------------------------------------------------------------
    # 3. CAPA CONTEXTUAL: STRENGTH OF SCHEDULE (SoS)
    # -------------------------------------------------------------------------
    # Ajusta la fuerza base según la calidad de los rivales enfrentados previamente.
    
    lambda_local_sos = raw_lambda_local
    lambda_visit_sos = raw_lambda_visit

    if sos_factors:
        sos_l = sos_factors.get("local_attack", 1.0)
        sos_v = sos_factors.get("visit_attack", 1.0)
        
        lambda_local_sos *= sos_l
        lambda_visit_sos *= sos_v
        
        if sos_l != 1.0 or sos_v != 1.0:
            ajuste_aplicado.append("SoS")

    # -------------------------------------------------------------------------
    # 4. CAPA ADAPTATIVA: REGRESIÓN A LA MEDIA (VOLATILIDAD)
    # -------------------------------------------------------------------------
    # Si un equipo tiene un CV muy alto (es inestable), desconfiamos de su promedio
    # y lo "regresamos" matemáticamente hacia la media de la liga.
    # Esta era la lógica que echabas de menos.
    
    def aplicar_regresion_volatilidad(valor, cv, media_global):
        """
        Aplica 'Shrinkage' hacia la media global si la volatilidad es alta.
        """
        CV_THRESHOLD_CAUTION = 0.50  # Si CV > 0.50, empezamos a ajustar
        MAX_DAMPENING = 0.30         # Máximo ajuste del 30% hacia la media
        
        if cv <= CV_THRESHOLD_CAUTION:
            return valor, False
            
        # Factor de regresión lineal basado en exceso de CV
        exceso_cv = cv - CV_THRESHOLD_CAUTION
        dampening_factor = min(exceso_cv * 0.5, MAX_DAMPENING)
        
        # Fórmula: (Valor * (1 - w)) + (Media * w)
        # Asumimos que la media del equipo tiende a media_global/2 (promedio por bando)
        media_esperada_equipo = media_global / 2
        
        valor_ajustado = (valor * (1 - dampening_factor)) + (media_esperada_equipo * dampening_factor)
        
        return valor_ajustado, True

    # Aplicamos regresión
    lambda_local_adapt, reg_l = aplicar_regresion_volatilidad(lambda_local_sos, cv_local_af, media_ref)
    lambda_visit_adapt, reg_v = aplicar_regresion_volatilidad(lambda_visit_sos, cv_visit_af, media_ref)

    if reg_l or reg_v:
        ajuste_aplicado.append("VOLATILIDAD(CV)")

    # -------------------------------------------------------------------------
    # 5. CAPA DE CALIBRACIÓN V9 (DAMPENING ESTRUCTURAL) — [NUEVO]
    # -------------------------------------------------------------------------
    # Ajuste fino basado en la correlación real de métricas (Bundesliga 24/25).
    # Diferencia entre eventos de "Suerte/Arbitro" (Tarjetas) vs "Física" (Tiros).
    
    final_lambda_local = lambda_local_adapt
    final_lambda_visit = lambda_visit_adapt

    # Diccionario de Coeficientes V9 (Calibrado)
    dampening_config = {
        "Goles": 0.50,              # Goles: 50% Ataque / 50% Defensa
        "goals": 0.50,
        "Remates": 0.24,            # Remates: 76% Ataque / 24% Defensa (Permisivo)
        "Remates (Shots)": 0.24,
        "shots": 0.24,
        "Remates a Puerta": 0.29,   # Precisión: 29% influencia defensiva
        "shots_on_target": 0.29,
        "Córners": 0.15,            # Poca influencia defensiva
        "corners": 0.15,
        "Faltas": 0.05,             # Casi nula influencia defensiva (Estilo propio)
        "fouls": 0.05,
        "Tarjetas": 0.05,           # Arbitraje manda
        "cards": 0.05,
        "default": 0.15
    }

    # Detección inteligente del tipo de evento
    key_found = "default"
    if tipo_evento in dampening_config:
        key_found = tipo_evento
    else:
        # Búsqueda heurística por texto
        evt_lower = str(tipo_evento).lower()
        if "gol" in evt_lower: key_found = "Goles"
        elif "shot" in evt_lower or "remate" in evt_lower:
            if "target" in evt_lower or "puerta" in evt_lower: key_found = "Remates a Puerta"
            else: key_found = "Remates (Shots)"
        elif "corner" in evt_lower: key_found = "Córners"
        elif "card" in evt_lower or "tarjeta" in evt_lower: key_found = "Tarjetas"
        elif "foul" in evt_lower or "falta" in evt_lower: key_found = "Faltas"

    # Obtener coeficiente V9
    target_dampening = dampening_config.get(key_found, 0.15)

    # Lógica de Ajuste V9
    if media_liga and media_liga > 0:
        avg_conceded = media_liga / 2
        
        # Calculamos qué tan buena/mala es la defensa del rival comparada con la media
        # Si la defensa es NORMAL, factor ~ 1.0 -> No hay cambio.
        # Si la defensa es MUY MALA, factor > 1.0 -> Aumenta lambda.
        f_def_visit = l_visit_ec / avg_conceded if avg_conceded > 0 else 1.0
        f_def_local = l_local_ec / avg_conceded if avg_conceded > 0 else 1.0

        # Aplicamos el "Freno" (Dampening) al factor defensivo
        # Si target_dampening es bajo (ej. 0.05), la defensa importa poco -> adj se acerca a 1.0
        adj_visit = (f_def_visit - 1) * target_dampening + 1
        adj_local = (f_def_local - 1) * target_dampening + 1
        
        # Clamps (Límites de seguridad para evitar explosiones)
        max_clamp = 1.35 if "Gol" in key_found else 1.25
        min_clamp = 0.80
        
        adj_visit = max(min_clamp, min(adj_visit, max_clamp))
        adj_local = max(min_clamp, min(adj_local, max_clamp))
        
        # Aplicamos el ajuste V9 sobre las lambdas ya adaptadas
        # Nota: Usamos la lambda base (raw) para el cálculo multiplicativo puro
        # y luego modulamos con el V9. Esto es híbrido.
        # Para respetar tu lógica anterior, aplicamos sobre la lambda que traíamos (adaptada).
        
        final_lambda_local = final_lambda_local * adj_visit
        final_lambda_visit = final_lambda_visit * adj_local
        
        # Registramos que se usó V9
        if abs(adj_visit - 1.0) > 0.01 or abs(adj_local - 1.0) > 0.01:
            tag = f"V9({key_found}:{target_dampening})"
            if tag not in ajuste_aplicado:
                ajuste_aplicado.append(tag)

    # -------------------------------------------------------------------------
    # 6. CONSTRUCCIÓN DEL DIAGNÓSTICO
    # -------------------------------------------------------------------------
    if ajuste_aplicado:
        metodo_usado += f" + [{'|'.join(ajuste_aplicado)}]"

    return {
        "lambda_local": round(final_lambda_local, 4),
        "lambda_visitante": round(final_lambda_visit, 4),
        "lambda_total": round(final_lambda_local + final_lambda_visit, 4),
        "n": n_efectivo,
        "metodo": metodo_usado,
        # Datos extra para debug/auditoría
        "raw_local_base": round(raw_lambda_local, 4),
        "raw_visit_
