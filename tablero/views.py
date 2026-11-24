from django.shortcuts import render
from django.utils import timezone

from . import datos, graficos
from . import indicadores as ind

FMT_FECHA = "%d-%m-%Y"


def _filtros(request):
    """Lee y valida los filtros de la URL (?zona=...&anio=...)."""
    anios = datos.anios_disponibles()
    zona = request.GET.get("zona", datos.ZONA_POR_DEFECTO)
    if zona not in datos.ZONAS:
        zona = datos.ZONA_POR_DEFECTO
    try:
        anio = int(request.GET.get("anio", anios[0]))
    except (TypeError, ValueError):
        anio = anios[0]
    if anio not in anios:
        anio = anios[0]
    return zona, anio, anios


def _contexto_base(request, vista):
    zona, anio, anios = _filtros(request)
    df, url_zona = datos.serie_zona(zona, anio)
    dfc, corte = ind.periodo_comparable(df, anio)
    if corte is None:
        raise datos.ErrorAPI(f"Open-Meteo no devolvió datos para {anio}.")
    resumen = ind.resumen_anual(dfc)
    parcial = not (corte.month == 12 and corte.day == 31)
    ctx = {
        "vista": vista,
        "zonas": datos.ZONAS,
        "zona": zona,
        "zona_info": datos.ZONAS[zona],
        "anio": anio,
        "anios": anios,
        "parcial": parcial,
        "periodo_txt": f"01-01 al {corte.strftime('%d-%m')} de cada año",
        "datos_desde": df["fecha"].min().strftime(FMT_FECHA),
        "datos_hasta": df["fecha"].max().strftime(FMT_FECHA),
        "anio_ref_desde": anio - datos.ANIOS_HISTORIA,
        "anio_ref_hasta": anio - 1,
        "fuentes": [url_zona],
        "api_docs": datos.API_DOCS,
        "consultado": timezone.localtime().strftime("%d-%m-%Y %H:%M"),
    }
    return ctx, dfc, resumen


def _error(request, vista, exc):
    return render(request, "tablero/error.html", {"vista": vista, "mensaje": str(exc),
                                                  "api_docs": datos.API_DOCS}, status=503)


def vista_general(request):
    """Nivel 1 · ¿Cómo está? KPI + gráficos de síntesis."""
    try:
        ctx, dfc, resumen = _contexto_base(request, "general")
    except datos.ErrorAPI as exc:
        return _error(request, "general", exc)
    anio = ctx["anio"]
    tabla = ind.mensual(dfc)
    ctx["kpis"] = ind.calcular_kpis(resumen, anio)
    ctx["graficos"] = [
        {"id": "G1", "pregunta": "¿En qué meses llovió más o menos de lo habitual?",
         "lectura": "Barra azul = lluvia del mes en el año elegido; marca negra = promedio de ese mismo mes en los 10 años previos.",
         "img": graficos.precip_mensual(tabla, anio)},
        {"id": "G2", "pregunta": "¿El año elegido es seco o lluvioso comparado con los 10 anteriores?",
         "lectura": "Cada barra es la lluvia acumulada en el mismo tramo del año; la línea punteada es el promedio de los 10 años previos.",
         "img": graficos.precip_por_anio(resumen, anio)},
        {"id": "G3", "pregunta": "¿El déficit de agua se está acumulando más rápido que lo habitual?",
         "lectura": "Balance = precipitación − evapotranspiración de referencia, acumulado día a día. Bajo la mediana gris = temporada más exigente en riego.",
         "img": graficos.balance_acumulado(dfc, anio)},
    ]
    return render(request, "tablero/general.html", ctx)


def vista_detalle(request):
    """Nivel 2 · ¿Dónde o cuándo ocurre? Cortes por mes, año y zona."""
    try:
        ctx, dfc, resumen = _contexto_base(request, "detalle")
        df_zonas, url_zonas = datos.serie_todas_las_zonas(ctx["anio"])
    except datos.ErrorAPI as exc:
        return _error(request, "detalle", exc)
    anio, zona = ctx["anio"], ctx["zona"]
    ctx["fuentes"].append(url_zonas)
    tabla = ind.mensual(dfc)
    ctx["graficos"] = [
        {"id": "G4", "pregunta": "¿En qué meses y años se concentraron los déficits y excesos de lluvia?",
         "lectura": "Rojo = llovió menos que el promedio del mes; azul = más. El año elegido va recuadrado.",
         "img": graficos.heatmap_anomalias(tabla, anio)},
        {"id": "G5", "pregunta": "¿En qué zonas agrícolas el año viene más seco, más cálido o con más heladas?",
         "lectura": "Cada punto es una zona: eje X lluvia acumulada, eje Y temperatura media, tamaño = días con helada. La zona elegida va en azul.",
         "img": graficos.comparacion_zonas(df_zonas, zona)},
        {"id": "G6", "pregunta": "¿En qué meses se concentra el riesgo de helada?",
         "lectura": "Cada caja muestra cómo se repartieron las mínimas diarias del mes; el número de arriba cuenta los días bajo 0 °C.",
         "img": graficos.distribucion_tmin(dfc, anio)},
    ]
    return render(request, "tablero/detalle.html", ctx)
