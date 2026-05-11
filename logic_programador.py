# logic_programador.py
# PLANIFICADOR OPERATIVO FINAL CON ROTACIÓN DE FINES DE SEMANA

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


# =========================================================
# DESCANSO ROTATIVO FIN DE SEMANA (CLAVE)
# =========================================================
def rotacion_fines_semana(semana, config_base):

    sabado = config_base["sabado"]
    domingo = config_base["domingo"]

    # 🔁 rotación semanal alterna
    if semana % 2 == 0:
        return {
            "Sábado": domingo,
            "Domingo": sabado
        }

    return {
        "Sábado": sabado,
        "Domingo": domingo
    }


# =========================================================
# PROGRAMADOR
# =========================================================
def generar_malla():

    st.header("📅 Planificador Operativo PRO")

    c1,c2 = st.columns(2)
    inicio = c1.date_input("Inicio", datetime.now())
    fin = c2.date_input("Fin", datetime.now() + timedelta(days=30))

    # =========================================================
    # CONFIG FIN DE SEMANA
    # =========================================================
    st.subheader("Descanso de fin de semana")

    sabado = st.multiselect("Sábado descansan", GRUPOS, default=["Grupo 1","Grupo 2"])
    domingo = st.multiselect("Domingo descansan", GRUPOS, default=["Grupo 3","Grupo 4"])

    config_base = {
        "sabado": sabado,
        "domingo": domingo
    }

    # =========================================================
    # ESTADO OPERATIVO
    # =========================================================
    carga = {g:0 for g in GRUPOS}
    conteo = {g:{"T1":0,"T2":0,"T3":0} for g in GRUPOS}

    # =========================================================
    # GENERAR
    # =========================================================
    if st.button("🚀 Generar malla"):

        fechas = pd.date_range(inicio, fin, freq="D")
        filas = []

        for fecha in fechas:

            dia = DIAS_ES[fecha.weekday()]
            semana = fecha.isocalendar().week
            festivo = fecha.date() in festivos_co

            asignados = {}

            # =================================================
            # ROTACIÓN FIN DE SEMANA
            # =================================================
            config = rotacion_fines_semana(semana, config_base)

            if dia == "Sábado":
                grupos_descanso = config["Sábado"]
            elif dia == "Domingo":
                grupos_descanso = config["Domingo"]
            else:
                grupos_descanso = []

            activos = [g for g in GRUPOS if g not in grupos_descanso]

            for g in grupos_descanso:
                asignados[g] = "DESCANSO"

            # =================================================
            # COBERTURA OBLIGATORIA T1 T2 T3
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
            # APOYO
            # =================================================
            for g in activos:
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

        st.success("Malla generada correctamente")

    # =========================================================
    # MALLA HORIZONTAL (OPERATIVA)
    # =========================================================
    if "malla" in st.session_state:

        st.subheader("📊 Malla horizontal por grupos")

        df = st.session_state["malla"]

        pivot = df.pivot(index="Grupo", columns="Fecha", values="Turno")

        def color(v):
            return {
                "DESCANSO":"background:#FFADAD;font-weight:bold",
                "T1":"background:#CAFFBF",
                "T2":"background:#9BF6FF",
                "T3":"background:#BDB2FF"
            }.get(v,"")

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
        c3.metric("Total registros", len(df))


# =========================================================
# PARAMETRIZADOR
# =========================================================
def parametrizador():

    st.header("🧩 Parametrizador")

    df = pd.DataFrame({"Nombre":["A","B","C","D"],"Grupo":["","","",""]})

    st.dataframe(df)

    if st.button("Asignar grupos"):
        df["Grupo"] = GRUPOS * 10
        st.success("Asignado")


# =========================================================
# MENÚ PRINCIPAL
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
