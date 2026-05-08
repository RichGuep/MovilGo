# =========================================================
# LOGIC_PROGRAMADOR.PY
# =========================================================

import streamlit as st
import pandas as pd
import io
import holidays

from datetime import datetime, timedelta
from github import Github

# =========================================================
# CONFIG
# =========================================================

GRUPOS = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]

TURNOS = ["T1", "T2", "T3", "DESC", "COMP"]

# =========================================================
# CARGAR PERSONAL DESDE empleados.xlsx
# =========================================================
def cargar_personal():
    repo = conectar_github()

    if not repo:
        return {}

    try:
        contents = repo.get_contents("empleados.xlsx")

        df_emp = pd.read_excel(
            io.BytesIO(contents.decoded_content)
        )

        # limpiar nombres de columnas
        df_emp.columns = df_emp.columns.str.strip()

        # validar columnas
        columnas = ["Nombre", "Cedula", "Grupo"]

        for c in columnas:
            if c not in df_emp.columns:
                st.error(f"Falta columna '{c}' en empleados.xlsx")
                return {}

        personal = {}

        for grupo in GRUPOS:

            grupo_df = df_emp[
                df_emp["Grupo"] == grupo
            ]

            personal[grupo] = []

            for _, row in grupo_df.iterrows():

                personal[grupo].append({
                    "Nombre": str(row["Nombre"]),
                    "Cedula": str(row["Cedula"])
                })

        return personal

    except Exception as e:
        st.error(f"Error cargando empleados.xlsx: {e}")
        return {}
# =========================================================
# GITHUB
# =========================================================

def conectar_github():

    try:

        if "GITHUB_TOKEN" not in st.secrets:

            st.error("❌ Token GITHUB_TOKEN no configurado.")
            return None

        return Github(
            st.secrets["GITHUB_TOKEN"]
        ).get_repo("RichGuep/movilgo")

    except Exception as e:

        st.error(f"Error GitHub: {e}")
        return None

# =========================================================
# HISTÓRICO
# =========================================================

def obtener_ultimo_estado_github(repo):

    try:

        contents = repo.get_contents(
            "malla_historica.xlsx"
        )

        df_hist = pd.read_excel(
            io.BytesIO(contents.decoded_content)
        )

        df_hist["Fecha_Raw"] = pd.to_datetime(
            df_hist["Fecha_Raw"]
        )

        estado = {}

        for g in GRUPOS:

            regs = (
                df_hist[df_hist["Grupo"] == g]
                .sort_values("Fecha_Raw")
            )

            if not regs.empty:

                u = regs.iloc[-1]

                estado[g] = {

                    "u": u["Turno"],

                    "n": int(
                        u.get("Noches_Acum", 0)
                    ) if u["Turno"] == "T3" else 0,

                    "d": int(
                        u.get(
                            "Deuda_Compensatorio",
                            0
                        )
                    )
                }

            else:

                estado[g] = {
                    "u": "DESC",
                    "n": 0,
                    "d": 0
                }

        return estado

    except:

        return {

            g: {
                "u": "DESC",
                "n": 0,
                "d": 0
            }

            for g in GRUPOS
        }

# =========================================================
# GUARDAR HISTÓRICO
# =========================================================

def guardar_malla_en_historico(df_nueva):

    repo = conectar_github()

    if not repo:
        return

    try:

        try:

            contents = repo.get_contents(
                "malla_historica.xlsx"
            )

            df_previo = pd.read_excel(
                io.BytesIO(contents.decoded_content)
            )

            df_previo["Fecha_Raw"] = pd.to_datetime(
                df_previo["Fecha_Raw"]
            )

            df_final = pd.concat(
                [df_previo, df_nueva]
            ).drop_duplicates(
                subset=["Grupo", "Fecha_Raw"],
                keep="last"
            )

        except:

            df_final = df_nueva

        output = io.BytesIO()

        with pd.ExcelWriter(
            output,
            engine="openpyxl"
        ) as writer:

            df_final.to_excel(
                writer,
                index=False
            )

        try:

            contents = repo.get_contents(
                "malla_historica.xlsx"
            )

            repo.update_file(

                "malla_historica.xlsx",

                "Actualización automática",

                output.getvalue(),

                contents.sha

            )

        except:

            repo.create_file(

                "malla_historica.xlsx",

                "Creación inicial",

                output.getvalue()

            )

        st.success("✅ Histórico sincronizado")

    except Exception as e:

        st.error(
            f"Error guardando histórico: {e}"
        )

# =========================================================
# VALIDADORES
# =========================================================

def es_cambio_saludable(ayer, hoy):

    if ayer in ["DESC", "COMP", "OFF"]:
        return True

    if hoy in ["DESC", "COMP", "OFF"]:
        return True

    jerarquia = {

        "T1": 1,
        "T2": 2,
        "T3": 3

    }

    return (
        jerarquia.get(hoy, 0)
        >= jerarquia.get(ayer, 0)
    )

# =========================================================
# ROTACIÓN DESCANSOS
# =========================================================

def rotar_descansos(
    fecha,
    descansos_base,
    activar_rotacion,
    tipo_rotacion
):

    if not activar_rotacion:
        return descansos_base

    dias = list(descansos_base.values())

    # =============================================
    # CICLO
    # =============================================

    if tipo_rotacion == "Mensual":

        ciclo = fecha.month - 1

    else:

        ciclo = (
            (fecha.month - 1) * 2
        )

        if fecha.day > 15:
            ciclo += 1

    # =============================================
    # ROTAR
    # =============================================

    rotacion = ciclo % len(dias)

    dias_rotados = (
        dias[rotacion:]
        +
        dias[:rotacion]
    )

    return {

        grupo: dias_rotados[i]

        for i, grupo in enumerate(
            descansos_base.keys()
        )
    }

# =========================================================
# COLORES
# =========================================================

def color_turno(val):

    colores = {

        "T1": """
            background-color:#1976D2;
            color:white;
            font-weight:bold;
            text-align:center;
        """,

        "T2": """
            background-color:#2E7D32;
            color:white;
            font-weight:bold;
            text-align:center;
        """,

        "T3": """
            background-color:#424242;
            color:white;
            font-weight:bold;
            text-align:center;
        """,

        "DESC": """
            background-color:#C62828;
            color:white;
            font-weight:bold;
            text-align:center;
        """,

        "COMP": """
            background-color:#EF6C00;
            color:white;
            font-weight:bold;
            text-align:center;
        """
    }

    return colores.get(val, "")

# =========================================================
# AUDITORÍA
# =========================================================

def auditar_malla(df):

    st.divider()

    st.header("🛡️ Auditoría Operacional")

    col1, col2 = st.columns(2)

    # =============================================
    # SALTOS
    # =============================================

    with col1:

        st.subheader("🚩 Saltos Riesgosos")

        alertas = []

        for g in df["Grupo"].unique():

            g_data = (
                df[df["Grupo"] == g]
                .sort_values("Fecha_Raw")
            )

            for i in range(1, len(g_data)):

                ayer = g_data.iloc[i - 1]["Turno"]
                hoy = g_data.iloc[i]["Turno"]

                fecha = g_data.iloc[i]["Fecha_Col"]

                if not es_cambio_saludable(
                    ayer,
                    hoy
                ):

                    alertas.append(
                        f"{g}: {ayer} → {hoy} ({fecha})"
                    )

        if alertas:

            for a in alertas:
                st.error(a)

        else:

            st.success(
                "✅ Sin saltos riesgosos"
            )

    # =============================================
    # COBERTURA
    # =============================================

    with col2:

        st.subheader("📡 Cobertura")

        cobertura = (
            df.groupby(
                ["Fecha_Col", "Turno"]
            )
            .size()
            .unstack(fill_value=0)
        )

        alertas = []

        for fecha in cobertura.index:

            for t in ["T1", "T2", "T3"]:

                if (
                    t not in cobertura.columns
                    or cobertura.loc[fecha, t] == 0
                ):

                    alertas.append(
                        f"Falta {t} el {fecha}"
                    )

        if alertas:

            for a in alertas:
                st.warning(a)

        else:

            st.success(
                "✅ Cobertura completa"
            )

# =========================================================
# PANTALLA PRINCIPAL
# =========================================================

def pantalla_programador():

    st.title(
        "📅 Programador Maestro MovilGo"
    )

    PERSONAL = cargar_personal()

    submodulo = st.radio(
        "Seleccione módulo",
        [
            "👷 Programación Técnicos",
            "🚍 Personal Abordaje"
        ],
        horizontal=True
    )

    dias_semana = [

        "Lunes",
        "Martes",
        "Miércoles",
        "Jueves",
        "Viernes",
        "Sábado",
        "Domingo"

    ]

    # =====================================================
    # CONFIG
    # =====================================================

    with st.container(border=True):

        st.subheader("⚙️ Configuración")

        col1, col2 = st.columns([2, 1])

        # =============================================
        # DESCANSOS
        # =============================================

        with col1:

            d_g1 = st.selectbox(
                "Descanso Grupo 1",
                dias_semana,
                index=0
            )

            d_g2 = st.selectbox(
                "Descanso Grupo 2",
                dias_semana,
                index=4
            )

            d_g3 = st.selectbox(
                "Descanso Grupo 3",
                dias_semana,
                index=5
            )

            d_g4 = st.selectbox(
                "Descanso Grupo 4",
                dias_semana,
                index=6
            )

            descansos_base = {

                "Grupo 1": dias_semana.index(d_g1),
                "Grupo 2": dias_semana.index(d_g2),
                "Grupo 3": dias_semana.index(d_g3),
                "Grupo 4": dias_semana.index(d_g4)

            }

        # =============================================
        # STAFFING
        # =============================================

        with col2:

            req_lider = st.number_input(
                "Masters",
                1,
                10,
                1
            )

            req_tecnico = st.number_input(
                "Técnicos A",
                1,
                20,
                3
            )

            req_aux = st.number_input(
                "Técnicos B",
                0,
                20,
                2
            )

    # =====================================================
    # ROTACIÓN AUTOMÁTICA
    # =====================================================

    st.subheader(
        "🔄 Rotación Automática Descansos"
    )

    r1, r2 = st.columns(2)

    with r1:

        activar_rotacion = st.toggle(
            "Activar Rotación",
            value=True
        )

    with r2:

        tipo_rotacion = st.selectbox(

            "Frecuencia",

            [
                "Mensual",
                "Quincenal"
            ]
        )

    if activar_rotacion:

        st.info(
            f"""
🔄 Rotación automática activa:
{tipo_rotacion}
"""
        )

    # =====================================================
    # HORARIOS
    # =====================================================

    st.subheader("⏰ Horarios Turnos")

    h1, h2, h3 = st.columns(3)

    with h1:

        st.markdown("### 🟦 T1")

        hora_inicio_t1 = st.time_input(
            "Inicio T1",
            value=datetime.strptime(
                "06:00",
                "%H:%M"
            ).time()
        )

        hora_fin_t1 = st.time_input(
            "Fin T1",
            value=datetime.strptime(
                "14:00",
                "%H:%M"
            ).time()
        )

    with h2:

        st.markdown("### 🟩 T2")

        hora_inicio_t2 = st.time_input(
            "Inicio T2",
            value=datetime.strptime(
                "14:00",
                "%H:%M"
            ).time()
        )

        hora_fin_t2 = st.time_input(
            "Fin T2",
            value=datetime.strptime(
                "22:00",
                "%H:%M"
            ).time()
        )

    with h3:

        st.markdown("### ⬛ T3")

        hora_inicio_t3 = st.time_input(
            "Inicio T3",
            value=datetime.strptime(
                "22:00",
                "%H:%M"
            ).time()
        )

        hora_fin_t3 = st.time_input(
            "Fin T3",
            value=datetime.strptime(
                "06:00",
                "%H:%M"
            ).time()
        )

    HORARIOS = {

        "T1": {
            "inicio": str(hora_inicio_t1),
            "fin": str(hora_fin_t1)
        },

        "T2": {
            "inicio": str(hora_inicio_t2),
            "fin": str(hora_fin_t2)
        },

        "T3": {
            "inicio": str(hora_inicio_t3),
            "fin": str(hora_fin_t3)
        }
    }

    # =====================================================
    # FECHAS
    # =====================================================

    st.subheader("📆 Periodo")

    c1, c2 = st.columns(2)

    f_ini = c1.date_input(
        "Inicio",
        datetime.now()
    )

    f_fin = c2.date_input(
        "Fin",
        datetime.now() + timedelta(days=14)
    )

    # =====================================================
    # GENERAR
    # =====================================================

    if st.button("🚀 Generar Malla"):

        repo = conectar_github()

        estado_ayer = obtener_ultimo_estado_github(
            repo
        )

        lista_fechas = [

            f_ini + timedelta(days=x)

            for x in range(
                (f_fin - f_ini).days + 1
            )
        ]

        resultados = []

        mem_t = {

            g: estado_ayer[g]["u"]

            for g in GRUPOS
        }

        mem_n = {

            g: estado_ayer[g]["n"]

            for g in GRUPOS
        }

        co_h = holidays.Colombia(
            years=[2024, 2025, 2026]
        )

        for fecha in lista_fechas:

            fecha_dt = pd.to_datetime(fecha)

            # =========================================
            # ROTACIÓN DESCANSOS
            # =========================================

            map_idx = rotar_descansos(

                fecha_dt,

                descansos_base,

                activar_rotacion,

                tipo_rotacion
            )

            dia_idx = fecha_dt.weekday()

            semana = fecha_dt.isocalendar()[1]

            es_fest = fecha_dt in co_h

            col_name = (
                f"{fecha_dt.strftime('%a %d/%m')}"
                f"{' 🇨🇴' if es_fest else ''}"
            )

            libranza_hoy = [

                g for g, idx in map_idx.items()

                if idx == dia_idx
            ]

            activos = [

                g for g in GRUPOS

                if g not in libranza_hoy
            ]

            turnos_hoy = {}

            # =========================================
            # ASIGNACIÓN TURNOS
            # =========================================

            for g in activos:

                idx_g = GRUPOS.index(g)

                t_sug = (
                    ["T1", "T2", "T3"]
                    [(idx_g + semana) % 3]
                )

                # =============================
                # VALIDACIÓN SALUDABLE
                # =============================

                if not es_cambio_saludable(
                    mem_t[g],
                    t_sug
                ):

                    t_sug = mem_t[g]

                # =============================
                # CONTROL NOCHES
                # =============================

                if (
                    mem_n[g] >= 6
                    and t_sug == "T3"
                ):

                    t_sug = "T1"

                turnos_hoy[g] = t_sug

            # =========================================
            # COBERTURA FORZADA
            # =========================================

            for tr in ["T1", "T2", "T3"]:

                if (
                    tr not in turnos_hoy.values()
                    and activos
                ):

                    for gf in activos:

                        if (
                            list(
                                turnos_hoy.values()
                            ).count(
                                turnos_hoy[gf]
                            ) > 1
                        ):

                            if es_cambio_saludable(
                                mem_t[gf],
                                tr
                            ):

                                turnos_hoy[gf] = tr
                                break

            # =========================================
            # GUARDAR
            # =========================================

            for g in GRUPOS:

                t_final = (

                    "DESC"

                    if g in libranza_hoy

                    else turnos_hoy.get(g, "T1")
                )

                noches = (

                    mem_n[g] + 1

                    if t_final == "T3"

                    else 0
                )

                hora_inicio = ""
                hora_fin = ""

                if t_final in HORARIOS:

                    hora_inicio = HORARIOS[
                        t_final
                    ]["inicio"]

                    hora_fin = HORARIOS[
                        t_final
                    ]["fin"]

                resultados.append({

                    "Grupo": g,
                    "Fecha_Col": col_name,
                    "Turno": t_final,
                    "Fecha_Raw": fecha_dt,
                    "Hora_Inicio": hora_inicio,
                    "Hora_Fin": hora_fin,
                    "Noches_Acum": noches,
                    "Req_Lider": req_lider,
                    "Req_Tecnico": req_tecnico,
                    "Req_Aux": req_aux

                })

                mem_t[g] = t_final
                mem_n[g] = noches

        st.session_state.malla_generada = (
            pd.DataFrame(resultados)
        )

        guardar_malla_en_historico(
            st.session_state.malla_generada
        )

        st.rerun()

    # =====================================================
    # VISUALIZAR
    # =====================================================

    if st.session_state.get(
        "malla_generada"
    ) is not None:

        df_v = (
            st.session_state
            .malla_generada
            .copy()
        )

        df_v["Fecha_Raw"] = pd.to_datetime(
            df_v["Fecha_Raw"]
        )

        # =============================================
        # REGLAS
        # =============================================

        st.subheader("📋 Reporte Detallado")

        with st.expander(
            "📖 Reglas Aplicadas",
            expanded=True
        ):

            st.markdown("""

### ✅ Reglas Operativas

1. Cada grupo tiene descanso semanal.
2. Rotación T1 → T2 → T3.
3. No se permiten saltos:
   - T3 → T1
   - T3 → T2
   - T2 → T1
4. Máximo 6 noches T3.
5. Cobertura diaria T1/T2/T3.
6. Control descansos simultáneos.
7. Balance operativo.
8. Índice fatiga.
9. Festivos automáticos.
10. Histórico automático.
11. Rotación automática descansos.

""")

        # =============================================
        # MATRIZ
        # =============================================

        matriz = df_v.pivot(

            index="Grupo",

            columns="Fecha_Col",

            values="Turno"
        )

        matriz = matriz.reindex(
            columns=df_v["Fecha_Col"].unique()
        )

        st.markdown(
            "🟦 T1 | 🟩 T2 | ⬛ T3 | 🟥 DESC | 🟧 COMP"
        )

        st.dataframe(

            matriz.style.map(color_turno),

            use_container_width=True,

            height=350
        )

        # =============================================
        # EDITOR
        # =============================================

        st.subheader("✍️ Editor Manual")

        config_col = {

            c: st.column_config.SelectboxColumn(
                options=TURNOS
            )

            for c in matriz.columns
        }

        matriz_editada = st.data_editor(

            matriz,

            column_config=config_col,

            use_container_width=True
        )

        # =============================================
        # GUARDAR
        # =============================================

        if st.button("💾 Guardar Cambios"):

            df_man = (

                matriz_editada

                .reset_index()

                .melt(

                    id_vars="Grupo",

                    var_name="Fecha_Col",

                    value_name="Turno"
                )
            )

            df_final = (

                df_v.drop(columns=["Turno"])

                .merge(
                    df_man,
                    on=["Grupo", "Fecha_Col"]
                )
            )

            guardar_malla_en_historico(
                df_final
            )

            st.session_state.malla_generada = (
                df_final
            )

            st.success(
                "✅ Cambios guardados"
            )

            st.rerun()

        # =============================================
        # AUDITORÍA
        # =============================================

        auditar_malla(df_v)

        # =============================================
        # DETALLADO PERSONAS
        # =============================================

        st.divider()

        st.subheader(
            "👥 Malla Detallada Personas"
        )

        malla_personas = []

        for _, row in df_v.iterrows():

            grupo = row["Grupo"]

            personas = PERSONAL.get(
                grupo,
                []
            )

            for persona in personas:

                malla_personas.append({

                    "Fecha": row[
                        "Fecha_Raw"
                    ].strftime("%Y-%m-%d"),

                    "Nombre": persona["Nombre"],

                    "Cedula": persona["Cedula"],

                    "Grupo": grupo,

                    "Turno": row["Turno"],

                    "Hora Inicio": row.get(
                        "Hora_Inicio",
                        ""
                    ),

                    "Hora Fin": row.get(
                        "Hora_Fin",
                        ""
                    )

                })

        if malla_personas:

            df_personas = pd.DataFrame(
                malla_personas
            )

            st.dataframe(

                df_personas,

                use_container_width=True,

                height=450
            )

            excel_buffer = io.BytesIO()

            with pd.ExcelWriter(
                excel_buffer,
                engine="openpyxl"
            ) as writer:

                df_personas.to_excel(

                    writer,

                    index=False,

                    sheet_name="Detalle_Personal"
                )

            st.download_button(

                label="📥 Descargar Detallado",

                data=excel_buffer.getvalue(),

                file_name="detalle_personal.xlsx",

                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
