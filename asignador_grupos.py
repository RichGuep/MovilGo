import random
import pandas as pd

def asignar_grupos(df, grupos, modo="balanceado"):

    df = df.copy()

    df["Grupo"] = None

    if modo == "aleatorio":

        for i, idx in enumerate(df.index):
            df.at[idx, "Grupo"] = random.choice(grupos)

        return df

    # =====================================================
    # MODO BALANCEADO (RECOMENDADO)
    # =====================================================

    conteo = {g: 0 for g in grupos}

    for idx, row in df.iterrows():

        grupo_min = min(conteo, key=conteo.get)

        df.at[idx, "Grupo"] = grupo_min

        conteo[grupo_min] += 1

    return df
