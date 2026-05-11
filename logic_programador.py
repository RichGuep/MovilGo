import streamlit as st
import pandas as pd
import io
import random
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
        repo = g.get_repo("RichGuep/movilgo")
        return repo

    except Exception as e:
        st.error(f"Error GitHub: {e}")
        return None


# =========================================================
# GUARDAR EXCEL
# =========================================================

def guardar_excel(repo, df, archivo, mensaje):
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    contenido = output.getvalue()

    try:
        file = repo.get_contents(archivo)

        repo.update_file(
            archivo,
            mensaje,
            contenido,
            file.sha
        )

    except Exception:
        repo.create_file(
            archivo,
            mensaje,
            contenido
        )


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
        st.error(f"Error: {e}")
        return

    df.columns = df.columns.str.strip()

    if "Grupo" not in df.columns:
        df["Grupo"] = ""

    df_tec = df[
        df["Cargo"].astype(str).str.contains(
            "Master|Tecnico A|Tecnico B",
            case=False,
            na=False
        )
    ]

    st.subheader("📋 Personal técnico")
    st.dataframe(df_tec, use_container_width=True)

    st.subheader("⏰ Parametrizador turnos")

    c1, c2 = st.columns(2)

    with c1:
        st.time_input(
            "Inicio T1",
            datetime.strptime("06:00", "%H:%M").time()
        )

        st.time_input(
            "Fin T1",
            datetime.strptime("14:00", "%H:%M").time()
        )

    with c2:
        st.time_input(
            "Inicio T2",
            datetime.strptime("14:00", "%H:%M").time()
        )

        st.time_input(
            "Fin T2",
            datetime.strptime("22:00", "%H:%M").time()
        )

    st.subheader("✍️ Editor")

    df_edit = st.data_editor(
        df_tec,
        use_container_width=True,
        num_rows="dynamic"
    )

    if st.button("💾 Guardar técnicos"):
        guardar_excel(
            repo,
            df_edit,
            "empleados.xlsx",
            "Actualización técnicos"
        )
        st.success("Guardado")


# =========================================================
# PROGRAMADOR TÉCNICOS
# =========================================================

def pantalla_programador_tecnicos():
    st.title("📅 Programador Técnicos")

    repo = conectar_github()
    if not repo:
        return

    try:
        archivo = repo.get_contents("empleados.xlsx")
        df_emp = pd.read_excel(io.BytesIO(archivo.decoded_content))
    except:
        st.error("Error empleados")
        return

    df_emp.columns = df_emp.columns.str.strip()

    df_emp = df_emp[
        df_emp["Cargo"].astype(str).str.contains(
            "Master|Tecnico A|Tecnico B",
            case=False,
            na=False
        )
    ]

    grupos = [
        "Grupo 1",
        "Grupo 2",
        "Grupo 3",
        "Grupo 4"
    ]

    dias = [
        "Lunes",
        "Martes",
        "Miércoles",
        "Jueves",
        "Viernes",
        "Sábado",
        "Domingo"
    ]

    st.subheader("⚙️ Configuración")

    c1, c2 = st.columns(2)

    fecha_ini = c1.date_input(
        "Inicio",
        datetime.now()
    )

    fecha_fin = c2.date_input(
        "Fin",
        datetime.now() + timedelta(days=30)
    )

    tipo_rotacion = st.radio(
        "Rotación descansos",
        ["Quincenal", "Mensual"]
    )

    st.subheader("Descansos iniciales")

    d1 = st.selectbox("Grupo 1", dias, 0)
    d2 = st.selectbox("Grupo 2", dias, 1)
    d3 = st.selectbox("Grupo 3", dias, 2)
    d4 = st.selectbox("Grupo 4", dias, 3)

    descansos = {
        "Grupo 1": dias.index(d1),
        "Grupo 2": dias.index(d2),
        "Grupo 3": dias.index(d3),
        "Grupo 4": dias.index(d4)
    }

    if st.button("🚀 Generar programación"):
        resultados = []

        fechas = pd.date_range(
            fecha_ini,
            fecha_fin
        )

        for fecha in fechas:

            if tipo_rotacion == "Quincenal":
                bloque = (fecha - fecha_ini).days // 15
            else:
                bloque = fecha.month - fecha_ini.month

            for grupo in grupos:

                descanso = (
                    descansos[grupo] + bloque
                ) % 7

                if fecha.weekday() == descanso:
                    turno = "DESC"
                else:
                    if fecha.isocalendar().week % 2 == 0:
                        turno = "T1"
                    else:
                        turno = "T2"

                resultados.append({
                    "Fecha": fecha,
                    "Grupo": grupo,
                    "Turno": turno
                })

        st.session_state["malla_tecnicos"] = pd.DataFrame(
            resultados
        )

    if "malla_tecnicos" not in st.session_state:
        return

    df = st.session_state["malla_tecnicos"]

    st.subheader("🔎 Auditoría")

    auditoria = df.groupby(
        ["Grupo", "Turno"]
    ).size().unstack(fill_value=0)

    st.dataframe(auditoria)

    st.subheader("✍️ Editor manual")

    df_edit = st.data_editor(
        df,
        use_container_width=True
    )

    if st.button("Guardar cambios"):
        st.session_state["malla_tecnicos"] = df_edit
        st.success("Actualizado")

    st.subheader("📋 Malla grupal")

    matriz = df_edit.pivot_table(
        index="Grupo",
        columns="Fecha",
        values="Turno",
        aggfunc="first"
    )

    st.dataframe(
        matriz,
        use_container_width=True
    )

    st.subheader("👤 Malla detallada")

    detalle = df_emp.merge(
        df_edit,
        on="Grupo"
    )

    matriz_persona = detalle.pivot_table(
        index=["Grupo", "Nombre", "Cargo"],
        columns="Fecha",
        values="Turno",
        aggfunc="first"
    )

    st.dataframe(
        matriz_persona,
        use_container_width=True
    )

    if st.button("☁️ Guardar histórico"):
        guardar_excel(
            repo,
            detalle,
            "malla_historica.xlsx",
            "Malla técnicos"
        )
        st.success("Guardado")


# =========================================================
# ABORDAJE
# =========================================================

def pantalla_abordaje():
    st.title("🚌 Personal Abordaje")

    repo = conectar_github()
    if not repo:
        return

    try:
        archivo = repo.get_contents("empleados.xlsx")
        df = pd.read_excel(io.BytesIO(archivo.decoded_content))
    except:
        st.error("Error")
        return

    df.columns = df.columns.str.strip()

    df = df[
        df["Cargo"].astype(str).str.contains(
            "Auxiliar de Abordaje y Atención al Público",
            case=False,
            na=False
        )
    ]

    st.dataframe(df)

    st.info("Grupos de 5 personas.")


# =========================================================
# ASIGNACIÓN DE GRUPOS
# =========================================================

def pantalla_asignacion_grupos():
    st.title("🧩 Asignación de grupos")

    repo = conectar_github()
    if not repo:
        return

    try:
        archivo = repo.get_contents("empleados.xlsx")
        df = pd.read_excel(io.BytesIO(
            archivo.decoded_content
        ))
    except:
        st.error("Error")
        return

    df.columns = df.columns.str.strip()

    if "Grupo" not in df.columns:
        df["Grupo"] = ""

    st.dataframe(df)

    if st.button("🚀 Asignar grupos"):
        asignacion = {}

        grupos_tecnicos = [
            "Grupo 1",
            "Grupo 2",
            "Grupo 3",
            "Grupo 4"
        ]

        grupos_ab = [
            "Grupo A",
            "Grupo B",
            "Grupo C",
            "Grupo D",
            "Grupo E"
        ]

        masters = df[
            df["Cargo"] == "Master"
        ].sample(frac=1)

        tec_a = df[
            df["Cargo"] == "Tecnico A"
        ].sample(frac=1)

        tec_b = df[
            df["Cargo"] == "Tecnico B"
        ].sample(frac=1)

        idx = 0
        for g in grupos_tecnicos:
            for _ in range(2):
                asignacion[
                    masters.iloc[idx]["Nombre"]
                ] = g
                idx += 1

        idx = 0
        for g in grupos_tecnicos:
            for _ in range(7):
                asignacion[
                    tec_a.iloc[idx]["Nombre"]
                ] = g
                idx += 1

        idx = 0
        for g in grupos_tecnicos:
            for _ in range(3):
                asignacion[
                    tec_b.iloc[idx]["Nombre"]
                ] = g
                idx += 1

        ab = df[
            df["Cargo"].astype(str).str.contains(
                "Auxiliar de Abordaje y Atención al Público",
                case=False,
                na=False
            )
        ].sample(frac=1)

        idx = 0
        for g in grupos_ab:
            for _ in range(5):
                asignacion[
                    ab.iloc[idx]["Nombre"]
                ] = g
                idx += 1

        df["Grupo"] = df["Nombre"].map(
            lambda x: asignacion.get(x, "")
        )

        st.session_state["df_grupos"] = df

    if "df_grupos" in st.session_state:
        st.dataframe(
            st.session_state["df_grupos"]
        )

        if st.button("💾 Guardar grupos"):
            guardar_excel(
                repo,
                st.session_state["df_grupos"],
                "empleados.xlsx",
                "Asignación grupos"
            )
            st.success("Guardado")


# =========================================================
# MENÚ PRINCIPAL
# =========================================================

def pantalla_programador():
    modulo = st.radio(
        "Selecciona módulo",
        [
            "👷 Técnicos",
            "📅 Programador Técnicos",
            "🚌 Personal Abordaje",
            "🧩 Grupos"
        ],
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
