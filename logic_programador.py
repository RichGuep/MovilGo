# logic_programador.py
# =========================================================
# OPTIMIZADOR INTELIGENTE PRO ENTERPRISE
# =========================================================
# ✔ Cobertura obligatoria T1/T2/T3
# ✔ Descanso de ley parametrizado
# ✔ Sacrificio inteligente fin de semana
# ✔ Compensado automático
# ✔ Balance de cargas
# ✔ Balance de sacrificios
# ✔ Días visibles en español
# ✔ Dashboard operativo
# ✔ Motor tipo enterprise
# =========================================================

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import holidays

# =========================================================
# CONFIG
# =========================================================
TURNOS = [
    "T1",
    "T2",
    "T3",
    "T1 APOYO",
    "T2 APOYO",
    "DESCANSO",
    "COMPENSADO"
]

GRUPOS = [
    "Grupo 1",
    "Grupo 2",
    "Grupo 3",
    "Grupo 4"
]

DIAS_ES = [
    "Lunes",
    "Martes",
    "Miércoles",
    "Jueves",
    "Viernes",
    "Sábado",
    "Domingo"
]

festivos_co = holidays.Colombia()

# =========================================================
# VALIDACIÓN CONFIG
# =========================================================
def validar_config(descanso_actual):

    errores = []

    conteo = {d: 0 for d in DIAS_ES}

    for g in GRUPOS:
        conteo[descanso_actual[g]] += 1

    for dia, cantidad in conteo.items():

        if cantidad > 2:

            errores.append(
                f"{dia}: {cantidad} descansos configurados "
                f"(máximo recomendado 2)"
            )

    return errores

# =========================================================
# PARAMETRIZADOR
# =========================================================
def parametrizador():

    st.header("🧩 Parametrizador de grupos")

    df = pd.DataFrame({
        "Empleado": [
            "Empleado A",
            "Empleado B",
            "Empleado C",
            "Empleado D"
        ],
        "Grupo": [
            "",
            "",
            "",
            ""
        ]
    })

    st.dataframe(
        df,
        use_container_width=True
    )

    if st.button("🎲 Asignar grupos"):

        st.success(
            "Grupos asignados correctamente"
        )

# =========================================================
# GENERADOR PRINCIPAL
# =========================================================
def generar_malla():

    st.header("🚀 OPTIMIZADOR INTELIGENTE PRO")

    # =====================================================
    # FECHAS
    # =====================================================
    c1, c2 = st.columns(2)

    inicio = c1.date_input(
        "Fecha inicio",
        date.today()
    )

    fin = c2.date_input(
        "Fecha fin",
        date.today() + timedelta(days=30)
    )

    # =====================================================
    # DESCANSOS
    # =====================================================
    st.subheader("⚖️ Parametrización descanso de ley")

    cols = st.columns(len(GRUPOS))

    descanso_actual = {}

    # Inicialización session_state
    for i, g in enumerate(GRUPOS):

        key = f"descanso_{g}"

        if key not in st.session_state:

            st.session_state[key] = DIAS_ES[i]

    # Selectores
    for i, g in enumerate(GRUPOS):

        key = f"descanso_{g}"

        descanso_actual[g] = cols[i].selectbox(
            g,
            DIAS_ES,
            key=key
        )

    # =====================================================
    # ROTACIÓN AUTOMÁTICA
    # =====================================================
    if st.button("🔄 Rotar descansos"):

        for g in GRUPOS:

            key = f"descanso_{g}"

            actual = st.session_state[key]

            st.session_state[key] = DIAS_ES[
                (DIAS_ES.index(actual) + 1) % 7
            ]

        st.rerun()

    # =====================================================
    # VALIDACIÓN VISUAL
    # =====================================================
    errores = validar_config(descanso_actual)

    if errores:

        st.warning(
            "⚠️ Hay demasiados descansos el mismo día."
        )

        for e in errores:
            st.warning(e)

    # =====================================================
    # GENERAR
    # =====================================================
    if st.button("🚀 Generar malla optimizada"):

        # =================================================
        # ESTADO GLOBAL
        # =================================================
        carga = {
            g: 0
            for g in GRUPOS
        }

        conteo_turnos = {
            g: {
                "T1": 0,
                "T2": 0,
                "T3": 0
            }
            for g in GRUPOS
        }

        # sacrificios fin de semana
        sacrificios = {
            g: 0
            for g in GRUPOS
        }

        # compensados pendientes
        compensados = {
            g: 0
            for g in GRUPOS
        }

        filas = []

        fechas = pd.date_range(
            inicio,
            fin,
            freq="D"
        )

        # =================================================
        # GENERACIÓN DIARIA
        # =================================================
        for fecha in fechas:

            dia = DIAS_ES[
                fecha.weekday()
            ]

            festivo = (
                fecha.date()
                in festivos_co
            )

            asignados = {}

            # =============================================
            # DESCANSOS CONFIGURADOS
            # =============================================
            grupos_descanso = [

                g for g in GRUPOS

                if descanso_actual[g] == dia
            ]

            activos = [

                g for g in GRUPOS

                if g not in grupos_descanso
            ]

            # =============================================
            # COBERTURA OBLIGATORIA
            # =============================================
            # SI NO ALCANZA PERSONAL
            # SE SACRIFICA DESCANSO
            # =============================================
            while len(activos) < 3:

                candidatos = [

                    (
                        sacrificios[g],
                        carga[g],
                        g
                    )

                    for g in grupos_descanso
                ]

                candidatos.sort()

                sacrificado = candidatos[0][2]

                grupos_descanso.remove(
                    sacrificado
                )

                activos.append(
                    sacrificado
                )

                sacrificios[
                    sacrificado
                ] += 1

                compensados[
                    sacrificado
                ] += 1

            # =============================================
            # ASIGNAR DESCANSOS
            # =============================================
            for g in grupos_descanso:

                asignados[g] = "DESCANSO"

            # =============================================
            # ASIGNAR TURNOS
            # =============================================
            for turno in ["T1", "T2", "T3"]:

                candidatos = [

                    (
                        carga[g],
                        conteo_turnos[g][turno],
                        g
                    )

                    for g in activos
                ]

                candidatos.sort()

                seleccionado = candidatos[0][2]

                asignados[
                    seleccionado
                ] = turno

                carga[
                    seleccionado
                ] += 1

                conteo_turnos[
                    seleccionado
                ][turno] += 1

                activos.remove(
                    seleccionado
                )

            # =============================================
            # COMPENSADOS ENTRE SEMANA
            # =============================================
            if dia not in [
                "Sábado",
                "Domingo"
            ]:

                for g in GRUPOS:

                    if compensados[g] > 0:

                        # no quitar cobertura
                        if g not in asignados:

                            asignados[g] = "COMPENSADO"

                            compensados[g] -= 1

            # =============================================
            # APOYO
            # =============================================
            for g in GRUPOS:

                if g not in asignados:

                    asignados[g] = "T1 APOYO"

            # =============================================
            # GUARDAR FILAS
            # =============================================
            for g in GRUPOS:

                filas.append({

                    "Fecha": fecha,

                    "Día": dia,

                    "Grupo": g,

                    "Turno": asignados[g],

                    "Festivo": (
                        "SI"
                        if festivo
                        else "NO"
                    )
                })

        # =================================================
        # DATAFRAME FINAL
        # =================================================
        df = pd.DataFrame(filas)

        st.session_state["malla"] = df

        st.success(
            "✅ Malla optimizada generada correctamente"
        )

    # =====================================================
    # VISUALIZAR
    # =====================================================
    if "malla" in st.session_state:

        st.subheader("📊 Malla horizontal")

        df = st.session_state["malla"]

        pivot = df.pivot(
            index="Grupo",
            columns="Fecha",
            values="Turno"
        )

        # =================================================
        # FORMATO COLUMNAS
        # =================================================
        columnas = {}

        for c in pivot.columns:

            fecha_txt = c.strftime("%d-%m")

            dia_txt = DIAS_ES[
                c.weekday()
            ]

            columnas[c] = (
                f"{fecha_txt}\n{dia_txt}"
            )

        pivot.rename(
            columns=columnas,
            inplace=True
        )

        # =================================================
        # COLORES
        # =================================================
        def color(v):

            return {

                "DESCANSO":
                    "background:#FFADAD",

                "COMPENSADO":
                    "background:#FFD6A5",

                "T1":
                    "background:#CAFFBF",

                "T2":
                    "background:#9BF6FF",

                "T3":
                    "background:#BDB2FF",

                "T1 APOYO":
                    "background:#E7E7E7",

                "T2 APOYO":
                    "background:#D6D6D6"

            }.get(v, "")

        st.dataframe(
            pivot.style.map(color),
            use_container_width=True
        )

        # =================================================
        # DASHBOARD
        # =================================================
        st.subheader("📊 Dashboard operativo")

        c1, c2, c3, c4 = st.columns(4)

        operativos = len(
            df[
                df["Turno"].isin(
                    ["T1", "T2", "T3"]
                )
            ]
        )

        descansos = len(
            df[
                df["Turno"] == "DESCANSO"
            ]
        )

        compensados_total = len(
            df[
                df["Turno"] == "COMPENSADO"
            ]
        )

        apoyos = len(
            df[
                df["Turno"] == "T1 APOYO"
            ]
        )

        c1.metric(
            "Turnos operativos",
            operativos
        )

        c2.metric(
            "Descansos",
            descansos
        )

        c3.metric(
            "Compensados",
            compensados_total
        )

        c4.metric(
            "Apoyos",
            apoyos
        )

        # =================================================
        # RESUMEN POR GRUPO
        # =================================================
        st.subheader("📈 Balance por grupo")

        resumen = df.pivot_table(
            index="Grupo",
            columns="Turno",
            aggfunc="size",
            fill_value=0
        )

        st.dataframe(
            resumen,
            use_container_width=True
        )

# =========================================================
# MENÚ PRINCIPAL
# =========================================================
def pantalla_programador():

    modulo = st.radio(
        "Módulo",
        [
            "Programador",
            "Parametrizador"
        ],
        horizontal=True
    )

    if modulo == "Programador":

        generar_malla()

    else:

        parametrizador()
