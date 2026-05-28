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
    """Aplica el formato visual de celdas según el turno."""
    def apply_styles(val):
        key = val if val and str(val).strip() != "" else "DESCANSO"
        bg = COLORES_MAP.get(key, "#1B2631")
        txt = "white" if key in ["DESCANSO", "COMPENSADO"] else "#17202A"
        return f'background-color: {bg}; color: {txt}; font-weight: 700; border: 0.5px solid #D5DBDB'
    return df_pivot.style.map(apply_styles)

# =========================================================
# 2. CONECTIVIDAD GITHUB Y CARGA DE DATOS
# =========================================================
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
        st.toast(f"✅ Archivo actualizado en GitHub.")
    except:
        repo.create_file(nombre_archivo, "Create", buffer.getvalue())
        st.toast(f"🆕 Archivo creado en GitHub.")

# =========================================================
# 3. GESTIÓN DE PERSONAL
# =========================================================
def asignar_grupos_automatico(df):
    df = df.copy()
    if 'GrupoAsignado' in df.columns: df = df.drop(columns=['GrupoAsignado'])
    m = df[df['Cargo'].str.contains('Master', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    ta = df[df['Cargo'].str.contains('Tecnico A', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    tb = df[df['Cargo'].str.contains('Tecnico B', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    res = []
    for i, g in enumerate(GRUPOS_TEC):
        temp_m = m.iloc[i*2:(i+1)*2].copy(); temp_m['GrupoAsignado'] = g
        temp_ta = ta.iloc[i*7:(i+1)*7].copy(); temp_ta['GrupoAsignado'] = g
        temp_tb = tb.iloc[i*3:(i+1)*3].copy(); temp_tb['GrupoAsignado'] = g
        res.extend([temp_m, temp_ta, temp_tb])
    abo = df[df['Cargo'].str.contains('Abordaje|Auxiliar', case=False, na=False)].copy()
    abo['GrupoAsignado'] = "Abordaje"
    res.append(abo)
    return pd.concat(res).reset_index(drop=True)

def pantalla_personal():
    st.subheader("👥 Gestión de Plantilla")
    if st.button("📥 Cargar empleados.xlsx"):
        df = cargar_excel("empleados.xlsx")
        if not df.empty: st.session_state.df_pers = df; st.success("Personal cargado.")
    if 'df_pers' in st.session_state:
        if st.button("🎲 Ejecutar Clasificación"):
            st.session_state.df_pers_ready = asignar_grupos_automatico(st.session_state.df_pers)
        if 'df_pers_ready' in st.session_state:
            df_edit = st.data_editor(st.session_state.df_pers_ready, use_container_width=True)
            if st.button("💾 Guardar Estructura"):
                guardar_github(df_edit, "empleados_grupos.xlsx")

# =========================================================
# 4. MOTOR ABORDAJE (42H SEMANALES - EQUIDAD 50/50)
# =========================================================
def calcular_horas_turno(turno_val):
    # Regla 2026: Todos los turnos operativos valen 7h. Descansos = 0h.
    if turno_val in ["DESCANSO", "COMPENSADO", "OFF", None]: return 0.0
    return 7.0

def generar_malla_abordaje_individual(inicio, fin, descansos_elegidos):
    df_emp = cargar_excel("empleados_grupos.xlsx")
    if df_emp.empty: return pd.DataFrame()
    personal = df_emp[df_emp['GrupoAsignado'] == "Abordaje"]['Nombre'].tolist()[:27]
    
    filas = []
    cola_compensatorios = [] # Deuda inmediata L-V
    conteo_descansos_fds = {p: 0 for p in personal} 

    for fecha in pd.date_range(inicio, fin):
        dia_n, asig, cupo_fuera = DIAS_ES[fecha.weekday()], {}, 5
        n_semana = fecha.isocalendar()[1]
        
        # 1. PRIORIDAD: Pago de Compensados (Lunes a Viernes)
        if 0 <= fecha.weekday() <= 4:
            for p in list(cola_compensatorios):
                if cupo_fuera > 0:
                    asig[p], cupo_fuera = "COMPENSADO", cupo_fuera - 1
                    cola_compensatorios.remove(p)

        # 2. EQUIDAD: Alternancia semanal de Grupos
        if n_semana % 2 == 0:
            sagrados = {"A": descansos_elegidos["A"], "B": descansos_elegidos["B"]}
        else:
            sagrados = {"A": descansos_elegidos["B"], "B": descansos_elegidos["A"]}

        # Identificar quién debería librar hoy según su grupo
        candidatos_hoy = []
        for i, p in enumerate(personal):
            es_su_dia = (i < 13 and dia_n == sagrados["A"]) or (i >= 13 and dia_n == sagrados["B"])
            if es_su_dia: candidatos_hoy.append(p)

        # Ordenar por quien lleva menos libranzas para balancear 13/13
        candidatos_hoy = sorted(candidatos_hoy, key=lambda x: conteo_descansos_fds[x])

        for p in candidatos_hoy:
            if p in asig: continue
            if cupo_fuera > 0:
                asig[p], cupo_fuera = "DESCANSO", cupo_fuera - 1
                if dia_n in ["Sábado", "Domingo"]: conteo_descansos_fds[p] += 1
            else:
                # Si trabaja por cobertura, entra a cola de compensado inmediato
                if p not in cola_compensatorios: cola_compensatorios.append(p)

        # 3. LLENADO OBLIGATORIO (11 T1 y 11 T2)
        dispos = [p for p in personal if p not in asig]
        np.random.seed(fecha.day)
        np.random.shuffle(dispos)
        for p in dispos:
            if list(asig.values()).count("T1") < 11: asig[p] = "T1"
            elif list(asig.values()).count("T2") < 11: asig[p] = "T2"
            else: asig[p] = "DISPONIBLE"
            
        for p in personal:
            filas.append({"Fecha": fecha, "Sujeto": p, "Turno": asig.get(p, "DESCANSO")})
    return pd.DataFrame(filas)

# =========================================================
# 5. MOTOR TÉCNICOS (ROTACIÓN)
# =========================================================
def generar_malla_tecnicos(inicio, fin, descansos_ley):
    filas, deudas = [], {g: 0 for g in GRUPOS_TEC}
    for fecha in pd.date_range(inicio, fin):
        dia_n, sem, asig = DIAS_ES[fecha.weekday()], fecha.isocalendar()[1], {}
        gps_h = [g for g, d in descansos_ley.items() if d == dia_n]
        if len(gps_h) > 1:
            idx = sem % len(gps_h); d_r = gps_h[idx]; asig[d_r] = "DESCANSO"
            for g in gps_h: 
                if g != d_r: deudas[g] += 1
        elif len(gps_h) == 1: asig[gps_h[0]] = "DESCANSO"
        
        if 0 <= fecha.weekday() <= 4:
            g_d = sorted([g for g, d in deudas.items() if d > 0 and g not in asig], key=lambda x: deudas[x], reverse=True)
            if g_d: asig[g_d[0]], deudas[g_d[0]] = "COMPENSADO", deudas[g_d[0]]-1
        
        activos = sorted([g for g in GRUPOS_TEC if g not in asig], key=lambda x: (GRUPOS_TEC.index(x) + sem) % 4)
        for g in activos:
            for t in ["T1", "T2", "T3", "T1 APOYO"]:
                if t not in asig.values(): asig[g] = t; break
        for g in GRUPOS_TEC: filas.append({"Fecha": fecha, "Sujeto": g, "Turno": asig.get(g, "DESCANSO")})
    return pd.DataFrame(filas)

# =========================================================
# 6. AUDITORÍA INTEGRAL Y TRANSACCIONAL
# =========================================================
def ejecutar_auditoria_completa(df):
    df_aud = df.copy(); df_aud["Fecha"] = pd.to_datetime(df_aud["Fecha"])
    # Cobertura Diaria
    cob = df_aud.groupby(["Fecha", "Turno"]).size().unstack(fill_value=0)
    for c in ["T1", "T2", "DESCANSO", "COMPENSADO", "DISPONIBLE"]:
        if c not in cob.columns: cob[c] = 0
    # Horas Semanales
    df_aud['Semana'] = df_aud['Fecha'].dt.isocalendar().week
    df_aud['Horas'] = df_aud['Turno'].apply(calcular_horas_turno)
    h_sem = df_aud.groupby(['Sujeto', 'Semana'])['Horas'].sum().unstack(fill_value=0)
    # Equidad Detallada
    eq_det = df_aud[df_aud['Turno'].isin(["DESCANSO", "COMPENSADO"])].groupby(['Sujeto', 'Turno']).size().unstack(fill_value=0)
    for c in ["DESCANSO", "COMPENSADO"]:
        if c not in eq_det.columns: eq_det[c] = 0
    eq_det["Total Libres"] = eq_det["DESCANSO"] + eq_det["COMPENSADO"]
    return cob, h_sem, eq_det

def generar_reporte_detallado(df_final, tipo, config_horas, config_descansos):
    df_emp = cargar_excel("empleados_grupos.xlsx")
    if df_emp.empty: return pd.DataFrame()
    
    # Combinamos datos operativos con los del personal de GitHub
    det = pd.merge(df_final, df_emp[['Nombre', 'Cargo', 'GrupoAsignado']], 
                   left_on="Sujeto", right_on="Nombre" if tipo == "Abordaje" else "GrupoAsignado", how="inner")
    
    # Manejo del Nombre en Técnicos debido al cruce por GrupoAsignado
    if tipo != "Abordaje":
        if "Nombre_y" in det.columns:
            det["Nombre"] = det["Nombre_y"]
        elif "Nombre" in det.columns:
            pass

    # Tiempos de jornada y cálculo de horas programadas
    det["Hora Inicio"] = det["Turno"].apply(lambda x: config_horas.get(x, {}).get("Inicio", "OFF"))
    det["Hora Fin"] = det["Turno"].apply(lambda x: config_horas.get(x, {}).get("Fin", "OFF"))
    det["Horas Prog"] = det["Turno"].apply(calcular_horas_turno)
    
    # Lógica para extraer el día de descanso estipulado originalmente
    def obtener_descanso_base(row):
        if tipo == "Abordaje":
            idx_empleado = df_emp[df_emp['Nombre'] == row['Nombre']].index
            if not idx_empleado.empty and idx_empleado[0] < 13:
                return config_descansos.get("A", "N/A")
            else:
                return config_descansos.get("B", "N/A")
        else:
            return config_descansos.get(row['GrupoAsignado'], "N/A")

    det["Día Descanso Base"] = det.apply(obtener_descanso_base, axis=1)
    
    # Estructuración final de las columnas del Reporte de Nómina
    columnas_ordenadas = ["Fecha", "Nombre", "Cargo", "GrupoAsignado", "Día Descanso Base", "Turno", "Hora Inicio", "Hora Fin", "Horas Prog"]
    return det[columnas_ordenadas]

# =========================================================
# 7. INTERFAZ DE USUARIO
# =========================================================
def pantalla_programador():
    tipo = st.sidebar.radio("Módulo Selección", ["Abordaje", "Técnicos"])
    
    with st.expander("⏰ Configuración Jornada (7h)"):
        config_h = {}
        t_l = ["T1", "T2", "T3", "RELEVO", "T1 APOYO", "DISPONIBLE"]
        def_h = {"T1": [time(6,0), time(13,0)], "T2": [time(13,0), time(20,0)], "T3": [time(22,0), time(5,0)], "RELEVO": [time(8,0), time(15,0)], "T1 APOYO": [time(7,0), time(14,0)], "DISPONIBLE": [time(8,0), time(15,0)]}
        cols = st.columns(3)
        for i, t in enumerate(t_l):
            with cols[i%3]:
                ini = st.time_input(f"Inicia {t}", def_h[t][0], key=f"i{t}"); fin = st.time_input(f"Fin {t}", def_h[t][1], key=f"f{t}")
                config_h[t] = {"Inicio": ini.strftime("%H:%M"), "Fin": fin.strftime("%H:%M")}
        config_h["DESCANSO"] = config_h["COMPENSADO"] = {"Inicio": "OFF", "Fin": "OFF"}

    c1, c2 = st.columns(2)
    inicio, fin = c1.date_input("Inicio", date(2026, 7, 1)), c2.date_input("Fin", date(2026, 12, 31))
    
    if tipo == "Abordaje":
        ca, cb = st.columns(2)
        desc_data = {"A": ca.selectbox("Día Base G1 (1-13)", DIAS_ES, index=5), "B": cb.selectbox("Día Base G2 (14-27)", DIAS_ES, index=6)}
    else:
        desc_data = {}
        cols = st.columns(4)
        for i, g in enumerate(GRUPOS_TEC): desc_data[g] = cols[i].selectbox(f"Descanso {g}", DIAS_ES, index=(i+6)%7)

    if st.button("🚀 GENERAR MALLA SEMESTRAL"):
        if tipo == "Abordaje": st.session_state.m_base = generar_malla_abordaje_individual(inicio, fin, desc_data)
        else: st.session_state.m_base = generar_malla_tecnicos(inicio, fin, desc_data)

    if 'm_base' in st.session_state and not st.session_state.m_base.empty:
        df_final = st.session_state.m_base
        pivot = df_final.pivot(index="Sujeto", columns="Fecha", values="Turno").fillna("DESCANSO")
        
        st.subheader("📝 Editor Maestro")
        df_edit = st.data_editor(style_malla(pivot), use_container_width=True)
        
        df_audit = df_edit.reset_index().melt(id_vars="Sujeto", var_name="Fecha", value_name="Turno")
        cob, h_sem, eq = ejecutar_auditoria_completa(df_audit)
        
        t1, t2, t3, t4 = st.tabs(["📊 Cobertura", "⚖️ Jornada 42h", "📈 Equidad Semestral", "📋 Reporte Nómina"])
        with t1:
            st.dataframe(cob.style.map(lambda v: 'background-color: #D5F5E3' if v==11 else ('background-color: #FADBD8' if v<11 else ''), subset=["T1", "T2"] if "T1" in cob.columns else []), use_container_width=True)
        with t2:
            st.write("Control de Horas Semanales:")
            st.dataframe(h_sem.style.highlight_between(left=42.1, right=100, color="#FADBD8"), use_container_width=True)
        with t3:
            st.dataframe(eq.style.background_gradient(cmap="Greens", subset=["Total Libres"]), use_container_width=True)
        with t4:
            rep = generar_reporte_detallado(df_audit, tipo, config_h, desc_data)
            st.dataframe(rep, use_container_width=True)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer: rep.to_excel(writer, index=False)
            st.download_button("📥 Descargar Reporte Nómina", output.getvalue(), f"Malla_{tipo}_{date.today()}.xlsx")

if __name__ == "__main__":
    pantalla_programador()
