import pandas as pd

# Cambia esta ruta por la de tu archivo ODS
archivo_ods = "C:/Users/RAFAEL OLIVARES/Documents/medicamentos.ods"

# Leer la hoja principal (si tienes más de una hoja, puedes poner sheet_name="NombreHoja")
df = pd.read_excel(archivo_ods, engine="odf")

# Mostrar las primeras filas para confirmar
print(df.head())
