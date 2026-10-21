import pandas as pd

MILLON = 1e6 #escala en la que están los precios


def valor(x):
    numero = x.getValue() if hasattr(x, "getValue") else x.X
    return 0 if abs(numero) < 1e-6 else numero


def exportar_resultados(d, mod, var, costos, etapa_1, nombre, archivo):
    N, M, C, H, T, P = d["N"], d["M"], d["C"], d["H"], d["T"], d["P"]
    z, y, w, q, r, s, e, v, o, capacidad = (var[k] for k in ["z", "y", "w", "q", "r", "s", "e", "v", "o", "capacidad"])
    abiertos = []
    for n in N:
        if y[n].X > 0.5:        # si quedó un punto limpio en ese sitio
            abiertos.append(n)
    punto_en = {n: p for p in P for n in N if z[p, n].X > 0.5} #qué punto actual quedó en cada sitio abierto

    # Resumen general
    costo_total = sum(valor(x) for x in costos.values()) * MILLON
    resumen = {
        "escenario": nombre, #optimo o actual
        "estado": etapa_1["estado"],
        "material_recuperado [ton]": sum(valor(e[h, n, m, t]) for h in H for n in N for m in M for t in T), #suma de lo que retiraron los camiones todas las semanas en todas las ubicaciones de todos los materiales
        "cota_superior [ton]": etapa_1["cota"],
        "gap [%]": etapa_1["gap [%]"],
        "tiempo [s]": round(etapa_1["tiempo [s]"], 2),
        "costo_total [CLP]": round(costo_total),
        "presupuesto [CLP]": d["presupuesto"],
        "variables": etapa_1["variables"],
        "variables binarias": etapa_1["binarias"],
        "variables enteras": etapa_1["enteras"],
        "restricciones": etapa_1["restricciones"],
    }

    #donde quedaron ubicados los puntos limpios
    ubicaciones = []
    for p in P:
        for n in N:
            if z[p, n].X > 0.5: #si se ubico el punto limpio en la ubicacion n
                ubicaciones.append({"punto": p, "nombre": d["nombre"][p], "sitio_actual": d["sitio_actual"][p], "sitio_asignado": n, "se_traslada": n != d["sitio_actual"][p]})

    #contenedores de cada sitio abierto: los existentes que llegaron con el punto y los nuevos que se compraron
    contenedores = []
    for n in abiertos:
        p = punto_en[n]
        for fila in d["dotacion"]:
            if fila["punto"] == p:
                contenedores.append({"sitio": n, "punto": p, "origen": "existente", "tipo": fila["tipo"], "material": fila["material"],
                                     "cantidad [cont]": fila["cantidad [cont]"], "capacidad [ton]": fila["capacidad [ton]"]})
        for c in C:
            nuevos = round(w[n, c].X) #a veces me daban numero muy cercano a un entero para eso el round
            if nuevos > 0:
                contenedores.append({"sitio": n, "punto": p, "origen": "nuevo", "tipo": c, "material": d["material_de"][c],
                                     "cantidad [cont]": nuevos, "capacidad [ton]": nuevos * d["cap_cont"][c]})

    #cuanto recolecta (en fraccion) cada sitio n del material de cada sector i
    recolectado = []
    for (i, n) in var["pares"]: #recorre todos los pares sector i ubicacion n que se encuentran dentro de la distancia max
        for m in M:
            if q[i, n, m].X > 1e-6: #evitar fracciones muy cercanas o practicamente 0
                recolectado.append({"sector": i, "sitio": n, "material": m, "fraccion [-]": q[i, n, m].X})

    #mostramos por cada sitio por cada material por cada semana cuanto recibió cuanto recolectaron los camiones, cuanto quedo almacenado sin retirar y la capacidad total del punto
    reporte_por_semana = []
    for n in abiertos:
        for m in M:
            cap = valor(capacidad[n, m]) #capacidad de los contenedores nuevos y existentes para ese material
            for t in T:
                reporte_por_semana.append({"sitio": n, "material": m, "semana": t, "recibido [ton]": valor(r[n, m, t]), "retirado [ton]": sum(valor(e[h, n, m, t]) for h in H), "almacenado [ton]": valor(s[n, m, t]), "capacidad [ton]": cap})

    #muestra por cada semana cada camión donde retiró material, cuánto recogió y su cap máxima
    recorridos = []
    for h in H:
        for t in T:
            if o[h, t].X > 0.5:
                #solo las paradas donde efectivamente retiró algo (sin costo por parada, una parada vacía no cambia nada)
                paradas = [n for n in N if v[h, n, t].X > 0.5 and sum(valor(e[h, n, m, t]) for m in M) > 0]
                recorridos.append({"camion": h, "semana": t, "paradas con retiro": ", ".join(paradas), "carga [ton]": sum(valor(e[h, n, m, t]) for n in N for m in M), "capacidad [ton]": d["cap_camion"][h]}) #sumamos para todas la ubicaciones y materiales

    #resumen de cuanto se gastó por cada componente
    resumen_costos = [{"componente": k, "monto [CLP]": round(valor(x) * MILLON), "% del presupuesto": round(100 * valor(x) * MILLON / d["presupuesto"], 1)} for k, x in costos.items()]
    resumen_costos.append({"componente": "Total gastado", "monto [CLP]": round(costo_total), "% del presupuesto": round(100 * costo_total / d["presupuesto"], 1)})
    resumen_costos.append({"componente": "Presupuesto", "monto [CLP]": d["presupuesto"], "% del presupuesto": 100})

    with pd.ExcelWriter(archivo) as excel:
        pd.DataFrame([resumen]).to_excel(excel, sheet_name="Resumen", index=False)
        pd.DataFrame(ubicaciones).to_excel(excel, sheet_name="Ubicaciones", index=False)
        pd.DataFrame(contenedores).to_excel(excel, sheet_name="Contenedores", index=False)
        pd.DataFrame(recolectado).to_excel(excel, sheet_name="Recolectado", index=False)
        pd.DataFrame(reporte_por_semana).to_excel(excel, sheet_name="Reporte por Semana", index=False)
        pd.DataFrame(recorridos).to_excel(excel, sheet_name="Recorridos por Semana", index=False)
        pd.DataFrame(resumen_costos).to_excel(excel, sheet_name="Resumen de Costos", index=False)

    print(f"[{nombre}] Resultados guardados en resultados_{nombre}.xlsx")
    return resumen
