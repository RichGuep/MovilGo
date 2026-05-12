# logic_programador.py
# =========================================================
# OPTIMIZADOR INTELIGENTE PRO - VERSION CONSOLIDADA
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


def guardar_github(df, nombre):

    repo = conectar_github()
    if not repo:
        return

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    data = buffer.getvalue()

    try:
        file = repo.get_contents(nombre)
        repo.update_file(nombre, "update malla", data, file.sha)
    except:
        repo.create_file(nombre, "create malla", data)

# =========================================================
# COLORES SUAVES
# =========================================================
def color_cell(v):

    return {
        "T1": "background-color:#D6EAF8;color:#1B4F72;",
        "T2": "background-color:#D5F5E3;color:#145A32;",
        "T3": "background-color:#FADBD8;color:#7B241C;",

        "T1 APOYO": "background-color:#EBF5FB;",
        "T2 APOYO": "background-color:#EAF2F8;",

        "DESCANSO": "background-color:#2C3E50;color:#F9E79F;font-weight:700;",

        "COMPENSADO": "background-color:#FDEBD0;color:#7E5109;font-weight:700;"
    }.get(v, "")

# =========================================================
# PARAMETRIZADOR
# =========================================================
def parametrizador():

    st.header("🧩 Parametrizador de grupos")

    df = pd.DataFrame({
        "Empleado": ["A","B","C","D"],
        "Grupo": ["","","",""]
    })

    st.dataframe(df)

# =========================================================
# VALIDACIONES
# =========================================================
def validar_saltos(prev, actual):

    if prev == "T3" and actual in ["T1","T2"]:
        return True

    if prev == "T2" and actual == "T1":
        return True

    return False

# =========================================================
# GENERADOR
# =========================================================
def generar_malla():

    st.header("🚀 OPTIMIZADOR PRO ENTERPRISE")

    c1,c2 = st.columns(2)

    inicio = c1.date_input("Inicio", date.today())
    fin = c2.date_input("Fin", date.today()+timedelta(days=30))

    st.session_state["inicio"] = inicio
    st.session_state["fin"] = fin

    # =====================================================
    # DESCANSO
    # =====================================================
    st.subheader("Descanso de ley")

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

    filas = []

    # =====================================================
    # GENERAR
    # =====================================================
    if st.button("Generar malla"):

        fechas = pd.date_range(inicio, fin)

        for fecha in fechas:

            dia = DIAS_ES[fecha.weekday()]
            festivo = fecha.date() in festivos_co

            asignados = {}

            descanso_grp = [g for g in GRUPOS if descanso[g]==dia]
            activos = [g for g in GRUPOS if g not in descanso_grp]

            # asegurar cobertura
            while len(activos) < 3:
                g = sorted(descanso_grp, key=lambda x:carga[x])[0]
                descanso_grp.remove(g)
                activos.append(g)
                compensado[g]+=1

            # DESCANSO
            for g in descanso_grp:
                asignados[g]="DESCANSO"

            # TURNOS PRINCIPALES (SIN HUECOS)
            orden_turnos = ["T1","T2","T3"]

            for i,turno in enumerate(orden_turnos):

                sel = sorted(activos, key=lambda g:(carga[g], conteo[g][turno]))[0]

                asignados[sel]=turno
                carga[sel]+=1
                conteo[sel][turno]+=1
                activos.remove(sel)

            # COMPENSADOS
            for g in GRUPOS:
                if compensado[g]>0 and g not in asignados:
                    asignados[g]="COMPENSADO"
                    compensado[g]-=1

            # APOYO CON REGLA ANTI-SALTOS
            for g in GRUPOS:

                if g not in asignados:

                    if conteo[g]["T3"] > 0:
                        asignados[g]="T2 APOYO"
                    elif conteo[g]["T2"] > conteo[g]["T1"]:
                        asignados[g]="T2 APOYO"
                    else:
                        asignados[g]="T1 APOYO"

            # GUARDAR
            for g in GRUPOS:

                filas.append({
                    "Fecha": fecha,
                    "Día": dia,
                    "Grupo": g,
                    "Turno": asignados[g],
                    "Festivo": "SI" if festivo else "NO"
                })

        df = pd.DataFrame(filas)
        st.session_state["malla"]=df

        guardar_github(df,"malla_historica.xlsx")

        st.success("Malla generada y guardada")

    # =====================================================
    # VISUALIZACIÓN (UNA SOLA MALLA)
    # =====================================================
    if "malla" in st.session_state:

        df = st.session_state["malla"]

        st.subheader("📊 Malla horizontal")

        pivot = df.pivot(index="Grupo",columns="Fecha",values="Turno")

        rename = {}
        for c in pivot.columns:
            rename[c]=f"{c.strftime('%d-%m')}\n{DIAS_ES[c.weekday()]}"

        pivot.rename(columns=rename,inplace=True)

        st.dataframe(
            pivot.style.map(color_cell),
            use_container_width=True
        )

        # =================================================
        # DASHBOARD
        # =================================================
        st.subheader("📊 Cobertura diaria")

        cov = df[df["Turno"].isin(["T1","T2","T3"])].groupby("Fecha").size()

        st.line_chart(cov)

        # =================================================
        # AUDITORÍA
        # =================================================
        st.subheader("🚨 Auditoría de sistema")

        errores = []

        for g in GRUPOS:

            prev = None
            gdf = df[df["Grupo"]==g]

            for _,r in gdf.iterrows():

                if prev and validar_saltos(prev, r["Turno"]):
                    errores.append(f"{g} salto {prev} → {r['Turno']} ({r['Fecha']})")

                prev = r["Turno"]

        if errores:
            st.error("Saltos detectados")
            st.write(errores)
        else:
            st.success("Sin saltos indebidos")

# =========================================================
# MENU
# =========================================================
def pantalla_programador():

    op = st.radio("Módulo",["Programador","Parametrizador"],horizontal=True)

    if op=="Programador":
        generar_malla()
    else:
        parametrizador()
