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
    # [MEJORA ADITIVA V5 - CALIBRACIÓN GRANULAR BUNDESLIGA] EFICIENCIA DEFENSIVA
    # -------------------------------------------------------------------------
    # CALIBRACIÓN REALIZADA EL: 2026-01-16 (Base: 150 Partidos 24/25)
    # Lógica: Asignamos un dampening basado en la correlación estadística (R²) real.
    
    # 1. DICCIONARIO DE CONFIGURACIÓN (El Cerebro Calibrado)
    # Valores derivados de Regresión Lineal (Offline V10):
    # - Goles: 0.50 (Varianza alta, defensa influye mucho en evitar fallo)
    # - Remates a Puerta (SoT): 0.30 (R² detectado de 0.29 -> Redondeado a 0.30)
    # - Remates (Shots): 0.24 (R² detectado de 0.239 -> Exacto 0.24)
    # - Córners: 0.15 (Estándar conservador)
    dampening_config = {
        "Goles": 0.50,              
        "Remates a Puerta": 0.30,   # SUBIDA: La defensa real frena más de lo que pensábamos.
        "Remates (Shots)": 0.24,    # SUBIDA: De 0.15 a 0.24. Ajuste crítico por volumen.
        "Córners": 0.15,            
        "Tarjetas Amarillas": 0.05, # Desacoplado
        "Faltas": 0.05,             # Desacoplado
        "default": 0.15             
    }

    if media_liga and media_liga > 0:
        # LÓGICA HÍBRIDA MEJORADA CON NUEVOS UMBRALES:
        target_dampening = 0.15 # Default
        clamp_max = 1.25

        # Inferencia por magnitud de la media 
        if media_liga < 0.5: # Rojas
            target_dampening = 0.05 
        elif media_liga < 4.0: # Goles (o Tarjetas bajas)
            # Goles sigue mandando con fuerza defensiva
            target_dampening = 0.50
            clamp_max = 1.35
            
            # PARCHE DE SEGURIDAD PARA TARJETAS
            if 3.5 <= media_liga <= 6.0: 
                target_dampening = 0.05 # Tarjetas son aleatorias, poco dampening
                clamp_max = 1.15
        
        elif media_liga < 12.0: # Córners, Tiros a Puerta (~8-10)
            # Aquí caen los SoT (Tiros a Puerta)
            # Si es SoT (media ~8-10), aplicamos el nuevo 0.30
            if media_liga > 7.0: 
                target_dampening = 0.30 # Calibración SoT
            else:
                target_dampening = 0.15 # Córners
                
        else: # Faltas (~22), Remates Totales (~26)
            # Diferenciamos por magnitud
            if media_liga > 20.0: 
                # Zona de Remates Totales (Shots)
                # Aplicamos el R² calculado de 0.24
                target_dampening = 0.24 
            else:
                # Zona intermedia (Faltas o Tiros bajos)
                target_dampening = 0.10

        # 2. CÁLCULO DE FACTORES
        ec_visit_avg = visit_ec.get('media', media_liga)
        raw_factor_visit = ec_visit_avg / (media_liga / 2)
        
        ec_local_avg = local_ec.get('media', media_liga)
        raw_factor_local = ec_local_avg / (media_liga / 2)

        # 3. APLICACIÓN
        adj_factor_visit = (raw_factor_visit - 1) * target_dampening + 1
        adj_factor_local = (raw_factor_local - 1) * target_dampening + 1
        
        # Clamps (Ligeramente ajustados para permitir la nueva varianza)
        adj_factor_visit = max(0.80, min(adj_factor_visit, clamp_max))
        adj_factor_local = max(0.80, min(adj_factor_local, clamp_max))

        final_lambda_local = final_lambda_local * adj_factor_visit
        final_lambda_visit = final_lambda_visit * adj_factor_local
        
        tag_damp = f"D{int(target_dampening*100)}"
        ajuste_aplicado.append(f"DEF[{tag_damp}](v{round(adj_factor_visit,2)}|l{round(adj_factor_local,2)})")

    # -------------------------------------------------------------------------
    # FIN BLOQUE ADITIVO V5
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
