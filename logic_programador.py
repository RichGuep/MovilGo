# logic_programador.py
# =========================================================
# OPTIMIZADOR INTELIGENTE PRO ENTERPRISE - STABLE BUILD
# =========================================================

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import holidays
import io

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
# EXCEL LOCAL
# =========================================================
def cargar_excel(nombre):
    try:
        return pd.read_excel(nombre)
    except:
        return pd.DataFrame()

def guardar_excel(df, nombre):
    df.to_excel(nombre, index=False)

# =========================================================
# PARAMETRIZADOR
# =========================================================
def parametrizador():
    st.header("🧩 Parametrizador de Grupos")

    df = cargar_excel("empleados.xlsx")

    if df.empty:
        df = pd.DataFrame({
            "Empleado": ["A","B","C","D"],
            "Grupo": ["","","",""]
        })

    st.dataframe(df, use_container_width=True)

    if st.button("🎲 Asignar grupos aleatoriamente"):
        import random
        grupos = GRUPOS * 100
        random.shuffle(grupos)

        df["Grupo"] = [grupos[i] for i in range(len(df))]
        guardar_excel(df, "empleados.xlsx")
        st.success("Grupos asignados")
        st.dataframe(df)

# =========================================================
# COLORES FUERTES (FONDO)
# =========================================================
def color_cell(val):

    estilos = {
        "T1": "background-color:#1E90FF;color:white;font-weight:bold;",
        "T2": "background-color:#00B050;color:white;font-weight:bold;",
        "T3": "background-color:#C00000;color:white;font-weight:bold;",
        "T1 APOYO": "background-color:#A9D0F5;",
        "T2 APOYO": "background-color:#A9F5A9;",
        "DESCANSO": "background-color:black;color:yellow;font-weight:bold;",
        "COMPENSADO": "background-color:#FF8C00;color:black;font-weight:bold;"
    }

    return estilos.get(val,"")

# =========================================================
# GENERADOR PRINCIPAL
# =========================================================
def generar_malla():

    st.header("🚀 OPTIMIZADOR INTELIGENTE PRO")

    c1,c2 = st.columns(2)

    inicio = c1.date_input("Inicio", date.today())
    fin = c2.date_input("Fin", date.today()+timedelta(days=30))

    # =====================================================
    # DESCANSO DE LEY
    # =====================================================
    st.subheader("⚖️ Descanso de Ley")

    descanso_actual = {}

    cols = st.columns(len(GRUPOS))

    for i,g in enumerate(GRUPOS):
        descanso_actual[g] = cols[i].selectbox(
            f"{g}",
            DIAS_ES,
            index=i
        )

    # =====================================================
    # GENERAR
    # =====================================================
    if st.button("🚀 Generar malla"):

        fechas = pd.date_range(inicio, fin)

        carga = {g:0 for g in GRUPOS}
        conteo = {g:{"T1":0,"T2":0,"T3":0} for g in GRUPOS}
        compensado = {g:0 for g in GRUPOS}

        filas = []

        for fecha in fechas:

            dia = DIAS_ES[fecha.weekday()]
            festivo = fecha.date() in festivos_co

            asignados = {}

            descanso = [g for g in GRUPOS if descanso_actual[g]==dia]
            activos = [g for g in GRUPOS if g not in descanso]

            # =================================================
            # ASEGURAR COBERTURA 3 TURNOS
            # =================================================
            if len(activos) < 3:
                faltan = 3 - len(activos)
                movidos = descanso[:faltan]
                for m in movidos:
                    activos.append(m)
                    descanso.remove(m)
                    compensado[m] += 1

            # DESCANSO
            for g in descanso:
                asignados[g] = "DESCANSO"

            # TURNOS BASE
            for turno in ["T1","T2","T3"]:

                candidatos = sorted(activos, key=lambda g:(carga[g], conteo[g][turno]))

                if candidatos:
                    sel = candidatos[0]
                    asignados[sel] = turno
                    carga[sel]+=1
                    conteo[sel][turno]+=1
                    activos.remove(sel)

            # APOYO + COMPENSADO
            for g in activos:

                if compensado[g]>0:
                    asignados[g]="COMPENSADO"
                    compensado[g]-=1
                else:
                    asignados[g]="T1 APOYO"

            # GUARDAR
            for g in GRUPOS:
                filas.append({
                    "Fecha": fecha,
                    "Día": dia,
                    "Grupo": g,
                    "Turno": asignados.get(g,"T1 APOYO"),
                    "Festivo": "SI" if festivo else "NO"
                })

        df = pd.DataFrame(filas)
        st.session_state["malla"]=df
        guardar_excel(df,"malla.xlsx")

        st.success("Malla generada correctamente")

    # =====================================================
    # VISUALIZACIÓN
    # =====================================================
    if "malla" in st.session_state:

        df = st.session_state["malla"]

        st.subheader("📊 Malla horizontal")

        pivot = df.pivot(index="Grupo",columns="Fecha",values="Turno")

        # nombres días
        rename = {}
        for c in pivot.columns:
            rename[c]=f"{c.strftime('%d-%m')}\n{DIAS_ES[c.weekday()]}"

        pivot.rename(columns=rename,inplace=True)

        # EDITOR MANUAL
        st.subheader("✏️ Editor Manual")

        edit = st.data_editor(
            df,
            column_config={
                "Turno": st.column_config.SelectboxColumn(
                    "Turno",
                    options=TURNOS
                )
            },
            use_container_width=True
        )

        if st.button("💾 Guardar edición"):
            st.session_state["malla"]=edit
            guardar_excel(edit,"malla.xlsx")
            st.success("Guardado")

        # MALLA COLORES
        st.dataframe(
            pivot.style.applymap(color_cell),
            use_container_width=True
        )

        # =================================================
        # AUDITORÍA
        # =================================================
        st.subheader("🚨 Auditoría")

        errores = []

        for g in GRUPOS:
            prev=None
            gdf=df[df["Grupo"]==g]

            for _,r in gdf.iterrows():
                if prev=="T3" and r["Turno"]=="T1":
                    errores.append(f"{g} salto T3→T1 {r['Fecha']}")
                prev=r["Turno"]

        if errores:
            st.error("Saltos indebidos detectados")
            st.write(errores)
        else:
            st.success("Sin saltos indebidos")

        # =================================================
        # COBERTURA
        # =================================================
        st.subheader("📊 Cobertura")

        cobertura = df[df["Turno"].isin(["T1","T2","T3"])].groupby("Fecha").size()

        st.line_chart(cobertura)

# =========================================================
# MENU
# =========================================================
def pantalla_programador():

    op = st.radio("Modulo",["Programador","Parametrizador"],horizontal=True)

    if op=="Programador":
        generar_malla()
    else:
        parametrizador()
