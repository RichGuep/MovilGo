# logic_programador.py
# =========================================================
# OPTIMIZADOR INTELIGENTE PRO ENTERPRISE - HORIZONTAL REAL
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
# COLORES SUAVES
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
# AUDITORÍA
# =========================================================
def auditoria(df):

    errores = []
    df = df.copy()
    df["Fecha"] = pd.to_datetime(df["Fecha"])

    # cobertura diaria
    cobertura = df[df["Turno"].isin(["T1","T2","T3"])].groupby("Fecha").size()

    for f,c in cobertura.items():
        if c < 3:
            errores.append(f"❌ Cobertura incompleta {f.date()} ({c}/3)")

    # saltos indebidos
    for g in GRUPOS:

        gdf = df[df["Grupo"] == g].sort_values("Fecha")

        prev = None

        for _, r in gdf.iterrows():

            if prev == "T2" and r["Turno"] == "T1":
                errores.append(f"{g} salto T2→T1 {r['Fecha'].date()}")

            if prev == "T3" and r["Turno"] in ["T1","T2"]:
                errores.append(f"{g} salto T3→alto {r['Fecha'].date()}")

            prev = r["Turno"]

    return errores, cobertura

# =========================================================
# GENERADOR
# =========================================================
def generar_malla():

    st.header("🚀 OPTIMIZADOR INTELIGENTE PRO")

    c1,c2 = st.columns(2)

    inicio = c1.date_input("Inicio", date.today())
    fin = c2.date_input("Fin", date.today()+timedelta(days=30))

    # =====================================================
    # DESCANSOS
    # =====================================================
    st.subheader("⚖️ Descanso de ley")

    descanso = {}
    cols = st.columns(len(GRUPOS))

    for i,g in enumerate(GRUPOS):
        descanso[g] = cols[i].selectbox(g, DIAS_ES, index=i)

    # =====================================================
    # ESTADO
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

            descanso_dia = [g for g in GRUPOS if descanso[g]==dia]
            activos = [g for g in GRUPOS if g not in descanso_dia]

            # asegurar cobertura
            while len(activos) < 3:

                mov = sorted(descanso_dia, key=lambda g:(sacrificio[g],carga[g]))[0]

                descanso_dia.remove(mov)
                activos.append(mov)

                sacrificio[mov]+=1
                compensado[mov]+=1

            # descansos
            for g in descanso_dia:
                asignados[g]="DESCANSO"

            # turnos obligatorios
            for turno in ["T1","T2","T3"]:

                sel = sorted(activos, key=lambda g:(carga[g],conteo[g][turno]))[0]

                asignados[sel]=turno
                carga[sel]+=1
                conteo[sel][turno]+=1
                activos.remove(sel)

            # compensados / apoyo
            for g in activos:

                if compensado[g]>0:
                    asignados[g]="COMPENSADO"
                    compensado[g]-=1
                else:
                    asignados[g]="T1 APOYO"

            # guardar
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

        st.success("Malla generada y guardada")

# =========================================================
# INTERFAZ PRINCIPAL (HORIZONTAL REAL)
# =========================================================
def pantalla_programador():

    op = st.radio("Módulo",["Programador","Parametrizador"],horizontal=True)

    if op=="Parametrizador":
        st.write("OK")
        return

    generar_malla()

    if "malla" not in st.session_state:
        return

    df = st.session_state["malla"]

    st.subheader("📊 MALLA HORIZONTAL REAL (EDITABLE)")

    # =====================================================
    # 🔥 CONVERSIÓN A MALLA HORIZONTAL REAL
    # =====================================================
    pivot = df.pivot(index="Grupo", columns="Fecha", values="Turno")

    pivot = pivot.sort_index(axis=1)

    # =====================================================
    # EDITOR ÚNICO (EXCEL REAL)
    # =====================================================
    edit = st.data_editor(
        pivot,
        use_container_width=True
    )

    # =====================================================
    # GUARDAR CAMBIOS
    # =====================================================
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

    # =====================================================
    # PANEL LATERAL DE AUDITORÍA
    # =====================================================
    col1, col2 = st.columns([2,1])

    with col2:

        st.subheader("🚨 Auditoría")

        errores, cobertura = auditoria(df)

        if errores:
            for e in errores[:15]:
                st.error(e)
        else:
            st.success("Sin errores")

        st.subheader("📈 Cobertura")

        st.line_chart(cobertura)

    with col1:

        st.subheader("📋 Vista operativa")

        st.dataframe(
            pivot.style.map(color_cell),
            use_container_width=True
        )
