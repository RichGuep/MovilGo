# logic_programador.py
# SISTEMA COMPLETO FINAL: PLANIFICADOR OPERATIVO COLOMBIA

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
            st.error("❌ Falta GITHUB_TOKEN")
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
# 🧩 PARAMETRIZADOR
# =========================================================
def parametrizador():

    st.header("🧩 Parametrizador de Grupos")

    df = cargar_excel("empleados.xlsx")

    if df.empty:
        st.warning("No hay empleados")
        return

    if "Grupo" not in df.columns:
        df["Grupo"] = ""

    st.dataframe(df, use_container_width=True)

    if st.button("🎲 Asignar grupos aleatorios"):

        df = df.sample(frac=1).reset_index(drop=True)

        asignacion = {}

        for i, nombre in enumerate(df["Nombre"]):
            asignacion[nombre] = GRUPOS[i % len(GRUPOS)]

        df["Grupo"] = df["Nombre"].map(asignacion)

        guardar_excel(df, "empleados.xlsx")

        st.success("Grupos asignados")
        st.dataframe(df, use_container_width=True)

# =========================================================
# 🚌 ABORDAJE
# =========================================================
def abordaje():

    st.header("🚌 Abordaje")

    df = cargar_excel("abordaje.xlsx")

    if df.empty:
        st.warning("Sin datos")
        return

    st.dataframe(df)

# =========================================================
# 📅 PROGRAMADOR PRINCIPAL
# =========================================================
def generar_malla():

    st.header("📅 Malla Operativa PRO")

    c1,c2 = st.columns(2)
    inicio = c1.date_input("Inicio", datetime.now())
    fin = c2.date_input("Fin", datetime.now() + timedelta(days=30))

    # =========================================================
    # DESCANSO DE LEY
    # =========================================================
    st.subheader("Descanso de ley")

    descanso = {}
    cols = st.columns(4)

    for i,g in enumerate(GRUPOS):
        descanso[g] = cols[i].selectbox(g, DIAS_ES, index=i)

    if "base_descanso" not in st.session_state:
        st.session_state["base_descanso"] = descanso.copy()

    if st.button("🔁 Rotar descanso mensual"):
        base = st.session_state["base_descanso"]

        nuevo = {}
        for g in GRUPOS:
            idx = DIAS_ES.index(base[g])
            nuevo[g] = DIAS_ES[(idx+1)%7]

        st.session_state["base_descanso"] = nuevo
        st.success("Rotación aplicada")

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
    if st.button("🚀 Generar malla"):

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

            # =================================================
            # RESET SEMANA → COMPENSADO
            # =================================================
            if semana != semana_actual:
                semana_actual = semana

                for g in GRUPOS:
                    if deuda[g] > 0:
                        compensado[g] += deuda[g]
                        deuda[g] = 0

            # =================================================
            # DESCANSO DE LEY
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
                    "Grupo": g,
                    "Día": dia,
                    "Turno": asignados.get(g,"T1 APOYO"),
                    "Festivo": "SI" if festivo else "NO"
                })

        df = pd.DataFrame(filas)

        st.session_state["malla"] = df
        guardar_excel(df, "malla_historica.xlsx")

        st.success("Malla generada correctamente")

    # =========================================================
    # 📊 MALLA HORIZONTAL (VISUAL OPERATIVA)
    # =========================================================
    if "malla" in st.session_state:

        st.subheader("📊 Malla horizontal por grupo")

        df = st.session_state["malla"]

        pivot = df.pivot(index="Grupo", columns="Fecha", values="Turno")

        dias_map = df.drop_duplicates("Fecha")[["Fecha"]].copy()
        dias_map["Dia"] = dias_map["Fecha"].dt.day_name()

        nuevas = {}

        for f in pivot.columns:
            d = dias_map[dias_map["Fecha"]==f]["Dia"].values[0]
            nuevas[f] = f.strftime("%d-%m\n"+d)

        pivot.rename(columns=nuevas, inplace=True)

        def color(v):

            if v == "DESCANSO":
                return "background:#FFADAD;font-weight:bold"

            if v == "COMPENSADO":
                return "background:#FFD6A5"

            if v == "T1":
                return "background:#CAFFBF"

            if v == "T2":
                return "background:#9BF6FF"

            if v == "T3":
                return "background:#BDB2FF"

            return ""

        st.dataframe(
            pivot.style.map(color),
            use_container_width=True
        )

        # =====================================================
        # DASHBOARD
        # =====================================================
        st.subheader("📊 Dashboard")

        c1,c2,c3 = st.columns(3)

        c1.metric("Operativos", len(df[df["Turno"].isin(["T1","T2","T3"])]))
        c2.metric("Descanso", len(df[df["Turno"]=="DESCANSO"]))
        c3.metric("Compensado", len(df[df["Turno"]=="COMPENSADO"]))

# =========================================================
# MENÚ
# =========================================================
def pantalla_programador():

    mod = st.radio(
        "Módulo",
        ["Programador","Parametrizador","Abordaje"],
        horizontal=True
    )

    if mod == "Programador":
        generar_malla()

    elif mod == "Parametrizador":
        parametrizador()

    else:
        abordaje()
