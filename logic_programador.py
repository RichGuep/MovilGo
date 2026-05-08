# =========================================================
# LOGIC_PROGRAMADOR.PY
# =========================================================

import streamlit as st
import pandas as pd
import io
import holidays
from datetime import datetime, timedelta
from github import Github

GRUPOS = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
TURNOS = ["T1", "T2", "T3", "DESC", "COMP"]

# =========================================================
# GITHUB
# =========================================================

def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            st.error("❌ Token GITHUB_TOKEN no configurado.")
            return None
        return Github(st.secrets["GITHUB_TOKEN"]).get_repo("RichGuep/movilgo")
    except Exception as e:
        st.error(f"Error GitHub: {e}")
        return None

# =========================================================
# HISTÓRICO
# =========================================================

def obtener_ultimo_estado_github(repo):
    try:
        contents = repo.get_contents("malla_historica.xlsx")
        df_hist = pd.read_excel(io.BytesIO(contents.decoded_content))
        df_hist["Fecha_Raw"] = pd.to_datetime(df_hist["Fecha_Raw"])

        estado = {}

        for g in GRUPOS:
            regs = df_hist[df_hist["Grupo"] == g].sort_values("Fecha_Raw")

            if not regs.empty:
                u = regs.iloc[-1]

                estado[g] = {
                    "u": u["Turno"],
                    "n": int(u.get("Noches_Acum", 0)) if u["Turno"] == "T3" else 0,
                    "d": int(u.get("Deuda_Compensatorio", 0))
                }

            else:
                estado[g] = {"u": "DESC", "n": 0, "d": 0}

        return estado

    except:
        return {
            g: {"u": "DESC", "n": 0, "d": 0}
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
            contents = repo.get_contents("malla_historica.xlsx")

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

        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_final.to_excel(writer, index=False)

        try:
            contents = repo.get_contents("malla_historica.xlsx")

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
        st.error(f"Error guardando histórico: {e}")

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

    return jerarquia.get(hoy, 0) >= jerarquia.get(ayer, 0)

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

    return colores.get(
        val,
        """
        background-color:white;
        color:black;
        """
    )

# =========================================================
# AUDITORÍA
# =========================================================

def auditar_malla(df):

    st.divider()

    st.header("🛡️ Auditoría Operacional")

    # =====================================================
    # ALERTAS
    # =====================================================

    col1, col2 = st.columns(2)

    with col1:

        st.subheader("🚩 Saltos Riesgosos")

        alertas_salud = []

        for g in df["Grupo"].unique():

            g_data = (
                df[df["Grupo"] == g]
                .sort_values("Fecha_Raw")
            )

            for i in range(1, len(g_data)):

                ayer = g_data.iloc[i - 1]["Turno"]
                hoy = g_data.iloc[i]["Turno"]
                fecha = g_data.iloc[i]["Fecha_Col"]

                if not es_cambio_saludable(ayer, hoy):

                    alertas_salud.append(
                        f"{g}: {ayer} → {hoy} ({fecha})"
                    )

        if alertas_salud:

            for a in alertas_salud:
                st.error(a)

        else:
            st.success("✅ Sin saltos riesgosos")

    with col2:

        st.subheader("📡 Cobertura")

        cobertura = (
            df.groupby(["Fecha_Col", "Turno"])
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
            st.success("✅ Cobertura completa")

    # =====================================================
    # KPIS
    # =====================================================

    st.subheader("📊 KPIs")

    total_desc = len(df[df["Turno"] == "DESC"])
    total_t3 = len(df[df["Turno"] == "T3"])
    total_comp = len(df[df["Turno"] == "COMP"])
    dias = df["Fecha_Raw"].nunique()

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Descansos", total_desc)
    c2.metric("Noches T3", total_t3)
    c3.metric("Compensatorios", total_comp)
    c4.metric("Días", dias)

    # =====================================================
    # COBERTURA DIARIA
    # =====================================================

    st.subheader("📅 Cobertura Operativa")

    cobertura_full = (
        df.groupby(["Fecha_Col", "Turno"])
        .size()
        .unstack(fill_value=0)
    )

    for c in TURNOS:
        if c not in cobertura_full.columns:
            cobertura_full[c] = 0

    cobertura_full = cobertura_full[TURNOS]

    st.dataframe(
        cobertura_full,
        use_container_width=True
    )

    # =====================================================
    # DESCANSOS
    # =====================================================

    st.subheader("🛌 Descansos por Semana")

    df_desc = df.copy()

    df_desc["Semana"] = (
        df_desc["Fecha_Raw"]
        .dt.isocalendar()
        .week
    )

    descansos = (
        df_desc[df_desc["Turno"] == "DESC"]
        .groupby(["Grupo", "Semana"])
        .size()
        .reset_index(name="Descansos")
    )

    if not descansos.empty:

        resumen_desc = (
            descansos
            .pivot(
                index="Grupo",
                columns="Semana",
                values="Descansos"
            )
            .fillna(0)
            .astype(int)
        )

        st.dataframe(
            resumen_desc,
            use_container_width=True
        )

        st.bar_chart(resumen_desc)

    # =====================================================
    # DESCANSOS SIMULTÁNEOS
    # =====================================================

    st.subheader("🚦 Descansos Simultáneos")

    descansos_dia = (
        df[df["Turno"] == "DESC"]
        .groupby("Fecha_Col")
        .size()
    )

    alertas_multi = []

    for fecha, cantidad in descansos_dia.items():

        if cantidad > 2:

            alertas_multi.append(
                f"{cantidad} grupos descansan el {fecha}"
            )

    if alertas_multi:

        for a in alertas_multi:
            st.error(a)

    else:
        st.success("✅ Descansos controlados")

    # =====================================================
    # BALANCE
    # =====================================================

    st.subheader("⚖️ Balance de Turnos")

    balance = (
        df.groupby(["Grupo", "Turno"])
        .size()
        .unstack(fill_value=0)
    )

    st.dataframe(
        balance,
        use_container_width=True
    )

    st.bar_chart(balance)

    # =====================================================
    # FATIGA
    # =====================================================

    st.subheader("🔥 Índice de Fatiga")

    fatiga_map = {
        "T1": 1,
        "T2": 2,
        "T3": 4,
        "DESC": 0,
        "COMP": 0
    }

    df["Fatiga"] = df["Turno"].map(fatiga_map)

    fatiga = (
        df.groupby("Grupo")["Fatiga"]
        .sum()
        .sort_values(ascending=False)
    )

    st.bar_chart(fatiga)

# =========================================================
# PANTALLA PRINCIPAL
# =========================================================

def pantalla_programador():

    st.title("📅 Programador Maestro MovilGo")

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

        with col1:

            d_g1 = st.selectbox(
                "Descanso Grupo 1",
                dias_semana,
                index=5
            )

            d_g2 = st.selectbox(
                "Descanso Grupo 2",
                dias_semana,
                index=5
            )

            d_g3 = st.selectbox(
                "Descanso Grupo 3",
                dias_semana,
                index=6
            )

            d_g4 = st.selectbox(
                "Descanso Grupo 4",
                dias_semana,
                index=6
            )

            map_idx = {
                "Grupo 1": dias_semana.index(d_g1),
                "Grupo 2": dias_semana.index(d_g2),
                "Grupo 3": dias_semana.index(d_g3),
                "Grupo 4": dias_semana.index(d_g4)
            }

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

        estado_ayer = obtener_ultimo_estado_github(repo)

        lista_fechas = [
            f_ini + timedelta(days=x)
            for x in range((f_fin - f_ini).days + 1)
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

            for g in activos:

                idx_g = GRUPOS.index(g)

                t_sug = (
                    ["T1", "T2", "T3"]
                    [(idx_g + semana) % 3]
                )

                if not es_cambio_saludable(
                    mem_t[g],
                    t_sug
                ):
                    t_sug = mem_t[g]

                if mem_n[g] >= 6 and t_sug == "T3":
                    t_sug = "T1"

                turnos_hoy[g] = t_sug

            # =============================================
            # COBERTURA FORZADA
            # =============================================

            for tr in ["T1", "T2", "T3"]:

                if (
                    tr not in turnos_hoy.values()
                    and activos
                ):

                    for gf in activos:

                        if (
                            list(turnos_hoy.values())
                            .count(turnos_hoy[gf]) > 1
                        ):

                            if es_cambio_saludable(
                                mem_t[gf],
                                tr
                            ):

                                turnos_hoy[gf] = tr
                                break

            # =============================================
            # GUARDAR
            # =============================================

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

                resultados.append({

                    "Grupo": g,
                    "Fecha_Col": col_name,
                    "Turno": t_final,
                    "Fecha_Raw": fecha_dt,
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

    if st.session_state.get("malla_generada") is not None:

        df_v = st.session_state.malla_generada.copy()

        df_v["Fecha_Raw"] = pd.to_datetime(
            df_v["Fecha_Raw"]
        )

        # =================================================
        # REPORTE DETALLADO
        # =================================================

        st.subheader("📋 Reporte Detallado")

        with st.expander(
            "📖 Reglas Aplicadas",
            expanded=True
        ):

            st.markdown("""
### ✅ Reglas Operativas

1. Cada grupo tiene un día fijo de descanso semanal.
2. Se respeta la rotación progresiva T1 → T2 → T3.
3. No se permiten saltos riesgosos:
   - T3 → T1
   - T3 → T2
   - T2 → T1
4. Ningún grupo puede superar 6 noches consecutivas T3.
5. Todos los días deben tener cobertura T1, T2 y T3.
6. Se controlan descansos simultáneos.
7. Se busca equilibrio entre grupos.
8. Se monitorea índice de fatiga.
9. Los festivos se detectan automáticamente.
10. Toda edición queda guardada en histórico.
""")

        matriz = df_v.pivot(
            index="Grupo",
            columns="Fecha_Col",
            values="Turno"
        )

        matriz = matriz.reindex(
            columns=df_v["Fecha_Col"].unique()
        )

        st.markdown("""
🟦 T1 | 🟩 T2 | ⬛ T3 | 🟥 DESC | 🟧 COMP
""")

        st.dataframe(
            matriz.style.map(color_turno),
            use_container_width=True,
            height=350
        )

        # =================================================
        # EDITOR
        # =================================================

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

        # =================================================
        # GUARDAR
        # =================================================

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

            guardar_malla_en_historico(df_final)

            st.session_state.malla_generada = df_final

            st.success("✅ Cambios guardados")

            st.rerun()

        # =================================================
        # AUDITORÍA
        # =================================================

        auditar_malla(df_v)
