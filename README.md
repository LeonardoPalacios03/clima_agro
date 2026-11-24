# Clima para el agro chileno · Ficha técnica

**Autor:** Leonardo Palacios - Marcos Muñoz

**Asignatura:** Visualización de Datos · INACAP · Evaluación N°3

**Aplicación desplegada:** https://clima-agro1.vercel.app

---

## 1. El tema

**Qué se analiza.** La disponibilidad de agua (lluvia y balance hídrico) y el riesgo de heladas en nueve zonas agrícolas de Chile, de Copiapó a Osorno, comparando el año elegido con los 10 años anteriores.

**A quién le sirve.** A agricultores y asesores técnicos que planifican riego, protección contra heladas o fechas de siembra; también a quien analiza la situación hídrica de una región (municipios, cooperativas, oficinas de INDAP).

**Preguntas que responde el tablero.**

| Nivel | Pregunta |
|---|---|
| Vista general — *¿cómo está?* | ¿El año viene más seco o más lluvioso que lo habitual en mi zona? ¿El déficit de agua se acumula más rápido que en otros años? ¿Hay más o menos heladas que lo normal? |
| Vista de detalle — *¿dónde o cuándo ocurre?* | ¿En qué meses se concentraron los déficits? ¿Qué zonas vienen peor este año? ¿En qué meses se concentra el riesgo de helada? |

## 2. La API

| | |
|---|---|
| **API** | [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api) — endpoint `https://archive-api.open-meteo.com/v1/archive` |
| **Qué entrega** | Series diarias derivadas de reanálisis ERA5 (0,25°, ~25 km) y ERA5-Land (0,1°, ~11 km) de Copernicus/ECMWF, desde 1940. Variables usadas: `precipitation_sum` (mm), `temperature_2m_mean`, `temperature_2m_min`, `temperature_2m_max` (°C) y `et0_fao_evapotranspiration` (mm, evapotranspiración de referencia FAO-56). |
| **Acceso** | Abierta, sin registro ni clave. Petición GET con `latitude`, `longitude`, `start_date`, `end_date`, `daily` y `timezone`. Acepta varias coordenadas separadas por coma y en ese caso devuelve una lista JSON (una estructura por ubicación). |
| **Licencia** | Datos bajo CC BY 4.0: la fuente se atribuye en el pie de cada vista. |
| **Limitaciones** | (1) Uso gratuito solo no comercial: menos de 10.000 llamadas/día, 5.000/hora y 600/minuto, contadas por IP; en Vercel la IP es compartida, así que el límite puede alcanzarse antes. (2) Los datos llegan con ~5 días de retraso. (3) Es un **reanálisis** (modelo + observaciones), no la medición de una estación: representa una celda de 11–25 km y suaviza fenómenos locales como heladas de fondo de valle. (4) El tablero usa año calendario y no año hidrológico (abr–mar). |

Cada vista muestra en el pie las URL exactas consultadas, de modo que un tercero puede abrirlas y verificar las cifras.

## 3. Decisiones de visualización

Todos los gráficos se generan en el servidor con **matplotlib** (`tablero/graficos.py`) y se incrustan como PNG. Color: azul = año elegido, gris = años de referencia; en el mapa de calor, rojo = déficit y azul = exceso, con gris neutro en cero.

| # | Vista | Pregunta que responde | Tipo elegido y por qué | Variables |
|---|---|---|---|---|
| G1 | General | ¿En qué meses llovió más o menos de lo habitual? | **Barras + marca de promedio.** La lluvia mensual es una magnitud que parte de cero y la longitud de la barra se compara con precisión contra una marca fija. Es más preciso que dos series de barras agrupadas porque deja una sola barra por mes. | mes, lluvia año, lluvia promedio |
| G2 | General | ¿El año es seco o lluvioso frente a los 10 anteriores? | **Barras con el año destacado y línea de promedio.** Comparar 11 totales entre sí es una tarea de magnitud: las barras alineadas a una base común son la codificación más precisa. | año, lluvia acumulada |
| G3 | General | ¿El déficit se acumula más rápido que lo habitual? | **Línea acumulada contra banda mín–máx y mediana histórica.** La pregunta trata de una trayectoria en el tiempo; la banda muestra la variabilidad normal sin dibujar 10 líneas encimadas. | día del año, balance acumulado, año (actual vs. históricos) → **3 variables** |
| G4 | Detalle | ¿En qué meses y años se concentraron déficits y excesos? | **Mapa de calor año × mes con escala divergente.** Con 11 × 12 celdas, la posición indica *cuándo* y el color el signo y la magnitud de la anomalía. Cada celda va rotulada con su valor, así que la lectura no depende solo del color. | año, mes, anomalía → **3 variables** |
| G5 | Detalle | ¿Qué zonas vienen más secas, más cálidas o con más heladas? | **Dispersión con tamaño y etiqueta directa.** Ubica cada zona en dos ejes continuos (lluvia y temperatura) y suma heladas como tamaño, rotulado con el número exacto. Las nueve zonas van etiquetadas por nombre y no por color, porque nueve colores no se distinguen. | zona, lluvia, temperatura media, días con helada → **4 variables** |
| G6 | Detalle | ¿En qué meses se concentra el riesgo de helada? | **Diagrama de caja por mes con línea de 0 °C** y conteo de heladas sobre cada caja. Muestra la *distribución* de la mínima diaria (la métrica crítica para heladas), no solo su promedio, que ocultaría las noches extremas. | mes, distribución T mín, n.º de heladas → **3 variables** |

**Gráfico descartado: climograma de doble eje** (barras de lluvia y línea de temperatura sobre dos escalas verticales). Es el formato clásico en climatología, pero lo descartamos por dos razones. Primero, el cruce visual entre barras y línea depende de cómo se fije cada escala, así que sugiere relaciones que no existen. Segundo, impide comparar el año elegido con su referencia, que es la pregunta central del tablero. Lo reemplazamos por G1 (lluvia contra su promedio) y G5 (lluvia y temperatura en ejes del mismo gráfico, sin doble escala). También descartamos la **serie diaria de precipitación**: con cientos de días en cero y algunos picos aislados, el gráfico resultaba ilegible.

## 4. Preparación de los datos

**Consumo** (`tablero/datos.py`). Se hacen dos consultas por página como máximo: una por la zona elegida (año elegido más los 10 anteriores) y otra, solo en la vista de detalle, con las nueve zonas para el año elegido. La segunda usa coordenadas separadas por coma, así que es una sola llamada. Las respuestas quedan en caché en memoria durante 3 horas para respetar los límites de la API. Si la API falla, la vista muestra un mensaje (HTTP 503) en vez de caerse:

```python
def _consultar(params):
    clave = tuple(sorted(params.items()))
    guardado = _cache.get(clave)
    if guardado and time.time() - guardado[0] < TTL_CACHE_S:
        return guardado[1]
    try:
        r = requests.get(API_URL, params=params, timeout=TIMEOUT_S)
        r.raise_for_status()
        js = r.json()
    except (requests.RequestException, ValueError) as exc:
        raise ErrorAPI(f"No fue posible consultar Open-Meteo ({exc.__class__.__name__}).") from exc
    if isinstance(js, dict) and js.get("error"):
        raise ErrorAPI(f"Open-Meteo respondió con error: {js.get('reason', 'sin detalle')}")
    _cache[clave] = (time.time(), js)
    return js
```

**Limpieza:**

```python
df = df.dropna(subset=["precip", "tmed", "tmin", "tmax", "et0"], how="all")  # días aún no publicados
df.loc[df["precip"] < 0, "precip"] = pd.NA      # valores físicamente imposibles
df.loc[df["et0"] < 0, "et0"] = pd.NA
for c in ["tmed", "tmin", "tmax"]:
    df[c] = df[c].interpolate(limit=2)          # solo huecos de 1–2 días; la lluvia NO se interpola
df["balance"] = df["precip"] - df["et0"]        # balance hídrico climático diario
```

**Período comparable** (`tablero/indicadores.py`). Si el año elegido está en curso, todos los años se recortan al mismo tramo (1 de enero hasta el último día con datos). Comparar medio año contra años completos mostraría un déficit que no existe:

```python
corte = df[df["anio"] == anio]["fecha"].max()
md = df["fecha"].dt.month * 100 + df["fecha"].dt.day
dfc = df[md <= corte.month * 100 + corte.day]
```

Los filtros (`zona` y `anio`) viajan en la URL (`?zona=talca&anio=2025`) y se validan contra listas cerradas antes de consultar la API.

## 5. Los indicadores

Los tres KPI se calculan sobre el período comparable de la zona elegida. Todos usan como referencia el **promedio de los 10 años anteriores en el mismo tramo del año**, y se muestran con su diferencia absoluta y porcentual.

| KPI | Fórmula | Unidad | Valor de referencia | Lectura favorable |
|---|---|---|---|---|
| Precipitación acumulada | Σ `precipitation_sum` diario del período | mm | Promedio de la misma suma en los 10 años previos | Mayor que la referencia |
| Balance hídrico climático | Σ (`precipitation_sum` − `et0_fao_evapotranspiration`) | mm (negativo = déficit) | Promedio del mismo balance en los 10 años previos | Mayor (menos negativo) que la referencia |
| Días con helada | N.º de días con `temperature_2m_min` ≤ 0 °C | días | Promedio de días con helada en los 10 años previos | Menor que la referencia |

## 6. Propuesta de valor y ética

**Qué decisión permite tomar.** Saber si conviene adelantar o reforzar el riego, contratar o activar protección contra heladas, o ajustar fechas de siembra y cosecha. Hoy esa información está repartida entre boletines regionales en PDF. El tablero la reúne en una sola pantalla, con la zona propia frente a su historia y frente a otras zonas.

**A quién sirve y a quién afecta.** Sirve a agricultores (sobre todo pequeños productores sin estación meteorológica propia), asesores técnicos y analistas regionales. También afecta a quien no lo usa directamente: aseguradoras y bancos podrían usar un "año desfavorable" para encarecer seguros o créditos agrícolas, y una lectura apresurada podría influir en la petición de una declaración de emergencia agrícola.

**Dilema ético: ¿contra qué "normal" comparamos?** La referencia decide el mensaje. Chile central vive una megasequía desde 2010, así que el promedio de los últimos 10 años ya es un período seco. Contra esa base, un año muy seco puede aparecer como "normal" o incluso "favorable". Una normal climatológica larga (1991–2020) mostraría déficits mucho mayores. La API sí entrega esos años, pero pedir 30 años por zona multiplica el peso de cada consulta y, en una IP compartida de Vercel, arriesgaba el bloqueo del servicio para todos los usuarios.

**Qué decidimos.** Usar el promedio de los 10 años previos, pero sin esconderlo:

1. La referencia y sus años exactos aparecen junto a cada KPI y en el pie de página.
2. G2 y G4 muestran cada uno de los 10 años de referencia, no solo su promedio, para que el usuario vea que la base es variable y mayormente seca.
3. Las etiquetas "favorable/desfavorable" se refieren siempre a esta referencia, nunca a un juicio absoluto.
4. Declaramos que los datos son de reanálisis y no de estación, para que nadie tome una decisión de alto costo (un seguro, un crédito, un reclamo) como si fueran medición oficial.
5. No interpolamos lluvia faltante ni mostramos datos guardados cuando la API falla: un tablero con cifras inventadas o desactualizadas sin aviso no es evidencia.

---

### Ejecución local y despliegue

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py runserver        # http://127.0.0.1:8000
```

Despliegue en Vercel: importar el repositorio de GitHub en Vercel (la configuración está en `vercel.json`, que apunta a `config/wsgi.py`) y definir la variable de entorno `DJANGO_SECRET_KEY`. No se requiere base de datos.

```
├── config/            settings.py · urls.py · wsgi.py
├── tablero/
│   ├── datos.py        consumo de Open-Meteo, caché y limpieza
│   ├── indicadores.py  período comparable y KPI
│   ├── graficos.py     6 gráficos matplotlib
│   ├── views.py        vista general y vista de detalle
│   └── templates/tablero/
├── requirements.txt
└── vercel.json
```
