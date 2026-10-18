import pandas as pd

MILLON = 1e6 #escala en la que están los precios


def valor(x):
    numero = x.getValue() if hasattr(x, "getValue") else x.X 
    return 0 if abs(numero) < 1e-6 else numero


def exportar_resultados(d, mod, var, costos, etapa_1, nombre, archivo):
    N, M, C, H, T, P = d["N"], d["M"], d["C"], d["H"], d["T"], d["P"]
    z, y, w, q, r, s, e, v, o, cont = (var[k] for k in ["z", "y", "w", "q", "r", "s", "e", "v", "o", "cont"])
    abiertos = []
    for n in N: # si quedó un punto limpio en ese sitio
        if y[n].X > 0.5:        # si quedó un punto limpio en ese sitio
            abiertos.append(n)

    # Resumen general
    costo_total = sum(valor(x) for x in costos.values()) * MILLON
    resumen = {
        "escenario": nombre, #optimo o actual
        "estado": etapa_1["estado"], #
        "material_recuperado [ton]": sum(valor(e[h, n, m, t]) for h in H for n in N for m in M for t in T), #suma de lo que retiraron los camiones todas las semanas en todas las ubicaciones de todos los materiales
        "cota_superior [ton]": etapa_1["cota"], 
        "gap [%]": etapa_1["gap [%]"],
        "tiempo [s]": round(etapa_1["tiempo [s]"], 2),
        "costo_total [CLP]": round(costo_total),
        "presupuesto [CLP]": d["presupuesto"],
    }

    #donde quedaron ubicados los puntos limpios
    ubicaciones = []
    for p in P:
        for n in N:
            if z[p, n].X > 0.5: #si se ubico el punto limpio en la ubicacion n 
                ubicaciones.append({"punto": p, "sitio_actual": d["sitio_actual"][p], "sitio_asignado": n, "se_traslada": n != d["sitio_actual"][p]})

    #cuantos contenedores de cada tipo quedaron en cada punto limpio
    contenedores = []
    for n in abiertos:
        for c in C:
            total = round(valor(cont[n, c])) #a veces me daban numero muy cercano a un entero para eso el round
            if total > 0:
                contenedores.append({"sitio": n, "tipo": c, "material": d["material_de"][c], "nuevos [cont]": round(w[n, c].X), "total [cont]": total, "capacidad [ton]": total * d["cap_cont"][c]})

    #cuanto recoleta (en fraccion) el sector n de cada ubicacion i
    recolectado = []
    for (i, n) in var["pares"]: #recorre todos los pares sector i ubicacion n que se encuentran dentro de la distancia max
        for m in M:
            if q[i, n, m].X > 1e-6: #evitar fracciones muy cercanas o practicamente 0
                recolectado.append({"sector": i, "sitio": n, "material": m, "fraccion [-]": q[i, n, m].X})

    #mostramos por cada sitio por cada material por cada semana cuanto recibió cuanto recolectaron los camiones, cuanto quedo almacenado sin retirar y la capacidad total del punto
    reporte_por_semana = []
    for n in abiertos:
        for m in M:
            capacidad = sum(d["cap_cont"][c] * valor(cont[n, c]) for c in d["C_m"][m]) #suma la capacidad para cada material segun todos sus posibles tipos de contenedores
            for t in T: 
                reporte_por_semana.append({"sitio": n, "material": m, "semana": t, "recibido [ton]": valor(r[n, m, t]), "retirado [ton]": sum(valor(e[h, n, m, t]) for h in H), "almacenado [ton]": valor(s[n, m, t]), "capacidad [ton]": capacidad})

    #muestra por cada semana cada camión donde paró, cuánto material recogió y su cap máxima
    recorridos = []
    for h in H:
        for t in T:
            if o[h, t].X > 0.5:
                paradas = [n for n in N if v[h, n, t].X > 0.5] #agrega las ubicaciones por donde pasó 
                recorridos.append({"camion": h, "semana": t, "paradas": ", ".join(paradas), "carga [ton]": sum(valor(e[h, n, m, t]) for n in N for m in M), "capacidad [ton]": d["cap_camion"][h]}) #sumamos para todas la ubicaciones y materiales

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
