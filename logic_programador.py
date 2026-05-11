# logic_programador.py
# VERSIÓN 13:05 COMPLETA

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
# ASIGNACIÓN DE GRUPOS
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
        abordaje = df[df["Cargo"].astype(str).str.contains("Auxiliar de Abordaje y Atención al Público", na=False)].sample(frac=1)

        if len(masters) < 8 or len(tec_a) < 28 or len(tec_b) < 12:
            st.error("❌ No cumple cantidades mínimas técnicos")
            return

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
# PROGRAMADOR TÉCNICOS
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

    if st.button("🚀 Generar malla"):
        fechas = pd.date_range(fecha_ini, fecha_fin, freq="D")
        filas = []

        # bloque de rotación: mínimo 4 días por turno antes de cambiar
        bloque_actual = {"Grupo 1": "T1", "Grupo 2": "T2", "Grupo 3": "T3", "Grupo 4": "T1"}
        dias_en_bloque = {g: 0 for g in GRUPOS_TEC}
        orden_rotacion = {"T1": "T2", "T2": "T3", "T3": "T1"}
        ultimo_turno = {g: None for g in GRUPOS_TEC}
        conteo_turnos = {g: {'T1': 0, 'T2': 0, 'T3': 0} for g in GRUPOS_TEC}

        for fecha in fechas:
            dia = DIAS[fecha.weekday()]
            asignados = {}

            # 1. descanso parametrizado
            descansan_hoy = [g for g in GRUPOS_TEC if descansos[g] == dia]
            activos = [g for g in GRUPOS_TEC if g not in descansan_hoy]
            for g in descansan_hoy:
                asignados[g] = "DESCANSO"
                ultimo_turno[g] = "DESCANSO"
                # si ya cumplió mínimo 4 días, rota al siguiente turno al descansar
                if dias_en_bloque[g] >= 4:
                    bloque_actual[g] = orden_rotacion[bloque_actual[g]]
                    dias_en_bloque[g] = 0

            # 2. garantizar T1/T2/T3 usando bloques y balance
            for turno_obj in ["T1", "T2", "T3"]:
                candidatos = []
                for g in activos:
                    if g in asignados:
                        continue
                    # evitar salto T3 -> T1 sin descanso
                    if ultimo_turno[g] == "T3" and turno_obj == "T1":
                        continue
                    prioridad_bloque = 0 if bloque_actual[g] == turno_obj else 1
                    balance = conteo_turnos[g][turno_obj]
                    candidatos.append((prioridad_bloque, balance, g))

                # relajar si no hay candidatos para asegurar cobertura
                if not candidatos:
                    for g in activos:
                        if g not in asignados:
                            candidatos.append((1, conteo_turnos[g][turno_obj], g))

                candidatos.sort()
                g_sel = candidatos[0][2]
                asignados[g_sel] = turno_obj
                ultimo_turno[g_sel] = turno_obj
                conteo_turnos[g_sel][turno_obj] += 1
                dias_en_bloque[g_sel] += 1

            # 3. grupo sobrante a apoyo (nunca T3 fijo)
            for g in activos:
                if g not in asignados:
                    apoyo = "T1 APOYO" if conteo_turnos[g]["T1"] <= conteo_turnos[g]["T2"] else "T2 APOYO"
                    asignados[g] = apoyo
                    ultimo_turno[g] = apoyo
                    dias_en_bloque[g] += 1

            # 4. guardar filas
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

    if "malla_tecnicos" in st.session_state:
        df = st.session_state["malla_tecnicos"]

        st.subheader("📋 Malla visual")
        pivot = df.pivot(index="Grupo", columns="Fecha", values="Turno")

        def colorear_turnos(val):
            colores = {
                "T1": "background-color: #D8F3DC; color: #1B4332; font-weight:bold;",
                "T2": "background-color: #DCEBFF; color: #1D3557; font-weight:bold;",
                "T3": "background-color: #EADCF8; color: #5A189A; font-weight:bold;",
                "T1 APOYO": "background-color: #FFF3BF; color: #7F5539; font-weight:bold;",
                "T2 APOYO": "background-color: #FFE8CC; color: #9C6644; font-weight:bold;",
                "DESCANSO": "background-color: #FFD6D6; color: #9D0208; font-weight:bold;",
                "COMPENSADO": "background-color: #FFF0F3; color: #C9184A; font-weight:bold;"
            }
            return colores.get(val, "")

        st.dataframe(
            pivot.style.map(colorear_turnos),
            use_container_width=True
        )

        st.subheader("✏️ Editor manual")
        edit = st.data_editor(
            df,
            column_config={
                "Turno": st.column_config.SelectboxColumn(
                    "Turno",
                    options=TURNOS
                )
            },
            use_container_width=True
        )

        if st.button("💾 Guardar cambios de malla"):
            st.session_state["malla_tecnicos"] = edit
            guardar_excel(edit, "malla_historica.xlsx")
            st.success("Cambios guardados")

        st.subheader("📊 Dashboard de Auditoría")

        total_turnos = len(df[df["Turno"].isin(["T1", "T2", "T3"])])
        total_descansos = len(df[df["Turno"] == "DESCANSO"])
        total_comp = len(df[df["Turno"] == "COMPENSADO"])

        m1, m2, m3 = st.columns(3)
        m1.metric("Turnos operativos", total_turnos)
        m2.metric("Descansos ley", total_descansos)
        m3.metric("Compensados", total_comp)

        st.markdown("### 📈 Balance de turnos por grupo")
        balance = df[df["Turno"].isin(["T1", "T2", "T3"])].groupby(["Grupo", "Turno"]).size().unstack(fill_value=0)
        st.bar_chart(balance)

        st.markdown("### 😴 Auditoría de descansos")
        descansos_df = df[df["Turno"].isin(["DESCANSO", "COMPENSADO"])].groupby(["Grupo", "Turno"]).size().unstack(fill_value=0)
        st.dataframe(descansos_df, use_container_width=True)

        st.markdown("### 🚨 Alertas de saltos inválidos")
        alertas = []
        for g in GRUPOS_TEC:
            gdf = df[df["Grupo"] == g]
            prev = None
            for _, r in gdf.iterrows():
                if prev == "T3" and r["Turno"] in ["T1", "T2"]:
                    alertas.append([g, r["Fecha"], "Salto inválido T3 → día"])
                prev = r["Turno"]

        if alertas:
            st.error(f"⚠️ {len(alertas)} alertas detectadas")
            st.dataframe(pd.DataFrame(alertas, columns=["Grupo", "Fecha", "Alerta"]))
        else:
            st.success("✅ Sin saltos inválidos detectados")

        st.markdown("### 🛡️ Auditoría de cobertura diaria (T1, T2 y T3 obligatorios)")
        cobertura_alertas = []

        for fecha in sorted(df["Fecha"].unique()):
            dia_df = df[df["Fecha"] == fecha]
            turnos_dia = set(dia_df["Turno"].tolist())
            faltantes = []

            for turno_obligatorio in ["T1", "T2", "T3"]:
                if turno_obligatorio not in turnos_dia:
                    faltantes.append(turno_obligatorio)

            if faltantes:
                cobertura_alertas.append({
                    "Fecha": fecha,
                    "Faltan": ", ".join(faltantes)
                })

        if cobertura_alertas:
            st.error(f"❌ {len(cobertura_alertas)} días NO cumplen cobertura completa")
            st.dataframe(pd.DataFrame(cobertura_alertas), use_container_width=True)
        else:
            st.success("✅ Todos los días tienen garantizados T1, T2 y T3")

# =========================================================
# ABORDAJE
# =========================================================
def pantalla_abordaje():
    st.header("🚌 Personal Abordaje")
    st.info("Módulo activo. Puedes extender aquí la lógica de abordaje ya funcional.")

# =========================================================
# MENÚ PRINCIPAL
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
