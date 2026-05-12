# =========================================================
# LOGIC_PROGRAMADOR - ENTERPRISE FINAL CONSOLIDADO
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
TURNOS_BASE = ["T1", "T2", "T3"]
TURNOS_ESPECIALES = ["T1 APOYO", "T2 APOYO", "DESCANSO", "COMPENSADO"]

DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
festivos_co = holidays.Colombia()

GRUPOS_BASE = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]

ROL_ESTRUCTURA = {
    "Master": 2,
    "Tecnico A": 7,
    "Tecnico B": 3
}

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


def cargar_empleados():
    repo = conectar_github()
    if not repo:
        return None

    try:
        file = repo.get_contents("empleados.xlsx")
        content = file.decoded_content
        return pd.read_excel(io.BytesIO(content))
    except:
        return None


def guardar_github(df, name):
    repo = conectar_github()
    if not repo:
        return

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    data = buffer.getvalue()

    try:
        file = repo.get_contents(name)
        repo.update_file(name, "update", data, file.sha)
    except:
        repo.create_file(name, "create", data)

# =========================================================
# HORARIOS PARAMETRIZABLES (EN FLUJO PRINCIPAL)
# =========================================================
def parametrizar_horarios():

    st.subheader("⏰ Horarios de Turnos")

    c1,c2,c3 = st.columns(3)

    t1_i = c1.time_input("T1 Inicio", datetime.strptime("05:30","%H:%M"))
    t1_f = c1.time_input("T1 Fin", datetime.strptime("12:50","%H:%M"))

    t2_i = c2.time_input("T2 Inicio", datetime.strptime("13:30","%H:%M"))
    t2_f = c2.time_input("T2 Fin", datetime.strptime("20:50","%H:%M"))

    t3_i = c3.time_input("T3 Inicio", datetime.strptime("21:30","%H:%M"))
    t3_f = c3.time_input("T3 Fin", datetime.strptime("04:50","%H:%M"))

    return {
        "T1": (t1_i.strftime("%H:%M"), t1_f.strftime("%H:%M")),
        "T2": (t2_i.strftime("%H:%M"), t2_f.strftime("%H:%M")),
        "T3": (t3_i.strftime("%H:%M"), t3_f.strftime("%H:%M"))
    }

# =========================================================
# GRUPOS (MANUAL + AUTOMÁTICO)
# =========================================================
def parametrizar_grupos(df):

    st.subheader("👥 Parametrización de Grupos")

    modo = st.radio("Modo asignación grupos", ["Manual", "Aleatorio"], horizontal=True)

    if modo == "Aleatorio":

        df = df.sample(frac=1).reset_index(drop=True)

        asignaciones = []

        grupos = GRUPOS_BASE.copy()

        i = 0

        for _, row in df.iterrows():

            grupo = grupos[i % len(grupos)]

            asignaciones.append(grupo)

            i += 1

        df["Grupo"] = asignaciones

    else:

        df["Grupo"] = st.data_editor(
            df[["Cedula","Nombre","Rol"]],
            use_container_width=True
        )["Grupo"]

    return df

# =========================================================
# MALLA GENERADOR (CORE CON BLOQUES)
# =========================================================
def generar_malla():

    st.header("🚀 OPTIMIZADOR ENTERPRISE FINAL")

    empleados = cargar_empleados()

    if empleados is None:
        st.error("No se pudo cargar empleados.xlsx desde GitHub")
        return

    empleados = parametrizar_grupos(empleados)

    horarios = parametrizar_horarios()

    # =====================================================
    # DESCANSOS (EN FLUJO PRINCIPAL)
    # =====================================================
    st.subheader("⚖️ Descansos por grupo")

    descanso = {}
    cols = st.columns(len(GRUPOS_BASE))

    for i,g in enumerate(GRUPOS_BASE):
        descanso[g] = cols[i].selectbox(g, DIAS_ES, index=i)

    # =====================================================
    # CONTROL DE ESTABILIDAD (BLOQUES)
    # =====================================================
    carga = {g:0 for g in GRUPOS_BASE}
    conteo = {g:{t:0 for t in TURNOS_BASE} for g in GRUPOS_BASE}

    last_turn = {g: None for g in GRUPOS_BASE}
    streak = {g: 0 for g in GRUPOS_BASE}

    filas = []

    inicio = st.date_input("Inicio", date.today())
    fin = st.date_input("Fin", date.today()+timedelta(days=30))

    # =====================================================
    if st.button("🚀 Generar malla"):

        fechas = pd.date_range(inicio, fin)

        for fecha in fechas:

            dia = DIAS_ES[fecha.weekday()]
            festivo = fecha.date() in festivos_co

            asignacion_grupo = {}

            # =================================================
            # ASIGNACIÓN POR GRUPO (T1/T2/T3 CON BLOQUES)
            # =================================================
            for g in GRUPOS_BASE:

                if dia == descanso[g]:
                    turno = "DESCANSO"
                else:

                    def score(t):

                        base = conteo[g][t]

                        if last_turn[g] != t:
                            if streak[g] < 4:
                                base += 1000
                            else:
                                base += 10
                        else:
                            base -= 5

                        return base

                    turno = min(TURNOS_BASE, key=score)

                # actualizar control
                if last_turn[g] == turno:
                    streak[g] += 1
                else:
                    streak[g] = 1
                    last_turn[g] = turno

                if turno in conteo[sel]:
                    conteo[sel][turno] += 1

            # =================================================
            # EXPANSIÓN A PERSONAS
            # =================================================
            for _, emp in empleados.iterrows():

                grupo = emp["Grupo"]

                turno = asignacion_grupo[grupo]

                if turno == "DESCANSO":
                    h_ini, h_fin = None, None
                else:
                    h_ini, h_fin = horarios[turno]

                filas.append({
                    "Fecha": fecha,
                    "Cedula": emp["Cedula"],
                    "Nombre": emp["Nombre"],
                    "Grupo": grupo,
                    "Turno": turno,
                    "Hora Inicio": h_ini,
                    "Hora Fin": h_fin,
                    "Festivo": "SI" if festivo else "NO"
                })

        df = pd.DataFrame(filas)

        st.session_state["malla_detallada"] = df

        guardar_github(df, "malla_detallada.xlsx")

        st.success("Malla generada correctamente")

# =========================================================
# AUDITORÍA COMPLETA
# =========================================================
def auditoria(df):

    errores = []

    df["Fecha"] = pd.to_datetime(df["Fecha"])

    # cobertura
    cobertura = df.groupby("Fecha").size()

    # sobrecarga por persona
    horas = df.groupby("Nombre").size()

    for n,h in horas.items():
        if h > 26:
            errores.append(f"{n} sobrecarga de turnos ({h})")

    # saltos críticos
    for c in df["Cedula"].unique():

        emp = df[df["Cedula"] == c].sort_values("Fecha")

        prev = None

        for _, r in emp.iterrows():

            if prev == "T3" and r["Turno"] in ["T1","T2"]:
                errores.append(f"{r['Nombre']} salto T3→mañana")

            prev = r["Turno"]

    return errores, cobertura

# =========================================================
# INTERFAZ
# =========================================================
def pantalla_programador():

    generar_malla()

    if "malla_detallada" not in st.session_state:
        return

    df = st.session_state["malla_detallada"]

    st.subheader("📊 MALLA DETALLADA FINAL")

    st.dataframe(df, use_container_width=True)

    st.subheader("🚨 Auditoría")

    errores, cobertura = auditoria(df)

    if errores:
        for e in errores[:20]:
            st.error(e)
    else:
        st.success("Sin errores críticos")

    st.line_chart(cobertura)
