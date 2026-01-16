import pandas as pd
import numpy as np
import streamlit as st

# =============================================================================
# MAPEOS Y CONFIGURACIÓN (Estructura Estable)
# =============================================================================
EVENT_TO_METRIC_MAP = {
    "goals": "Goles",
    "corners": "Córners",
    "cards": "Tarjetas Amarillas",
    "shots": "Remates (Shots)",
    "shots_on_target": "Remates a Puerta",
    "fouls": "Faltas"
}

CSV_COLUMNS_MAP = {
    "Goles": {"home": "FTHG", "away": "FTAG"},
    "Remates (Shots)": {"home": "HS", "away": "AS"},
    "Remates a Puerta": {"home": "HST", "away": "AST"},
    "Córners": {"home": "HC", "away": "AC"},
    "Faltas": {"home": "HF", "away": "AF"},
    "Tarjetas Amarillas": {"home": "HY", "away": "AY"},
    "Tarjetas Rojas": {"home": "HR", "away": "AR"}
}

# Configuración Smart Inertia
STRUCTURAL_CHANGE_THRESHOLD = 0.25 
HISTORY_LOOKBACK = 10 

# =============================================================================
# FUNCIONES DE CARGA Y CÁLCULO
# =============================================================================

@st.cache_data
def load_data_cached(file):
    """Carga y cachea el CSV para velocidad máxima."""
    try:
        if file is None: return None
        df = pd.read_csv(file)
        # Limpieza de fechas robusta
        df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['Date'])
        return df
    except Exception as e:
        return None

def calcular_parametros_liga(df, metric_key):
    """Calcula Media de Liga y Rho."""
    cols = CSV_COLUMNS_MAP.get(metric_key)
    if not cols: return 1.25, 0.0, {}, 1.0, 2.5 

    col_h = cols["home"]
    col_a = cols["away"]

    total_matches = len(df)
    sum_home = df[col_h].sum()
    sum_away = df[col_a].sum()
    
    if total_matches > 0:
        mean_total_match = (sum_home + sum_away) / total_matches
        mean_per_team = mean_total_match / 2 
        league_avg_conceded = mean_per_team 
    else:
        mean_total_match = 2.5
        mean_per_team = 1.25
        league_avg_conceded = 1.25

    rho = df[col_h].corr(df[col_a])
    if pd.isna(rho): rho = 0.0

    # Mapa de Fuerza Defensiva
    teams = pd.concat([df['HomeTeam'], df['AwayTeam']]).unique()
    def_strength = {}
    
    for t in teams:
        matches_h = df[df['HomeTeam'] == t]
        matches_a = df[df['AwayTeam'] == t]
        played = len(matches_h) + len(matches_a)
        
        if played > 0:
            # Cuánto concedió este equipo (Goles en contra)
            conceded = matches_h[col_a].sum() + matches_a[col_h].sum()
            def_strength[t] = conceded / played
        else:
            def_strength[t] = league_avg_conceded

    return mean_per_team, rho, def_strength, league_avg_conceded, mean_total_match

def _extraer_metricas_equipo(df, team, metric_key, modo_filtro):
    """Auxiliar para extraer listas crudas."""
    cols = CSV_COLUMNS_MAP.get(metric_key)
    if not cols: return [], [], []
    
    col_h = cols["home"]
    col_a = cols["away"]

    team_matches = df[(df['HomeTeam'] == team) | (df['AwayTeam'] == team)].sort_values(by='Date', ascending=False)
    
    data_for = []
    data_against = []
    rivals_list = [] 

    for _, row in team_matches.iterrows():
        is_home = row['HomeTeam'] == team
        rival = row['AwayTeam'] if is_home else row['HomeTeam']
        
        val_for = row[col_h] if is_home else row[col_a]
        val_ag = row[col_a] if is_home else row[col_h]
        
        insertar = False
        if modo_filtro == "GLOBAL": insertar = True
        elif modo_filtro == "CASA" and is_home: insertar = True
        elif modo_filtro == "FUERA" and not is_home: insertar = True
            
        if insertar:
            data_for.append(val_for)
            data_against.append(val_ag)
            rivals_list.append(rival)
            
    return data_for, data_against, rivals_list

def obtener_datos_equipo(df_current, team, metric_key, modo_filtro, def_strength_map, league_avg_base, df_history=None):
    """
    Extrae datos aplicando 'Smart Inertia'.
    """
    # 1. Datos Actuales
    curr_for, curr_ag, curr_rivals = _extraer_metricas_equipo(df_current, team, metric_key, modo_filtro)
    
    # Lógica SoS
    rival_factors = []
    for rival in curr_rivals:
        r_conceded = def_strength_map.get(rival, league_avg_base)
        if r_conceded < 0.1: r_conceded = 0.1 
        if league_avg_base < 0.1: league_avg_base = 0.1
        factor = league_avg_base / r_conceded
        rival_factors.append(factor)
        
    sos_attack = np.mean(rival_factors) if rival_factors else 1.0

    # 2. Smart Inertia
    final_for = curr_for
    final_against = curr_ag
    
    if df_history is not None and len(curr_for) > 0:
        hist_for, hist_ag, _ = _extraer_metricas_equipo(df_history, team, metric_key, modo_filtro)
        if len(hist_for) >= 5:
            mean_curr = np.mean(curr_for)
            mean_hist = np.mean(hist_for)
            delta = abs(mean_curr - mean_hist) / mean_hist if mean_hist > 0 else 1.0 
            if delta <= STRUCTURAL_CHANGE_THRESHOLD:
                n_inject = min(len(hist_for), HISTORY_LOOKBACK)
                final_for = curr_for + hist_for[:n_inject]
                final_against = curr_ag + hist_ag[:n_inject]
                
    if len(final_for) > 40:
        final_for = final_for[:40]
        final_against = final_against[:40]
    
    return final_for, final_against, sos_attack

# =============================================================================
#  MÓDULO DE EFICIENCIA INTELIGENTE (V6.5) - ESCUDO DE HIERRO
# =============================================================================
def calcular_factor_letalidad(df, team_name):
    """
    V6.5: Factor K Defensivo (0.75x - 1.01x).
    """
    try:
        league_goals = df['FTHG'].sum() + df['FTAG'].sum()
        league_shots = df['HS'].sum() + df['AS'].sum()
        league_sot = df['HST'].sum() + df['AST'].sum()
        
        if league_shots == 0: return {'K_Goles': 1.0, 'K_SoT': 1.0, 'Tag': 'NO DATA'}
        
        avg_conv_league = league_goals / league_shots
        avg_prec_league = league_sot / league_shots

        home_games = df[df['HomeTeam'] == team_name]
        away_games = df[df['AwayTeam'] == team_name]
        
        team_goals = home_games['FTHG'].sum() + away_games['FTAG'].sum()
        team_shots = home_games['HS'].sum() + away_games['AS'].sum()
        team_sot = home_games['HST'].sum() + away_games['AST'].sum()
        
        if team_shots == 0: 
            return {'K_Goles': 1.0, 'K_SoT': 1.0, 'Tag': '⚪ NEUTRO'}

        team_conv = team_goals / team_shots
        team_prec = team_sot / team_shots

        k_goals = team_conv / avg_conv_league if avg_conv_league > 0 else 1.0
        k_sot = team_prec / avg_prec_league if avg_prec_league > 0 else 1.0
        
        k_goals = max(0.75, min(k_goals, 1.01))
        k_sot = max(0.75, min(k_sot, 1.01))

        tag = "⚪ ESTÁNDAR"
        conv_pct = team_conv * 100
        
        if conv_pct > 20.0: tag = "🔥 NUCLEAR (Visual)" 
        elif conv_pct > 15.0: tag = "🟢 LETAL (Visual)"
        elif conv_pct < 9.0: tag = "🔵 ESCOPETA (Filtro Activo)"

        return {
            'K_Goles': k_goals,
            'K_SoT': k_sot,
            'Tag': tag,
            'Conv_Pct': round(conv_pct, 2)
        }

    except Exception:
        return {'K_Goles': 1.0, 'K_SoT': 1.0, 'Tag': 'ERROR'}

# =============================================================================
#  MÓDULO FACTOR ÁRBITRO (V7.5) - JUEZ DE HIERRO
# =============================================================================
def calcular_factor_arbitro(df, referee_name):
    """
    V7.5: Solo Castiga, No Premia (Max 1.0).
    Normalización de Texto ACTIVA.
    """
    try:
        if 'Referee' not in df.columns:
            return {'K_Cards': 1.0, 'K_Fouls': 1.0, 'Tag': 'NO DATA'}
        
        # 0. NORMALIZACIÓN
        referee_clean = str(referee_name).strip()
        ref_games = df[df['Referee'] == referee_clean]
        if len(ref_games) == 0:
            ref_games = df[df['Referee'].astype(str).str.strip() == referee_clean]

        n_games = len(ref_games)
        if n_games < 3:
            return {'K_Cards': 1.0, 'K_Fouls': 1.0, 'Tag': '⚪ NEUTRO'}
        
        # 2. Medias
        total_cards = (df['HY'] + df['AY'] + df['HR'] + df['AR']).sum()
        total_fouls = (df['HF'] + df['AF']).sum()
        total_games = len(df)
        
        if total_games == 0: return {'K_Cards': 1.0, 'K_Fouls': 1.0, 'Tag': 'NO DATA'}
        
        avg_cards_league = total_cards / total_games
        avg_fouls_league = total_fouls / total_games
            
        ref_cards = (ref_games['HY'] + ref_games['AY'] + ref_games['HR'] + ref_games['AR']).sum()
        ref_fouls = (ref_games['HF'] + ref_games['AF']).sum()
        
        avg_cards_ref = ref_cards / n_games
        avg_fouls_ref = ref_fouls / n_games
        
        # 3. Ratio
        k_cards = avg_cards_ref / avg_cards_league if avg_cards_league > 0 else 1.0
        k_fouls = avg_fouls_ref / avg_fouls_league if avg_fouls_league > 0 else 1.0
        
        # 4. CAPS V7.5 - JUEZ DE HIERRO
        # Max 1.0 (Neutraliza el premio)
        # Min 0.80 (Mantiene la protección ante jueces permisivos)
        k_cards = max(0.80, min(k_cards, 1.0))
        k_fouls = max(0.80, min(k_fouls, 1.0))
        
        # 5. Etiquetado (Solo informativo)
        tag = "⚪ ESTÁNDAR"
        if avg_cards_ref > avg_cards_league * 1.15: tag = "🔥 ESTRICTO (Visual)"
        elif k_cards < 0.90: tag = "🔵 PERMISIVO (Filtro Activo)"
        
        return {
            'K_Cards': k_cards,
            'K_Fouls': k_fouls,
            'Tag': tag
        }

    except Exception:

        return {'K_Cards': 1.0, 'K_Fouls': 1.0, 'Tag': 'ERROR'}

# =============================================================================
# [NUEVO] MÓDULO ADITIVO: CÁLCULO DE DEBILIDAD DEFENSIVA
# =============================================================================
def calcular_factor_debilidad(df, home_team, away_team):
    """
    Calcula qué tan débil es la defensa comparada con el promedio de la liga.
    Retorna factores > 1.0 si la defensa es mala (recibe más goles que la media).
    """
    try:
        # 1. Promedios Globales de la Liga (Benchmark)
        avg_conceded_home = df['FTAG'].mean() # Goles que recibe el Local
        avg_conceded_away = df['FTHG'].mean() # Goles que recibe el Visitante
        
        # 2. Datos de los equipos específicos
        # Defensa del Local (jugando en casa)
        home_games = df[df['HomeTeam'] == home_team]
        if len(home_games) > 0:
            home_conceded_avg = home_games['FTAG'].mean()
            factor_defensa_local = home_conceded_avg / avg_conceded_home if avg_conceded_home > 0 else 1.0
        else:
            factor_defensa_local = 1.0

        # Defensa del Visitante (jugando fuera)
        away_games = df[df['AwayTeam'] == away_team]
        if len(away_games) > 0:
            away_conceded_avg = away_games['FTHG'].mean()
            factor_defensa_visit = away_conceded_avg / avg_conceded_away if avg_conceded_away > 0 else 1.0
        else:
            factor_defensa_visit = 1.0
            
        # Limites de seguridad (evitar multiplicadores extremos por falta de datos)
        factor_defensa_local = max(0.5, min(factor_defensa_local, 2.0))
        factor_defensa_visit = max(0.5, min(factor_defensa_visit, 2.0))

        return {
            "weakness_home": factor_defensa_local,   # Qué tan débil es el local defendiendo
            "weakness_away": factor_defensa_visit    # Qué tan débil es el visitante defendiendo
        }

    except Exception:
        return {"weakness_home": 1.0, "weakness_away": 1.0}
