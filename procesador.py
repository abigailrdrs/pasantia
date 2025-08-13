from gurobipy import *
import pandas as pd
import math
import time
import os

M = [0, 1]
H = [0, 1, 2]
E = [0, 1, 2]
tt = 0
Mval = 100000

def cargar_archivos_y_modelar(num, max_n):
    carpeta = os.path.join(os.getcwd(), "datos_reordenados")
    resultados = {}

    for i in range(num):
        nombre_archivo = f"archivo_reordenado_{i+1}.xlsx"
        ruta_archivo = os.path.join(carpeta, nombre_archivo)
        if not os.path.isfile(ruta_archivo):
            print(f"⚠️ Falta {ruta_archivo}")
            continue

        df = pd.read_excel(ruta_archivo)

        for n in range(5, max_n):
            J = list(range(n))

            # --- Recorte seguro a n filas
            df_n = df.iloc[:n, :].copy()

            # --- Columnas esperadas y saneo
            if "tps procédé 1" not in df_n.columns or "tps procédé 2" not in df_n.columns:
                print(f"⚠️ Faltan columnas de tiempos en {nombre_archivo}")
                continue

            proc1 = df_n["tps procédé 1"].fillna(0).astype(float).apply(math.ceil).astype(int).tolist()
            proc2 = df_n["tps procédé 2"].fillna(0).astype(float).apply(math.ceil).astype(int).tolist()
            proces = {
                0: {j: proc1[j] for j in J},
                1: {j: proc2[j] for j in J},
            }

            # longitudes desde col índice 9 -> clip a {0,1}
            if df_n.shape[1] <= 9:
                print(f"⚠️ El archivo {nombre_archivo} no tiene columna índice 9")
                continue
            longitudes = (
                df_n.iloc[:, 9].fillna(0).astype(int).clip(lower=0, upper=1).tolist()
            )
            if len(longitudes) < n:
                longitudes += [0] * (n - len(longitudes))

            # mf desde col índice 5: valores 1/2 -> -1 => {0,1}, con clamp
            if df_n.shape[1] <= 5:
                print(f"⚠️ El archivo {nombre_archivo} no tiene columna índice 5")
                continue
            mf_raw = df_n.iloc[:, 5].fillna(1).astype(int).tolist()
            mf = [max(1, min(2, x)) - 1 for x in mf_raw]  # {0,1}

            # due amplio mientras depuramos (evita que C21 fuerce inviable)
            due = [10000 for _ in J]

            # --- Modelo
            model = Model(f"Bombardier_file{i+1}_n{n}")
            model.setParam("OutputFlag", 0)

            # Variables
            x = model.addVars(E, J, vtype=GRB.BINARY, name="x")
            g = model.addVars(E, M, J, vtype=GRB.BINARY, name="g")
            b = model.addVars(E, J, J, vtype=GRB.BINARY, name="b")
            y = model.addVars(M, J, J, vtype=GRB.BINARY, name="y")
            z = model.addVars(H, M, J, vtype=GRB.BINARY, name="z")
            # q eliminado temporalmente para evitar contradicciones
            c = model.addVars(J, vtype=GRB.INTEGER, lb=0, name="c")
            d = model.addVars(J, vtype=GRB.INTEGER, lb=0, name="d")
            t = model.addVars(M, J, vtype=GRB.INTEGER, lb=0, name="t")
            a = model.addVars(M, J, vtype=GRB.INTEGER, lb=0, name="a")
            cmax = model.addVar(vtype=GRB.INTEGER, lb=0, name="cmax")

            # --- Restricciones
            # C1: cada trabajo en una única etapa e
            model.addConstrs((quicksum(x[e, j] for e in E) == 1 for j in J), name="C1")

            # C2: si longitud[j]=1 obliga x[2,j]=1
            model.addConstrs((x[2, j] >= longitudes[j] for j in J), name="C2")

            # C4_C9: antisimetrias con big-M y x
            model.addConstrs((
                b[e, j, k] + b[e, k, j] <= 1 + Mval * (2 - x[e, j] - x[e, k])
                for e in E for j in J for k in J if j != k
            ), name="C4_C9")

            # C10: enlace g-x
            model.addConstrs((quicksum(g[e, m, j] for m in M) == x[e, j] for e in E for j in J), name="C10")

            # C11 (coherente con mf): sólo la máquina mf[j] puede tener g=1
            model.addConstrs((g[e, m, j] == 0 for e in E for j in J for m in M if m != mf[j]), name="C11_forbid_others")
            model.addConstrs((g[e, mf[j], j] == x[e, j] for e in E for j in J), name="C11_assign_mf")

            # C14: c[k] ≥ t + proc + a - Mval*(1 - b[e,j,k])
            model.addConstrs((
                c[k] >= t[m, j] + proces[m][j] + a[m, j] + 2 * tt
                - Mval * (1 - b[e, j, k])
                for m in M for e in E for j in J for k in J if j != k
            ), name="C14")

            # C15: d[j] = t[m,j] - tt para m != mf[j]
            model.addConstrs((d[j] == t[m, j] - tt for j in J for m in M if m != mf[j]), name="C15")

            # C16: d[j] ≥ c[j]
            model.addConstrs((d[j] >= c[j] for j in J), name="C16")

            # Ordenamiento condicional por máquina (reemplaza tu C17 plana)
            Gjm = {(m, j): quicksum(g[e, m, j] for e in E) for m in M for j in J}
            Gkm = {(m, k): quicksum(g[e, m, k] for e in E) for m in M for k in J}

            # y sólo puede ser 1 si j y k están en m
            model.addConstrs((y[m, j, k] <= Gjm[m, j] for m in M for j in J for k in J if j != k), name="Y_up1")
            model.addConstrs((y[m, j, k] <= Gkm[m, k] for m in M for j in J for k in J if j != k), name="Y_up2")
            # si ambos están en m, exactamente uno de {y[m,j,k], y[m,k,j]} es 1
            model.addConstrs((y[m, j, k] + y[m, k, j] >= Gjm[m, j] + Gkm[m, k] - 1
                              for m in M for j in J for k in J if j != k), name="Y_low")
            model.addConstrs((y[m, j, k] + y[m, k, j] <= 1
                              for m in M for j in J for k in J if j != k), name="Y_ub")

            # C18: exactamente un z por (m,j)
            model.addConstrs((quicksum(z[h, m, j] for h in H) == 1 for m in M for j in J), name="C18")

            # C19a/b/c: restricciones sobre z
            model.addConstrs((z[2, 0, j] == 0 for j in J), name="C19a")
            model.addConstrs((z[1, 1, j] == 0 for j in J), name="C19b")
            model.addConstrs((z[0, 1, j] == 0 for j in J), name="C19c")

            # C20: precedencia activa sólo si j y k están en m
            model.addConstrs((
                t[m, k] >= t[m, j] + proces[m][j] + a[m, j] + 2 * tt
                - Mval * (1 - y[m, j, k])
                - Mval * (2 - Gjm[m, j] - Gkm[m, k])  # desactiva si no comparten máquina
                for m in M for j in J for k in J if j != k
            ), name="C20_cond")

            # C21: fecha límite en la máquina mf[j] (due alto por ahora)
            model.addConstrs((t[mf[j], j] + proces[mf[j]][j] + a[mf[j], j] + tt <= due[j] for j in J), name="C21")

            # C22a/b: RELAJADAS a ≥ para no atrapar el reloj en igualdad
            model.addConstrs((a[0, j] >= (t[mf[j], j] - tt) - (t[0, j] + proces[0][j]) for j in J if mf[j] != 0), name="C22a_ge")
            model.addConstrs((a[1, j] >= (t[mf[j], j] - tt) - (t[1, j] + proces[1][j]) for j in J if mf[j] != 1), name="C22b_ge")

            # C28: makespan
            model.addConstrs((cmax >= t[mf[j], j] + proces[mf[j]][j] + a[mf[j], j] + tt for j in J), name="C28")

            # Objetivo
            model.setObjective(cmax, GRB.MINIMIZE)

            # Resolver
            start = time.time()
            model.optimize()
            end = time.time()
            resultados[n] = end - start
            #analizar que tiempo es el que me esta imprimiendo

            # Mostrar resultados ordenados por tiempo de inicio en cada máquina
            # Verificamos que el modelo encontró solución
            if model.status in [GRB.OPTIMAL, GRB.SUBOPTIMAL]:
                print(f"\n✅ Makespan mínimo: {cmax.X}\n")

                # Mostrar tiempos ordenados por máquina
                for m in M:
                    tiempos = []
                    for j in J:
                        if t[m, j].X is not None:   # evita errores si alguna variable no está definida
                            tiempos.append((t[m, j].X, j))

                    # Ordenar por tiempo de inicio
                    tiempos.sort(key=lambda x: x[0])

                    print(f"--- Máquina {m+1} ---")
                    for inicio, j in tiempos:
                        fin = inicio + proces[m][j]
                        espera = a[m, j].X if a[m, j].X is not None else 0
                        print(f"Trabajo {j+1}: inicio = {abs(inicio)}, fin = {abs(fin)}, espera = {abs(espera)}")
            else:
                print("\n⚠️ Modelo no tiene solución factible, no se pueden mostrar tiempos.")

            if model.status == GRB.INFEASIBLE:
                print("El modelo es inviable. Calculando IIS...")
                model.computeIIS()
                iis_name = f"modelo_inviable_file{i+1}_n{n}.ilp"
                model.write(iis_name)
                for cst in model.getConstrs():
                    if cst.IISConstr:
                        print(f"Inviable: {cst.constrName}")

        for n in range(5, max_n):
            if n in resultados:
                print(f" {n}: {resultados[n]}")