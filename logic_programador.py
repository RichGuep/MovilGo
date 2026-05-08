import streamlit as st
import io
import pandas as pd
from datetime import datetime, timedelta

from github import Github
import streamlit as st

# =====================================
# CONEXIÓN GITHUB
# =====================================

def conectar_github():

    try:
        if "GITHUB_TOKEN" not in st.secrets:
            st.error(
                "❌ Token GITHUB_TOKEN no configurado"
            )
            return None

        g = Github(
            st.secrets["GITHUB_TOKEN"]
        )

        repo = g.get_repo(
            "RichGuep/movilgo"
        )

        return repo

    except Exception as e:
        st.error(
            f"Error GitHub: {e}"
        )
        return None

# inicio pantallas

def pantalla_tecnicos():

    st.title("👷 Control de Técnicos - MovilGo")

    repo = conectar_github()

    if not repo:
        st.error("No hay conexión con GitHub")
        return

    # =========================================
    # CARGA DE PERSONAL
    # =========================================

    try:

        contents = repo.get_contents("empleados.xlsx")

        df = pd.read_excel(io.BytesIO(contents.decoded_content))

        df.columns = df.columns.str.strip()

    except Exception as e:

        st.error(f"Error cargando personal: {e}")
        return

    # =========================================
    # FILTROS
    # =========================================

    st.subheader("🔎 Filtros")

    col1, col2, col3 = st.columns(3)

    grupos = st.multiselect(
        "Filtrar por grupo",
        options=df["Grupo"].unique(),
        default=df["Grupo"].unique()
    )

    cargos = st.multiselect(
        "Filtrar por cargo",
        options=df["Cargo"].unique() if "Cargo" in df.columns else [],
        default=df["Cargo"].unique() if "Cargo" in df.columns else []
    )

    df_f = df.copy()

    if grupos:
        df_f = df_f[df_f["Grupo"].isin(grupos)]

    if cargos:
        df_f = df_f[df_f["Cargo"].isin(cargos)]

    # =========================================
    # KPIs TÉCNICOS
    # =========================================

    st.subheader("📊 KPIs de Personal")

    c1, c2, c3 = st.columns(3)

    c1.metric("Total Técnicos", len(df_f))
    c2.metric("Grupos Activos", df_f["Grupo"].nunique())
    c3.metric("Cargos", df_f["Cargo"].nunique() if "Cargo" in df_f.columns else 0)

    st.divider()

    # =========================================
    # DISTRIBUCIÓN POR GRUPO
    # =========================================

    st.subheader("📦 Distribución por Grupo")

    dist = df_f.groupby("Grupo").size().reset_index(name="Cantidad")

    st.bar_chart(dist.set_index("Grupo"))

    # =========================================
    # TABLA EDITABLE (CONTROL OPERATIVO)
    # =========================================

    st.subheader("✍️ Gestión de Personal")

    df_edit = st.data_editor(
        df_f,
        use_container_width=True,
        num_rows="dynamic"
    )

    # =========================================
    # GUARDAR CAMBIOS
    # =========================================

    if st.button("💾 Guardar cambios de personal"):

        try:

            output = io.BytesIO()

            with pd.ExcelWriter(output, engine="openpyxl") as writer:

                df_edit.to_excel(writer, index=False)

            try:

                contents = repo.get_contents("empleados.xlsx")

                repo.update_file(
                    "empleados.xlsx",
                    "Actualización técnicos",
                    output.getvalue(),
                    contents.sha
                )

            except:

                repo.create_file(
                    "empleados.xlsx",
                    "Creación empleados",
                    output.getvalue()
                )

            st.success("✅ Personal actualizado correctamente")

        except Exception as e:

            st.error(f"Error guardando: {e}")

    # =========================================
    # ANALÍTICA SIMPLE POR TÉCNICO
    # =========================================

    st.divider()

    st.subheader("📈 Análisis de distribución")

    if st.checkbox("Ver distribución avanzada"):

        col = "Grupo"

        analisis = df_f.groupby(col).size()

        st.bar_chart(analisis)

    
# =========================================================
# PERSONAL ABORDAJE (VERSIÓN CORREGIDA)
# =========================================================

def pantalla_abordaje():

    st.header("🚌 Programador Personal Abordaje")

    GRUPOS_AB = ["Grupo A", "Grupo B", "Grupo C", "Grupo D", "Grupo E"]

    dias_semana = [
        "Lunes", "Martes", "Miércoles",
        "Jueves", "Viernes", "Sábado", "Domingo"
    ]

    # ============================================
    # CONEXIÓN GITHUB
    # ============================================

    repo = conectar_github()
    if not repo:
        return

    try:
        contents = repo.get_contents("empleados.xlsx")

        df_emp = pd.read_excel(
            io.BytesIO(contents.decoded_content)
        )

        df_emp.columns = df_emp.columns.str.strip()

        df_ab = df_emp[
            df_emp["Cargo"]
            .astype(str)
            .str.contains("Auxiliar de Abordaje", case=False, na=False)
        ]

        if df_ab.empty:
            st.error("No se encontró personal de abordaje.")
            return

        st.success(f"Personal abordaje cargado: {len(df_ab)} personas")

    except Exception as e:
        st.error(f"Error cargando abordaje: {e}")
        return

    # ============================================
    # GRUPOS AUTOMÁTICOS
    # ============================================

    personal_grupos = {}

    nombres = list(df_ab["Nombre"])

    for i, grupo in enumerate(GRUPOS_AB):
        inicio = i * 5
        fin = inicio + 5
        personal_grupos[grupo] = nombres[inicio:fin]

    # ============================================
    # DESCANSOS
    # ============================================

    st.subheader("📅 Parametrizador de Descansos")

    c1, c2 = st.columns(2)

    d_a = c1.selectbox("Grupo A", dias_semana, index=0, key="ab_a")
    d_b = c2.selectbox("Grupo B", dias_semana, index=3, key="ab_b")
    d_c = c1.selectbox("Grupo C", dias_semana, index=4, key="ab_c")
    d_d = c2.selectbox("Grupo D", dias_semana, index=5, key="ab_d")
    d_e = c1.selectbox("Grupo E", dias_semana, index=6, key="ab_e")

    descansos = {
        "Grupo A": dias_semana.index(d_a),
        "Grupo B": dias_semana.index(d_b),
        "Grupo C": dias_semana.index(d_c),
        "Grupo D": dias_semana.index(d_d),
        "Grupo E": dias_semana.index(d_e)
    }

    # ============================================
    # HORARIOS
    # ============================================

    st.subheader("⏰ Horarios")

    h1, h2, h3 = st.columns(3)

    with h1:
        st.markdown("### T1")
        st.time_input("Inicio T1", datetime.strptime("06:00", "%H:%M").time(), key="t1i")
        st.time_input("Fin T1", datetime.strptime("14:00", "%H:%M").time(), key="t1f")

    with h2:
        st.markdown("### T2")
        st.time_input("Inicio T2", datetime.strptime("14:00", "%H:%M").time(), key="t2i")
        st.time_input("Fin T2", datetime.strptime("22:00", "%H:%M").time(), key="t2f")

    with h3:
        st.markdown("### TR")
        st.time_input("Inicio TR", datetime.strptime("10:00", "%H:%M").time(), key="tri")
        st.time_input("Fin TR", datetime.strptime("18:00", "%H:%M").time(), key="trf")

    # ============================================
    # FECHAS
    # ============================================

    st.subheader("📆 Periodo")

    c1, c2 = st.columns(2)

    fecha_ini = c1.date_input("Inicio", datetime.now(), key="ab_fi")
    fecha_fin = c2.date_input("Fin", datetime.now() + timedelta(days=14), key="ab_ff")

    # ============================================
    # FUNCIONES AUXILIARES
    # ============================================

    def rotar_grupos(grupos, semana):
        if semana % 2 == 0:
            return grupos[:2], grupos[2:]
        else:
            return grupos[2:], grupos[:2]

    # ============================================
    # BOTÓN GENERAR
    # ============================================

    if st.button("🚀 Generar Malla Abordaje", use_container_width=True):

        resultados = []

        fechas = pd.date_range(fecha_ini, fecha_fin, freq="D")

        # contador TR
        tr_counter = {
            nombre: 0
            for grupo in personal_grupos.values()
            for nombre in grupo
        }

        # lista personas
        personas = []
        for g, lista in personal_grupos.items():
            for nombre in lista:
                personas.append({"nombre": nombre, "grupo": g})

        for fecha in fechas:

            dia_semana = fecha.weekday()
            semana = fecha.isocalendar().week

            # ======================
            # DESCANSO
            # ======================
            grupo_descanso = None

            for g, d in descansos.items():
                if d == dia_semana:
                    grupo_descanso = g
                    break

            resultados.append({
                "Fecha": fecha,
                "Grupo": grupo_descanso,
                "Turno": "DESC"
            })

            # ======================
            # ACTIVOS
            # ======================
            activos = [g for g in GRUPOS_AB if g != grupo_descanso]

            t1, t2 = rotar_grupos(activos, semana)

            for g in t1:
                resultados.append({"Fecha": fecha, "Grupo": g, "Turno": "T1"})

            for g in t2:
                resultados.append({"Fecha": fecha, "Grupo": g, "Turno": "T2"})

            # ======================
            # TR INTELIGENTE
            # ======================
            grupo_personas = [
                p for p in personas if p["grupo"] == grupo_descanso
            ]

            if grupo_personas:
                seleccion = min(
                    grupo_personas,
                    key=lambda p: tr_counter[p["nombre"]]
                )

                tr_counter[seleccion["nombre"]] += 1

                resultados.append({
                    "Fecha": fecha,
                    "Grupo": grupo_descanso,
                    "Turno": "TR",
                    "Persona_TR": seleccion["nombre"]
                })

        st.session_state["malla_abordaje"] = pd.DataFrame(resultados)

        st.success("✅ Malla optimizada generada correctamente")

    # ============================================
    # MOSTRAR RESULTADOS
    # ============================================

    if "malla_abordaje" in st.session_state:

        df = st.session_state["malla_abordaje"]

        st.subheader("📋 Malla Grupal")

        matriz = df.pivot_table(
            index="Grupo",
            columns="Fecha",
            values="Turno",
            aggfunc="first"
        )

        st.dataframe(matriz, use_container_width=True)

        st.subheader("👤 Personal asignado a TR")

        tr_df = df[df["Turno"] == "TR"][["Fecha", "Grupo", "Persona_TR"]]

        st.dataframe(tr_df, use_container_width=True)


def pantalla_programador():
    modulo = st.radio(
        "Selecciona módulo",
        ["👷 Técnicos", "🚍 Personal Abordaje"],
        horizontal=True
    )

    if modulo == "👷 Técnicos":
        pantalla_tecnicos()
    else:
        pantalla_abordaje()
