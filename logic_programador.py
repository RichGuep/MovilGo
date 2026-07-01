import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date, time
import holidays
import io
import os
import json
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
    """Aplica el formato visual de celdas según el turno original."""
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
# 3. GESTIÓN DE PERSONAL (AUTOMÁTICA + DESPLEGABLE MANUAL)
# =========================================================
def asignar_grupos_automatico(df):
    df = df.copy()
    if 'GrupoAsignado' in df.columns: 
        df = df.drop(columns=['GrupoAsignado'])
    
    # Separación estricta para no diluir las cuotas de técnicos
    supervisores = df[df['Cargo'].str.contains('Supervisor', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    df_ops = df[~df['Cargo'].str.contains('Supervisor', case=False, na=False)]
    
    m = df_ops[df_ops['Cargo'].str.contains('Master', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    ta = df_ops[df_ops['Cargo'].str.contains('Tecnico A', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    tb = df_ops[df_ops['Cargo'].str.contains('Tecnico B', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    
    res = []
    # Distribución equitativa inyectando 1 supervisor por cada bloque
    for i, g in enumerate(GRUPOS_TEC):
        temp_m = m.iloc[i*2:(i+1)*2].copy(); temp_m['GrupoAsignado'] = g
        temp_ta = ta.iloc[i*7:(i+1)*7].copy(); temp_ta['GrupoAsignado'] = g
        temp_tb = tb.iloc[i*3:(i+1)*3].copy(); temp_tb['GrupoAsignado'] = g
        
        if i < len(supervisores):
            temp_sup = supervisores.iloc[[i]].copy()
            temp_sup['GrupoAsignado'] = g
            res.append(temp_sup)
            
        res.extend([temp_m, temp_ta, temp_tb])
        
    abo = df_ops[df_ops['Cargo'].str.contains('Abordaje|Auxiliar', case=False, na=False)].copy()
    abo['GrupoAsignado'] = "Abordaje"
    res.append(abo)
    
    return pd.concat(res).reset_index(drop=True)

def pantalla_personal():
    st.subheader("👥 Gestión de Plantilla Operativa")
    
    if 'df_pers_ready' not in st.session_state:
        st.session_state.df_pers_ready = pd.DataFrame()

    c1, c2 = st.columns(2)
    with c1:
        if st.button("📥 Cargar empleados.xlsx Base"):
            df = cargar_excel("empleados.xlsx")
            if not df.empty: 
                st.session_state.df_pers_ready = df
                st.success("Personal cargado exitosamente.")
    with c2:
        if st.button("🎲 Ejecutar Clasificación Aleatoria"):
            df_base = cargar_excel("empleados.xlsx")
            if not df_base.empty:
                st.session_state.df_pers_ready = asignar_grupos_automatico(df_base)
                st.success("¡Distribución terminada! Supervisores asignados del Grupo 1 al 4.")

    if not st.session_state.df_pers_ready.empty:
        st.markdown("---")
        st.markdown("##### ✍️ Modificación e Inyección Manual de Grupos")
        st.caption("💡 Haz doble clic sobre la celda de 'GrupoAsignado' para reasignar el bloque o supervisor a mano.")
        
        if 'GrupoAsignado' not in st.session_state.df_pers_ready.columns:
            st.session_state.df_pers_ready['GrupoAsignado'] = "None"
            
        st.session_state.df_pers_ready['GrupoAsignado'] = st.session_state.df_pers_ready['GrupoAsignado'].fillna("None").astype(str)
        opciones_grupos = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4", "Abordaje", "None"]
        
        # EDITOR INTERACTIVO CON SELECTOR MULTIOPCIÓN
        df_edit = st.data_editor(
            st.session_state.df_pers_ready,
            use_container_width=True,
            column_config={
                "GrupoAsignado": st.column_config.SelectboxColumn(
                    "📦 Grupo Asignado",
                    help="Establece el grupo definitivo para la malla",
                    options=opciones_grupos,
                    required=True
                )
            },
            key="maestro_personal_dropdown"
        )
        
        if st.button("💾 Guardar Estructura Definitiva en GitHub"):
            st.session_state.df_pers_ready = df_edit
            guardar_github(df_edit, "empleados_grupos.xlsx")

# =========================================================
# 4. MOTORES DE ROTACIÓN ORIGINALES PRESERVADOS
# =========================================================
def calcular_horas_turno(turno_val):
    if turno_val in ["DESCANSO", "COMPENSADO", "OFF", None]: return 0.0
    return 7.0

def generar_malla_abordaje_individual(inicio, fin, descansos_elegidos, cuota_descansos_lv, cuota_t1, cuota_t2):
    df_emp = cargar_excel("empleados_grupos.xlsx")
    if df_emp.empty: return pd.DataFrame()
    
    df_pool = df_emp[df_emp['GrupoAsignado'] == "Abordaje"]
    personal = df_pool[~df_pool['Cargo'].str.contains('Supervisor', case=False, na=False)]['Nombre'].tolist()
    supervisores = df_pool[df_pool['Cargo'].str.contains('Supervisor', case=False, na=False)]['Nombre'].tolist()
    
    filas = []
    cola_compensatorios = [] 
    conteo_descansos_fds = {p: 0 for p in personal + supervisores} 

    for fecha in pd.date_range(inicio, fin):
        dia_n, asig, cupo_fuera = DIAS_ES[fecha.weekday()], {}, cuota_descansos_lv
        n_semana = fecha.isocalendar()[1]
        
        if 0 <= fecha.weekday() <= 4:
            for p in list(cola_compensatorios):
                if cupo_fuera > 0 and p in personal:
                    asig[p], cupo_fuera = "COMPENSADO", cupo_fuera - 1
                    cola_compensatorios.remove(p)

        if n_semana % 2 == 0:
            sagrados = {"A": descansos_elegidos["A"], "B": descansos_elegidos["B"]}
        else:
            sagrados = {"A": descansos_elegidos["B"], "B": descansos_elegidos["A"]}

        candidatos_hoy = []
        mitad_pool = len(personal) // 2
        for i, p in enumerate(personal):
            es_su_dia = (i < mitad_pool and dia_n == sagrados["A"]) or (i >= mitad_pool and dia_n == sagrados["B"])
            if es_su_dia: candidatos_hoy.append(p)

        candidatos_hoy = sorted(candidatos_hoy, key=lambda x: conteo_descansos_fds[x])

        for p in candidatos_hoy:
            if p in asig: continue
            if cupo_fuera > 0:
                asig[p], cupo_fuera = "DESCANSO", cupo_fuera - 1
                if dia_n in ["Sábado", "Domingo"]: conteo_descansos_fds[p] += 1
            else:
                if p not in cola_compensatorios: cola_compensatorios.append(p)

        dispos = [p for p in personal if p not in asig]
        np.random.seed(fecha.day)
        np.random.shuffle(dispos)
        for p in dispos:
            if list(asig.values()).count("T1") < cuota_t1: asig[p] = "T1"
            elif list(asig.values()).count("T2") < cuota_t2: asig[p] = "T2"
            else: asig[p] = "DISPONIBLE"
            
        for sup in supervisores:
            if dia_n == sagrados["B"]: asig[sup] = "DESCANSO"
            else: asig[sup] = "T1" if list(asig.values()).count("T1") <= list(asig.values()).count("T2") else "T2"
            
        for p in personal + supervisores:
            filas.append({"Fecha": fecha, "Sujeto": p, "Turno": asig.get(p, "DESCANSO")})
    return pd.DataFrame(filas)

def generar_malla_tecnicos(inicio, fin, descansos_ley):
    df_emp = cargar_excel("empleados_grupos.xlsx")
    if df_emp.empty: return pd.DataFrame()
    
    supervisores_mapeo = df_emp[df_emp['Cargo'].str.contains('Supervisor', case=False, na=False)].set_index('GrupoAsignado')['Nombre'].to_dict()
    
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
        
        # LOGICA MODULAR ORIGINAL: Cobertura ininterrumpida de turnos críticos por ordenación
        activos = sorted([g for g in GRUPOS_TEC if g not in asig], key=lambda x: (GRUPOS_TEC.index(x) + sem) % 4)
        for g in activos:
            for t in ["T1", "T2", "T3", "T1 APOYO"]:
                if t not in asig.values(): asig[g] = t; break
                
        for g in GRUPOS_TEC:
            turno_asignado = asig.get(g, "DESCANSO")
            filas.append({"Fecha": fecha, "Sujeto": g, "Turno": turno_asignado})
            
            if g in supervisores_mapeo:
                filas.append({"Fecha": fecha, "Sujeto": f"SVP - {supervisores_mapeo[g]} ({g})", "Turno": turno_asignado})
                
    return pd.DataFrame(filas)

# =========================================================
# 5. AUDITORÍA INTEGRAL DE LA REFORMA
# =========================================================
def ejecutar_auditoria_completa(df):
    df_aud = df.copy(); df_aud["Fecha"] = pd.to_datetime(df_aud["Fecha"])
    cob = df_aud.groupby(["Fecha", "Turno"]).size().unstack(fill_value=0)
    for c in ["T1", "T2", "T3", "DESCANSO", "COMPENSADO", "DISPONIBLE"]:
        if c not in cob.columns: cob[c] = 0
    df_aud['Semana'] = df_aud['Fecha'].dt.isocalendar().week
    df_aud['Horas'] = df_aud['Turno'].apply(lambda x: calcular_horas_turno(x))
    h_sem = df_aud.groupby(['Sujeto', 'Semana'])['Horas'].sum().unstack(fill_value=0)
    
    eq_det = df_aud[df_aud['Turno'].isin(["DESCANSO", "COMPENSADO"])].groupby(['Sujeto', 'Turno']).size().unstack(fill_value=0)
    for c in ["DESCANSO", "COMPENSADO"]:
        if c not in eq_det.columns: eq_det[c] = 0
    eq_det["Total Libres"] = eq_det["DESCANSO"] + eq_det["COMPENSADO"]
    return cob, h_sem, eq_det

def generar_reporte_detallado(df_final, tipo, config_horas, config_descansos):
    df_emp = cargar_excel("empleados_grupos.xlsx")
    if df_emp.empty: return pd.DataFrame()
    
    det = pd.merge(df_final, df_emp[['Nombre', 'Cargo', 'GrupoAsignado']], 
                   left_on="Sujeto", right_on="Nombre" if tipo == "Abordaje" else "GrupoAsignado", how="inner")
    
    det["Hora Inicio"] = det["Turno"].apply(lambda x: config_horas.get(x, {}).get("Inicio", "OFF"))
    det["Hora Fin"] = det["Turno"].apply(lambda x: config_horas.get(x, {}).get("Fin", "OFF"))
    det["Horas Prog"] = det["Turno"].apply(calcular_horas_turno)
    
    def obtener_descanso_base(row):
        if tipo == "Abordaje":
            idx_empleado = df_emp[df_emp['Nombre'] == row['Nombre']].index
            if not idx_empleado.empty and idx_empleado[0] < 13: return config_descansos.get("A", "N/A")
            else: return config_descansos.get("B", "N/A")
        else:
            return config_descansos.get(row['GrupoAsignado'], "N/A")

    det["Día Descanso Base"] = det.apply(obtener_descanso_base, axis=1)
    columnas_ordenadas = ["Fecha", "Nombre", "Cargo", "GrupoAsignado", "Día Descanso Base", "Turno", "Hora Inicio", "Hora Fin", "Horas Prog"]
    return det[columnas_ordenadas]

# =========================================================
# 6. INTERFAZ DE USUARIO DEL PROGRAMADOR
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

    # CARGA DE CUOTAS NUMÉRICAS RECEPTIVAS EN ABORDAJE
    if tipo == "Abordaje":
        with st.expander("📊 Parámetros de Capacidad - Abordaje", expanded=True):
            pc1, pc2, pc3 = st.columns(3)
            cuota_desc_lv = pc1.number_input("Cupo máximo de descansos L-V", min_value=1, max_value=15, value=5)
            cuota_t1 = pc2.number_input("Personal requerido en T1", min_value=1, max_value=20, value=11)
            cuota_t2 = pc3.number_input("Personal requerido en T2", min_value=1, max_value=20, value=11)

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
        if tipo == "Abordaje": 
            st.session_state.m_base = generar_malla_abordaje_individual(inicio, fin, desc_data, cuota_desc_lv, cuota_t1, cuota_t2)
        else: 
            st.session_state.m_base = generar_malla_tecnicos(inicio, fin, desc_data)

    if 'm_base' in st.session_state and not st.session_state.m_base.empty:
        df_final = st.session_state.m_base.copy()
        
        st.write("---")
        st.subheader("📋 Malla Resultante y Ajustes Manuales")
        
        # FILTRADO DE GRUPO DINÁMICO EN PANTALLA
        opciones_vista = ["Ver Todo"] + (GRUPOS_TEC if tipo == "Técnicos" else ["Abordaje"])
        if tipo == "Técnicos": opciones_vista.append("Supervisores")
            
        filtro_grupo = st.selectbox("🔍 Filtrar visualización por Bloque:", opciones_vista)
        
        if filtro_grupo == "Supervisores":
            df_display = df_final[df_final["Sujeto"].str.contains("SVP -", na=False)]
        elif filtro_grupo != "Ver Todo":
            if tipo == "Técnicos":
                df_display = df_final[(df_final["Sujeto"] == filtro_grupo) | (df_final["Sujeto"].str.contains(f"\({filtro_grupo}\)", na=False))]
            else:
                df_display = df_final[df_final["Sujeto"] != "Abordaje"]
        else:
            df_display = df_final.copy()

        pivot = df_display.pivot(index="Sujeto", columns="Fecha", values="Turno").fillna("DESCANSO")
        pivot.columns = [p.strftime('%Y-%m-%d') if isinstance(p, (datetime, date, pd.Timestamp)) else str(p) for p in pivot.columns]
        
        # EDITOR DE CELDAS CON COLORES ORIGINALES RESTAURADOS
        df_edit_matriz = st.data_editor(style_malla(pivot), use_container_width=True, key=f"ed_v3_{filtro_grupo}")
        
        df_audit = df_edit_matriz.reset_index().melt(id_vars="Sujeto", var_name="Fecha", value_name="Turno")
        cob, h_sem, eq = ejecutar_auditoria_completa(df_audit)
        
        t1, t2, t3, t4 = st.tabs(["📊 Cobertura Lograda", "⚖️ Jornada 42h (Reforma)", "📈 Historial Equidad", "📋 Reporte Nómina"])
        with t1:
            st.dataframe(cob, use_container_width=True)
        with t2:
            st.dataframe(h_sem.style.highlight_between(left=42.1, right=100, color="#FADBD8"), use_container_width=True)
        with t3:
            st.dataframe(eq.style.background_gradient(cmap="Greens", subset=["Total Libres"]), use_container_width=True)
        with t4:
            try:
                rep = generar_reporte_detallado(df_audit, tipo, config_h, desc_data)
                st.dataframe(rep, use_container_width=True)
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer: rep.to_excel(writer, index=False)
                st.download_button("📥 Descargar Reporte Nómina", output.getvalue(), f"Malla_{tipo}_{date.today()}.xlsx")
            except:
                st.info("Reporte disponible en pool completo.")

if __name__ == "__main__":
    pantalla_programador()
