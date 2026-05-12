# logic_programador.py
# =========================================================
# OPTIMIZADOR INTELIGENTE PRO ENTERPRISE - ESTABLE FINAL
# =========================================================

import streamlit as st
import pandas as pd
from datetime import date, timedelta
import holidays
import io
import base64
from github import Github

# =========================================================
# CONFIG
# =========================================================
TURNOS = ["T1","T2","T3","T1 APOYO","T2 APOYO","DESCANSO","COMPENSADO"]

GRUPOS = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]

DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]

festivos_co = holidays.Colombia()

# =========================================================
# HORARIOS (REFERENCIA)
# =========================================================
HORARIOS = {
    "T1": ("05:30","12:50"),
    "T2": ("13:30","20:50"),
    "T3": ("21:30","04:50"),
    "T1 APOYO": ("05:30","12:50"),
    "T2 APOYO": ("13:30","20:50")
}

# =========================================================
# GITHUB (CORREGIDO)
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

    content = buffer.getvalue()

    encoded = base64.b64encode(content).decode("utf-8")

    path = "malla_historica.xlsx"

    try:
        file = repo.get_contents(path)

        repo.update_file(
            path,
            "update malla",
            encoded,
            file.sha
        )

    except:

        repo.create_file(
            path,
            "create malla",
            encoded
        )

# =========================================================
# COLORES SUAVES
# =========================================================
def color_cell(v):

    return {
        "T1":"background-color:#D6EAF8;",
        "T2":"background-color:#D5F5E3;",
        "T3":"background-color:#FADBD8;",
        "T1 APOYO":"background-color:#D6EAF8;",
        "T2 APOYO":"background-color:#D5F5E3;",
        "DESCANSO":"background-color:#2C3E50;color:#F9E79F;",
        "COMPENSADO":"background-color:#FDEBD0;"
    }.get(v,"")

# =========================================================
# AUDITORIA REAL
# =========================================================
def auditoria(df):

    errores = []

    df = df.copy()
    df["Fecha"] = pd.to_datetime(df["Fecha"])

    # ---------------------------
    # COBERTURA
    # ---------------------------
    for fecha, g in df.groupby("Fecha"):

        turnos = set(g["Turno"])

        if "T1" not in turnos and "T1 APOYO" not in turnos:
            errores.append(f"❌ Falta T1 {fecha.date()}")

        if "T2" not in turnos and "T2 APOYO" not in turnos:
            errores.append(f"❌ Falta T2 {fecha.date()}")

        if "T3" not in turnos:
            errores.append(f"❌ Falta T3 {fecha.date()}")

    # ---------------------------
    # SALTOS
    # ---------------------------
    for grupo, gdf in df.groupby("Grupo"):

        gdf = gdf.sort_values("Fecha")

        prev = None

        for _, r in gdf.iterrows():

            if prev == "T2" and r["Turno"] == "T1":
                errores.append(f"{grupo} salto T2→T1 {r['Fecha'].date()}")

            if prev == "T3" and r["Turno"] in ["T1","T2","T1 APOYO","T2 APOYO"]:
                errores.append(f"{grupo} salto T3 inválido {r['Fecha'].date()}")

            prev = r["Turno"]

    return errores

# =========================================================
# GENERADOR INTELIGENTE CON APOYO
# =========================================================
def generar_malla(modo, fijo):

    st.header("🚀 OPTIMIZADOR PRO ENTERPRISE")

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
            disponibles = GRUPOS.copy()

            # DESCANSOS
            desc = [g for g in GRUPOS if descanso[g]==dia]

            for g in desc:
                asignados[g] = "DESCANSO"
                if g in disponibles:
                    disponibles.remove(g)

            # MODO FIJO / ROTACIÓN
            if modo == "Fijo por grupo":

                for idx,g in enumerate(disponibles[:3]):
                    asignados[g] = fijo[g]

            else:

                offset = (i // 7) % 3

                for j,g in enumerate(disponibles[:3]):
                    asignados[g] = rotacion[(offset+j)%3]

            # ---------------------------
            # COBERTURA FALTANTE → APOYO
            # ---------------------------
            turnos_asignados = list(asignados.values())

            faltantes = []

            if "T1" not in turnos_asignados and "T1 APOYO" not in turnos_asignados:
                faltantes.append("T1")

            if "T2" not in turnos_asignados and "T2 APOYO" not in turnos_asignados:
                faltantes.append("T2")

            if "T3" not in turnos_asignados:
                faltantes.append("T3")

            sobrantes = disponibles[3:]

            for f in faltantes:

                if sobrantes:
                    g = sobrantes.pop(0)
                    asignados[g] = f

            for g in sobrantes:
                asignados[g] = "T1 APOYO"

            # guardar
            for g in GRUPOS:

                filas.append({
                    "Fecha": fecha,
                    "Día": dia,
                    "Grupo": g,
                    "Turno": asignados.get(g,"DESCANSO"),
                    "Festivo": "SI" if festivo else "NO"
                })

        df = pd.DataFrame(filas)

        st.session_state["malla"] = df

        guardar_github(df)

        st.success("Malla generada correctamente")

# =========================================================
# PROGRAMACIÓN DETALLADA
# =========================================================
def programacion_detallada(df):

    st.subheader("📋 Programación detallada")

    detalle = []

    for _,r in df.iterrows():

        turno = r["Turno"]

        inicio, fin = HORARIOS.get(turno, ("",""))

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

    modo = st.radio("Modo", ["Rotación","Fijo por grupo"])

    fijo = {}

    if modo == "Fijo por grupo":

        st.subheader("🔒 Turnos fijos")

        cols = st.columns(len(GRUPOS))

        for i,g in enumerate(GRUPOS):
            fijo[g] = cols[i].selectbox(g, ["T1","T2","T3"])

    generar_malla(modo, fijo)

    if "malla" not in st.session_state:
        return

    df = st.session_state["malla"]

    col1,col2 = st.columns([3,1])

    with col1:

        st.subheader("📊 MALLA HORIZONTAL EDITABLE")

        pivot = df.pivot(index="Grupo", columns="Fecha", values="Turno")

        edit = st.data_editor(
            pivot,
            use_container_width=True
        )

        if st.button("💾 Guardar"):

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
            st.success("OK")

    programacion_detallada(df)
