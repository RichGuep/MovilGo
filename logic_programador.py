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
# 3. GESTIÓN DE PERSONAL (ESTRUCTURA DE CUADRILLA FIJA)
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
        if i < len(supervisores):
            temp_sup = supervisores.iloc[[i]].copy(); temp_sup['GrupoAsignado'] = g; res.append(temp_sup)
        if i < len(m):
            temp_m = m.iloc[[i]].copy(); temp_m['GrupoAsignado'] = g; res.append(temp_m)
            
        temp_ta = ta.iloc[i*7:(i+1)*7].copy(); temp_ta['GrupoAsignado'] = g
        temp_tb = tb.iloc[i*3:(i+1)*3].copy(); temp_tb['GrupoAsignado'] = g
        res.extend([temp_ta, temp_tb])
        
    abo = df[df['Cargo'].str.contains('Abordaje|Auxiliar', case=False, na=False)].copy()
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
                st.success("Distribución cuadrilla guardada.")

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
            key="personal_dropdown_v20"
        )
        if st.button("💾 Guardar Estructura Definitiva en GitHub"):
            st.session_state.df_pers_ready = df_edit
            guardar_github(df_edit, "empleados_grupos.xlsx")

# =========================================================
# 4. MOTOR DE ASIGNACIÓN CON TRANSICIÓN PROGRESIVA RESTRINGIDA
# =========================================================
def generar_malla_tecnicos_avanzado(inicio, fin, descansos_iniciales, conceder_compensatorio, tipo_ciclo_descanso):
    df_emp = cargar_excel("empleados_grupos.xlsx")
    if df_emp.empty: return pd.DataFrame()
    
    filas, deudas = [], {g: 0 for g in GRUPOS_TEC}
    pool_descansos = ["Viernes", "Sábado", "Domingo", "Lunes"]
    supervisores_mapeo = df_emp[df_emp['Cargo'].str.contains('Supervisor', case=False, na=False)].set_index('GrupoAsignado')['Nombre'].to_dict()
    
    ultimos_turnos_grupos = {
        "Grupo 1": "T1",
        "Grupo 2": "T2",
        "Grupo 3": "T3",
        "Grupo 4": "T1 APOYO"
    }
    
    fue_descanso_ayer = {g: False for g in GRUPOS_TEC}

    for fecha in pd.date_range(inicio, fin):
        dia_n, sem, asig = DIAS_ES[fecha.weekday()], fecha.isocalendar()[1], {}
        
        delta_meses = (fecha.year - inicio.year) * 12 + (fecha.month - inicio.month)
        if tipo_ciclo_descanso == "Mensual": desplazamiento = delta_meses
        elif tipo_ciclo_descanso == "Trimestral": desplazamiento = delta_meses // 3
        else: desplazamiento = 0
            
        descansos_vivos = {}
        for idx_g, g in enumerate(GRUPOS_TEC):
            dia_inicial = descansos_iniciales[g]
            idx_inicial = pool_descansos.index(dia_inicial) if dia_inicial in pool_descansos else 0
            idx_rotado = (idx_inicial + desplazamiento) % len(pool_descansos)
            descansos_vivos[g] = pool_descansos[idx_rotado]

        # 1. Asignar Descansos Base
        gps_h = [g for g, d in descansos_vivos.items() if d == dia_n]
        if len(gps_h) > 1:
            idx = sem % len(gps_h); d_r = gps_h[idx]; asig[d_r] = "DESCANSO"
            for g in gps_h: 
                if g != d_r and conceder_compensatorio: deudas[g] += 1
        elif len(gps_h) == 1: asig[gps_h[0]] = "DESCANSO"
        
        # 2. Asignar Compensatorios
        if 0 <= fecha.weekday() <= 4 and conceder_compensatorio:
            g_d = sorted([g for g, d in deudas.items() if d > 0 and g not in asig], key=lambda x: deudas[x], reverse=True)
            if g_d: 
                asig[g_d[0]] = "COMPENSADO"
                deudas[g_d[0]] -= 1
        
        for g in GRUPOS_TEC:
            if asig.get(g) in ["DESCANSO", "COMPENSADO"]:
                fue_descanso_ayer[g] = True
        
        # 3. Distribución de Coberturas con Restricción Avanzada T1/T1 APOYO
        activos = [g for g in GRUPOS_TEC if g not in asig]
        grupos_estables = [g for g in activos if not fue_descanso_ayer[g]]
        grupos_mutables = [g for g in activos if fue_descanso_ayer[g]]
        
        for g in grupos_estables:
            asig[g] = ultimos_turnos_grupos[g]
            
        turnos_disponibles_pool = ["T1", "T2", "T3", "T1 APOYO"]
        for g_est in grupos_estables:
            t_ocupado = asig[g_est]
            if t_ocupado in turnos_disponibles_pool:
                turnos_disponibles_pool.remove(t_ocupado)
                
        for g_mut in sorted(grupos_mutables, key=lambda x: (GRUPOS_TEC.index(x) + sem) % 4):
            t_anterior = ultimos_turnos_grupos[g_mut]
            turno_encontrado = False
            
            for t_libre in turnos_disponibles_pool:
                es_valido = (
                    (t_anterior in ["T1", "T1 APOYO"] and t_libre in ["T2", "T3"]) or
                    (t_anterior == "T2" and t_libre == "T3") or
                    (t_anterior in ["DESCANSO", "COMPENSADO", "DISPONIBLE"])
                )
                
                if es_valido:
                    asig[g_mut] = t_libre
                    ultimos_turnos_grupos[g_mut] = t_libre
                    turnos_disponibles_pool.remove(t_libre)
                    turno_encontrado = True
                    break
            
            if not turno_encontrado:
                if t_anterior in turnos_disponibles_pool:
                    asig[g_mut] = t_anterior
                    turnos_disponibles_pool.remove(t_anterior)
                else:
                    asig[g_mut] = "DISPONIBLE"
                    ultimos_turnos_grupos[g_mut] = "DISPONIBLE"
                    
            fue_descanso_ayer[g_mut] = False

        for g in GRUPOS_TEC:
            turno_asignado = asig.get(g, "DESCANSO")
            filas.append({"Fecha": fecha, "Sujeto": g, "Turno": turno_asignado})
            if g in supervisores_mapeo:
                filas.append({"Fecha": fecha, "Sujeto": f"{g} - Supervisor: {supervisores_mapeo[g]}", "Turno": turno_asignado})
                
    return pd.DataFrame(filas)

# =========================================================
# 5. CÁLCULO DINÁMICO DE HORAS Y AUDITORÍAS
# =========================================================
def calcular_delta_horas(inicio_str, fin_str):
    if inicio_str == "OFF" or fin_str == "OFF" or pd.isna(inicio_str) or pd.isna(fin_str): return 0.0
    try:
        t_ini = datetime.strptime(str(inicio_str).strip(), "%H:%M")
        t_fin = datetime.strptime(str(fin_str).strip(), "%H:%M")
        if t_fin >= t_ini: return (t_fin - t_ini).seconds / 3600.0
        else: return ((t_fin + timedelta(days=1)) - t_ini).seconds / 3600.0
    except: return 0.0

def ejecutar_auditoria_completa(df_plano, config_horas):
    df_aud = df_plano.copy()
    df_aud["Fecha"] = pd.to_datetime(df_aud["Fecha"])
    
    cob = df_aud.groupby(["Fecha", "Turno"]).size().unstack(fill_value=0)
    for c in ["T1", "T2", "T3", "RELEVO", "T1 APOYO", "DESCANSO", "COMPENSADO", "DISPONIBLE"]:
        if c not in cob.columns: cob[c] = 0
        
    df_aud['Semana'] = df_aud['Fecha'].dt.isocalendar().week
    
    def asignar_horas_vivas(turno):
        ini = config_horas.get(turno, {}).get("Inicio", "OFF")
        fin = config_horas.get(turno, {}).get("Fin", "OFF")
        return calcular_delta_horas(ini, fin)
        
    df_aud['Horas'] = df_aud['Turno'].apply(asignar_horas_vivas)
    h_sem = df_aud.groupby(['Sujeto', 'Semana'])['Horas'].sum().unstack(fill_value=0)
    return cob, h_sem

def verificar_alarmas_cambios_drasticos(df_plano):
    df_plano = df_plano.sort_values(by=["Sujeto", "Fecha"])
    alertas = []
    for sujeto, group in df_plano.groupby("Sujeto"):
        lista_turnos = group["Turno"].tolist()
        lista_fechas = group["Fecha"].tolist()
        for i in range(1, len(lista_turnos)):
            t_anterior = lista_turnos[i-1]
            t_actual = lista_turnos[i]
            fecha_act = lista_fechas[i]
            semana_num = fecha_act.isocalendar()[1]
            
            novedad = None
            if t_anterior == "T3" and t_actual in ["T1", "T1 APOYO"]: 
                novedad = f"Fatiga Crítica (T3 -> {t_actual})"
            elif t_anterior == "T2" and t_actual in ["T1", "T1 APOYO"]: 
                novedad = f"Transición Corta (T2 -> {t_actual})"
                
            if novedad:
                alertas.append({
                    "Sujeto": sujeto, "Fecha": fecha_act, "Semana": semana_num,
                    "Mensaje": f"🚨 **{novedad}** en '{sujeto}' el {fecha_act.strftime('%Y-%m-%d')}."
                })
    return alertas

def generar_reporte_detallado(df_final, config_horas, config_descansos, matriz_tecnicos_capacidades=None):
    df_emp = cargar_excel("empleados_grupos.xlsx")
    if df_emp.empty: return pd.DataFrame()
    
    filas_reporte = []
    df_final['Fecha'] = pd.to_datetime(df_final['Fecha'])
    df_sub = df_emp[df_emp['GrupoAsignado'].isin(GRUPOS_TEC)]
    
    for _, emp in df_sub.iterrows():
        g_pertenece = emp['GrupoAsignado']
        cargo_actual = emp['Cargo']
        nombre_real = emp['Nombre']
        
        if "Supervisor" in str(cargo_actual):
            malla_bloque = df_final[df_final['Sujeto'] == f"{g_pertenece} - Supervisor: {nombre_real}"]
        else:
            malla_bloque = df_final[df_final['Sujeto'] == g_pertenece]
            
        for _, m_fila in malla_bloque.iterrows():
            turno = m_fila['Turno']
            if matriz_tecnicos_capacidades and cargo_actual in matriz_tecnicos_capacidades:
                limite_cupo = matriz_tecnicos_capacidades[cargo_actual].get(turno, 99)
                if limite_cupo == 0 and turno not in ["DESCANSO", "COMPENSADO"]: turno = "DISPONIBLE"

            ini = config_horas.get(turno, {}).get("Inicio", "OFF")
            fin = config_horas.get(turno, {}).get("Fin", "OFF")

            filas_reporte.append({
                "Fecha": m_fila['Fecha'].strftime('%Y-%m-%d'),
                "Nombre": nombre_real, "Cargo": cargo_actual, "GrupoAsignado": g_pertenece,
                "Día Descanso Base": config_descansos.get(g_pertenece, "Domingo"), "Turno": turno,
                "Hora Inicio": ini, "Hora Fin": fin, "Horas Prog": calcular_delta_horas(ini, fin)
            })
    return pd.DataFrame(filas_reporte)

# =========================================================
# 6. POP-UPS CON INTEGRACIÓN DE T1 APOYO (ST.DIALOG)
# =========================================================
@st.dialog("🛠️ Modificar Asignación de Turno", width="small")
def popup_cambio_manual_directo(sujeto, fecha_str, turno_actual):
    st.markdown(f"**Sujeto/Bloque:** `{sujeto}`")
    st.markdown(f"**Fecha Seleccionada:** `{fecha_str}`")
    st.markdown(f"**Turno Actual:** `{turno_actual}`")
    
    opciones_turnos = ["T1", "T2", "T3", "RELEVO", "T1 APOYO", "DESCANSO", "COMPENSADO", "DISPONIBLE"]
    nuevo_turno = st.selectbox("Seleccione el nuevo Turno de reemplazo:", opciones_turnos, index=opciones_turnos.index(turno_actual) if turno_actual in opciones_turnos else 5)
    
    if st.button("💾 Guardar y Aplicar Cambio"):
        t_ant_eval = "T1" if turno_actual in ["T1", "T1 APOYO"] else turno_actual
        t_nue_eval = "T1" if nuevo_turno in ["T1", "T1 APOYO"] else nuevo_turno

        if t_ant_eval in ["T1", "T2", "T3"] and t_nue_eval in ["T1", "T2", "T3"]:
            es_valido_manual = (
                (t_ant_eval == "T1" and t_nue_eval in ["T2", "T3"]) or
                (t_ant_eval == "T2" and t_nue_eval == "T3") or
                (t_ant_eval == t_nue_eval)
            )
            if not es_valido_manual:
                st.error(f"❌ **Cambio Prohibido:** No puedes retroceder el turno de `{turno_actual}` a `{nuevo_turno}`. Se violan las reglas de transición progresiva.")
                return 
                
        df = st.session_state.m_base
        idx = df[(df['Sujeto'] == sujeto) & (pd.to_datetime(df['Fecha']) == pd.to_datetime(fecha_str))].index
        if not idx.empty:
            st.session_state.m_base.at[idx[0], 'Turno'] = nuevo_turno
            st.toast(f"✅ Turno modificado exitosamente.")
            st.rerun()

def procesar_archivo_malla_externa(df_externo):
    try:
        columna_clave = df_externo.columns[0]
        df_externo = df_externo.rename(columns={columna_clave: "Sujeto"})
        df_plano = df_externo.melt(id_vars="Sujeto", var_name="Fecha", value_name="Turno")
        df_plano["Fecha"] = pd.to_datetime(df_plano["Fecha"])
        df_plano["Turno"] = df_plano["Turno"].fillna("DESCANSO").astype(str).str.strip().str.upper()
        return df_plano
    except Exception as e: return pd.DataFrame()

# =========================================================
# 7. INTERFAZ OPERATIVA PRINCIPAL
# =========================================================
def pantalla_programador():
    st.sidebar.markdown("---")
    st.sidebar.subheader("📥 Carga de Mallas Externas")
    archivo_malla = st.sidebar.file_uploader("Arrastra aquí el Excel de la Malla (.xlsx):", type=["xlsx", "xls"])
    
    if archivo_malla is not None:
        try:
            df_cargado_raw = pd.read_excel(archivo_malla)
            if st.sidebar.button("🔄 Importar y Evaluar Malla"):
                df_aplanado = procesar_archivo_malla_externa(df_cargado_raw)
                if not df_aplanado.empty:
                    st.session_state.m_base = df_aplanado
                    st.sidebar.success("📋 Malla acoplada.")
        except Exception as e: st.sidebar.error(f"Error: {str(e)}")

    st.markdown("### ⚙️ Panel de Parámetros Avanzados de Cuadrilla")
    conceder_compensatorio = st.checkbox("⚖️ Otorgar y calcular días Compensatorios por Cobertura Dominical (Reforma Laboral)", value=True)
    tipo_ciclo_descanso = st.selectbox("🔄 Ciclo de Rotación Temporal para los días de Descanso Base:", options=["Fijo sin rotación", "Mensual", "Trimestral"])

    matriz_tecnicos_cap = {}
    with st.expander("📊 Parámetros de Capacidad por Cargo y Turno", expanded=False):
        cargos_disponibles = ["Master", "Tecnico A", "Tecnico B", "Supervisor"]
        cargos_seleccionados = st.multiselect("💼 Seleccione los cargos a parametrizar:", options=cargos_disponibles, default=["Master", "Tecnico A", "Supervisor"])
        turnos_claves = ["T1", "T2", "T3", "RELEVO", "T1 APOYO", "DISPONIBLE"]
        for cargo in cargos_seleccionados:
            st.markdown(f"🔹 **Dotación de {cargo} por Grupo en cada Turno:**")
            cols_j = st.columns(6)
            matriz_tecnicos_cap[cargo] = {}
            for idx, t in enumerate(turnos_claves):
                with cols_j[idx]:
                    val_def = 1 if cargo == "Supervisor" else (2 if t in ["T1", "T2"] else (1 if t == "T3" else 0))
                    cant = st.number_input(f"{t}", min_value=0, max_value=20, value=val_def, key=f"req_t_{cargo}_{t}")
                    matriz_tecnicos_cap[cargo][t] = cant
            st.caption("---")

    with st.expander("⏰ Configuración Rangos de Jornada (Basado en Horas Reales)", expanded=False):
        config_h = {}
        t_l = ["T1", "T2", "T3", "RELEVO", "T1 APOYO", "DISPONIBLE"]
        def_h = {"T1": [time(5,30), time(13,30)], "T2": [time(13,30), time(21,30)], "T3": [time(21,30), time(5,30)], "RELEVO": [time(8,0), time(15,0)], "T1 APOYO": [time(7,0), time(14,0)], "DISPONIBLE": [time(8,0), time(15,0)]}
        cols = st.columns(3)
        for i, t in enumerate(t_l):
            with cols[i%3]:
                ini = st.time_input(f"Inicia {t}", def_h[t][0], key=f"i{t}"); fin = st.time_input(f"Fin {t}", def_h[t][1], key=f"f{t}")
                config_h[t] = {"Inicio": ini.strftime("%H:%M"), "Fin": fin.strftime("%H:%M")}
        config_h["DESCANSO"] = config_h["COMPENSADO"] = {"Inicio": "OFF", "Fin": "OFF"}

    st.write("---")
    c1, c2 = st.columns(2)
    inicio, fin = c1.date_input("Inicio", date(2026, 7, 1)), c2.date_input("Fin", date(2026, 12, 31))
    
    st.write("##### 🗓️ Mapeo Inicial del Descanso Base de Cuadrillas:")
    cols = st.columns(4)
    desc_data = {"Grupo 1": cols[0].selectbox("Descanso G1", DIAS_ES, index=4), "Grupo 2": cols[1].selectbox("Descanso G2", DIAS_ES, index=5), "Grupo 3": cols[2].selectbox("Descanso G3", DIAS_ES, index=6), "Grupo 4": cols[3].selectbox("Descanso G4", DIAS_ES, index=0)}

    if st.button("🚀 GENERAR MALLA CON REGLAS Y ROTACIÓN DE DESCANSOS"):
        st.session_state.m_base = generar_malla_tecnicos_avanzado(inicio, fin, desc_data, conceder_compensatorio, tipo_ciclo_descanso)

    if 'm_base' in st.session_state and not st.session_state.m_base.empty:
        df_final = st.session_state.m_base.copy()
        df_audit = df_final.copy()
        df_audit["Fecha"] = pd.to_datetime(df_audit["Fecha"])
        
        cob, h_sem = ejecutar_auditoria_completa(df_audit, config_h)
        
        dias_sin_t1 = cob[cob["T1"] == 0].index.tolist()
        dias_sin_t2 = cob[cob["T2"] == 0].index.tolist()
        dias_sin_t3 = cob[cob["T3"] == 0].index.tolist()
        fechas_novedad = sorted(list(set(dias_sin_t1 + dias_sin_t2 + dias_sin_t3)))
        
        if fechas_novedad:
            st.error(f"⚠️ **Novedad en Cobertura 24/7:** Hay {len(fechas_novedad)} días desprotegidos. Fechas críticas: {[d.strftime('%Y-%m-%d') for d in fechas_novedad[:5]]}.")
        else:
            st.success("✅ **Malla 100% Protegida:** Todos los días cumplen con el soporte operativo 24/7 sin novedad.")
            
        st.write("---")
        st.subheader("📋 Malla de Turnos Operativa e Interactiva")
        st.caption("🔒 **Filtro de Seguridad Activo:** Restricción estricta de retrocesos horarios aplicada sobre T1 y T1 APOYO.")
        
        pivot = df_final.pivot(index="Sujeto", columns="Fecha", values="Turno").fillna("DESCANSO")
        pivot.columns = [p.strftime('%Y-%m-%d') if isinstance(p, (datetime, date, pd.Timestamp)) else str(p) for p in pivot.columns]
        
        fila_semaforo = {}
        for col_fecha in pivot.columns:
            col_dt = pd.to_datetime(col_fecha)
            t1_ok = cob.at[col_dt, "T1"] > 0 if col_dt in cob.index else False
            t2_ok = cob.at[col_dt, "T2"] > 0 if col_dt in cob.index else False
            t3_ok = cob.at[col_dt, "T3"] > 0 if col_dt in cob.index else False
            fila_semaforo[col_fecha] = "✅ OK 24/7" if (t1_ok and t2_ok and t3_ok) else "❌ FALTA TURNO"
                
        df_semaforo_row = pd.DataFrame([fila_semaforo], index=["🔍 AUDITORÍA 24/7"])
        pivot_completa_con_semaforo = pd.concat([pivot, df_semaforo_row])
        
        # --- 🛠️ COMPONENTE CORREGIDO SEGURO PARA PYTHON 3.14 / NUEVO STREAMLIT ---
        df_editada_vista = st.dataframe(
            style_malla(pivot_completa_con_semaforo),
            use_container_width=True,
            on_select="rerun",
            key="malla_interactiva_clics"
        )
        
        # Procesamiento adaptado del diccionario interno de Streamlit
        seleccion_dict = st.session_state.malla_interactiva_clics.get("selection", {})
        seleccionada = seleccion_dict.get("rows", [])
        columnas_sel = seleccion_dict.get("columns", [])
        
        if seleccionada and columnas_sel:
            fila_idx = seleccionada[0]
            col_idx = columnas_sel[0]
            
            sujeto_clic = pivot_completa_con_semaforo.index[fila_idx]
            fecha_clic = pivot_completa_con_semaforo.columns[col_idx]
            turno_clic = pivot_completa_con_semaforo.at[sujeto_clic, fecha_clic]
            
            if sujeto_clic != "🔍 AUDITORÍA 24/7":
                popup_cambio_manual_directo(sujeto_clic, fecha_clic, turno_clic)

        st.write("---")
        t1, t2, t3 = st.tabs(["📊 Distribución Diaria", "⚠️ Alarmas de Fatiga", "📋 Reporte Nómina Detallado"])
        with t1: st.dataframe(cob, use_container_width=True)
        with t2:
            lista_alertas = verificar_alarmas_cambios_drasticos(df_audit)
            if lista_alertas:
                for idx_al, alerta in enumerate(lista_alertas[:15]):
                    st.markdown(alerta["Mensaje"])
            else: st.success("✅ Sin de alertas de fatiga.")
        with t3:
            rep_individual = generar_reporte_detallado(df_audit, config_h, desc_data, matriz_tecnicos_cap)
            if not rep_individual.empty:
                st.dataframe(rep_individual, use_container_width=True)
                r_col1, r_col2 = st.columns(2)
                with r_col1:
                    resumen_persona = rep_individual.groupby("Nombre")["Horas Prog"].sum().reset_index()
                    resumen_persona.columns = ["Nombre Empleado", "Total Horas Laboradas"]
                    st.dataframe(resumen_persona.style.background_gradient(cmap="Blues", subset=["Total Horas Laboradas"]), use_container_width=True)
                with r_col2:
                    resumen_grupo = rep_individual.groupby("GrupoAsignado")["Horas Prog"].sum().reset_index()
                    resumen_grupo.columns = ["Grupo / Cuadrilla", "Total Horas Acumuladas"]
                    st.dataframe(resumen_grupo.style.background_gradient(cmap="Purples", subset=["Total Horas Acumuladas"]), use_container_width=True)
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer: 
                    rep_individual.to_excel(writer, sheet_name="Detalle_Dias", index=False)
                    resumen_persona.to_excel(writer, sheet_name="Total_Persona", index=False)
                    resumen_grupo.to_excel(writer, sheet_name="Total_Grupo", index=False)
                st.download_button("📥 Descargar Reporte Nómina Maestro (.xlsx)", output.getvalue(), f"Nomina_Completa_Tecnicos_{date.today()}.xlsx")
