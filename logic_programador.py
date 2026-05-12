# =========================================================
# SISTEMA ENTERPRISE DE PROGRAMACIÓN DE TURNOS
# TECNICOS + ABORDAJE + PARAMETRIZADOR + AUDITORIA
# =========================================================

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import holidays
import io
import base64
from github import Github

# =========================================================
# CONFIG GLOBAL
# =========================================================

TURNOS_TEC = ["T1","T2","T3","T1 APOYO","T2 APOYO","DESCANSO","COMPENSADO"]
TURNOS_AB = ["T1","T2"]

GRUPOS_TEC = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]
GRUPOS_AB = ["Abordaje 1","Abordaje 2","Abordaje 3","Abordaje 4","Abordaje 5"]

DIAS = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]

festivos = holidays.Colombia()

MAX_AB = 10

# =========================================================
# GITHUB
# =========================================================

def repo():
    try:
        return Github(st.secrets["GITHUB_TOKEN"]).get_repo("RichGuep/movilgo")
    except:
        return None


def load_employees():
    r = repo()
    if not r:
        return None
    try:
        f = r.get_contents("empleados.xlsx")
        data = base64.b64decode(f.content)
        return pd.read_excel(io.BytesIO(data))
    except:
        return None


def save_file(df, name):
    r = repo()
    if not r:
        return

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as w:
        df.to_excel(w, index=False)

    data = buffer.getvalue()

    try:
        f = r.get_contents(name)
        r.update_file(name, "update", data, f.sha)
    except:
        r.create_file(name, "create", data)

# =========================================================
# AUDITORIA GLOBAL
# =========================================================

def auditoria(df, tipo="TEC"):

    errores = []

    df = df.copy()
    df["Fecha"] = pd.to_datetime(df["Fecha"])

    if tipo == "TEC":

        for g in df["Grupo"].unique():

            gdf = df[df["Grupo"] == g].sort_values("Fecha")

            prev = None
            streak = 0

            for _,r in gdf.iterrows():

                t = r["Turno"]

                # SALTOS CRÍTICOS
                if prev == "T3" and t in ["T1","T2"]:
                    errores.append(f"❌ Salto T3 → {t} | {g} | {r['Fecha'].date()}")

                # BLOQUES
                if t in ["T1","T2","T3"]:
                    streak = streak + 1 if prev == t else 1
                    if streak < 4:
                        errores.append(f"⚠️ Bloque corto {g} {t} {r['Fecha'].date()}")

                prev = t

    else:

        # ABORDAJE
        pivot = df.groupby(["Nombre","Turno"]).size().unstack(fill_value=0)

        if "T1" in pivot and "T2" in pivot:
            diff = (pivot["T1"] - pivot["T2"]).abs().mean()
            if diff > 3:
                errores.append("⚠️ Desbalance fuerte entre T1 y T2")

    return errores

# =========================================================
# 🧠 PERSONAL TECNICO
# =========================================================

def pantalla_tecnico():

    st.header("🧠 Personal Técnico")

    df = load_employees()
    if df is None:
        return

    tecnicos = df[df["Cargo"].isin(["Master","Tecnico A","Tecnico B"])]

    inicio = st.date_input("Inicio", date.today())
    fin = st.date_input("Fin", date.today()+timedelta(days=30))

    descanso = {}

    cols = st.columns(4)

    for i,g in enumerate(GRUPOS_TEC):
        descanso[g] = cols[i].selectbox(g, DIAS, index=i)

    carga = {g:0 for g in GRUPOS_TEC}
    conteo = {g:{"T1":0,"T2":0,"T3":0} for g in GRUPOS_TEC}
    last = {g:None for g in GRUPOS_TEC}
    streak = {g:0 for g in GRUPOS_TEC}

    rows = []

    if st.button("🚀 Generar Técnico"):

        for f in pd.date_range(inicio, fin):

            dia = DIAS[f.weekday()]
            fest = f.date() in festivos

            asignados = {}

            descanso_dia = [g for g in GRUPOS_TEC if descanso[g]==dia]
            activos = [g for g in GRUPOS_TEC if g not in descanso_dia]

            for g in descanso_dia:
                asignados[g] = "DESCANSO"

            for t in ["T1","T2","T3"]:

                def score(g):
                    base = carga[g] + conteo[g][t]
                    if last[g] != t:
                        base += 1000 if streak[g] < 4 else 10
                    return base

                sel = sorted(activos,key=score)[0]

                asignados[sel]=t
                carga[sel]+=1
                conteo[sel][t]+=1

                streak[sel] = streak[sel]+1 if last[sel]==t else 1
                last[sel]=t

                activos.remove(sel)

            for g in activos:
                asignados[g]="T1 APOYO"

            for g in GRUPOS_TEC:
                rows.append({
                    "Fecha":f,
                    "Grupo":g,
                    "Turno":asignados[g],
                    "Día":dia,
                    "Festivo":"SI" if fest else "NO"
                })

        df_out = pd.DataFrame(rows)

        st.session_state["tec"]=df_out

        save_file(df_out,"malla_tecnicos.xlsx")

    if "tec" in st.session_state:

        dfv = st.session_state["tec"]

        st.subheader("📊 Malla Técnica")

        pivot = dfv.pivot(index="Grupo",columns="Fecha",values="Turno")

        st.data_editor(pivot,use_container_width=True)

        st.subheader("🚨 Auditoría")

        err = auditoria(dfv,"TEC")

        for e in err[:20]:
            st.error(e)

# =========================================================
# 🚌 PERSONAL ABORDAJE
# =========================================================

def pantalla_abordaje():

    st.header("🚌 Personal de Abordaje")

    df = load_employees()
    if df is None:
        return

    ab = df[df["Cargo"]=="Auxiliar de Abordaje y Atención al Público"]

    inicio = st.date_input("Inicio AB", date.today())
    fin = st.date_input("Fin AB", date.today()+timedelta(days=30))

    descanso = {}

    cols = st.columns(5)

    for i,g in enumerate(GRUPOS_AB):
        descanso[g] = cols[i].selectbox(g, DIAS, index=i)

    rows = []

    if st.button("🚀 Generar Abordaje"):

        for f in pd.date_range(inicio, fin):

            dia = DIAS[f.weekday()]
            fest = f.date() in festivos

            asignados = {"T1":[], "T2":[]}

            descanso_global = any(dia == descanso[g] for g in GRUPOS_AB)

            if descanso_global:

                for _,r in ab.iterrows():
                    rows.append({
                        "Fecha":f,
                        "Nombre":r["Nombre"],
                        "Turno":"DESCANSO",
                        "Festivo":"SI" if fest else "NO"
                    })
                continue

            pool = ab.sample(frac=1)

            for _,r in pool.iterrows():

                turno = "T1" if len(asignados["T1"]) < MAX_AB else "T2"

                asignados[turno].append(r["Nombre"])

                rows.append({
                    "Fecha":f,
                    "Nombre":r["Nombre"],
                    "Turno":turno,
                    "Festivo":"SI" if fest else "NO"
                })

        df_out = pd.DataFrame(rows)

        st.session_state["ab"]=df_out

        save_file(df_out,"malla_abordaje.xlsx")

    if "ab" in st.session_state:

        st.subheader("📊 Abordaje")

        st.data_editor(
            st.session_state["ab"].pivot(index="Nombre",columns="Fecha",values="Turno"),
            use_container_width=True
        )

        st.subheader("🚨 Auditoría")

        err = auditoria(st.session_state["ab"],"AB")

        for e in err[:20]:
            st.warning(e)

# =========================================================
# PARAMETRIZADOR
# =========================================================

def pantalla_parametrizador():

    st.header("⚙️ Parametrizador")

    df = load_employees()

    if df is None:
        return

    st.dataframe(df)

    st.info("Aquí va asignación de grupos (ya integrada en versión anterior)")

# =========================================================
# MENU PRINCIPAL
# =========================================================

def main():

    op = st.radio(
        "Módulos",
        ["Personal Técnico","Parametrizador","Personal de Abordaje"],
        horizontal=True
    )

    if op=="Personal Técnico":
        pantalla_tecnico()

    if op=="Personal de Abordaje":
        pantalla_abordaje()

    if op=="Parametrizador":
        pantalla_parametrizador()

main()
