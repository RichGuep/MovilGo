# logic_programador.py
# =========================================================
# OPTIMIZADOR INTELIGENTE PRO ENTERPRISE vFINAL
# =========================================================

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import holidays

# =========================================================
# CONFIG
# =========================================================
TURNOS = ["T1","T2","T3","T1 APOYO","T2 APOYO","DESCANSO","COMPENSADO"]

GRUPOS = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]

DIAS_ES = [
    "Lunes","Martes","Miércoles",
    "Jueves","Viernes","Sábado","Domingo"
]

festivos_co = holidays.Colombia()

# =========================================================
# COLORES SUAVES (FONDO REAL)
# =========================================================
def color_cell(v):

    estilos = {
        "T1": "background-color:#AED6F1;color:#0B3C5D;font-weight:600;",
        "T2": "background-color:#A9DFBF;color:#145A32;font-weight:600;",
        "T3": "background-color:#F5B7B1;color:#641E16;font-weight:600;",

        "T1 APOYO": "background-color:#D6EAF8;",
        "T2 APOYO": "background-color:#D5F5E3;",

        "DESCANSO": "background-color:#1C2833;color:#F7DC6F;font-weight:800;",

        "COMPENSADO": "background-color:#FDEBD0;color:#7E5109;font-weight:700;"
    }

    return estilos.get(v, "")

# =========================================================
# PARAMETRIZADOR (mínimo sin romper sistema)
# =========================================================
def parametrizador():

    st.header("🧩 Parametrizador")

    df = pd.DataFrame({
        "Empleado": ["A","B","C","D"],
        "Grupo": ["","","",""]
    })

    st.dataframe(df, use_container_width=True)

    if st.button("Asignar"):
        df["Grupo"] = GRUPOS * 10
        st.success("Grupos asignados")

# =========================================================
# GENERADOR
# =========================================================
def generar_malla():

    st.header("🚀 OPTIMIZADOR PRO ENTERPRISE")

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
    # GENERAR
    # =====================================================
    if st.button("Generar malla"):

        fechas = pd.date_range(inicio, fin)

        for fecha in fechas:

            dia = DIAS_ES[fecha.weekday()]
            festivo = fecha.date() in festivos_co

            asignados = {}

            descanso = [g for g in GRUPOS if descanso_actual[g]==dia]
            activos = [g for g in GRUPOS if g not in descanso]

            # =================================================
            # GARANTIZAR COBERTURA T1/T2/T3
            # =================================================
            while len(activos) < 3:

                mov = sorted(descanso, key=lambda g:(sacrificio[g], carga[g]))[0]
                descanso.remove(mov)
                activos.append(mov)

                sacrificio[mov]+=1
                compensado[mov]+=1

            # =================================================
            # DESCANSO
            # =================================================
            for g in descanso:
                asignados[g]="DESCANSO"

            # =================================================
            # TURNOS PRINCIPALES (SIN HUECOS)
            # =================================================
            for turno in ["T1","T2","T3"]:

                candidatos = sorted(
                    activos,
                    key=lambda g:(carga[g], conteo[g][turno])
                )

                sel = candidatos[0]
                asignados[sel]=turno
                carga[sel]+=1
                conteo[sel][turno]+=1
                activos.remove(sel)

            # =================================================
            # COMPENSADO (EQUILIBRADO)
            # =================================================
            for g in sorted(GRUPOS, key=lambda x:compensado[x]):

                if compensado[g] > 0 and g not in asignados:
                    asignados[g]="COMPENSADO"
                    compensado[g]-=1
                    break

            # =================================================
            # APOYOS SIN SALTOS PROHIBIDOS
            # =================================================
            for g in GRUPOS:

                if g not in asignados:

                    if conteo[g]["T3"] > 0:
                        asignados[g]="T2 APOYO"
                    elif conteo[g]["T2"] > conteo[g]["T1"]:
                        asignados[g]="T2 APOYO"
                    else:
                        asignados[g]="T1 APOYO"

            # =================================================
            # GUARDAR
            # =================================================
            for g in GRUPOS:

                filas.append({
                    "Fecha": fecha,
                    "Día": dia,
                    "Grupo": g,
                    "Turno": asignados[g],
                    "Festivo": "SI" if festivo else "NO"
                })

        df = pd.DataFrame(filas)
        st.session_state["malla"]=df
        st.success("Malla generada")

    # =====================================================
    # VISUALIZACIÓN
    # =====================================================
    if "malla" in st.session_state:

        df = st.session_state["malla"]

        # ==============================
        # MALLA HORIZONTAL
        # ==============================
        st.subheader("📊 Malla horizontal")

        pivot = df.pivot(index="Grupo",columns="Fecha",values="Turno")

        rename={}
        for c in pivot.columns:
            rename[c]=f"{c.strftime('%d-%m')}\n{DIAS_ES[c.weekday()]}"

        pivot.rename(columns=rename,inplace=True)

        st.dataframe(
            pivot.style.map(color_cell),
            use_container_width=True
        )

        # ==============================
        # EDITOR (MISMA ESTRUCTURA)
        # ==============================
        st.subheader("✏️ Editor de malla (horizontal real)")

        edit_df = st.data_editor(
            df,
            use_container_width=True,
            column_config={
                "Turno": st.column_config.SelectboxColumn(
                    "Turno",
                    options=TURNOS
                )
            }
        )

        if st.button("Guardar edición"):
            st.session_state["malla"]=edit_df
            st.success("Guardado")

        # ==============================
        # AUDITORÍA
        # ==============================
        st.subheader("🚨 Auditoría")

        errores=[]

        for g in GRUPOS:

            gdf=df[df["Grupo"]==g]
            prev=None

            for _,r in gdf.iterrows():

                if prev=="T2" and r["Turno"]=="T1":
                    errores.append(f"{g} salto T2→T1 {r['Fecha']}")

                if prev=="T3" and r["Turno"] in ["T1","T2"]:
                    errores.append(f"{g} salto T3→inferior {r['Fecha']}")

                prev=r["Turno"]

        if errores:
            st.error("Saltos indebidos")
            st.write(errores)
        else:
            st.success("Sin saltos indebidos")

        # ==============================
        # COBERTURA
        # ==============================
        st.subheader("📈 Cobertura diaria")

        cov=df[df["Turno"].isin(["T1","T2","T3"])].groupby("Fecha").size()

        st.line_chart(cov)

# =========================================================
# MENU
# =========================================================
def pantalla_programador():

    op = st.radio("Módulo",["Programador","Parametrizador"],horizontal=True)

    if op=="Programador":
        generar_malla()
    else:
        parametrizador()
