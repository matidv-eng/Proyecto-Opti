# -*- coding: utf-8 -*-
"""
Genera 'Instancias Excel/instancia_prueba.xlsx' con DATOS INVENTADOS.

Sirve para dos cosas:
  1) Probar main.py mientras Catalán y Liu juntan los datos reales.
  2) Fijar el formato (hojas, columnas y unidades) que debe tener la instancia real.

La instancia es chica a propósito (8 sectores, 5 sitios, 3 puntos actuales, 6 semanas)
para que corra con la licencia gratuita limitada de Gurobi (2000 variables / 2000 restricciones).

IMPORTANTE: este archivo NO va en el ZIP final; la instancia real se arma con datos con fuente.
"""

import os

import numpy as np
import pandas as pd

CARPETA_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(CARPETA_RAIZ, "Instancias Excel", "instancia_prueba.xlsx")

rng = np.random.default_rng(20)

# ---------------------------------------------------------------------------
# Territorio: sectores, macrozonas y sitios candidatos
# ---------------------------------------------------------------------------
sectores = pd.DataFrame({
    "sector": [f"Z{k}" for k in range(1, 9)],
    "macrozona": ["Norte"] * 4 + ["Sur"] * 4,
    "x [km]": rng.uniform(0, 8, 8).round(2),
    "y [km]": np.r_[rng.uniform(5, 10, 4), rng.uniform(0, 5, 4)].round(2),
    "poblacion [hab]": rng.integers(3000, 9000, 8),
})

sitios = pd.DataFrame({
    "sitio": [f"S{k}" for k in range(1, 6)],
    "macrozona": ["Norte", "Norte", "Sur", "Sur", "Sur"],
    "x [km]": [2.0, 6.0, 1.5, 4.0, 6.5],
    "y [km]": [8.0, 6.5, 3.5, 1.5, 4.0],
    "superficie [m2]": [25, 45, 30, 20, 50],
})

puntos_actuales = pd.DataFrame({
    "punto": ["P1", "P2", "P3"],
    "sitio_actual": ["S1", "S3", "S4"],
})

# ---------------------------------------------------------------------------
# Materiales y contenedores
# ---------------------------------------------------------------------------
materiales = pd.DataFrame({"material": ["papel_carton", "plastico", "vidrio", "metal", "carton_liquidos"]})

tipos = pd.DataFrame({
    "tipo": ["PC_3m3", "PL_1m3", "PL_3m3", "VI_2m3", "VI_3m3", "ME_1m3", "CL_1m3"],
    "material": ["papel_carton", "plastico", "plastico", "vidrio", "vidrio", "metal", "carton_liquidos"],
    "capacidad [ton/cont]": [0.20, 0.035, 0.10, 0.60, 0.90, 0.05, 0.04],
    "superficie [m2/cont]": [3.0, 1.4, 3.0, 2.2, 3.2, 1.4, 1.4],
    "costo_compra [CLP/cont/año]": [180000, 60000, 150000, 220000, 300000, 60000, 60000],
    "costo_mantencion [CLP/cont/año]": [40000, 15000, 35000, 45000, 60000, 15000, 15000],
})

# Dotación estándar: contenedores que tiene hoy CADA punto actual (se trasladan con el punto si este se mueve)
dotacion = pd.DataFrame({
    "tipo": ["PC_3m3", "PL_3m3", "VI_2m3", "ME_1m3", "CL_1m3"],
    "cantidad [cont/punto]": [1, 1, 1, 1, 1],
})

# ---------------------------------------------------------------------------
# Generación y estacionalidad
# ---------------------------------------------------------------------------
gen_base = {"papel_carton": 0.035, "plastico": 0.025, "vidrio": 0.030, "metal": 0.006, "carton_liquidos": 0.003}
generacion = pd.DataFrame(
    [(z, mat, round(g * rng.uniform(0.8, 1.2), 4)) for z in sectores["sector"] for mat, g in gen_base.items()],
    columns=["sector", "material", "generacion [ton/hab/año]"],
)

# Año de 52 semanas con 12 de verano un 20% más altas: 12*sv + 40*sr = 1, sv = 1.2*sr.
sr = 1 / (12 * 1.2 + 40)
sv = 1.2 * sr
semanas = pd.DataFrame({
    "semana": range(1, 7),
    "temporada": ["verano", "verano", "resto", "resto", "resto", "resto"],
    "fraccion_generacion [-]": [round(sv, 5)] * 2 + [round(sr, 5)] * 4,
})

# ---------------------------------------------------------------------------
# Atractivos para el modelo de elección (logit)
#   atractivo = exp(-beta * distancia) si distancia <= dmax, 0 si no
#   (beta y dmax NO entran al modelo: se usan solo aquí, en la metodología)
# ---------------------------------------------------------------------------
beta, dmax, circuidad = 0.6, 6.0, 1.3


def distancia(x1, y1, x2, y2):
    return circuidad * np.hypot(x1 - x2, y1 - y2)


filas = []
for _, z in sectores.iterrows():
    for _, s in sitios.iterrows():
        d = distancia(z["x [km]"], z["y [km]"], s["x [km]"], s["y [km]"])
        if d <= dmax:
            filas.append((z["sector"], s["sitio"], round(float(np.exp(-beta * d)), 4)))
atractivo_sitios = pd.DataFrame(filas, columns=["sector", "sitio", "atractivo [-]"])

# Alternativas de reciclaje de terceros y los materiales que reciben
alt_coords = {"A1": (1.0, 6.0), "A2": (5.0, 8.5), "A3": (3.0, 2.5), "A4": (7.0, 1.0)}
alternativas = pd.DataFrame(
    [("A1", "vidrio"), ("A2", "vidrio"), ("A2", "plastico"), ("A3", "papel_carton"),
     ("A3", "plastico"), ("A3", "metal"), ("A4", "vidrio")],
    columns=["alternativa", "material"],
)
filas = []
for _, z in sectores.iterrows():
    for a, (ax, ay) in alt_coords.items():
        d = distancia(z["x [km]"], z["y [km]"], ax, ay)
        if d <= dmax:
            filas.append((z["sector"], a, round(float(np.exp(-beta * d)), 4)))
atractivo_alt = pd.DataFrame(filas, columns=["sector", "alternativa", "atractivo [-]"])

# Atractivo de "no reciclar en ninguna parte": se calibra para que con los puntos actuales
# el modelo reproduzca las toneladas observadas (en la instancia real, tarea de Gabo).
sectores["atractivo_no_reciclar [-]"] = 15.0

# ---------------------------------------------------------------------------
# Camiones y costos
# ---------------------------------------------------------------------------
camiones = pd.DataFrame({
    "camion": ["H1", "H2"],
    "capacidad [ton/recorrido]": [3.0, 3.0],
    "costo_recorrido [CLP/recorrido]": [150000, 150000],
})

costos = pd.DataFrame([
    ("costo_habilitacion", 1200000, "CLP por sitio nuevo habilitado (anualizado)"),
    ("costo_traslado_contenedor", 40000, "CLP por contenedor trasladado"),
    ("costo_parada", 20000, "CLP por parada de camión"),
    ("presupuesto", 6500000, "CLP para el horizonte"),
], columns=["parametro", "valor", "unidad"])

coordenadas = pd.concat([
    sectores[["sector", "x [km]", "y [km]"]].rename(columns={"sector": "elemento"}).assign(tipo="sector"),
    sitios[["sitio", "x [km]", "y [km]"]].rename(columns={"sitio": "elemento"}).assign(tipo="sitio"),
    pd.DataFrame([(a, x, y) for a, (x, y) in alt_coords.items()],
                 columns=["elemento", "x [km]", "y [km]"]).assign(tipo="alternativa"),
])[["elemento", "tipo", "x [km]", "y [km]"]]

leeme = pd.DataFrame([
    ("Sectores", "Un sector por fila (zona censal). macrozona: distrito al que pertenece (cada sector en una sola). atractivo_no_reciclar: se calibra con las toneladas 2023."),
    ("Sitios", "Ubicaciones candidatas (incluye las actuales). macrozona: dónde está el sitio. superficie: espacio para contenedores."),
    ("PuntosActuales", "Los puntos limpios que existen hoy y el sitio donde están."),
    ("Materiales", "Las 5 categorías del DS 12."),
    ("TiposContenedor", "Cada tipo recibe un solo material. capacidad en toneladas (volumen x densidad aparente del material)."),
    ("DotacionActual", "Dotación estándar: contenedores que tiene hoy cada punto actual (igual para todos). Si el punto se mueve, se trasladan con él."),
    ("Generacion", "Generación anual por habitante de cada material en cada sector."),
    ("Semanas", "Una fila por semana del horizonte. fraccion_generacion: parte de la generación anual que ocurre esa semana. temporada solo se usa para gráficos."),
    ("AtractivoSitios", "Solo pares sector-sitio dentro de la distancia máxima; el resto se asume 0."),
    ("Alternativas", "Una fila por cada material que recibe cada alternativa de terceros."),
    ("AtractivoAlternativas", "Atractivo de cada alternativa para cada sector (pares fuera de distancia se omiten)."),
    ("Camiones", "Camiones asignados a la red de puntos limpios (no los domiciliarios)."),
    ("Costos", "Parámetros escalares. No cambiar los nombres de la columna parametro."),
    ("Coordenadas", "Solo para mapas; el modelo no las usa."),
    ("AVISO", "TODOS LOS DATOS DE ESTE ARCHIVO SON INVENTADOS. Solo sirven de plantilla y para probar el código."),
], columns=["hoja", "descripcion"])

os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
with pd.ExcelWriter(SALIDA) as w:
    leeme.to_excel(w, sheet_name="LEEME", index=False)
    sectores[["sector", "macrozona", "poblacion [hab]", "atractivo_no_reciclar [-]"]].to_excel(w, sheet_name="Sectores", index=False)
    sitios[["sitio", "macrozona", "superficie [m2]"]].to_excel(w, sheet_name="Sitios", index=False)
    puntos_actuales.to_excel(w, sheet_name="PuntosActuales", index=False)
    materiales.to_excel(w, sheet_name="Materiales", index=False)
    tipos.to_excel(w, sheet_name="TiposContenedor", index=False)
    dotacion.to_excel(w, sheet_name="DotacionActual", index=False)
    generacion.to_excel(w, sheet_name="Generacion", index=False)
    semanas.to_excel(w, sheet_name="Semanas", index=False)
    atractivo_sitios.to_excel(w, sheet_name="AtractivoSitios", index=False)
    alternativas.to_excel(w, sheet_name="Alternativas", index=False)
    atractivo_alt.to_excel(w, sheet_name="AtractivoAlternativas", index=False)
    camiones.to_excel(w, sheet_name="Camiones", index=False)
    costos.to_excel(w, sheet_name="Costos", index=False)
    coordenadas.to_excel(w, sheet_name="Coordenadas", index=False)

print(f"Instancia de prueba escrita en: {SALIDA}")
