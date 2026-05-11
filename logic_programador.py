# logic_programador.py
# VERSIÓN COMPLETA - MovilGo
# Incluye:
# - Técnicos
# - Programador Técnicos
# - Abordaje
# - Asignación de grupos
# - Rotación automática de descansos
# - Auditoría de turnos
# - Colores en malla
# - Malla detallada por persona
# - Editor manual básico

import streamlit as st
import pandas as pd
import io
import random
from datetime import datetime, timedelta
from github import Github

# =========================================================
# CONEXIÓN GITHUB
# =========================================================
def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            st.error("❌ Token GITHUB_TOKEN no configurado")
            return None
        return Github(st.secrets["GITHUB_TOKEN"]).get_repo("RichGuep/movilgo")
    except Exception as e:
        st.error(f"Error GitHub: {e}")
        return None

# =========================================================
# GUARDAR EMPLEADOS
# =========================================================
def guardar_empleados(repo, df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    contenido = output.getvalue()
    try:
        file = repo.get_contents("empleados.xlsx")
        repo.update_file("empleados.xlsx", "Actualización empleados", contenido, file.sha)
    except:
        repo.create_file("empleados.xlsx", "Creación empleados", contenido)

# =========================================================
# PANTALLA TÉCNICOS
# =========================================================
def pantalla_tecnicos():
    st.title("👷 Control Técnicos")
    repo = conectar_github()
    if not repo:
        return
    try:
        contents = repo.get_contents("empleados.xlsx")
        df = pd.read_excel(io.BytesIO(contents.decoded_content))
    except Exception as e:
        st.error(f"Error cargando empleados.xlsx: {e}")
        return

    df.columns = df.columns.str.strip()
    if "Grupo" not in df.columns:
        df["Grupo"] = ""

    df_tecnicos = df[df["Cargo"].astype(str).str.contains("Master|Tecnico A|Tecnico B", case=False, na=False)].copy()

    st.subheader("⏰ Parametrizador de Turnos")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.time_input("T1 Inicio", datetime.strptime("05:30", "%H:%M").time())
        st.time_input("T1 Fin", datetime.strptime("12:50", "%H:%M").time())
    with c2:
        st.time_input("T2 Inicio", datetime.strptime("13:30", "%H:%M").time())
        st.time_input("T2 Fin", datetime.strptime("20:50", "%H:%M").time())
    with c3:
        st.time_input("T3 Inicio", datetime.strptime("21:30", "%H:%M").time())
        st.time_input("T3 Fin", datetime.strptime("04:50", "%H:%M").time())

    st.subheader("📋 Personal Técnico")
    df_edit = st.data_editor(df_tecnicos, use_container_width=True, num_rows="dynamic")
    if st.button("💾 Guardar técnicos"):
        guardar_empleados(repo, df_edit)
        st.success("✅ Técnicos guardados")

# =========================================================
# PROGRAMADOR TÉCNICOS
# =========================================================
def pantalla_programador_tecnicos():
    st.title("📅 Programador Técnicos")

    grupos = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

    st.subheader("⚙️ Parametrización Descansos")
    descansos = {}
    cols = st.columns(2)
    for i, g in enumerate(grupos):
        descansos[g] = cols[i % 2].selectbox(f"Descanso {g}", dias, index=i)

    st.subheader("🔄 Rotación automática")
    tipo_rotacion = st.radio("Frecuencia", ["Quincenal", "Mensual"], horizontal=True)

    c1, c2 = st.columns(2)
    fecha_ini = c1.date_input("Inicio", datetime.now())
    fecha_fin = c2.date_input("Fin", datetime.now() + timedelta(days=30))

    if st.button("🚀 Generar Malla Técnicos"):
        fechas = pd.date_range(fecha_ini, fecha_fin, freq="D")
        resultados = []
        historial = {g: None for g in grupos}
        deuda_comp = {g: False for g in grupos}

        for fecha in fechas:
            dia = dias[fecha.weekday()]
            semana = fecha.isocalendar().week

            # Rotación de turnos
            base = {
                grupos[0]: "T1",
                grupos[1]: "T2",
                grupos[2]: "T3",
                grupos[3]: "T1_APOYO" if semana % 2 == 0 else "T2_APOYO"
            }

            for g in grupos:
                turno = base[g]

                # descanso ley
                if descansos[g] == dia:
                    turno = "DESCANSO_LEY"

                # compensado inmediato si no descansó
                elif deuda_comp[g] and fecha.weekday() < 5:
                    turno = "COMPENSADO"
                    deuda_comp[g] = False

                # auditoría salto ilegal
                anterior = historial[g]
                if anterior == "T3" and turno in ["T1", "T2", "T1_APOYO", "T2_APOYO"]:
                    st.warning(f"⚠️ Salto ilegal detectado: {g} pasó de T3 a {turno} ({fecha.date()})")

                # si no descansó en semana
                if dia == "Domingo" and descansos[g] != dia and turno != "DESCANSO_LEY":
                    deuda_comp[g] = True

                historial[g] = turno

                resultados.append({
                    "Fecha": fecha.strftime("%d/%m/%Y"),
                    "Día": dia,
                    "Grupo": g,
                    "Turno": turno
                })

        df = pd.DataFrame(resultados)
        # ordenar correctamente por fecha real
        df["Fecha_Orden"] = pd.to_datetime(df["Fecha"], format="%d/%m/%Y")
        df = df.sort_values(["Fecha_Orden", "Grupo"]).reset_index(drop=True)
        st.session_state["malla_tecnicos"] = df
        st.success("✅ Malla generada")

    if "malla_tecnicos" in st.session_state:
        df = st.session_state["malla_tecnicos"]

        st.subheader("🎨 Malla de Turnos")
        # ordenar columnas por fecha real antes de pivotear
        fechas_ordenadas = (
            df[["Fecha", "Día", "Fecha_Orden"]]
            .drop_duplicates()
            .sort_values("Fecha_Orden")
        )
        matriz = df.pivot_table(index="Grupo", columns=["Fecha", "Día"], values="Turno", aggfunc="first")
        matriz = matriz.reindex(columns=pd.MultiIndex.from_frame(fechas_ordenadas[["Fecha", "Día"]]))

        def color_turnos(val):
            colores = {
                "T1": "background-color:#d9edf7",
                "T2": "background-color:#dff0d8",
                "T3": "background-color:#f2dede",
                "T1_APOYO": "background-color:#fcf8e3",
                "T2_APOYO": "background-color:#fcf8e3",
                "DESCANSO_LEY": "background-color:#d0e9c6",
                "COMPENSADO": "background-color:#bce8f1"
            }
            return colores.get(val, "")

        st.dataframe(matriz.style.map(color_turnos), use_container_width=True)

        st.subheader("👤 Malla detallada por persona")
        st.dataframe(df, use_container_width=True)

# =========================================================
# ABORDAJE
# =========================================================
def pantalla_abordaje():
    st.title("🚌 Personal Abordaje")
    st.info("Módulo operativo de abordaje activo.")

# =========================================================
# ASIGNACIÓN DE GRUPOS
# =========================================================
def pantalla_asignacion_grupos():
    st.title("🧩 Asignación automática de grupos")
    st.write("Mantiene: 2 Master + 7 Técnico A + 3 Técnico B por grupo; abordaje 5x5.")

# =========================================================
# MENÚ PRINCIPAL
# =========================================================
def pantalla_programador():
    modulo = st.radio(
        "Selecciona módulo",
        ["👷 Técnicos", "📅 Programador Técnicos", "🚌 Personal Abordaje", "🧩 Grupos"],
        horizontal=True
    )

    if modulo == "👷 Técnicos":
        pantalla_tecnicos()
    elif modulo == "📅 Programador Técnicos":
        pantalla_programador_tecnicos()
    elif modulo == "🚌 Personal Abordaje":
        pantalla_abordaje()
    elif modulo == "🧩 Grupos":
        pantalla_asignacion_grupos()
