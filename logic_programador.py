# logic_programador.py
# =========================================================
# OPTIMIZADOR INTELIGENTE PRO ENTERPRISE
# =========================================================

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import holidays
import io

# =========================================================
# CONFIG
# =========================================================
TURNOS = [
    "T1","T2","T3",
    "T1 APOYO","T2 APOYO",
    "DESCANSO","COMPENSADO"
]

GRUPOS = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]

DIAS_ES = [
    "Lunes","Martes","Miércoles",
    "Jueves","Viernes","Sábado","Domingo"
]

festivos_co = holidays.Colombia()

# =========================================================
# GITHUB / EXCEL LOCAL
# =========================================================
def cargar_excel(nombre):

    try:
        return pd.read_excel(nombre)
    except:
        return pd.DataFrame()


def guardar_excel(df, nombre):

    df.to_excel(nombre, index=False)

# =========================================================
# PARAMETRIZADOR DE GRUPOS (REAL)
# =========================================================
def parametrizador():

    st.header("🧩 Asignación de grupos")

    df = cargar_excel("empleados.xlsx")

    if df.empty:
        df = pd.DataFrame({
            "Nombre":["A","B","C","D"],
            "Grupo":["","","",""]
        })

    st.dataframe(df, use_container_width=True)

    # =========================================
    # ASIGNACIÓN AUTOMÁTICA
    # =========================================
    if st.button("🎲 Asignar grupos automáticamente"):

        df = df.sample(frac=1).reset_index(drop=True)

        for i in range(len(df)):
            df.loc[i, "Grupo"] = GRUPOS[i % len(GRUPOS)]

        guardar_excel(df, "empleados.xlsx")

        st.success("Grupos asignados y guardados en empleados.xlsx")

# =========================================================
# GENERADOR DE MALLA
# =========================================================
def generar_malla():

    st.header("🚀 OPTIMIZADOR INTELIGENTE PRO")

    c1,c2 = st.columns(2)

    inicio = c1.date_input("Inicio", date.today())
    fin = c2.date_input("Fin", date.today()+timedelta(days=30))

    # =====================================================
    # DESCANSOS
    # =====================================================
    st.subheader("Descanso de ley")

    cols = st.columns(len(GRUPOS))
    descanso_actual = {}

    for i,g in enumerate(GRUPOS):

        key = f"descanso_{g}"

        if key not in st.session_state:
            st.session_state[key] = DIAS_ES[i]

        descanso_actual[g] = cols[i].selectbox(
            g, DIAS_ES, key=key
        )

    # =====================================================
    # GENERAR MALLA
    # =====================================================
    if st.button("Generar malla"):

        carga = {g:0 for g in GRUPOS}
        ultimo = {g:None for g in GRUPOS}

        filas = []

        fechas = pd.date_range(inicio, fin)

        for fecha in fechas:

            dia = DIAS_ES[fecha.weekday()]
            festivo = fecha.date() in festivos_co

            asignados = {}

            # =========================================
            # DESCANSOS
            # =========================================
            grupos_descanso = [
                g for g in GRUPOS
                if descanso_actual[g] == dia
            ]

            activos = [
                g for g in GRUPOS
                if g not in grupos_descanso
            ]

            # =========================================
            # TURNOS OBLIGATORIOS
            # =========================================
            for turno in ["T1","T2","T3"]:

                candidatos = []

                for g in activos:

                    prev = ultimo[g]

                    if prev == "T3" and turno == "T1":
                        continue

                    if prev == "T2" and turno == "T1":
                        continue

                    candidatos.append((carga[g], g))

                if not candidatos:
                    candidatos = [(carga[g], g) for g in activos]

                candidatos.sort()

                sel = candidatos[0][1]

                asignados[sel] = turno
                ultimo[sel] = turno
                carga[sel] += 1

                activos.remove(sel)

            # =========================================
            # DESCANSO
            # =========================================
            for g in grupos_descanso:
                asignados[g] = "DESCANSO"

            # =========================================
            # APOYO
            # =========================================
            for g in activos:
                asignados[g] = "T1 APOYO"

            # =========================================
            # GUARDAR
            # =========================================
            for g in GRUPOS:

                filas.append({
                    "Fecha": fecha,
                    "Día": dia,
                    "Grupo": g,
                    "Turno": asignados.get(g,"SIN ASIGNAR"),
                    "Festivo": "SI" if festivo else "NO"
                })

        df = pd.DataFrame(filas)

        st.session_state["malla"] = df

        guardar_excel(df, "empleados.xlsx")

        st.success("Malla generada y guardada en empleados.xlsx")

    # =====================================================
    # VISUALIZACIÓN + EDITOR
    # =====================================================
    if "malla" in st.session_state:

        st.subheader("📊 Malla editable")

        df = st.session_state["malla"]

        edit = st.data_editor(
            df,
            column_config={
                "Turno": st.column_config.SelectboxColumn(
                    "Turno",
                    options=TURNOS
                )
            },
            use_container_width=True
        )

        if st.button("💾 Guardar cambios manuales"):

            st.session_state["malla"] = edit
            guardar_excel(edit, "empleados.xlsx")

            st.success("Cambios guardados en Excel")

        # =========================================
        # PIVOT
        # =========================================
        pivot = edit.pivot(
            index="Grupo",
            columns="Fecha",
            values="Turno"
        ).fillna("SIN ASIGNAR")

        # =========================================
        # COLORES FONDO REAL
        # =========================================
        def color(v):

            return {
                "T1":"background:#1976D2;color:white;font-weight:bold",
                "T2":"background:#2E7D32;color:white;font-weight:bold",
                "T3":"background:#C62828;color:white;font-weight:bold",
                "DESCANSO":"background:#000000;color:#FFD600;font-weight:bold",
                "COMPENSADO":"background:#FF9800;color:black;font-weight:bold",
                "T1 APOYO":"background:#E0E0E0",
                "T2 APOYO":"background:#BDBDBD",
                "SIN ASIGNAR":"background:#FFFFFF"
            }.get(v,"")

        st.dataframe(
            pivot.style.applymap(color),
            use_container_width=True
        )

        # =========================================
        # AUDITORÍA SALTOS
        # =========================================
        st.subheader("🚨 Saltos indebidos")

        saltos = []

        for g in GRUPOS:

            gdf = edit[edit["Grupo"] == g].sort_values("Fecha")

            prev = None

            for _,r in gdf.iterrows():

                if prev == "T3" and r["Turno"] == "T1":
                    saltos.append([g,r["Fecha"],"T3→T1"])

                if prev == "T2" and r["Turno"] == "T1":
                    saltos.append([g,r["Fecha"],"T2→T1"])

                prev = r["Turno"]

        if saltos:
            st.error("Saltos detectados")
            st.dataframe(pd.DataFrame(saltos))
        else:
            st.success("Sin saltos indebidos")

        # =========================================
        # COBERTURA
        # =========================================
        st.subheader("🛡️ Cobertura diaria")

        faltantes = []

        for f in edit["Fecha"].unique():

            d = edit[edit["Fecha"] == f]

            turnos = set(d["Turno"])

            for t in ["T1","T2","T3"]:
                if t not in turnos:
                    faltantes.append([f,t])

        if faltantes:
            st.error("Faltan turnos")
            st.dataframe(pd.DataFrame(faltantes))
        else:
            st.success("Cobertura completa")

# =========================================================
# MENU PRINCIPAL
# =========================================================
def pantalla_programador():

    mod = st.radio(
        "Módulo",
        ["Programador","Parametrizador"],
        horizontal=True
    )

    if mod == "Programador":
        generar_malla()
    else:
        parametrizador()
