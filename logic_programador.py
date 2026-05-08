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
    st.title("👷 Programador Técnicos")
    st.success("Módulo técnicos funcionando")

    st.header("🚍 Programador Personal Abordaje")

    dias_semana = [
        "Lunes",
        "Martes",
        "Miércoles",
        "Jueves",
        "Viernes",
        "Sábado",
        "Domingo"
    ]

    # =========================================
    # CARGAR PERSONAL ABORDAJE
    # =========================================

    repo = conectar_github()

    if not repo:
        st.error("No se pudo conectar a GitHub.")
        return

    try:
        contents = repo.get_contents("empleados.xlsx")

        df_emp = pd.read_excel(
            io.BytesIO(contents.decoded_content)
        )

        df_emp.columns = df_emp.columns.str.strip()

        columnas = [
            "Nombre",
            "Cedula",
            "Cargo"
        ]

        for c in columnas:
            if c not in df_emp.columns:
                st.error(
                    f"Falta columna '{c}' en empleados.xlsx"
                )
                return

        # Filtrar auxiliares de abordaje
        df_ab = df_emp[
            df_emp["Cargo"]
            .astype(str)
            .str.contains(
                "Auxiliar de Abordaje y Atención al Público ",
                case=False,
                na=False
            )
        ]

        if df_ab.empty:
            st.error(
                "No se encontró personal de abordaje."
            )
            return

        st.success(
            f"Personal abordaje cargado: {len(df_ab)} personas"
        )

    except Exception as e:
        st.error(
            f"Error cargando abordaje: {e}"
        )
        return

    # =========================================
    # PARAMETRIZADOR DESCANSOS
    # =========================================

    st.subheader(
        "📅 Parametrizador de Descansos"
    )

    c1, c2 = st.columns(2)

    d_a = c1.selectbox(
        "Grupo A",
        dias_semana,
        index=0
    )

    d_b = c2.selectbox(
        "Grupo B",
        dias_semana,
        index=1
    )

    d_c = c1.selectbox(
        "Grupo C",
        dias_semana,
        index=2
    )

    d_d = c2.selectbox(
        "Grupo D",
        dias_semana,
        index=3
    )

    d_e = c1.selectbox(
        "Grupo E",
        dias_semana,
        index=4
    )

    # =========================================
    # HORARIOS
    # =========================================

    st.subheader("⏰ Horarios")

    h1, h2, h3 = st.columns(3)

    with h1:
        st.markdown("### T1")
        st.time_input(
            "Inicio T1",
            datetime.strptime(
                "06:00",
                "%H:%M"
            ).time()
        )
        st.time_input(
            "Fin T1",
            datetime.strptime(
                "14:00",
                "%H:%M"
            ).time()
        )

    with h2:
        st.markdown("### T2")
        st.time_input(
            "Inicio T2",
            datetime.strptime(
                "14:00",
                "%H:%M"
            ).time()
        )
        st.time_input(
            "Fin T2",
            datetime.strptime(
                "22:00",
                "%H:%M"
            ).time()
        )

    with h3:
        st.markdown("### TR")
        st.time_input(
            "Inicio TR",
            datetime.strptime(
                "10:00",
                "%H:%M"
            ).time()
        )
        st.time_input(
            "Fin TR",
            datetime.strptime(
                "18:00",
                "%H:%M"
            ).time()
        )

    # =========================================
    # PERIODO
    # =========================================

    st.subheader("📆 Periodo")

    f1, f2 = st.columns(2)

    f1.date_input(
        "Inicio",
        datetime.now()
    )

    f2.date_input(
        "Fin",
        datetime.now() + timedelta(days=14)
    )

    # =========================================
    # BOTÓN
    # =========================================

    if st.button(
        "🚀 Generar Malla Abordaje"
    ):
        st.success(
            "✅ Módulo de abordaje funcionando correctamente."
        )
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
