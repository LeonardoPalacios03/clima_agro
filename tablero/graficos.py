"""Gráficos generados en el servidor con matplotlib (PNG en base64)."""
import base64
import io
import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

from .datos import ZONAS
from .indicadores import MESES

# Paleta: azul = año seleccionado, gris = historia; divergente rojo (seco) / gris / azul (húmedo).
AZUL = "#2a78d6"
GRIS = "#b9b7ae"
GRIS_OSC = "#52514e"
TINTA = "#0b0b0b"
ROJO = "#d03b3b"
SUPERFICIE = "#fcfcfb"
DIVERGENTE = LinearSegmentedColormap.from_list(
    "seco_humedo", ["#b8322f", "#e98a7f", "#f0efec", "#86b6ef", "#1c5cab"])

plt.rcParams.update({
    "figure.facecolor": SUPERFICIE,
    "axes.facecolor": SUPERFICIE,
    "axes.edgecolor": "#c3c2b7",
    "axes.labelcolor": GRIS_OSC,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": "#e1e0d9",
    "grid.linewidth": 0.6,
    "xtick.color": GRIS_OSC,
    "ytick.color": GRIS_OSC,
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
    "axes.titlecolor": TINTA,
    "legend.frameon": False,
})


def _png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


# ---------------------------------------------------------------- Vista general

def precip_mensual(tabla_mensual, anio):
    """G1 · Barras del año elegido vs. marca del promedio mensual histórico."""
    hist = tabla_mensual.drop(index=anio, errors="ignore")
    meses = [m for m in range(1, 13) if m in tabla_mensual.columns and not np.isnan(tabla_mensual.loc[anio].get(m, np.nan))]
    actual = [tabla_mensual.loc[anio, m] for m in meses]
    prom = [hist[m].mean() for m in meses]
    x = np.arange(len(meses))
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ax.bar(x, actual, width=0.6, color=AZUL, label=str(anio), zorder=2)
    ax.scatter(x, prom, marker="_", s=420, linewidths=2.5, color=TINTA, label="Promedio 10 años previos", zorder=3)
    ax.set_xticks(x, [MESES[m - 1] for m in meses])
    ax.set_ylabel("mm")
    ax.set_title(f"Precipitación mensual {anio} vs. promedio")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper left")
    return _png(fig)


def precip_por_anio(resumen, anio):
    """G2 · Precipitación del período comparable por año, año elegido destacado."""
    anios = resumen.index.tolist()
    vals = resumen["precip"].values
    prom = resumen.drop(index=anio)["precip"].mean()
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    colores = [AZUL if a == anio else GRIS for a in anios]
    ax.bar([str(a) for a in anios], vals, color=colores, width=0.65, zorder=2)
    ax.axhline(prom, color=TINTA, linestyle="--", linewidth=1.2, zorder=3)
    ax.text(-0.45, prom, f"promedio {prom:,.0f} mm".replace(",", "."), va="bottom", ha="left",
            color=TINTA, fontsize=9, bbox={"facecolor": SUPERFICIE, "edgecolor": "none", "pad": 1})
    i = anios.index(anio)
    ax.text(i, vals[i], f"{vals[i]:,.0f}".replace(",", "."), ha="center", va="bottom", color=TINTA,
            fontsize=9, fontweight="bold")
    ax.set_ylabel("mm acumulados en el período")
    ax.set_title("¿Cómo se ubica el año frente a los 10 anteriores?")
    ax.grid(axis="x", visible=False)
    ax.tick_params(axis="x", rotation=0, labelsize=8.5)
    return _png(fig)


def balance_acumulado(dfc, anio):
    """G3 · Balance hídrico acumulado (P − ET0) día a día: año elegido vs. rango histórico."""
    piv = dfc.assign(acum=dfc.groupby("anio")["balance"].cumsum()).pivot_table(
        index="dia_anio", columns="anio", values="acum")
    hist = piv.drop(columns=anio, errors="ignore")
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ax.fill_between(hist.index, hist.min(axis=1), hist.max(axis=1), color=GRIS, alpha=0.35, lw=0,
                    label="Rango 10 años previos")
    ax.plot(hist.index, hist.median(axis=1), color=GRIS_OSC, lw=1.4, linestyle="--", label="Mediana histórica")
    ax.plot(piv.index, piv[anio], color=AZUL, lw=2.2, label=str(anio))
    ax.axhline(0, color="#c3c2b7", lw=1)
    inicios = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
    ax.set_xticks([d for d in inicios if d <= piv.index.max()],
                  [MESES[i] for i, d in enumerate(inicios) if d <= piv.index.max()])
    ax.set_ylabel("mm acumulados (negativo = déficit)")
    ax.set_title("Balance hídrico acumulado (precipitación − evapotranspiración)")
    ax.legend(loc="lower left", fontsize=8.5)
    return _png(fig)


# ---------------------------------------------------------------- Vista de detalle

def heatmap_anomalias(tabla_mensual, anio):
    """G4 · Año × mes × anomalía de precipitación (mm) respecto del promedio mensual de los 10 años previos."""
    base = tabla_mensual.drop(index=anio, errors="ignore").mean()
    anom = tabla_mensual - base
    datos = anom.values.astype(float)
    lim = np.nanmax(np.abs(datos)) if np.isfinite(datos).any() else 1
    lim = max(lim, 1)
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    im = ax.imshow(datos, cmap=DIVERGENTE, norm=TwoSlopeNorm(0, -lim, lim), aspect="auto")
    ax.set_xticks(range(len(anom.columns)), [MESES[m - 1] for m in anom.columns])
    ax.set_yticks(range(len(anom.index)), [str(a) for a in anom.index])
    for (i, j), v in np.ndenumerate(datos):
        if np.isfinite(v):
            color = "white" if abs(v) > lim * 0.6 else TINTA
            ax.text(j, i, f"{v:+.0f}", ha="center", va="center", fontsize=7, color=color)
    fila = list(anom.index).index(anio)
    ax.add_patch(plt.Rectangle((-0.5, fila - 0.5), len(anom.columns), 1, fill=False, ec=TINTA, lw=1.6))
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, shrink=0.85, pad=0.02)
    cb.set_label("mm sobre (+) / bajo (−) el promedio")
    cb.outline.set_visible(False)
    ax.set_title("Anomalía de precipitación por mes y año")
    return _png(fig)


def comparacion_zonas(df_zonas, zona_sel):
    """G5 · Zonas: precipitación (x) vs. temperatura media (y); tamaño = días con helada."""
    g = df_zonas.groupby("zona").agg(precip=("precip", "sum"), tmed=("tmed", "mean"),
                                     heladas=("tmin", lambda s: int((s <= 0).sum())))
    g = g.loc[[z for z in ZONAS if z in g.index]]
    g["heladas"] = g["heladas"].astype(int)
    tam = 40 + g["heladas"] * 6
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    colores = [AZUL if z == zona_sel else GRIS for z in g.index]
    ax.scatter(g["precip"], g["tmed"], s=tam, c=colores, edgecolors=SUPERFICIE, linewidths=2, zorder=3)
    for z, fila in g.iterrows():
        ax.annotate(f"{ZONAS[z]['nombre']} · {int(fila['heladas'])} d", (fila["precip"], fila["tmed"]),
                    xytext=(7, 4), textcoords="offset points", fontsize=8.5,
                    color=TINTA, fontweight="bold" if z == zona_sel else "normal")
    ax.set_xlabel("Precipitación acumulada del período (mm)")
    ax.set_ylabel("Temperatura media (°C)")
    ax.set_title("¿Dónde está más seco, más cálido o con más heladas?")
    for h in (0, 20, 60):
        ax.scatter([], [], s=40 + h * 6, color=GRIS, label=f"{h} días con helada")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=8, labelspacing=1.4, borderpad=0.8,
              title="Tamaño del punto", title_fontsize=8)
    ax.margins(x=0.18, y=0.15)
    return _png(fig)


def distribucion_tmin(dfc, anio):
    """G6 · Distribución de la temperatura mínima diaria por mes; número de heladas sobre cada caja."""
    d = dfc[dfc["anio"] == anio]
    meses = sorted(d["mes"].unique())
    datos = [d.loc[d["mes"] == m, "tmin"].dropna().values for m in meses]
    fig, ax = plt.subplots(figsize=(7.2, 3.9))
    bp = ax.boxplot(datos, patch_artist=True, widths=0.55, showfliers=True,
                    medianprops={"color": TINTA, "lw": 1.6},
                    flierprops={"marker": "o", "markersize": 3, "markerfacecolor": GRIS_OSC, "markeredgewidth": 0},
                    whiskerprops={"color": GRIS_OSC}, capprops={"color": GRIS_OSC})
    for caja in bp["boxes"]:
        caja.set(facecolor="#b7d3f6", edgecolor=AZUL)
    ax.axhline(0, color=ROJO, lw=1.3, linestyle="--")
    ax.text(len(meses) + 0.45, 0, "0 °C", color=ROJO, va="bottom", ha="right", fontsize=8.5)
    tope = max((x.max() for x in datos if len(x)), default=0)
    for i, x in enumerate(datos, start=1):
        n = int((x <= 0).sum())
        ax.text(i, tope + 1, f"{n}", ha="center", fontsize=8.5, color=ROJO if n else GRIS_OSC,
                fontweight="bold" if n else "normal")
    ax.text(0.4, tope + 2.6, "días con helada →", fontsize=8, color=GRIS_OSC)
    ax.set_xticks(range(1, len(meses) + 1), [MESES[m - 1] for m in meses])
    ax.set_ylabel("Temperatura mínima diaria (°C)")
    ax.set_ylim(top=tope + 4)
    ax.set_title(f"Distribución de mínimas diarias por mes, {anio}")
    ax.grid(axis="x", visible=False)
    return _png(fig)
