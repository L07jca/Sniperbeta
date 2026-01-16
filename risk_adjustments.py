def ajustar_z_dinamico(
    z_base: float,
    cv_max: float,
    drawdown: float,
    z_cap: float = 2.5
):
    # -------------------------
    # Ajuste por CV
    # -------------------------
    if cv_max >= 0.30:
        z_cv = 0.30
    elif cv_max >= 0.25:
        z_cv = 0.15
    else:
        z_cv = 0.0

    # -------------------------
    # Ajuste por Drawdown
    # -------------------------
    if drawdown >= 0.10:
        z_dd = 0.30
    elif drawdown >= 0.05:
        z_dd = 0.15
    else:
        z_dd = 0.0

    z_final = z_base + z_cv + z_dd
    return min(round(z_final, 2), z_cap)
