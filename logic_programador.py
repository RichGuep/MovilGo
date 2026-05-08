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
    # CARGAR PERSONAL
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

        personal_grupos[grupo] = nombres[inicio:fin]

    # ============================================
    # DESCANSOS
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
        index=3,
        key="ab_b"
    )

    d_c = c1.selectbox(
        "Grupo C",
        dias_semana,
        index=4,
        key="ab_c"
    )

    d_d = c2.selectbox(
        "Grupo D",
        dias_semana,
        index=5,
        key="ab_d"
    )

    d_e = c1.selectbox(
        "Grupo E",
        dias_semana,
        index=6,
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
        st.time_input(
            "Inicio T1",
            datetime.strptime(
                "06:00",
                "%H:%M"
            ).time(),
            key="t1i"
        )
        st.time_input(
            "Fin T1",
            datetime.strptime(
                "14:00",
                "%H:%M"
            ).time(),
            key="t1f"
        )

    with h2:
        st.markdown("### T2")
        st.time_input(
            "Inicio T2",
            datetime.strptime(
                "14:00",
                "%H:%M"
            ).time(),
            key="t2i"
        )
        st.time_input(
            "Fin T2",
            datetime.strptime(
                "22:00",
                "%H:%M"
            ).time(),
            key="t2f"
        )

    with h3:
        st.markdown("### TR")
        st.time_input(
            "Inicio TR",
            datetime.strptime(
                "10:00",
                "%H:%M"
            ).time(),
            key="tri"
        )
        st.time_input(
            "Fin TR",
            datetime.strptime(
                "18:00",
                "%H:%M"
            ).time(),
            key="trf"
        )

    # ============================================
    # FECHAS
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
        datetime.now()
        + timedelta(days=14),
        key="ab_ff"
    )

# =========================================
# BOTÓN GENERAR
# =========================================

if st.button(
    "🚀 Generar Malla Abordaje",
    use_container_width=True
):

    resultados = []

    fechas = pd.date_range(
        fecha_ini,
        fecha_fin,
        freq="D"
    )

    tr_acumulado = {
        p["Nombre"]: 0
        for grupo in personal_grupos.values()
        for p in grupo
    }

    for fecha in fechas:

        dia_semana = fecha.weekday()
        semana = fecha.isocalendar().week

        # identificar grupo descanso
        grupo_descanso = None

        for g, d in descansos.items():
            if d == dia_semana:
                grupo_descanso = g
                break

        # guardar DESC
        resultados.append({
            "Fecha": fecha.strftime("%Y-%m-%d"),
            "Grupo": grupo_descanso,
            "Turno": "DESC"
        })

        # grupos activos
        grupos_activos = [
            g for g in GRUPOS_AB
            if g != grupo_descanso
        ]

        # rotación semanal
        if semana % 2 == 0:
            grupos_t1 = grupos_activos[:2]
            grupos_t2 = grupos_activos[2:]
        else:
            grupos_t2 = grupos_activos[:2]
            grupos_t1 = grupos_activos[2:]

        # guardar T1
        for g in grupos_t1:
            resultados.append({
                "Fecha": fecha.strftime("%Y-%m-%d"),
                "Grupo": g,
                "Turno": "T1"
            })

        # guardar T2
        for g in grupos_t2:
            resultados.append({
                "Fecha": fecha.strftime("%Y-%m-%d"),
                "Grupo": g,
                "Turno": "T2"
            })

        # asignar relevo TR
        personas_descanso = personal_grupos[
            grupo_descanso
        ]

        relevo = min(
            personas_descanso,
            key=lambda x: tr_acumulado[
                x["Nombre"]
            ]
        )

        tr_acumulado[
            relevo["Nombre"]
        ] += 1

        resultados.append({
            "Fecha": fecha.strftime("%Y-%m-%d"),
            "Grupo": grupo_descanso,
            "Turno": "TR",
            "Persona_TR": relevo["Nombre"]
        })

    st.session_state[
        "malla_abordaje"
    ] = pd.DataFrame(
        resultados
    )

    st.success(
        "✅ Malla de abordaje generada correctamente"
    )

# =========================================
# MOSTRAR MALLA
# =========================================

if "malla_abordaje" in st.session_state:

    df = st.session_state[
        "malla_abordaje"
    ]

    st.subheader(
        "📋 Malla Grupal"
    )

    matriz = df.pivot_table(
        index="Grupo",
        columns="Fecha",
        values="Turno",
        aggfunc="first"
    )

    st.dataframe(
        matriz,
        use_container_width=True
    )

    st.subheader(
        "👤 Personal asignado a TR"
    )

    tr_df = df[
        df["Turno"] == "TR"
    ][[
        "Fecha",
        "Grupo",
        "Persona_TR"
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
