# logic_programador.py
# =========================================================
# OPTIMIZADOR INTELIGENTE PRO + AUDITORÍA ENTERPRISE
# =========================================================

import streamlit as st
import pandas as pd
from datetime import date, timedelta
import holidays

# =========================================================
# CONFIG
# =========================================================
TURNOS = ["T1","T2","T3","T1 APOYO","T2 APOYO","DESCANSO","COMPENSADO"]
GRUPOS = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]
DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
festivos_co = holidays.Colombia()

# =========================================================
# COLORES
# =========================================================
def color_cell(v):

    return {
        "T1":"background-color:#AED6F1",
        "T2":"background-color:#A9DFBF",
        "T3":"background-color:#F5B7B1",
        "T1 APOYO":"background-color:#D6EAF8",
        "T2 APOYO":"background-color:#D5F5E3",
        "DESCANSO":"background-color:#2C3E50;color:#F9E79F;font-weight:700",
        "COMPENSADO":"background-color:#FDEBD0"
    }.get(v,"")

# =========================================================
# GENERADOR
# =========================================================
def generar_malla():

    st.header("🚀 OPTIMIZADOR PRO + AUDITORÍA")

    c1,c2 = st.columns(2)
    inicio = c1.date_input("Inicio", date.today())
    fin = c2.date_input("Fin", date.today()+timedelta(days=30))

    # =====================================================
    # DESCANSO DE LEY
    # =====================================================
    st.subheader("⚖️ Descanso de ley")

    descanso_actual = {}
    cols = st.columns(len(GRUPOS))

    for i,g in enumerate(GRUPOS):
        descanso_actual[g] = cols[i].selectbox(g, DIAS_ES, index=i)

    # =====================================================
    # ESTADO
    # =====================================================
    carga = {g:0 for g in GRUPOS}
    conteo = {g:{"T1":0,"T2":0,"T3":0} for g in GRUPOS}
    compensado = {g:0 for g in GRUPOS}
    sacrificio = {g:0 for g in GRUPOS}

    filas = []

    # =====================================================
    # GENERACIÓN
    # =====================================================
    if st.button("🚀 Generar malla"):

        fechas = pd.date_range(inicio, fin)

        for f in fechas:

            dia = DIAS_ES[f.weekday()]
            festivo = f.date() in festivos_co

            asignados = {}

            descanso = [g for g in GRUPOS if descanso_actual[g]==dia]
            activos = [g for g in GRUPOS if g not in descanso]

            # COBERTURA
            while len(activos) < 3:
                mov = sorted(descanso, key=lambda g:(sacrificio[g], carga[g]))[0]
                descanso.remove(mov)
                activos.append(mov)
                sacrificio[mov]+=1
                compensado[mov]+=1

            # DESCANSO
            for g in descanso:
                asignados[g]="DESCANSO"

            # TURNOS
            for t in ["T1","T2","T3"]:

                sel = sorted(activos, key=lambda g:(carga[g], conteo[g][t]))[0]
                asignados[sel]=t
                carga[sel]+=1
                conteo[sel][t]+=1
                activos.remove(sel)

            # COMPENSADO
            for g in GRUPOS:
                if compensado[g]>0 and g not in asignados:
                    asignados[g]="COMPENSADO"
                    compensado[g]-=1

            # APOYO
            for g in GRUPOS:
                if g not in asignados:
                    asignados[g]="T1 APOYO"

            for g in GRUPOS:
                filas.append({
                    "Grupo":g,
                    "Fecha":f,
                    "Día":dia,
                    "Turno":asignados[g],
                    "Festivo":"SI" if festivo else "NO"
                })

        df = pd.DataFrame(filas)
        st.session_state["df"]=df

    # =====================================================
    # MALLA
    # =====================================================
    if "df" in st.session_state:

        df = st.session_state["df"]

        pivot = df.pivot(index="Grupo", columns="Fecha", values="Turno")

        pivot.columns = [
            f"{c.strftime('%d-%m')}\n{DIAS_ES[c.weekday()]}"
            for c in pivot.columns
        ]

        st.subheader("📊 Malla operativa")

        st.dataframe(
            pivot.style.map(color_cell),
            use_container_width=True
        )

        # =====================================================
        # ================== DASHBOARD PRO ====================
        # =====================================================
        st.subheader("📊 DASHBOARD PROFESIONAL")

        col1,col2,col3,col4 = st.columns(4)

        total_turnos = df[df["Turno"].isin(["T1","T2","T3"])]

        col1.metric("Cobertura total", len(total_turnos))
        col2.metric("Descansos", len(df[df["Turno"]=="DESCANSO"]))
        col3.metric("Compensados", len(df[df["Turno"]=="COMPENSADO"]))
        col4.metric("Grupos activos", len(GRUPOS))

        # =====================================================
        # EQUILIBRIO POR GRUPO
        # =====================================================
        st.subheader("⚖️ Balance por grupo")

        balance = df.groupby(["Grupo","Turno"]).size().unstack(fill_value=0)

        st.dataframe(balance, use_container_width=True)

        # =====================================================
        # ROTACIÓN (BALANCE REAL)
        # =====================================================
        st.subheader("🔄 Equilibrio de rotación")

        rotacion = df[df["Turno"].isin(["T1","T2","T3"])].groupby("Grupo").size()

        st.bar_chart(rotacion)

        # =====================================================
        # COBERTURA POR DÍA
        # =====================================================
        st.subheader("📅 Cobertura diaria T1/T2/T3")

        cobertura = df[df["Turno"].isin(["T1","T2","T3"])].groupby("Fecha").size()

        st.line_chart(cobertura)

        # =====================================================
        # AUDITORÍA DE DESCANSOS
        # =====================================================
        st.subheader("🛌 Auditoría de descansos")

        audit_desc = df[df["Turno"]=="DESCANSO"].groupby("Grupo").size()

        st.dataframe(audit_desc)

        # =====================================================
        # ALERTAS
        # =====================================================
        st.subheader("🚨 Alertas del sistema")

        alertas = []

        for g in GRUPOS:
            gdf = df[df["Grupo"]==g]

            if len(gdf[gdf["Turno"]=="DESCANSO"]) < 4:
                alertas.append(f"{g} pocos descansos")

            if len(gdf[gdf["Turno"]=="T3"]) > len(gdf[gdf["Turno"]=="T1"]):
                alertas.append(f"{g} sobrecarga T3")

        if alertas:
            st.error(alertas)
        else:
            st.success("Sistema balanceado")

# =========================================================
# MENU
# =========================================================
def pantalla_programador():

    op = st.radio("Módulo",["Programador","Parametrizador"],horizontal=True)

    if op=="Programador":
        generar_malla()
    else:
        st.write("Parametrizador activo")
