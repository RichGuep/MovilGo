# =========================================================
# OPTIMIZADOR INTELIGENTE PRO ENTERPRISE
# TECNICOS + ABORDAJE + PARAMETRIZADOR + AUDITORIA
# =========================================================

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import holidays
import io
from github import Github

# =========================================================
# CONFIG
# =========================================================

TURNOS_TEC = ["T1","T2","T3","T1 APOYO","T2 APOYO","DESCANSO","COMPENSADO"]
TURNOS_AB = ["T1","T2"]

GRUPOS_TEC = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]
GRUPOS_AB = ["Grupo A","Grupo B","Grupo C","Grupo D","Grupo E"]

DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]

festivos_co = holidays.Colombia()

MAX_AB = 10

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
        repo.update_file("malla_historica.xlsx", "update", data, file.sha)
    except:
        repo.create_file("malla_historica.xlsx", "create", data)

# =========================================================
# COLORES
# =========================================================

def color_cell(v):
    return {
        "T1":"background-color:#D6EAF8;color:#1B4F72;",
        "T2":"background-color:#D5F5E3;color:#145A32;",
        "T3":"background-color:#FADBD8;color:#7B241C;",
        "T1 APOYO":"background-color:#EBF5FB;",
        "T2 APOYO":"background-color:#EAF2F8;",
        "DESCANSO":"background-color:#2C3E50;color:white;font-weight:700;",
        "COMPENSADO":"background-color:#FDEBD0;"
    }.get(v,"")

# =========================================================
# AUDITORIA TECNICOS
# =========================================================

def auditoria_tecnicos(df):

    errores = []
    df = df.copy()
    df["Fecha"] = pd.to_datetime(df["Fecha"])

    cobertura = df[df["Turno"].isin(["T1","T2","T3"])].groupby("Fecha").size()

    for f,c in cobertura.items():
        if c < 3:
            errores.append(f"❌ Cobertura incompleta {f.date()} ({c}/3)")

    for g in GRUPOS_TEC:

        gdf = df[df["Grupo"] == g].sort_values("Fecha")

        prev = None
        streak = 0

        for _,r in gdf.iterrows():

            t = r["Turno"]

            if prev == "T3" and t in ["T1","T2"]:
                errores.append(f"❌ Salto T3→{t} | {g} | {r['Fecha'].date()}")

            if t in ["T1","T2","T3"]:
                streak = streak + 1 if prev == t else 1
                if streak < 4:
                    errores.append(f"⚠️ Bloque corto {g} {t} {r['Fecha'].date()}")

            prev = t

    return errores, cobertura

# =========================================================
# AUDITORIA ABORDAJE
# =========================================================

def auditoria_abordaje(df):

    errores = []
    df = df.copy()

    pivot = df.groupby(["Nombre","Turno"]).size().unstack(fill_value=0)

    if "T1" in pivot.columns and "T2" in pivot.columns:

        diff = (pivot["T1"] - pivot["T2"]).abs().mean()

        if diff > 3:
            errores.append("⚠️ Desbalance global entre T1 y T2")

    return errores

# =========================================================
# 🧠 PERSONAL TECNICO
# =========================================================

def pantalla_tecnico():

    st.header("🧠 Personal Técnico")

    inicio = st.date_input("Inicio", date.today())
    fin = st.date_input("Fin", date.today()+timedelta(days=30))

    descanso = {}
    cols = st.columns(4)

    for i,g in enumerate(GRUPOS_TEC):
        descanso[g] = cols[i].selectbox(g, DIAS_ES, index=i)

    carga = {g:0 for g in GRUPOS_TEC}
    conteo = {g:{"T1":0,"T2":0,"T3":0} for g in GRUPOS_TEC}
    last = {g:None for g in GRUPOS_TEC}
    streak = {g:0 for g in GRUPOS_TEC}

    filas = []

    if st.button("🚀 Generar Técnico"):

        for f in pd.date_range(inicio, fin):

            dia = DIAS_ES[f.weekday()]
            fest = f.date() in festivos_co

            asignados = {}

            descanso_dia = [g for g in GRUPOS_TEC if descanso[g] == dia]
            activos = [g for g in GRUPOS_TEC if g not in descanso_dia]

            for g in descanso_dia:
                asignados[g] = "DESCANSO"

            for t in ["T1","T2","T3"]:

                def score(g):
                    base = carga[g] + conteo[g][t]
                    if last[g] != t:
                        base += 1000 if streak[g] < 4 else 10
                    return base

                # =====================================================
                # 🔥 FIX CRÍTICO: PROTECCIÓN DE LISTA VACÍA
                # =====================================================

                if len(activos) == 0:
                    activos = [g for g in GRUPOS_TEC if g not in descanso_dia]

                if len(activos) == 0:
                    activos = GRUPOS_TEC.copy()

                sel = sorted(activos, key=score)[0]

                asignados[sel] = t

                carga[sel] += 1
                conteo[sel][t] += 1

                streak[sel] = streak[sel] + 1 if last[sel] == t else 1
                last[sel] = t

                activos.remove(sel)

            for g in activos:
                asignados[g] = "T1 APOYO"

            for g in GRUPOS_TEC:
                filas.append({
                    "Fecha": f,
                    "Grupo": g,
                    "Turno": asignados[g],
                    "Día": dia,
                    "Festivo": "SI" if fest else "NO"
                })

        df = pd.DataFrame(filas)

        st.session_state["malla"] = df

        guardar_github(df)

        st.success("Malla técnica generada")

    if "malla" in st.session_state:

        df = st.session_state["malla"]

        st.subheader("📊 Malla Técnica")

        pivot = df.pivot(index="Grupo", columns="Fecha", values="Turno")

        st.data_editor(pivot, use_container_width=True)

        st.subheader("🚨 Auditoría")

        err, cov = auditoria_tecnicos(df)

        for e in err[:20]:
            st.error(e)

# =========================================================
# 🚌 PERSONAL ABORDAJE
# =========================================================

def pantalla_abordaje():

    st.header("🚌 Personal de Abordaje")

    inicio = st.date_input("Inicio AB", date.today())
    fin = st.date_input("Fin AB", date.today()+timedelta(days=30))

    descanso = {}
    cols = st.columns(len(GRUPOS_AB))

    for i,g in enumerate(GRUPOS_AB):
        descanso[g] = cols[i].selectbox(g, DIAS_ES, index=i)

    filas = []
    historial = {}

    if st.button("🚀 Generar Abordaje"):

        for f in pd.date_range(inicio, fin):

            dia = DIAS_ES[f.weekday()]
            fest = f.date() in festivos_co

            grupos_descanso = [g for g in GRUPOS_AB if descanso[g] == dia]

            if grupos_descanso:

                for g in GRUPOS_AB:
                    filas.append({
                        "Fecha": f,
                        "Grupo": g,
                        "Turno": "DESCANSO",
                        "Festivo": "SI" if fest else "NO"
                    })

                continue

            t1, t2 = 0, 0

            for g in GRUPOS_AB:

                if g not in historial:
                    historial[g] = {"T1":0,"T2":0}

                if historial[g]["T1"] <= historial[g]["T2"]:
                    turno = "T1"
                else:
                    turno = "T2"

                if turno == "T1" and t1 >= MAX_AB:
                    turno = "T2"
                if turno == "T2" and t2 >= MAX_AB:
                    turno = "T1"

                if turno == "T1":
                    t1 += 1
                else:
                    t2 += 1

                historial[g][turno] += 1

                filas.append({
                    "Fecha": f,
                    "Grupo": g,
                    "Turno": turno,
                    "Festivo": "SI" if fest else "NO"
                })

        df = pd.DataFrame(filas)

        st.session_state["abordaje"] = df

        guardar_github(df)

        st.success("Malla de abordaje generada")

    if "abordaje" in st.session_state:

        df = st.session_state["abordaje"]

        st.subheader("📊 Abordaje")

        st.data_editor(
            df.pivot(index="Grupo", columns="Fecha", values="Turno"),
            use_container_width=True
        )

        st.subheader("🚨 Auditoría")

        err = auditoria_abordaje(df)

        for e in err:
            st.warning(e)

# =========================================================
# PARAMETRIZADOR
# =========================================================

def pantalla_parametrizador():

    st.header("⚙️ Parametrizador")

    st.info("Base lista para conectar empleados.xlsx y reglas de negocio")

# =========================================================
# MAIN (IMPORTANTE)
# =========================================================

def main():

    menu = st.radio(
        "Módulos",
        ["Personal Técnico", "Personal de Abordaje", "Parametrizador"],
        horizontal=True
    )

    if menu == "Personal Técnico":
        pantalla_tecnico()

    elif menu == "Personal de Abordaje":
        pantalla_abordaje()

    elif menu == "Parametrizador":
        pantalla_parametrizador()
  
