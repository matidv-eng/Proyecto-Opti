import pandas as pd

def leer_instancia(ruta):
    hojas = pd.read_excel(ruta, sheet_name=None)  

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
    d["I"] = list(sectores["sector"])                        
    d["N"] = list(sitios["sitio"])                           
    d["P"] = list(puntos["punto"])                           
    d["M"] = list(materiales["material"])                    
    d["C"] = list(tipos["tipo"])                             
    d["H"] = list(camiones["camion"])                        
    d["T"] = list(semanas["semana"])                         
    d["K"] = list(sitios["macrozona"].unique())              
    d["O"] = list(alternativas["alternativa"].unique())      

    #subconjuntos
    d["N_k"] = {k: list(sitios[sitios["macrozona"] == k]["sitio"]) for k in d["K"]} #subconjunto de ubicaciones candidatas por macrozona k
    d["C_m"] = {m: list(tipos[tipos["material"] == m]["tipo"]) for m in d["M"]} #subconjunto de tipos de contenedores por cada material m
    d["O_m"] = {m: list(alternativas[alternativas["material"] == m]["alternativa"]) for m in d["M"]} #subconjunto de alternativas por cada material m

    #parámetros
    d["poblacion"] = dict(zip(sectores["sector"], sectores["poblacion [hab]"])) #poblacion por sector
    d["u_no"] = dict(zip(materiales["material"], materiales["atractivo_no_reciclar [-]"])) #atractivo de no reciclar el material m
    d["superficie"] = dict(zip(sitios["sitio"], sitios["superficie [m2]"])) #superficie por ubicacion candidata n
    d["sitio_actual"] = dict(zip(puntos["punto"], puntos["sitio_actual"])) #puntos actuales
    d["nombre"] = dict(zip(puntos["punto"], puntos["nombre_sitio_actual"])) #nombre municipal de cada punto actual

    d["cap_cont"] = dict(zip(tipos["tipo"], tipos["capacidad [ton/cont]"])) #capacidad por cada tipo de contenedor c
    d["area_cont"] = dict(zip(tipos["tipo"], tipos["superficie [m2/cont]"])) #superficie que ocupa cada tipo de contenedor c
    d["costo_compra"] = dict(zip(tipos["tipo"], tipos["costo_compra [CLP/cont]"])) #costo de comprar el contenedor c (una vez en el horizonte)
    d["costo_mant"] = dict(zip(tipos["tipo"], tipos["costo_mantencion [CLP/cont/año]"])) #costo de mantener el contenedor c
    d["material_de"] = dict(zip(tipos["tipo"], tipos["material"])) #contenedor que material recibe

    #contenedores que ya tiene cada punto limpio
    punto_de = dict(zip(puntos["nombre_sitio_actual"], puntos["punto"])) #nombre y su numero de punto
    p_dot = [punto_de[nombre] for nombre in dotacion["punto"]]
    filas = list(zip(p_dot, dotacion["material"], dotacion["tipo_existente"], dotacion["cantidad [cont/punto]"],
                     dotacion["capacidad_util [ton/cont]"], dotacion["superficie [m2/cont]"]))
    d["tipo_exist"] = {(p, m): tipo for p, m, tipo, n, cap, area in filas} #tipo de contenedor existente del punto p para el material m
    d["n_exist"] = {(p, m): n for p, m, tipo, n, cap, area in filas} #cantidad de contenedores existentes del punto p para el material m
    d["cap_exist"] = {(p, m): n * cap for p, m, tipo, n, cap, area in filas} #capacidad existente [ton] del punto p para el material m
    d["area_exist"] = {p: sum(n * area for q, m, tipo, n, cap, area in filas if q == p) for p in d["P"]} #superficie [m2] de los contenedores existentes del punto p

    d["gen"] = {(i, m): g for i, m, g in zip(generacion["sector"], generacion["material"], generacion["generacion [ton/hab/año]"])} #generacion por material en cada sector
    d["sigma"] = dict(zip(semanas["semana"], semanas["fraccion_generacion [-]"])) #generación por semana

    #atractivo a reciclar y a las alternativas solo en los pares dentro de la distancia max
    d["u_sitio"] = {(i, n): u for i, n, u in zip(atr_sitios["sector"], atr_sitios["sitio"], atr_sitios["atractivo [-]"])} #atractivo de reciclar desde sector i a ubicacion n
    d["u_alt"] = {(i, o): u for i, o, u in zip(atr_alt["sector"], atr_alt["alternativa"], atr_alt["atractivo [-]"])} #atractivo de usar la alternativa o desde el sector i

    d["cap_camion"] = dict(zip(camiones["camion"], camiones["capacidad [ton/recorrido]"])) #cap por recorrido de cada camion
    d["costo_recorrido"] = dict(zip(camiones["camion"], camiones["costo_recorrido [CLP/recorrido]"])) #costo de cada camion por operar un recorrido

    valores = dict(zip(costos["parametro"], costos["valor"]))
    d["costo_habilitacion"] = valores["cH"] #costo de habilitar una ubicacion nueva (incluye trasladar los contenedores)
    d["presupuesto"] = valores["B"]         #presupuesto anual
    d["F"] = valores["F"]                   #visitas maximas por semana de toda la flota

    return d
