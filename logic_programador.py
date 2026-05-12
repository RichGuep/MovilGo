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
# PARAMETRIZADOR
# =========================================================

def pantalla_parametrizador():
    st.header("⚙️ Parametrizador de Grupos Inteligente")

    df = cargar_empleados()

    if df is None:
        st.error("No se pudo cargar empleados.xlsx")
        return

    st.dataframe(df)

    if "Cargo" not in df.columns or "Nombre" not in df.columns:
        st.error("Faltan columnas requeridas")
        return

    if st.button("🚀 Asignar grupos automáticamente"):

        tecnicos = df[df["Cargo"].isin(["Master", "Tecnico A", "Tecnico B"])].sample(frac=1)
        abordaje = df[df["Cargo"] == "Auxiliar de Abordaje y Atención al Público"].sample(frac=1)

        grupos_tecnicos = {f"Grupo {i+1}": [] for i in range(4)}
        grupos_abordaje = {f"Abordaje {i+1}": [] for i in range(5)}

        masters = tecnicos[tecnicos["Cargo"] == "Master"]
        a = tecnicos[tecnicos["Cargo"] == "Tecnico A"]
        b = tecnicos[tecnicos["Cargo"] == "Tecnico B"]

        for i in range(4):
            grupos_tecnicos[f"Grupo {i+1}"].extend(masters.iloc[i*2:(i+1)*2]["Nombre"].tolist())
            grupos_tecnicos[f"Grupo {i+1}"].extend(a.iloc[i*7:(i+1)*7]["Nombre"].tolist())
            grupos_tecnicos[f"Grupo {i+1}"].extend(b.iloc[i*3:(i+1)*3]["Nombre"].tolist())

        for i, nombre in enumerate(abordaje["Nombre"]):
            grupos_abordaje[f"Abordaje {(i % 5) + 1}"].append(nombre)

        df["GrupoAsignado"] = ""

        for g, lista in grupos_tecnicos.items():
            df.loc[df["Nombre"].isin(lista), "GrupoAsignado"] = g

        for g, lista in grupos_abordaje.items():
            df.loc[df["Nombre"].isin(lista), "GrupoAsignado"] = g

        guardar_empleados(df)

        st.success("Grupos asignados correctamente")

# =========================================================
# MÓDULOS FALTANTES (CORRECCIÓN DEL ERROR)
# =========================================================

def pantalla_tecnico():
    st.header("🛠️ Personal Técnico")

    df = cargar_empleados()
    if df is None:
        st.warning("No hay datos de empleados")
        return

    st.dataframe(df[df["Cargo"].isin(["Master","Tecnico A","Tecnico B"])])

def pantalla_abordaje():
    st.header("🚌 Personal de Abordaje")

    df = cargar_empleados()
    if df is None:
        st.warning("No hay datos de empleados")
        return

    st.dataframe(df[df["Cargo"] == "Auxiliar de Abordaje y Atención al Público"])

# =========================================================
# GENERADOR MALLA (TU LÓGICA ORIGINAL SIN CAMBIOS)
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

            for g in descanso_dia:
                asignados[g]="DESCANSO"

            for turno in ["T1","T2","T3"]:

                sel = activos[0]
                activos.remove(sel)

                asignados[sel]=turno

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
# MAIN (CORREGIDO)
# =========================================================

def main():

    st.title("🚀 Optimización Operativa 24/7")

    modulo = st.radio(
        "Módulos",
        ["Personal Técnico", "Personal de Abordaje", "Parametrizador", "Programador"],
        horizontal=True
    )

    if modulo == "Personal Técnico":
        pantalla_tecnico()

    elif modulo == "Personal de Abordaje":
        pantalla_abordaje()

    elif modulo == "Parametrizador":
        pantalla_parametrizador()

    elif modulo == "Programador":
        generar_malla()

# =========================================================

main()
