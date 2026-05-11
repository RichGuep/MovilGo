# logic_programador.py
# VERSIÓN ESTABLE - ROTACIÓN SEGURA SIN SALTOS INVÁLIDOS

import streamlit as st
import pandas as pd
import io
import random
from datetime import datetime, timedelta
from github import Github

# =========================================================
# CONFIGURACIÓN
# =========================================================
TURNOS = ["T1", "T2", "T3", "T1 APOYO", "T2 APOYO", "DESCANSO", "COMPENSADO"]

HORARIOS = {
    "T1": "05:30-12:50",
    "T2": "13:30-20:50",
    "T3": "21:30-04:50",
    "T1 APOYO": "05:30-12:50",
    "T2 APOYO": "13:30-20:50",
}

GRUPOS_TEC = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

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

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    data = output.getvalue().decode("latin1")

    try:
        c = repo.get_contents(nombre)
        repo.update_file(nombre, "update", data, c.sha)
    except:
        repo.create_file(nombre, "create", data)

# =========================================================
# ASIGNACIÓN DE GRUPOS
# =========================================================
def asignar_grupos():
    st.header("🧩 Asignación automática de grupos")

    df = cargar_excel("empleados.xlsx")
    if df.empty:
        st.warning("No hay empleados")
        return

    if "Grupo" not in df.columns:
        df["Grupo"] = ""

    st.dataframe(df, use_container_width=True)

    if st.button("🚀 Asignar grupos automáticamente"):
        asignacion = {}

        masters = df[df["Cargo"] == "Master"].sample(frac=1)
        tec_a = df[df["Cargo"] == "Tecnico A"].sample(frac=1)
        tec_b = df[df["Cargo"] == "Tecnico B"].sample(frac=1)
        abordaje = df[df["Cargo"].astype(str).str.contains("Auxiliar de Abordaje", na=False)].sample(frac=1)

        idx = 0
        for g in GRUPOS_TEC:
            for _ in range(2):
                if idx < len(masters):
                    asignacion[masters.iloc[idx]["Nombre"]] = g
                    idx += 1

        idx = 0
        for g in GRUPOS_TEC:
            for _ in range(7):
                if idx < len(tec_a):
                    asignacion[tec_a.iloc[idx]["Nombre"]] = g
                    idx += 1

        idx = 0
        for g in GRUPOS_TEC:
            for _ in range(3):
                if idx < len(tec_b):
                    asignacion[tec_b.iloc[idx]["Nombre"]] = g
                    idx += 1

        grupos_ab = ["Grupo A", "Grupo B", "Grupo C", "Grupo D", "Grupo E"]
        idx = 0
        for g in grupos_ab:
            for _ in range(5):
                if idx < len(abordaje):
                    asignacion[abordaje.iloc[idx]["Nombre"]] = g
                    idx += 1

        df["Grupo"] = df["Nombre"].map(lambda x: asignacion.get(x, ""))
        guardar_excel(df, "empleados.xlsx")

        st.success("✅ Grupos asignados")
        st.dataframe(df, use_container_width=True)

# =========================================================
# MOTOR DE ROTACIÓN SEGURO (CLAVE)
# =========================================================
def siguiente_turno(turno):
    if turno == "T1":
        return "T2"
    if turno == "T2":
        return "T3"
    if turno == "T3":
        return "T1"


def salto_invalido(prev, nuevo):
    return (prev == "T3" and nuevo == "T1") or (prev == "T2" and nuevo == "T1")

# =========================================================
# PROGRAMADOR TÉCNICOS
# =========================================================
def generar_malla_tecnicos():
    st.header("📅 Programador Técnicos")

    c1, c2 = st.columns(2)
    fecha_ini = c1.date_input("Inicio", datetime.now())
    fecha_fin = c2.date_input("Fin", datetime.now() + timedelta(days=30))

    if st.button("🚀 Generar malla"):

        fechas = pd.date_range(fecha_ini, fecha_fin, freq="D")

        # estado por grupo
        estado = {
            g: {
                "turno": random.choice(["T1", "T2", "T3"]),
                "dias": 0,
                "prev": None
            }
            for g in GRUPOS_TEC
        }

        filas = []

        for fecha in fechas:
            dia = DIAS[fecha.weekday()]

            for g in GRUPOS_TEC:

                actual = estado[g]["turno"]
                dias = estado[g]["dias"]
                prev = estado[g]["prev"]

                # rotación cada 4 días
                if dias >= 4:
                    nuevo = siguiente_turno(actual)

                    if not salto_invalido(actual, nuevo):
                        estado[g]["turno"] = nuevo
                        estado[g]["dias"] = 0

                turno_final = estado[g]["turno"]

                filas.append({
                    "Fecha": fecha.strftime("%Y-%m-%d"),
                    "Día": dia,
                    "Grupo": g,
                    "Turno": turno_final
                })

                estado[g]["prev"] = turno_final
                estado[g]["dias"] += 1

        df = pd.DataFrame(filas)

        st.session_state["malla_tecnicos"] = df

        guardar_excel(df, "malla_historica.xlsx")
        st.success("✅ Malla generada sin saltos inválidos")

    # VISUAL
    if "malla_tecnicos" in st.session_state:
        df = st.session_state["malla_tecnicos"]

        pivot = df.pivot_table(
            index="Grupo",
            columns="Fecha",
            values="Turno",
            aggfunc="first"
        )

        st.dataframe(pivot, use_container_width=True)

# =========================================================
# ABORDAJE
# =========================================================
def pantalla_abordaje():
    st.header("🚌 Personal Abordaje")
    st.info("Módulo activo")

# =========================================================
# MENÚ PRINCIPAL
# =========================================================
def pantalla_programador():
    mod = st.radio(
        "Selecciona módulo",
        ["📅 Programador Técnicos", "🧩 Grupos", "🚌 Personal Abordaje"],
        horizontal=True
    )

    if mod == "📅 Programador Técnicos":
        generar_malla_tecnicos()
    elif mod == "🧩 Grupos":
        asignar_grupos()
    else:
        pantalla_abordaje()
