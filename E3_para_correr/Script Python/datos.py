import pandas as pd

#lee la instancia y guarda cada conjunto y parametro con el mismo nombre que tiene en el informe (seccion 5)

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
    d["I"] = list(sectores["sector"])                        #sectores censales
    d["N"] = list(sitios["sitio"])                           #ubicaciones candidatas
    d["P"] = list(puntos["punto"])                           #puntos limpios existentes
    d["M"] = list(materiales["material"])                    #materiales
    d["C"] = list(tipos["tipo"])                             #tipos de contenedores nuevos
    d["H"] = list(camiones["camion"])                        #tipos de camion
    d["T"] = list(semanas["semana"])                         #semanas
    d["K"] = list(sitios["macrozona"].unique())              #macrozonas
    d["O"] = list(alternativas["alternativa"].unique())      #alternativas externas

    #subconjuntos
    d["N_k"] = {k: list(sitios[sitios["macrozona"] == k]["sitio"]) for k in d["K"]}             #ubicaciones de la macrozona k
    d["C_m"] = {m: list(tipos[tipos["material"] == m]["tipo"]) for m in d["M"]}                  #contenedores que reciben el material m
    d["O_m"] = {m: list(alternativas[alternativas["material"] == m]["alternativa"]) for m in d["M"]}  #alternativas que reciben el material m

    #datos auxiliares que no son parametros del modelo, sirven para construir otros o para exportar los resultados
    sitio_actual = dict(zip(puntos["punto"], puntos["sitio_actual"]))                  #sitio donde opera hoy cada punto
    d["sitio_actual"] = sitio_actual
    d["nombre"] = dict(zip(puntos["punto"], puntos["nombre_sitio_actual"]))            #nombre municipal de cada punto
    d["material_de"] = dict(zip(tipos["tipo"], tipos["material"]))                     #material que recibe cada tipo de contenedor

    #parametros, con el nombre del informe
    d["nu"] = dict(zip(sectores["sector"], sectores["poblacion [hab]"]))                                      #nu_i poblacion [hab]
    d["g"] = {(i, m): g for i, m, g in zip(generacion["sector"], generacion["material"],
                                            generacion["generacion [ton/hab/año]"])}                           #g_im generacion [ton/(hab*año)]
    d["sigma"] = dict(zip(semanas["semana"], semanas["fraccion_generacion [-]"]))                             #sigma_t fraccion semanal [-]
    d["u"] = {(i, n): u for i, n, u in zip(atr_sitios["sector"], atr_sitios["sitio"], atr_sitios["atractivo [-]"])}   #u_in atractivo de la ubicacion [-]
    d["A"] = list(d["u"].keys())                                                                              #conjunto A, pares sector-ubicacion dentro de la distancia maxima
    d["psi"] = {(i, o): u for i, o, u in zip(atr_alt["sector"], atr_alt["alternativa"], atr_alt["atractivo [-]"])}    #psi_io atractivo de la alternativa [-]
    d["phi_N"] = dict(zip(materiales["material"], materiales["atractivo_no_reciclar [-]"]))                   #phi^N_m atractivo de no reciclar [-]
    d["iota"] = {(p, n): 1 if sitio_actual[p] == n else 0 for p in d["P"] for n in d["N"]}                    #iota_pn vale 1 si el punto p opera hoy en n [-]

    #contenedores existentes de cada punto (DotacionActual)
    punto_de = dict(zip(puntos["nombre_sitio_actual"], puntos["punto"]))
    filas = list(zip([punto_de[nombre] for nombre in dotacion["punto"]], dotacion["material"], dotacion["tipo_existente"],
                     dotacion["cantidad [cont/punto]"], dotacion["capacidad_util [ton/cont]"], dotacion["superficie [m2/cont]"]))
    d["tipo_exist"] = {(p, m): tipo for p, m, tipo, n, cap, area in filas}                                    #dato auxiliar para exportar
    d["zeta_E"] = {(p, m): n for p, m, tipo, n, cap, area in filas}                                          #zeta^E_pm contenedores existentes [cont]
    d["kappa_E"] = {(p, m): n * cap for p, m, tipo, n, cap, area in filas}                                   #kappa^E_pm capacidad existente [ton]
    d["a_E"] = {p: sum(n * area for q, m, tipo, n, cap, area in filas if q == p) for p in d["P"]}             #a^E_p superficie existente [m2]

    d["theta"] = dict(zip(tipos["tipo"], tipos["capacidad [ton/cont]"]))                  #theta_c capacidad de un contenedor nuevo [ton/cont]
    d["alpha"] = dict(zip(tipos["tipo"], tipos["superficie [m2/cont]"]))                  #alpha_c superficie de un contenedor nuevo [m2/cont]
    d["mu"] = dict(zip(sitios["sitio"], sitios["superficie [m2]"]))                       #mu_n superficie disponible [m2]
    d["lambda"] = dict(zip(camiones["camion"], camiones["capacidad [ton/recorrido]"]))    #lambda_h capacidad en masa [ton/recorrido]
    d["omega"] = dict(zip(camiones["camion"], camiones["volumen [m3/recorrido]"]))        #omega_h capacidad en volumen [m3/recorrido]
    d["delta"] = dict(zip(materiales["material"], materiales["densidad [ton/m3]"]))       #delta_m densidad aparente [ton/m3]
    d["gamma_C"] = dict(zip(tipos["tipo"], tipos["costo_compra [CLP/cont]"]))             #gamma^C_c costo de compra [CLP/cont]
    d["rho_M"] = dict(zip(tipos["tipo"], tipos["costo_mantencion [CLP/cont/año]"]))       #rho^M_c costo de mantencion [CLP/(cont*año)]
    d["gamma_R"] = dict(zip(camiones["camion"], camiones["costo_recorrido [CLP/recorrido]"]))  #gamma^R_h costo de un recorrido [CLP/recorrido]

    valores = dict(zip(costos["parametro"], costos["valor"]))
    d["gamma_H"] = valores["cH"]      #gamma^H costo de habilitacion por traslado [CLP/traslado]
    d["gamma_V"] = valores["cP"]      #gamma^V costo de cada parada [CLP/parada]
    d["j"] = valores["j"]             #j recorridos maximos por camion y semana
    d["b"] = valores["B"]             #b presupuesto anual [CLP]

    return d
