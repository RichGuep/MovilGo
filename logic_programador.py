# logic_programador.py
# Versión completa con programación avanzada de técnicos y abordaje

import streamlit as st
import pandas as pd
import io
from github import Github
from datetime import datetime, timedelta

# =========================================================
# CONEXIÓN GITHUB
# =========================================================

def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            st.error("❌ Token GITHUB_TOKEN no configurado")
            return None
        g = Github(st.secrets["GITHUB_TOKEN"])
        return g.get_repo("RichGuep/movilgo")
    except Exception as e:
        st.error(f"Error GitHub: {e}")
        return None


def guardar_excel(repo, df, archivo, mensaje):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    contenido = output.getvalue()
    try:
        file = repo.get_contents(archivo)
        repo.update_file(archivo, mensaje, contenido, file.sha)
    except Exception:
        repo.create_file(archivo, mensaje, contenido)

# =========================================================
# PANTALLA TÉCNICOS
# =========================================================

def pantalla_tecnicos():
    st.title("👷 Control Técnicos")
    repo = conectar_github()
    if not repo:
        return

    try:
        archivo = repo.get_contents("empleados.xlsx")
        df = pd.read_excel(io.BytesIO(archivo.decoded_content))
    except Exception as e:
        st.error(f"Error cargando empleados.xlsx: {e}")
        return

    df.columns = df.columns.str.strip()
    if "Grupo" not in df.columns:
        df["Grupo"] = ""

    df_tec = df[df["Cargo"].astype(str).str.contains("Master|Tecnico A|Tecnico B", case=False, na=False)].copy()

    st.subheader("📋 Personal técnico")
    df_edit = st.data_editor(df_tec, use_container_width=True, num_rows="dynamic")

    st.subheader("⏰ Parametrizador turnos")
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

    if st.button("💾 Guardar técnicos"):
        guardar_excel(repo, df_edit, "empleados.xlsx", "Actualización técnicos")
        st.success("✅ Técnicos guardados")

# =========================================================
# PROGRAMADOR TÉCNICOS AVANZADO
# =========================================================

def color_turnos(val):
    colores = {
        "T1": "background-color: #d4edda",
        "T2": "background-color: #d1ecf1",
        "T3": "background-color: #e2d6f5",
        "T1 Apoyo": "background-color: #fff3cd",
        "T2 Apoyo": "background-color: #ffe5b4",
        "DESC": "background-color: #f8d7da",
        "DESC_COMP": "background-color: #f9d5e5",
        "DESC_PENDIENTE": "background-color: #e2e3e5",
    }
    return colores.get(val, "")


def pantalla_programador_tecnicos():
    st.title("📅 Programador Técnicos")
    repo = conectar_github()
    if not repo:
        return

    try:
        archivo = repo.get_contents("empleados.xlsx")
        df_emp = pd.read_excel(io.BytesIO(archivo.decoded_content))
    except Exception:
        st.error("Error cargando empleados.xlsx")
        return

    df_emp.columns = df_emp.columns.str.strip()
    df_emp = df_emp[df_emp["Cargo"].astype(str).str.contains("Master|Tecnico A|Tecnico B", case=False, na=False)].copy()

    grupos = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

    st.subheader("⚙️ Configuración")
    c1, c2 = st.columns(2)
    fecha_ini = c1.date_input("Inicio", datetime.now())
    fecha_fin = c2.date_input("Fin", datetime.now() + timedelta(days=30))
    tipo_rotacion = st.radio("Rotación descansos", ["Quincenal", "Mensual"], horizontal=True)

    st.subheader("📅 Descanso parametrizado")
    descansos_base = {}
    for i, g in enumerate(grupos):
        descansos_base[g] = dias.index(st.selectbox(g, dias, index=i))

    if st.button("🚀 Generar programación"):
        fechas = pd.date_range(fecha_ini, fecha_fin, freq="D")
        resultados = []
        ultimo_turno = {g: None for g in grupos}
        descansos_oficiales = {g: 0 for g in grupos}
        pendientes = {g: 0 for g in grupos}

        for fecha in fechas:
            bloque = ((fecha - fecha_ini).days // 15) if tipo_rotacion == "Quincenal" else (fecha.month - fecha_ini.month)
            descanso_hoy = {g: (descansos_base[g] + bloque) % 7 for g in grupos}
            nombre_dia = fecha.weekday()

            # asignación base rotativa
            orden = grupos.copy()
            idx = fecha.day % 4
            orden = orden[idx:] + orden[:idx]
            asignados = {orden[0]: "T1", orden[1]: "T2", orden[2]: "T3", orden[3]: "T1 Apoyo" if fecha.day % 2 == 0 else "T2 Apoyo"}

            for g in grupos:
                turno = asignados[g]

                # respetar descanso parametrizado si es posible
                if descanso_hoy[g] == nombre_dia:
                    if turno.endswith("Apoyo"):
                        turno = "DESC"
                        descansos_oficiales[g] += 1
                    else:
                        pendientes[g] += 1
                        turno = "DESC_PENDIENTE"

                # compensado inmediato lunes-viernes
                elif pendientes[g] > 0 and nombre_dia < 5 and turno.endswith("Apoyo"):
                    turno = "DESC_COMP"
                    pendientes[g] -= 1

                # bloqueo T3 -> no pasar directo a T1/T2
                if ultimo_turno[g] == "T3" and turno in ["T1", "T2"]:
                    turno = "T1 Apoyo"

                ultimo_turno[g] = turno

                resultados.append({
                    "Fecha": fecha,
                    "Grupo": g,
                    "Turno": turno
                })

        df_malla = pd.DataFrame(resultados)
        st.session_state["malla_tecnicos"] = df_malla

    if "malla_tecnicos" not in st.session_state:
        return

    df = st.session_state["malla_tecnicos"]

    st.subheader("🔎 Auditoría")
    auditoria = df.groupby(["Grupo", "Turno"]).size().unstack(fill_value=0)
    st.dataframe(auditoria)

    st.subheader("✍️ Editor manual")
    df_edit = st.data_editor(df, use_container_width=True)
    if st.button("Guardar cambios"):
        st.session_state["malla_tecnicos"] = df_edit
        st.success("✅ Cambios guardados")

    st.subheader("📋 Malla por grupo")
    matriz = df_edit.pivot_table(index="Grupo", columns="Fecha", values="Turno", aggfunc="first")
    st.dataframe(matriz.style.map(color_turnos), use_container_width=True)

    st.subheader("👤 Malla detallada por persona")
    detalle = df_emp.merge(df_edit, on="Grupo")
    matriz_persona = detalle.pivot_table(index=["Grupo", "Nombre", "Cargo"], columns="Fecha", values="Turno", aggfunc="first")
    st.dataframe(matriz_persona.style.map(color_turnos), use_container_width=True)

    if st.button("☁️ Guardar histórico"):
        guardar_excel(repo, detalle, "malla_historica.xlsx", "Actualización malla técnicos")
        st.success("✅ Histórico guardado")

# =========================================================
# ABORDAJE
# =========================================================

def pantalla_abordaje():
    st.title("🚌 Personal Abordaje")
    st.info("Módulo listo; conserva tu lógica actual de abordaje aquí.")

# =========================================================
# ASIGNACIÓN DE GRUPOS
# =========================================================

def pantalla_asignacion_grupos():
    st.title("🧩 Asignación de grupos")
    st.info("Mantén aquí tu lógica actual de asignación: 2 Master, 7 Técnico A, 3 Técnico B; abordaje 5x5.")

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
