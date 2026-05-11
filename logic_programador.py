# logic_programador.py
# VERSIÓN BASE + ROTACIÓN MENSUAL DE DESCANSOS (INTEGRACIÓN SEGURA)

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
        df = pd.read_excel(io.BytesIO(c.decoded_content))
        df.columns = df.columns.str.strip()
        return df
    except:
        return pd.DataFrame()


def guardar_excel(df, nombre):
    repo = conectar_github()
    if not repo:
        return
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    data = output.getvalue()

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

    # 🔒 estado base descansos
    if "descansos_base" not in st.session_state:
        st.session_state["descansos_base"] = {}

    st.dataframe(df, use_container_width=True)

    if st.button("🚀 Asignar grupos automáticamente"):
        asignacion = {}

        masters = df[df["Cargo"] == "Master"].sample(frac=1)
        tec_a = df[df["Cargo"] == "Tecnico A"].sample(frac=1)
        tec_b = df[df["Cargo"] == "Tecnico B"].sample(frac=1)
        abordaje = df[df["Cargo"].astype(str).str.contains("Auxiliar de Abordaje y Atención al Público", na=False)].sample(frac=1)

        if len(masters) < 8 or len(tec_a) < 28 or len(tec_b) < 12:
            st.error("❌ No cumple cantidades mínimas técnicos")
            return

        idx = 0
        for g in GRUPOS_TEC:
            for _ in range(2):
                asignacion[masters.iloc[idx]["Nombre"]] = g
                idx += 1

        idx = 0
        for g in GRUPOS_TEC:
            for _ in range(7):
                asignacion[tec_a.iloc[idx]["Nombre"]] = g
                idx += 1

        idx = 0
        for g in GRUPOS_TEC:
            for _ in range(3):
                asignacion[tec_b.iloc[idx]["Nombre"]] = g
                idx += 1

        grupos_ab = ["Grupo A", "Grupo B", "Grupo C", "Grupo D", "Grupo E"]

        if len(abordaje) >= 25:
            idx = 0
            for g in grupos_ab:
                for _ in range(5):
                    asignacion[abordaje.iloc[idx]["Nombre"]] = g
                    idx += 1

        df["Grupo"] = df["Nombre"].map(lambda x: asignacion.get(x, ""))
        guardar_excel(df, "empleados.xlsx")

        st.success("✅ Grupos asignados")
        st.dataframe(df, use_container_width=True)

# =========================================================
# PROGRAMADOR TÉCNICOS
# =========================================================
def generar_malla_tecnicos():
    st.header("📅 Programador Técnicos")

    c1, c2 = st.columns(2)
    fecha_ini = c1.date_input("Inicio", datetime.now())
    fecha_fin = c2.date_input("Fin", datetime.now() + timedelta(days=30))

    st.subheader("Descanso parametrizado")

    descansos = {}
    cols = st.columns(4)

    for i, g in enumerate(GRUPOS_TEC):
        descansos[g] = cols[i].selectbox(g, DIAS, index=i)

    # 🔒 guardar base inicial
    if "descansos_base" not in st.session_state:
        st.session_state["descansos_base"] = descansos.copy()

    # =========================================================
    # 🔁 ROTACIÓN MENSUAL (SIN ROMPER SISTEMA)
    # =========================================================
    st.divider()

    if st.button("🔁 Activar rotación mensual de descansos"):
        base = st.session_state["descansos_base"]

        if not base:
            base = descansos.copy()

        nuevos = {}
        for g in GRUPOS_TEC:
            idx = DIAS.index(base[g])
            nuevos[g] = DIAS[(idx + 1) % len(DIAS)]

        st.session_state["descansos_base"] = nuevos
        st.success("✅ Rotación mensual activada")

    # =========================================================
    # GENERACIÓN DE MALLA
    # =========================================================
    if st.button("🚀 Generar malla"):

        fechas = pd.date_range(fecha_ini, fecha_fin, freq="D")
        filas = []

        bloque_actual = {"Grupo 1": "T1", "Grupo 2": "T2", "Grupo 3": "T3", "Grupo 4": "T1"}
        dias_en_bloque = {g: 0 for g in GRUPOS_TEC}
        orden_rotacion = {"T1": "T2", "T2": "T3", "T3": "T1"}
        ultimo_turno = {g: None for g in GRUPOS_TEC}
        conteo_turnos = {g: {"T1": 0, "T2": 0, "T3": 0} for g in GRUPOS_TEC}

        # =====================================================
        # APLICAR ROTACIÓN POR MES
        # =====================================================
        descansos = st.session_state["descansos_base"].copy()
        offset = fecha_ini.month - 1

        for g in GRUPOS_TEC:
            idx = DIAS.index(descansos[g])
            descansos[g] = DIAS[(idx + offset) % len(DIAS)]

        # =====================================================
        # GENERACIÓN
        # =====================================================
        for fecha in fechas:
            dia = DIAS[fecha.weekday()]
            asignados = {}

            descansan = [g for g in GRUPOS_TEC if descansos[g] == dia]
            activos = [g for g in GRUPOS_TEC if g not in descansan]

            for g in descansan:
                asignados[g] = "DESCANSO"
                ultimo_turno[g] = "DESCANSO"

                if dias_en_bloque[g] >= 4:
                    bloque_actual[g] = orden_rotacion[bloque_actual[g]]
                    dias_en_bloque[g] = 0

            for turno in ["T1", "T2", "T3"]:
                candidatos = []

                for g in activos:
                    if g in asignados:
                        continue
                    if ultimo_turno[g] == "T3" and turno == "T1":
                        continue

                    candidatos.append((0 if bloque_actual[g] == turno else 1,
                                       conteo_turnos[g][turno],
                                       g))

                if not candidatos:
                    for g in activos:
                        if g not in asignados:
                            candidatos.append((1, conteo_turnos[g][turno], g))

                candidatos.sort()
                sel = candidatos[0][2]

                asignados[sel] = turno
                ultimo_turno[sel] = turno
                conteo_turnos[sel][turno] += 1
                dias_en_bloque[sel] += 1

            for g in activos:
                if g not in asignados:
                    asignados[g] = "T1 APOYO" if conteo_turnos[g]["T1"] <= conteo_turnos[g]["T2"] else "T2 APOYO"
                    dias_en_bloque[g] += 1

            for g in GRUPOS_TEC:
                filas.append({
                    "Fecha": fecha.strftime("%Y-%m-%d"),
                    "Día": dia,
                    "Grupo": g,
                    "Turno": asignados[g]
                })

        df = pd.DataFrame(filas)
        st.session_state["malla_tecnicos"] = df
        guardar_excel(df, "malla_historica.xlsx")

        st.success("✅ Malla generada")

# =========================================================
# ABORDAJE
# =========================================================
def pantalla_abordaje():
    st.header("🚌 Personal Abordaje")
    st.info("Módulo activo")

# =========================================================
# MENÚ
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
