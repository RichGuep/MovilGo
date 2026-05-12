# logic_programador.py
# =========================================================
# OPTIMIZADOR INTELIGENTE PRO ENTERPRISE - REACTIVO
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
# COLORES SUAVES
# =========================================================
def color_cell(v):
    return {
        "T1":"background-color:#D6EAF8;",
        "T2":"background-color:#D5F5E3;",
        "T3":"background-color:#FADBD8;",

        "T1 APOYO":"background-color:#EBF5FB;",
        "T2 APOYO":"background-color:#EAF2F8;",

        "DESCANSO":"background-color:#2C3E50;color:#F9E79F;font-weight:700;",
        "COMPENSADO":"background-color:#FDEBD0;font-weight:600;"
    }.get(v,"")

# =========================================================
# PARAMETRIZADOR
# =========================================================
def parametrizador():

    st.header("🧩 Parametrizador")

    df = pd.DataFrame({
        "Empleado":["A","B","C","D"],
        "Grupo":["","","",""]
    })

    st.dataframe(df, use_container_width=True)

# =========================================================
# AUDITORÍA REACTIVA
# =========================================================
def auditoria(df):

    errores = []

    for g in GRUPOS:

        prev = None
        gdf = df[df["Grupo"] == g].sort_values("Fecha")

        for _, r in gdf.iterrows():

            if prev == "T2" and r["Turno"] == "T1":
                errores.append(f"{g} salto T2→T1 {r['Fecha'].date()}")

            if prev == "T3" and r["Turno"] in ["T1","T2"]:
                errores.append(f"{g} salto T3→alto {r['Fecha'].date()}")

            prev = r["Turno"]

    return errores

# =========================================================
# GENERADOR + EDITOR
# =========================================================
def generar_malla():

    st.header("🚀 OPTIMIZADOR INTELIGENTE PRO")

    # =========================
    # FECHAS
    # =========================
    c1,c2 = st.columns(2)

    inicio = c1.date_input("Inicio", date.today())
    fin = c2.date_input("Fin", date.today()+timedelta(days=30))

    # =========================
    # DESCANSO DE LEY
    # =========================
    st.subheader("⚖️ Descanso de ley")

    descanso = {}
    cols = st.columns(len(GRUPOS))

    for i,g in enumerate(GRUPOS):
        descanso[g] = cols[i].selectbox(g, DIAS_ES, index=i, key=f"d_{g}")

    # =========================
    # ESTADO
    # =========================
    carga = {g:0 for g in GRUPOS}
    conteo = {g:{"T1":0,"T2":0,"T3":0} for g in GRUPOS}
    compensado = {g:0 for g in GRUPOS}
    sacrificio = {g:0 for g in GRUPOS}

    # =========================
    # GENERAR
    # =========================
    if st.button("🚀 Generar malla"):

        filas = []
        fechas = pd.date_range(inicio, fin)

        for f in fechas:

            dia = DIAS_ES[f.weekday()]
            festivo = f.date() in festivos_co

            asignados = {}

            descanso_grupos = [g for g in GRUPOS if descanso[g]==dia]
            activos = [g for g in GRUPOS if g not in descanso_grupos]

            # COBERTURA MÍNIMA
            while len(activos) < 3:

                mov = sorted(descanso_grupos, key=lambda g:(sacrificio[g],carga[g]))[0]
                descanso_grupos.remove(mov)
                activos.append(mov)

                sacrificio[mov]+=1
                compensado[mov]+=1

            # DESCANSO
            for g in descanso_grupos:
                asignados[g]="DESCANSO"

            # TURNOS BASE
            for t in ["T1","T2","T3"]:

                sel = sorted(activos, key=lambda g:(carga[g],conteo[g][t]))[0]
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

        st.session_state["df"]=pd.DataFrame(filas)

    # =========================
    # VISUAL + EDITOR + ALERTAS
    # =========================
    if "df" in st.session_state:

        df = st.session_state["df"]

        # ---------------------
        # PIVOT HORIZONTAL
        # ---------------------
        pivot = df.pivot(index="Grupo", columns="Fecha", values="Turno")

        pivot.columns = [
            f"{c.strftime('%d-%m')}\n{DIAS_ES[c.weekday()]}"
            for c in pivot.columns
        ]

        # =========================
        # LAYOUT
        # =========================
        col1,col2 = st.columns([3,1])

        with col1:

            st.subheader("📊 Malla editable")

            edited = st.data_editor(
                pivot,
                use_container_width=True,
                key="editor",
                column_config={
                    c: st.column_config.SelectboxColumn(
                        c,
                        options=TURNOS
                    )
                    for c in pivot.columns
                }
            )

            if st.button("💾 Guardar cambios"):

                tmp = edited.reset_index()

                long = tmp.melt(
                    id_vars=["Grupo"],
                    var_name="Fecha",
                    value_name="Turno"
                )

                st.session_state["df"]=long

                st.rerun()

            st.dataframe(
                edited.style.map(color_cell),
                use_container_width=True
            )

        # =========================
        # ALERTAS DINÁMICAS
        # =========================
        with col2:

            st.subheader("🚨 Auditoría")

            errores = auditoria(df)

            if not errores:
                st.success("Sin errores")

            else:
                st.warning(f"{len(errores)} alertas activas")

                for e in errores:
                    st.error(e)

        # =========================
        # COBERTURA
        # =========================
        st.subheader("📈 Cobertura T1/T2/T3")

        cov = df[df["Turno"].isin(["T1","T2","T3"])].groupby("Fecha").size()

        st.line_chart(cov)

        # =========================
        # BALANCE
        # =========================
        st.subheader("⚖️ Balance por grupo")

        st.dataframe(
            df.groupby(["Grupo","Turno"]).size().unstack(fill_value=0),
            use_container_width=True
        )

# =========================================================
# MENU
# =========================================================
def pantalla_programador():

    op = st.radio("Módulo",["Programador","Parametrizador"],horizontal=True)

    if op=="Programador":
        generar_malla()
    else:
        parametrizador()
