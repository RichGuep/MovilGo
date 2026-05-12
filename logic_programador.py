import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date, time
import holidays
import io
from github import Github

# =========================================================
# 1. CONFIGURACIÓN, CONSTANTES Y ESTILOS
# =========================================================
DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
INICIALES = {"Lunes": "L", "Martes": "M", "Miércoles": "X", "Jueves": "J", "Viernes": "V", "Sábado": "S", "Domingo": "D"}
festivos_co = holidays.Colombia()

GRUPOS_TEC = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]

COLORES_MAP = {
    "T1": "#D6EAF8", "T2": "#D5F5E3", "T3": "#FADBD8",
    "RELEVO": "#E8DAEF", "DISPONIBLE": "#EAEDED",
    "T1 APOYO": "#EBF5FB", "DESCANSO": "#1B2631", "COMPENSADO": "#2E4053"
}

def style_malla(df_pivot):
    def apply_styles(val):
        key = val if val and str(val).strip() != "" else "DESCANSO"
        bg = COLORES_MAP.get(key, "#1B2631")
        txt = "white" if key in ["DESCANSO", "COMPENSADO"] else "#17202A"
        return f'background-color: {bg}; color: {txt}; font-weight: 700; border: 0.5px solid #D5DBDB'
    return df_pivot.style.map(apply_styles)

# =========================================================
# 2. CONECTIVIDAD Y FUNCIONES BASE
# =========================================================
def obtener_tipo_dia(fecha):
    if fecha in festivos_co: return "Festivo"
    return "Sábado" if fecha.weekday() == 5 else "Domingo" if fecha.weekday() == 6 else "Hábil"

def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets: return None
        return Github(st.secrets["GITHUB_TOKEN"]).get_repo("RichGuep/movilgo")
    except: return None

def cargar_excel(nombre_archivo):
    repo = conectar_github()
    if not repo: return pd.DataFrame()
    try:
        contents = repo.get_contents(nombre_archivo)
        return pd.read_excel(io.BytesIO(contents.decoded_content))
    except: return pd.DataFrame()

def guardar_github(df, nombre_archivo):
    repo = conectar_github()
    if not repo: return
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    try:
        file = repo.get_contents(nombre_archivo)
        repo.update_file(nombre_archivo, f"Update {datetime.now()}", buffer.getvalue(), file.sha)
        st.toast(f"✅ {nombre_archivo} sincronizado.")
    except:
        repo.create_file(nombre_archivo, "Create", buffer.getvalue())
        st.toast(f"🆕 {nombre_archivo} creado.")

# =========================================================
# 3. MOTORES DE GENERACIÓN CON REGLA DE COMPENSATORIOS
# =========================================================

def generar_malla_tecnicos(inicio, fin, descansos_config):
    filas = []
    # RASTREADOR DE DEUDA: Si trabajan en su día libre, se les debe 1 día.
    deudas = {g: 0 for g in GRUPOS_TEC}
    
    for fecha in pd.date_range(inicio, fin):
        dia_n = DIAS_ES[fecha.weekday()]; sem = fecha.isocalendar()[1]
        asig = {}
        
        # 1. Asignar COMPENSADOS (Prioridad L-V)
        if 0 <= fecha.weekday() <= 4:
            con_deuda = [g for g, v in deudas.items() if v > 0]
            if con_deuda:
                g_comp = sorted(con_deuda, key=lambda x: deudas[x], reverse=True)[0]
                asig[g_comp] = "COMPENSADO"
                deudas[g_comp] -= 1

        # 2. Asignar Descansos programados (Ley)
        for g, d_pref in descansos_config.items():
            if dia_n == d_pref and g not in asig:
                asig[g] = "DESCANSO"

        # 3. Llenar Turnos Operativos (Rotación T3, T2, T1)
        activos = [g for g in GRUPOS_TEC if g not in asig]
        off = sem % 4
        act_r = sorted(activos, key=lambda x: (GRUPOS_TEC.index(x) + off) % 4)
        t_ops = ["T3", "T2", "T1", "T1 APOYO"]
        for g in act_r:
            for t in t_ops:
                if t not in asig.values(): asig[g] = t; break
            if g not in asig: asig[g] = "T1 APOYO"
        
        # 4. Generar deuda si hoy debían descansar pero trabajaron (porque no hubo cupo o festivo)
        for g, d_pref in descansos_config.items():
            if dia_n == d_pref and asig.get(g) in ["T1", "T2", "T3"]:
                deudas[g] += 1

        for g in GRUPOS_TEC: filas.append({"Fecha": fecha, "Sujeto": g, "Turno": asig.get(g, "DESCANSO")})
    return pd.DataFrame(filas)

def generar_malla_abordaje_individual(inicio, fin, d_ba, d_bb):
    df_emp = cargar_excel("empleados_grupos.xlsx")
    personal = df_emp[df_emp['GrupoAsignado'] == "Abordaje"]['Nombre'].tolist()
    if not personal: return pd.DataFrame()
    
    filas = []
    deudas_p = {p: 0 for p in personal} # RASTREADOR DE DEUDA ABORDAJE
    mitad = len(personal) // 2
    bloque_a, bloque_b = personal[:mitad], personal[mitad:]
    
    for fecha in pd.date_range(inicio, fin):
        dia_n = DIAS_ES[fecha.weekday()]; sem = fecha.isocalendar()[1]
        asig = {}
        # Rotación de fines de semana
        inv = sem % 2 == 0
        d_hoy_a = d_ba if not inv else d_bb
        d_hoy_b = d_bb if not inv else d_ba

        # 1. Pago de COMPENSADOS (Prioridad L-V)
        if 0 <= fecha.weekday() <= 4:
            p_deuda = [p for p in personal if deudas_p[p] > 0]
            for p in p_deuda:
                if len(asig) < (len(personal) - 20): # Máximo permitido para no romper el cupo de 20
                    asig[p] = "COMPENSADO"; deudas_p[p] -= 1

        # 2. Descansos por bloque
        for p in bloque_a:
            if dia_n == d_hoy_a and p not in asig: asig[p] = "DESCANSO"
        for p in bloque_b:
            if dia_n == d_hoy_b and p not in asig: asig[p] = "DESCANSO"

        # 3. LLENADO ESTRICTO DE CUPOS (10 T1 / 10 T2)
        libres = [p for p in personal if p not in asig]
        c1 = c2 = 0
        for p in libres:
            if c1 < 10: asig[p] = "T1"; c1 += 1
            elif c2 < 10: asig[p] = "T2"; c2 += 1
            else: asig[p] = "DISPONIBLE"

        # 4. Generar deuda si trabajaron en su día parametrizado
        if dia_n in [d_ba, d_bb]:
            for p in personal:
                if ((p in bloque_a and dia_n == d_hoy_a) or (p in bloque_b and dia_n == d_hoy_b)) and asig[p] in ["T1", "T2"]:
                    deudas_p[p] += 1

        for p in personal: filas.append({"Fecha": fecha, "Sujeto": p, "Turno": asig.get(p, "T1")})
    return pd.DataFrame(filas)

# =========================================================
# 4. INTERFAZ: PARAMETRIZADORES, EDITOR Y AUDITORÍA
# =========================================================
def pantalla_programador():
    tipo = st.sidebar.radio("Módulo Operativo", ["Técnicos", "Abordaje"])
    
    # ⏰ PARAMETRIZADOR DE HORAS
    with st.expander("⏰ Parametrizador de Horarios (Inicio/Fin)"):
        config_h = {}
        t_list = ["T1", "T2", "T3", "RELEVO", "T1 APOYO", "DISPONIBLE"]
        def_h = {"T1":[time(6,0),time(14,0)], "T2":[time(14,0),time(22,0)], "T3":[time(22,0),time(6,0)], 
                 "RELEVO":[time(8,0),time(16,0)], "T1 APOYO":[time(7,0),time(15,0)], "DISPONIBLE":[time(8,0),time(16,0)]}
        cols = st.columns(3)
        for i, t in enumerate(t_list):
            with cols[i%3]:
                ini = st.time_input(f"Inicio {t}", def_h[t][0], key=f"h_ini{t}")
                fin = st.time_input(f"Fin {t}", def_h[t][1], key=f"h_fin{t}")
                config_h[t] = {"Inicio": ini.strftime("%H:%M"), "Fin": fin.strftime("%H:%M")}
        config_h["DESCANSO"] = config_h["COMPENSADO"] = {"Inicio": "OFF", "Fin": "OFF"}

    # 📅 PARAMETRIZADOR DE DESCANSOS
    with st.expander("📅 Configuración de Días de Descanso"):
        if tipo == "Técnicos":
            st.write("Selecciona el día de descanso base para cada grupo:")
            desc_conf = {}
            cols_d = st.columns(4)
            for i, g in enumerate(GRUPOS_TEC):
                desc_conf[g] = cols_d[i].selectbox(f"{g}", DIAS_ES, index=(i+5)%7, key=f"d_tec{g}")
        else:
            st.write("Configuración de bloques (Sábado/Domingo rotativo):")
            c_ab1, c_ab2 = st.columns(2)
            d_ba = c_ab1.selectbox("Día Bloque A", DIAS_ES, index=5)
            d_bb = c_ab2.selectbox("Día Bloque B", DIAS_ES, index=6)

    c1, c2 = st.columns(2)
    inicio = c1.date_input("Fecha Inicio", date.today())
    fin = c2.date_input("Fecha Fin", date.today() + timedelta(days=21))
    
    if st.button("🚀 Generar Malla y Validar Reglas"):
        if tipo == "Técnicos":
            st.session_state.m_tec = generar_malla_tecnicos(inicio, fin, desc_conf)
        else:
            st.session_state.m_abo = generar_malla_abordaje_individual(inicio, fin, d_ba, d_bb)

    # 📝 EDITOR Y MÉTRICAS
    m_key = "m_tec" if tipo == "Técnicos" else "m_abo"
    if m_key in st.session_state:
        df = st.session_state[m_key]
        df["Label"] = df["Fecha"].apply(lambda x: f"{INICIALES[DIAS_ES[x.weekday()]]} {x.strftime('%d/%m')}")
        pivot = df.pivot(index="Sujeto", columns="Label", values="Turno").fillna("DESCANSO")
        sorted_cols = sorted(pivot.columns, key=lambda x: datetime.strptime(x.split(" ")[1] + "/2026", '%d/%m/%Y'))
        
        st.subheader(f"📝 Editor Maestro: {tipo}")
        df_edit = st.data_editor(style_malla(pivot[sorted_cols]), use_container_width=True)
        
        # 📊 AUDITORÍA DE CUPOS 10/10
        st.divider()
        df_final = df_edit.reset_index().melt(id_vars="Sujeto", var_name="Label", value_name="Turno")
        conteo = df_final.groupby(["Label", "Turno"]).size().unstack(fill_value=0)
        
        st.subheader("📊 Auditoría de Cobertura (Meta: 10 T1 / 10 T2)")
        if "T1" in conteo.columns and "T2" in conteo.columns:
            st.dataframe(conteo[["T1", "T2"]].T, use_container_width=True)
            if (conteo["T1"] < 10).any() or (conteo["T2"] < 10).any():
                st.error("🚨 Alerta: Cobertura insuficiente (<10) detectada.")
            else: st.success("✅ Cobertura 10/10 garantizada.")

        st.subheader("⚖️ Métricas de Equidad y Compensados")
        equidad = df_final.groupby(["Sujeto", "Turno"]).size().unstack(fill_value=0)
        st.dataframe(equidad.style.background_gradient(cmap="Greens"), use_container_width=True)
