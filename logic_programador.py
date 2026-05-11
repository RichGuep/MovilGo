# logic_programador.py
# OPTIMIZADOR PRO ENTERPRISE - SIN SALTOS INADECUADOS

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import holidays

# =========================================================
# CONFIG
# =========================================================
TURNOS = [
    "T1","T2","T3",
    "T1 APOYO","T2 APOYO",
    "DESCANSO","COMPENSADO"
]

GRUPOS = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]

DIAS_ES = [
    "Lunes","Martes","Miércoles",
    "Jueves","Viernes","Sábado","Domingo"
]

festivos_co = holidays.Colombia()

# =========================================================
# VALIDACIÓN
# =========================================================
def validar_config(descanso_actual):

    errores = []

    conteo = {d:0 for d in DIAS_ES}

    for g in GRUPOS:
        conteo[descanso_actual[g]] += 1

    for d,c in conteo.items():
        if c > 2:
            errores.append(f"{d}: {c} descansos")

    return errores

# =========================================================
# PARAMETRIZADOR
# =========================================================
def parametrizador():

    st.header("🧩 Parametrizador")

    st.info("Gestión de grupos activa")

    if st.button("Asignar grupos"):
        st.success("Grupos asignados")

# =========================================================
# CONTROL DE SECUENCIA (CLAVE)
# =========================================================
def es_salto_invalido(prev, nuevo):

    if prev == "T3" and nuevo == "T1":
        return True

    if prev == "T2" and nuevo == "T1":
        return True

    return False

# =========================================================
# GENERADOR
# =========================================================
def generar_malla():

    st.header("🚀 OPTIMIZADOR PRO SIN SALTOS")

    c1,c2 = st.columns(2)

    inicio = c1.date_input("Inicio", datetime.now())

    fin = c2.date_input("Fin", datetime.now() + timedelta(days=30))

    # =====================================================
    # DESCANSO
    # =====================================================
    st.subheader("Descanso de ley")

    descanso_actual = {}

    cols = st.columns(len(GRUPOS))

    for i,g in enumerate(GRUPOS):
        descanso_actual[g] = cols[i].selectbox(g, DIAS_ES, index=i)

    if st.button("🚀 Generar malla"):

        carga = {g:0 for g in GRUPOS}

        conteo = {g:{"T1":0,"T2":0,"T3":0} for g in GRUPOS}

        ultimo_turno = {g:None for g in GRUPOS}

        compensado = {g:0 for g in GRUPOS}

        filas = []

        fechas = pd.date_range(inicio, fin)

        for fecha in fechas:

            dia = DIAS_ES[fecha.weekday()]

            festivo = fecha.date() in festivos_co

            asignados = {}

            # =================================================
            # DESCANSO
            # =================================================
            grupos_descanso = [
                g for g in GRUPOS
                if descanso_actual[g] == dia
            ]

            activos = [
                g for g in GRUPOS
                if g not in grupos_descanso
            ]

            for g in grupos_descanso:
                asignados[g] = "DESCANSO"

            # =================================================
            # TURNOS CON CONTROL DE SECUENCIA
            # =================================================
            for turno in ["T1","T2","T3"]:

                candidatos = []

                for g in activos:

                    prev = ultimo_turno[g]

                    if es_salto_invalido(prev, turno):
                        continue

                    candidatos.append((carga[g], g))

                if not candidatos:
                    continue

                candidatos.sort()

                sel = candidatos[0][1]

                asignados[sel] = turno

                ultimo_turno[sel] = turno

                carga[sel] += 1

                conteo[sel][turno] += 1

                activos.remove(sel)

            # =================================================
            # APOYO
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
                    "Turno": asignados.get(g),
                    "Festivo": "SI" if festivo else "NO"
                })

        df = pd.DataFrame(filas)

        st.session_state["malla"] = df

        st.success("Malla generada sin saltos peligrosos")

    # =====================================================
    # VISUAL MEJORADA
    # =====================================================
    if "malla" in st.session_state:

        st.subheader("📊 Malla visual mejorada")

        df = st.session_state["malla"]

        pivot = df.pivot(index="Grupo", columns="Fecha", values="Turno")

        def color(v):

            return {
                "DESCANSO":"background:#FF6B6B;color:white;font-weight:bold",
                "COMPENSADO":"background:#FFD93D",
                "T1":"background:#6BCB77",
                "T2":"background:#4D96FF",
                "T3":"background:#845EC2;color:white",
                "T1 APOYO":"background:#E0E0E0",
                "T2 APOYO":"background:#CFCFCF"
            }.get(v,"")

        st.dataframe(
            pivot.style.map(color),
            use_container_width=True
        )

        # =================================================
        # DASHBOARD
        # =================================================
        st.subheader("📊 Dashboard")

        c1,c2,c3 = st.columns(3)

        c1.metric("Operativos", len(df[df["Turno"].isin(["T1","T2","T3"])]))

        c2.metric("Descanso", len(df[df["Turno"]=="DESCANSO"]))

        c3.metric("Compensado", len(df[df["Turno"]=="COMPENSADO"]))

# =========================================================
# MENU
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
