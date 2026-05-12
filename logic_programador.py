# =========================================================
# LOGIC_PROGRAMADOR - V2 MALLA DETALLADA
# =========================================================

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import holidays
import io
from github import Github

# =========================================================
# CONFIG BASE
# =========================================================
TURNOS = ["T1","T2","T3","T1 APOYO","T2 APOYO","DESCANSO","COMPENSADO"]
GRUPOS = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]
DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]

festivos_co = holidays.Colombia()

# =========================================================
# ⚙️ HORARIOS PARAMETRIZABLES
# =========================================================
def obtener_horarios():

    st.sidebar.subheader("⏰ Horarios de Turno")

    t1_ini = st.sidebar.time_input("T1 Inicio", datetime.strptime("05:30","%H:%M"))
    t1_fin = st.sidebar.time_input("T1 Fin", datetime.strptime("12:50","%H:%M"))

    t2_ini = st.sidebar.time_input("T2 Inicio", datetime.strptime("13:30","%H:%M"))
    t2_fin = st.sidebar.time_input("T2 Fin", datetime.strptime("20:50","%H:%M"))

    t3_ini = st.sidebar.time_input("T3 Inicio", datetime.strptime("21:30","%H:%M"))
    t3_fin = st.sidebar.time_input("T3 Fin", datetime.strptime("04:50","%H:%M"))

    return {
        "T1": (t1_ini.strftime("%H:%M"), t1_fin.strftime("%H:%M")),
        "T2": (t2_ini.strftime("%H:%M"), t2_fin.strftime("%H:%M")),
        "T3": (t3_ini.strftime("%H:%M"), t3_fin.strftime("%H:%M"))
    }

# =========================================================
# 👥 PERSONAL
# =========================================================
def cargar_personal():

    st.sidebar.subheader("👥 Personal")

    if "personal" not in st.session_state:

        st.warning("⚠️ Debes cargar el personal")

        file = st.sidebar.file_uploader("Subir Excel Personal")

        if file:
            df = pd.read_excel(file)
            st.session_state["personal"] = df

    return st.session_state.get("personal", None)

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
        file = repo.get_contents("malla_detallada.xlsx")
        repo.update_file("malla_detallada.xlsx", "update", data, file.sha)
    except:
        repo.create_file("malla_detallada.xlsx", "create", data)

# =========================================================
# AUDITORÍA PRO
# =========================================================
def auditoria_detallada(df):

    errores = []

    df["Fecha"] = pd.to_datetime(df["Fecha"])

    # cobertura
    cobertura = df.groupby("Fecha").size()

    # saltos horarios inválidos
    for c in df["Cedula"].unique():

        emp = df[df["Cedula"] == c].sort_values("Fecha")

        prev = None

        for _, r in emp.iterrows():

            if prev == "T3" and r["Turno"] in ["T1","T2"]:
                errores.append(f"{r['Nombre']} salto nocturno indebido")

            prev = r["Turno"]

    # carga excesiva
    horas_por_persona = df.groupby("Nombre").size()

    for n, h in horas_por_persona.items():
        if h > 26:
            errores.append(f"{n} sobrecarga de turnos: {h}")

    return errores, cobertura

# =========================================================
# GENERADOR BASE
# =========================================================
def generar_malla():

    st.header("🚀 OPTIMIZADOR PRO + MALLA DETALLADA")

    horarios = obtener_horarios()
    personal = cargar_personal()

    if personal is None:
        st.error("Debes cargar el personal (Cedula, Nombre, Grupo)")
        return

    inicio = st.date_input("Inicio", date.today())
    fin = st.date_input("Fin", date.today()+timedelta(days=30))

    descanso = {}
    cols = st.columns(len(GRUPOS))

    for i,g in enumerate(GRUPOS):
        descanso[g] = cols[i].selectbox(g, DIAS_ES, index=i)

    # =====================================================
    carga = {g:0 for g in GRUPOS}
    conteo = {g:{"T1":0,"T2":0,"T3":0} for g in GRUPOS}
    compensado = {g:0 for g in GRUPOS}
    sacrificio = {g:0 for g in GRUPOS}

    last_turn = {g: None for g in GRUPOS}
    streak = {g: 0 for g in GRUPOS}

    filas = []

    # =====================================================
    if st.button("🚀 Generar malla"):

        fechas = pd.date_range(inicio, fin)

        for fecha in fechas:

            dia = DIAS_ES[fecha.weekday()]
            festivo = fecha.date() in festivos_co

            asignados = {}

            descanso_dia = [g for g in GRUPOS if descanso[g]==dia]
            activos = [g for g in GRUPOS if g not in descanso_dia]

            while len(activos) < 3:
                mov = sorted(descanso_dia, key=lambda g:(sacrificio[g],carga[g]))[0]
                descanso_dia.remove(mov)
                activos.append(mov)

            for g in descanso_dia:
                asignados[g]="DESCANSO"

            # TURNOS
            for turno in ["T1","T2","T3"]:

                sel = sorted(activos, key=lambda g:(carga[g],conteo[g][turno]))[0]

                asignados[sel]=turno
                carga[sel]+=1
                conteo[sel][turno]+=1

                activos.remove(sel)

            for g in activos:
                asignados[g]="T1 APOYO"

            # =================================================
            # MALLA DETALLADA (EXPANSIÓN POR PERSONA)
            # =================================================
            for _, p in personal.iterrows():

                grupo = p["Grupo"]

                turno = asignados.get(grupo,"DESCANSO")

                if turno == "DESCANSO":
                    ini, fin_h = None, None
                else:
                    ini, fin_h = horarios[turno]

                filas.append({
                    "Fecha": fecha,
                    "Cedula": p["Cedula"],
                    "Nombre": p["Nombre"],
                    "Grupo": grupo,
                    "Turno": turno,
                    "Hora Inicio": ini,
                    "Hora Fin": fin_h
                })

        df = pd.DataFrame(filas)

        st.session_state["malla_detallada"] = df

        guardar_github(df)

        st.success("Malla detallada generada")

# =========================================================
# INTERFAZ
# =========================================================
def pantalla_programador():

    generar_malla()

    if "malla_detallada" not in st.session_state:
        return

    df = st.session_state["malla_detallada"]

    st.subheader("📊 MALLA DETALLADA")

    st.dataframe(df, use_container_width=True)

    # =====================================================
    st.subheader("🚨 Auditoría")

    errores, cobertura = auditoria_detallada(df)

    if errores:
        for e in errores[:20]:
            st.error(e)
    else:
        st.success("Sin errores detectados")

    st.line_chart(cobertura)
