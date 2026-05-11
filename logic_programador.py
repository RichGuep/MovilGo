# logic_programador.py
# VERSIÓN COMPLETA + AUDITORÍA + DASHBOARD + DESCANSO FLEXIBLE

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
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    data = output.getvalue()

    try:
        c = repo.get_contents(nombre)
        repo.update_file(nombre, "update", data, c.sha)
    except:
        repo.create_file(nombre, "create", data)

# =========================================================
# GRUPOS
# =========================================================
def asignar_grupos():
    st.header("🧩 Asignación automática de grupos")

    df = cargar_excel("empleados.xlsx")
    if df.empty:
        st.warning("No hay empleados")
        return

    if "Grupo" not in df.columns:
        df["Grupo"] = ""

    st.dataframe(df, use_container_width=True)

    if st.button("🚀 Asignar grupos automáticamente"):
        asignacion = {}

        masters = df[df["Cargo"] == "Master"].sample(frac=1)
        tec_a = df[df["Cargo"] == "Tecnico A"].sample(frac=1)
        tec_b = df[df["Cargo"] == "Tecnico B"].sample(frac=1)
        abordaje = df[df["Cargo"].astype(str).str.contains("Auxiliar de Abordaje", na=False)].sample(frac=1)

        idx = 0
        for g in GRUPOS_TEC:
            for _ in range(2):
                asignacion[masters.iloc[idx]["Nombre"]] = g
                idx += 1

        idx = 0
        for g in GRUPOS_TEC:
            for _ in range(7):
                asignacion[tec_a.iloc[idx]["Nombre"]] = g
                idx += 1

        idx = 0
        for g in GRUPOS_TEC:
            for _ in range(3):
                asignacion[tec_b.iloc[idx]["Nombre"]] = g
                idx += 1

        if len(abordaje) >= 25:
            idx = 0
            for g in GRUPOS_AB:
                for _ in range(5):
                    asignacion[abordaje.iloc[idx]["Nombre"]] = g
                    idx += 1

        df["Grupo"] = df["Nombre"].map(lambda x: asignacion.get(x, ""))
        guardar_excel(df, "empleados.xlsx")

        st.success("✅ Grupos asignados")
        st.dataframe(df)

# =========================================================
# PROGRAMADOR
# =========================================================
def generar_malla_tecnicos():
    st.header("📅 Programador Técnicos")

    c1, c2 = st.columns(2)
    fecha_ini = c1.date_input("Inicio", datetime.now())
    fecha_fin = c2.date_input("Fin", datetime.now() + timedelta(days=30))

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
            nuevos[g] = DIAS[(idx + 1) % len(DIAS)]

        st.session_state["descansos_base"] = nuevos
        st.success("✅ Rotación aplicada")

    # =========================================================
    # MÉTRICAS DESCANSO
    # =========================================================
    DESCANSO_OBJETIVO = 2
    descanso_real_mes = {g: 0 for g in GRUPOS_TEC}

    # =========================================================
    # GENERACIÓN
    # =========================================================
    if st.button("🚀 Generar malla"):

        fechas = pd.date_range(fecha_ini, fecha_fin, freq="D")
        filas = []

        bloque = {g: "T1" for g in GRUPOS_TEC}
        dias_bloque = {g: 0 for g in GRUPOS_TEC}
        ultimo = {g: None for g in GRUPOS_TEC}
        conteo = {g: {"T1": 0, "T2": 0, "T3": 0} for g in GRUPOS_TEC}

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

            descansan = []
            activos = []

            # DESCANSO FLEXIBLE
            for g in GRUPOS_TEC:
                if descansos[g] == dia and descanso_real_mes[g] < DESCANSO_OBJETIVO:
                    asignados[g] = "DESCANSO"
                    descanso_real_mes[g] += 1
                else:
                    activos.append(g)

            # =================================================
            # TURNO BASE
            # =================================================
            for turno in ["T1", "T2", "T3"]:
                candidatos = []

                for g in activos:
                    if ultimo[g] == "T3" and turno == "T1":
                        continue

                    candidatos.append((0 if bloque[g] == turno else 1,
                                       conteo[g][turno],
                                       g))

                if not candidatos:
                    candidatos = [(1, 0, g) for g in activos]

                candidatos.sort()
                sel = candidatos[0][2]

                asignados[sel] = turno
                ultimo[sel] = turno
                conteo[sel][turno] += 1
                dias_bloque[sel] += 1
                activos.remove(sel)

            # =================================================
            # COMPENSADOS
            # =================================================
            for g in activos:
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

        st.success("✅ Malla generada")

        # =====================================================
        # 📊 DASHBOARD + AUDITORÍA
        # =====================================================
        st.subheader("📊 Dashboard")

        m1, m2, m3 = st.columns(3)

        m1.metric("Turnos operativos", len(df[df["Turno"].isin(["T1","T2","T3"])]))
        m2.metric("Descansos", len(df[df["Turno"]=="DESCANSO"]))
        m3.metric("Compensados", len(df[df["Turno"]=="COMPENSADO"]))

        st.markdown("### 📈 Balance por grupo")
        st.bar_chart(df.groupby(["Grupo","Turno"]).size().unstack(fill_value=0))

        # =====================================================
        # 🚨 AUDITORÍA SALTOS
        # =====================================================
        st.markdown("### 🚨 Auditoría saltos inválidos")

        alertas = []

        for g in GRUPOS_TEC:
            gdf = df[df["Grupo"] == g]
            prev = None
            for _, r in gdf.iterrows():
                if prev == "T3" and r["Turno"] in ["T1","T2"]:
                    alertas.append([g, r["Fecha"], "Salto T3 → día"])
                prev = r["Turno"]

        if alertas:
            st.error(f"{len(alertas)} alertas")
            st.dataframe(pd.DataFrame(alertas, columns=["Grupo","Fecha","Error"]))
        else:
            st.success("Sin saltos inválidos")

        # =====================================================
        # 🛡️ COBERTURA
        # =====================================================
        st.markdown("### 🛡️ Cobertura diaria")

        faltas = []

        for f in df["Fecha"].unique():
            d = df[df["Fecha"] == f]
            turnos = set(d["Turno"])
            missing = [t for t in ["T1","T2","T3"] if t not in turnos]

            if missing:
                faltas.append([f, missing])

        if faltas:
            st.warning("Días incompletos")
            st.dataframe(pd.DataFrame(faltas, columns=["Fecha","Faltantes"]))
        else:
            st.success("Cobertura completa")

# =========================================================
# MENÚ
# =========================================================
def pantalla_programador():
    mod = st.radio("Módulo", ["Programador Técnicos","Grupos"], horizontal=True)

    if mod == "Programador Técnicos":
        generar_malla_tecnicos()
    else:
        asignar_grupos()
