# =========================================================
# OPTIMIZADOR INTELIGENTE PRO ENTERPRISE - HORIZONTAL REAL
# CONSOLIDADO (DESCANSOS + COMPENSADOS ESTABLES)
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
        "DESCANSO":"background-color:#2C3E50;color:#F9E79F;font-weight:700;",
        "COMPENSADO":"background-color:#FDEBD0;"
    }.get(v,"")

# =========================================================
# AUDITORIA
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
# GENERADOR (CON DESCANSOS ROBUSTOS)
# =========================================================

def generar_malla():

    st.header("🚀 OPTIMIZADOR INTELIGENTE PRO")

    c1,c2 = st.columns(2)

    inicio = c1.date_input("Inicio", date.today())
    fin = c2.date_input("Fin", date.today()+timedelta(days=30))

    st.subheader("⚖️ Descanso de ley")

    descanso = {}
    cols = st.columns(len(GRUPOS))

    for i,g in enumerate(GRUPOS):
        descanso[g] = cols[i].selectbox(g, DIAS_ES, index=i)

    # =========================
    # ESTADO
    # =========================

    carga = {g:0 for g in GRUPOS}
    conteo = {g:{"T1":0,"T2":0,"T3":0} for g in GRUPOS}

    compensado = {g:2 for g in GRUPOS}  # 🔥 CONSISTENTE (no infinito)
    sacrificio = {g:0 for g in GRUPOS}

    last_turn = {g:None for g in GRUPOS}
    streak = {g:0 for g in GRUPOS}

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

            descanso_dia = [g for g in GRUPOS if descanso[g] == dia]
            activos = [g for g in GRUPOS if g not in descanso_dia]

            # 🔥 ASEGURAR COBERTURA REAL
            while len(activos) < 3:

                mov = sorted(descanso_dia, key=lambda g:(sacrificio[g],carga[g]))[0]

                descanso_dia.remove(mov)
                activos.append(mov)

                sacrificio[mov] += 1
                compensado[mov] += 1

            # DESCANSO
            for g in descanso_dia:
                asignados[g] = "DESCANSO"
                last_turn[g] = "DESCANSO"
                streak[g] = 0

            # TURNOS PRINCIPALES
            for turno in ["T1","T2","T3"]:

                def score(g):
                    base = carga[g] + conteo[g][turno]

                    if last_turn[g] != turno:
                        base += 1000 if streak[g] < 4 else 10
                    else:
                        base -= 5

                    return base

                # 🔥 SAFE MODE
                if len(activos) == 0:
                    activos = [g for g in GRUPOS if g not in descanso_dia]

                sel = sorted(activos, key=score)[0]

                asignados[sel] = turno

                carga[sel] += 1
                conteo[sel][turno] += 1

                streak[sel] = streak[sel] + 1 if last_turn[sel] == turno else 1
                last_turn[sel] = turno

                activos.remove(sel)

            # APOYO / COMPENSADO
            for g in activos:

                if compensado[g] > 0:
                    asignados[g] = "COMPENSADO"
                    compensado[g] -= 1
                else:
                    asignados[g] = "T1 APOYO"

                streak[g] = streak[g] + 1 if last_turn[g] == asignados[g] else 1
                last_turn[g] = asignados[g]

            # GUARDADO
            for g in GRUPOS:
                filas.append({
                    "Fecha": fecha,
                    "Día": dia,
                    "Grupo": g,
                    "Turno": asignados[g],
                    "Festivo": "SI" if festivo else "NO"
                })

        df = pd.DataFrame(filas)

        st.session_state["malla"] = df

        guardar_github(df)

        st.success("Malla generada con lógica estable de descansos")

# =========================================================
# INTERFAZ
# =========================================================

def pantalla_programador():

    op = st.radio("Módulo",["Programador","Parametrizador"],horizontal=True)

    if op == "Parametrizador":
        st.write("OK")
        return

    generar_malla()

    if "malla" not in st.session_state:
        return

    df = st.session_state["malla"]

    st.subheader("📊 MALLA EDITABLE")

    pivot = df.pivot(index="Grupo", columns="Fecha", values="Turno")
    pivot = pivot.sort_index(axis=1)

    edit = st.data_editor(pivot, use_container_width=True)

    if st.button("💾 Guardar cambios"):

        df_edit = edit.reset_index().melt(
            id_vars="Grupo",
            var_name="Fecha",
            value_name="Turno"
        )

        df_edit["Fecha"] = pd.to_datetime(df_edit["Fecha"])

        st.session_state["malla"] = df_edit

        guardar_github(df_edit)

        st.success("Cambios guardados")

    col1, col2 = st.columns([2,1])

    with col2:

        st.subheader("🚨 Auditoría")

        errores, cobertura = auditoria(df)

        for e in errores[:15]:
            st.error(e)

        st.subheader("📈 Cobertura")

        st.line_chart(cobertura)

    with col1:

        st.subheader("📋 Vista operativa")

        st.dataframe(pivot.style.map(color_cell), use_container_width=True)
  
# =========================================================
# ENTRY POINT CENTRAL (OBLIGATORIO PARA APP.PY)
# =========================================================

def main():

    st.title("🚀 Optimización Operativa 24/7")

    modulo = st.radio(
        "Selecciona módulo",
        [
            "🧠 Personal Técnico",
            "🚌 Personal de Abordaje",
            "⚙️ Parametrizador"
        ],
        horizontal=True
    )

    if modulo == "🧠 Personal Técnico":
        pantalla_tecnico()

    elif modulo == "🚌 Personal de Abordaje":
        pantalla_abordaje()

    elif modulo == "⚙️ Parametrizador":
        pantalla_parametrizador()
