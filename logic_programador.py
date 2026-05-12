# logic_programador.py
# =========================================================
# OPTIMIZADOR INTELIGENTE PRO ENTERPRISE - ESTABLE
# =========================================================

import streamlit as st
import pandas as pd
from datetime import date, timedelta
import holidays
import io
from github import Github

# =========================================================
# CONFIG
# =========================================================
TURNOS = ["T1","T2","T3","T1 APOYO","T2 APOYO","DESCANSO","COMPENSADO"]

GRUPOS = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]

DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]

festivos_co = holidays.Colombia()

# =========================================================
# HORARIOS (solo para programación detallada)
# =========================================================
HORARIOS = {
    "T1": ("05:30","12:50"),
    "T2": ("13:30","20:50"),
    "T3": ("21:30","04:50")
}

# =========================================================
# GITHUB
# =========================================================
def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            return None
        return Github(st.secrets["GITHUB_TOKEN"]).get_repo("RichGuep/movilgo")
    except:
        return None


def guardar_github(df):
    repo = conectar_github()
    if not repo:
        return

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    data = buffer.getvalue()

    try:
        file = repo.get_contents("malla_historica.xlsx")
        repo.update_file("malla_historica.xlsx", "update", data, file.sha)
    except:
        repo.create_file("malla_historica.xlsx", "create", data)

# =========================================================
# COLORES (SOFT)
# =========================================================
def color_cell(v):
    return {
        "T1":"background-color:#D6EAF8;",
        "T2":"background-color:#D5F5E3;",
        "T3":"background-color:#FADBD8;",
        "T1 APOYO":"background-color:#EAF2F8;",
        "T2 APOYO":"background-color:#EBF5FB;",
        "DESCANSO":"background-color:#2C3E50;color:#F9E79F;",
        "COMPENSADO":"background-color:#FDEBD0;"
    }.get(v,"")

# =========================================================
# AUDITORIA
# =========================================================
def auditoria(df):

    errores = []
    df = df.copy()
    df["Fecha"] = pd.to_datetime(df["Fecha"])

    for fecha, grupo in df.groupby("Fecha"):

        turnos = grupo["Turno"].tolist()

        for t in ["T1","T2","T3"]:
            if t not in turnos:
                errores.append(f"❌ Falta {t} {fecha.date()}")

    return errores

# =========================================================
# GENERADOR (SIN CAMBIAR LO QUE YA FUNCIONABA)
# =========================================================
def generar_malla():

    st.header("🚀 OPTIMIZADOR INTELIGENTE PRO")

    c1,c2 = st.columns(2)

    inicio = c1.date_input("Inicio", date.today())
    fin = c2.date_input("Fin", date.today()+timedelta(days=30))

    descanso = {}
    cols = st.columns(len(GRUPOS))

    for i,g in enumerate(GRUPOS):
        descanso[g] = cols[i].selectbox(g, DIAS_ES, index=i)

    if st.button("🚀 Generar malla"):

        fechas = pd.date_range(inicio, fin)

        filas = []

        rotacion = ["T1","T2","T3"]

        for i,fecha in enumerate(fechas):

            dia = DIAS_ES[fecha.weekday()]
            festivo = fecha.date() in festivos_co

            asignados = {}
            activos = GRUPOS.copy()

            # descansos
            desc = [g for g in GRUPOS if descanso[g]==dia]

            for g in desc:
                asignados[g] = "DESCANSO"
                if g in activos:
                    activos.remove(g)

            # rotación estable
            offset = (i // 7) % 3

            for j,g in enumerate(activos[:3]):

                asignados[g] = rotacion[(offset+j)%3]

            for g in activos[3:]:

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
        guardar_github(df)

        st.success("Malla generada")

# =========================================================
# PROGRAMACIÓN DETALLADA (NUEVO BLOQUE)
# =========================================================
def programacion_detallada(df):

    st.subheader("📋 Programación detallada")

    detalle = []

    for _,r in df.iterrows():

        turno = r["Turno"]

        if turno in HORARIOS:

            inicio, fin = HORARIOS[turno]
        else:
            inicio, fin = "",""

        detalle.append({
            "Fecha": r["Fecha"],
            "Grupo": r["Grupo"],
            "Turno": turno,
            "Hora inicio": inicio,
            "Hora fin": fin
        })

    st.dataframe(pd.DataFrame(detalle), use_container_width=True)

# =========================================================
# UI PRINCIPAL
# =========================================================
def pantalla_programador():

    generar_malla()

    if "malla" not in st.session_state:
        return

    df = st.session_state["malla"]

    col1,col2 = st.columns([3,1])

    with col1:

        st.subheader("📊 MALLA HORIZONTAL (EDITABLE REAL)")

        pivot = df.pivot(index="Grupo", columns="Fecha", values="Turno")
        pivot = pivot.sort_index(axis=1)

        edit = st.data_editor(
            pivot,
            use_container_width=True
        )

        if st.button("💾 Guardar cambios"):

            df_edit = edit.reset_index().melt(
                id_vars="Grupo",
                var_name="Fecha",
                value_name="Turno"
            )

            df_edit["Fecha"] = pd.to_datetime(df_edit["Fecha"])

            st.session_state["malla"] = df_edit
            guardar_github(df_edit)

            st.success("Guardado")

        st.dataframe(pivot.style.map(color_cell), use_container_width=True)

    with col2:

        st.subheader("🚨 ALERTAS")

        errores = auditoria(df)

        for e in errores[:15]:
            st.error(e)

        if not errores:
            st.success("Sin errores")

    # =====================================================
    # ABAJO: PROGRAMACIÓN DETALLADA
    # =====================================================
    programacion_detallada(df)
