import pandas as pd
from logic.rotacion import rotar_grupos
from logic.reglas import obtener_descanso, asignar_tr

def generar_malla(fecha_ini, fecha_fin, grupos, personal_grupos, descansos):

    resultados = []
    fechas = pd.date_range(fecha_ini, fecha_fin)

    tr_counter = {}

    personas = [
        {"nombre": p, "grupo": g}
        for g, lista in personal_grupos.items()
        for p in lista
    ]

    for fecha in fechas:

        dia = fecha.weekday()
        semana = fecha.isocalendar().week

        grupo_descanso = obtener_descanso(dia, descansos)

        # DESCANSO
        resultados.append({
            "Fecha": fecha,
            "Grupo": grupo_descanso,
            "Turno": "DESC"
        })

        # ACTIVOS
        activos = [g for g in grupos if g != grupo_descanso]
        t1, t2 = rotar_grupos(activos, semana)

        for g in t1:
            resultados.append({"Fecha": fecha, "Grupo": g, "Turno": "T1"})

        for g in t2:
            resultados.append({"Fecha": fecha, "Grupo": g, "Turno": "T2"})

        # TR
        tr = asignar_tr(grupo_descanso, personas, tr_counter, fecha)

        if tr:
            resultados.append(tr)

    return pd.DataFrame(resultados)
