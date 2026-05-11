# =========================================================
# logic_programador.py
# VERSIÓN BLINDADA DEFINITIVA (MOTOR DETERMINÍSTICO)
# =========================================================

import streamlit as st
import pandas as pd
import io
import random
from datetime import datetime, timedelta
from github import Github

# =========================================================
# CONFIG
# =========================================================
TURNOS_BASE = ["T1", "T2", "T3"]
TURNOS = ["T1", "T2", "T3", "T1 APOYO", "T2 APOYO", "DESCANSO", "COMPENSADO"]

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
# MOTOR BLINDADO (ESTADO ÚNICO)
# =========================================================
def siguiente_turno(t):
    return {"T1": "T2", "T2": "T3", "T3": "T1"}[t]


def salto_prohibido(prev, nuevo):
    return (prev == "T3" and nuevo == "T1") or (prev == "T2" and nuevo == "T1")


# =========================================================
# GENERADOR BLINDADO
# =========================================================
def generar_malla_tecnicos():

    st.header("🛡️ Programador Técnicos (MODO BLINDADO)")

    c1, c2 = st.columns(2)
    fecha_ini = c1.date_input("Inicio", datetime.now())
    fecha_fin = c2.date_input("Fin", datetime.now() + timedelta(days=30))

    if st.button("🚀 GENERAR MALLA BLINDADA"):

        fechas = pd.date_range(fecha_ini, fecha_fin, freq="D")

        # 🔥 estado único fuente de verdad
        estado = {
            g: {
                "turno": random.choice(TURNOS_BASE),
                "dias": 0,
                "prev": random.choice(TURNOS_BASE)
            }
            for g in GRUPOS_TEC
        }

        conteo = {
            g: {"T1": 0, "T2": 0, "T3": 0}
            for g in GRUPOS_TEC
        }

        filas = []

        for fecha in fechas:

            dia = DIAS[fecha.weekday()]
            asignados = {}

            # =====================================================
            # 🔁 ASIGNACIÓN BLINDADA POR GRUPO
            # =====================================================
            for g in GRUPOS_TEC:

                actual = estado[g]["turno"]
                prev = estado[g]["prev"]
                dias = estado[g]["dias"]

                # 🔁 rotación cada 4 días
                if dias >= 4:
                    candidato = siguiente_turno(actual)

                    # 🔒 bloqueo absoluto de saltos prohibidos
                    if not salto_prohibido(actual, candidato):
                        estado[g]["turno"] = candidato
                        estado[g]["dias"] = 0
                        actual = candidato

                # ⚖️ control de balance (evita sobreuso de un turno)
                opciones = ["T1", "T2", "T3"]
                opciones.sort(key=lambda x: conteo[g][x])

                elegido = None

                for op in opciones:
                    if not salto_prohibido(prev, op):
                        elegido = op
                        break

                if not elegido:
                    elegido = actual  # fallback seguro

                asignados[g] = elegido

                # actualizar estado único
                estado[g]["prev"] = elegido
                estado[g]["turno"] = elegido
                estado[g]["dias"] += 1
                conteo[g][elegido] += 1

            # =====================================================
            # GUARDAR
            # =====================================================
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

        st.success("✅ MALLA BLINDADA GENERADA")

# =========================================================
# DASHBOARD BLINDADO
# =========================================================
    if "malla_tecnicos" in st.session_state:

        df = st.session_state["malla_tecnicos"]

        st.subheader("📋 Malla")

        pivot = df.pivot_table(index="Grupo", columns="Fecha", values="Turno", aggfunc="first")
        st.dataframe(pivot, use_container_width=True)

        # =====================================================
        # 📊 BALANCE REAL
        # =====================================================
        st.subheader("⚖️ Balance de turnos")

        balance = df[df["Turno"].isin(["T1", "T2", "T3"])] \
            .groupby(["Grupo", "Turno"]) \
            .size().unstack(fill_value=0)

        st.bar_chart(balance)

        # =====================================================
        # 🚨 AUDITORÍA REAL DE SALTOS
        # =====================================================
        st.subheader("🚨 Auditoría de saltos")

        alertas = []

        for g in GRUPOS_TEC:
            gdf = df[df["Grupo"] == g].sort_values("Fecha")
            prev = None

            for _, r in gdf.iterrows():
                if prev == "T3" and r["Turno"] in ["T1", "T2"]:
                    alertas.append([g, r["Fecha"], "T3 → inválido"])
                if prev == "T2" and r["Turno"] == "T1":
                    alertas.append([g, r["Fecha"], "T2 → T1"])
                prev = r["Turno"]

        if alertas:
            st.error(f"⚠️ {len(alertas)} violaciones detectadas")
            st.dataframe(pd.DataFrame(alertas, columns=["Grupo", "Fecha", "Error"]))
        else:
            st.success("🟢 Sin violaciones de reglas")

        # =====================================================
        # 🛡️ COBERTURA
        # =====================================================
        st.subheader("🛡️ Cobertura diaria")

        cobertura = []

        for fecha in df["Fecha"].unique():
            dia_df = df[df["Fecha"] == fecha]
            turnos = set(dia_df["Turno"])

            faltan = [t for t in ["T1", "T2", "T3"] if t not in turnos]

            if faltan:
                cobertura.append({"Fecha": fecha, "Faltan": ", ".join(faltan)})

        if cobertura:
            st.error("❌ Días incompletos")
            st.dataframe(pd.DataFrame(cobertura))
        else:
            st.success("✅ Cobertura perfecta")

# =========================================================
# MENÚ
# =========================================================
def pantalla_programador():
    mod = st.radio(
        "Selecciona módulo",
        ["📅 Programador Técnicos"],
        horizontal=True
    )

    if mod == "📅 Programador Técnicos":
        generar_malla_tecnicos()
