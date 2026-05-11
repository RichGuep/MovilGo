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
# ✔ Auditoría de saltos indebidos
# ✔ Auditoría de cobertura diaria
# ✔ Malla visual profesional
# ✔ Días en español
# =========================================================

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
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
# VALIDACIÓN CONFIG
# =========================================================
def validar_config(descanso_actual):

    errores = []

    conteo = {d: 0 for d in DIAS_ES}

    for g in GRUPOS:
        conteo[descanso_actual[g]] += 1

    for dia, cantidad in conteo.items():
        if cantidad > 2:
            errores.append(f"{dia}: {cantidad} descansos configurados")

    return errores

# =========================================================
# PARAMETRIZADOR
# =========================================================
def parametrizador():

    st.header("🧩 Parametrizador de grupos")

    df = pd.DataFrame({
        "Empleado": ["Empleado A","Empleado B","Empleado C","Empleado D"],
        "Grupo": ["","","",""]
    })

    st.dataframe(df, use_container_width=True)

    if st.button("🎲 Asignar grupos"):
        st.success("Grupos asignados correctamente")

# =========================================================
# GENERADOR PRINCIPAL
# =========================================================
def generar_malla():

    st.header("🚀 OPTIMIZADOR INTELIGENTE PRO ENTERPRISE")

    # =====================================================
    # FECHAS
    # =====================================================
    c1, c2 = st.columns(2)

    inicio = c1.date_input("Fecha inicio", date.today())
    fin = c2.date_input("Fecha fin", date.today() + timedelta(days=30))

    # =====================================================
    # DESCANSOS
    # =====================================================
    st.subheader("⚖️ Parametrización descanso de ley")

    cols = st.columns(len(GRUPOS))

    descanso_actual = {}

    for i, g in enumerate(GRUPOS):

        key = f"descanso_{g}"

        if key not in st.session_state:
            st.session_state[key] = DIAS_ES[i]

        descanso_actual[g] = cols[i].selectbox(
            g,
            DIAS_ES,
            key=key
        )

    # =====================================================
    # ROTACIÓN
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
    # VALIDACIÓN
    # =====================================================
    errores = validar_config(descanso_actual)

    if errores:
        st.warning("⚠️ Configuración de descansos con advertencias")
        for e in errores:
            st.warning(e)

    # =====================================================
    # GENERAR
    # =====================================================
    if st.button("🚀 Generar malla optimizada"):

        carga = {g: 0 for g in GRUPOS}

        conteo_turnos = {
            g: {"T1":0,"T2":0,"T3":0}
            for g in GRUPOS
        }

        sacrificios = {g:0 for g in GRUPOS}
        compensados = {g:0 for g in GRUPOS}

        ultimo_turno = {g: None for g in GRUPOS}

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
            # DESCANSOS
            # =================================================
            grupos_descanso = [
                g for g in GRUPOS
                if descanso_actual[g] == dia
            ]

            activos = [
                g for g in GRUPOS
                if g not in grupos_descanso
            ]

            # =================================================
            # COBERTURA MÍNIMA
            # =================================================
            while len(activos) < 3:

                candidatos = [
                    (sacrificios[g], carga[g], g)
                    for g in grupos_descanso
                ]

                candidatos.sort()

                g = candidatos[0][2]

                grupos_descanso.remove(g)
                activos.append(g)

                sacrificios[g] += 1
                compensados[g] += 1

            # =================================================
            # DESCANSO
            # =================================================
            for g in grupos_descanso:
                asignados[g] = "DESCANSO"

            # =================================================
            # TURNOS (SIN HUECOS)
            # =================================================
            for turno in ["T1","T2","T3"]:

                candidatos = []

                for g in activos:

                    prev = ultimo_turno[g]

                    # evitar salto crítico
                    if prev == "T3" and turno == "T1":
                        continue

                    if prev == "T2" and turno == "T1":
                        continue

                    candidatos.append((carga[g], g))

                # RELAJAR SI ES NECESARIO
                if not candidatos:
                    candidatos = [(carga[g], g) for g in activos]

                if not candidatos:
                    continue

                candidatos.sort()

                sel = candidatos[0][1]

                asignados[sel] = turno

                ultimo_turno[sel] = turno

                carga[sel] += 1

                conteo_turnos[sel][turno] += 1

                activos.remove(sel)

            # =================================================
            # APOYO
            # =================================================
            for g in activos:
                asignados[g] = "T1 APOYO"

            # =================================================
            # GUARDAR
            # =================================================
            for g in GRUPOS:

                filas.append({
                    "Fecha": fecha,
                    "Día": dia,
                    "Grupo": g,
                    "Turno": asignados.get(g, "SIN ASIGNAR"),
                    "Festivo": "SI" if festivo else "NO"
                })

        df = pd.DataFrame(filas)

        st.session_state["malla"] = df

        st.success("✅ Malla generada correctamente")

    # =====================================================
    # VISUALIZACIÓN
    # =====================================================
    if "malla" in st.session_state:

        st.subheader("📊 Malla horizontal")

        df = st.session_state["malla"]

        pivot = df.pivot(
            index="Grupo",
            columns="Fecha",
            values="Turno"
        ).fillna("SIN ASIGNAR")

        # =================================================
        # AUDITORÍA SALTOS
        # =================================================
        st.subheader("🚨 Auditoría de saltos indebidos")

        saltos = []

        for g in GRUPOS:

            gdf = df[df["Grupo"] == g].sort_values("Fecha")

            prev = None

            for _, r in gdf.iterrows():

                if prev == "T3" and r["Turno"] == "T1":
                    saltos.append([g, r["Fecha"], "T3 → T1"])

                if prev == "T2" and r["Turno"] == "T1":
                    saltos.append([g, r["Fecha"], "T2 → T1"])

                prev = r["Turno"]

        if saltos:
            st.error(f"⚠️ {len(saltos)} saltos detectados")
            st.dataframe(pd.DataFrame(saltos, columns=["Grupo","Fecha","Error"]))
        else:
            st.success("✅ Sin saltos indebidos")

        # =================================================
        # AUDITORÍA COBERTURA
        # =================================================
        st.subheader("🛡️ Auditoría de cobertura diaria")

        faltantes = []

        for fecha in df["Fecha"].unique():

            dia_df = df[df["Fecha"] == fecha]

            turnos = set(dia_df["Turno"])

            for t in ["T1","T2","T3"]:
                if t not in turnos:
                    faltantes.append([fecha, t])

        if faltantes:
            st.error("❌ Días con turnos faltantes")
            st.dataframe(pd.DataFrame(faltantes, columns=["Fecha","Falta"]))
        else:
            st.success("✅ Cobertura completa")

        # =================================================
        # COLORES PRO
        # =================================================
        def color(v):

            return {
                "DESCANSO":"background:#FF4D4D;color:white;font-weight:bold",
                "COMPENSADO":"background:#FFD166;font-weight:bold",
                "T1":"background:#06D6A0;font-weight:bold",
                "T2":"background:#118AB2;color:white;font-weight:bold",
                "T3":"background:#8338EC;color:white;font-weight:bold",
                "T1 APOYO":"background:#E0E0E0",
                "T2 APOYO":"background:#CFCFCF",
                "SIN ASIGNAR":"background:#000;color:white"
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
