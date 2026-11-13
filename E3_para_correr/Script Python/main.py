import os #es buil_in de python no hay que instalarla
import gurobipy as gp
from gurobipy import GRB
from datos import leer_instancia
from exportar import exportar_resultados

CARPETA_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETA_INSTANCIAS = os.path.join(CARPETA_RAIZ, "Instancias Excel")
CARPETA_SALIDA = os.path.join(CARPETA_RAIZ, "Análisis de Excels")
ARCHIVO_INSTANCIA = "instancia_E4.xlsx"

TIEMPO = 30 * 60           #limite de 30 minutos que pide el enunciado
GAP = 0                    #se resuelve hasta el optimo, solo se detiene antes si se acaba el tiempo
MILLON = 1e6               #los costos van en millones para que gurobi no tenga problemas numericos

#los conjuntos, parametros y variables tienen el mismo nombre que en el informe (secciones 5 y 6)


def construir_modelo(d):
    I, N, P, M, C, H, T, K, A = d["I"], d["N"], d["P"], d["M"], d["C"], d["H"], d["T"], d["K"], d["A"]
    nu, g, sigma, u, psi, phi_N = d["nu"], d["g"], d["sigma"], d["u"], d["psi"], d["phi_N"]
    zeta_E, kappa_E, a_E = d["zeta_E"], d["kappa_E"], d["a_E"]
    theta, alpha, mu, lam, omega, delta = d["theta"], d["alpha"], d["mu"], d["lambda"], d["omega"], d["delta"]
    gamma_C, rho_M, gamma_H, gamma_R, gamma_V, j, b = d["gamma_C"], d["rho_M"], d["gamma_H"], d["gamma_R"], d["gamma_V"], d["j"], d["b"]

    #psi barra: atractivo de todas las alternativas externas que tiene el sector i para el material m
    psi_barra = {(i, m): sum(psi.get((i, o), 0) for o in d["O_m"][m]) for i in I for m in M}
    #eta: atractivo de no llevar el material m a ningun punto limpio, o sea usar una alternativa o no reciclar
    eta = {(i, m): phi_N[m] + psi_barra[i, m] for i in I for m in M}

    mod = gp.Model("puntos_limpios")

    #variables
    z = mod.addVars(P, N, vtype=GRB.BINARY, name="z")         #binaria 1 si el punto actual p queda operando en el sitio n 0 eoc
    w = mod.addVars(N, C, vtype=GRB.INTEGER, name="w")        #cantidad de contenedores nuevos de tipo c en n
    q = mod.addVars([(i, n, m) for (i, n) in A for m in M], ub=1, name="q") #fraccion del material m del sector i que llega a n
    q0 = mod.addVars(I, M, ub=1, name="q0")                   #fraccion del material m del sector i que no llega a ningun punto limpio
    r = mod.addVars(N, M, T, name="r")                        #material m recibido en n en la semana t
    l = mod.addVars(N, M, T, name="l")                        #material m que llega a n en la semana t y se pierde porque no cabe (ell en el informe)
    s = mod.addVars(N, M, T, name="s")                        #material m almacenado en n al cierre de la semana t
    e = mod.addVars(H, N, M, T, name="e")                     #material m retirado desde n por el camion h en la semana t
    v = mod.addVars(H, N, T, vtype=GRB.INTEGER, name="v")     #paradas del camion h en n en la semana t
    x = mod.addVars(H, T, vtype=GRB.INTEGER, name="x")        #recorridos que hace el camion h en la semana t

    #el sitio n opera si le llega algun punto (suma de z sobre p)
    opera = {n: z.sum("*", n) for n in N}

    #capacidad de cada sitio para el material m, suma los contenedores nuevos y los que trae el punto p si queda en n
    capacidad = {(n, m): gp.quicksum(theta[c] * w[n, c] for c in d["C_m"][m])
                         + gp.quicksum(kappa_E[p, m] * z[p, n] for p in P) for n in N for m in M}

    #restricciones
    #R1 cada punto actual queda en un solo sitio, el mismo de hoy o uno nuevo
    mod.addConstrs((z.sum(p, "*") == 1 for p in P), name="R1")
    #R2 cada sitio recibe a lo mas un punto
    mod.addConstrs((opera[n] <= 1 for n in N), name="R2")
    #R3 al menos un punto limpio por macrozona
    mod.addConstrs((gp.quicksum(opera[n] for n in d["N_k"][k]) >= 1 for k in K), name="R3")

    #R4 a R7 son la eleccion de los vecinos con el logit linealizado
    #R4 el material de cada sector se reparte entre los puntos limpios y no llevarlo a ninguno
    mod.addConstrs((gp.quicksum(q[i, n, m] for (i2, n) in A if i2 == i) + q0[i, m] == 1 for i in I for m in M), name="R4")
    #R5 y R6 si el sitio opera la fraccion que recibe es proporcional a su atractivo, si no opera R6 no exige nada
    mod.addConstrs((q[i, n, m] <= u[i, n] / eta[i, m] * q0[i, m] for (i, n) in A for m in M), name="R5")
    mod.addConstrs((q[i, n, m] >= u[i, n] / eta[i, m] * (q0[i, m] - (1 - opera[n])) for (i, n) in A for m in M), name="R6")
    #R7 un sitio sin punto limpio no recibe nada
    mod.addConstrs((q[i, n, m] <= u[i, n] / (u[i, n] + eta[i, m]) * opera[n] for (i, n) in A for m in M), name="R7")
    #R8 lo que llevan los vecinos a n se recibe, y lo que no cabe en los contenedores se pierde
    mod.addConstrs((gp.quicksum(nu[i] * g[i, m] * sigma[t] * q[i, n, m] for (i, n2) in A if n2 == n)
                    == r[n, m, t] + l[n, m, t] for n in N for m in M for t in T), name="R8")

    for n in N:
        for m in M:
            for pos, t in enumerate(T):
                anterior = s[n, m, T[pos - 1]] if pos > 0 else 0   #los puntos parten vacios
                #R9 lo que estaba guardado mas lo recibido tiene que caber en los contenedores
                mod.addConstr(anterior + r[n, m, t] <= capacidad[n, m], name=f"R9[{n},{m},{t}]")
                #R10 balance de lo almacenado
                mod.addConstr(s[n, m, t] == anterior + r[n, m, t] - e.sum("*", n, m, t), name=f"R10[{n},{m},{t}]")
    #R10 los puntos terminan el año vacios, asi todo lo recibido termina retirado por los camiones
    mod.addConstrs((s[n, m, T[-1]] == 0 for n in N for m in M), name="R10")

    #R11 los contenedores nuevos y existentes caben en el sitio, y si no opera no puede tener contenedores
    mod.addConstrs((gp.quicksum(alpha[c] * w[n, c] for c in C)
                    + gp.quicksum(a_E[p] * z[p, n] for p in P) <= mu[n] * opera[n] for n in N), name="R11")
    #R12 al menos un contenedor por material en cada punto que opera
    mod.addConstrs((gp.quicksum(w[n, c] for c in d["C_m"][m])
                    + gp.quicksum(zeta_E[p, m] * z[p, n] for p in P) >= opera[n] for n in N for m in M), name="R12")
    #R13 solo se retira de un punto si el camion para ahi, y cada parada carga como mucho la capacidad en peso
    mod.addConstrs((e.sum(h, n, "*", t) <= lam[h] * v[h, n, t] for h in H for n in N for t in T), name="R13")
    #R14 lo que se retira en cada parada cabe en el volumen del camion, el plastico y el carton lo llenan antes que el peso
    mod.addConstrs((gp.quicksum(e[h, n, m, t] / delta[m] for m in M) <= omega[h] * v[h, n, t]
                    for h in H for n in N for t in T), name="R14")

    #R15 presupuesto anual en millones
    #gamma_H ya incluye trasladar los contenedores y se paga solo si el punto p queda en un sitio distinto al de hoy (iota = 0)
    iota = d["iota"]
    costos = {
        "Habilitación de traslados": gamma_H / MILLON * gp.quicksum((1 - iota[p, n]) * z[p, n] for p in P for n in N),
        "Compra de contenedores nuevos": gp.quicksum(gamma_C[c] / MILLON * w[n, c] for n in N for c in C),
        "Mantención de contenedores nuevos": gp.quicksum(rho_M[c] / MILLON * w[n, c] for n in N for c in C),
        "Recorridos de camiones": gp.quicksum(gamma_R[h] / MILLON * x[h, t] for h in H for t in T),
        "Paradas de camiones": gamma_V / MILLON * v.sum(),
    }
    mod.addConstr(gp.quicksum(costos.values()) <= b / MILLON, name="R15")

    #R16 lo que retira un camion en la semana, sumando todas sus paradas, cabe en su capacidad en peso por los recorridos que hace
    mod.addConstrs((e.sum(h, "*", "*", t) <= lam[h] * x[h, t] for h in H for t in T), name="R16")
    #R17 lo mismo en volumen
    mod.addConstrs((gp.quicksum(e[h, n, m, t] / delta[m] for n in N for m in M) <= omega[h] * x[h, t]
                    for h in H for t in T), name="R17")
    #R18 en cada recorrido un camion para a lo mas una vez en cada punto
    mod.addConstrs((v[h, n, t] <= x[h, t] for h in H for n in N for t in T), name="R18")
    #R19 cada camion hace como mucho j recorridos por semana
    mod.addConstrs((x[h, t] <= j for h in H for t in T), name="R19")
    #R20 un camion solo para donde opera un punto limpio, j no limita nada mas porque v <= x <= j
    mod.addConstrs((v[h, n, t] <= j * opera[n] for h in H for n in N for t in T), name="R20")

    #funcion objetivo, maximizar el material que se recicla en toda la comuna
    #lo que llevan los vecinos a los puntos limpios, menos lo que se pierde por capacidad, mas lo que llevan a alternativas
    #todo pesa 1 porque una tonelada reciclada vale lo mismo sin importar por donde se recicle
    #las fracciones semanales suman 1, por eso lo que lleva un sector en el año es nu * g * q
    llega = gp.quicksum(nu[i] * g[i, m] * q[i, n, m] for (i, n) in A for m in M)
    alternativas = gp.quicksum(nu[i] * g[i, m] * psi_barra[i, m] / eta[i, m] * q0[i, m] for i in I for m in M)
    mod.setObjective(llega - l.sum() + alternativas, GRB.MAXIMIZE)

    variables = {"z": z, "w": w, "q": q, "q0": q0, "r": r, "l": l, "s": s, "e": e, "v": v, "x": x,
                 "opera": opera, "capacidad": capacidad, "psi_barra": psi_barra, "eta": eta}
    return mod, variables, costos


def resolver(mod):
    mod.Params.MIPGap = GAP
    mod.Params.TimeLimit = TIEMPO
    mod.update()   #gurobi agrega las variables y restricciones recien aca, sin esto el tamano sale 0
    #guardar el tamano del modelo para la tabla del informe, a las enteras se le restan las binarias porque gurobi las cuenta como enteras
    tamano = {"variables": mod.NumVars, "binarias": mod.NumBinVars,
              "enteras": mod.NumIntVars - mod.NumBinVars, "restricciones": mod.NumConstrs}

    mod.optimize()
    if mod.SolCount == 0:   #no encontro ninguna solucion factible
        print("El modelo no tiene solución.")
        return None

    return {
        "estado": "Óptimo" if mod.Status == GRB.OPTIMAL else "Límite de tiempo",   #optimo si cerro el gap, si no se acabo el tiempo
        "toneladas": mod.ObjVal,        #toneladas recicladas en la comuna en la mejor solucion
        "cota": mod.ObjBound,           #lo maximo que se podria reciclar segun gurobi
        "gap [%]": 100 * mod.MIPGap,    #si no cerro en 30 min este es el gap final que se reporta
        "tiempo [s]": mod.Runtime,
        **tamano,                       #agrega variables, binarias, enteras y restricciones al mismo diccionario
    }


def main():
    os.makedirs(CARPETA_SALIDA, exist_ok=True)
    d = leer_instancia(os.path.join(CARPETA_INSTANCIAS, ARCHIVO_INSTANCIA))

    mod, variables, costos = construir_modelo(d)
    solucion = resolver(mod)
    if solucion is not None:
        resumen = exportar_resultados(d, mod, variables, costos, solucion, os.path.join(CARPETA_SALIDA, "resultados.xlsx"))
        print("\nResumen:")
        for clave, valor in resumen.items():
            print(f"  {clave}: {valor}")


if __name__ == "__main__":
    main()
