# logic_programador.py
# OPTIMIZADOR INTELIGENTE PRO - VERSION ESTABLE FINAL

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import holidays

# =========================================================
# CONFIG
# =========================================================
TURNOS = ["T1","T2","T3","T1 APOYO","T2 APOYO","DESCANSO","COMPENSADO"]

GRUPOS = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]

DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]

festivos_co = holidays.Colombia()

# =========================================================
# VALIDACIÓN DE CONFIGURACIÓN
# =========================================================
def validar_config(descanso_actual):

    errores = []

    conteo = {d:0 for d in DIAS_ES}

    for g in GRUPOS:
        conteo[descanso_actual[g]] += 1

    for dia, cant in conteo.items():
        if cant > 2:
            errores.append(f"{dia}: {cant} descansos (máximo permitido 2)")

    return errores

# =========================================================
# OPTIMIZADOR DE DESCANSO (AJUSTE SUAVE)
# =========================================================
def optimizar_descanso(descanso_actual, dia):

    grupos = [g for g in GRUPOS if descanso_actual[g] == dia]

    # si hay demasiados descansando ese día
    if len(grupos) > 2:

        excedentes = grupos[2:]

        for g in excedentes:
            for d in DIAS_ES:
                if d != dia:
                    descanso_actual[g] = d
                    break

        grupos = grupos[:2]

    return grupos

# =========================================================
# PARAMETRIZADOR (CORREGIDO)
# =========================================================
def parametrizador():

    st.header("🧩 Parametrizador de Grupos")

    df = pd.DataFrame({
        "Nombre": ["Empleado A","Empleado B","Empleado C","Empleado D"],
        "Grupo": ["","","",""]
    })

    st.dataframe(df)

    if st.button("🎲 Asignar grupos"):

        df["Grupo"] = GRUPOS * 10

        st.success("Grupos asignados correctamente")

# =========================================================
# PROGRAMADOR PRINCIPAL
# =========================================================
def generar_malla():

    st.header("🚀 OPTIMIZADOR INTELIGENTE PRO")

    c1, c2 = st.columns(2)
    inicio = c1.date_input("Fecha inicio", datetime.now())
    fin = c2.date_input("Fecha fin", datetime.now() + timedelta(days=30))

    # =========================================================
    # DESCANSO DE LEY (FUENTE ÚNICA - UI)
    # =========================================================
    st.subheader("Parametrización de descanso de ley")

    descanso_actual = {}

    cols = st.columns(len(GRUPOS))

    for i, g in enumerate(GRUPOS):
        descanso_actual[g] = cols[i].selectbox(
            g,
            DIAS_ES,
            key=f"desc_{g}"
        )

    # =========================================================
    # VALIDACIÓN ANTES DE GENERAR
    # =========================================================
    if st.button("🚀 Generar malla optimizada"):

        errores = validar_config(descanso_actual)

        if errores:
            st.error("⚠️ Configuración inválida detectada")
            for e in errores:
                st.warning(e)
            st.stop()

        # =====================================================
        # ESTADO OPERATIVO
        # =====================================================
        carga = {g:0 for g in GRUPOS}
        conteo = {g:{"T1":0,"T2":0,"T3":0} for g in GRUPOS}

        filas = []

        fechas = pd.date_range(inicio, fin)

        # =====================================================
        # GENERACIÓN
        # =====================================================
        for fecha in fechas:

            dia = DIAS_ES[fecha.weekday()]
            festivo = fecha.date() in festivos_co

            asignados = {}

            # =================================================
            # DESCANSO REAL (RESPETA UI + OPTIMIZA SOLO SI ES NECESARIO)
            # =================================================
            grupos_descanso = optimizar_descanso(descanso_actual, dia)

            activos = [g for g in GRUPOS if g not in grupos_descanso]

            for g in grupos_descanso:
                asignados[g] = "DESCANSO"

            # =================================================
            # COBERTURA OBLIGATORIA T1 T2 T3
            # =================================================
            for turno in ["T1","T2","T3"]:

                candidatos = [(carga[g], conteo[g][turno], g) for g in activos]

                if not candidatos:
                    continue

                candidatos.sort()

                sel = candidatos[0][2]

                asignados[sel] = turno

                carga[sel] += 1
                conteo[sel][turno] += 1

                activos.remove(sel)

            # =================================================
            # APOYO / COMPLETAR
            # =================================================
            for g in activos:
                asignados[g] = "T1 APOYO"

            # =================================================
            # GUARDADO
            # =================================================
            for g in GRUPOS:
                filas.append({
                    "Fecha": fecha,
                    "Grupo": g,
                    "Día": dia,
                    "Turno": asignados.get(g, "T1 APOYO"),
                    "Festivo": "SI" if festivo else "NO"
                })

        df = pd.DataFrame(filas)

        st.session_state["malla"] = df

        st.success("Malla generada correctamente")

    # =========================================================
    # VISUALIZACIÓN MALLA
    # =========================================================
    if "malla" in st.session_state:

        st.subheader("📊 Malla horizontal")

        df = st.session_state["malla"]

        pivot = df.pivot(index="Grupo", columns="Fecha", values="Turno")

        def color(v):
            return {
                "DESCANSO":"background:#FFADAD",
                "COMPENSADO":"background:#FFD6A5",
                "T1":"background:#CAFFBF",
                "T2":"background:#9BF6FF",
                "T3":"background:#BDB2FF"
            }.get(v,"")

        st.dataframe(pivot.style.map(color), use_container_width=True)

        # =====================================================
        # DASHBOARD
        # =====================================================
        st.subheader("📊 Dashboard")

        c1,c2,c3 = st.columns(3)

        c1.metric("Turnos operativos", len(df[df["Turno"].isin(["T1","T2","T3"])]))
        c2.metric("Descansos", len(df[df["Turno"]=="DESCANSO"]))
        c3.metric("Compensados", len(df[df["Turno"]=="COMPENSADO"]))

# =========================================================
# MENU PRINCIPAL
# =========================================================
def pantalla_programador():

    mod = st.radio(
        "Módulo",
        ["Programador","Parametrizador"],
        horizontal=True
    )

    if mod == "Programador":
        generar_malla()
    else:
        parametrizador()
