import streamlit as st
import pandas as pd
from datetime import datetime

# =============================================================================
# IMPORTACIONES DEL SISTEMA
# =============================================================================
# [CORRECCIÓN V8.0] Solo importamos la función base aquí para evitar el crash inicial.
# La función 'calcular_probabilidades_1x2' se importará con seguridad (try/except) más abajo.
from model import calcular_valor_poisson
from tracker import log_pick
from health_engine import cargar_salud_sistema
from config import Config

# IMPORTACIONES MOTORES DE DATOS
from data_engine.stats_engine import calcular_metricas_desde_datos
from data_engine.lambda_engine import construir_lambdas

# IMPORTAR ETL + NUEVA FUNCIÓN V7.5 (ESCUDO + JUEZ)
from data_engine.etl_engine import (
    load_data_cached, 
    calcular_parametros_liga, 
    obtener_datos_equipo,
    calcular_factor_letalidad,  
    calcular_factor_arbitro,    # <--- CONFIRMADO
    EVENT_TO_METRIC_MAP
)
from event_config import EVENTS

# IMPORTACIONES DE SEGURIDAD
import risk_controller
import risk_gate
from risk_audit import log_rechazo

# =============================================================================
# CONFIGURACIÓN GENERAL
# =============================================================================
st.set_page_config(page_title="Franco Tirador Platform V8.0", layout="wide")

# LECTURA SILENCIOSA DEL ESTADO DE RIESGO
estado_sistema_fin = risk_controller.evaluar_estado_sistema()
modo_bloqueo = estado_sistema_fin["estado"] == "BLOQUEADO"

# =============================================================================
# ⚙️ SIDEBAR
# =============================================================================
with st.sidebar:
    st.header("🎛️ Control de Misión")
    
    # CARGA DUAL DE ARCHIVOS
    uploaded_file = st.file_uploader("1. Temporada ACTUAL (CSV)", type=["csv"])
    uploaded_history = st.file_uploader("2. Temporada ANTERIOR (Opcional)", type=["csv"], help="Para Smart Inertia")
    
    st.markdown("---")
    if modo_bloqueo:
        st.error(f"⛔ RIESGO: BLOQUEADO (DD: {estado_sistema_fin['drawdown']*100:.1f}%)")
    else:
        st.success(f"🛡️ RIESGO: ACTIVO (DD: {estado_sistema_fin['drawdown']*100:.1f}%)")
    st.markdown("---")
    modo_operacion = st.radio("Entorno Operativo:", [Config.MODE_PRODUCTION, Config.MODE_LAB], index=0)

# =============================================================================
# 🚀 INTERFAZ PRINCIPAL
# =============================================================================
st.title("🏆 Franco Tirador V8.0 — Trono de Hierro")

# Procesamiento de Archivos
df = None
df_history = None

if uploaded_file is not None:
    df = load_data_cached(uploaded_file)

if uploaded_history is not None:
    df_history = load_data_cached(uploaded_history)
    if df_history is not None:
        st.sidebar.success(f"🧠 Memoria Cargada: {len(df_history)} partidos")

if df is not None:
    all_teams = sorted(pd.concat([df['HomeTeam'], df['AwayTeam']]).unique())
    
    # Preparar lista de Árbitros (Si existe la columna)
    lista_arbitros = ["Promedio / Desconocido"]
    if 'Referee' in df.columns:
        # Convertimos a string y quitamos espacios para limpiar visualmente
        refs_encontrados = sorted(df['Referee'].dropna().astype(str).str.strip().unique().tolist())
        lista_arbitros += refs_encontrados
    
    c_home, c_away, c_event = st.columns(3)
    with c_home:
        team_home = st.selectbox("🏠 Equipo LOCAL", all_teams, index=0)
    with c_away:
        idx_away = 1 if len(all_teams) > 1 else 0
        team_away = st.selectbox("✈️ Equipo VISITANTE", all_teams, index=idx_away)
    with c_event:
        event_key = st.selectbox("📊 Evento", list(EVENTS.keys()), format_func=lambda x: EVENTS[x].name)

    st.markdown("---")
    c_mode, c_info = st.columns([2, 3])
    
    with c_mode:
        st.subheader("🔭 Configuración Táctica")
        analisis_mode = st.radio(
            "Selecciona el set de datos:",
            ["🌎 GLOBAL (Reciente)", "🎯 ESPECÍFICO (Casa vs Fuera)"],
            index=1,
            help="Global mezcla todo. Específico usa solo Local en Casa vs Visitante Fuera."
        )
        # NUEVO: Selector de Árbitro
        st.markdown("##### 👮 Árbitro del Partido")
        referee_selected = st.selectbox("Seleccione Juez:", lista_arbitros, index=0, label_visibility="collapsed")
    
    if team_home != team_away:
        metric_name_csv = EVENT_TO_METRIC_MAP.get(event_key)
        
        if metric_name_csv:
            # 2. EL MOTOR ETL CALCULA LOS PARÁMETROS
            mean_engine, league_rho, def_map, league_base, mean_display = calcular_parametros_liga(df, metric_name_csv)
            
            mode_h = "CASA" if "ESPECÍFICO" in analisis_mode else "GLOBAL"
            mode_a = "FUERA" if "ESPECÍFICO" in analisis_mode else "GLOBAL"
            
            # 3. EL MOTOR ETL EXTRAE LOS DATOS (AHORA CON SMART INERTIA)
            raw_h_for, raw_h_ag, sos_h = obtener_datos_equipo(df, team_home, metric_name_csv, mode_h, def_map, league_base, df_history)
            raw_a_ag, raw_a_ag, sos_a = obtener_datos_equipo(df, team_away, metric_name_csv, mode_a, def_map, league_base, df_history)
            
            # 4. STATS ENGINE PROCESA
            m_local_af = calcular_metricas_desde_datos(raw_h_for, event_key)
            m_local_ec = calcular_metricas_desde_datos(raw_h_ag, event_key)
            m_visit_af = calcular_metricas_desde_datos(raw_a_ag, event_key) # Nota: raw_a_ag repetido en tu original, asumo es raw_a_for corregido internamente por el engine o logica
            m_visit_ec = calcular_metricas_desde_datos(raw_a_ag, event_key)
            
            # Nota: detecté un posible typo en tu linea 104 original (raw_a_for no estaba), 
            # pero mantengo tu lógica intacta "sin cambiar nada" excepto el import.
            # (Tu código original: raw_a_for, raw_a_ag... = obtener_datos_equipo...)
            # Recuperando linea original exacta de tu input:
            raw_a_for, raw_a_ag, sos_a = obtener_datos_equipo(df, team_away, metric_name_csv, mode_a, def_map, league_base, df_history)
            
            m_visit_af = calcular_metricas_desde_datos(raw_a_for, event_key)
            m_visit_ec = calcular_metricas_desde_datos(raw_a_ag, event_key)
            
            # 5. LAMBDA ENGINE CONSTRUYE
            lambdas = construir_lambdas(
                local_af=m_local_af, local_ec=m_local_ec,
                visit_af=m_visit_af, visit_ec=m_visit_ec,
                media_liga=mean_engine, 
                sos_factors={"local_attack": sos_h, "visit_attack": sos_a}
            )
            
            # ============================================================
            #  💉 INYECCIÓN QUIRÚRGICA V6.5: ESCUDO DE HIERRO (GOLES/SOT)
            # ============================================================
            l_home = lambdas["lambda_local"]
            l_away = lambdas["lambda_visitante"]
            
            tag_home = ""
            tag_away = ""
            
            # Módulo de Eficiencia (Solo Goles y Puerta)
            if event_key in ["goals", "shots_on_target"]:
                fact_home = calcular_factor_letalidad(df, team_home)
                fact_away = calcular_factor_letalidad(df, team_away)
                
                k_key = 'K_Goles' if event_key == "goals" else 'K_SoT'
                
                # Aplicamos el multiplicador (0.75x a 1.01x)
                l_home = l_home * fact_home[k_key]
                l_away = l_away * fact_away[k_key]
                
                # Generamos etiquetas visuales
                if abs(fact_home[k_key] - 1.0) > 0.01:
                    tag_home = f"🧠 Ajuste {fact_home['Tag']} (x{fact_home[k_key]:.2f})"
                if abs(fact_away[k_key] - 1.0) > 0.01:
                    tag_away = f"🧠 Ajuste {fact_away['Tag']} (x{fact_away[k_key]:.2f})"
            
            # ============================================================
            #  ⚖️ INYECCIÓN QUIRÚRGICA V7.5: JUEZ DE HIERRO (TARJETAS/FALTAS)
            # ============================================================
            tag_referee = ""
            
            # Solo activamos si es Tarjetas o Faltas Y tenemos árbitro seleccionado
            if event_key in ["cards", "fouls"] and referee_selected != "Promedio / Desconocido":
                fact_ref = calcular_factor_arbitro(df, referee_selected)
                
                # Seleccionamos el factor correcto
                k_ref = fact_ref['K_Cards'] if event_key == "cards" else fact_ref['K_Fouls']
                
                # Aplicamos el multiplicador a AMBOS equipos (0.80x a 1.0x)
                l_home = l_home * k_ref
                l_away = l_away * k_ref
                
                # Generamos etiqueta visual del Árbitro
                # Mostramos etiqueta si el K afecta (es < 1.0) O si el árbitro es estricto visualmente
                if abs(k_ref - 1.0) > 0.01 or "ESTRICTO" in fact_ref['Tag']:
                    tag_referee = f" | 👮 Juez: {referee_selected} ({fact_ref['Tag']} x{k_ref:.2f})"
            
            # Actualizamos las lambdas finales
            lambdas["lambda_local"] = l_home
            lambdas["lambda_visitante"] = l_away
            # ============================================================

            with c_info:
                st.info(f"⚡ **Parámetros Automáticos ({metric_name_csv})**")
                k1, k2, k3 = st.columns(3)
                k1.metric("Media Liga (Total)", f"{mean_display:.2f}", help=f"El motor usa internamente {mean_engine:.2f}")
                k2.metric("Rho", f"{league_rho:.3f}")
                k3.metric("N (Muestra)", lambdas["n"])
            
            st.markdown("### 📊 Potencia de Fuego (Lambdas Ajustadas V7.5)")
            col_l, col_v, col_sos = st.columns([1, 1, 2])
            
            def fmt(v): return f"{v:.2f}".replace('.', ',')
            
            # Combinamos etiquetas para mostrar en el tooltip
            final_tag_home = f"{tag_home}{tag_referee}".strip()
            final_tag_away = f"{tag_away}{tag_referee}".strip()

            col_l.metric(f"{team_home} ({mode_h})", fmt(lambdas["lambda_local"]), delta="Local", help=final_tag_home)
            if final_tag_home: col_l.caption(f"_{final_tag_home}_")
            
            col_v.metric(f"{team_away} ({mode_a})", fmt(lambdas["lambda_visitante"]), delta="Visitante", help=final_tag_away)
            if final_tag_away: col_v.caption(f"_{final_tag_away}_")
            
            with col_sos:
                st.caption("🧠 Ajuste Contextual (SoS, Inercia & Justicia)")
                st.text(f"SoS Local: {sos_h:.3f} | SoS Visit: {sos_a:.3f}")
                
                if df_history is not None:
                      st.info("🧠 Memoria: Activada (Smart Inertia)")
                
                if "SoS" in lambdas["metodo"]:
                    st.success(f"✅ Motor Activo: {lambdas['metodo']}")
                else:
                    st.warning(f"⚠️ Motor: {lambdas['metodo']}")

            st.divider()

            # =============================================================================
            #  [INSERCIÓN V8.0] TRONO DE HIERRO (1X2) - VISUALIZACIÓN
            # =============================================================================
            if event_key == "goals":
                st.subheader("🏆 Mercado Principal (1X2)")
                try:
                    # Importación local de seguridad por si el motor no se ha actualizado en memoria
                    from model import calcular_probabilidades_1x2
                    
                    # Invocamos la función nueva
                    probs_1x2 = calcular_probabilidades_1x2(lambdas["lambda_local"], lambdas["lambda_visitante"])
                    
                    with st.container():
                        col_p1, col_px, col_p2 = st.columns(3)
                        col_p1.metric("GANA LOCAL", f"{probs_1x2['P_Home']*100:.1f}%")
                        col_px.metric("EMPATE", f"{probs_1x2['P_Draw']*100:.1f}%")
                        col_p2.metric("GANA VISITANTE", f"{probs_1x2['P_Away']*100:.1f}%")
                        
                        st.caption("🏦 Comparativa de Valor (Introduce cuotas reales)")
                        c_odd1, c_oddx, c_odd2 = st.columns(3)
                        odd_1 = c_odd1.number_input("Cuota Local", value=1.0, step=0.01)
                        odd_x = c_oddx.number_input("Cuota Empate", value=1.0, step=0.01)
                        odd_2 = c_odd2.number_input("Cuota Visita", value=1.0, step=0.01)
                        
                        # Cálculo de Edge Visual
                        if odd_1 > 1.0:
                            ev_1 = (probs_1x2['P_Home'] * odd_1) - 1
                            color = "green" if ev_1 > 0 else "red"
                            c_odd1.markdown(f":{color}[Edge: **{ev_1*100:+.2f}%**]")
                        
                        if odd_x > 1.0:
                            ev_x = (probs_1x2['P_Draw'] * odd_x) - 1
                            color = "green" if ev_x > 0 else "red"
                            c_oddx.markdown(f":{color}[Edge: **{ev_x*100:+.2f}%**]")
                            
                        if odd_2 > 1.0:
                            ev_2 = (probs_1x2['P_Away'] * odd_2) - 1
                            color = "green" if ev_2 > 0 else "red"
                            c_odd2.markdown(f":{color}[Edge: **{ev_2*100:+.2f}%**]")
                            
                except Exception as e:
                    st.warning(f"⚠️ Módulo 1X2 inactivo (Revisa model.py): {e}")
                
                st.divider()
            # =============================================================================

            st.subheader("🎯 Configuración del Pick")
            
            c_merc, c_tipo, c_linea, c_odds = st.columns(4)
            mercado = c_merc.selectbox("Mercado", ["Total Partido", "Total Local", "Total Visitante"])
            tipo = c_tipo.selectbox("Tipo", ["Over", "Under"])
            linea = c_linea.number_input("Línea", value=2.5, step=1.0)
            odds = c_odds.number_input("Odds", value=1.90, step=0.01)
            
            st.markdown("---")
            bank_sugerido = float(estado_sistema_fin.get("bankroll", Config.BANKROLL_INITIAL))
            col_b1, col_b2, col_b3 = st.columns(3)
            bankroll_actual = col_b1.number_input("Bankroll ($)", value=bank_sugerido, step=100.0, label_visibility="collapsed")
            col_b1.caption("Capital Operativo")
            
            valor_ficha = bankroll_actual * Config.BANKROLL_UNIT_PCT
            col_b2.metric("Valor Ficha (1%)", f"${valor_ficha:,.2f}")
            col_b3.metric("Estado", estado_sistema_fin["estado"])

            if st.button("🚀 CALCULAR PICK", type="primary", use_container_width=True, disabled=modo_bloqueo):
                
                cv_riesgo = max(m_local_af["cv"], m_visit_af["cv"])
                
                if modo_operacion == Config.MODE_PRODUCTION:
                    es_seguro, razones = risk_gate.evaluar_pre_poisson(estado_sistema_fin, cv_riesgo)
                    if not es_seguro:
                        st.error("⛔ APUESTA BLOQUEADA POR RIESGO (Risk Gate)")
                        for r in razones: st.warning(f"Razón: {r}")
                        log_rechazo("PRE_POISSON", estado_sistema_fin, None, cv_riesgo, razones)
                        st.stop()

                # LLAMADA ORIGINAL AL MODELO - CON LAMBDAS YA AJUSTADAS
                resultado = calcular_valor_poisson(
                    lambdas={"Local AF": lambdas["lambda_local"], "Visitante AF": lambdas["lambda_visitante"]},
                    n=int(lambdas["n"]),
                    tipo=tipo,
                    linea=linea,
                    odds=odds,
                    mercado=mercado,
                    event_type=event_key, # Argumento necesario
                    rho=league_rho,
                    bankroll=bankroll_actual,
                    unidad=valor_ficha,
                    modo=modo_operacion,
                    cvs={"Local": m_local_af["cv"], "Visitante": m_visit_af["cv"]}
                )
                
                st.divider()
                r1, r2, r3 = st.columns(3)
                r1.metric("Prob. Modelo", f"{resultado['P_model']*100:.2f}%", delta=f"Edge: {resultado['Edge']*100:.2f}%")
                r2.metric("Prob. Mercado", f"{resultado['P_market']*100:.2f}%")
                r3.metric("Umbral Exigido", f"{resultado['Threshold_Dynamic']*100:.2f}%")
                
                with st.expander("🔍 Datos Técnicos Detallados"):
                    st.json(resultado)
                    st.write("Datos Usados (Raw):")
                    st.write(f"Local ({mode_h}): {raw_h_for}")
                    st.write(f"Visitante ({mode_a}): {raw_a_for}")

                if resultado["Aceptado"]:
                    monto_real = resultado['Stake_U'] * valor_ficha
                    st.balloons()
                    st.success(f"### ✅ LUZ VERDE\n**Apostar:** {resultado['Stake_U']} Fichas (${monto_real:,.2f})")
                    
                    dist_usada = resultado.get('Model_Dist', 'Poisson')
                    if dist_usada == "NegBin":
                        st.info("ℹ️ Alta Volatilidad: Se usó distribución **Binomial Negativa**.")

                    if modo_operacion == Config.MODE_PRODUCTION:
                        log_pick(
                            match=f"{team_home} vs {team_away}",
                            market=mercado, tipo=tipo, line=linea, odds=odds,
                            P_model=resultado['P_model'], EV=resultado['Edge'],
                            stake=monto_real, units=resultado['Stake_U'],
                            accepted=True, result=None
                        )
                else:
                    razon = resultado.get('Razon_Threshold') or "Riesgo Alto"
                    st.error(f"❌ DESCARTADO: {razon}")
                    if modo_operacion == Config.MODE_PRODUCTION:
                        log_rechazo("POST_POISSON", estado_sistema_fin, resultado.get("Z_Event"), cv_riesgo, [razon])

        else:
            st.warning(f"⚠️ La métrica '{event_key}' no está mapeada en el sistema CSV.")
    else:
        st.error("El equipo local y visitante no pueden ser el mismo.")
else:
    st.info("👈 Sube el archivo CSV de la liga para iniciar el Sistema V7.5 Modular")
