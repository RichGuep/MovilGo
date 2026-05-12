# =========================================================
# OPTIMIZADOR INTELIGENTE PRO ENTERPRISE - FULL SYSTEM
# + PROGRAMADOR + PARAMETRIZADOR + ABORDAJE
# + AUDITORÍA + EDITOR + GITHUB
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

MAX_AB_T1 = 10
MAX_AB_T2 = 10

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
        repo.update_file("empleados.xlsx", "update", data, file.sha)
    except:
        repo.create_file("empleados.xlsx", "create", data)


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
# AUDITORÍA (PROGRAMADOR)
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
# PARAMETRIZADOR TECNICOS + ABORDAJE
# =========================================================

def pantalla_parametrizador():

    st.header("⚙️ Parametrizador de Grupos")

    df = cargar_empleados()

    if df is None:
        st.error("No se pudo cargar empleados.xlsx")
        return

    if "Cargo" not in df.columns or "Nombre" not in df.columns:
        st.error("Faltan columnas: Nombre y Cargo")
        return

    st.dataframe(df)

    if st.button("🚀 Asignar grupos"):

        # =========================
        # TECNICOS (4 GRUPOS)
        # =========================

        tecnicos = df[df["Cargo"].isin(["Master","Tecnico A","Tecnico B"])].sample(frac=1)

        masters = tecnicos[tecnicos["Cargo"]=="Master"]
        a = tecnicos[tecnicos["Cargo"]=="Tecnico A"]
        b = tecnicos[tecnicos["Cargo"]=="Tecnico B"]

        grupos = {f"Grupo {i+1}":[] for i in range(4)}

        for i in range(4):

            grupos[f"Grupo {i+1}"].extend(masters.iloc[i*2:(i+1)*2]["Nombre"].tolist())
            grupos[f"Grupo {i+1}"].extend(a.iloc[i*7:(i+1)*7]["Nombre"].tolist())
            grupos[f"Grupo {i+1}"].extend(b.iloc[i*3:(i+1)*3]["Nombre"].tolist())

        # =========================
        # ABORDAJE (5 GRUPOS)
        # =========================

        ab = df[df["Cargo"]=="Auxiliar de Abordaje y Atención al Público"].sample(frac=1)

        grupos_ab = {f"Abordaje {i+1}":[] for i in range(5)}

        for i,n in enumerate(ab["Nombre"]):
            grupos_ab[f"Abordaje {(i%5)+1}"].append(n)

        st.subheader("🧠 Técnicos")
        st.json(grupos)

        st.subheader("🚌 Abordaje")
        st.json(grupos_ab)

        df["GrupoAsignado"] = ""

        for g,lista in grupos.items():
            df.loc[df["Nombre"].isin(lista),"GrupoAsignado"] = g

        for g,lista in grupos_ab.items():
            df.loc[df["Nombre"].isin(lista),"GrupoAsignado"] = g

        guardar_empleados(df)

        st.success("Grupos asignados correctamente")

# =========================================================
# ABORDAJE (PROGRAMACIÓN TURNO SIMPLE)
# =========================================================

def pantalla_abordaje():

    st.header("🚌 Personal de Abordaje")

    df = cargar_empleados()

    if df is None:
        return

    ab = df[df["Cargo"]=="Auxiliar de Abordaje y Atención al Público "].copy()

    if len(ab) < 20:
        st.warning("Se recomienda mínimo 20 personas")

    inicio = st.date_input("Inicio", date.today())
    fin = st.date_input("Fin", date.today()+timedelta(days=30))

    descanso = st.selectbox("Día descanso", DIAS_ES, index=5)

    filas = []

    if st.button("🚀 Generar Abordaje"):

        for fecha in pd.date_range(inicio, fin):

            dia = DIAS_ES[fecha.weekday()]
            festivo = fecha.date() in festivos_co

            if dia == descanso:

                for _,r in ab.iterrows():
                    filas.append({
                        "Fecha":fecha,
                        "Nombre":r["Nombre"],
                        "Turno":"DESCANSO",
                        "Festivo":"SI" if festivo else "NO"
                    })
                continue

            pool = ab.sample(frac=1)

            t1 = 0
            t2 = 0

            for _,r in pool.iterrows():

                if t1 < MAX_AB_T1:
                    turno = "T1"
                    t1 += 1
                else:
                    turno = "T2"
                    t2 += 1

                filas.append({
                    "Fecha":fecha,
                    "Nombre":r["Nombre"],
                    "Turno":turno,
                    "Festivo":"SI" if festivo else "NO"
                })

        df_ab = pd.DataFrame(filas)

        st.session_state["abordaje"] = df_ab
        guardar_github(df_ab)

        st.success("Abordaje generado")

    if "abordaje" in st.session_state:

        st.subheader("📊 Vista Abordaje")

        st.data_editor(
            st.session_state["abordaje"].pivot(index="Nombre", columns="Fecha", values="Turno"),
            use_container_width=True
        )

# =========================================================
# GENERADOR PROGRAMADOR (COMPLETO)
# =========================================================

def generar_malla():

    st.header("🚀 Programador Inteligente")

    c1,c2 = st.columns(2)

    inicio = c1.date_input("Inicio", date.today())
    fin = c2.date_input("Fin", date.today()+timedelta(days=30))

    descanso = {}
    cols = st.columns(len(GRUPOS))

    for i,g in enumerate(GRUPOS):
        descanso[g] = cols[i].selectbox(g, DIAS_ES, index=i)

    carga = {g:0 for g in GRUPOS}
    conteo = {g:{"T1":0,"T2":0,"T3":0} for g in GRUPOS}

    last = {g:None for g in GRUPOS}
    streak = {g:0 for g in GRUPOS}

    filas = []

    if st.button("🚀 Generar"):

        for fecha in pd.date_range(inicio, fin):

            dia = DIAS_ES[fecha.weekday()]
            festivo = fecha.date() in festivos_co

            descanso_dia = [g for g in GRUPOS if descanso[g]==dia]
            activos = [g for g in GRUPOS if g not in descanso_dia]

            asignados = {}

            for g in descanso_dia:
                asignados[g]="DESCANSO"

            for turno in ["T1","T2","T3"]:

                def score(g):
                    base = carga[g]+conteo[g][turno]
                    if last[g]!=turno:
                        base += 1000 if streak[g]<4 else 10
                    return base

                sel = sorted(activos,key=score)[0]

                asignados[sel]=turno
                carga[sel]+=1
                conteo[sel][turno]+=1

                last[sel]=turno
                streak[sel]=streak[sel]+1 if last[sel]==turno else 1

                activos.remove(sel)

            for g in activos:
                asignados[g]="T1 APOYO"

            for g in GRUPOS:
                filas.append({
                    "Fecha":fecha,
                    "Grupo":g,
                    "Turno":asignados[g],
                    "Día":dia,
                    "Festivo":"SI" if festivo else "NO"
                })

        df = pd.DataFrame(filas)
        st.session_state["malla"]=df
        guardar_github(df)

# =========================================================
# INTERFAZ PRINCIPAL
# =========================================================

def pantalla_programador():

    op = st.radio(
        "Módulo",
        ["Programador","Parametrizador","Personal de Abordaje"],
        horizontal=True
    )

    if op=="Parametrizador":
        pantalla_parametrizador()
        return

    if op=="Personal de Abordaje":
        pantalla_abordaje()
        return

    generar_malla()

    if "malla" not in st.session_state:
        return

    df = st.session_state["malla"]

    st.subheader("📊 MALLA EDITABLE")

    pivot = df.pivot(index="Grupo", columns="Fecha", values="Turno")

    edit = st.data_editor(pivot, use_container_width=True)

    if st.button("💾 Guardar cambios"):

        df2 = edit.reset_index().melt(
            id_vars="Grupo",
            var_name="Fecha",
            value_name="Turno"
        )

        st.session_state["malla"]=df2
        guardar_github(df2)

        st.success("Guardado")

    st.subheader("🚨 Auditoría")

    errores,cobertura = auditoria(df)

    for e in errores[:10]:
        st.error(e)

    st.line_chart(cobertura)
