import math
import numpy as np
from collections import Counter
from statistics import median

# Intentamos importar config, si falla usamos defaults para evitar errores circulares
try:
    from config import Config
except ImportError:
    class Config:
        MIN_MATCHES_DATA = 5

try:
    from event_config import get_event_config
except ImportError:
    get_event_config = None


# =============================================================================
# UTILIDADES INTERNAS
# =============================================================================
def _time_decay_weights(n, alpha=0.15):
    """
    Genera pesos exponenciales para Time Decay.
    Asume que datos[0] es el MÁS RECIENTE (izquierda).
    """
    # Se usa 'i' directamente como exponente de decaimiento
    w = np.array([math.exp(-alpha * i) for i in range(n)])
    
    # Normalizar para que la suma sea 1.0
    return w / w.sum()


def _detectar_outliers_iqr(data, factor=3.0):
    """
    Detecta valores atípicos usando el rango intercuartílico (IQR).
    
    MEJORA BETA: Se aumentó el factor de 1.5 (Estándar) a 3.0 (Permisivo).
    Esto evita que goleadas reales (ej: 6-1) sean eliminadas del análisis
    en equipos Top como Bayern o City.
    """
    if len(data) < 4:
        return []
        
    sorted_data = sorted(data)
    n = len(sorted_data)

    q1 = sorted_data[n // 4]
    q3 = sorted_data[(3 * n) // 4]
    iqr = q3 - q1

    # Rango Extendido (Solo borra anomalías extremas, no partidos buenos)
    lower = q1 - factor * iqr
    upper = q3 + factor * iqr

    return [x for x in data if x < lower or x > upper]


# =============================================================================
# MOTOR ESTADÍSTICO — DESCRIPTIVO
# =============================================================================
def calcular_metricas_desde_datos(
    datos,
    event_type: str,
    usar_time_decay: bool = True,
    devolver_diagnostico: bool = True
):
    """
    Calcula métricas estadísticas.
    Entrada: datos (lista) donde index 0 es el más reciente.
    """

    # -------------------------------------------------------------------------
    # 1. Configuración y Validaciones
    # -------------------------------------------------------------------------
    cv_expected = 1.0
    if get_event_config:
        try:
            event_cfg = get_event_config(event_type)
            cv_expected = getattr(event_cfg, 'cv_expected', 1.0)
        except Exception:
            pass

    if not isinstance(datos, (list, tuple)):
        raise ValueError("Los datos deben ser una lista o tupla")

    # Limpieza de nulos y conversión
    datos_limpios = [float(x) for x in datos if x is not None]

    if any(x < 0 for x in datos_limpios):
        raise ValueError("Los datos no pueden ser negativos")

    n = len(datos_limpios)

    # Validación de muestra mínima
    if n < Config.MIN_MATCHES_DATA:
        return {
            "valido": False,
            "razones": ["MUESTRA_INSUFICIENTE"],
            "n": n,
            "event_type": event_type,
            "lambda": 0.0,
            "std": 0.0,
            "cv": 0.0
        }

    # -------------------------------------------------------------------------
    # 2. Detección de Outliers (MEJORADO)
    # -------------------------------------------------------------------------
    # Primero detectamos outliers pero NO los borramos inmediatamente si usamos Time Decay,
    # ya que el Time Decay por sí solo ya penaliza lo antiguo.
    # Sin embargo, para mantener la higiene, borraremos solo los EXTREMOS (Factor 3.0).
    
    outliers = _detectar_outliers_iqr(datos_limpios, factor=3.0)
    
    # Filtramos los datos para el cálculo (Winsorizing suave)
    datos_calc = [x for x in datos_limpios if x not in outliers]
    n_calc = len(datos_calc)
    
    if n_calc < 1: # Si borramos todo (raro), usamos los originales
        datos_calc = datos_limpios
        n_calc = n

    arr = np.array(datos_calc)

    # -------------------------------------------------------------------------
    # 3. Cálculo de Media y Varianza (Con Time Decay)
    # -------------------------------------------------------------------------
    if usar_time_decay:
        w = _time_decay_weights(n_calc)
        media = float(np.sum(arr * w))
        # Varianza ponderada
        varianza = float(np.sum(w * (arr - media) ** 2))
    else:
        media = float(arr.mean())
        varianza = float(arr.var(ddof=1)) if n_calc > 1 else 0.0

    std = math.sqrt(varianza) if varianza > 0 else 0.0
    
    # Coeficiente de Variación (CV)
    cv = std / media if media > 0 else 0.0

    # -------------------------------------------------------------------------
    # 4. Métricas Adicionales
    # -------------------------------------------------------------------------
    cv_norm = cv / cv_expected if cv_expected > 0 else cv

    rango = float(arr.max() - arr.min()) if n_calc > 0 else 0.0
    mediana = float(median(arr)) if n_calc > 0 else 0.0
    
    if n_calc > 0:
        counts = Counter(arr)
        moda = float(counts.most_common(1)[0][0])
    else:
        moda = 0.0

    # -------------------------------------------------------------------------
    # 5. Flags de Diagnóstico
    # -------------------------------------------------------------------------
    flags = []

    if media <= 0:
        flags.append("MEDIA_INVALIDA")

    if cv_norm >= 1.5:
        flags.append("CV_MUY_ALTO")
    elif cv_norm >= 1.2:
        flags.append("CV_ALTO")

    if outliers:
        flags.append("OUTLIERS_DETECTADOS")

    # Estado humano legible
    if cv_norm >= 1.5:
        estado = "INCIERTO"
    elif cv_norm >= 1.2:
        estado = "VOLÁTIL"
    else:
        estado = "ESTABLE"

    # -------------------------------------------------------------------------
    # 6. Retorno Estructurado
    # -------------------------------------------------------------------------
    es_valido = "MEDIA_INVALIDA" not in flags

    resultado = {
        "valido": es_valido,
        "event_type": event_type,
        "n": n,
        "lambda": round(media, 4),      # Lambda crítica para el modelo
        "media": round(media, 4),
        "mediana": round(mediana, 4),
        "moda": round(moda, 4),
        "varianza": round(varianza, 4),
        "std": round(std, 4),           # Necesario para lambda_engine
        "desviacion_std": round(std, 4),
        "cv": round(cv, 4),
        "cv_normalizado": round(cv_norm, 4),
        "rango": round(rango, 4),
        "flags": flags,
        "estado_estadistico": estado
    }

    if devolver_diagnostico:
        resultado["outliers"] = outliers

    return resultado
