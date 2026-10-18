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
    d["C"] = list(tipos["tipo"])                             # tipos de contenedor
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
    d["u_no"] = dict(zip(sectores["sector"], sectores["atractivo_no_reciclar [-]"])) #atractivo no reciclar en sector i
    d["superficie"] = dict(zip(sitios["sitio"], sitios["superficie [m2]"])) #superficie por ubicacion candidata n
    d["sitio_actual"] = dict(zip(puntos["punto"], puntos["sitio_actual"])) #puntos actuales

    d["cap_cont"] = dict(zip(tipos["tipo"], tipos["capacidad [ton/cont]"])) #capacidad por cada tipo de contenedor c 
    d["area_cont"] = dict(zip(tipos["tipo"], tipos["superficie [m2/cont]"])) #superficie que ocupa cada tipo de contenedor c
    d["costo_compra"] = dict(zip(tipos["tipo"], tipos["costo_compra [CLP/cont/año]"])) #costo de comprar el contenedor c
    d["costo_mant"] = dict(zip(tipos["tipo"], tipos["costo_mantencion [CLP/cont/año]"])) #costo de mantener el contenedor c 
    d["material_de"] = dict(zip(tipos["tipo"], tipos["material"])) #contenedor que material recibe

    #cantidad actual de contenedores por punto limpio
    por_punto = dict(zip(dotacion["tipo"], dotacion["cantidad [cont/punto]"])) 
    d["cont_actual"] = {(p, c): por_punto.get(c, 0) for p in d["P"] for c in d["C"]} #cantidad de contenedores c actualmente en el punto p

    d["gen"] = {(i, m): g for i, m, g in zip(generacion["sector"], generacion["material"], generacion["generacion [ton/hab/año]"])} #generacion por material en cada sector 
    d["sigma"] = dict(zip(semanas["semana"], semanas["fraccion_generacion [-]"])) #generación por semana

    #atractivo a reciclar y a las alternativas solo en los pares dentro de la distancia max
    d["u_sitio"] = {(i, n): u for i, n, u in zip(atr_sitios["sector"], atr_sitios["sitio"], atr_sitios["atractivo [-]"])} #atractivo de reciclar desde sector i a ubicacion n
    d["u_alt"] = {(i, o): u for i, o, u in zip(atr_alt["sector"], atr_alt["alternativa"], atr_alt["atractivo [-]"])} #atractivo de usar la alternativa en el sector i en la ubicacion n

    d["cap_camion"] = dict(zip(camiones["camion"], camiones["capacidad [ton/recorrido]"])) #cap por recorrido de cada camion
    d["costo_recorrido"] = dict(zip(camiones["camion"], camiones["costo_recorrido [CLP/recorrido]"])) #costo de cada camión por operar un recorrido

    valores = dict(zip(costos["parametro"], costos["valor"])) 
    d["costo_habilitacion"] = valores["costo_habilitacion"] #costo de habilitar una ubicación candidata
    d["costo_traslado"] = valores["costo_traslado_contenedor"] #costo de trasladar un contenedor ind a que distancia y que tipo de cont es
    d["costo_parada"] = valores["costo_parada"] #costo del camion de parar en un punto limpio
    d["presupuesto"] = valores["presupuesto"] 

    return d
