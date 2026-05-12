# =========================================================
# OPTIMIZADOR INTELIGENTE PRO ENTERPRISE - HORIZONTAL REAL
# + PARAMETRIZADOR CORREGIDO (SOLO CARGO)
# =========================================================

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import holidays
import io
import base64
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


def cargar_empleados():
    repo = conectar_github()
    if not repo:
        return None

    try:
        file = repo.get_contents("empleados.xlsx")
        data = base64.b64decode(file.content)
        return pd.read_excel(io.BytesIO(data))
    except:
        return None


def guardar_empleados(df):
    repo = conectar_github()
    if not repo:
        return

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    data = buffer.getvalue()

    try:
        file = repo.get_contents("empleados.xlsx")
        repo.update_file("empleados.xlsx", "update empleados", data, file.sha)
    except:
        repo.create_file("empleados.xlsx", "create empleados", data)


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
# PARAMETRIZADOR (CORREGIDO SOLO CARGO)
# =========================================================

def pantalla_parametrizador():

    st.header("⚙️ Parametrizador de Grupos Inteligente")

    df = cargar_empleados()

    if df is None:
        st.error("No se pudo cargar empleados.xlsx")
        return

    st.subheader("📄 Vista empleados")
    st.dataframe(df)

    if "Cargo" not in df.columns:
        st.error("❌ Falta la columna 'Cargo' en empleados.xlsx")
        return

    if "Nombre" not in df.columns:
        st.error("❌ Falta la columna 'Nombre' en empleados.xlsx")
        return

    if st.button("🚀 Asignar grupos automáticamente"):

        # =====================================================
        # TECNICOS (4 GRUPOS)
        # =====================================================

        tecnicos = df[df["Cargo"].isin(["Master", "Tecnico A", "Tecnico B"])].copy()
        tecnicos = tecnicos.sample(frac=1).reset_index(drop=True)

        masters = tecnicos[tecnicos["Cargo"] == "Master"]
        a = tecnicos[tecnicos["Cargo"] == "Tecnico A"]
        b = tecnicos[tecnicos["Cargo"] == "Tecnico B"]

        grupos_tecnicos = {f"Grupo {i+1}": [] for i in range(4)}

        for i in range(4):

            grupos_tecnicos[f"Grupo {i+1}"].extend(
                masters.iloc[i*2:(i+1)*2]["Nombre"].tolist()
            )

            grupos_tecnicos[f"Grupo {i+1}"].extend(
                a.iloc[i*7:(i+1)*7]["Nombre"].tolist()
            )

            grupos_tecnicos[f"Grupo {i+1}"].extend(
                b.iloc[i*3:(i+1)*3]["Nombre"].tolist()
            )

        # =====================================================
        # ABORDAJE (5 GRUPOS DE 5 PERSONAS)
        # =====================================================

        abordaje = df[df["Cargo"] == "Auxiliar de Abordaje y Atención al Público"].copy()
        abordaje = abordaje.sample(frac=1).reset_index(drop=True)

        grupos_abordaje = {f"Abordaje {i+1}": [] for i in range(5)}

        for i, nombre in enumerate(abordaje["Nombre"]):
            grupo = f"Abordaje {(i % 5) + 1}"
            grupos_abordaje[grupo].append(nombre)

        # =====================================================
        # RESULTADO
        # =====================================================

        st.subheader("🧠 Grupos Técnicos")
        st.json(grupos_tecnicos)

        st.subheader("🚌 Grupos Abordaje")
        st.json(grupos_abordaje)

        # =====================================================
        # GUARDAR
        # =====================================================

        df["GrupoAsignado"] = ""

        for g, lista in grupos_tecnicos.items():
            df.loc[df["Nombre"].isin(lista), "GrupoAsignado"] = g

        for g, lista in grupos_abordaje.items():
            df.loc[df["Nombre"].isin(lista), "GrupoAsignado"] = g

        guardar_empleados(df)

        st.success("✅ Grupos asignados y guardados en GitHub")

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
# AUDITORÍA
# =========================================================

def auditoria(df):

    errores = []
    df = df.copy()
    df["Fecha"] = pd.to_datetime(df["Fecha"])

    cobertura = df[df["Turno"].isin(["T1","T2","T3"])].groupby("Fecha").size()

    for f,c in cobertura.items():
        if c < 3:
            errores.append(f"❌ Cobertura incompleta {f.date()} ({c}/3)")

    return errores, cobertura

# =========================================================
# GENERADOR MALLA
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

    carga = {g:0 for g in GRUPOS}
    conteo = {g:{"T1":0,"T2":0,"T3":0} for g in GRUPOS}

    compensado = {g:0 for g in GRUPOS}
    sacrificio = {g:0 for g in GRUPOS}

    last_turn = {g: None for g in GRUPOS}
    streak = {g: 0 for g in GRUPOS}

    filas = []

    if st.button("🚀 Generar malla"):

        fechas = pd.date_range(inicio, fin)

        for fecha in fechas:

            dia = DIAS_ES[fecha.weekday()]
            festivo = fecha.date() in festivos_co

            asignados = {}

            descanso_dia = [g for g in GRUPOS if descanso[g]==dia]
            activos = [g for g in GRUPOS if g not in descanso_dia]

            while len(activos) < 3:
                mov = sorted(descanso_dia, key=lambda g:(sacrificio[g],carga[g]))[0]
                descanso_dia.remove(mov)
                activos.append(mov)

            for g in descanso_dia:
                asignados[g]="DESCANSO"
                last_turn[g]="DESCANSO"
                streak[g]=0

            for turno in ["T1","T2","T3"]:

                def score(g):
                    base = carga[g] + conteo[g][turno]
                    if last_turn[g] != turno:
                        base += 1000 if streak[g] < 4 else 10
                    else:
                        base -= 5
                    return base

                sel = sorted(activos, key=score)[0]

                asignados[sel]=turno
                carga[sel]+=1
                conteo[sel][turno]+=1

                if last_turn[sel]==turno:
                    streak[sel]+=1
                else:
                    streak[sel]=1
                    last_turn[sel]=turno

                activos.remove(sel)

            for g in activos:
                asignados[g]="T1 APOYO"

            for g in GRUPOS:
                filas.append({
                    "Fecha":fecha,
                    "Día":dia,
                    "Grupo":g,
                    "Turno":asignados[g],
                    "Festivo":"SI" if festivo else "NO"
                })

        df = pd.DataFrame(filas)
        st.session_state["malla"]=df
        guardar_github(df)

        st.success("Malla generada")

# =========================================================
# INTERFAZ
# =========================================================

def pantalla_programador():

    op = st.radio("Módulo",["Programador","Parametrizador"],horizontal=True)

    if op=="Parametrizador":
        pantalla_parametrizador()
        return

    generar_malla()

    if "malla" not in st.session_state:
        return

    df = st.session_state["malla"]

    st.subheader("📊 MALLA")

    pivot = df.pivot(index="Grupo", columns="Fecha", values="Turno")

    st.data_editor(pivot, use_container_width=True)
