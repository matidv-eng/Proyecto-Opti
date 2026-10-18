ICS1113 Optimización - Grupo 20 - Entrega 3
Relocalización de la red de puntos limpios de Puente Alto

CÓMO EJECUTAR
  Desde esta carpeta:   python main.py
  Corre de inicio a fin sin intervención y usa rutas relativas.
  Tiempo máximo: 30 minutos por escenario (25 para maximizar toneladas + 5 para abaratar).

LIBRERÍAS
  gurobipy y pandas (pandas usa openpyxl internamente para leer y escribir Excel).

ARCHIVOS
  main.py      Configuración, modelo (restricciones R1 a R17, igual que en el informe) y resolución.
  datos.py     Lee la instancia desde "Instancias Excel".
  exportar.py  Escribe los resultados en "Análisis de Excels".

RESOLUCIÓN EN DOS ETAPAS
  1) Se maximizan las toneladas retiradas.
  2) Sin perder esas toneladas, se minimiza el costo total (objetivo secundario).

ESCENARIOS
  optimo                El modelo decide dónde queda cada punto limpio.
  ubicaciones_actuales  Los puntos quedan donde están hoy (caso base de comparación).

RESULTADOS (carpeta "Análisis de Excels")
  resultados_<escenario>.xlsx
      Resumen       Toneladas recuperadas, gap, tiempo, costo y tamaño del modelo.
      Ubicaciones   Sitio actual y sitio asignado de cada punto limpio.
      Contenedores  Contenedores nuevos, totales y capacidad por punto.
      Captura       Fracción de cada material de cada sector que llega a cada punto.
      Flujos        Recibido, retirado y almacenado por punto, material y semana.
      Recorridos    Paradas y carga de cada camión por semana.
      Costos        Desglose del presupuesto.
  comparacion_escenarios.xlsx   Ambos escenarios lado a lado.
  log_gurobi_<escenario>.txt    Registro completo de Gurobi.
