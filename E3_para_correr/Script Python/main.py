import os #es buil_in de python no hay que instalarla
import pandas as pd
import gurobipy as gp
from gurobipy import GRB
from datos import leer_instancia
from exportar import exportar_resultados

CARPETA_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETA_INSTANCIAS = os.path.join(CARPETA_RAIZ, "Instancias Excel")
CARPETA_SALIDA = os.path.join(CARPETA_RAIZ, "Análisis de Excels")
ARCHIVO_INSTANCIA = "instancia21oct.xlsx"

#segundos maximos de cada etapa, la 1 maximiza toneladas y la 2 baja el costo
#suman 30 min en total, el caso actual tiene menos tiempo porque las ubicaciones ya estan fijas y es mas facil
TIEMPOS = {"optimo": (18 * 60, 4 * 60),
           "ubicaciones_actuales": (6 * 60, 2 * 60)}
GAP = 0.005                #para cuando esta a menos de 0,5% del optimo
SEMILLA = 0                #para obtener los mismos resultados
HILOS = 4                  #con cuantos nucleos se va a resolver
MILLON = 1e6               #los costos van en millones para que gurobi no tenga problemas numericos

def construir_modelo(d, fijar_ubicaciones_actuales=False):
    I, N, P, M, C, H, T, K = d["I"], d["N"], d["P"], d["M"], d["C"], d["H"], d["T"], d["K"]

    pares = list(d["u_sitio"].keys())   #pares sector sitio que estan dentro de la distancia maxima
    #atractivo de no llevar el material m a ningun punto limpio, o sea no reciclar o usar una alternativa
    u0 = {(i, m): d["u_no"][m] + sum(d["u_alt"].get((i, o), 0) for o in d["O_m"][m]) for i in I for m in M}

    mod = gp.Model("puntos_limpios")

    #variables
    z = mod.addVars(P, N, vtype=GRB.BINARY, name="z")         #binaria 1 si el punto actual p queda operando en el sitio n 0 eoc
    y = mod.addVars(N, vtype=GRB.BINARY, name="y")            #binaria 1 si hay un punto limpio operando en n 0 eoc
    w = mod.addVars(N, C, vtype=GRB.INTEGER, name="w")        #cantidad de contenedores nuevos de tipo c en n
    q = mod.addVars([(i, n, m) for (i, n) in pares for m in M], ub=1, name="q") #fraccion del material m del sector i que llega a n
    q0 = mod.addVars(I, M, ub=1, name="q0")                   #fraccion del material m del sector i que no llega a ningun punto limpio
    r = mod.addVars(N, M, T, name="r")                        #material m recibido en n en la semana t
    s = mod.addVars(N, M, T, name="s")                        #material m almacenado en n al cierre de la semana t
    e = mod.addVars(H, N, M, T, name="e")                     #material m retirado desde n por el camion h en la semana t
    v = mod.addVars(H, N, T, vtype=GRB.BINARY, name="v")      #binaria 1 si el camion h para en n en la semana t 0 eoc
    o = mod.addVars(H, T, vtype=GRB.BINARY, name="o")         #binaria 1 si el camion h se ocupa en la semana t 0 eoc

    #capacidad de cada sitio para el material m, suma los contenedores nuevos y los que trae el punto p si queda en n
    capacidad = {(n, m): gp.quicksum(d["cap_cont"][c] * w[n, c] for c in d["C_m"][m])
                         + gp.quicksum(d["cap_exist"][p, m] * z[p, n] for p in P) for n in N for m in M}

    #restricciones
    #R1 cada punto actual queda en un solo sitio, el mismo de hoy o uno nuevo
    mod.addConstrs((z.sum(p, "*") == 1 for p in P), name="R1")
    #R2 cada sitio recibe a lo mas un punto y opera solo si recibe uno
    mod.addConstrs((z.sum("*", n) == y[n] for n in N), name="R2")
    #R3 al menos un punto limpio por macrozona
    #en el caso actual no se pide porque hoy no hay puntos en sur oriente y seria infactible
    if not fijar_ubicaciones_actuales:
        mod.addConstrs((gp.quicksum(y[n] for n in d["N_k"][k]) >= 1 for k in K), name="R3")

    #R4 a R7 son la eleccion de los vecinos con el logit linealizado
    #R4 el material de cada sector se reparte entre los puntos limpios y no llevarlo a ninguno
    mod.addConstrs((gp.quicksum(q[i, n, m] for (j, n) in pares if j == i) + q0[i, m] == 1 for i in I for m in M), name="R4")
    #R5 y R6 si el sitio opera la fraccion que recibe es proporcional a su atractivo
    mod.addConstrs((q[i, n, m] <= d["u_sitio"][i, n] / u0[i, m] * q0[i, m] for (i, n) in pares for m in M), name="R5")
    mod.addConstrs((q[i, n, m] >= d["u_sitio"][i, n] / u0[i, m] * (q0[i, m] - (1 - y[n])) for (i, n) in pares for m in M), name="R6")
    #R7 un sitio sin punto limpio no recibe nada
    mod.addConstrs((q[i, n, m] <= d["u_sitio"][i, n] / (d["u_sitio"][i, n] + u0[i, m]) * y[n] for (i, n) in pares for m in M), name="R7")
    #R8 lo recibido no puede ser mas de lo que generan los sectores que eligen ese punto
    mod.addConstrs((r[n, m, t] <= gp.quicksum(d["poblacion"][i] * d["gen"][i, m] * d["sigma"][t] * q[i, n, m] for (i, j) in pares if j == n) for n in N for m in M for t in T), name="R8")

    for n in N:
        for m in M:
            for k, t in enumerate(T):
                anterior = s[n, m, T[k - 1]] if k > 0 else 0   #los puntos parten vacios
                #R9 lo que estaba guardado mas lo recibido tiene que caber en los contenedores
                mod.addConstr(anterior + r[n, m, t] <= capacidad[n, m], name=f"R9[{n},{m},{t}]")
                #R10 balance de lo almacenado
                mod.addConstr(s[n, m, t] == anterior + r[n, m, t] - e.sum("*", n, m, t), name=f"R10[{n},{m},{t}]")

    #R11 los contenedores nuevos y existentes caben en el sitio, y si no opera no puede tener contenedores
    mod.addConstrs((gp.quicksum(d["area_cont"][c] * w[n, c] for c in C)
                    + gp.quicksum(d["area_exist"][p] * z[p, n] for p in P) <= d["superficie"][n] * y[n] for n in N), name="R11")
    #R12 al menos un contenedor por material en cada punto que opera
    mod.addConstrs((gp.quicksum(w[n, c] for c in d["C_m"][m])
                    + gp.quicksum(d["n_exist"][p, m] * z[p, n] for p in P) >= y[n] for n in N for m in M), name="R12")
    #R13 lo que retira un camion en la semana no supera su capacidad
    mod.addConstrs((e.sum(h, "*", "*", t) <= d["cap_camion"][h] * o[h, t] for h in H for t in T), name="R13")
    #R14 un camion solo retira donde para
    mod.addConstrs((e.sum(h, n, "*", t) <= d["cap_camion"][h] * v[h, n, t] for h in H for n in N for t in T), name="R14")
    #R15 un camion solo para si sale esa semana
    mod.addConstrs((v[h, n, t] <= o[h, t] for h in H for n in N for t in T), name="R15")
    #R16 un camion solo para en sitios con punto limpio
    mod.addConstrs((v[h, n, t] <= y[n] for h in H for n in N for t in T), name="R16")

    #R17 presupuesto anual en millones
    #cH ya incluye trasladar los contenedores y el costo del recorrido incluye las paradas
    traslados = [(p, n) for p in P for n in N if n != d["sitio_actual"][p]] #el punto p queda en un sitio distinto al de hoy
    costos = {
        "Habilitación de sitios nuevos": d["costo_habilitacion"] / MILLON * gp.quicksum(z[p, n] for (p, n) in traslados),
        "Compra de contenedores nuevos": gp.quicksum(d["costo_compra"][c] / MILLON * w[n, c] for n in N for c in C),
        "Mantención de contenedores nuevos": gp.quicksum(d["costo_mant"][c] / MILLON * w[n, c] for n in N for c in C),
        "Recorridos de camiones": gp.quicksum(d["costo_recorrido"][h] / MILLON * o[h, t] for h in H for t in T),
    }
    costo_total = gp.quicksum(costos.values())
    mod.addConstr(costo_total <= d["presupuesto"] / MILLON, name="R17")

    #R18 maximo F visitas por semana sumando todos los camiones
    mod.addConstrs((v.sum("*", "*", t) <= d["F"] for t in T), name="R18")

    #caso actual, cada punto se queda en el sitio donde esta hoy
    if fijar_ubicaciones_actuales:
        for p in P:
            z[p, d["sitio_actual"][p]].LB = 1

    #funcion objetivo, maximizar el material retirado
    mod.setObjective(e.sum(), GRB.MAXIMIZE)

    variables = {"z": z, "y": y, "w": w, "q": q, "r": r, "s": s, "e": e, "v": v, "o": o, "capacidad": capacidad, "pares": pares}
    return mod, variables, costos, costo_total


#se resuelve en dos etapas, la 1 maximiza las toneladas y la 2 baja el costo sin perder esas toneladas
#asi no compra contenedores ni hace recorridos que no sirven
def resolver(mod, variables, costo_total, nombre):
    tiempo_etapa_1, tiempo_etapa_2 = TIEMPOS[nombre]   #segundos que tiene cada etapa en este escenario
    mod.Params.Seed = SEMILLA
    mod.Params.Threads = HILOS
    mod.Params.MIPGap = GAP
    mod.update()   #gurobi agrega las variables y restricciones recien aca, sin esto el tamano sale 0
    #guardar el tamano del modelo para la tabla del informe, a las enteras se le restan las binarias porque gurobi las cuenta como enteras
    tamano = {"variables": mod.NumVars, "binarias": mod.NumBinVars,
              "enteras": mod.NumIntVars - mod.NumBinVars, "restricciones": mod.NumConstrs}

    #etapa 1, maximiza el material retirado que es el objetivo que se puso en construir_modelo
    mod.Params.TimeLimit = tiempo_etapa_1
    mod.optimize()
    if mod.SolCount == 0:   #no encontro ninguna solucion factible, ese escenario no se exporta
        print(f"[{nombre}] El modelo no tiene solución.")
        return None

    #se guardan los resultados de la etapa 1 ahora porque en la etapa 2 cambia el objetivo y ObjVal pasa a ser el costo
    etapa_1 = {
        "estado": f"Óptimo (gap <= {100 * GAP:g} %)" if mod.Status == GRB.OPTIMAL else "Límite de tiempo",   #optimo si llego al gap, si no se acabo el tiempo
        "toneladas": mod.ObjVal,        #toneladas retiradas en la mejor solucion
        "cota": mod.ObjBound,           #lo maximo que se podria retirar segun gurobi
        "gap [%]": 100 * mod.MIPGap,    #diferencia entre las toneladas y la cota
        "tiempo [s]": mod.Runtime,
        **tamano,                       #agrega variables, binarias, enteras y restricciones al mismo diccionario
    }

    #etapa 2, parte desde la solucion de la etapa 1 y no puede perder toneladas
    for x in mod.getVars():
        x.Start = x.X   #le pasa a gurobi la solucion de la etapa 1 como punto de partida
    #tiene que retirar al menos lo mismo que en la etapa 1, el 1e-4 es un margen chico por redondeo
    mod.addConstr(variables["e"].sum() >= etapa_1["toneladas"] - 1e-4, name="mantener_toneladas")
    mod.setObjective(costo_total, GRB.MINIMIZE)   #ahora minimiza el costo
    mod.Params.TimeLimit = tiempo_etapa_2
    mod.optimize()
    etapa_1["tiempo [s]"] += mod.Runtime   #suma el tiempo de la etapa 2 al total

    return etapa_1   #el modelo queda con la solucion de la etapa 2 y esa es la que se exporta

def main():
    os.makedirs(CARPETA_SALIDA, exist_ok=True)
    d = leer_instancia(os.path.join(CARPETA_INSTANCIAS, ARCHIVO_INSTANCIA))

    escenarios = [("optimo", False),                #el modelo decide donde queda cada punto
                  ("ubicaciones_actuales", True)]   #los puntos se quedan donde estan hoy, sirve para comparar
    resumenes = []
    for nombre, fijar in escenarios:
        mod, variables, costos, costo_total = construir_modelo(d, fijar)
        etapa_1 = resolver(mod, variables, costo_total, nombre)
        if etapa_1 is not None:
            resumen = exportar_resultados(d, mod, variables, costos, etapa_1, nombre,
                                          os.path.join(CARPETA_SALIDA, f"resultados_{nombre}.xlsx"))
            resumenes.append(resumen)

    if resumenes:
        tabla = pd.DataFrame(resumenes)
        tabla.to_excel(os.path.join(CARPETA_SALIDA, "comparacion_escenarios.xlsx"), index=False)
        print("\nResumen:")
        print(tabla[["escenario", "estado", "material_recuperado [ton]", "gap [%]", "costo_total [CLP]"]].to_string(index=False))

if __name__ == "__main__":
    main()
