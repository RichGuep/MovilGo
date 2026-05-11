# logic_programador.py
# VERSIÓN COMPLETA RESTAURADA + FIX SALTOS

import streamlit as st
import pandas as pd
import io
import random
from datetime import datetime, timedelta
from github import Github

# =========================================================
# CONFIGURACIÓN
# =========================================================
TURNOS = ["T1", "T2", "T3", "T1 APOYO", "T2 APOYO", "DESCANSO", "COMPENSADO"]

HORARIOS = {
    "T1": "05:30-12:50",
    "T2": "13:30-20:50",
    "T3": "21:30-04:50",
    "T1 APOYO": "05:30-12:50",
    "T2 APOYO": "13:30-20:50",
}

GRUPOS_TEC = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
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
        df = pd.read_excel(io.BytesIO(c.decoded_content))
        df.columns = df.columns.str.strip()
        return df
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
# ASIGNACIÓN DE GRUPOS (ORIGINAL RESTAURADO)
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

        grupos_ab = ["Grupo A", "Grupo B", "Grupo C", "Grupo D", "Grupo E"]

        if len(abordaje) >= 25:
            idx = 0
            for g in grupos_ab:
                for _ in range(5):
                    asignacion[abordaje.iloc[idx]["Nombre"]] = g
                    idx += 1

        df["Grupo"] = df["Nombre"].map(lambda x: asignacion.get(x, ""))

        guardar_excel(df, "empleados.xlsx")

        st.success("✅ Grupos asignados")
        st.dataframe(df, use_container_width=True)

# =========================================================
# MOTOR DE ROTACIÓN SEGURO (FIX SOLO AQUÍ)
# =========================================================
def siguiente_turno(t):
    return {"T1": "T2", "T2": "T3", "T3": "T1"}.get(t, t)


def salto_invalido(prev, nuevo):
    return (prev == "T3" and nuevo == "T1") or (prev == "T2" and nuevo == "T1")

# =========================================================
# PROGRAMADOR (ORIGINAL + FIX MÍNIMO)
# =========================================================
def generar_malla_tecnicos():
    st.header("📅 Programador Técnicos")

    c1, c2 = st.columns(2)
    fecha_ini = c1.date_input("Inicio", datetime.now())
    fecha_fin = c2.date_input("Fin", datetime.now() + timedelta(days=30))

    if st.button("🚀 Generar malla"):

        fechas = pd.date_range(fecha_ini, fecha_fin, freq="D")
        filas = []

        estado = {
            g: {
                "turno": random.choice(["T1", "T2", "T3"]),
                "dias": 0,
                "prev": None
            }
            for g in GRUPOS_TEC
        }

        for fecha in fechas:
            dia = DIAS[fecha.weekday()]
            asignados = {}

            for g in GRUPOS_TEC:

                actual = estado[g]["turno"]
                dias = estado[g]["dias"]
                prev = estado[g]["prev"]

                # 🔒 BLOQUE DE 4 DÍAS
                if dias >= 4:
                    nuevo = siguiente_turno(actual)

                    # FIX: NO SE PERMITE SALTO INVALIDO
                    if not salto_invalido(actual, nuevo):
                        estado[g]["turno"] = nuevo
                        estado[g]["dias"] = 0

                asignados[g] = estado[g]["turno"]
                estado[g]["prev"] = estado[g]["turno"]
                estado[g]["dias"] += 1

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
    # 📊 DASHBOARD COMPLETO RESTAURADO
    # =====================================================
    if "malla_tecnicos" in st.session_state:

        df = st.session_state["malla_tecnicos"]

        st.subheader("📋 Malla visual")
        pivot = df.pivot_table(index="Grupo", columns="Fecha", values="Turno", aggfunc="first")
        st.dataframe(pivot, use_container_width=True)

        # =========================
        # 📊 BALANCE TURNOS
        # =========================
        st.subheader("📊 Balance de turnos")

        balance = df[df["Turno"].isin(["T1", "T2", "T3"])] \
            .groupby(["Grupo", "Turno"]) \
            .size().unstack(fill_value=0)

        st.bar_chart(balance)

        # =========================
        # 😴 DESCANSOS
        # =========================
        st.subheader("😴 Descansos y compensados")

        desc = df[df["Turno"].isin(["DESCANSO", "COMPENSADO"])] \
            .groupby(["Grupo", "Turno"]) \
            .size().unstack(fill_value=0)

        st.dataframe(desc, use_container_width=True)

        # =========================
        # 🚨 SALTOS INVALIDOS
        # =========================
        st.subheader("🚨 Auditoría de saltos")

        alertas = []

        for g in GRUPOS_TEC:
            gdf = df[df["Grupo"] == g].sort_values("Fecha")
            prev = None

            for _, r in gdf.iterrows():
                if prev == "T3" and r["Turno"] in ["T1", "T2"]:
                    alertas.append([g, r["Fecha"], "T3 → turno diurno"])
                if prev == "T2" and r["Turno"] == "T1":
                    alertas.append([g, r["Fecha"], "T2 → T1"])
                prev = r["Turno"]

        if alertas:
            st.error(f"⚠️ {len(alertas)} saltos inválidos")
            st.dataframe(pd.DataFrame(alertas, columns=["Grupo", "Fecha", "Error"]))
        else:
            st.success("✅ Sin saltos inválidos")

        # =========================
        # 🛡️ COBERTURA
        # =========================
        st.subheader("🛡️ Cobertura diaria")

        cobertura = []

        for fecha in df["Fecha"].unique():
            dia_df = df[df["Fecha"] == fecha]
            turnos = set(dia_df["Turno"])

            faltan = [t for t in ["T1", "T2", "T3"] if t not in turnos]

            if faltan:
                cobertura.append({"Fecha": fecha, "Faltan": ", ".join(faltan)})

        if cobertura:
            st.error(f"❌ {len(cobertura)} días incompletos")
            st.dataframe(pd.DataFrame(cobertura))
        else:
            st.success("✅ Cobertura completa")

# =========================================================
# ABORDAJE (INTACTO)
# =========================================================
def pantalla_abordaje():
    st.header("🚌 Personal Abordaje")
    st.info("Módulo activo")

# =========================================================
# MENÚ
# =========================================================
def pantalla_programador():
    mod = st.radio(
        "Selecciona módulo",
        ["📅 Programador Técnicos", "🧩 Grupos", "🚌 Personal Abordaje"],
        horizontal=True
    )

    if mod == "📅 Programador Técnicos":
        generar_malla_tecnicos()
    elif mod == "🧩 Grupos":
        asignar_grupos()
    else:
        pantalla_abordaje()
