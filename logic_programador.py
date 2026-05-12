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

TURNOS = ["T1","T2","T3","T1 APOYO","T2 APOYO","DESCANSO","COMPENSADO"]

GRUPOS = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]

GRUPOS_AB = ["Grupo A","Grupo B","Grupo C","Grupo D","Grupo E"]

DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]

festivos_co = holidays.Colombia()

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

def auditoria(df):

    errores = []
    df = df.copy()
    df["Fecha"] = pd.to_datetime(df["Fecha"])

    cobertura = df[df["Turno"].isin(["T1","T2","T3"])].groupby("Fecha").size()

    for f,c in cobertura.items():
        if c < 3:
            errores.append(f"❌ Cobertura incompleta {f.date()} ({c}/3)")

    for g in GRUPOS:

        gdf = df[df["Grupo"] == g].sort_values("Fecha")

        prev = None
        streak = 0

        for _, r in gdf.iterrows():

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
# TECNICOS
# =========================================================

def pantalla_tecnico():

    try:

        st.header("🧠 Personal Técnico")

        inicio = st.date_input("Inicio", date.today())
        fin = st.date_input("Fin", date.today() + timedelta(days=30))

        descanso = {}
        cols = st.columns(4)

        for i,g in enumerate(GRUPOS):
            descanso[g] = cols[i].selectbox(g, DIAS_ES, index=i)

        carga = {g:0 for g in GRUPOS}
        conteo = {g:{"T1":0,"T2":0,"T3":0} for g in GRUPOS}
        last = {g:None for g in GRUPOS}
        streak = {g:0 for g in GRUPOS}

        filas = []

        if st.button("🚀 Generar Técnico"):

            for f in pd.date_range(inicio, fin):

                dia = DIAS_ES[f.weekday()]
                fest = f.date() in festivos_co

                asignados = {}

                descanso_dia = [g for g in GRUPOS if descanso[g] == dia]
                activos = [g for g in GRUPOS if g not in descanso_dia]

                for g in descanso_dia:
                    asignados[g] = "DESCANSO"

                for t in ["T1","T2","T3"]:

                    def score(g):
                        base = carga[g] + conteo[g][t]
                        if last[g] != t:
                            base += 1000 if streak[g] < 4 else 10
                        return base

                    if len(activos) == 0:
                        activos = GRUPOS.copy()

                    sel = sorted(activos, key=score)[0]

                    asignados[sel] = t

                    carga[sel] += 1
                    conteo[sel][t] += 1

                    streak[sel] = streak[sel] + 1 if last[sel] == t else 1
                    last[sel] = t

                    activos.remove(sel)

                for g in activos:
                    asignados[g] = "T1 APOYO"

                for g in GRUPOS:
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

    except Exception as e:
        st.error(f"Error en técnico: {e}")

# =========================================================
# ABORDAJE
# =========================================================

def pantalla_abordaje():

    try:

        st.header("🚌 Personal de Abordaje")

        st.info("Módulo operativo activo")

    except Exception as e:
        st.error(f"Error en abordaje: {e}")

# =========================================================
# PARAMETRIZADOR
# =========================================================

def pantalla_parametrizador():

    st.header("⚙️ Parametrizador")

# =========================================================
# MAIN (ROUTER CENTRAL - FIX DEFINITIVO)
# =========================================================

def main():

    try:

        st.title("🚀 Optimización Operativa 24/7")

        modulo = st.radio(
            "Módulos",
            ["Personal Técnico", "Personal de Abordaje", "Parametrizador"],
            horizontal=True
        )

        if modulo == "Personal Técnico":
            pantalla_tecnico()

        elif modulo == "Personal de Abordaje":
            pantalla_abordaje()

        elif modulo == "Parametrizador":
            pantalla_parametrizador()

    except Exception as e:
        st.error("💥 Error crítico en main()")
        st.exception(e)
