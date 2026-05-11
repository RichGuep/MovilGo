import streamlit as st
import io
import pandas as pd
from github import Github
from datetime import datetime, timedelta


# =====================================
# CONEXIÓN GITHUB
# =====================================

def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            st.error("❌ Token GITHUB_TOKEN no configurado")
            return None

        g = Github(st.secrets["GITHUB_TOKEN"])
        repo = g.get_repo("RichGuep/movilgo")
        return repo

    except Exception as e:
        st.error(f"Error GitHub: {e}")
        return None


# =====================================
# GUARDAR EMPLEADOS
# =====================================

def guardar_empleados(repo, df):

    if "Grupo" not in df.columns:
        df["Grupo"] = ""

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    contenido = output.getvalue()

    try:
        file = repo.get_contents("empleados.xlsx")

        repo.update_file(
            "empleados.xlsx",
            "Actualización empleados MovilGo",
            contenido,
            file.sha
        )

    except Exception:
        repo.create_file(
            "empleados.xlsx",
            "Creación empleados MovilGo",
            contenido
        )


# =====================================
# PANTALLA TÉCNICOS
# =====================================

def pantalla_tecnicos():

    st.title("👷 Control Técnicos")

    repo = conectar_github()
    if not repo:
        return

    try:
        file = repo.get_contents("empleados.xlsx")
        df = pd.read_excel(io.BytesIO(file.decoded_content))
    except Exception as e:
        st.error(f"Error leyendo empleados.xlsx: {e}")
        return

    df.columns = df.columns.str.strip()

    if "Grupo" not in df.columns:
        df["Grupo"] = ""

    required = ["Nombre", "Cargo"]
    for col in required:
        if col not in df.columns:
            st.error(f"Falta columna: {col}")
            return

    df = df[
        df["Cargo"].astype(str).str.contains(
            "Master|Tecnico A|Tecnico B",
            case=False,
            na=False
        )
    ]

    st.dataframe(df, use_container_width=True)

    if st.button("💾 Guardar"):
        guardar_empleados(repo, df)
        st.success("Guardado correctamente")


# =====================================
# ASIGNACIÓN DE GRUPOS
# =====================================

def pantalla_asignacion_grupos():

    st.title("🧩 Asignación de Grupos")

    repo = conectar_github()
    if not repo:
        return

    try:
        file = repo.get_contents("empleados.xlsx")
        df = pd.read_excel(io.BytesIO(file.decoded_content))
    except Exception as e:
        st.error(f"Error leyendo archivo: {e}")
        return

    df.columns = df.columns.str.strip()

    if "Grupo" not in df.columns:
        df["Grupo"] = ""

    st.dataframe(df, use_container_width=True)

    grupos_tecnicos = [
        "Grupo 1",
        "Grupo 2",
        "Grupo 3",
        "Grupo 4"
    ]

    grupos_abordaje = [
        "Grupo A",
        "Grupo B",
        "Grupo C",
        "Grupo D",
        "Grupo E"
    ]

    if st.button("🚀 Asignar grupos automáticamente"):

        asignacion = {}

        tecnicos = df[
            df["Cargo"].astype(str).str.contains(
                "Master|Tecnico A|Tecnico B",
                case=False,
                na=False
            )
        ].reset_index(drop=True)

        for i, row in tecnicos.iterrows():
            grupo = grupos_tecnicos[i % 4]
            asignacion[row["Nombre"]] = grupo

        abordaje = df[
            df["Cargo"].astype(str).str.contains(
                "Abordaje",
                case=False,
                na=False
            )
        ].reset_index(drop=True)

        for i, row in abordaje.iterrows():
            grupo = grupos_abordaje[i % 5]
            asignacion[row["Nombre"]] = grupo

        df["Grupo"] = df["Nombre"].map(
            lambda x: asignacion.get(x, "")
        )

        st.session_state["df_grupos"] = df

        st.success("✅ Grupos asignados")

    if "df_grupos" in st.session_state:

        st.subheader("Resultado")

        st.dataframe(
            st.session_state["df_grupos"],
            use_container_width=True
        )

        if st.button("💾 Guardar grupos"):
            guardar_empleados(
                repo,
                st.session_state["df_grupos"]
            )
            st.success("Guardado en GitHub")


# =====================================
# PERSONAL ABORDAJE
# =====================================

def pantalla_abordaje():

    st.title("🚌 Programador Personal Abordaje")

    repo = conectar_github()
    if not repo:
        return

    try:
        file = repo.get_contents("empleados.xlsx")
        df = pd.read_excel(io.BytesIO(file.decoded_content))
    except Exception as e:
        st.error(f"Error leyendo archivo: {e}")
        return

    df.columns = df.columns.str.strip()

    df_ab = df[
        df["Cargo"].astype(str).str.contains(
            "Abordaje",
            case=False,
            na=False
        )
    ]

    if df_ab.empty:
        st.warning("No hay personal de abordaje")
        return

    st.success(f"{len(df_ab)} personas cargadas")

    grupos = ["Grupo A", "Grupo B", "Grupo C", "Grupo D", "Grupo E"]

    dias = [
        "Lunes",
        "Martes",
        "Miércoles",
        "Jueves",
        "Viernes",
        "Sábado",
        "Domingo"
    ]

    st.subheader("Configurar descansos")

    descansos = {}

    for g in grupos:
        descanso = st.selectbox(
            f"Descanso {g}",
            dias,
            key=g
        )
        descansos[g] = descanso

    fecha_inicio = st.date_input(
        "Fecha inicio",
        datetime.now()
    )

    fecha_fin = st.date_input(
        "Fecha fin",
        datetime.now() + timedelta(days=14)
    )

    if st.button("🚀 Generar malla"):

        fechas = pd.date_range(
            fecha_inicio,
            fecha_fin,
            freq="D"
        )

        resultado = []

        for fecha in fechas:

            nombre_dia = dias[fecha.weekday()]

            for grupo in grupos:

                if descansos[grupo] == nombre_dia:
                    turno = "DESC"
                else:
                    turno = "ACTIVO"

                resultado.append({
                    "Fecha": fecha,
                    "Grupo": grupo,
                    "Turno": turno
                })

        malla = pd.DataFrame(resultado)

        st.session_state["malla_abordaje"] = malla

        st.success("Malla generada")

    if "malla_abordaje" in st.session_state:

        malla = st.session_state["malla_abordaje"]

        matriz = malla.pivot(
            index="Grupo",
            columns="Fecha",
            values="Turno"
        )

        st.dataframe(
            matriz,
            use_container_width=True
        )


# =====================================
# MENÚ PRINCIPAL
# =====================================

def pantalla_programador():

    modulo = st.radio(
        "Selecciona módulo",
        [
            "👷 Técnicos",
            "🚍 Personal Abordaje",
            "🧩 Grupos"
        ],
        horizontal=True
    )

    if modulo == "👷 Técnicos":
        pantalla_tecnicos()

    elif modulo == "🚍 Personal Abordaje":
        pantalla_abordaje()

    elif modulo == "🧩 Grupos":
        pantalla_asignacion_grupos()
