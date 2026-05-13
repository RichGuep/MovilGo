import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date, time
import holidays
import io
import openpyxl
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
        st.toast(f"✅ Archivo {nombre_archivo} actualizado en GitHub.")
    except:
        repo.create_file(nombre_archivo, "Create", buffer.getvalue())
        st.toast(f"🆕 Archivo {nombre_archivo} creado en GitHub.")

# =========================================================
# 3. GESTIÓN DE PERSONAL
# =========================================================
def asignar_grupos_automatico(df):
    df = df.copy()
    if 'GrupoAsignado' in df.columns: df = df.drop(columns=['GrupoAsignado'])
    # Técnicos: Distribución equitativa por cargo
    m = df[df['Cargo'].str.contains('Master', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    ta = df[df['Cargo'].str.contains('Tecnico A', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    tb = df[df['Cargo'].str.contains('Tecnico B', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    res = []
    for i, g in enumerate(GRUPOS_TEC):
        temp_m = m.iloc[i*2:(i+1)*2].copy(); temp_m['GrupoAsignado'] = g
        temp_ta = ta.iloc[i*7:(i+1)*7].copy(); temp_ta['GrupoAsignado'] = g
        temp_tb = tb.iloc[i*3:(i+1)*3].copy(); temp_tb['GrupoAsignado'] = g
        res.extend([temp_m, temp_ta, temp_tb])
    # Abordaje: Todos al mismo grupo para rotación individual
    abo = df[df['Cargo'].str.contains('Abordaje|Auxiliar', case=False, na=False)].copy()
    abo['GrupoAsignado'] = "Abordaje"
    res.append(abo)
    return pd.concat(res).reset_index(drop=True)

def pantalla_personal():
    st.subheader("👥 Gestión de Plantilla y Estructura")
    c1, c2 = st.columns(2)
    if c1.button("📥 Importar Lista (empleados.xlsx)"):
        df = cargar_excel("empleados.xlsx")
        if not df.empty: st.session_state.df_pers = df; st.success("Datos cargados.")
    if c2.button("🎲 Ejecutar Clasificación"):
        if 'df_pers' in st.session_state:
            st.session_state.df_pers_ready = asignar_grupos_automatico(st.session_state.df_pers)
            st.balloons()
    
    if 'df_pers_ready' in st.session_state:
        df_edit = st.data_editor(st.session_state.df_pers_ready, use_container_width=True)
        if st.button("💾 Guardar Estructura Final"):
            guardar_github(df_edit, "empleados_grupos.xlsx")

# =========================================================
# 4. MOTOR ABORDAJE (EQUIDAD 13/13 - LEY 42H - 11/11)
# =========================================================
def calcular_horas_turno(turno_val):
    if turno_val in ["DESCANSO", "COMPENSADO", "OFF", None]: return 0.0
    return 7.0 # Todos los turnos operativos valen 7h en 2026

def generar_malla_abordaje_individual(inicio, fin, descansos_elegidos):
    df_emp = cargar_excel("empleados_grupos.xlsx")
    if df_emp.empty: return pd.DataFrame()
    
    # Tomar las 27 personas de abordaje
    personal = df_emp[df_emp['GrupoAsignado'] == "Abordaje"]['Nombre'].tolist()[:27]
    filas = []
    cola_compensatorios = [] # Deuda para pagar L-V inmediato
    conteo_descansos_fds = {p: 0 for p in personal} # Para meta 13/13

    for fecha in pd.date_range(inicio, fin):
        dia_n, asig, cupo_fuera = DIAS_ES[fecha.weekday()], {}, 5
        n_semana = fecha.isocalendar()[1]
        
        # 1. Pago de Compensatorios (Prioridad Lunes a Viernes)
        if 0 <= fecha.weekday() <= 4:
            for p in list(cola_compensatorios):
                if cupo_fuera > 0:
                    asig[p], cupo_fuera = "COMPENSADO", cupo_fuera - 1
                    cola_compensatorios.remove(p)

        # 2. Lógica de Alternancia (Día Sagrado)
        # Intercambio de roles cada semana para equidad
        if n_semana % 2 == 0:
            sag_g1, sag_g2 = descansos_elegidos["A"], descansos_elegidos["B"]
        else:
            sag_g1, sag_g2 = descansos_elegidos["B"], descansos_elegidos["A"]

        # Candidatos que hoy deberían librar
        candidatos_hoy = []
        for i, p in enumerate(personal):
            es_su_dia = (i < 13 and dia_n == sag_g1) or (i >= 13 and dia_n == sag_g2)
            if es_su_dia: candidatos_hoy.append(p)

        # Priorizar a quienes llevan MENOS descansos reales en fin de semana
        candidatos_hoy = sorted(candidatos_hoy, key=lambda x: conteo_descansos_fds[x])

        for p in candidatos_hoy:
            if p in asig: continue
            if cupo_fuera > 0:
                asig[p], cupo_fuera = "DESCANSO", cupo_fuera - 1
                if dia_n in ["Sábado", "Domingo"]:
                    conteo_descansos_fds[p] += 1
            else:
                # Si no hay cupo (ya hay 5 fuera), entra a cola de compensado inmediato
                if p not in cola_compensatorios: cola_compensatorios.append(p)

        # 3. Llenado Blindado (11 T1 y 11 T2)
        dispos = [p for p in personal if p not in asig]
        np.random.seed(fecha.day)
        np.random.shuffle(dispos)
        for p in dispos:
            if list(asig.values()).count("T1") < 11: asig[p] = "T1"
            elif list(asig.values()).count("T2") < 11: asig[p] = "T2"
            else: asig[p] = "DISPONIBLE" # También suma 7 horas
            
        for p in personal:
            filas.append({"Fecha": fecha, "Sujeto": p, "Turno": asig.get(p, "DESCANSO")})
            
    return pd.DataFrame(filas)

# =========================================================
# 5. MOTOR TÉCNICOS (ROTACIÓN POR SEMANA)
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
        turnos_base = ["T1", "T2", "T3", "T1 APOYO"]
        for g in activos:
            for t in turnos_base:
                if t not in asig.values(): asig[g] = t; break
            if g not in asig: asig[g] = "T1 APOYO"
        for g in GRUPOS_TEC: filas.append({"Fecha": fecha, "Sujeto": g, "Turno": asig.get(g, "DESCANSO")})
    return pd.DataFrame(filas)

# =========================================================
# 6. AUDITORÍAS Y REPORTES
# =========================================================
def ejecutar_auditoria_total(df, tipo):
    df_aud = df.copy(); df_aud["Fecha"] = pd.to_datetime(df_aud["Fecha"])
    # Cobertura por día
    cob = df_aud.groupby(["Fecha", "Turno"]).size().unstack(fill_value=0)
    for c in ["T1", "T2", "T3", "DESCANSO", "COMPENSADO"]:
        if c not in cob.columns: cob[c] = 0
    # Horas Semanales (Control 42h)
    df_aud['Semana'] = df_aud['Fecha'].dt.isocalendar().week
    df_aud['Horas'] = df_aud['Turno'].apply(calcular_horas_turno)
    h_sem = df_aud.groupby(['Sujeto', 'Semana'])['Horas'].sum().unstack(fill_value=0)
    # Equidad Fin de Semana
    df_aud['EsFDS'] = df_aud['Fecha'].dt.weekday.isin([5, 6])
    eq_fds = df_aud[df_aud['EsFDS']].groupby(['Sujeto', 'Turno']).size().unstack(fill_value=0)
    return cob, h_sem, eq_fds

def generar_reporte_nomina(df_final, tipo, config_horas):
    df_emp = cargar_excel("empleados_grupos.xlsx")
    if df_emp.empty: return pd.DataFrame()
    det = pd.merge(df_final, df_emp[['Nombre', 'Cargo', 'GrupoAsignado']], 
                   left_on="Sujeto", right_on="Nombre" if tipo == "Abordaje" else "GrupoAsignado", how="inner")
    det["Hora Inicio"] = det["Turno"].apply(lambda x: config_horas.get(x, {}).get("Inicio", "OFF"))
    det["Hora Fin"] = det["Turno"].apply(lambda x: config_horas.get(x, {}).get("Fin", "OFF"))
    det["Horas Prog"] = det["Turno"].apply(calcular_horas_turno)
    return det[["Fecha", "Nombre", "Cargo", "Turno", "Hora Inicio", "Hora Fin", "Horas Prog"]]

# =========================================================
# 7. INTERFAZ PRINCIPAL
# =========================================================
def pantalla_programador():
    tipo = st.sidebar.radio("Módulo Operativo", ["Abordaje", "Técnicos"])
    
    with st.expander("⏰ Parametrizar Jornada (Ref. 7 horas)"):
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
    inicio, fin = c1.date_input("Desde", date(2026, 7, 1)), c2.date_input("Hasta", date(2026, 12, 31))
    
    desc_data = {}
    if tipo == "Abordaje":
        st.info("Equidad 50/50: Se alternarán los días base cada semana.")
        ca, cb = st.columns(2)
        desc_data = {"A": ca.selectbox("Día Base Grupo 1", DIAS_ES, index=5), "B": cb.selectbox("Día Base Grupo 2", DIAS_ES, index=6)}
    else:
        cols_d = st.columns(4)
        for i, g in enumerate(GRUPOS_TEC): desc_data[g] = cols_d[i].selectbox(f"Descanso {g}", DIAS_ES, index=(i+6)%7)

    if st.button("🚀 GENERAR MALLA COMPLETA"):
        with st.spinner("Calculando equidad y coberturas..."):
            if tipo == "Abordaje": st.session_state.m_base = generar_malla_abordaje_individual(inicio, fin, desc_data)
            else: st.session_state.m_base = generar_malla_tecnicos(inicio, fin, desc_data)

    if 'm_base' in st.session_state and not st.session_state.m_base.empty:
        df_final = st.session_state.m_base
        pivot = df_final.pivot(index="Sujeto", columns="Fecha", values="Turno").fillna("DESCANSO")
        
        st.subheader("📝 Editor Maestro de Turnos")
        df_edit = st.data_editor(style_malla(pivot), use_container_width=True)
        
        # Procesar auditorías sobre los datos editados
        df_final_audit = df_edit.reset_index().melt(id_vars="Sujeto", var_name="Fecha", value_name="Turno")
        cob, h_sem, eq = ejecutar_auditoria_total(df_final_audit, tipo)
        
        tab1, tab2, tab3, tab4 = st.tabs(["📊 Cobertura (11/11)", "⚖️ Ley 42h", "🎯 Equidad FDS", "📋 Reporte Nómina"])
        
        with tab1:
            st.dataframe(cob.style.map(lambda v: 'background-color: #D5F5E3' if v==11 else ('background-color: #FADBD8' if v<11 else ''), subset=["T1", "T2"] if "T1" in cob.columns else []), use_container_width=True)
        with tab2:
            st.write("Horas por semana (Rojo si > 42):")
            st.dataframe(h_sem.style.highlight_between(left=42.1, right=100, color="#FADBD8"), use_container_width=True)
        with tab3:
            st.write("Descansos efectivos en Sábados y Domingos (Semestre):")
            st.dataframe(eq, use_container_width=True)
        with tab4:
            malla_rep = generar_reporte_nomina(df_final_audit, tipo, config_h)
            st.dataframe(malla_rep, use_container_width=True)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer: malla_rep.to_excel(writer, index=False)
            st.download_button("📥 Descargar Reporte Nómina", output.getvalue(), f"Malla_{tipo}_{date.today()}.xlsx")
