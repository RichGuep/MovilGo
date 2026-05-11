# logic_programador.py
# SISTEMA FINAL CORREGIDO: ESPAÑOL + DESCANSO DE LEY REAL

import streamlit as st
import pandas as pd
import io
from datetime import datetime, timedelta
from github import Github
import holidays

# =========================================================
# CONFIG
# =========================================================
TURNOS = ["T1","T2","T3","T1 APOYO","T2 APOYO","DESCANSO","COMPENSADO"]

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


def cargar_excel(nombre):
    repo = conectar_github()
    if not repo:
        return pd.DataFrame()
    try:
        c = repo.get_contents(nombre)
        return pd.read_excel(io.BytesIO(c.decoded_content))
    except:
        return pd.DataFrame()


def guardar_excel(df, nombre):
    repo = conectar_github()
    if not repo:
        return

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    data = buffer.getvalue()

    try:
        c = repo.get_contents(nombre)
        repo.update_file(nombre, "update", data, c.sha)
    except:
        repo.create_file(nombre, "create", data)

# =========================================================
# PARAMETRIZADOR
# =========================================================
def parametrizador():

    st.header("🧩 Parametrizador")

    df = cargar_excel("empleados.xlsx")

    if df.empty:
        st.warning("Sin datos")
        return

    if "Grupo" not in df.columns:
        df["Grupo"] = ""

    st.dataframe(df)

    if st.button("Asignar grupos"):

        df = df.sample(frac=1).reset_index(drop=True)

        for i,n in enumerate(df["Nombre"]):
            df.loc[df["Nombre"]==n,"Grupo"] = GRUPOS[i % len(GRUPOS)]

        guardar_excel(df, "empleados.xlsx")

        st.success("Grupos asignados")

# =========================================================
# PROGRAMADOR
# =========================================================
def generar_malla():

    st.header("📅 Malla Operativa PRO")

    c1,c2 = st.columns(2)
    inicio = c1.date_input("Inicio", datetime.now())
    fin = c2.date_input("Fin", datetime.now() + timedelta(days=30))

    # =========================================================
    # DESCANSO DE LEY (FIJO)
    # =========================================================
    st.subheader("Descanso de ley")

    descanso = {}
    cols = st.columns(4)

    for i,g in enumerate(GRUPOS):
        descanso[g] = cols[i].selectbox(g, DIAS_ES, index=i)

    if "base_descanso" not in st.session_state:
        st.session_state["base_descanso"] = descanso.copy()

    if st.button("Rotar"):
        base = st.session_state["base_descanso"]

        st.session_state["base_descanso"] = {
            g: DIAS_ES[(DIAS_ES.index(base[g]) + 1) % 7]
            for g in GRUPOS
        }

    # =========================================================
    # ESTADO
    # =========================================================
    carga = {g:0 for g in GRUPOS}
    conteo = {g:{"T1":0,"T2":0,"T3":0} for g in GRUPOS}
    deuda = {g:0 for g in GRUPOS}
    compensado = {g:0 for g in GRUPOS}

    # =========================================================
    # GENERACIÓN
    # =========================================================
    if st.button("Generar malla"):

        fechas = pd.date_range(inicio, fin, freq="D")
        filas = []

        semana_actual = None
        descanso = st.session_state["base_descanso"]

        for fecha in fechas:

            dia = DIAS_ES[fecha.weekday()]
            semana = fecha.isocalendar().week
            festivo = fecha.date() in festivos_co

            asignados = {}
            activos = []

            # RESET SEMANA
            if semana != semana_actual:
                semana_actual = semana

                for g in GRUPOS:
                    if deuda[g] > 0:
                        compensado[g] += deuda[g]
                        deuda[g] = 0

            # =================================================
            # DESCANSO DE LEY (NO SE TOCA)
            # =================================================
            for g in GRUPOS:

                if descanso[g] == dia and not festivo:
                    asignados[g] = "DESCANSO"
                else:
                    activos.append(g)

                    if descanso[g] == dia:
                        deuda[g] += 1

            # =================================================
            # TURNOS
            # =================================================
            for turno in ["T1","T2","T3"]:

                candidatos = [(carga[g], conteo[g][turno], g) for g in activos]

                if not candidatos:
                    continue

                candidatos.sort()

                sel = candidatos[0][2]

                asignados[sel] = turno

                carga[sel] += 1
                conteo[sel][turno] += 1

                activos.remove(sel)

            # =================================================
            # COMPENSADO
            # =================================================
            for g in activos:

                if compensado[g] > 0:
                    asignados[g] = "COMPENSADO"
                    compensado[g] -= 1
                else:
                    asignados[g] = "T1 APOYO"

            # =================================================
            # GUARDADO
            # =================================================
            for g in GRUPOS:

                filas.append({
                    "Fecha": fecha,
                    "Grupo": g,
                    "Día": dia,   # 👈 ESPAÑOL REAL FIJO
                    "Turno": asignados.get(g,"T1 APOYO"),
                    "Festivo": "SI" if festivo else "NO"
                })

        df = pd.DataFrame(filas)

        st.session_state["malla"] = df

        guardar_excel(df, "malla_historica.xlsx")

        st.success("Malla generada")

    # =========================================================
    # MALLA HORIZONTAL
    # =========================================================
    if "malla" in st.session_state:

        st.subheader("📊 Malla horizontal")

        df = st.session_state["malla"]

        pivot = df.pivot(index="Grupo", columns="Fecha", values="Turno")

        # ✔ DÍAS EN ESPAÑOL (FIX REAL)
        dias_por_fecha = df.drop_duplicates("Fecha")[["Fecha","Día"]]

        columnas = {}

        for f in pivot.columns:
            dia = dias_por_fecha[dias_por_fecha["Fecha"]==f]["Día"].values[0]
            columnas[f] = f.strftime("%d-%m") + "\n" + dia

        pivot.rename(columns=columnas, inplace=True)

        def color(v):
            return {
                "DESCANSO":"background:#FFADAD",
                "COMPENSADO":"background:#FFD6A5",
                "T1":"background:#CAFFBF",
                "T2":"background:#9BF6FF",
                "T3":"background:#BDB2FF"
            }.get(v,"")

        st.dataframe(pivot.style.map(color), use_container_width=True)

        # =====================================================
        # DASHBOARD
        # =====================================================
        st.subheader("📊 Dashboard")

        c1,c2,c3 = st.columns(3)

        c1.metric("Operativos", len(df[df["Turno"].isin(["T1","T2","T3"])]))
        c2.metric("Descanso", len(df[df["Turno"]=="DESCANSO"]))
        c3.metric("Compensado", len(df[df["Turno"]=="COMPENSADO"]))

# =========================================================
# MENU
# =========================================================
def pantalla_programador():

    mod = st.radio(
        "Módulo",
        ["Programador","Parametrizador"],
        horizontal=True
    )

    if mod == "Programador":
        generar_malla()

    else:
        parametrizador()
