from gurobipy import *
import requests
import pandas as pd
import math
import time
import os
#hi
M = [0, 1]
H = [0, 1, 2]
E = [0, 1, 2]
tt=0

Mval = 100000

resultados={}
tiempo_total = 0

def cargar_archivos_y_modelar(num,max_n):
    carpeta = os.path.join(os.getcwd(), "datos_reordenados")
    resultados = {}
    for i in range(num):
        nombre_archivo = f"archivo_reordenado_{i+1}.xlsx"
        ruta_archivo = os.path.join(carpeta, nombre_archivo)
        # Leer archivo
        df = pd.read_excel(ruta_archivo)
        for n in range(5,max_n):
            J=list(range(n))

            # Procesamiento: convertir NaN en 0, luego transformar a int
            proces = {
                0: {k: math.ceil(v) for k, v in df["tps procédé 1"].fillna(0).astype(float).to_dict().items()},
                1: {k: math.ceil(v) for k, v in df["tps procédé 2"].fillna(0).astype(float).to_dict().items()}
            }


            # Cargar longitudes desde columna J (número 9, índice 9)
            longitudes = df.iloc[:, 9].fillna(0).astype(int).tolist()

            # Cargar mf desde columna F (número 5, índice 5)
            mf = df.iloc[:, 5].fillna(0).astype(int).tolist()
            mf = [x - 1 for x in mf]
            due = [100 for _ in J]


            # Crear modelo
            model = Model("Bombardier")

            # Variables
            x = model.addVars(E, J, vtype=GRB.BINARY, name="x")
            g = model.addVars(E, M, J, vtype=GRB.BINARY, name="g")
            b = model.addVars([0, 1, 2], J, J, vtype=GRB.BINARY, name="b")
            y = model.addVars(M, J, J, vtype=GRB.BINARY, name="y")
            z = model.addVars(H, M, J, vtype=GRB.BINARY, name="z")
            q = model.addVars(M, E, J, vtype=GRB.BINARY, name="q")
            c = model.addVars(J, vtype=GRB.INTEGER, name="c")
            d = model.addVars(J, vtype=GRB.INTEGER, name="d")
            t = model.addVars(M, J, vtype=GRB.INTEGER, name="t")
            a = model.addVars(M, J, vtype=GRB.INTEGER, name="a")
            cmax = model.addVar(vtype=GRB.INTEGER, name="cmax")


            # Restricciones representativas
            model.addConstrs((quicksum(x[e, j] for e in E) == 1 for j in J), name="C1")
            model.addConstrs((x[2, j] >= longitudes[j] for j in J), name="C2")
            model.addConstrs((b[e, j, k] + b[e, k, j] <= 1 + Mval * (2 - x[e, j] - x[e, k])
                            for e in E for j in J for k in J if j != k), name="C4_C9")
            model.addConstrs((quicksum(g[e, m, j] for m in M) == x[e, j] for e in E for j in J), name="C10")
            model.addConstrs((g[e, mf[j], j] == 0 for e in E for j in J), name="C11")
            model.addConstrs((q[mf[j], fi, j] == x[fi, j] for fi in E for j in J), name="C12")
            model.addConstrs((q[m, fi, j] == 0 for m in M for fi in E for j in J if m != mf[j]), name="C13")
            model.addConstrs((c[k] >= t[m, j] + proces[m][j] + a[m, j] + 2*tt - Mval * (1 - b[e, j, k])
                            for m in M for e in E for j in J for k in J if j != k), name="C14")
            model.addConstrs((d[j] == t[m, j] - tt for j in J for m in M if m != mf[j]), name="C15")
            model.addConstrs((d[j] >= c[j] for j in J), name="C16")
    
            model.addConstrs((y[m, j, k] + y[m, k, j] ==1 for m in M for j in J for k in J if j != k), name="C17")
            model.addConstrs((quicksum(z[h, m, j] for h in H) == 1 for m in M for j in J), name="C18")
            model.addConstrs((z[2, 0, j] == 0 for j in J), name="C19a")
            model.addConstrs((z[1, 1, j] == 0 for j in J), name="C19b")
            model.addConstrs((z[0, 1, j] == 0 for j in J), name="C19c")

            model.addConstrs((
                t[m, k] >= t[m, j] + proces[m][j] + a[m, j] + 2*tt
                - Mval * (1 - y[m, j, k])
                for m in M for j in J for k in J if j != k
            ), name="C20")

            model.addConstrs((t[mf[j], j] + proces[mf[j]][j] + a[mf[j], j] + tt <= due[j] for j in J), name="C21")
            model.addConstrs((a[0, j] == (t[mf[j], j] - tt) - (t[0, j] + proces[0][j]) for j in J if mf[j] != 0), name="C22a")
            model.addConstrs((a[1, j] == (t[mf[j], j] - tt) - (t[1, j] + proces[1][j]) for j in J if mf[j] != 1), name="C22b")
            model.addConstrs((cmax >= t[mf[j], j] + proces[mf[j]][j] + a[mf[j], j] + tt for j in J), name="C28")


            # Objetivo
            model.setObjective(cmax, GRB.MINIMIZE)
            model.setParam('OutputFlag', 0)

            # Optimizar e imprimir el tiempo
            start = time.time()
            model.optimize()
            end = time.time()

            resultados[n]=end-start
            #analizar que tiempo es el que me esta imprimiendo

            # Mostrar resultados ordenados por tiempo de inicio en cada máquina
            # Verificamos que el modelo encontró solución
            #if model.status in [GRB.OPTIMAL, GRB.SUBOPTIMAL]:
                #print(f"\n✅ Makespan mínimo: {cmax.X}\n")

                # Mostrar tiempos ordenados por máquina
                #for m in M:
                    #tiempos = []
                    #for j in J:
                        #if t[m, j].X is not None:   # evita errores si alguna variable no está definida
                            #tiempos.append((t[m, j].X, j))

                    # Ordenar por tiempo de inicio
                    #tiempos.sort(key=lambda x: x[0])

                    #print(f"--- Máquina {m+1} ---")
                    #for inicio, j in tiempos:
                        #fin = inicio + proces[m][j]
                        #espera = a[m, j].X if a[m, j].X is not None else 0
                        #print(f"Trabajo {j+1}: inicio = {abs(inicio)}, fin = {abs(fin)}, espera = {abs(espera)}")
            #else:
                #print("\n⚠️ Modelo no tiene solución factible, no se pueden mostrar tiempos.")

            #me explica donde hay problemas
            if model.status == GRB.INFEASIBLE:
                print("El modelo es inviable. Calculando IIS...")
                model.computeIIS()
                model.write("modelo_inviable.ilp")  # Exporta el IIS para revisión

                # También podés imprimir los nombres de las restricciones responsables
                for c in model.getConstrs():
                    if c.IISConstr:
                        print(f"Inviable: {c.constrName}")

        for i in range(5,max_n):
            print(f" {i}: {resultados[i]}")