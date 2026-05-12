# logic_programador.py
# =========================================================
# OPTIMIZADOR INTELIGENTE PRO - MALLA HORIZONTAL EDITABLE
# =========================================================

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import holidays

# =========================================================
# CONFIG
# =========================================================
TURNOS = ["T1","T2","T3","T1 APOYO","T2 APOYO","DESCANSO","COMPENSADO"]

GRUPOS = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]

DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]

festivos_co = holidays.Colombia()

# =========================================================
# COLORES SUAVES
# =========================================================
def color_cell(v):
    return {
        "T1":"background:#D6EAF8",
        "T2":"background:#D5F5E3",
        "T3":"background:#FADBD8",

        "DESCANSO":"background:#2C3E50;color:#F9E79F;font-weight:700",
        "COMPENSADO":"background:#FDEBD0",

        "T1 APOYO":"background:#EBF5FB",
        "T2 APOYO":"background:#EAF2F8"
    }.get(v,"")

# =========================================================
# MOTOR
# =========================================================
def generar_base(inicio, fin):

    carga = {g:0 for g in GRUPOS}
    conteo = {g:{"T1":0,"T2":0,"T3":0} for g in GRUPOS}
    compensado = {g:0 for g in GRUPOS}

    filas = []

    fechas = pd.date_range(inicio, fin)

    for fecha in fechas:

        dia = DIAS_ES[fecha.weekday()]
        festivo = fecha.date() in festivos_co

        asignados = {}

        descanso = [g for g in GRUPOS if st.session_state["descanso"][g]==dia]
        activos = [g for g in GRUPOS if g not in descanso]

        while len(activos) < 3:
            g = sorted(descanso, key=lambda x:carga[x])[0]
            descanso.remove(g)
            activos.append(g)
            compensado[g]+=1

        for g in descanso:
            asignados[g]="DESCANSO"

        for turno in ["T1","T2","T3"]:

            sel = sorted(activos, key=lambda g:(carga[g],conteo[g][turno]))[0]

            asignados[sel]=turno
            carga[sel]+=1
            conteo[sel][turno]+=1
            activos.remove(sel)

        for g in GRUPOS:
            if compensado[g]>0 and g not in asignados:
                asignados[g]="COMPENSADO"
                compensado[g]-=1

        for g in GRUPOS:
            if g not in asignados:
                asignados[g]="T1 APOYO"

        for g in GRUPOS:
            filas.append({
                "Fecha": fecha,
                "Día": dia,
                "Grupo": g,
                "Turno": asignados[g],
                "Festivo": "SI" if festivo else "NO"
            })

    return pd.DataFrame(filas)

# =========================================================
# AUDITORIA
# =========================================================
def auditoria(df):

    errores = []
    cobertura = []

    for f, gdf in df.groupby("Fecha"):

        cnt = len(gdf[gdf["Turno"].isin(["T1","T2","T3"])])

        if cnt < 3:
            cobertura.append(f"⚠️ Cobertura incompleta {f.date()} ({cnt}/3)")

    for g in GRUPOS:

        prev = None
        gdf = df[df["Grupo"]==g]

        for _,r in gdf.iterrows():

            if prev=="T3" and r["Turno"] in ["T1","T2"]:
                errores.append(f"{g} T3→{r['Turno']} {r['Fecha'].date()}")

            if prev=="T2" and r["Turno"]=="T1":
                errores.append(f"{g} T2→T1 {r['Fecha'].date()}")

            prev = r["Turno"]

    return errores, cobertura

# =========================================================
# UI PRINCIPAL
# =========================================================
def generar_malla():

    st.header("🚀 OPTIMIZADOR PRO - MALLA HORIZONTAL")

    c1,c2 = st.columns(2)

    inicio = c1.date_input("Inicio", date.today())
    fin = c2.date_input("Fin", date.today()+timedelta(days=30))

    st.session_state["inicio"]=inicio
    st.session_state["fin"]=fin

    # =====================================================
    # DESCANSO
    # =====================================================
    st.subheader("⚖️ Descanso de ley")

    if "descanso" not in st.session_state:
        st.session_state["descanso"] = {
            g: DIAS_ES[i] for i,g in enumerate(GRUPOS)
        }

    cols = st.columns(len(GRUPOS))

    for i,g in enumerate(GRUPOS):

        st.session_state["descanso"][g] = cols[i].selectbox(
            g,
            DIAS_ES,
            index=DIAS_ES.index(st.session_state["descanso"][g])
        )

    # =====================================================
    # GENERAR
    # =====================================================
    if st.button("Generar malla"):

        st.session_state["malla"] = generar_base(inicio,fin)

    # =====================================================
    # VISUALIZACIÓN ÚNICA
    # =====================================================
    if "malla" in st.session_state:

        df = st.session_state["malla"]

        st.subheader("📊 MALLA HORIZONTAL EDITABLE")

        pivot = df.pivot(index="Grupo",columns="Fecha",values="Turno")

        rename = {}
        for c in pivot.columns:
            rename[c]=f"{c.strftime('%d-%m')}\n{DIAS_ES[c.weekday()]}"

        pivot.rename(columns=rename,inplace=True)

        # ================================
        # EDITOR REAL (MISMA MALLA)
        # ================================
        edited = st.data_editor(
            pivot,
            use_container_width=True,
            num_rows="fixed"
        )

        # reconstrucción segura
        df_edit = edited.reset_index().melt(
            id_vars=["Grupo"],
            var_name="Fecha",
            value_name="Turno"
        )

        st.session_state["malla"]=df_edit

        # ================================
        # PANEL DE ALERTAS LATERAL
        # ================================
        col1,col2 = st.columns([3,1])

        with col2:

            st.subheader("🚨 Alertas")

            errores,cobertura = auditoria(df_edit)

            if errores:
                st.error("Saltos indebidos")
                for e in errores:
                    st.write(e)
            else:
                st.success("Sin saltos")

            if cobertura:
                st.warning("Cobertura")
                for c in cobertura:
                    st.write(c)
            else:
                st.success("Cobertura OK")

        # ================================
        # DASHBOARD
        # ================================
        st.subheader("📊 Dashboard")

        c1,c2,c3 = st.columns(3)

        c1.metric("T1", len(df_edit[df_edit["Turno"]=="T1"]))
        c2.metric("T2/T3", len(df_edit[df_edit["Turno"].isin(["T2","T3"])]))
        c3.metric("Descansos", len(df_edit[df_edit["Turno"]=="DESCANSO"]))

# =========================================================
# MENU
# =========================================================
def pantalla_programador():

    op = st.radio("Módulo",["Programador","Parametrizador"],horizontal=True)

    if op=="Programador":
        generar_malla()
    else:
        st.write("Parametrizador activo")
