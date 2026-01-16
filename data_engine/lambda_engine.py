# =============================================================================
# LAMBDA_ENGINE.PY — MOTOR INTELIGENTE V5.0 (CONTEXT AWARE)
# -----------------------------------------------------------------------------
# 1. Modelo Base: Multiplicativo (Ataque * Defensa / Media)
# 2. Capa Contextual: Ajuste por Strength of Schedule (SoS)
# 3. Capa Adaptativa: Regresión a la media basada en Volatilidad (CV)
# =============================================================================

def construir_lambdas(
    local_af: dict,
    local_ec: dict,
    visit_af: dict,
    visit_ec: dict,
    media_liga: float = None,
    sos_factors: dict = None
):
    """
    Construye las Lambdas de Poisson aplicando lógica avanzada de contexto.
    
    Args:
        local_af, local_ec: Estadísticas del Local (A favor/En contra)
        visit_af, visit_ec: Estadísticas del Visitante
        media_liga: Promedio de goles/eventos de la liga (Global)
        sos_factors: (Opcional) Diccionario con factores de ajuste por rival.
                     Ej: {'local_attack': 1.1, 'visit_defense': 0.9}
    """

    # -------------------------------------------------------------------------
    # 1. VALIDACIÓN DE INTEGRIDAD
    # -------------------------------------------------------------------------
    inputs = [local_af, local_ec, visit_af, visit_ec]

    if not all(isinstance(m, dict) for m in inputs):
        raise ValueError("Error Crítico: Los inputs estadísticos deben ser diccionarios.")

    if not all(m.get("valido", False) for m in inputs):
        raise ValueError("Error Crítico: Uno o más bloques de datos son inválidos o insuficientes.")

    # -------------------------------------------------------------------------
    # 2. EXTRACCIÓN DE DATOS BASE
    # -------------------------------------------------------------------------
    l_local_af = local_af["lambda"]
    l_local_ec = local_ec["lambda"]
    l_visit_af = visit_af["lambda"]
    l_visit_ec = visit_ec["lambda"]
    
    # Extraemos la volatilidad (CV) para el ajuste adaptativo
    # Si no existe CV (versiones viejas), asumimos 0.0 (estable)
    cv_local_af = local_af.get("cv", 0.0)
    cv_visit_af = visit_af.get("cv", 0.0)

    metodo_usado = "LINEAL"
    ajuste_aplicado = []

    # -------------------------------------------------------------------------
    # 3. CÁLCULO BASE (EL MOTOR)
    # -------------------------------------------------------------------------
    
    # Si no hay media de liga, usamos 2.5 goles (o 1.25 por equipo) como ancla teórica
    # para evitar divisiones peligrosas, o hacemos fallback al lineal.
    media_referencia = media_liga if (media_liga is not None and media_liga > 0) else 2.5

    if media_liga is not None and media_liga > 0:
        try:
            # FÓRMULA MULTIPLICATIVA (Dixcon-Coles Standard)
            # Exp_Local = (Fuerza_Ataque_Local * Fuerza_Defensa_Visit) * Media_Global
            # Donde Fuerza = Lambda_Equipo / Media_Global_Local_o_Visit
            # Simplificación Algebraica: (Local_AF * Visit_EC) / Media_Liga
            
            raw_lambda_local = (l_local_af * l_visit_ec) / media_liga
            raw_lambda_visit = (l_visit_af * l_local_ec) / media_liga
            
            metodo_usado = "MULTIPLICATIVO"
        except ZeroDivisionError:
            # Fallback matemático extremo
            raw_lambda_local = (l_local_af + l_visit_ec) / 2
            raw_lambda_visit = (l_visit_af + l_local_ec) / 2
            metodo_usado = "LINEAL (Error Div0)"
    else:
        # FÓRMULA LINEAL (Promedio Simple)
        raw_lambda_local = (l_local_af + l_visit_ec) / 2
        raw_lambda_visit = (l_visit_af + l_local_ec) / 2
        metodo_usado = "LINEAL (Sin Media)"

    # -------------------------------------------------------------------------
    # 4. CAPA CONTEXTUAL: STRENGTH OF SCHEDULE (SoS)
    # -------------------------------------------------------------------------
    # Esta capa premia o castiga según la calidad de los rivales pasados.
    # Si no se proveen factores, se asume neutralidad (1.0).
    
    sos_l_att = 1.0
    sos_v_att = 1.0
    
    if sos_factors:
        sos_l_att = sos_factors.get("local_attack", 1.0)
        sos_v_att = sos_factors.get("visit_attack", 1.0)
        # Podríamos añadir factores defensivos aquí también
        
        if sos_l_att != 1.0 or sos_v_att != 1.0:
            ajuste_aplicado.append("SoS")

    # Aplicamos el ajuste SoS
    lambda_local_sos = raw_lambda_local * sos_l_att
    lambda_visit_sos = raw_lambda_visit * sos_v_att

    # -------------------------------------------------------------------------
    # 5. CAPA ADAPTATIVA: REGRESIÓN POR VOLATILIDAD
    # -------------------------------------------------------------------------
    # Si un equipo es muy inestable (CV alto), su promedio es poco confiable.
    # Lo "regresamos" hacia la media de la liga para reducir el riesgo de sobreestimación.
    
    def aplicar_dampening(valor, cv, media_ref):
        # Umbral de CV donde empezamos a desconfiar
        CV_THRESHOLD = 0.50
        if cv <= CV_THRESHOLD:
            return valor, False
        
        # Factor de duda: qué tanto nos movemos hacia la media
        # Si CV es 1.0, dampening es 0.25 (movemos 25% el valor hacia la media)
        dampening = min((cv - CV_THRESHOLD) * 0.5, 0.30) 
        
        # Fórmula de Regresión: (1 - w) * Valor + w * Media
        valor_ajustado = (valor * (1 - dampening)) + ((media_ref / 2) * dampening)
        return valor_ajustado, True

    final_lambda_local, reg_l = aplicar_dampening(lambda_local_sos, cv_local_af, media_referencia)
    final_lambda_visit, reg_v = aplicar_dampening(lambda_visit_sos, cv_visit_af, media_referencia)

    if reg_l or reg_v:
        ajuste_aplicado.append("VOLATILIDAD")

    # Etiqueta final del método para el frontend
    if ajuste_aplicado:
        metodo_usado += f" + [{'|'.join(ajuste_aplicado)}]"

    # -------------------------------------------------------------------------
    # 6. RETORNO FINAL
    # -------------------------------------------------------------------------
    # Tamaño de muestra efectivo (el eslabón más débil)
    n = min(local_af["n"], local_ec["n"], visit_af["n"], visit_ec["n"])
    
    # -------------------------------------------------------------------------
    # [MEJORA ADITIVA V2 - CALIBRADA] EFICIENCIA DEFENSIVA CON SUAVIZADO
    # -------------------------------------------------------------------------
    # Objetivo: Ajustar la predicción según la debilidad defensiva del rival,
    # pero aplicando "frenos" (dampening) según el tipo de métrica para evitar
    # explosiones en métricas de alto volumen (como Remates).

    if media_liga and media_liga > 0:
        # 1. DETECCIÓN AUTOMÁTICA DE SUAVIZADO (DAMPENING)
        # Basado en la frecuencia del evento (Media Liga)
        if media_liga < 4.0:
            # BAJA FRECUENCIA (Goles, Tarjetas) -> Mantenemos alta fidelidad (0.65)
            # Queremos que la debilidad defensiva impacte fuerte aquí.
            dampening = 0.65
        elif media_liga < 12.0:
            # MEDIA FRECUENCIA (Córners, Tiros a Puerta) -> Suavizado medio (0.35)
            # Evitamos que un equipo malo conceda 5 córners extra de golpe.
            dampening = 0.35
        else:
            # ALTA FRECUENCIA (Remates, Faltas) -> Suavizado agresivo (0.20)
            # Un 10% de debilidad en remates (25 total) son 2.5 remates. Es mucho.
            # Lo bajamos al 20% de impacto real.
            dampening = 0.20

        # 2. CÁLCULO DE FACTORES (USANDO DATOS 'EN CONTRA' EC)
        # Visitante: Su debilidad es cuánto permite (EC) vs la media
        ec_visit_avg = visit_ec.get('media', media_liga)
        raw_factor_visit = ec_visit_avg / (media_liga / 2)
        
        # Local: Su debilidad es cuánto permite (EC) vs la media
        ec_local_avg = local_ec.get('media', media_liga)
        raw_factor_local = ec_local_avg / (media_liga / 2)

        # 3. APLICACIÓN DEL SUAVIZADO (FÓRMULA DE AMORTIGUACIÓN)
        # Factor_Final = (Factor_Crudo - 1) * Resistencia + 1
        adj_factor_visit = (raw_factor_visit - 1) * dampening + 1
        adj_factor_local = (raw_factor_local - 1) * dampening + 1
        
        # Límites de seguridad (Clamp) para evitar locuras matemáticas
        adj_factor_visit = max(0.8, min(adj_factor_visit, 1.4))
        adj_factor_local = max(0.8, min(adj_factor_local, 1.4))

        # 4. APLICACIÓN FINAL ADITIVA
        final_lambda_local = final_lambda_local * adj_factor_visit
        final_lambda_visit = final_lambda_visit * adj_factor_local
        
        # Log para auditoría visual en frontend
        tag_damp = "H" if dampening == 0.20 else ("M" if dampening == 0.35 else "L")
        ajuste_aplicado.append(f"DEF_ADJ[{tag_damp}](v{round(adj_factor_visit,2)}|l{round(adj_factor_local,2)})")
    
    # -------------------------------------------------------------------------
    # FIN BLOQUE ADITIVO V2
    # -------------------------------------------------------------------------

    

    return {
        "lambda_local": round(final_lambda_local, 4),
        "lambda_visitante": round(final_lambda_visit, 4),
        "lambda_total": round(final_lambda_local + final_lambda_visit, 4),
        "n": n,
        "metodo": metodo_usado,
        "raw_local": round(raw_lambda_local, 4),    # Para depuración
        "raw_visit": round(raw_lambda_visit, 4)     # Para depuración
    }
