# logic_programador.py
# SISTEMA COMPLETO: DESCANSO + COMPENSADO + FESTIVOS COLOMBIA + MALLA PRO

import streamlit as st
import pandas as pd
import io
from datetime import datetime, timedelta
from github import Github
import holidays

# =========================================================
# CONFIGURACIÓN
# =========================================================
TURNOS = ["T1","T2","T3","T1 APOYO","T2 APOYO","DESCANSO","COMPENSADO"]

GRUPOS_TEC = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]

DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]

# 🇨🇴 FESTIVOS COLOMBIA
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
# PROGRAMADOR
# =========================================================
def generar_malla_tecnicos():

    st.header("📅 Programador Técnico (Colombia PRO)")

    c1,c2 = st.columns(2)
    inicio = c1.date_input("Inicio", datetime.now())
    fin = c2.date_input("Fin", datetime.now() + timedelta(days=28))

    # =========================================================
    # DESCANSO DE LEY
    # =========================================================
    st.subheader("Descanso de ley")

    descanso = {}
    cols = st.columns(4)

    for i,g in enumerate(GRUPOS_TEC):
        descanso[g] = cols[i].selectbox(g, DIAS_ES, index=i)

    if "base_descanso" not in st.session_state:
        st.session_state["base_descanso"] = descanso.copy()

    # =========================================================
    # ROTACIÓN
    # =========================================================
    if st.button("🔁 Rotar descanso mensual"):

        base = st.session_state["base_descanso"]

        nuevo = {}
        for g in GRUPOS_TEC:
            idx = DIAS_ES.index(base[g])
            nuevo[g] = DIAS_ES[(idx+1)%7]

        st.session_state["base_descanso"] = nuevo
        st.success("Rotación aplicada")

    # =========================================================
    # ESTADO
    # =========================================================
    carga = {g:0 for g in GRUPOS_TEC}
    conteo = {g:{"T1":0,"T2":0,"T3":0} for g in GRUPOS_TEC}
    compensado = {g:0 for g in GRUPOS_TEC}
    incumplimiento = {g:0 for g in GRUPOS_TEC}

    # =========================================================
    # GENERACIÓN
    # =========================================================
    if st.button("🚀 Generar malla"):

        fechas = pd.date_range(inicio, fin, freq="D")
        filas = []

        semana_actual = None

        descanso = st.session_state["base_descanso"]

        for fecha in fechas:

            dia_es = DIAS_ES[fecha.weekday()]
            semana = fecha.isocalendar().week

            es_festivo = fecha.date() in festivos_co

            asignados = {}
            activos = []

            # =================================================
            # RESET SEMANA
            # =================================================
            if semana != semana_actual:
                semana_actual = semana

                for g in GRUPOS_TEC:
                    if incumplimiento[g] > 0:
                        compensado[g] += incumplimiento[g]
                        incumplimiento[g] = 0

            # =================================================
            # DESCANSO DE LEY
            # =================================================
            for g in GRUPOS_TEC:

                if descanso[g] == dia_es and not es_festivo:

                    asignados[g] = "DESCANSO"

                else:
                    activos.append(g)

            # =================================================
            # TURNOS (SAFE MODE)
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
            # COMPENSADO
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
            for g in GRUPOS_TEC:

                filas.append({
                    "Fecha": fecha.strftime("%Y-%m-%d"),
                    "Día": dia_es,
                    "Grupo": g,
                    "Turno": asignados.get(g,"T1 APOYO"),
                    "Festivo": "SI" if es_festivo else "NO"
                })

        df = pd.DataFrame(filas)

        st.session_state["malla"] = df
        guardar_excel(df, "malla_historica.xlsx")

        st.success("Malla generada correctamente")

        # =========================================================
        # 📊 MALLA VISUAL
        # =========================================================
        st.subheader("📊 Malla de turnos")

        df["Fecha"] = pd.to_datetime(df["Fecha"])

        pivot = df.pivot(index="Grupo", columns="Fecha", values="Turno")

        def estilo(v, fecha):

            if pd.isna(v):
                return ""

            if fecha.date() in festivos_co:
                return "background:#FFB703;font-weight:bold;color:black"

            if fecha.weekday() >= 5:
                return "background:#8ECAE6;font-weight:bold"

            return {
                "T1":"background:#D8F3DC",
                "T2":"background:#DCEBFF",
                "T3":"background:#EADCF8",
                "DESCANSO":"background:#FFD6D6",
                "COMPENSADO":"background:#FFF3BF"
            }.get(v,"")

        styled = pivot.style.apply(
            lambda col: [
                estilo(val, col.name) for val in col
            ],
            axis=0
        )

        st.dataframe(styled, use_container_width=True)

        # =========================================================
        # 📊 DASHBOARD
        # =========================================================
        st.subheader("📊 Dashboard")

        c1,c2,c3 = st.columns(3)

        c1.metric("Operativos", len(df[df["Turno"].isin(["T1","T2","T3"])]))
        c2.metric("Descansos", len(df[df["Turno"]=="DESCANSO"]))
        c3.metric("Compensados", len(df[df["Turno"]=="COMPENSADO"]))

        st.bar_chart(df.groupby(["Grupo","Turno"]).size().unstack(fill_value=0))

        # =========================================================
        # 🛡️ COBERTURA
        # =========================================================
        st.subheader("🛡️ Cobertura T1/T2/T3")

        cobertura = []

        for f in df["Fecha"].unique():

            d = df[df["Fecha"]==f]
            ts = set(d["Turno"])

            cobertura.append({
                "Fecha": f,
                "Completo": all(x in ts for x in ["T1","T2","T3"])
            })

        cov = pd.DataFrame(cobertura)

        st.metric("Días completos", cov["Completo"].sum())
        st.metric("Días incompletos", len(cov[cov["Completo"]==False]))

# =========================================================
# MENÚ
# =========================================================
def pantalla_programador():

    mod = st.radio(
        "Módulo",
        ["Programador Técnicos","Abordaje"],
        horizontal=True
    )

    if mod == "Programador Técnicos":
        generar_malla_tecnicos()
    else:
        pantalla_abordaje()
