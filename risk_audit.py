# risk_audit.py
import csv
from datetime import datetime
from pathlib import Path

# =============================================================================
# CONFIG
# =============================================================================
AUDIT_FILE = Path("data/rechazos_audit.csv")

HEADERS = [
    "timestamp",
    "fase",
    "estado_sistema",
    "z_base",
    "z_dinamico",
    "cv_max",
    "drawdown",
    "razones"
]


def _init_file():
    if not AUDIT_FILE.exists():
        AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_FILE, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(HEADERS)


# =============================================================================
# LOGGER PRINCIPAL
# =============================================================================
def log_rechazo(
    fase: str,
    estado_sistema: dict,
    z_dinamico: float | None,
    cv_max: float,
    razones: list[str]
):
    """
    Registra un rechazo del sistema (pre o post Poisson)
    """

    _init_file()

    row = [
        datetime.utcnow().isoformat(),
        fase,
        estado_sistema.get("estado"),
        estado_sistema.get("z"),
        z_dinamico,
        round(cv_max, 4),
        round(estado_sistema.get("drawdown", 0), 4),
        ";".join(razones)
    ]

    with open(AUDIT_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(row)
