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
    """Clasifica al personal respetando tu estructura: 1 Supervisor, 1 Master, 3 Tec B, 7 Tec A por grupo."""
    df = df.copy()
    if 'GrupoAsignado' in df.columns: df = df.drop(columns=['GrupoAsignado'])
    
    supervisores = df[df['Cargo'].str.contains('Supervisor', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    m = df[df['Cargo'].str.contains('Master', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    ta = df[df['Cargo'].str.contains('Tecnico A', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    tb = df[df['Cargo'].str.contains('Tecnico B', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    
    res = []
    for i, g in enumerate(GRUPOS_TEC):
        # Distribución exacta según las cuotas solicitadas
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
                st.success("Distribución calculada según tu estructura de cuadrilla.")

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
            key="personal_dropdown_v12"
        )
        if st.button("💾 Guardar Estructura Definitiva en GitHub"):
            st.session_state.df_pers_ready = df_edit
            guardar_github(df_edit, "empleados_grupos.xlsx")

# =========================================================
# 4. MOTORES DE ASIGNACIÓN DETERMINISTAS MANTENIDOS
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
                
        for g in GRUPOS_TEC:
            turno_asignado = asig.get(g, "DESCANSO")
            # Dejamos las filas limpias por Grupo. El reporte de nómina se encargará de abrir los nombres reales.
            filas.append({"Fecha": fecha, "Sujeto": g, "Turno": turno_asignado})
                
    return pd.DataFrame(filas)

# =========================================================
# 5. MATEMÁTICA REAL DE HORAS Y ALARMAS DE FATIGA
# =========================================================
def calcular_delta_horas(inicio_str, fin_str):
    if inicio_str == "OFF" or fin_str == "OFF" or pd.isna(inicio_str) or pd.isna(fin_str): return 0.0
    try:
        t_ini = datetime.strptime(str(inicio_str).strip(), "%H:%M")
        t_fin = datetime.strptime(str(fin_str).strip(), "%H:%M")
        if t_fin >= t_ini:
            return (t_fin - t_ini).seconds / 3600.0
        else:
            return ((t_fin + timedelta(days=1)) - t_ini).seconds / 3600.0
    except:
        return 0.0

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
            if t_anterior == "T3" and t_actual == "T1":
                novedad = "Fatiga Crítica (T3 -> T1)"
            elif t_anterior == "T2" and t_actual == "T1":
                novedad = "Transición Corta (T2 -> T1)"
                
            if novedad:
                alertas.append({
                    "Sujeto": sujeto,
                    "Fecha": fecha_act,
                    "Semana": semana_num,
                    "Mensaje": f"🚨 **{novedad}** en '{sujeto}' el {fecha_act.strftime('%Y-%m-%d')}."
                })
    return alertas

def generar_reporte_detallado(df_final, tipo, config_horas, config_descansos, matriz_tecnicos_capacidades=None):
    """Cruza la malla de bloques con el listado de personas reales e inyecta al Supervisor en su grupo."""
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
                ini = config_horas.get(turno, {}).get("Inicio", "OFF")
                fin = config_horas.get(turno, {}).get("Fin", "OFF")
                
                filas_reporte.append({
                    "Fecha": m_fila['Fecha'].strftime('%Y-%m-%d'),
                    "Nombre": emp['Nombre'],
                    "Cargo": emp['Cargo'],
                    "GrupoAsignado": "Abordaje",
                    "Día Descanso Base": config_descansos.get("A", "Sábado"),
                    "Turno": turno,
                    "Hora Inicio": ini,
                    "Hora Fin": fin,
                    "Horas Prog": calcular_delta_horas(ini, fin)
                })
    else:
        # PROCESAMIENTO UNIFICADO: Todos los empleados (Técnicos y Supervisores) jalan el turno de su GrupoAsignado
        df_sub = df_emp[df_emp['GrupoAsignado'].isin(GRUPOS_TEC)]
        for _, emp in df_sub.iterrows():
            g_pertenece = emp['GrupoAsignado']
            cargo_actual = emp['Cargo']
            nombre_real = emp['Nombre']
            
            # Buscamos en la malla el registro correspondiente al bloque de su cuadrilla
            malla_bloque = df_final[df_final['Sujeto'] == g_pertenece]
                
            for _, m_fila in malla_bloque.iterrows():
                turno = m_fila['Turno']
                
                # Control paramétrico por cargo
                if matriz_tecnicos_capacidades and cargo_actual in matriz_tecnicos_capacidades:
                    limite_cupo = matriz_tecnicos_capacidades[cargo_actual].get(turno, 99)
                    if limite_cupo == 0 and turno not in ["DESCANSO", "COMPENSADO"]:
                        turno = "DISPONIBLE"

                ini = config_horas.get(turno, {}).get("Inicio", "OFF")
                fin = config_horas.get(turno, {}).get("Fin", "OFF")

                filas_reporte.append({
                    "Fecha": m_fila['Fecha'].strftime('%Y-%m-%d'),
                    "Nombre": nombre_real,
                    "Cargo": cargo_actual,
                    "GrupoAsignado": g_pertenece,
                    "Día Descanso Base": config_descansos.get(g_pertenece, "Domingo"),
                    "Turno": turno,
                    "Hora Inicio": ini,
                    "Hora Fin": fin,
                    "Horas Prog": calcular_delta_horas(ini, fin) # <--- Sma el tiempo real
                })
                
    return pd.DataFrame(filas_reporte)

# =========================================================
# 6. POP-UPS INTERACTIVOS (ST.DIALOG)
# =========================================================
@st.dialog("🛠️ Modificar Turno Específico")
def popup_cambio_manual(sujeto, fecha_str, turno_actual):
    st.write(f"Modificando la asignación de **{sujeto}** para el día **{fecha_str}**.")
    
    opciones_turnos = ["T1", "T2", "T3", "RELEVO", "T1 APOYO", "DESCANSO", "COMPENSADO", "DISPONIBLE"]
    nuevo_turno = st.selectbox("Seleccione el nuevo Turno:", opciones_turnos, index=opciones_turnos.index(turno_actual) if turno_actual in opciones_turnos else 5)
    
    if st.button("💾 Guardar Ajuste"):
        df = st.session_state.m_base
        idx = df[(df['Sujeto'] == sujeto) & (pd.to_datetime(df['Fecha']) == pd.to_datetime(fecha_str))].index
        if not idx.empty:
            st.session_state.m_base.at[idx[0], 'Turno'] = nuevo_turno
            st.success("¡Malla modificada!")
            st.rerun()

@st.dialog("🔍 Mitigación de Alerta de Fatiga Semanal", width="large")
def popup_resolver_fatiga(sujeto, fecha_novedad, semana_num):
    st.markdown(f"### Historial de la Semana {semana_num} para el Bloque: **{sujeto}**")
    
    df_malla = st.session_state.m_base.copy()
    df_malla['Fecha'] = pd.to_datetime(df_malla['Fecha'])
    df_malla['Semana'] = df_malla['Fecha'].dt.isocalendar().week
    
    df_semana = df_malla[(df_malla['Sujeto'] == sujeto) & (df_malla['Semana'] == semana_num)].sort_values(by="Fecha")
    
    pivot_sem = df_semana.pivot(index="Sujeto", columns="Fecha", values="Turno")
    pivot_sem.columns = [c.strftime('%Y-%m-%d') for c in pivot_sem.columns]
    st.dataframe(style_malla(pivot_sem), use_container_width=True)
    
    st.markdown("---")
    dia_modificar = st.selectbox("Día a cambiar:", list(pivot_sem.columns), index=list(pivot_sem.columns).index(fecha_novedad.strftime('%Y-%m-%d')) if fecha_novedad.strftime('%Y-%m-%d') in pivot_sem.columns else 0)
    opciones = ["T1", "T2", "T3", "RELEVO", "T1 APOYO", "DESCANSO", "COMPENSADO", "DISPONIBLE"]
    nuevo_t = st.selectbox("Nuevo Turno:", opciones, value="DESCANSO")
    
    if st.button("💾 Aplicar Corrección"):
        idx_maestro = st.session_state.m_base[(st.session_state.m_base['Sujeto'] == sujeto) & (pd.to_datetime(st.session_state.m_base['Fecha']) == pd.to_datetime(dia_modificar))].index
        if not idx_maestro.empty:
            st.session_state.m_base.at[idx_maestro[0], 'Turno'] = nuevo_t
            st.rerun()

# =========================================================
# 8. MÓDULO: IMPORTADOR EXTERNO (.MELT)
# =========================================================
def procesar_archivo_malla_externa(df_externo):
    try:
        columna_clave = df_externo.columns[0]
        df_externo = df_externo.rename(columns={columna_clave: "Sujeto"})
        df_plano = df_externo.melt(id_vars="Sujeto", var_name="Fecha", value_name="Turno")
        df_plano["Fecha"] = pd.to_datetime(df_plano["Fecha"])
        df_plano["Turno"] = df_plano["Turno"].fillna("DESCANSO").astype(str).str.strip().str.upper()
        return df_plano
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        return pd.DataFrame()

# =========================================================
# 9. INTERFAZ OPERATIVA PRINCIPAL
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
                    st.sidebar.success("📋 Malla externa acoplada.")
        except Exception as e: st.sidebar.error(f"Error: {str(e)}")

    tipo = st.sidebar.radio("Módulo Selección", ["Abordaje", "Técnicos"])
    
    matriz_tecnicos_cap = {}
    with st.expander("📊 Parámetros de Capacidad y Roles Requeridos", expanded=False):
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

    c1, c2 = st.columns(2)
    inicio, fin = c1.date_input("Inicio", date(2026, 7, 1)), c2.date_input("Fin", date(2026, 12, 31))
    
    if tipo == "Abordaje":
        ca, cb = st.columns(2)
        desc_data = {"A": ca.selectbox("Día Base G1 (1-13)", DIAS_ES, index=5), "B": cb.selectbox("Día Base G2 (14-27)", DIAS_ES, index=6)}
    else:
        desc_data = {}
        cols = st.columns(4)
        for i, g in enumerate(GRUPOS_TEC): desc_data[g] = cols[i].selectbox(f"Descanso {g}", DIAS_ES, index=(i+6)%7)

    if st.button("🚀 GENERAR MALLA SEMESTRAL CON ALGORITMO"):
        if tipo == "Abordaje": 
            st.session_state.m_base = generar_malla_abordaje_individual(inicio, fin, desc_data, cuota_desc_lv, cuota_t1, cuota_t2)
        else: 
            st.session_state.m_base = generar_malla_tecnicos(inicio, fin, desc_data)

    if 'm_base' in st.session_state and not st.session_state.m_base.empty:
        df_final = st.session_state.m_base.copy()
        
        st.write("---")
        st.subheader("📋 Malla de Turnos bajo Evaluación")
        
        with st.expander("🛠️ Panel de Ajuste Rápido (Pop-up Interactivo)", expanded=False):
            st.caption("Selecciona el sujeto y la fecha para sobreescribir la celda mediante un Pop-up.")
            col_p1, col_p2 = st.columns(2)
            suj_cambio = col_p1.selectbox("Sujeto / Bloque:", list(df_final["Sujeto"].unique()))
            f_cambio = col_p2.selectbox("Fecha del cambio:", [pd.to_datetime(d).strftime('%Y-%m-%d') for d in sorted(df_final["Fecha"].unique())])
            
            turno_act_row = df_final[(df_final['Sujeto'] == suj_cambio) & (pd.to_datetime(df_final['Fecha']) == pd.to_datetime(f_cambio))]['Turno'].values
            turno_actual_sel = turno_act_row[0] if len(turno_act_row) > 0 else "DESCANSO"
            if st.button("🪟 Abrir Ventana de Cambio"): popup_cambio_manual(suj_cambio, f_cambio, turno_actual_sel)

        opciones_vista = ["Ver Todo"] + (GRUPOS_TEC if tipo == "Técnicos" else ["Abordaje"])
        filtro_grupo = st.selectbox("🔍 Filtrar Malla por Bloque en Pantalla:", opciones_vista)
        
        df_display = df_final[df_final["Sujeto"].astype(str).str.contains(filtro_grupo, na=False)] if filtro_grupo != "Ver Todo" else df_final.copy()

        pivot = df_display.pivot(index="Sujeto", columns="Fecha", values="Turno").fillna("DESCANSO")
        pivot.columns = [p.strftime('%Y-%m-%d') if isinstance(p, (datetime, date, pd.Timestamp)) else str(p) for p in pivot.columns]
        
        # MUESTRA ÚNICAMENTE LAS 4 FILAS DE GRUPO PRINCIPALES (Sujetos limpios)
        pivot_clean = pivot[pivot.index.isin(GRUPOS_TEC or ["Abordaje"])] if tipo == "Técnicos" and filtro_grupo == "Ver Todo" else pivot
        st.dataframe(style_malla(pivot_clean), use_container_width=True)
        
        df_audit = df_final.copy()
        df_audit["Fecha"] = pd.to_datetime(df_audit["Fecha"])
        cob, h_sem = ejecutar_auditoria_completa(df_audit, config_h)
        
        st.write("---")
        t1, t2, t3, t4 = st.tabs(["📊 Cobertura Lograda", "⚠️ Alarmas de Fatiga Interactivas", "⚖️ Jornada 42h (Reforma)", "📋 Reporte Nómina Detallado"])
        
        with t1:
            st.dataframe(cob, use_container_width=True)
        with t2:
            lista_alertas = verificar_alarmas_cambios_drasticos(df_audit)
            if lista_alertas:
                for idx_al, alerta in enumerate(lista_alertas[:15]):
                    col_al1, col_al2 = st.columns([0.8, 0.2])
                    col_al1.markdown(alerta["Mensaje"])
                    if col_al2.button("🪟 Resolver Novedad", key=f"btn_al_{idx_al}_{alerta['Sujeto']}"):
                        popup_resolver_fatiga(alerta["Sujeto"], alerta["Fecha"], alerta["Semana"])
            else: st.success("✅ Sin alertas de fatiga.")
        with t3:
            st.dataframe(h_sem.style.highlight_between(left=42.01, right=100, color="#FADBD8"), use_container_width=True)
            
        with t4:
            # EL REPORTE AHORA SÍ PROCESA DINÁMICAMENTE AL SUPERVISOR DESGLOSADO
            rep_individual = generar_reporte_detallado(df_audit, tipo, config_h, desc_data, matriz_tecnicos_cap if tipo == "Técnicos" else None)
            if not rep_individual.empty:
                st.dataframe(rep_individual, use_container_width=True)
                
                st.subheader("📊 Resumen Consolidado de Horas Laboradas Semestrales")
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
                st.download_button("📥 Descargar Reporte Nómina Maestro (.xlsx)", output.getvalue(), f"Nomina_Completa_{tipo}_{date.today()}.xlsx")
