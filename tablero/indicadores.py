"""Período comparable y cálculo de los tres KPI."""
import pandas as pd

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def periodo_comparable(df, anio):
    """Recorta todos los años al mismo tramo 01-ene -> (último mes-día con datos del año elegido).

    Así un año en curso (parcial) se compara contra el mismo tramo de los años anteriores
    y no contra años completos, lo que inflaría artificialmente el déficit.
    """
    actual = df[df["anio"] == anio]
    if actual.empty:
        return df.iloc[0:0], None
    corte = actual["fecha"].max()
    clave_corte = corte.month * 100 + corte.day
    md = df["fecha"].dt.month * 100 + df["fecha"].dt.day
    return df[md <= clave_corte].copy(), corte


def resumen_anual(dfc):
    """Una fila por año con los agregados del período comparable."""
    g = dfc.groupby("anio")
    return pd.DataFrame({
        "precip": g["precip"].sum(min_count=1),
        "et0": g["et0"].sum(min_count=1),
        "balance": g["balance"].sum(min_count=1),
        "tmed": g["tmed"].mean(),
        "heladas": g["tmin"].apply(lambda s: int((s <= 0).sum())),
        "dias": g.size(),
    })


def _kpi(nombre, valor, ref, unidad, mayor_es_mejor, decimales=0, ref_txt="promedio 10 años previos"):
    dif = valor - ref
    pct = (dif / abs(ref) * 100) if ref not in (0, None) and abs(ref) > 1e-9 else None
    favorable = (dif >= 0) if mayor_es_mejor else (dif <= 0)
    if abs(dif) < 10 ** (-decimales) / 2:
        estado, flecha = "neutro", "="
    else:
        estado = "favorable" if favorable else "desfavorable"
        flecha = "▲" if dif > 0 else "▼"
    fmt = f"{{:,.{decimales}f}}"
    return {
        "nombre": nombre,
        "valor": fmt.format(valor).replace(",", "."),
        "unidad": unidad,
        "referencia": fmt.format(ref).replace(",", "."),
        "ref_txt": ref_txt,
        "diferencia": (("+" if dif > 0 else "") + fmt.format(dif)).replace(",", "."),
        "pct": None if pct is None else f"{pct:+.0f} %",
        "estado": estado,
        "flecha": flecha,
    }


def calcular_kpis(resumen, anio):
    """KPI del año elegido contra el promedio de los 10 años anteriores (mismo período)."""
    actual = resumen.loc[anio]
    hist = resumen.drop(index=anio, errors="ignore")
    return [
        _kpi("Precipitación acumulada", actual["precip"], hist["precip"].mean(), "mm", True),
        _kpi("Balance hídrico climático (P − ET0)", actual["balance"], hist["balance"].mean(), "mm", True),
        _kpi("Días con helada (T mín ≤ 0 °C)", actual["heladas"], hist["heladas"].mean(), "días", False,
             decimales=0),
    ]


def mensual(dfc):
    """Precipitación mensual por año (período comparable)."""
    return dfc.groupby(["anio", "mes"])["precip"].sum(min_count=1).unstack("mes")
