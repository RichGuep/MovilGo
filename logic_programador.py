# logic_programador.py
# =========================================================
# OPTIMIZADOR INTELIGENTE PRO ENTERPRISE - CON HORARIOS
# =========================================================

import streamlit as st
import pandas as pd
from datetime import date, timedelta
import holidays
import io
from github import Github

# =========================================================
# CONFIG TURNOS + HORARIOS
# =========================================================
TURNOS = ["T1","T2","T3","T1 APOYO","T2 APOYO","DESCANSO","COMPENSADO"]

TURNOS_PRINCIPALES = ["T1","T2","T3"]

HORARIOS = {
    "T1": "05:30 - 12:50",
    "T2": "13:30 - 20:50",
    "T3": "21:30 - 04:50"
}

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
        "DESCANSO":"background-color:#2C3E50;color:#F9E79F;",
        "COMPENSADO":"background-color:#FDEBD0;"
    }.get(v,"")

# =========================================================
# MODOS
# =========================================================
MODOS = ["Rotación semanal","Fijo quincenal","Fijo mensual"]

# =========================================================
# AUDITORIA CON HORARIOS
# =========================================================
def auditoria(df):

    errores = []
    df = df.copy()
    df["Fecha"] = pd.to_datetime(df["Fecha"])

    for fecha, grupo in df.groupby("Fecha"):

        turnos = grupo["Turno"].tolist()

        for t in TURNOS_PRINCIPALES:
            if t not in turnos:
                errores.append(f"❌ Falta {t} {fecha.date()}")

    return errores

# =========================================================
# GENERADOR
# =========================================================
def generar_malla(modo):

    st.header("🚀 OPTIMIZADOR PRO - HORARIOS OPERATIVOS")

    c1,c2 = st.columns(2)

    inicio = c1.date_input("Inicio", date.today())
    fin = c2.date_input("Fin", date.today()+timedelta(days=30))

    # =========================
    # HORARIOS VISUALES
    # =========================
    st.subheader("⏰ Horarios definidos")

    st.info(f"""
    - **T1:** {HORARIOS['T1']}  
    - **T2:** {HORARIOS['T2']}  
    - **T3:** {HORARIOS['T3']}
    """)

    # =========================
    # DESCANSOS
    # =========================
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
            descansan = [g for g in GRUPOS if descanso[g]==dia]

            for g in descansan:
                asignados[g]="DESCANSO"
                if g in disponibles:
                    disponibles.remove(g)

            # ROTACIÓN CONTROLADA
            if modo == "Rotación semanal":
                offset = (i // 7) % 3
            elif modo == "Fijo quincenal":
                offset = (i // 15) % 3
            else:
                offset = (i // 30) % 3

            # ASIGNACIÓN PRINCIPAL
            for j,g in enumerate(disponibles[:3]):

                turno = rotacion[(offset + j) % 3]

                asignados[g] = f"{turno} ({HORARIOS[turno]})"

            # APOYOS
            for g in disponibles[3:]:

                asignados[g] = "T1 APOYO"

            # GUARDAR
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
# UI PRINCIPAL
# =========================================================
def pantalla_programador():

    modo = st.radio("Modo de planificación", MODOS)

    generar_malla(modo)

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

        for e in errores[:12]:
            st.error(e)

        if not errores:
            st.success("Sin errores")

        st.subheader("⏰ Referencia horarios")

        st.write(HORARIOS)
