import os #es buil_in de python no hay que instalarla
import pandas as pd
import gurobipy as gp
from gurobipy import GRB
from datos import leer_instancia
from exportar import exportar_resultados

CARPETA_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETA_INSTANCIAS = os.path.join(CARPETA_RAIZ, "Instancias Excel")
CARPETA_SALIDA = os.path.join(CARPETA_RAIZ, "Análisis de Excels")
ARCHIVO_INSTANCIA = "instancia_prueba.xlsx"   #cambiar cuando tenga los datos reales

TIEMPO_ETAPA_1 = 25 * 60   #25 minutos para maximizar lo recolectado
TIEMPO_ETAPA_2 = 5 * 60    #5 para elegir la opcion de menor costo
SEMILLA = 0                #para obtener los mismos resultados
HILOS = 4                  #con cuantos nucleos se va a resolver
MILLON = 1e6               

def construir_modelo(d, fijar_ubicaciones_actuales=False):
    I, N, P, M, C, H, T, K = d["I"], d["N"], d["P"], d["M"], d["C"], d["H"], d["T"], d["K"]

    pares = list(d["u_sitio"].keys())   #pares (sector, sitio) dentro de la distancia máxima
    #atractivo de no usar la red para el material m
    u0 = {(i, m): d["u_no"][i] + sum(d["u_alt"].get((i, o), 0) for o in d["O_m"][m]) for i in I for m in M}

    mod = gp.Model("puntos_limpios")

    #Variables
    z = mod.addVars(P, N, vtype=GRB.BINARY, name="z")         #binaria 1 si punto actual p queda operando en el sitio n 0 eoc
    y = mod.addVars(N, vtype=GRB.BINARY, name="y")            #binaria 1 si hay un punto limpio operando en n 0 eoc
    w = mod.addVars(N, C, vtype=GRB.INTEGER, name="w")        #cantidad de contenedores nuevos de tipo c en n
    q = mod.addVars([(i, n, m) for (i, n) in pares for m in M], ub=1, name="q") #fracción del material m del sector i que llega a n
    q0 = mod.addVars(I, M, ub=1, name="q0")                   #fracción del material m del sector i que no llega a ningun punto limpio
    r = mod.addVars(N, M, T, name="r")                        #material m recibido en n en la semana t
    s = mod.addVars(N, M, T, name="s")                        #material m almacenado en n al cierre de la semana t 
    e = mod.addVars(H, N, M, T, name="e")                     #material m retirado desde n por el camión h en la semana t
    v = mod.addVars(H, N, T, vtype=GRB.BINARY, name="v")      #binaria 1 si el camión h para en n en la semana t 0 eoc
    o = mod.addVars(H, T, vtype=GRB.BINARY, name="o")         #binaria 1 si el camión h se ocupa en la semana t 0 eoc

    #z_np vale 0 si no queda operando en ese punto, 1 si es que si por lo que se le suman los contenedores del punto anterior a los comprados para esa ubicacion n
    cont = {(n, c): w[n, c] + gp.quicksum(d["cont_actual"][p, c] * z[p, n] for p in P) for n in N for c in C} 

    #Restricciones
    # R1: cada punto actual queda operando en exactamente un sitio (se mantiene o se traslada)
    mod.addConstrs((z.sum(p, "*") == 1 for p in P), name="R1") 
    # R2: un sitio recibe a lo más un punto, y opera si recibe uno
    mod.addConstrs((z.sum("*", n) == y[n] for n in N), name="R2")
    # R3: al menos un punto limpio en cada macrozona (equidad)
    mod.addConstrs((gp.quicksum(y[n] for n in d["N_k"][k]) >= 1 for k in K), name="R3")

    # R4-R7: elección de los vecinos (logit linealizado)
    # R4: el material de cada sector se reparte entre los puntos y la opción externa
    mod.addConstrs((gp.quicksum(q[i, n, m] for (j, n) in pares if j == i) + q0[i, m] == 1 for i in I for m in M), name="R4")
    # R5 y R6: si el sitio opera, la fracción es proporcional a su atractivo (logit)
    mod.addConstrs((q[i, n, m] <= d["u_sitio"][i, n] / u0[i, m] * q0[i, m] for (i, n) in pares for m in M), name="R5")
    #R6
    mod.addConstrs((q[i, n, m] >= d["u_sitio"][i, n] / u0[i, m] * (q0[i, m] - (1 - y[n])) for (i, n) in pares for m in M), name="R6")
    # R7: un sitio sin punto limpio no recibe nada
    mod.addConstrs((q[i, n, m] <= d["u_sitio"][i, n] / (d["u_sitio"][i, n] + u0[i, m]) * y[n] for (i, n) in pares for m in M), name="R7")
    # R8: lo recibido no supera lo que generan los sectores que eligen ese punto
    mod.addConstrs((r[n, m, t] <= gp.quicksum(d["poblacion"][i] * d["gen"][i, m] * d["sigma"][t] * q[i, n, m] for (i, j) in pares if j == n) for n in N for m in M for t in T), name="R8")

    for n in N:
        for m in M:
            capacidad = gp.quicksum(d["cap_cont"][c] * cont[n, c] for c in d["C_m"][m])
            for k, t in enumerate(T):
                anterior = s[n, m, T[k - 1]] if k > 0 else 0   # los puntos parten vacíos
                # R9: lo almacenado más lo recibido cabe en los contenedores
                mod.addConstr(anterior + r[n, m, t] <= capacidad, name=f"R9[{n},{m},{t}]")
                # R10: balance de material almacenado
                mod.addConstr(s[n, m, t] == anterior + r[n, m, t] - e.sum("*", n, m, t), name=f"R10[{n},{m},{t}]")

    # R11: los contenedores caben en la superficie del sitio (y solo hay contenedores si opera)
    mod.addConstrs((gp.quicksum(d["area_cont"][c] * cont[n, c] for c in C) <= d["superficie"][n] * y[n] for n in N), name="R11")
    # R12: al menos un contenedor por material en cada punto que opera
    mod.addConstrs((gp.quicksum(cont[n, c] for c in d["C_m"][m]) >= y[n] for n in N for m in M), name="R12")
    # R13: lo que retira un camión en su recorrido no supera su capacidad
    mod.addConstrs((e.sum(h, "*", "*", t) <= d["cap_camion"][h] * o[h, t] for h in H for t in T), name="R13")
    # R14: un camión solo retira donde para
    mod.addConstrs((e.sum(h, n, "*", t) <= d["cap_camion"][h] * v[h, n, t] for h in H for n in N for t in T), name="R14")
    # R15: un camión solo para si hace recorrido esa semana
    mod.addConstrs((v[h, n, t] <= o[h, t] for h in H for n in N for t in T), name="R15")
    # R16: un camión solo para en sitios con punto limpio
    mod.addConstrs((v[h, n, t] <= y[n] for h in H for n in N for t in T), name="R16")

    # R17: presupuesto anual (en millones de CLP)
    traslados = [(p, n) for p in P for n in N if n != d["sitio_actual"][p]]
    costos = {
        "Habilitación de sitios nuevos": d["costo_habilitacion"] / MILLON * gp.quicksum(z[p, n] for (p, n) in traslados),
        "Traslado de contenedores": d["costo_traslado"] / MILLON * gp.quicksum(
            sum(d["cont_actual"][p, c] for c in C) * z[p, n] for (p, n) in traslados),
        "Compra de contenedores": gp.quicksum(d["costo_compra"][c] / MILLON * w[n, c] for n in N for c in C),
        "Mantención de contenedores": gp.quicksum(d["costo_mant"][c] / MILLON * cont[n, c] for n in N for c in C),
        "Recorridos de camiones": gp.quicksum(d["costo_recorrido"][h] / MILLON * o[h, t] for h in H for t in T),
        "Paradas de camiones": d["costo_parada"] / MILLON * v.sum(),
    }
    costo_total = gp.quicksum(costos.values())
    mod.addConstr(costo_total <= d["presupuesto"] / MILLON, name="R17")

    # Escenario base: los puntos se quedan donde están hoy
    if fijar_ubicaciones_actuales:
        for p in P:
            z[p, d["sitio_actual"][p]].LB = 1

    # Técnico (no es parte del modelo del informe): si los camiones son iguales, se usan en orden.
    # Evita que Gurobi revise soluciones idénticas con los camiones intercambiados.
    if len(set(d["cap_camion"].values())) == 1 and len(set(d["costo_recorrido"].values())) == 1:
        mod.addConstrs((o[H[a], t] >= o[H[a + 1], t] for a in range(len(H) - 1) for t in T), name="simetria")

    # Objetivo principal: maximizar el material retirado
    mod.setObjective(e.sum(), GRB.MAXIMIZE)

    variables = {"z": z, "y": y, "w": w, "q": q, "r": r, "s": s, "e": e, "v": v, "o": o, "cont": cont, "pares": pares}
    return mod, variables, costos, costo_total


# ---------------------------------------------------------------------------
# Resolución en dos etapas
#   1) maximizar las toneladas retiradas
#   2) sin perder esas toneladas, minimizar el costo (evita comprar contenedores o hacer recorridos de más)
# ---------------------------------------------------------------------------
def resolver(mod, variables, costo_total, nombre):
    log = []   # Gurobi no puede escribir archivos en rutas con tildes en Windows, así que el log lo guarda Python

    def guardar_log(modelo, donde):
        if donde == GRB.Callback.MESSAGE:
            log.append(modelo.cbGet(GRB.Callback.MSG_STRING))

    mod.Params.Seed = SEMILLA
    mod.Params.Threads = HILOS

    # Etapa 1
    mod.Params.TimeLimit = TIEMPO_ETAPA_1
    mod.optimize(guardar_log)

    if mod.SolCount == 0:
        print(f"[{nombre}] El modelo no tiene solución.")
        if mod.Status in (GRB.INFEASIBLE, GRB.INF_OR_UNBD):
            mod.computeIIS()
            conflicto = [c.ConstrName for c in mod.getConstrs() if c.IISConstr]
            with open(os.path.join(CARPETA_SALIDA, f"conflicto_{nombre}.txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(conflicto))
            print(f"[{nombre}] Las restricciones en conflicto quedaron en conflicto_{nombre}.txt")
        return None

    etapa_1 = {
        "estado": "Óptimo" if mod.Status == GRB.OPTIMAL else "Límite de tiempo",
        "toneladas": mod.ObjVal,
        "cota": mod.ObjBound,
        "gap [%]": 100 * mod.MIPGap,
        "tiempo [s]": mod.Runtime,
    }

    # Etapa 2: se parte desde la solución de la etapa 1 y se exige no perder toneladas
    for x in mod.getVars():
        x.Start = x.X
    mod.addConstr(variables["e"].sum() >= etapa_1["toneladas"] - 1e-4, name="mantener_toneladas")
    mod.setObjective(costo_total, GRB.MINIMIZE)
    mod.Params.TimeLimit = TIEMPO_ETAPA_2
    mod.optimize(guardar_log)
    etapa_1["tiempo [s]"] += mod.Runtime

    with open(os.path.join(CARPETA_SALIDA, f"log_gurobi_{nombre}.txt"), "w", encoding="utf-8") as f:
        f.write("".join(log))
    return etapa_1


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------
def main():
    os.makedirs(CARPETA_SALIDA, exist_ok=True)
    d = leer_instancia(os.path.join(CARPETA_INSTANCIAS, ARCHIVO_INSTANCIA))

    escenarios = [("optimo", False),                # el modelo decide dónde queda cada punto
                  ("ubicaciones_actuales", True)]   # caso base: los puntos quedan donde están hoy
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
