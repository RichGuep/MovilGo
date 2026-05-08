
def calcular_equidad(df):

    if "Persona_TR" not in df.columns:
        return 0

    tr = df[df["Turno"] == "TR"].groupby("Persona_TR").size()

    if len(tr) == 0:
        return 0

    return tr.std()
