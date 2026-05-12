# logic_programador.py
# =========================================================
# OPTIMIZADOR INTELIGENTE PRO ENTERPRISE - FATIGA REAL
# =========================================================

import streamlit as st
import pandas as pd
from datetime import date, timedelta
import holidays
import io
from github import Github

# =========================================================
# CONFIG
# =========================================================
TURNOS = ["T1","T2","T3","T1 APOYO","T2 APOYO","DESCANSO","COMPENSADO"]

GRUPOS = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]

DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]

festivos_co = holidays.Colombia()

# =========================================================
# REGLA DE FATIGA (CLAVE NUEVA)
# =========================================================
def validar_transicion(prev, actual):

    if prev == "T3" and actual in ["T1","T1 APOYO","T2 APOYO"]:
        return False

    if prev == "T2" and actual == "T1":
        return False

    return True

# =========================================================
# GITHUB
# =========================================================
def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            return None
        return Github(st.secrets["GITHUB_TOKEN"]).get_repo("RichGuep/movilgo")
    except:
        return None


def guardar_github(df):

    repo = conectar_github()
    if not repo:
        return

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    data = buffer.getvalue()

    try:
        file = repo.get_contents("malla_historica.xlsx")
        repo.update_file("malla_historica.xlsx","update",data,file.sha)
    except:
        repo.create_file("malla_historica.xlsx","create",data)

# =========================================================
# COLORES SUAVES
# =========================================================
def color_cell(v):

    return {
        "T1":"background:#D6EAF8",
        "T2":"background:#D5F5E3",
        "T3":"background:#FADBD8",

        "T1 APOYO":"background:#EAF2F8",
        "T2 APOYO":"background:#E8F6F3",

        "DESCANSO":"background:#1C1C1C;color:#FFD700;font-weight:700",

        "COMPENSADO":"background:#FDEBD0"
    }.get(v,"")

# =========================================================
# AUDITORÍA COMPLETA
# =========================================================
def auditoria(df):

    errores = []
    df = df.copy()

    df["Fecha"] = pd.to_datetime(df["Fecha"])

    # COBERTURA
    cov = df[df["Turno"].isin(["T1","T2","T3"])].groupby("Fecha").size()

    for f,c in cov.items():
        if c < 3:
            errores.append(f"❌ Cobertura incompleta {f.date()} ({c}/3)")

    # FATIGA POR GRUPO
    for g in GRUPOS:

        gdf = df[df["Grupo"]==g].sort_values("Fecha")

        prev = None

        for _,r in gdf.iterrows():

            act = r["Turno"]

            if prev and not validar_transicion(prev, act):
                errores.append(f"🚨 Fatiga {g}: {prev} → {act} ({r['Fecha'].date()})")

            prev = act

    return errores, cov

# =========================================================
# GENERADOR
# =========================================================
def generar_malla():

    st.header("🚀 OPTIMIZADOR PRO - FATIGA CONTROLADA")

    c1,c2 = st.columns(2)

    inicio = c1.date_input("Inicio", date.today())
    fin = c2.date_input("Fin", date.today()+timedelta(days=30))

    st.subheader("Descanso de ley")

    descanso = {}
    cols = st.columns(len(GRUPOS))

    for i,g in enumerate(GRUPOS):
        descanso[g] = cols[i].selectbox(g, DIAS_ES, index=i)

    carga = {g:0 for g in GRUPOS}
    conteo = {g:{"T1":0,"T2":0,"T3":0} for g in GRUPOS}

    compensado = {g:0 for g in GRUPOS}

    filas = []

    if st.button("🚀 Generar malla"):

        for f in pd.date_range(inicio, fin):

            dia = DIAS_ES[f.weekday()]
            fest = f.date() in festivos_co

            asign = {}

            descanso_g = [g for g in GRUPOS if descanso[g]==dia]
            activos = [g for g in GRUPOS if g not in descanso_g]

            while len(activos) < 3:
                activos.append(descanso_g.pop())

            for g in descanso_g:
                asign[g]="DESCANSO"

            prev_turno = {}

            for turno in ["T1","T2","T3"]:

                candidatos = sorted(activos, key=lambda g:(carga[g],conteo[g][turno]))

                for sel in candidatos:

                    if validar_transicion(prev_turno.get(sel), turno):
                        asign[sel]=turno
                        carga[sel]+=1
                        conteo[sel][turno]+=1
                        activos.remove(sel)
                        prev_turno[sel]=turno
                        break

            for g in activos:
                asign[g]="T1 APOYO"

            for g in GRUPOS:
                filas.append({
                    "Fecha": f,
                    "Día": dia,
                    "Grupo": g,
                    "Turno": asign[g],
                    "Festivo":"SI" if fest else "NO"
                })

        st.session_state["malla"]=pd.DataFrame(filas)

        guardar_github(st.session_state["malla"])

        st.success("Malla generada")

# =========================================================
# UI PRINCIPAL
# =========================================================
def pantalla_programador():

    generar_malla()

    if "malla" not in st.session_state:
        return

    df = st.session_state["malla"]

    st.subheader("📊 MALLA HORIZONTAL REAL")

    pivot = df.pivot(index="Grupo", columns="Fecha", values="Turno")

    st.dataframe(pivot.style.map(color_cell), use_container_width=True)

    st.subheader("✏️ EDITOR")

    edit = st.data_editor(df, use_container_width=True)

    st.session_state["malla"]=edit

    col1,col2 = st.columns([2,1])

    with col2:

        st.subheader("🚨 ALERTAS")

        errores,cov = auditoria(edit)

        if errores:
            for e in errores[:15]:
                st.error(e)
        else:
            st.success("OK")

        st.subheader("📈 COBERTURA")
        st.line_chart(cov)

    with col1:

        st.subheader("📋 VISTA")

        st.dataframe(pivot.style.map(color_cell), use_container_width=True)
