# logic_programador.py
# =========================================================
# OPTIMIZADOR INTELIGENTE PRO ENTERPRISE - CORREGIDO
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
TURNOS_PRINCIPALES = ["T1","T2","T3"]

GRUPOS = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]
DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]

festivos_co = holidays.Colombia()

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
# COLORES
# =========================================================
def color_cell(v):
    return {
        "T1":"background-color:#D6EAF8;",
        "T2":"background-color:#D5F5E3;",
        "T3":"background-color:#FADBD8;",
        "T1 APOYO":"background-color:#EAF2F8;",
        "T2 APOYO":"background-color:#EBF5FB;",
        "DESCANSO":"background-color:#2C3E50;color:#F9E79F;font-weight:700;",
        "COMPENSADO":"background-color:#FDEBD0;"
    }.get(v,"")

# =========================================================
# AUDITORIA
# =========================================================
def auditoria(df):

    errores = []
    df = df.copy()
    df["Fecha"] = pd.to_datetime(df["Fecha"])

    # cobertura diaria
    for fecha, grupo in df.groupby("Fecha"):

        turnos = grupo["Turno"].tolist()

        if "T1" not in turnos:
            errores.append(f"❌ Falta T1 {fecha.date()}")
        if "T2" not in turnos:
            errores.append(f"❌ Falta T2 {fecha.date()}")
        if "T3" not in turnos:
            errores.append(f"❌ Falta T3 {fecha.date()}")

    # saltos por grupo
    for g in GRUPOS:

        gdf = df[df["Grupo"] == g].sort_values("Fecha")

        prev = None

        for _, r in gdf.iterrows():

            if prev == "T2" and r["Turno"] == "T1":
                errores.append(f"{g} salto T2→T1 {r['Fecha'].date()}")

            if prev == "T3" and r["Turno"] in ["T1","T2"]:
                errores.append(f"{g} salto T3→alto {r['Fecha'].date()}")

            prev = r["Turno"]

    return errores

# =========================================================
# GENERADOR CORREGIDO
# =========================================================
def generar_malla():

    st.header("🚀 OPTIMIZADOR PRO - ESTABLE")

    c1,c2 = st.columns(2)

    inicio = c1.date_input("Inicio", date.today())
    fin = c2.date_input("Fin", date.today() + timedelta(days=30))

    descanso = {}
    cols = st.columns(len(GRUPOS))

    for i,g in enumerate(GRUPOS):
        descanso[g] = cols[i].selectbox(g, DIAS_ES, index=i)

    filas = []

    if st.button("🚀 Generar malla"):

        fechas = pd.date_range(inicio, fin)

        # tracking diario GLOBAL (clave del fix)
        estado_dia = {t: None for t in TURNOS_PRINCIPALES}

        for fecha in fechas:

            dia = DIAS_ES[fecha.weekday()]
            festivo = fecha.date() in festivos_co

            asignados = {}

            disponibles = GRUPOS.copy()

            # ============================
            # DESCANSOS
            # ============================
            descansan = [g for g in GRUPOS if descanso[g] == dia]

            for g in descansan:
                asignados[g] = "DESCANSO"
                if g in disponibles:
                    disponibles.remove(g)

            # ============================
            # ASIGNACIÓN PRINCIPAL GLOBAL
            # (CLAVE: NO DUPLICADOS)
            # ============================

            for turno in TURNOS_PRINCIPALES:

                if disponibles:

                    g = disponibles.pop(0)

                    asignados[g] = turno

                    estado_dia[turno] = g

            # ============================
            # APOYOS / COMPENSADO
            # ============================

            for g in disponibles:

                asignados[g] = "T1 APOYO"

            # ============================
            # GUARDAR
            # ============================

            for g in GRUPOS:

                filas.append({
                    "Fecha": fecha,
                    "Día": dia,
                    "Grupo": g,
                    "Turno": asignados.get(g, "DESCANSO"),
                    "Festivo": "SI" if festivo else "NO"
                })

        df = pd.DataFrame(filas)

        st.session_state["malla"] = df

        guardar_github(df)

        st.success("Malla generada correctamente")

# =========================================================
# UI
# =========================================================
def pantalla_programador():

    op = st.radio("Módulo", ["Programador","Parametrizador"], horizontal=True)

    if op == "Parametrizador":
        st.write("OK")
        return

    generar_malla()

    if "malla" not in st.session_state:
        return

    df = st.session_state["malla"]

    col1,col2 = st.columns([3,1])

    with col1:

        st.subheader("📊 MALLA OPERATIVA")

        pivot = df.pivot(index="Grupo", columns="Fecha", values="Turno")
        pivot = pivot.sort_index(axis=1)

        edit = st.data_editor(
            pivot,
            use_container_width=True,
            num_rows="fixed"
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

        for e in errores[:12]:
            st.error(e)

        if not errores:
            st.success("Todo OK")
