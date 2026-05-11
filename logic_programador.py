# logic_programador.py
# SISTEMA COMPLETO + MALLA + CALENDARIO PRO + AUDITORÍA + DESCANSO CORRECTO

import streamlit as st
import pandas as pd
import io
from datetime import datetime, timedelta
from github import Github

# =========================================================
# CONFIGURACIÓN
# =========================================================
TURNOS = ["T1", "T2", "T3", "T1 APOYO", "T2 APOYO", "DESCANSO", "COMPENSADO"]

GRUPOS_TEC = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
GRUPOS_AB = ["Grupo A", "Grupo B", "Grupo C", "Grupo D", "Grupo E"]

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

# =========================================================
# GITHUB
# =========================================================
def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            st.error("❌ Falta GITHUB_TOKEN")
            return None
        return Github(st.secrets["GITHUB_TOKEN"]).get_repo("RichGuep/movilgo")
    except Exception as e:
        st.error(f"GitHub error: {e}")
        return None


def cargar_excel(nombre):
    repo = conectar_github()
    if not repo:
        return pd.DataFrame()
    try:
        c = repo.get_contents(nombre)
        return pd.read_excel(io.BytesIO(c.decoded_content))
    except:
        return pd.DataFrame()


def guardar_excel(df, nombre):
    repo = conectar_github()
    if not repo:
        return

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    data = buffer.getvalue()

    try:
        c = repo.get_contents(nombre)
        repo.update_file(nombre, "update", data, c.sha)
    except:
        repo.create_file(nombre, "create", data)

# =========================================================
# GRUPOS
# =========================================================
def asignar_grupos():
    st.header("🧩 Asignación de grupos")

    df = cargar_excel("empleados.xlsx")
    if df.empty:
        st.warning("No hay empleados")
        return

    if "Grupo" not in df.columns:
        df["Grupo"] = ""

    st.dataframe(df)

    if st.button("Asignar grupos"):
        guardar_excel(df, "empleados.xlsx")
        st.success("OK")

# =========================================================
# ABORDAJE
# =========================================================
def pantalla_abordaje():
    st.header("🚌 Personal Abordaje")

    df = cargar_excel("abordaje.xlsx")

    if df.empty:
        st.warning("No hay datos")
        return

    st.dataframe(df, use_container_width=True)

# =========================================================
# CALENDARIO PRO (NUEVO)
# =========================================================
def vista_calendario_pro(df):

    st.subheader("📆 Vista calendario PRO (operativa por semanas)")

    df = df.copy()
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    df["Semana"] = df["Fecha"].dt.isocalendar().week
    df["Día"] = df["Fecha"].dt.day_name()

    calendario = df.pivot_table(
        index=["Grupo", "Semana"],
        columns="Fecha",
        values="Turno",
        aggfunc="first"
    )

    def color(val):
        return {
            "T1":"background:#D8F3DC;color:#1B4332;font-weight:bold",
            "T2":"background:#DCEBFF;color:#1D3557;font-weight:bold",
            "T3":"background:#EADCF8;color:#5A189A;font-weight:bold",
            "DESCANSO":"background:#FFD6D6;color:#9D0208;font-weight:bold",
            "COMPENSADO":"background:#FFF3BF;color:#7F5539;font-weight:bold",
            "T1 APOYO":"background:#FFF7ED",
            "T2 APOYO":"background:#FFF7ED"
        }.get(val, "")

    st.dataframe(calendario.style.map(color), use_container_width=True)

# =========================================================
# PROGRAMADOR TÉCNICOS
# =========================================================
def generar_malla_tecnicos():

    st.header("📅 Programador Técnicos")

    c1, c2 = st.columns(2)
    fecha_ini = c1.date_input("Inicio", datetime.now())
    fecha_fin = c2.date_input("Fin", datetime.now() + timedelta(days=30))

    # =========================================================
    # DESCANSO PARAMETRIZADO
    # =========================================================
    st.subheader("Descanso parametrizado")

    descansos = {}
    cols = st.columns(4)

    for i, g in enumerate(GRUPOS_TEC):
        descansos[g] = cols[i].selectbox(g, DIAS, index=i)

    if "descansos_base" not in st.session_state:
        st.session_state["descansos_base"] = descansos.copy()

    # =========================================================
    # ROTACIÓN MENSUAL
    # =========================================================
    if st.button("🔁 Rotar descansos mensualmente"):
        base = st.session_state["descansos_base"]

        nuevos = {}
        for g in GRUPOS_TEC:
            idx = DIAS.index(base[g])
            nuevos[g] = DIAS[(idx + 1) % 7]

        st.session_state["descansos_base"] = nuevos
        st.success("Rotación aplicada")

    # =========================================================
    # CONTROL SEMANAL
    # =========================================================
    descanso_semana = {g: 0 for g in GRUPOS_TEC}

    # =========================================================
    # GENERACIÓN
    # =========================================================
    if st.button("🚀 Generar malla"):

        fechas = pd.date_range(fecha_ini, fecha_fin, freq="D")
        filas = []

        bloque = {g: "T1" for g in GRUPOS_TEC}
        conteo = {g: {"T1":0,"T2":0,"T3":0} for g in GRUPOS_TEC}
        ultimo = {g: None for g in GRUPOS_TEC}

        descansos = st.session_state["descansos_base"].copy()

        offset = fecha_ini.month - 1
        for g in GRUPOS_TEC:
            idx = DIAS.index(descansos[g])
            descansos[g] = DIAS[(idx + offset) % 7]

        # =====================================================
        # LOOP
        # =====================================================
        for fecha in fechas:

            dia = DIAS[fecha.weekday()]
            asignados = {}

            if fecha.weekday() == 0:
                descanso_semana = {g: 0 for g in GRUPOS_TEC}

            activos = []

            # =================================================
            # DESCANSO REAL (1 POR SEMANA)
            # =================================================
            for g in GRUPOS_TEC:

                if descansos[g] == dia and descanso_semana[g] < 1:
                    asignados[g] = "DESCANSO"
                    descanso_semana[g] += 1
                else:
                    activos.append(g)

            # =================================================
            # TURNOS
            # =================================================
            for turno in ["T1","T2","T3"]:

                candidatos = []

                for g in activos:

                    if ultimo[g] == "T3" and turno == "T1":
                        continue

                    candidatos.append((0 if bloque[g]==turno else 1,
                                       conteo[g][turno],
                                       g))

                if not candidatos:
                    candidatos = [(1,0,g) for g in activos]

                candidatos.sort()
                sel = candidatos[0][2]

                asignados[sel] = turno
                ultimo[sel] = turno
                conteo[sel][turno] += 1

                activos.remove(sel)

            # =================================================
            # COMPENSADOS CORREGIDOS
            # =================================================
            for g in activos:

                if descansos[g] != dia:
                    asignados[g] = "T1 APOYO" if conteo[g]["T1"] <= conteo[g]["T2"] else "T2 APOYO"
                else:
                    asignados[g] = "COMPENSADO"

            # =================================================
            # GUARDAR
            # =================================================
            for g in GRUPOS_TEC:

                filas.append({
                    "Fecha": fecha.strftime("%Y-%m-%d"),
                    "Día": dia,
                    "Grupo": g,
                    "Turno": asignados[g]
                })

        df = pd.DataFrame(filas)

        st.session_state["malla_tecnicos"] = df
        guardar_excel(df, "malla_historica.xlsx")

        st.success("Malla generada")

        # =====================================================
        # 📊 MALLA
        # =====================================================
        st.subheader("📊 Malla de turnos")

        pivot = df.pivot(index="Grupo", columns="Fecha", values="Turno")

        def color(v):
            return {
                "T1":"background:#D8F3DC",
                "T2":"background:#DCEBFF",
                "T3":"background:#EADCF8",
                "DESCANSO":"background:#FFD6D6",
                "COMPENSADO":"background:#FFF3BF"
            }.get(v,"")

        st.dataframe(pivot.style.map(color), use_container_width=True)

        # =====================================================
        # 📆 CALENDARIO PRO
        # =====================================================
        vista_calendario_pro(df)

        # =====================================================
        # 📊 DASHBOARD
        # =====================================================
        st.subheader("📊 Dashboard")

        c1,c2,c3 = st.columns(3)

        c1.metric("Operativos", len(df[df["Turno"].isin(["T1","T2","T3"])]))
        c2.metric("Descansos", len(df[df["Turno"]=="DESCANSO"]))
        c3.metric("Compensados", len(df[df["Turno"]=="COMPENSADO"]))

        st.bar_chart(df.groupby(["Grupo","Turno"]).size().unstack(fill_value=0))

        # =====================================================
        # 🛡️ COBERTURA
        # =====================================================
        st.subheader("🛡️ Cobertura T1/T2/T3")

        cobertura = []

        for f in df["Fecha"].unique():

            d = df[df["Fecha"]==f]
            ts = set(d["Turno"])

            cobertura.append({
                "Fecha": f,
                "Completo": all(x in ts for x in ["T1","T2","T3"])
            })

        cov = pd.DataFrame(cobertura)

        st.metric("Días completos", cov["Completo"].sum())
        st.metric("Días incompletos", len(cov[cov["Completo"]==False]))

# =========================================================
# MENÚ
# =========================================================
def pantalla_programador():

    mod = st.radio(
        "Módulo",
        ["Programador Técnicos","Grupos","Abordaje"],
        horizontal=True
    )

    if mod == "Programador Técnicos":
        generar_malla_tecnicos()
    elif mod == "Grupos":
        asignar_grupos()
    else:
        pantalla_abordaje()
