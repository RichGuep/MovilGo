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

    
# =========================================================
# PERSONAL ABORDAJE
# =========================================================
def pantalla_abordaje():

    st.header("🚌 Programador Personal Abordaje")

    GRUPOS_AB = [
        "Grupo A",
        "Grupo B",
        "Grupo C",
        "Grupo D",
        "Grupo E"
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

    # ============================================
    # CARGAR PERSONAL DESDE empleados.xlsx
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

        # Filtrar personal de abordaje por Cargo
        df_ab = df_emp[
            df_emp["Cargo"]
            .astype(str)
            .str.contains(
                "Auxiliar de Abordaje",
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

    # ============================================
    # CREAR GRUPOS AUTOMÁTICOS
    # ============================================

    personal_grupos = {}

    nombres = list(df_ab["Nombre"])

    for i, grupo in enumerate(GRUPOS_AB):

        inicio = i * 5
        fin = inicio + 5

        personal_grupos[grupo] = nombres[
            inicio:fin
        ]

    # ============================================
    # PARAMETRIZADOR DESCANSOS
    # ============================================

    st.subheader(
        "📅 Parametrizador de Descansos"
    )

    c1, c2 = st.columns(2)

    d_a = c1.selectbox(
        "Grupo A",
        dias_semana,
        index=0,
        key="ab_a"
    )

    d_b = c2.selectbox(
        "Grupo B",
        dias_semana,
        index=1,
        key="ab_b"
    )

    d_c = c1.selectbox(
        "Grupo C",
        dias_semana,
        index=2,
        key="ab_c"
    )

    d_d = c2.selectbox(
        "Grupo D",
        dias_semana,
        index=3,
        key="ab_d"
    )

    d_e = c1.selectbox(
        "Grupo E",
        dias_semana,
        index=4,
        key="ab_e"
    )

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

        inicio_t1 = st.time_input(
            "Inicio T1",
            datetime.strptime(
                "06:00",
                "%H:%M"
            ).time(),
            key="t1i"
        )

        fin_t1 = st.time_input(
            "Fin T1",
            datetime.strptime(
                "14:00",
                "%H:%M"
            ).time(),
            key="t1f"
        )

    with h2:

        st.markdown("### T2")

        inicio_t2 = st.time_input(
            "Inicio T2",
            datetime.strptime(
                "14:00",
                "%H:%M"
            ).time(),
            key="t2i"
        )

        fin_t2 = st.time_input(
            "Fin T2",
            datetime.strptime(
                "22:00",
                "%H:%M"
            ).time(),
            key="t2f"
        )

    with h3:

        st.markdown("### TR")

        inicio_tr = st.time_input(
            "Inicio TR",
            datetime.strptime(
                "10:00",
                "%H:%M"
            ).time(),
            key="tri"
        )

        fin_tr = st.time_input(
            "Fin TR",
            datetime.strptime(
                "18:00",
                "%H:%M"
            ).time(),
            key="trf"
        )

    # ============================================
    # PERIODO
    # ============================================

    st.subheader("📆 Periodo")

    f1, f2 = st.columns(2)

    fecha_ini = f1.date_input(
        "Inicio",
        datetime.now(),
        key="ab_fi"
    )

    fecha_fin = f2.date_input(
        "Fin",
        datetime.now() + timedelta(days=14),
        key="ab_ff"
    )

    # ============================================
    # BOTÓN GENERAR
    # ============================================

    if st.button("🚀 Generar Malla Abordaje"):

        resultados = []

        fechas = [
            fecha_ini + timedelta(days=x)
            for x in range(
                (fecha_fin - fecha_ini).days + 1
            )
        ]

        conteo_tr = {}

        for grupo in GRUPOS_AB:
            for persona in personal_grupos[grupo]:
                conteo_tr[persona] = 0

        for fecha in fechas:

            fecha_dt = pd.to_datetime(fecha)

            dia_semana = fecha_dt.weekday()

            semana = fecha_dt.isocalendar()[1]

            # ==============================
            # identificar grupo descanso
            # ==============================

            grupos_descanso = [
                g for g, d in descansos.items()
                if d == dia_semana
            ]

            if not grupos_descanso:
                st.error(
                    f"No hay grupo configurado para descansar el día {dias_semana[dia_semana]}"
                )
                return

            if len(grupos_descanso) > 1:
                st.error(
                    f"Hay varios grupos descansando el mismo día ({dias_semana[dia_semana]}). Cada grupo debe tener un día diferente."
                )
                return

            grupo_descanso = grupos_descanso[0]

            grupos_activos = [
                g for g in GRUPOS_AB
                if g != grupo_descanso
            ]

            # ==============================
            # rotación semanal
            # ==============================

            if semana % 2 == 0:
                grupos_t1 = grupos_activos[:2]
                grupos_t2 = grupos_activos[2:]
            else:
                grupos_t2 = grupos_activos[:2]
                grupos_t1 = grupos_activos[2:]

            # ==============================
            # asignar T1
            # ==============================

            for g in grupos_t1:
                resultados.append({
                    "Fecha": fecha_dt,
                    "Grupo": g,
                    "Turno": "T1"
                })

            # ==============================
            # asignar T2
            # ==============================

            for g in grupos_t2:
                resultados.append({
                    "Fecha": fecha_dt,
                    "Grupo": g,
                    "Turno": "T2"
                })

            # ==============================
            # asignar relevo TR
            # ==============================

            personas = personal_grupos[grupo_descanso]

            persona_tr = min(
                personas,
                key=lambda x: conteo_tr[x]
            )

            conteo_tr[persona_tr] += 1

            resultados.append({
                "Fecha": fecha_dt,
                "Grupo": grupo_descanso,
                "Turno": "TR",
                "Persona TR": persona_tr
            })

        df_malla = pd.DataFrame(
            resultados
        )

        st.session_state["malla_abordaje"] = df_malla

        st.success(
            "✅ Malla abordaje generada correctamente"
        )

    # ============================================
    # VISUALIZAR
    # ============================================

    if "malla_abordaje" in st.session_state:

        df = st.session_state[
            "malla_abordaje"
        ]

        st.subheader(
            "📋 Malla Grupal"
        )

        matriz = df.pivot(
            index="Grupo",
            columns="Fecha",
            values="Turno"
        )

        st.dataframe(
            matriz,
            use_container_width=True
        )

        st.subheader(
            "👥 Personal asignado a TR"
        )

        tr_df = df[
            df["Turno"] == "TR"
        ][[
            "Fecha",
            "Grupo",
            "Persona TR"
        ]]

        st.dataframe(
            tr_df,
            use_container_width=True
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
