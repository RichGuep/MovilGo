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
# 1. CONSTANTES, ESTILOS Y CONTROL DE FESTIVOS
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
    """Aplica el formato visual de celdas según el turno con los colores exactos."""
    def apply_styles(val):
        key = str(val).strip() if val and str(val).strip() != "" else "DESCANSO"
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
    if 'GrupoAsignado' in df.columns: df = df.drop(columns=['GrupoAsignado'])
    
    supervisores = df[df['Cargo'].str.contains('Supervisor', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    df_ops = df[~df['Cargo'].str.contains('Supervisor', case=False, na=False)]
    
    m = df_ops[df_ops['Cargo'].str.contains('Master', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    ta = df_ops[df_ops['Cargo'].str.contains('Tecnico A', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    tb = df_ops[df_ops['Cargo'].str.contains('Tecnico B', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    
    res = []
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
                st.success("Personal base cargado.")
    with c2:
        if st.button("🎲 Ejecutar Clasificación Aleatoria"):
            df_base = cargar_excel("empleados.xlsx")
            if not df_base.empty:
                st.session_state.df_pers_ready = asignar_grupos_automatico(df_base)
                st.success("Distribución aleatoria calculada con supervisores.")

    if not st.session_state.df_pers_ready.empty:
        st.markdown("---")
        if 'GrupoAsignado' not in st.session_state.df_pers_ready.columns:
            st.session_state.df_pers_ready['GrupoAsignado'] = "None"
        st.session_state.df_pers_ready['GrupoAsignado'] = st.session_state.df_pers_ready['GrupoAsignado'].fillna("None").astype(str)
        
        opciones_grupos = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4", "Abordaje", "None"]
        df_edit = st.data_editor(
            st.session_state.df_pers_ready,
            use_container_width=True,
            column_config={
                "GrupoAsignado": st.column_config.SelectboxColumn("📦 Grupo Asignado", options=opciones_grupos, required=True)
            },
            key="personal_dropdown_v4"
        )
        if st.button("💾 Guardar Estructura Definitiva en GitHub"):
            st.session_state.df_pers_ready = df_edit
            guardar_github(df_edit, "empleados_grupos.xlsx")

# =========================================================
# 4. MOTORES DE ROTACIÓN DE TURNOS PRESERVADOS COMPLETO
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
        
        # Secuencia modular determinista inalterada del código original
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
# 5. AUDITORÍA INTEGRAL Y ALARMAS DE FATIGA
# =========================================================
def ejecutar_auditoria_completa(df):
    df_aud = df.copy(); df_aud["Fecha"] = pd.to_datetime(df_aud["Fecha"])
    cob = df_aud.groupby(["Fecha", "Turno"]).size().unstack(fill_value=0)
    for c in ["T1", "T2", "T3", "RELEVO", "T1 APOYO", "DESCANSO", "COMPENSADO", "DISPONIBLE"]:
        if c not in cob.columns: cob[c] = 0
        
    df_aud['Semana'] = df_aud['Fecha'].dt.isocalendar().week
    df_aud['Horas'] = df_aud['Turno'].apply(lambda x: calcular_horas_turno(x))
    h_sem = df_aud.groupby(['Sujeto', 'Semana'])['Horas'].sum().unstack(fill_value=0)
    
    eq_det = df_aud[df_aud['Turno'].isin(["DESCANSO", "COMPENSADO"])].groupby(['Sujeto', 'Turno']).size().unstack(fill_value=0)
    for c in ["DESCANSO", "COMPENSADO"]:
        if c not in eq_det.columns: eq_det[c] = 0
    eq_det["Total Libres"] = eq_det["DESCANSO"] + eq_det["COMPENSADO"]
    return cob, h_sem, eq_det

def verificar_alarmas_cambios_drasticos(df_plano):
    """Genera alertas si un sujeto pasa de T3->T1 o T2->T1 de forma consecutiva (Requisito 5)."""
    df_plano = df_plano.sort_values(by=["Sujeto", "Fecha"])
    alertas = []
    
    for sujeto, group in df_plano.groupby("Sujeto"):
        lista_turnos = group["Turno"].tolist()
        lista_fechas = group["Fecha"].tolist()
        
        for i in range(1, len(lista_turnos)):
            t_anterior = lista_turnos[i-1]
            t_actual = lista_turnos[i]
            fecha_act = lista_fechas[i].strftime('%Y-%m-%d')
            
            if t_anterior == "T3" and t_actual == "T1":
                alertas.append(f"🚨 **Fatiga Crítica:** '{sujeto}' cambia drásticamente de Nocturno (**T3**) a Mañana (**T1**) el día {fecha_act}.")
            elif t_anterior == "T2" and t_actual == "T1":
                alertas.append(f"⚠️ **Transición Corta:** '{sujeto}' cambia de Tarde (**T2**) a Mañana (**T1**) el día {fecha_act} reduciendo descanso interjornada.")
    return alertas

def generar_reporte_detallado(df_final, tipo, config_horas, config_descansos, matriz_tecnicos_capacidades=None):
    """Cruza la malla de bloques con el listado de técnicos individuales para generar el reporte de nómina (Requisito 2)."""
    df_emp = cargar_excel("empleados_grupos.xlsx")
    if df_emp.empty: return pd.DataFrame()
    
    filas_reporte = []
    df_final['Fecha'] = pd.to_datetime(df_final['Fecha'])
    
    if tipo == "Abordaje":
        df_sub = df_emp[df_emp['GrupoAsignado'] == "Abordaje"]
        for _, emp in df_sub.iterrows():
            malla_persona = df_final[df_final['Sujeto'] == emp['Nombre']]
            for _, m_fila in malla_persona.iterrows():
                turno = m_fila['Turno']
                filas_reporte.append({
                    "Fecha": m_fila['Fecha'].strftime('%Y-%m-%d'),
                    "Nombre": emp['Nombre'],
                    "Cargo": emp['Cargo'],
                    "GrupoAsignado": "Abordaje",
                    "Día Descanso Base": config_descansos.get("A", "Sábado"),
                    "Turno": turno,
                    "Hora Inicio": config_horas.get(turno, {}).get("Inicio", "OFF"),
                    "Hora Fin": config_horas.get(turno, {}).get("Fin", "OFF"),
                    "Horas Prog": calcular_horas_turno(turno)
                })
    else:
        # Mapeo detallado de Técnicos individuales clonando el estado asignado a su bloque
        df_sub = df_emp[df_emp['GrupoAsignado'].isin(GRUPOS_TEC)]
        for _, emp in df_sub.iterrows():
            g_pertenece = emp['GrupoAsignado']
            cargo_actual = emp['Cargo']
            
            if "Supervisor" in str(cargo_actual):
                malla_bloque = df_final[df_final['Sujeto'].str.contains(f"SVP - {emp['Nombre']}", na=False)]
            else:
                malla_bloque = df_final[df_final['Sujeto'] == g_pertenece]
                
            for _, m_fila in malla_bloque.iterrows():
                turno = m_fila['Turno']
                
                # REGLA DE FILTRADO DINÁMICO POR PARÁMETROS:
                # Si el usuario configuró 0 para este cargo en este turno específico en el parametrizador superior,
                # el reporte de nómina limpia su estado mandándolo a DISPONIBLE para no inflar cuotas.
                if matriz_tecnicos_capacidades and cargo_actual in matriz_tecnicos_capacidades:
                    limite_cupo = matriz_tecnicos_capacidades[cargo_actual].get(turno, 99)
                    if limite_cupo == 0 and turno not in ["DESCANSO", "COMPENSADO"]:
                        turno = "DISPONIBLE"

                filas_reporte.append({
                    "Fecha": m_fila['Fecha'].strftime('%Y-%m-%d'),
                    "Nombre": emp['Nombre'],
                    "Cargo": cargo_actual,
                    "GrupoAsignado": g_pertenece,
                    "Día Descanso Base": config_descansos.get(g_pertenece, "Domingo"),
                    "Turno": turno,
                    "Hora Inicio": config_horas.get(turno, {}).get("Inicio", "OFF"),
                    "Hora Fin": config_horas.get(turno, {}).get("Fin", "OFF"),
                    "Horas Prog": calcular_horas_turno(turno)
                })
                
    return pd.DataFrame(filas_reporte)

# =========================================================
# 6. INTERFAZ OPERATIVA DEL PROGRAMADOR
# =========================================================
def pantalla_programador():
    tipo = st.sidebar.radio("Módulo Selección", ["Abordaje", "Técnicos"])
    
    # 1. MEJORA REQUERIDA: PARAMETRIZADOR DINÁMICO POR CARGO Y TURNO (Requisito 1)
    matriz_tecnicos_cap = {}
    with st.expander("📊 Parámetros de Capacidad y Roles Requeridos", expanded=True):
        if tipo == "Abordaje":
            pc1, pc2, pc3 = st.columns(3)
            cuota_desc_lv = pc1.number_input("Cupo máximo de descansos L-V", min_value=1, max_value=15, value=5)
            cuota_t1 = pc2.number_input("Personal requerido en T1", min_value=1, max_value=25, value=11)
            cuota_t2 = pc3.number_input("Personal requerido en T2", min_value=1, max_value=25, value=11)
        else:
            st.markdown("##### ⚙️ Selección de Cargos Activos y Cuota por Turno:")
            cargos_disponibles = ["Master", "Tecnico A", "Tecnico B", "Supervisor"]
            cargos_seleccionados = st.multiselect(
                "💼 Seleccione qué cargos se incluirán en la programación técnica:",
                options=cargos_disponibles,
                default=["Master", "Tecnico A", "Supervisor"]
            )
            
            turnos_claves = ["T1", "T2", "T3", "RELEVO", "T1 APOYO", "DISPONIBLE"]
            
            # Formulario dinámico indexado por Cargo -> Turno
            for cargo in cargos_seleccionados:
                st.markdown(f"🔹 **Dotación de {cargo} por Grupo en cada Turno:**")
                cols_j = st.columns(6)
                matriz_tecnicos_cap[cargo] = {}
                for idx, t in enumerate(turnos_claves):
                    with cols_j[idx]:
                        val_def = 1 if cargo == "Supervisor" else (2 if t in ["T1", "T2"] else (1 if t == "T3" else 0))
                        cant = st.number_input(f"{t}", min_value=0, max_value=20, value=val_def, key=f"req_tec_{cargo}_{t}")
                        matriz_tecnicos_cap[cargo][t] = cant
                st.caption("---")

    with st.expander("⏰ Configuración Rangos de Jornada (7h)"):
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

    if st.button("🚀 GENERAR MALLA SEMESTRAL CON REGLAS"):
        if tipo == "Abordaje": 
            st.session_state.m_base = generar_malla_abordaje_individual(inicio, fin, desc_data, cuota_desc_lv, cuota_t1, cuota_t2)
        else: 
            st.session_state.m_base = generar_malla_tecnicos(inicio, fin, desc_data)

    if 'm_base' in st.session_state and not st.session_state.m_base.empty:
        df_final = st.session_state.m_base.copy()
        
        st.write("---")
        st.subheader("📋 Malla Resultante y Ajustes Manuales")
        
        opciones_vista = ["Ver Todo"] + (GRUPOS_TEC if tipo == "Técnicos" else ["Abordaje"])
        if tipo == "Técnicos": opciones_vista.append("Supervisores")
            
        filtro_grupo = st.selectbox("🔍 Filtrar Malla por Bloque en Pantalla:", opciones_vista)
        
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
        
        # EDITOR INTERACTIVO CON FORMATO Y COLOR CONDICIONAL RESTAURADO (REQUISITO 3)
        df_edit_matriz = st.data_editor(style_malla(pivot), use_container_width=True, key=f"ed_final_prod_{filtro_grupo}")
        
        df_audit = df_edit_matriz.reset_index().melt(id_vars="Sujeto", var_name="Fecha", value_name="Turno")
        df_audit["Fecha"] = pd.to_datetime(df_audit["Fecha"])
        
        cob, h_sem, eq = ejecutar_auditoria_completa(df_audit)
        
        st.write("---")
        t1, t2, t3, t4 = st.tabs(["📊 Cobertura Lograda", "⚠️ Alarmas de Fatiga", "⚖️ Jornada 42h (Reforma)", "📋 Reporte Nómina Detallado"])
        
        with t1:
            st.write("### Cuotas de Cobertura Diaria Evaluadas")
            
            # REQUISITO 4: ALERTA DE CUMPLIMIENTO DE LOS 3 TURNOS CRÍTICOS (T1, T2, T3) TODOS LOS DÍAS
            if tipo == "Técnicos" and filtro_grupo == "Ver Todo":
                dias_sin_t1 = cob[cob["T1"] == 0].index.tolist()
                dias_sin_t2 = cob[cob["T2"] == 0].index.tolist()
                dias_sin_t3 = cob[cob["T3"] == 0].index.tolist()
                
                if dias_sin_t1 or dias_sin_t2 or dias_sin_t3:
                    fechas_alertas = sorted(list(set(dias_sin_t1 + dias_sin_t2 + dias_sin_t3)))
                    st.error(f"🚨 **Alerta de Cobertura Desprotegida:** Se detectaron días sin operación 24/7 en el semestre. Fechas con fallas en T1/T2/T3: {[d.strftime('%Y-%m-%d') for d in fechas_alertas[:5]]} (Mostrando primeras 5).")
                else:
                    st.success("✅ **Garantía 24/7 Exitosa:** Se confirma el cumplimiento de los 3 turnos (T1, T2, T3) de soporte técnico para todos los días del periodo.")
                    
            st.dataframe(cob, use_container_width=True)
            
        with t2:
            st.write("### Escáner de Protección y Fatiga (Reglas de Transición)")
            # REQUISITO 5: ALARMA DE CAMBIOS DRÁSTICOS DE TURNO (T3 a T1 / T2 a T1)
            lista_alertas_drasticas = verificar_alarmas_cambios_drasticos(df_audit)
            if lista_alertas_drasticas:
                for alerta in lista_alertas_drasticas[:30]: # Limitar visualización para no saturar
                    st.markdown(alerta)
            else:
                st.success("✅ Excelente. No se detectaron transiciones críticas o violaciones al descanso en las celdas actuales.")
                
        with t3:
            st.dataframe(h_sem.style.highlight_between(left=42.01, right=100, color="#FADBD8"), use_container_width=True)
            
        with t4:
            st.write("### 💵 Reporte Consolidado de Nómina Detallado por Empleado")
            # REQUISITO 2: GENERACIÓN DEL REPORTE DETALLADO CRUZANDO CONTRA LA CONFIGURACIÓN DE CAPACIDADES
            rep_individual = generar_reporte_detallado(df_audit, tipo, config_h, desc_data, matriz_tecnicos_cap if tipo == "Técnicos" else None)
            
            if not rep_individual.empty:
                st.dataframe(rep_individual, use_container_width=True)
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer: 
                    rep_individual.to_excel(writer, index=False)
                st.download_button("📥 Descargar Reporte Nómina Maestro (.xlsx)", output.getvalue(), f"Nomina_Detallada_{tipo}_{date.today()}.xlsx")
            else:
                st.warning("⚠️ Asegúrate de tener el filtro superior en 'Ver Todo' para compilar el reporte de nómina consolidado por persona.")

if __name__ == "__main__":
    pantalla_programador()
