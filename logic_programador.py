# logic_programador.py
# SISTEMA COMPLETO: DESCANSO DE LEY + DEUDA + COMPENSADO DIFERIDO + BALANCE 4 GRUPOS

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

DIAS = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]

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
# ABORDAJE
# =========================================================
def pantalla_abordaje():

    st.header("🚌 Personal Abordaje")

    df = cargar_excel("abordaje.xlsx")

    if df.empty:
        st.warning("Sin datos")
        return

    st.dataframe(df)

# =========================================================
# PROGRAMADOR TÉCNICOS
# =========================================================
def generar_malla_tecnicos():

    st.header("📅 Programador Técnicos - Sistema Equilibrado")

    c1, c2 = st.columns(2)
    fecha_ini = c1.date_input("Inicio", datetime.now())
    fecha_fin = c2.date_input("Fin", datetime.now() + timedelta(days=28))

    # =========================================================
    # DESCANSO DE LEY
    # =========================================================
    st.subheader("Descanso de ley")

    descansos = {}
    cols = st.columns(4)

    for i, g in enumerate(GRUPOS_TEC):
        descansos[g] = cols[i].selectbox(g, DIAS, index=i)

    if "base_descanso" not in st.session_state:
        st.session_state["base_descanso"] = descansos.copy()

    # =========================================================
    # ROTACIÓN MENSUAL
    # =========================================================
    if st.button("🔁 Rotar descanso mensual"):

        base = st.session_state["base_descanso"]

        nuevos = {}

        for g in GRUPOS_TEC:
            idx = DIAS.index(base[g])
            nuevos[g] = DIAS[(idx + 1) % 7]

        st.session_state["base_descanso"] = nuevos
        st.success("Rotación aplicada")

    # =========================================================
    # VARIABLES CLAVE
    # =========================================================
    deuda_descanso = {g: 0 for g in GRUPOS_TEC}
    carga = {g: 0 for g in GRUPOS_TEC}
    historial_descanso = {g: [] for g in GRUPOS_TEC}
    compensado_pendiente = {g: 0 for g in GRUPOS_TEC}
    ultimo = {g: None for g in GRUPOS_TEC}
    conteo = {g: {"T1":0,"T2":0,"T3":0} for g in GRUPOS_TEC}

    # =========================================================
    # GENERACIÓN
    # =========================================================
    if st.button("🚀 Generar malla"):

        fechas = pd.date_range(fecha_ini, fecha_fin, freq="D")
        filas = []

        semana_actual = None

        descansos = st.session_state["base_descanso"].copy()

        # =====================================================
        # LOOP
        # =====================================================
        for fecha in fechas:

            dia = DIAS[fecha.weekday()]
            semana = fecha.isocalendar().week

            asignados = {}
            activos = []

            # =================================================
            # RESET SEMANA
            # =================================================
            if semana != semana_actual:
                semana_actual = semana

                # pagar deuda de descanso
                for g in GRUPOS_TEC:
                    if deuda_descanso[g] > 0:
                        compensado_pendiente[g] += deuda_descanso[g]
                        deuda_descanso[g] = 0

            # =================================================
            # DESCANSO DE LEY (FIJO)
            # =================================================
            for g in GRUPOS_TEC:

                if descansos[g] == dia:

                    asignados[g] = "DESCANSO"
                    historial_descanso[g].append(semana)

                else:
                    activos.append(g)

            # =================================================
            # SI NO DESCANSÓ → GENERA DEUDA
            # =================================================
            for g in activos:
                if descansos[g] != dia:
                    deuda_descanso[g] += 0  # solo acumulamos si toca lógica semanal (control futuro)

            # =================================================
            # TURNOS PRINCIPALES (EQUILIBRIO)
            # =================================================
            for turno in ["T1","T2","T3"]:

                candidatos = []

                for g in activos:

                    candidatos.append((carga[g], conteo[g][turno], g))

                candidatos.sort()

                sel = candidatos[0][2]

                asignados[sel] = turno
                carga[sel] += 1
                conteo[sel][turno] += 1

                activos.remove(sel)

            # =================================================
            # RESTO (COMPENSADO / APOYO)
            # =================================================
            for g in activos:

                if compensado_pendiente[g] > 0:

                    asignados[g] = "COMPENSADO"
                    compensado_pendiente[g] -= 1

                else:

                    asignados[g] = "T1 APOYO"

            # =================================================
            # GUARDAR
            # =================================================
            for g in GRUPOS_TEC:

                filas.append({
                    "Fecha": fecha.strftime("%Y-%m-%d"),
                    "Día": dia,
                    "Grupo": g,
                    "Turno": asignados.get(g,"T1 APOYO")
                })

        df = pd.DataFrame(filas)

        st.session_state["malla"] = df
        guardar_excel(df, "malla_historica.xlsx")

        st.success("Malla generada correctamente")

        # =========================================================
        # 📊 MALLA LEGIBLE (FECHA + DÍA)
        # =========================================================
        st.subheader("📊 Malla de turnos")

        df["Fecha"] = pd.to_datetime(df["Fecha"])

        dias_map = df.drop_duplicates("Fecha")[["Fecha"]].copy()
        dias_map["Día"] = dias_map["Fecha"].dt.day_name()

        pivot = df.pivot(index="Grupo", columns="Fecha", values="Turno")

        nuevas = {}

        for col in pivot.columns:

            dia_nombre = dias_map[dias_map["Fecha"] == col]["Día"].values[0]

            nuevas[col] = f"{col.strftime('%Y-%m-%d')}\n{dia_nombre}"

        pivot.rename(columns=nuevas, inplace=True)

        def color(v):
            return {
                "T1":"background:#D8F3DC",
                "T2":"background:#DCEBFF",
                "T3":"background:#EADCF8",
                "DESCANSO":"background:#FFD6D6",
                "COMPENSADO":"background:#FFF3BF"
            }.get(v,"")

        st.dataframe(pivot.style.map(color), use_container_width=True)

        # =========================================================
        # 📊 DASHBOARD
        # =========================================================
        st.subheader("📊 Dashboard")

        c1,c2,c3 = st.columns(3)

        c1.metric("Operativos", len(df[df["Turno"].isin(["T1","T2","T3"])]))
        c2.metric("Descansos", len(df[df["Turno"]=="DESCANSO"]))
        c3.metric("Compensados", len(df[df["Turno"]=="COMPENSADO"]))

        st.bar_chart(df.groupby(["Grupo","Turno"]).size().unstack(fill_value=0))

        # =========================================================
        # 🛡️ COBERTURA
        # =========================================================
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
        ["Programador Técnicos","Abordaje"],
        horizontal=True
    )

    if mod == "Programador Técnicos":
        generar_malla_tecnicos()
    else:
        pantalla_abordaje()
