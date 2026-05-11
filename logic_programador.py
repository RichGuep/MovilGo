import streamlit as st
# logic_programador.py

```python
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
# GUARDAR EMPLEADOS
# =========================================================


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


# =========================================================
# PANTALLA TÉCNICOS
# =========================================================


def pantalla_tecnicos():

    st.title("👷 Control Técnicos - MovilGo")

    repo = conectar_github()

    if not repo:
        return

    try:
        contents = repo.get_contents("empleados.xlsx")
        df = pd.read_excel(io.BytesIO(contents.decoded_content))

    except Exception as e:
        st.error(f"❌ Error cargando empleados.xlsx: {e}")
        return

    df.columns = df.columns.str.strip()

    if "Grupo" not in df.columns:
        df["Grupo"] = ""

    required_cols = ["Nombre", "Cargo"]

    for col in required_cols:
        if col not in df.columns:
            st.error(f"❌ Falta columna obligatoria: {col}")
            return

    # =====================================
    # FILTRO TÉCNICOS
    # =====================================

    df_tecnicos = df[
        df["Cargo"].astype(str).str.contains(
            "Master|Tecnico A|Tecnico B",
            case=False,
            na=False
        )
    ].copy()

    st.subheader("📋 Personal Técnico")

    st.dataframe(df_tecnicos, use_container_width=True)

    # =====================================
    # PARAMETRIZADOR TURNOS
    # =====================================

    st.subheader("⏰ Parametrizador de Turnos")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("### T1")
        t1_inicio = st.time_input(
            "Inicio T1",
            datetime.strptime("06:00", "%H:%M").time(),
            key="t1_inicio"
        )

        t1_fin = st.time_input(
            "Fin T1",
            datetime.strptime("14:00", "%H:%M").time(),
            key="t1_fin"
        )

    with c2:
        st.markdown("### T2")

        t2_inicio = st.time_input(
            "Inicio T2",
            datetime.strptime("14:00", "%H:%M").time(),
            key="t2_inicio"
        )

        t2_fin = st.time_input(
            "Fin T2",
            datetime.strptime("22:00", "%H:%M").time(),
            key="t2_fin"
        )

    with c3:
        st.markdown("### DESCANSO")

        dia_descanso = st.selectbox(
            "Día descanso general",
            [
                "Lunes",
                "Martes",
                "Miércoles",
                "Jueves",
                "Viernes",
                "Sábado",
                "Domingo"
            ]
        )

    st.divider()

    # =====================================
    # KPIs
    # =====================================

    c1, c2, c3 = st.columns(3)

    c1.metric("Total Técnicos", len(df_tecnicos))
    c2.metric("Grupos", df_tecnicos["Grupo"].nunique())
    c3.metric("Cargos", df_tecnicos["Cargo"].nunique())

    # =====================================
    # DISTRIBUCIÓN
    # =====================================

    st.subheader("📦 Distribución por Grupo")

    dist = df_tecnicos.groupby("Grupo").size().reset_index(name="Cantidad")

    st.bar_chart(dist.set_index("Grupo"))

    st.dataframe(dist, use_container_width=True)

    # =====================================
    # EDITOR
    # =====================================

    st.subheader("✍️ Gestión Personal")

    df_edit = st.data_editor(
        df_tecnicos,
        use_container_width=True,
        num_rows="dynamic",
        key="editor_tecnicos"
    )

    if st.button("💾 Guardar técnicos"):

        guardar_empleados(repo, df_edit)

        st.success("✅ Técnicos guardados correctamente")


# =========================================================
# PROGRAMADOR TÉCNICOS
# =========================================================


def pantalla_programador_tecnicos():

    st.title("📅 Programador Técnicos")

    grupos = [
        "Grupo 1",
        "Grupo 2",
        "Grupo 3",
        "Grupo 4"
    ]

    dias_semana = [
        "Lunes",
        "Martes",
        "Miércoles",
        "Jueves",
        "Viernes",
        "Sábado",
        "Domingo"
    ]

    st.subheader("📅 Configuración Descansos")

    c1, c2 = st.columns(2)

    d1 = c1.selectbox("Grupo 1", dias_semana, index=0)
    d2 = c2.selectbox("Grupo 2", dias_semana, index=1)
    d3 = c1.selectbox("Grupo 3", dias_semana, index=2)
    d4 = c2.selectbox("Grupo 4", dias_semana, index=3)

    descansos = {
        "Grupo 1": d1,
        "Grupo 2": d2,
        "Grupo 3": d3,
        "Grupo 4": d4
    }

    st.subheader("📆 Periodo")

    c1, c2 = st.columns(2)

    fecha_ini = c1.date_input(
        "Fecha inicio",
        datetime.now(),
        key="tec_fi"
    )

    fecha_fin = c2.date_input(
        "Fecha fin",
        datetime.now() + timedelta(days=14),
        key="tec_ff"
    )

    if st.button("🚀 Generar Malla Técnicos"):

        fechas = pd.date_range(fecha_ini, fecha_fin, freq="D")

        resultados = []

        for fecha in fechas:

            nombre_dia = dias_semana[fecha.weekday()]

            for grupo in grupos:

                if descansos[grupo] == nombre_dia:
                    turno = "DESC"
                else:
                    semana = fecha.isocalendar().week

                    if semana % 2 == 0:
                        turno = "T1"
                    else:
                        turno = "T2"

                resultados.append({
                    "Fecha": fecha,
                    "Grupo": grupo,
                    "Turno": turno
                })

        st.session_state["malla_tecnicos"] = pd.DataFrame(resultados)

        st.success("✅ Malla técnicos generada")

    if "malla_tecnicos" in st.session_state:

        df = st.session_state["malla_tecnicos"]

        matriz = df.pivot_table(
            index="Grupo",
            columns="Fecha",
            values="Turno",
            aggfunc="first"
        )

        st.dataframe(matriz, use_container_width=True)


# =========================================================
# PERSONAL ABORDAJE
# =========================================================


def pantalla_abordaje():

    st.title("🚌 Programador Personal Abordaje")

    repo = conectar_github()

    if not repo:
        return

    try:
        contents = repo.get_contents("empleados.xlsx")

        df = pd.read_excel(io.BytesIO(contents.decoded_content))

    except Exception as e:
        st.error(f"❌ Error cargando empleados.xlsx: {e}")
        return

    df.columns = df.columns.str.strip()

    df_ab = df[
        df["Cargo"].astype(str).str.contains(
            "Auxiliar de Abordaje y Atención al Público",
            case=False,
            na=False
        )
    ].copy()

    if df_ab.empty:
        st.warning("⚠️ No hay auxiliares de abordaje")
        return

    st.success(f"✅ Personal cargado: {len(df_ab)}")

    grupos = [
        "Grupo A",
        "Grupo B",
        "Grupo C",
        "Grupo D",
        "Grupo E"
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

    st.subheader("📅 Descansos")

    descansos = {}

    for grupo in grupos:

        descansos[grupo] = st.selectbox(
            f"Descanso {grupo}",
            dias,
            key=grupo
        )

    st.subheader("📆 Periodo")

    c1, c2 = st.columns(2)

    fecha_ini = c1.date_input(
        "Inicio",
        datetime.now(),
        key="ab_ini"
    )

    fecha_fin = c2.date_input(
        "Fin",
        datetime.now() + timedelta(days=14),
        key="ab_fin"
    )

    if st.button("🚀 Generar Malla Abordaje"):

        fechas = pd.date_range(fecha_ini, fecha_fin, freq="D")

        resultados = []

        for fecha in fechas:

            nombre_dia = dias[fecha.weekday()]

            for grupo in grupos:

                if descansos[grupo] == nombre_dia:
                    turno = "DESC"
                else:

                    semana = fecha.isocalendar().week

                    if semana % 2 == 0:
                        turno = "T1"
                    else:
                        turno = "T2"

                resultados.append({
                    "Fecha": fecha,
                    "Grupo": grupo,
                    "Turno": turno
                })

        st.session_state["malla_abordaje"] = pd.DataFrame(resultados)

        st.success("✅ Malla abordaje generada")

    if "malla_abordaje" in st.session_state:

        df = st.session_state["malla_abordaje"]

        matriz = df.pivot_table(
            index="Grupo",
            columns="Fecha",
            values="Turno",
            aggfunc="first"
        )

        st.dataframe(matriz, use_container_width=True)


# =========================================================
# ASIGNACIÓN DE GRUPOS
# =========================================================


def pantalla_asignacion_grupos():

    st.title("🧩 Asignación de Grupos")

    repo = conectar_github()

    if not repo:
        return

    try:
        contents = repo.get_contents("empleados.xlsx")

        df = pd.read_excel(io.BytesIO(contents.decoded_content))

    except Exception as e:
        st.error(f"❌ Error leyendo archivo: {e}")
        return

    df.columns = df.columns.str.strip()

    if "Grupo" not in df.columns:
        df["Grupo"] = ""

    st.subheader("📋 Personal Actual")

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

        # =====================================
        # MASTER
        # =====================================

        masters = df[
            df["Cargo"] == "Master"
        ].sample(frac=1).reset_index(drop=True)

        if len(masters) < 8:
            st.error("❌ Se requieren 8 Master")
            return

        idx = 0

        for grupo in grupos_tecnicos:
            for _ in range(2):
                asignacion[
                    masters.iloc[idx]["Nombre"]
                ] = grupo
                idx += 1

        # =====================================
        # TECNICO A
        # =====================================

        tec_a = df[
            df["Cargo"] == "Tecnico A"
        ].sample(frac=1).reset_index(drop=True)

        if len(tec_a) < 28:
            st.error("❌ Se requieren 28 Tecnico A")
            return

        idx = 0

        for grupo in grupos_tecnicos:
            for _ in range(7):
                asignacion[
                    tec_a.iloc[idx]["Nombre"]
                ] = grupo
                idx += 1

        # =====================================
        # TECNICO B
        # =====================================

        tec_b = df[
            df["Cargo"] == "Tecnico B"
        ].sample(frac=1).reset_index(drop=True)

        if len(tec_b) < 12:
            st.error("❌ Se requieren 12 Tecnico B")
            return

        idx = 0

        for grupo in grupos_tecnicos:
            for _ in range(3):
                asignacion[
                    tec_b.iloc[idx]["Nombre"]
                ] = grupo
                idx += 1

        # =====================================
        # ABORDAJE
        # =====================================

        abordaje = df[
            df["Cargo"].astype(str).str.contains(
                "Auxiliar de Abordaje y Atención al Público",
                case=False,
                na=False
            )
        ].sample(frac=1).reset_index(drop=True)

        if len(abordaje) < 25:
            st.error("❌ Se requieren 25 auxiliares")
            return

        idx = 0

        for grupo in grupos_abordaje:
            for _ in range(5):

                asignacion[
                    abordaje.iloc[idx]["Nombre"]
                ] = grupo

                idx += 1

        # =====================================
        # APLICAR
        # =====================================

        df["Grupo"] = df["Nombre"].map(
            lambda x: asignacion.get(x, "")
        )

        st.session_state["df_grupos"] = df

        st.success("✅ Grupos asignados correctamente")

    if "df_grupos" in st.session_state:

        st.subheader("📊 Resultado")

        st.dataframe(
            st.session_state["df_grupos"],
            use_container_width=True
        )

        if st.button("💾 Guardar grupos"):

            guardar_empleados(
                repo,
                st.session_state["df_grupos"]
            )

            st.success("✅ Guardado correctamente")


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
