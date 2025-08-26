import os
import requests
import pandas as pd
#funcion que crea los archivos
def datos(num):
    
    url = "https://raw.githubusercontent.com/abigailrdrs/datos_pasantia/main/datos_originales.xlsx"


    r = requests.get(url)
    with open("archivo.xlsx", "wb") as f:
        f.write(r.content)
    df = pd.read_excel("archivo.xlsx")

    #Reordena los datos y guarda en una carpeta llamada "datos_reordenados"
    carpeta_actual = os.getcwd()
    nombre_carpeta = "datos_reordenados"
    ruta_carpeta = os.path.join(carpeta_actual, nombre_carpeta)
    # Reordenar los datos
    
    columnas = ["Trabajos", "Tiempos","Objetivo"]
    carpeta = "TIEMPOS"
    if not os.path.exists(carpeta):
        os.makedirs(carpeta)
    for i in range(num):
        semilla=42+i
        df_reordenado = df.sample(frac=1, random_state=semilla).reset_index(drop=True)
        # Guardar archivo reordenado en la carpeta creada
        nombre_archivo = f"archivo_reordenado_{i+1}.xlsx"
        ruta_completa = os.path.join(ruta_carpeta, nombre_archivo)
        df_reordenado.to_excel(ruta_completa, index=False)

        
        df = pd.DataFrame(columns=columnas)
        nombre_archivo = os.path.join(carpeta, f"archivo_tiempos{i+1}.xlsx")
        df.to_excel(nombre_archivo, index=False)
