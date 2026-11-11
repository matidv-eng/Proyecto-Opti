import pandas as pd

MILLON = 1e6 #escala en la que estan los precios


def valor(x):
    numero = x.getValue() if hasattr(x, "getValue") else x.X
    return 0 if abs(numero) < 1e-6 else numero


def exportar_resultados(d, mod, var, costos, solucion, archivo):
    N, M, C, H, T, P, I = d["N"], d["M"], d["C"], d["H"], d["T"], d["P"], d["I"]
    z, w, q, q0, r, l, s, e, v, x, opera, capacidad, psi, eta = (var[k] for k in ["z", "w", "q", "q0", "r", "l", "s", "e", "v", "x", "opera", "capacidad", "psi", "eta"])
    abiertos = [n for n in N if valor(opera[n]) > 0.5]                  #sitios donde quedo un punto limpio
    punto_en = {n: p for p in P for n in N if z[p, n].X > 0.5}         #que punto actual quedo en cada sitio abierto

    #a donde va el material de cada sector, lo que no llega a puntos limpios se reparte entre alternativas y no reciclar segun sus atractivos (logit)
    generado = {(i, m): d["poblacion"][i] * d["gen"][i, m] for i in I for m in M}                      #toneladas al año
    a_puntos = {(i, m): 0 for i in I for m in M}
    for (i, n) in var["pares"]:
        for m in M:
            a_puntos[i, m] += generado[i, m] * q[i, n, m].X
    a_alternativas = {(i, m): generado[i, m] * psi[i, m] / eta[i, m] * q0[i, m].X for i in I for m in M}
    no_reciclado = {(i, m): generado[i, m] * d["u_no"][m] / eta[i, m] * q0[i, m].X for i in I for m in M}

    # Resumen general
    costo_total = sum(valor(c) for c in costos.values()) * MILLON
    resumen = {
        "estado": solucion["estado"],
        "reciclado total [ton]": solucion["toneladas"],                                         #funcion objetivo, puntos limpios mas alternativas
        "reciclado en puntos limpios [ton]": sum(valor(r[n, m, t]) for n in N for m in M for t in T),
        "reciclado en alternativas [ton]": sum(a_alternativas.values()),
        "perdido por capacidad [ton]": sum(valor(l[n, m, t]) for n in N for m in M for t in T),
        "no reciclado [ton]": sum(no_reciclado.values()),
        "material_retirado [ton]": sum(valor(e[h, n, m, t]) for h in H for n in N for m in M for t in T),
        "recorridos en el año": sum(round(x[h, t].X) for h in H for t in T),
        "paradas en el año": sum(round(v[h, n, t].X) for h in H for n in N for t in T),
        "cota_superior [ton]": solucion["cota"],
        "gap [%]": solucion["gap [%]"],
        "tiempo [s]": round(solucion["tiempo [s]"], 2),
        "costo_total [CLP]": round(costo_total),
        "presupuesto [CLP]": d["presupuesto"],
        "variables": solucion["variables"],
        "variables binarias": solucion["binarias"],
        "variables enteras": solucion["enteras"],
        "restricciones": solucion["restricciones"],
    }

    #destino del material de cada tipo en toda la comuna
    destino = []
    for m in M:
        recibido = sum(valor(r[n, m, t]) for n in N for t in T)
        alternativas = sum(a_alternativas[i, m] for i in I)
        destino.append({"material": m, "generado [ton]": sum(generado[i, m] for i in I),
                        "recibido en puntos limpios [ton]": recibido,
                        "perdido por capacidad [ton]": sum(valor(l[n, m, t]) for n in N for t in T),
                        "a alternativas [ton]": alternativas,
                        "no reciclado [ton]": sum(no_reciclado[i, m] for i in I),
                        "reciclado total [ton]": recibido + alternativas})
    destino = pd.DataFrame(destino).set_index("material")
    destino.loc["Total"] = destino.sum()
    for col in destino.columns[1:]:
        destino[col.replace("[ton]", "[%]")] = 100 * destino[col] / destino["generado [ton]"]
    destino = destino.reset_index()

    #destino del material por sector, lo que llega a puntos limpios incluye lo que despues se pierde por capacidad
    destino_sector = [{"sector": i, "material": m, "generado [ton]": generado[i, m], "a puntos limpios [ton]": a_puntos[i, m],
                       "a alternativas [ton]": a_alternativas[i, m], "no reciclado [ton]": no_reciclado[i, m]}
                      for i in I for m in M if generado[i, m] > 0]

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
        for m in M:
            if d["n_exist"][p, m] > 0:
                contenedores.append({"sitio": n, "punto": p, "origen": "existente", "tipo": d["tipo_exist"][p, m], "material": m,
                                     "cantidad [cont]": d["n_exist"][p, m], "capacidad [ton]": d["cap_exist"][p, m]})
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

    #por cada sitio, material y semana cuanto recibio, cuanto se perdio, cuanto retiraron los camiones, cuanto quedo almacenado y la capacidad del punto
    reporte_por_semana = []
    for n in abiertos:
        for m in M:
            cap = valor(capacidad[n, m]) #capacidad de los contenedores nuevos y existentes para ese material
            for t in T:
                reporte_por_semana.append({"sitio": n, "material": m, "semana": t, "recibido [ton]": valor(r[n, m, t]), "perdido [ton]": valor(l[n, m, t]),
                                           "retirado [ton]": sum(valor(e[h, n, m, t]) for h in H), "almacenado [ton]": valor(s[n, m, t]), "capacidad [ton]": cap})

    #por cada camion y semana cuantos recorridos hizo, donde paro y cuanto se llevo en peso y en volumen
    recorridos = []
    for h in H:
        for t in T:
            veces = round(x[h, t].X)
            if veces > 0:
                paradas = {n: round(v[h, n, t].X) for n in N if v[h, n, t].X > 0.5}
                recorridos.append({"camion": h, "semana": t, "recorridos": veces,
                                   "paradas": ", ".join(f"{n} ({k})" for n, k in paradas.items()), "total paradas": sum(paradas.values()),
                                   "carga [ton]": sum(valor(e[h, n, m, t]) for n in N for m in M), "capacidad [ton]": d["cap_camion"][h] * veces,
                                   "volumen usado [m3]": sum(valor(e[h, n, m, t]) / d["densidad"][m] for n in N for m in M), "volumen disponible [m3]": d["vol_camion"][h] * veces})

    #resumen de cuanto se gasto por cada componente
    resumen_costos = [{"componente": k, "monto [CLP]": round(valor(c) * MILLON), "% del presupuesto": round(100 * valor(c) * MILLON / d["presupuesto"], 1)} for k, c in costos.items()]
    resumen_costos.append({"componente": "Total gastado", "monto [CLP]": round(costo_total), "% del presupuesto": round(100 * costo_total / d["presupuesto"], 1)})
    resumen_costos.append({"componente": "Presupuesto", "monto [CLP]": d["presupuesto"], "% del presupuesto": 100})

    with pd.ExcelWriter(archivo) as excel:
        pd.DataFrame([resumen]).to_excel(excel, sheet_name="Resumen", index=False)
        destino.to_excel(excel, sheet_name="Destino del material", index=False)
        pd.DataFrame(destino_sector).to_excel(excel, sheet_name="Destino por sector", index=False)
        pd.DataFrame(ubicaciones).to_excel(excel, sheet_name="Ubicaciones", index=False)
        pd.DataFrame(contenedores).to_excel(excel, sheet_name="Contenedores", index=False)
        pd.DataFrame(recolectado).to_excel(excel, sheet_name="Recolectado", index=False)
        pd.DataFrame(reporte_por_semana).to_excel(excel, sheet_name="Reporte por Semana", index=False)
        pd.DataFrame(recorridos).to_excel(excel, sheet_name="Recorridos por Semana", index=False)
        pd.DataFrame(resumen_costos).to_excel(excel, sheet_name="Resumen de Costos", index=False)

    print(f"Resultados guardados en {archivo}")
    return resumen
