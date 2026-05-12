# logic_programador.py
# =========================================================
# OPTIMIZADOR INTELIGENTE PRO ENTERPRISE - VERSION ESTABLE
# =========================================================

import streamlit as st
import pandas as pd
from datetime import date, timedelta
import holidays

# =========================================================
# CONFIG
# =========================================================
TURNOS = ["T1","T2","T3","T1 APOYO","T2 APOYO","DESCANSO","COMPENSADO"]

GRUPOS = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]

DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]

festivos_co = holidays.Colombia()

# =========================================================
# COLORES SUAVES (FONDO)
# =========================================================
def color_cell(v):

    return {
        "T1": "background-color:#D6EAF8;",
        "T2": "background-color:#D5F5E3;",
        "T3": "background-color:#FADBD8;",

        "T1 APOYO": "background-color:#EBF5FB;",
        "T2 APOYO": "background-color:#EAF2F8;",

        "DESCANSO": "background-color:#2C3E50;color:#F9E79F;font-weight:700;",
        "COMPENSADO": "background-color:#FDEBD0;font-weight:600;"
    }.get(v, "")

# =========================================================
# GENERADOR
# =========================================================
def generar_malla():

    st.header("🚀 OPTIMIZADOR PRO ENTERPRISE")

    c1, c2 = st.columns(2)

    inicio = c1.date_input("Fecha inicio", date.today())
    fin = c2.date_input("Fecha fin", date.today() + timedelta(days=30))

    # =====================================================
    # DESCANSO DE LEY
    # =====================================================
    st.subheader("⚖️ Descanso de ley")

    descanso_actual = {}
    cols = st.columns(len(GRUPOS))

    for i, g in enumerate(GRUPOS):
        descanso_actual[g] = cols[i].selectbox(
            g,
            DIAS_ES,
            index=i,
            key=f"desc_{g}"
        )

    # =====================================================
    # ESTADO
    # =====================================================
    carga = {g: 0 for g in GRUPOS}
    conteo = {g: {"T1":0,"T2":0,"T3":0} for g in GRUPOS}
    compensado = {g: 0 for g in GRUPOS}
    sacrificio = {g: 0 for g in GRUPOS}

    # =====================================================
    # GENERAR
    # =====================================================
    if st.button("🚀 Generar malla"):

        filas = []
        fechas = pd.date_range(inicio, fin)

        for f in fechas:

            dia = DIAS_ES[f.weekday()]
            festivo = f.date() in festivos_co

            asignados = {}

            descanso = [g for g in GRUPOS if descanso_actual[g] == dia]
            activos = [g for g in GRUPOS if g not in descanso]

            # =========================================
            # COBERTURA MÍNIMA 3 TURNOS
            # =========================================
            while len(activos) < 3:

                mov = sorted(descanso, key=lambda g:(sacrificio[g], carga[g]))[0]
                descanso.remove(mov)
                activos.append(mov)

                sacrificio[mov] += 1
                compensado[mov] += 1

            # =========================================
            # DESCANSOS
            # =========================================
            for g in descanso:
                asignados[g] = "DESCANSO"

            # =========================================
            # TURNOS OBLIGATORIOS
            # =========================================
            for t in ["T1","T2","T3"]:

                sel = sorted(activos, key=lambda g:(carga[g], conteo[g][t]))[0]

                asignados[sel] = t
                carga[sel] += 1
                conteo[sel][t] += 1
                activos.remove(sel)

            # =========================================
            # COMPENSADOS
            # =========================================
            for g in GRUPOS:
                if compensado[g] > 0 and g not in asignados:
                    asignados[g] = "COMPENSADO"
                    compensado[g] -= 1

            # =========================================
            # APOYO (SIN SALTOS PROHIBIDOS)
            # =========================================
            for g in GRUPOS:

                if g not in asignados:

                    # BLOQUEO SALTOS:
                    if conteo[g]["T3"] > 0:
                        asignados[g] = "T2 APOYO"
                    elif conteo[g]["T2"] > conteo[g]["T1"]:
                        asignados[g] = "T2 APOYO"
                    else:
                        asignados[g] = "T1 APOYO"

            # =========================================
            # GUARDAR
            # =========================================
            for g in GRUPOS:

                filas.append({
                    "Grupo": g,
                    "Fecha": f,
                    "Día": dia,
                    "Turno": asignados[g],
                    "Festivo": "SI" if festivo else "NO"
                })

        st.session_state["df"] = pd.DataFrame(filas)

    # =====================================================
    # MALLA ÚNICA EDITABLE
    # =====================================================
    if "df" in st.session_state:

        df = st.session_state["df"]

        pivot = df.pivot(index="Grupo", columns="Fecha", values="Turno")

        pivot.columns = [
            f"{c.strftime('%d-%m')}\n{DIAS_ES[c.weekday()]}"
            for c in pivot.columns
        ]

        st.subheader("📊 MALLA ÚNICA EDITABLE")

        edited = st.data_editor(
            pivot,
            use_container_width=True,
            key="malla_editor"
        )

        # =========================================
        # GUARDAR CAMBIOS
        # =========================================
        if st.button("💾 Guardar cambios"):

            tmp = edited.copy().reset_index()

            long = tmp.melt(
                id_vars=["Grupo"],
                var_name="Fecha",
                value_name="Turno"
            )

            st.session_state["df"] = long

            st.success("Malla actualizada")

        # =========================================
        # VISTA COLOREADA
        # =========================================
        st.dataframe(
            edited.style.map(color_cell),
            use_container_width=True
        )

        # =========================================
        # AUDITORÍA SALTOS
        # =========================================
        st.subheader("🚨 Auditoría de saltos")

        errores = []

        for g in GRUPOS:

            prev = None
            gdf = df[df["Grupo"] == g]

            for _, r in gdf.iterrows():

                if prev == "T3" and r["Turno"] in ["T1","T2"]:
                    errores.append(f"{g}: T3 → {r['Turno']} ({r['Fecha']})")

                if prev == "T2" and r["Turno"] == "T1":
                    errores.append(f"{g}: T2 → T1 ({r['Fecha']})")

                prev = r["Turno"]

        if errores:
            st.error("Saltos indebidos detectados")
            st.write(errores)
        else:
            st.success("Sin saltos indebidos")

        # =========================================
        # COBERTURA
        # =========================================
        st.subheader("📈 Cobertura T1/T2/T3")

        cov = df[df["Turno"].isin(["T1","T2","T3"])].groupby("Fecha").size()

        st.line_chart(cov)

# =========================================================
# MENU
# =========================================================
def pantalla_programador():

    op = st.radio("Módulo", ["Programador","Parametrizador"], horizontal=True)

    if op == "Programador":
        generar_malla()
    else:
        st.write("Parametrizador activo")
