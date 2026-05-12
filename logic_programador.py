# logic_programador.py
# =========================================================
# OPTIMIZADOR INTELIGENTE PRO ENTERPRISE - VERSION ESTABLE
# =========================================================

import streamlit as st
import pandas as pd
from datetime import date, timedelta
import holidays
import io

# =========================================================
# CONFIG
# =========================================================
TURNOS = [
    "T1", "T2", "T3",
    "T1 APOYO", "T2 APOYO",
    "DESCANSO", "COMPENSADO"
]

GRUPOS = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]

DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]

festivos_co = holidays.Colombia()

# =========================================================
# ESTANDARIZACIÓN APOYOS
# =========================================================
def normalizar_turno(t):
    if t == "T1 APOYO":
        return "T1"
    if t == "T2 APOYO":
        return "T2"
    return t

# =========================================================
# COLORES SUAVES
# =========================================================
def color_cell(v):

    estilos = {
        "T1": "background-color:#D6EAF8",
        "T2": "background-color:#D5F5E3",
        "T3": "background-color:#FADBD8",

        "T1 APOYO": "background-color:#EBF5FB",
        "T2 APOYO": "background-color:#EAF2F8",

        "DESCANSO": "background-color:#000000;color:#FFD700;font-weight:700",

        "COMPENSADO": "background-color:#FDEBD0"
    }

    return estilos.get(v, "")

# =========================================================
# GITHUB (simplificado)
# =========================================================
def guardar_excel_github(df, nombre="malla_historica.xlsx"):
    try:
        df.to_excel(nombre, index=False)
    except:
        pass

# =========================================================
# AUDITORÍA
# =========================================================
def auditoria(df):

    errores = []
    cobertura = []

    for fecha in df["Fecha"].unique():

        df_dia = df[df["Fecha"] == fecha]

        turnos = df_dia["Turno"].apply(normalizar_turno)

        # cobertura mínima
        for t in ["T1","T2","T3"]:
            if t not in list(turnos.values):
                errores.append(f"FALTA {t} en {fecha}")

        # saltos indebidos por grupo
        for g in GRUPOS:

            gdf = df_dia[df_dia["Grupo"] == g].sort_values("Fecha")

            prev = None

            for _, r in gdf.iterrows():

                act = normalizar_turno(r["Turno"])

                if prev == "T3" and act in ["T1"]:
                    errores.append(f"{g} T3→T1 {r['Fecha']}")

                if prev == "T3" and act == "T1 APOYO":
                    errores.append(f"{g} T3→APOYO {r['Fecha']}")

                if prev == "T2" and act == "T1":
                    errores.append(f"{g} T2→T1 {r['Fecha']}")

                prev = act

    return errores

# =========================================================
# GENERADOR
# =========================================================
def generar_malla():

    st.header("🚀 OPTIMIZADOR PRO")

    c1, c2 = st.columns(2)

    inicio = c1.date_input("Inicio", date.today())
    fin = c2.date_input("Fin", date.today() + timedelta(days=30))

    # =====================================================
    # DESCANSO
    # =====================================================
    st.subheader("Descanso de ley")

    descanso_actual = {}

    cols = st.columns(len(GRUPOS))

    for i, g in enumerate(GRUPOS):
        descanso_actual[g] = cols[i].selectbox(g, DIAS_ES, index=i)

    # =====================================================
    # VARIABLES
    # =====================================================
    carga = {g:0 for g in GRUPOS}
    conteo = {g:{"T1":0,"T2":0,"T3":0} for g in GRUPOS}

    filas = []

    # =====================================================
    # GENERACIÓN
    # =====================================================
    if st.button("Generar malla"):

        fechas = pd.date_range(inicio, fin)

        for fecha in fechas:

            dia = DIAS_ES[fecha.weekday()]
            festivo = fecha.date() in festivos_co

            asignados = {}

            descanso = [g for g in GRUPOS if descanso_actual[g] == dia]
            activos = [g for g in GRUPOS if g not in descanso]

            # asegurar cobertura mínima
            while len(activos) < 3:
                mover = descanso.pop(0)
                activos.append(mover)

            # descansos
            for g in descanso:
                asignados[g] = "DESCANSO"

            # turnos base
            for turno in ["T1","T2","T3"]:

                candidatos = sorted(activos, key=lambda g:(carga[g], conteo[g][turno]))

                sel = candidatos[0]

                asignados[sel] = turno

                carga[sel] += 1
                conteo[sel][turno] += 1

                activos.remove(sel)

            # apoyos
            for g in activos:
                asignados[g] = "T1 APOYO"

            # guardar
            for g in GRUPOS:
                filas.append({
                    "Fecha": fecha,
                    "Día": dia,
                    "Grupo": g,
                    "Turno": asignados[g],
                    "Festivo": "SI" if festivo else "NO"
                })

        df = pd.DataFrame(filas)

        st.session_state["malla"] = df

        guardar_excel_github(df)

        st.success("Malla generada")

    # =====================================================
    # VISUALIZACIÓN
    # =====================================================
    if "malla" in st.session_state:

        df = st.session_state["malla"]

        # FIX FECHAS
        df["Fecha"] = pd.to_datetime(df["Fecha"]).dt.date

        # =================================================
        # MALLA HORIZONTAL
        # =================================================
        pivot = df.pivot(index="Grupo", columns="Fecha", values="Turno")

        rename = {
            c: f"{c.strftime('%d-%m')}\n{DIAS_ES[c.weekday()]}"
            for c in pivot.columns
        }

        pivot.rename(columns=rename, inplace=True)

        st.subheader("📊 Malla horizontal")

        st.dataframe(
            pivot.style.map(color_cell),
            use_container_width=True
        )

        # =================================================
        # EDITOR ÚNICO (MISMA DATA)
        # =================================================
        st.subheader("✏️ Editor único")

        edit = st.data_editor(
            df,
            use_container_width=True,
            column_config={
                "Turno": st.column_config.SelectboxColumn(
                    "Turno",
                    options=TURNOS
                )
            }
        )

        st.session_state["malla"] = edit

        # =================================================
        # AUDITORÍA
        # =================================================
        st.subheader("🚨 Auditoría")

        errores = auditoria(edit)

        if errores:
            st.error("Se encontraron inconsistencias")
            st.write(errores)
        else:
            st.success("Sin errores")

        # =================================================
        # COBERTURA
        # =================================================
        st.subheader("📈 Cobertura diaria")

        cov = edit.groupby("Fecha")["Turno"].apply(lambda x: sum(x.isin(["T1","T2","T3"])))

        st.line_chart(cov)

# =========================================================
# MENU
# =========================================================
def pantalla_programador():

    op = st.radio("Módulo", ["Programador","Parametrizador"], horizontal=True)

    if op == "Programador":
        generar_malla()
    else:
        st.write("Parametrizador en siguiente versión")
