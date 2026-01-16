print("🔵 [PASO 1] Iniciando script V7.3...")

import sys
import os
import traceback 

try:
    import pandas as pd
    import numpy as np
    import time
    import warnings
except Exception as e:
    print(f"❌ Error libs: {e}")
    sys.exit()

warnings.filterwarnings("ignore")

BASE_DIR = r"C:\Users\Luis_Javier\Documents\estadisticas\csv_backtest"
FILE_CURRENT = "E0-2.csv"
EVENTO_TEST = "cards" 
MERCADO_TEST = "Total Partido"
ODDS_TEST = 1.90              
BANKROLL_INICIAL = 1000.0
MIN_PARTIDOS_DATA = 4

# IMPORTACIONES
try:
    from config import Config
    from model import calcular_valor_poisson
    from data_engine.etl_engine import (
        obtener_datos_equipo, 
        calcular_parametros_liga, 
        calcular_factor_arbitro, 
        EVENT_TO_METRIC_MAP, 
        load_data_cached,
        CSV_COLUMNS_MAP # Importamos esto para debug
    )
    from data_engine.stats_engine import calcular_metricas_desde_datos
    from data_engine.lambda_engine import construir_lambdas
    print("✅ Motores OK.")
except Exception as e:
    print(f"❌ Error Motores: {e}")
    sys.exit()

Config.DEFAULT_Z = 0.5 

def ejecutar_backtest():
    print("\n" + "="*60)
    print(f"🔬 BACKTEST V7.3 - DEBUG DE DATOS")
    print("="*60)

    path_curr = os.path.join(BASE_DIR, FILE_CURRENT)
    if not os.path.exists(path_curr): return

    df_curr = pd.read_csv(path_curr)
    df_curr['Date'] = pd.to_datetime(df_curr['Date'], dayfirst=True, errors='coerce')
    df_curr = df_curr.dropna(subset=['Date']).sort_values('Date')
    
    print(f"📂 Archivo: {len(df_curr)} partidos.")
    
    # VERIFICACIÓN CLAVE: ¿Qué columnas estamos leyendo?
    metric_name = EVENT_TO_METRIC_MAP.get(EVENTO_TEST)
    cols_map = CSV_COLUMNS_MAP.get(metric_name)
    print(f"🔑 Evento: '{EVENTO_TEST}' -> Métrica: '{metric_name}'")
    print(f"🔑 Columnas esperadas: {cols_map}")

    if not cols_map:
        print("❌ ERROR: No hay mapeo de columnas para este evento.")
        return

    # Acumuladores
    bank_base = BANKROLL_INICIAL
    bank_smart = BANKROLL_INICIAL
    bets_base = 0
    wins_base = 0
    bets_smart = 0
    wins_smart = 0
    divergencias = 0
    arbitros_activos = 0

    print("🚀 Iniciando bucle...")

    for idx, row in df_curr.iterrows():
        try:
            fecha = row['Date']
            home, away = row['HomeTeam'], row['AwayTeam']
            referee = row.get('Referee', None)
            
            df_conocido = df_curr[df_curr['Date'] < fecha]
            matches_h = len(df_conocido[(df_conocido['HomeTeam']==home) | (df_conocido['AwayTeam']==home)])
            
            if matches_h < MIN_PARTIDOS_DATA: continue

            # 1. ETL
            # Aquí forzamos a leer "Tarjetas Amarillas" que es lo que está mapeado
            mean_team, rho, def_map, league_base, _ = calcular_parametros_liga(df_conocido, metric_name)
            
            raw_h, _, sos_h = obtener_datos_equipo(df_conocido, home, metric_name, "GLOBAL", def_map, league_base, None)
            raw_a, _, sos_a = obtener_datos_equipo(df_conocido, away, metric_name, "GLOBAL", def_map, league_base, None)
            
            # DEBUG CRÍTICO: Si los arrays están vacíos, sabemos por qué falla
            if len(raw_h) == 0 or len(raw_a) == 0:
                # print(f"⚠️ Arrays vacíos para {home} vs {away}. (Match History: {matches_h})")
                continue

            stats_h = calcular_metricas_desde_datos(raw_h, EVENTO_TEST)
            stats_a = calcular_metricas_desde_datos(raw_a, EVENTO_TEST)

            if not (stats_h["valido"] and stats_a["valido"]): 
                # print(f"⚠️ Stats inválidos para {home} vs {away}")
                continue

            # 2. LAMBDAS
            lambdas = construir_lambdas(stats_h, stats_h, stats_a, stats_a, mean_team, {'local_attack': sos_h, 'visit_attack': sos_a})
            l_h_base, l_a_base = lambdas["lambda_local"], lambdas["lambda_visitante"]

            # 3. JUSTICIA
            fact_ref = calcular_factor_arbitro(df_conocido, referee)
            k_ref = fact_ref.get('K_Cards', 1.0) # Usamos factor Cards
            
            l_h_smart = l_h_base * k_ref
            l_a_smart = l_a_base * k_ref
            
            if abs(k_ref - 1.0) > 0.05:
                arbitros_activos += 1
                # print(f"   👮 Juez {referee}: x{k_ref:.2f}")

            # 4. CÁLCULO
            linea = round(l_h_base + l_a_base) - 0.5
            if linea < 2.5: linea = 2.5
            
            # Usamos una función lambda ficticia para el cálculo rápido
            # Si quieres el detalle completo, descomenta las líneas de abajo, pero para test rápido:
            
            real = row['HY'] + row['AY'] # Solo Amarillas porque es lo que estamos prediciendo
            # (Si quisieras Amarillas+Rojas tendrías que sumar HR+AR también, pero el modelo predice lo que lee)
            
            win = real > linea
            
            # Simulación simple de Poisson (sin llamar a todo el modelo pesado para ir rápido)
            # Asumimos que si EV > 0 apostamos.
            
            # ... Para ser precisos, llamamos al modelo real:
            res_base = calcular_valor_poisson({"Local AF": l_h_base, "Visitante AF": l_a_base}, lambdas["n"], "Over", linea, ODDS_TEST, MERCADO_TEST, EVENTO_TEST, rho, bank_base, bank_base*0.01, Config.MODE_LAB, {"Local": stats_h["cv"], "Visitante": stats_a["cv"]})
            res_smart = calcular_valor_poisson({"Local AF": l_h_smart, "Visitante AF": l_a_smart}, lambdas["n"], "Over", linea, ODDS_TEST, MERCADO_TEST, EVENTO_TEST, rho, bank_smart, bank_smart*0.01, Config.MODE_LAB, {"Local": stats_h["cv"], "Visitante": stats_a["cv"]})

            if res_base['Aceptado']:
                bets_base += 1
                bank_base += (bank_base*0.01*(ODDS_TEST-1)) if win else -(bank_base*0.01)
            
            if res_smart['Aceptado']:
                bets_smart += 1
                bank_smart += (bank_smart*0.01*(ODDS_TEST-1)) if win else -(bank_smart*0.01)
                
            if res_base['Aceptado'] != res_smart['Aceptado']: divergencias += 1

        except Exception as e:
            print(f"Error Loop: {e}")
            continue

    # --- RESULTADOS ---
    print("\n" + "="*60)
    print("📊 REPORTE DE INTELIGENCIA (V7.3)")
    print("="*60)
    print(f"Intervenciones Juez: {arbitros_activos}")
    print(f"Divergencias: {divergencias}")
    
    print("\n🔵 MODELO BASE")
    if bets_base > 0: print(f"Apuestas: {bets_base} | ROI: {(bank_base-1000)/1000:.2%}")
    else: print("Sin apuestas.")

    print("\n🔥 MODELO JUSTICIA")
    if bets_smart > 0: print(f"Apuestas: {bets_smart} | ROI: {(bank_smart-1000)/1000:.2%}")
    else: print("Sin apuestas.")

    impacto = ((bank_smart - bank_base)/1000)*100
    print(f"\n🏆 DIFERENCIA DE ROI: {impacto:+.2f}%")

if __name__ == "__main__":
    ejecutar_backtest()