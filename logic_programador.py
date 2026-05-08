import streamlit as st
import io
import pandas as pd
from datetime import datetime, timedelta

def pantalla_tecnicos():
    st.title("👷 Programador Técnicos")
    st.success("Módulo técnicos funcionando")

def pantalla_abordaje():
        st.title("🚍 Programador Personal Abordaje")

    GRUPOS_AB = [
        "Grupo A",
        "Grupo B",
        "Grupo C",
        "Grupo D",
        "Grupo E"
    ]

    dias_semana = [
        "Lunes","Martes","Miércoles",
        "Jueves","Viernes","Sábado","Domingo"
    ]

    # =====================================
    # CARGAR PERSONAL
    # =====================================

    repo = conectar_github()

    try:
        contents = repo.get_contents(
            "empleados.xlsx"
        )

        df_emp = pd.read_excel(
            io.BytesIO(contents.decoded_content)
        )

        df_emp.columns = (
            df_emp.columns.str.strip()
        )

        df_ab = df_emp[
            df_emp["Area"] == "Abordaje"
        ]

    except Exception as e:
        st.error(
            f"Error cargando abordaje: {e}"
        )
        return

    st.success(
        f"{len(df_ab)} personas cargadas."
    )

    # =====================================
    # PARAMETRIZADOR DESCANSOS
    # =====================================

    st.subheader(
        "📅 Descanso semanal por grupo"
    )

    descansos = {}

    c1, c2 = st.columns(2)

    descansos["Grupo A"] = dias_semana.index(
        c1.selectbox(
            "Grupo A",
            dias_semana,
            index=0
        )
    )

    descansos["Grupo B"] = dias_semana.index(
        c2.selectbox(
            "Grupo B",
            dias_semana,
            index=1
        )
    )

    descansos["Grupo C"] = dias_semana.index(
        c1.selectbox(
            "Grupo C",
            dias_semana,
            index=2
        )
    )

    descansos["Grupo D"] = dias_semana.index(
        c2.selectbox(
            "Grupo D",
            dias_semana,
            index=3
        )
    )

    descansos["Grupo E"] = dias_semana.index(
        c1.selectbox(
            "Grupo E",
            dias_semana,
            index=4
        )
    )

    # =====================================
    # FECHAS
    # =====================================

    st.subheader("📆 Periodo")

    c1, c2 = st.columns(2)

    fecha_ini = c1.date_input(
        "Inicio",
        datetime.now()
    )

    fecha_fin = c2.date_input(
        "Fin",
        datetime.now() + timedelta(days=14)
    )

    # =====================================
    # GENERAR
    # =====================================

    if st.button(
        "🚀 Generar Malla Abordaje"
    ):

        resultados = []

        # contador TR
        tr_acum = {}

        for _, row in df_ab.iterrows():
            tr_acum[row["Nombre"]] = 0

        fechas = [
            fecha_ini + timedelta(days=x)
            for x in range(
                (fecha_fin - fecha_ini).days + 1
            )
        ]

        for fecha in fechas:

            fecha_dt = pd.to_datetime(
                fecha
            )

            dia = fecha_dt.weekday()

            # grupo descanso
            grupo_descanso = None

            for g, d in descansos.items():
                if d == dia:
                    grupo_descanso = g

            activos = [
                g for g in GRUPOS_AB
                if g != grupo_descanso
            ]

            # rotación semanal
            semana = (
                fecha_dt.isocalendar()[1]
            )

            if semana % 2 == 0:
                grupos_t1 = activos[:2]
                grupos_t2 = activos[2:]
            else:
                grupos_t2 = activos[:2]
                grupos_t1 = activos[2:]

            # ------------------------
            # elegir TR
            # ------------------------

            df_activos = df_ab[
                df_ab["Grupo"].isin(
                    activos
                )
            ]

            nombre_tr = min(
                df_activos["Nombre"],
                key=lambda x:
                tr_acum[x]
            )

            tr_acum[nombre_tr] += 1

            # ------------------------
            # guardar personas
            # ------------------------

            for _, persona in df_ab.iterrows():

                grupo = persona["Grupo"]
                nombre = persona["Nombre"]

                if grupo == grupo_descanso:
                    turno = "DESC"

                elif nombre == nombre_tr:
                    turno = "TR"

                elif grupo in grupos_t1:
                    turno = "T1"

                else:
                    turno = "T2"

                resultados.append({
                    "Fecha":
                        fecha_dt.strftime(
                            "%Y-%m-%d"
                        ),
                    "Nombre":
                        nombre,
                    "Grupo":
                        grupo,
                    "Turno":
                        turno
                })

        df_final = pd.DataFrame(
            resultados
        )

        st.session_state[
            "malla_abordaje"
        ] = df_final

        st.success(
            "✅ Malla abordaje generada"
        )

    # =====================================
    # MOSTRAR
    # =====================================

    if (
        "malla_abordaje"
        in st.session_state
    ):

        df = st.session_state[
            "malla_abordaje"
        ]

        st.subheader(
            "📋 Detallado"
        )

        st.dataframe(
            df,
            use_container_width=True,
            height=500
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
