import math
import numpy as np
from collections import Counter
from statistics import median

from config import Config
from event_config import get_event_config


# =============================================================================
# UTILIDADES INTERNAS
# =============================================================================
def _time_decay_weights(n, alpha=0.15):
    """
    CORREGIDO: Genera pesos exponenciales para Time Decay.
    
    Asume que datos[0] es el MÁS RECIENTE (izquierda).
    - i = 0 (reciente) -> peso máximo (exp(0) = 1.0)
    - i aumenta (antiguo) -> peso disminuye
    """
    # Se usa 'i' directamente como exponente de decaimiento
    w = np.array([math.exp(-alpha * i) for i in range(n)])
    
    # Normalizar para que la suma sea 1.0
    return w / w.sum()


def _detectar_outliers_iqr(data):
    """
    Detecta valores atípicos usando el rango intercuartílico (IQR).
    """
    if len(data) < 4:
        return []
        
    sorted_data = sorted(data)
    n = len(sorted_data)

    q1 = sorted_data[n // 4]
    q3 = sorted_data[(3 * n) // 4]
    iqr = q3 - q1

    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr

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
    try:
        event_cfg = get_event_config(event_type)
    except Exception:
        # Fallback de seguridad si el evento no existe en config
        from event_config import EVENTS
        event_cfg = list(EVENTS.values())[0]

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

    arr = np.array(datos_limpios)

    # -------------------------------------------------------------------------
    # 2. Cálculo de Media y Varianza (Con Time Decay Corregido)
    # -------------------------------------------------------------------------
    if usar_time_decay:
        w = _time_decay_weights(n)
        media = float(np.sum(arr * w))
        # Varianza ponderada
        varianza = float(np.sum(w * (arr - media) ** 2))
    else:
        media = float(arr.mean())
        varianza = float(arr.var(ddof=1)) if n > 1 else 0.0

    std = math.sqrt(varianza) if varianza > 0 else 0.0
    
    # Coeficiente de Variación (CV)
    cv = std / media if media > 0 else 0.0

    # -------------------------------------------------------------------------
    # 3. Métricas Adicionales y Outliers
    # -------------------------------------------------------------------------
    # CV Normalizado vs Esperado del evento
    cv_expected = getattr(event_cfg, 'cv_expected', 1.0)
    cv_norm = cv / cv_expected if cv_expected > 0 else cv

    rango = float(arr.max() - arr.min())
    mediana = float(median(arr))
    
    # Moda (Manejo seguro si hay múltiples modas o array vacío)
    if n > 0:
        counts = Counter(arr)
        moda = float(counts.most_common(1)[0][0])
    else:
        moda = 0.0

    outliers = _detectar_outliers_iqr(arr.tolist())

    # -------------------------------------------------------------------------
    # 4. Flags de Diagnóstico
    # -------------------------------------------------------------------------
    flags = []

    if media <= 0:
        flags.append("MEDIA_INVALIDA")

    if std == 0 and media > 0:
        # Nota: Varianza 0 es posible matemáticamente pero rara en deportes
        pass 

    if cv_norm >= 1.5:
        flags.append("CV_MUY_ALTO")
    elif cv_norm >= 1.2:
        flags.append("CV_ALTO")

    if outliers:
        flags.append("OUTLIERS_PRESENTES")

    # Estado humano legible
    if cv_norm >= 1.5:
        estado = "INCIERTO"
    elif cv_norm >= 1.2:
        estado = "VOLÁTIL"
    else:
        estado = "ESTABLE"

    # -------------------------------------------------------------------------
    # 5. Retorno Estructurado
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

