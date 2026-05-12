# logic_programador.py
# =========================================================
# OPTIMIZADOR INTELIGENTE PRO - BALANCEADO
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
# ESTILOS (COLORES SUAVES)
# =========================================================
def color_cell(v):

    estilos = {
        "T1": "background-color:#D6EAF8;color:#1B4F72;font-weight:600;",
        "T2": "background-color:#D5F5E3;color:#145A32;font-weight:600;",
        "T3": "background-color:#FADBD8;color:#7B241C;font-weight:600;",

        "T1 APOYO": "background-color:#EBF5FB;",
        "T2 APOYO": "background-color:#EAF2F8;",

        "DESCANSO": "background-color:#2C3E50;color:#F9E79F;font-weight:700;",

        "COMPENSADO": "background-color:#FDEBD0;color:#7E5109;font-weight:700;"
    }

    return estilos.get(v, "")

# =========================================================
# PARAMETRIZADOR
# =========================================================
def parametrizador():

    st.header("🧩 Parametrizador")

    df = pd.DataFrame({
        "Empleado": ["A","B","C","D"],
        "Grupo": ["","","",""]
    })

    st.dataframe(df, use_container_width=True)

    if st.button("🎲 Asignar grupos"):
        df["Grupo"] = GRUPOS * 10
        st.success("Grupos asignados")

# =========================================================
# GENERADOR
# =========================================================
def generar_malla():

    st.header("🚀 OPTIMIZADOR INTELIGENTE PRO")

    c1,c2 = st.columns(2)

    inicio = c1.date_input("Inicio", date.today())
    fin = c2.date_input("Fin", date.today()+timedelta(days=30))

    # =====================================================
    # DESCANSO DE LEY
    # =====================================================
    st.subheader("⚖️ Descanso de ley")

    descanso_actual = {}
    cols = st.columns(len(GRUPOS))

    for i,g in enumerate(GRUPOS):
        descanso_actual[g] = cols[i].selectbox(g, DIAS_ES, index=i)

    # =====================================================
    # ESTADO BALANCE
    # =====================================================
    carga = {g:0 for g in GRUPOS}
    conteo = {g:{"T1":0,"T2":0,"T3":0} for g in GRUPOS}

    compensado = {g:0 for g in GRUPOS}
    sacrificio = {g:0 for g in GRUPOS}

    filas = []

    # =====================================================
    # GENERACIÓN
    # =====================================================
    if st.button("🚀 Generar malla"):

        fechas = pd.date_range(inicio, fin)

        for fecha in fechas:

            dia = DIAS_ES[fecha.weekday()]
            festivo = fecha.date() in festivos_co

            asignados = {}

            descanso = [g for g in GRUPOS if descanso_actual[g]==dia]
            activos = [g for g in GRUPOS if g not in descanso]

            # =================================================
            # COBERTURA MÍNIMA BALANCEADA
            # =================================================
            while len(activos) < 3:

                candidatos = sorted(
                    descanso,
                    key=lambda g:(sacrificio[g], carga[g])
                )

                movido = candidatos[0]
                descanso.remove(movido)
                activos.append(movido)

                sacrificio[movido] += 1
                compensado[movido] += 1

            # =================================================
            # DESCANSO
            # =================================================
            for g in descanso:
                asignados[g] = "DESCANSO"

            # =================================================
            # TURNOS PRINCIPALES (SIN HUECOS)
            # =================================================
            for turno in ["T1","T2","T3"]:

                candidatos = sorted(
                    activos,
                    key=lambda g:(carga[g], conteo[g][turno])
                )

                sel = candidatos[0]

                asignados[sel] = turno
                carga[sel]+=1
                conteo[sel][turno]+=1
                activos.remove(sel)

            # =================================================
            # COMPENSADOS (BALANCEADOS)
            # =================================================
            for g in sorted(GRUPOS, key=lambda x:(compensado[x], carga[x])):

                if compensado[g] > 0 and g not in asignados:
                    asignados[g] = "COMPENSADO"
                    compensado[g]-=1
                    break

            # =================================================
            # APOYO + REGLA ANTI-SALTO
            # =================================================
            for g in GRUPOS:

                if g not in asignados:

                    if conteo[g]["T3"] > 0:
                        asignados[g] = "T2 APOYO"
                    elif conteo[g]["T2"] > conteo[g]["T1"]:
                        asignados[g] = "T2 APOYO"
                    else:
                        asignados[g] = "T1 APOYO"

            # =================================================
            # GUARDAR
            # =================================================
            for g in GRUPOS:

                filas.append({
                    "Fecha": fecha,
                    "Día": dia,
                    "Grupo": g,
                    "Turno": asignados[g],
                    "Festivo": "SI" if festivo else "NO"
                })

        df = pd.DataFrame(filas)
        st.session_state["malla"]=df

        st.success("Malla generada correctamente")

    # =====================================================
    # VISUALIZACIÓN
    # =====================================================
    if "malla" in st.session_state:

        df = st.session_state["malla"]

        st.subheader("📊 Malla horizontal")

        pivot = df.pivot(index="Grupo",columns="Fecha",values="Turno")

        rename = {}
        for c in pivot.columns:
            rename[c]=f"{c.strftime('%d-%m')}\n{DIAS_ES[c.weekday()]}"

        pivot.rename(columns=rename,inplace=True)

        st.dataframe(
            pivot.style.map(color_cell),
            use_container_width=True
        )

        # =================================================
        # EDITOR
        # =================================================
        st.subheader("✏️ Editor manual")

        edit = st.data_editor(
            df,
            use_container_width=True
        )

        if st.button("💾 Guardar cambios"):
            st.session_state["malla"]=edit
            st.success("Guardado")

        # =================================================
        # AUDITORÍA
        # =================================================
        st.subheader("🚨 Auditoría de saltos")

        errores=[]

        for g in GRUPOS:
            prev=None
            gdf=df[df["Grupo"]==g]

            for _,r in gdf.iterrows():

                if prev=="T2" and r["Turno"]=="T1":
                    errores.append(f"{g} T2→T1 {r['Fecha']}")

                if prev=="T3" and r["Turno"] in ["T1","T2"]:
                    errores.append(f"{g} T3→alto {r['Fecha']}")

                prev=r["Turno"]

        if errores:
            st.error("Saltos detectados")
            st.write(errores)
        else:
            st.success("Sin saltos indebidos")

        # =================================================
        # COBERTURA
        # =================================================
        st.subheader("📈 Cobertura diaria")

        cov = df[df["Turno"].isin(["T1","T2","T3"])].groupby("Fecha").size()

        st.line_chart(cov)

# =========================================================
# MENU
# =========================================================
def pantalla_programador():

    op = st.radio("Módulo",["Programador","Parametrizador"],horizontal=True)

    if op=="Programador":
        generar_malla()
    else:
        parametrizador()
