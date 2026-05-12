# logic_programador.py
# =========================================================
# OPTIMIZADOR INTELIGENTE PRO ENTERPRISE - HORIZONTAL REAL
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
TURNOS = [
    "T1", "T2", "T3",
    "T1 APOYO", "T2 APOYO",
    "DESCANSO", "COMPENSADO"
]

GRUPOS = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]

DIAS_ES = [
    "Lunes", "Martes", "Miércoles",
    "Jueves", "Viernes", "Sábado", "Domingo"
]

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
# COLORES SUAVES
# =========================================================
def color_cell(v):

    return {
        "T1": "background-color:#D6EAF8;",
        "T2": "background-color:#D5F5E3;",
        "T3": "background-color:#FADBD8;",

        "T1 APOYO": "background-color:#EBF5FB;",
        "T2 APOYO": "background-color:#EAF2F8;",

        "DESCANSO": "background-color:#2C3E50;color:#F9E79F;font-weight:700;",

        "COMPENSADO": "background-color:#FDEBD0;"
    }.get(v, "")

# =========================================================
# AUDITORÍA
# =========================================================
def auditoria(df):

    errores = []
    df = df.copy()

    # seguridad fechas
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")

    # =====================================================
    # COBERTURA DIARIA (T1/T2/T3)
    # =====================================================
    cobertura = df[df["Turno"].isin(["T1", "T2", "T3"])] \
        .groupby("Fecha").size()

    for f, c in cobertura.items():
        if c < 3:
            errores.append(f"❌ Cobertura incompleta {f.date()} ({c}/3)")

    # =====================================================
    # SALTOS INDEBIDOS
    # =====================================================
    for g in GRUPOS:

        gdf = df[df["Grupo"] == g].sort_values("Fecha")

        prev = None

        for _, r in gdf.iterrows():

            if prev == "T2" and r["Turno"] == "T1":
                errores.append(f"{g} salto T2→T1 {r['Fecha'].date()}")

            if prev == "T3" and r["Turno"] in ["T1", "T2"]:
                errores.append(f"{g} salto T3→alto {r['Fecha'].date()}")

            prev = r["Turno"]

    return errores, cobertura

# =========================================================
# GENERADOR
# =========================================================
def generar_malla():

    st.header("🚀 OPTIMIZADOR INTELIGENTE PRO")

    c1, c2 = st.columns(2)

    inicio = c1.date_input("Inicio", date.today())
    fin = c2.date_input("Fin", date.today() + timedelta(days=30))

    # =====================================================
    # DESCANSO DE LEY
    # =====================================================
    st.subheader("⚖️ Descanso de ley")

    descanso = {}
    cols = st.columns(len(GRUPOS))

    for i, g in enumerate(GRUPOS):
        descanso[g] = cols[i].selectbox(g, DIAS_ES, index=i)

    # =====================================================
    # ESTADO
    # =====================================================
    carga = {g: 0 for g in GRUPOS}
    conteo = {g: {"T1": 0, "T2": 0, "T3": 0} for g in GRUPOS}

    compensado = {g: 0 for g in GRUPOS}
    sacrificio = {g: 0 for g in GRUPOS}

    filas = []

    # =====================================================
    # GENERACIÓN
    # =====================================================
    if st.button("🚀 Generar malla"):

        fechas = pd.date_range(inicio, fin)

        for fecha in fechas:

            dia = DIAS_ES[fecha.weekday()]
            festivo = fecha.date() in festivos_co

            asignados = {}

            descanso_dia = [g for g in GRUPOS if descanso[g] == dia]
            activos = [g for g in GRUPOS if g not in descanso_dia]

            # =================================================
            # COBERTURA MÍNIMA 3
            # =================================================
            while len(activos) < 3:

                mov = sorted(descanso_dia, key=lambda g: (sacrificio[g], carga[g]))[0]

                descanso_dia.remove(mov)
                activos.append(mov)

                sacrificio[mov] += 1
                compensado[mov] += 1

            # =================================================
            # DESCANSOS
            # =================================================
            for g in descanso_dia:
                asignados[g] = "DESCANSO"

            # =================================================
            # TURNOS PRINCIPALES
            # =================================================
            for turno in ["T1", "T2", "T3"]:

                sel = sorted(activos, key=lambda g: (carga[g], conteo[g][turno]))[0]

                asignados[sel] = turno
                carga[sel] += 1
                conteo[sel][turno] += 1
                activos.remove(sel)

            # =================================================
            # COMPENSADO / APOYO
            # =================================================
            for g in activos:

                if compensado[g] > 0:
                    asignados[g] = "COMPENSADO"
                    compensado[g] -= 1
                else:
                    asignados[g] = "T1 APOYO"

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
        st.session_state["malla"] = df

        guardar_github(df)

        st.success("Malla generada y guardada")

# =========================================================
# INTERFAZ PRINCIPAL
# =========================================================
def pantalla_programador():

    op = st.radio("Módulo", ["Programador", "Parametrizador"], horizontal=True)

    if op == "Parametrizador":
        st.info("Módulo en expansión")
        return

    generar_malla()

    if "malla" not in st.session_state:
        return

    df = st.session_state["malla"]

    # =====================================================
    # PIVOT HORIZONTAL REAL
    # =====================================================
    pivot = df.pivot(index="Grupo", columns="Fecha", values="Turno").sort_index(axis=1)

    # =====================================================
    # LAYOUT CONTROL CENTER
    # =====================================================
    col1, col2 = st.columns([3, 1])

    # =====================================================
    # MALLA + EDITOR
    # =====================================================
    with col1:

        st.subheader("📊 Malla Operativa")

        st.dataframe(
            pivot.style.map(color_cell),
            use_container_width=True
        )

        st.subheader("✏️ Editor directo")

        edit = st.data_editor(
            df,
            use_container_width=True,
            column_config={
                "Turno": st.column_config.SelectboxColumn(
                    "Turno",
                    options=TURNOS
                )
            }
        )

        st.session_state["malla"] = edit

    # =====================================================
    # PANEL DERECHO
    # =====================================================
    with col2:

        st.subheader("🚨 Alertas")

        errores, cobertura = auditoria(edit)

        if errores:
            for e in errores[:15]:
                st.caption(f"⚠️ {e}")
        else:
            st.success("Sin alertas")

        st.divider()

        st.subheader("📈 Cobertura")

        st.line_chart(cobertura, height=180)

        st.divider()

        st.caption("✔ Sistema activo")
        st.caption("✔ Auditoría en tiempo real")
        st.caption("✔ Editor sincronizado")
