import pandas as pd


def leer_instancia(ruta):
    hojas = pd.read_excel(ruta, sheet_name=None)  # diccionario {nombre de hoja: tabla}

    sectores = hojas["Sectores"]
    sitios = hojas["Sitios"]
    puntos = hojas["PuntosActuales"]
    materiales = hojas["Materiales"]
    tipos = hojas["TiposContenedor"]
    dotacion = hojas["DotacionActual"]
    generacion = hojas["Generacion"]
    semanas = hojas["Semanas"]
    atr_sitios = hojas["AtractivoSitios"]
    alternativas = hojas["Alternativas"]
    atr_alt = hojas["AtractivoAlternativas"]
    camiones = hojas["Camiones"]
    costos = hojas["Costos"]

    d = {}

    #conjuntos
    d["I"] = list(sectores["sector"])                        # sectores
    d["N"] = list(sitios["sitio"])                           # sitios candidatos
    d["P"] = list(puntos["punto"])                           # puntos limpios actuales
    d["M"] = list(materiales["material"])                    # materiales
    d["C"] = list(tipos["tipo"])                             # tipos de contenedor que se pueden comprar
    d["H"] = list(camiones["camion"])                        # camiones
    d["T"] = list(semanas["semana"])                         # semanas
    d["K"] = list(sitios["macrozona"].unique())              # macrozonas
    d["O"] = list(alternativas["alternativa"].unique())      # alternativas

    #subconjuntos
    d["N_k"] = {k: list(sitios[sitios["macrozona"] == k]["sitio"]) for k in d["K"]} #subconjunto de ubicaciones candidatas por macrozona k
    d["C_m"] = {m: list(tipos[tipos["material"] == m]["tipo"]) for m in d["M"]} #subconjunto de tipos de contenedores por cada material m
    d["O_m"] = {m: list(alternativas[alternativas["material"] == m]["alternativa"]) for m in d["M"]} #subconjunto de alternativas por cada material m

    #parámetros
    d["poblacion"] = dict(zip(sectores["sector"], sectores["poblacion [hab]"])) #poblacion por sector
    d["u_no"] = dict(zip(materiales["material"], materiales["atractivo_no_reciclar [-]"])) #atractivo de no reciclar el material m (calibrado, hoja Calibracion)
    d["superficie"] = dict(zip(sitios["sitio"], sitios["superficie [m2]"])) #superficie por ubicacion candidata n
    d["sitio_actual"] = dict(zip(puntos["punto"], puntos["sitio_actual"])) #puntos actuales

    d["cap_cont"] = dict(zip(tipos["tipo"], tipos["capacidad [ton/cont]"])) #capacidad por cada tipo de contenedor c
    d["area_cont"] = dict(zip(tipos["tipo"], tipos["superficie [m2/cont]"])) #superficie que ocupa cada tipo de contenedor c
    d["costo_compra"] = dict(zip(tipos["tipo"], tipos["costo_compra [CLP/cont]"])) #costo de comprar el contenedor c (se paga una vez en el horizonte)
    d["costo_mant"] = dict(zip(tipos["tipo"], tipos["costo_mantencion [CLP/cont/año]"])) #costo anual de mantener un contenedor nuevo c
    d["material_de"] = dict(zip(tipos["tipo"], tipos["material"])) #contenedor que material recibe

    #dotación actual: cada punto tiene sus propios contenedores (tipos existentes, distintos de los que se compran)
    #DotacionActual identifica los puntos por nombre ("Los Toros"), así que se cruza con PuntosActuales
    if "nombre_sitio_actual" in puntos.columns:
        d["nombre"] = dict(zip(puntos["punto"], puntos["nombre_sitio_actual"])) #nombre municipal de cada punto actual
    else:
        d["nombre"] = {p: p for p in d["P"]} #si DotacionActual ya viene con P1..P7 no hace falta el nombre
    punto_de = {nombre: p for p, nombre in d["nombre"].items()}
    sin_cruce = sorted(set(dotacion["punto"]) - set(punto_de))
    if sin_cruce:
        raise ValueError("DotacionActual tiene puntos que no aparecen en PuntosActuales: " + ", ".join(sin_cruce)
                         + ". La columna 'nombre_sitio_actual' de PuntosActuales debe usar exactamente los mismos nombres que DotacionActual.")

    d["dotacion"] = [] #filas de la dotación actual, solo para exportar
    d["n_exist"] = {(p, m): 0 for p in d["P"] for m in d["M"]}     #contenedores existentes del punto p para el material m
    d["cap_exist"] = {(p, m): 0.0 for p in d["P"] for m in d["M"]} #capacidad existente [ton] del punto p para el material m
    d["area_exist"] = {p: 0.0 for p in d["P"]}                     #superficie [m2] que ocupan los contenedores existentes del punto p
    for _, fila in dotacion.iterrows():
        p, m, cantidad = punto_de[fila["punto"]], fila["material"], fila["cantidad [cont/punto]"]
        d["n_exist"][p, m] += cantidad
        d["cap_exist"][p, m] += cantidad * fila["capacidad_util [ton/cont]"]
        d["area_exist"][p] += cantidad * fila["superficie [m2/cont]"]
        d["dotacion"].append({"punto": p, "tipo": fila["tipo_existente"], "material": m, "cantidad [cont]": cantidad,
                              "capacidad [ton]": cantidad * fila["capacidad_util [ton/cont]"]})

    d["gen"] = {(i, m): g for i, m, g in zip(generacion["sector"], generacion["material"], generacion["generacion [ton/hab/año]"])} #generacion por material en cada sector
    d["sigma"] = dict(zip(semanas["semana"], semanas["fraccion_generacion [-]"])) #generación por semana

    #atractivo a reciclar y a las alternativas solo en los pares dentro de la distancia max
    d["u_sitio"] = {(i, n): u for i, n, u in zip(atr_sitios["sector"], atr_sitios["sitio"], atr_sitios["atractivo [-]"])} #atractivo de reciclar desde sector i a ubicacion n
    d["u_alt"] = {(i, o): u for i, o, u in zip(atr_alt["sector"], atr_alt["alternativa"], atr_alt["atractivo [-]"])} #atractivo de usar la alternativa o desde el sector i

    d["cap_camion"] = dict(zip(camiones["camion"], camiones["capacidad [ton/recorrido]"])) #cap por recorrido de cada camion
    d["costo_recorrido"] = dict(zip(camiones["camion"], camiones["costo_recorrido [CLP/recorrido]"])) #costo de cada camión por operar un recorrido (incluye las paradas)

    valores = dict(zip(costos["parametro"], costos["valor"]))
    d["costo_habilitacion"] = valores["cH"] #costo de habilitar una ubicación nueva (incluye el traslado de los contenedores)
    d["presupuesto"] = valores["B"]         #presupuesto anual
    d["F"] = valores["F"]                   #visitas máximas por semana de toda la flota

    revisar_datos(d)
    return d


def revisar_datos(d):
    #avisa con un mensaje claro si falta algún dato, en vez de que Gurobi falle con NaN
    faltan_un = [m for m in d["M"] if pd.isna(d["u_no"][m])]
    if faltan_un:
        raise ValueError(f"Falta el atractivo_no_reciclar de {', '.join(faltan_un)} (hoja Materiales). "
                         "Se calibra en la hoja Calibracion; si está vacío, abrir el Excel y guardarlo desde Excel para que calcule.")
    for nombre, dic in [("gen", d["gen"]), ("u_sitio", d["u_sitio"]), ("u_alt", d["u_alt"]), ("sigma", d["sigma"])]:
        if any(pd.isna(x) for x in dic.values()):
            raise ValueError(f"Hay celdas vacías en el parámetro {nombre}.")
    faltan_gen = [(i, m) for i in d["I"] for m in d["M"] if (i, m) not in d["gen"]]
    if faltan_gen:
        raise ValueError(f"Faltan {len(faltan_gen)} pares sector-material en Generacion, por ejemplo {faltan_gen[0]}.")
