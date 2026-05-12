# logic_programador.py
# =========================================================
# OPTIMIZADOR INTELIGENTE PRO ENTERPRISE vFINAL EDITOR
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

DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]

festivos_co = holidays.Colombia()

# =========================================================
# COLORES SUAVES (FONDO)
# =========================================================
def color_cell(v):

    estilos = {
        "T1": "background-color:#AED6F1;color:#154360;font-weight:600;",
        "T2": "background-color:#A9DFBF;color:#145A32;font-weight:600;",
        "T3": "background-color:#F5B7B1;color:#641E16;font-weight:600;",

        "T1 APOYO": "background-color:#D6EAF8;",
        "T2 APOYO": "background-color:#D5F5E3;",

        "DESCANSO": "background-color:#1C2833;color:#F9E79F;font-weight:800;",

        "COMPENSADO": "background-color:#FDEBD0;color:#7E5109;font-weight:700;"
    }

    return estilos.get(v, "")

# =========================================================
# PARAMETRIZADOR SIMPLE
# =========================================================
def parametrizador():

    st.header("🧩 Parametrizador")

    df = pd.DataFrame({
        "Empleado": ["A","B","C","D"],
        "Grupo": ["","","",""]
    })

    st.dataframe(df, use_container_width=True)

    if st.button("Asignar grupos"):
        st.success("Grupos asignados (demo)")

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
    # GENERAR MALLA
    # =====================================================
    if st.button("Generar malla"):

        fechas = pd.date_range(inicio, fin)

        for fecha in fechas:

            dia = DIAS_ES[fecha.weekday()]
            festivo = fecha.date() in festivos_co

            asignados = {}

            # ================================
            # DESCANSO DE LEY
            # ================================
            descanso = [g for g in GRUPOS if descanso_actual[g]==dia]
            activos = [g for g in GRUPOS if g not in descanso]

            # ================================
            # COBERTURA MÍNIMA T1/T2/T3
            # ================================
            while len(activos) < 3:

                mov = sorted(descanso, key=lambda g:(sacrificio[g], carga[g]))[0]
                descanso.remove(mov)
                activos.append(mov)

                sacrificio[mov]+=1
                compensado[mov]+=1

            # ================================
            # DESCANSOS
            # ================================
            for g in descanso:
                asignados[g] = "DESCANSO"

            # ================================
            # TURNOS PRINCIPALES
            # ================================
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

            # ================================
            # COMPENSADOS
            # ================================
            for g in sorted(GRUPOS, key=lambda x:compensado[x]):

                if compensado[g] > 0 and g not in asignados:
                    asignados[g]="COMPENSADO"
                    compensado[g]-=1
                    break

            # ================================
            # APOYOS SIN SALTOS
            # ================================
            for g in GRUPOS:

                if g not in asignados:

                    if conteo[g]["T3"] > 0:
                        asignados[g]="T2 APOYO"
                    elif conteo[g]["T2"] > conteo[g]["T1"]:
                        asignados[g]="T2 APOYO"
                    else:
                        asignados[g]="T1 APOYO"

            # ================================
            # GUARDAR
            # ================================
            for g in GRUPOS:

                filas.append({
                    "Fecha": fecha,
                    "Día": dia,
                    "Grupo": g,
                    "Turno": asignados[g],
                    "Festivo": "SI" if festivo else "NO"
                })

        st.session_state["malla"]=pd.DataFrame(filas)
        st.success("Malla generada correctamente")

    # =====================================================
    # VISUALIZACIÓN + EDICIÓN
    # =====================================================
    if "malla" in st.session_state:

        df = st.session_state["malla"]

        # ================================
        # MALLA HORIZONTAL
        # ================================
        st.subheader("📊 Malla horizontal")

        pivot = df.pivot(index="Grupo",columns="Fecha",values="Turno")

        rename = {}
        for c in pivot.columns:
            rename[c]=f"{c.strftime('%d-%m')}\n{DIAS_ES[c.weekday()]}"

        pivot.rename(columns=rename,inplace=True)

        st.dataframe(
            pivot.style.map(color_cell),
            use_container_width=True
        )

        # ================================
        # EDITOR TIPO EXCEL REAL
        # ================================
        st.subheader("✏️ Editor tipo Excel (clic en celda)")

        edit_df = st.data_editor(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Turno": st.column_config.SelectboxColumn(
                    "Turno",
                    options=TURNOS
                )
            }
        )

        if st.button("💾 Guardar edición"):
            st.session_state["malla"]=edit_df
            st.success("Cambios guardados")

        # ================================
        # AUDITORÍA
        # ================================
        st.subheader("🚨 Auditoría")

        errores=[]

        for g in GRUPOS:

            prev=None
            gdf=df[df["Grupo"]==g]

            for _,r in gdf.iterrows():

                if prev=="T2" and r["Turno"]=="T1":
                    errores.append(f"{g} salto T2→T1 {r['Fecha']}")

                if prev=="T3" and r["Turno"] in ["T1","T2"]:
                    errores.append(f"{g} salto T3 inválido {r['Fecha']}")

                prev=r["Turno"]

        if errores:
            st.error("Saltos indebidos")
            st.write(errores)
        else:
            st.success("Sin saltos indebidos")

        # ================================
        # COBERTURA
        # ================================
        st.subheader("📈 Cobertura")

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
