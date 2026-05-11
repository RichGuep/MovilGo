# logic_programador.py
# SISTEMA COMPLETO: PARAMETRIZADOR + DESCANSO DE LEY + COMPENSADO REAL + MALLA PRO

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
    except Exception as e:
        st.error(f"GitHub error: {e}")
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
# ABORDAJE
# =========================================================
def pantalla_abordaje():
    st.header("🚌 Personal Abordaje")

    df = cargar_excel("abordaje.xlsx")

    if df.empty:
        st.warning("Sin datos")
        return

    st.dataframe(df)

# =========================================================
# 🧩 PARAMETRIZADOR DE GRUPOS (RESTAURADO)
# =========================================================
def parametrizador_grupos():

    st.header("🧩 Parametrizador de grupos")

    df = cargar_excel("empleados.xlsx")

    if df.empty:
        st.warning("No hay empleados cargados")
        return

    if "Grupo" not in df.columns:
        df["Grupo"] = ""

    st.dataframe(df, use_container_width=True)

    grupos = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]

    if st.button("🎲 Asignar grupos aleatorios"):

        df = df.sample(frac=1).reset_index(drop=True)

        asignacion = {}

        i = 0
        for nombre in df["Nombre"]:
            asignacion[nombre] = grupos[i % len(grupos)]
            i += 1

        df["Grupo"] = df["Nombre"].map(asignacion)

        guardar_excel(df, "empleados.xlsx")

        st.success("Grupos asignados correctamente")
        st.dataframe(df, use_container_width=True)

# =========================================================
# PROGRAMADOR TÉCNICOS
# =========================================================
def generar_malla_tecnicos():

    st.header("📅 Programador Técnico PRO")

    c1,c2 = st.columns(2)
    inicio = c1.date_input("Inicio", datetime.now())
    fin = c2.date_input("Fin", datetime.now() + timedelta(days=28))

    # =========================================================
    # DESCANSO DE LEY
    # =========================================================
    st.subheader("Descanso de ley")

    descanso = {}
    cols = st.columns(4)

    for i,g in enumerate(["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]):
        descanso[g] = cols[i].selectbox(g, DIAS_ES, index=i)

    if "base_descanso" not in st.session_state:
        st.session_state["base_descanso"] = descanso.copy()

    # =========================================================
    # ROTACIÓN
    # =========================================================
    if st.button("🔁 Rotar descanso mensual"):

        base = st.session_state["base_descanso"]

        nuevo = {}
        for g in base:
            idx = DIAS_ES.index(base[g])
            nuevo[g] = DIAS_ES[(idx+1)%7]

        st.session_state["base_descanso"] = nuevo
        st.success("Rotación aplicada")

    # =========================================================
    # ESTADO
    # =========================================================
    carga = {g:0 for g in st.session_state["base_descanso"]}
    conteo = {g:{"T1":0,"T2":0,"T3":0} for g in st.session_state["base_descanso"]}
    deuda = {g:0 for g in st.session_state["base_descanso"]}
    compensado = {g:0 for g in st.session_state["base_descanso"]}

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
            # RESET SEMANA → COMPENSADO REAL
            # =================================================
            if semana != semana_actual:
                semana_actual = semana

                for g in deuda:
                    if deuda[g] > 0:
                        compensado[g] += deuda[g]
                        deuda[g] = 0

            # =================================================
            # DESCANSO DE LEY (MANDATORIO)
            # =================================================
            for g in descanso:

                if descanso[g] == dia and not festivo:

                    asignados[g] = "DESCANSO"

                else:

                    activos.append(g)

                    # si era su día de ley y no descansó → genera deuda
                    if descanso[g] == dia:
                        deuda[g] += 1

            # =================================================
            # TURNOS PRINCIPALES
            # =================================================
            for turno in ["T1","T2","T3"]:

                candidatos = [(carga[g], conteo[g][turno], g) for g in activos]

                if not candidatos:
                    candidatos = [(0,0,g) for g in activos]

                candidatos.sort()

                sel = candidatos[0][2]

                asignados[sel] = turno

                carga[sel] += 1
                conteo[sel][turno] += 1

                if sel in activos:
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
            for g in descanso:

                filas.append({
                    "Fecha": fecha.strftime("%Y-%m-%d"),
                    "Día": dia,
                    "Grupo": g,
                    "Turno": asignados.get(g,"T1 APOYO"),
                    "Festivo": "SI" if festivo else "NO"
                })

        df = pd.DataFrame(filas)

        st.session_state["malla"] = df
        guardar_excel(df, "malla_historica.xlsx")

        st.success("Malla generada correctamente")

        # =========================================================
        # DASHBOARD
        # =========================================================
        st.subheader("📊 Dashboard")

        c1,c2,c3 = st.columns(3)

        c1.metric("Operativos", len(df[df["Turno"].isin(["T1","T2","T3"])]))
        c2.metric("Descansos", len(df[df["Turno"]=="DESCANSO"]))
        c3.metric("Compensados", len(df[df["Turno"]=="COMPENSADO"]))

        st.bar_chart(df.groupby(["Grupo","Turno"]).size().unstack(fill_value=0))

# =========================================================
# MENÚ PRINCIPAL
# =========================================================
def pantalla_programador():

    mod = st.radio(
        "Módulo",
        ["Programador Técnicos","Parametrizador","Abordaje"],
        horizontal=True
    )

    if mod == "Programador Técnicos":
        generar_malla_tecnicos()

    elif mod == "Parametrizador":
        parametrizador_grupos()

    else:
        pantalla_abordaje()
