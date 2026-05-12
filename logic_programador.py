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
# EXCEL LOCAL
# =========================================================
def cargar_excel(nombre):
    try:
        return pd.read_excel(nombre)
    except:
        return pd.DataFrame()

def guardar_excel(df, nombre):
    df.to_excel(nombre, index=False)

# =========================================================
# PARAMETRIZADOR (NO SE TOCA)
# =========================================================
def parametrizador():

    st.header("🧩 Asignación de grupos")

    df = cargar_excel("empleados.xlsx")

    if df.empty:
        st.warning("No hay empleados")
        return

    st.dataframe(df, use_container_width=True)

    if st.button("🎲 Asignar grupos aleatoriamente"):

        import random

        grupos = GRUPOS.copy()

        asignacion = {}

        for i,emp in enumerate(df["Empleado"]):

            asignacion[emp] = grupos[i % len(grupos)]

        df["Grupo"] = df["Empleado"].map(asignacion)

        guardar_excel(df, "empleados.xlsx")

        st.success("Grupos asignados")
        st.dataframe(df)

# =========================================================
# COLORES FUERTES (FONDO)
# =========================================================
def estilo_turno(val):

    return {
        "T1": "background-color:#1976D2;color:white;",
        "T2": "background-color:#2E7D32;color:white;",
        "T3": "background-color:#C62828;color:white;",
        "T1 APOYO": "background-color:#90CAF9;color:black;",
        "T2 APOYO": "background-color:#A5D6A7;color:black;",
        "COMPENSADO": "background-color:#FFD54F;color:black;",
        "DESCANSO": "background-color:#000000;color:#FFD600;font-weight:bold;"
    }.get(val, "")

# =========================================================
# AUDITORIA
# =========================================================
def auditoria(df):

    alertas = []

    for g in GRUPOS:

        gdf = df[df["Grupo"] == g].sort_values("Fecha")

        prev = None

        for _, r in gdf.iterrows():

            if prev == "T3" and r["Turno"] == "T1":
                alertas.append([g, r["Fecha"], "SALTO T3 → T1"])

            prev = r["Turno"]

    return pd.DataFrame(alertas, columns=["Grupo","Fecha","Error"])

# =========================================================
# GENERADOR PRINCIPAL
# =========================================================
def generar_malla():

    st.header("🚀 OPTIMIZADOR INTELIGENTE PRO")

    c1,c2 = st.columns(2)

    inicio = c1.date_input("Inicio", date.today())
    fin = c2.date_input("Fin", date.today() + timedelta(days=30))

    # =====================================================
    # DESCANSOS
    # =====================================================
    st.subheader("Descanso de ley")

    descanso = {}

    cols = st.columns(4)

    for i,g in enumerate(GRUPOS):
        descanso[g] = cols[i].selectbox(g, DIAS_ES, index=i)

    # =====================================================
    # GENERACIÓN
    # =====================================================
    if st.button("Generar malla"):

        fechas = pd.date_range(inicio, fin, freq="D")

        carga = {g:0 for g in GRUPOS}
        conteo = {g:{"T1":0,"T2":0,"T3":0} for g in GRUPOS}

        filas = []

        for fecha in fechas:

            dia = DIAS_ES[fecha.weekday()]
            festivo = fecha.date() in festivos_co

            asignados = {}
            activos = GRUPOS.copy()

            # DESCANSO
            for g in GRUPOS:
                if descanso[g] == dia:
                    asignados[g] = "DESCANSO"
                    if g in activos:
                        activos.remove(g)

            # GARANTIZAR COBERTURA
            if len(activos) < 3:
                activos = GRUPOS.copy()

            # T1 T2 T3
            for turno in ["T1","T2","T3"]:

                candidatos = [(carga[g], conteo[g][turno], g) for g in activos]
                candidatos.sort()

                sel = candidatos[0][2]

                asignados[sel] = turno

                carga[sel] += 1
                conteo[sel][turno] += 1

                activos.remove(sel)

            # APOYO
            for g in GRUPOS:
                if g not in asignados:
                    asignados[g] = "T1 APOYO"

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

        guardar_excel(df, "malla.xlsx")

        st.success("Malla generada")

    # =====================================================
    # VISUALIZACIÓN
    # =====================================================
    if "malla" in st.session_state:

        df = st.session_state["malla"]

        pivot = df.pivot(index="Grupo", columns="Fecha", values="Turno")

        # DÍAS EN ESPAÑOL
        new_cols = {}
        for c in pivot.columns:
            new_cols[c] = c.strftime("%d-%m") + "\n" + DIAS_ES[c.weekday()]

        pivot.rename(columns=new_cols, inplace=True)

        st.subheader("📊 Malla editable")

        edited = st.data_editor(pivot, use_container_width=True)

        if st.button("💾 Guardar cambios manuales"):
            st.session_state["malla"] = edited.reset_index().melt(id_vars="Grupo")
            st.success("Cambios guardados")

        # COLORES
        st.dataframe(
            edited.style.map(estilo_turno),
            use_container_width=True
        )

        # =================================================
        # AUDITORIA
        # =================================================
        st.subheader("🚨 Auditoría")

        errores = auditoria(df)

        if not errores.empty:
            st.error("Saltos indebidos detectados")
            st.dataframe(errores)
        else:
            st.success("Sin saltos indebidos")

        # =================================================
        # COBERTURA
        # =================================================
        st.subheader("📊 Cobertura T1/T2/T3")

        cobertura = df[df["Turno"].isin(["T1","T2","T3"])].groupby("Fecha").size()

        st.line_chart(cobertura)

# =========================================================
# MENU
# =========================================================
def pantalla_programador():

    opcion = st.radio("Módulo", ["Programador","Parametrizador"], horizontal=True)

    if opcion == "Programador":
        generar_malla()
    else:
        parametrizador()
