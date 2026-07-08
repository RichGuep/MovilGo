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
festivos_co = holidays.Colombia(years=range(2025, 2030))
GRUPOS_TEC = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]

COLORES_MAP = {
    "T1": "#D6EAF8", "T2": "#D5F5E3", "T3": "#FADBD8", "T4": "#FCF3CF",
    "RELEVO": "#E8DAEF", "DISPONIBLE": "#EAEDED",
    "DESCANSO": "#1B2631", "COMPENSADO": "#2E4053",
    "✅ OK 24/7": "#2ECC71", "❌ FALTA TURNO": "#E74C3C"
}

def style_malla(df_pivot):
    """Aplica el formato visual con colores de turnos y resalta Sábados, Domingos y Festivos de Colombia."""
    styles = pd.DataFrame('', index=df_pivot.index, columns=df_pivot.columns)
    for col in df_pivot.columns:
        es_fin_semana = False
        es_festivo = False
        try:
            fecha_dt = pd.to_datetime(col)
            if fecha_dt.weekday() in [5, 6]: es_fin_semana = True
            if fecha_dt in festivos_co: es_festivo = True
        except: pass

        for idx in df_pivot.index:
            val = df_pivot.at[idx, col]
            key = str(val).strip() if val and str(val).strip() != "" else "DESCANSO"
            bg = COLORES_MAP.get(key, "#1B2631")
            txt = "white" if key in ["DESCANSO", "COMPENSADO", "✅ OK 24/7", "❌ FALTA TURNO"] else "#17202A"
            
            border_style = "0.5px solid #D5DBDB"
            if es_festivo: border_style = "2px solid #E67E22"
            elif es_fin_semana: border_style = "1.5px solid #7F8C8D"
                
            styles.at[idx, col] = f'background-color: {bg}; color: {txt}; font-weight: 700; border: {border_style};'
    return df_pivot.style.apply(lambda _: styles, axis=None)

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
# 4. MOTOR DE ASIGNACIÓN CON PROTECCIÓN CIRCADIANA ESTRICTA
# =========================================================
def generar_malla_tecnicos_avanzado(inicio, fin, descansos_iniciales, conceder_compensatorio, tipo_ciclo_descanso, activar_t4=False):
    df_emp = cargar_excel("empleados_grupos.xlsx")
    if df_emp.empty: return pd.DataFrame()
    
    filas, deudas = [], {g: 0 for g in GRUPOS_TEC}
    pool_descansos = ["Viernes", "Sábado", "Domingo", "Lunes"]
    
    # Rastrear el último turno real trabajado por cada grupo para memoria de retorno
    ultimo_turno_trabajado = {g: "T1" for g in GRUPOS_TEC}

    for fecha in pd.date_range(inicio, fin):
        dia_n, sem, asig = DIAS_ES[fecha.weekday()], fecha.isocalendar()[1], {}
        delta_meses = (fecha.year - inicio.year) * 12 + (fecha.month - inicio.month)
        fecha_str = fecha.strftime('%Y-%m-%d')
        es_fin_semana = (fecha.weekday() in [5, 6])
        
        if tipo_ciclo_descanso == "Mensual": desplazamiento = delta_meses
        elif tipo_ciclo_descanso == "Trimestral": desplazamiento = delta_meses // 3
        else: desplazamiento = 0
            
        descansos_vivos = {}
        for idx_g, g in enumerate(GRUPOS_TEC):
            dia_inicial = descansos_iniciales[g]
            idx_inicial = pool_descansos.index(dia_inicial) if dia_inicial in pool_descansos else 0
            idx_rotado = (idx_inicial + desplazamiento) % len(pool_descansos)
            descansos_vivos[g] = pool_descansos[idx_rotado]

        # Descansos Base
        gps_h = [g for g, d in descansos_vivos.items() if d == dia_n]
        if len(gps_h) > 1:
            idx = sem % len(gps_h); d_r = gps_h[idx]; asig[d_r] = "DESCANSO"
            for g in gps_h: 
                if g != d_r and conceder_compensatorio: deudas[g] += 1
        elif len(gps_h) == 1: asig[gps_h[0]] = "DESCANSO"
        
        # Compensatorios L-V
        if 0 <= fecha.weekday() <= 4 and conceder_compensatorio:
            g_d = sorted([g for g, d in deudas.items() if d > 0 and g not in asig], key=lambda x: deudas[x], reverse=True)
            if g_d: 
                asig[g_d[0]] = "COMPENSADO"
                deudas[g_d[0]] -= 1
        
        # Determinar secuencia base de turnos activa según el botón y el día
        if activar_t4 and not es_fin_semana:
            secuencia_turnos = ["T1", "T2", "T3", "T4"]
            turnos_operativos_necesarios = ["T1", "T2", "T3", "T4"]
        else:
            secuencia_turnos = ["T1", "T2", "T3", "DISPONIBLE"]
            turnos_operativos_necesarios = ["T1", "T2", "T3"]
        
        # Asignación Teórica Semanal
        for idx_g, g in enumerate(GRUPOS_TEC):
            if g not in asig:
                idx_turno = (sem + idx_g) % len(secuencia_turnos)
                turno_propuesto = secuencia_turnos[idx_turno]
                
                # 🔥 BLINDAJE MOTOR AUTOMÁTICO (Filtro Circadiano de Retorno)
                # Si viene de un turno nocturno pesado, bloqueamos el retorno a turnos de la mañana/tarde
                if ultimo_turno_trabajado[g] in ["T3", "T4"] and turno_propuesto in ["T1", "T2", "DISPONIBLE"]:
                    # Forzar una transición segura o mantenerlo en el ciclo superior nocturno
                    turno_propuesto = "T3" if "T3" in turnos_operativos_necesarios else "T2"
                
                asig[g] = turno_propuesto

        # Algoritmo de Rescate Automático de Cobertura 24/7
        turnos_cubiertos_hoy = [asig[g] for g in GRUPOS_TEC if asig[g] in turnos_operativos_necesarios]
        turnos_faltantes = [t for t in turnos_operativos_necesarios if t not in turnos_cubiertos_hoy]
        
        if turnos_faltantes:
            for g in GRUPOS_TEC:
                if asig.get(g) == "DISPONIBLE":
                    asig[g] = turnos_faltantes[0]
                    break

        # Guardar en memoria el turno de hoy si fue de trabajo real
        for g in GRUPOS_TEC:
            if asig[g] in ["T1", "T2", "T3", "T4"]:
                ultimo_turno_trabajado[g] = asig[g]

        # Forzar Persistencia de cambios manuales macro
        for g in GRUPOS_TEC:
            turno_final = asig.get(g, "DESCANSO")
            if "ajustes_manuales" in st.session_state and (g, fecha_str) in st.session_state.ajustes_manuales:
                turno_final = st.session_state.ajustes_manuales[(g, fecha_str)]
            filas.append({"Fecha": fecha, "Sujeto": g, "Turno": turno_final})
                
    return pd.DataFrame(filas)

# =========================================================
# 5. CÁLCULO DE RECARGOS Y HORAS EXTRAS INTEGRAL (REFORMA)
# =========================================================
def obtener_minutos_desde_time(objeto_hora):
    if objeto_hora is None: return None
    if isinstance(objeto_hora, time): return objeto_hora.hour * 60 + objeto_hora.minute
    s = str(objeto_hora).strip().upper()
    if s in ["OFF", "NAN", ""]: return None
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.hour * 60 + dt.minute
        except: pass
    return None

def calcular_metricas_reforma(inicio_str, fin_str, fecha_ts):
    if pd.isna(inicio_str) or pd.isna(fin_str): return 0.0, 0.0, 0.0
    s_ini = str(inicio_str).strip().upper()
    s_fin = str(fin_str).strip().upper()
    if "OFF" in s_ini or "OFF" in s_fin: return 0.0, 0.0, 0.0

    min_inicio = obtener_minutos_desde_time(inicio_str)
    min_fin = obtener_minutos_desde_time(fin_str)
    if min_inicio is None or min_fin is None: return 0.0, 0.0, 0.0

    if min_fin >= min_inicio:
        minutos_totales = min_fin - min_inicio
    else:
        minutos_totales = (1440 - min_inicio) + min_fin
        
    total_horas = minutos_totales / 60.0
    horas_extras = max(0.0, total_horas - 7.0)
    
    minutos_nocturnos = 0
    min_actual = min_inicio
    for _ in range(int(minutos_totales)):
        min_ciclo = min_actual % 1440
        if min_ciclo >= 1140 or min_ciclo < 360: minutos_nocturnos += 1
        min_actual += 1
        
    horas_nocturnas = minutos_nocturnos / 60.0
    return round(total_horas, 2), round(horas_extras, 2), round(horas_nocturnas, 2)

def procesar_archivo_malla_externa(df_externo):
    try:
        columna_clave = df_externo.columns[0]
        df_externo = df_externo.rename(columns={columna_clave: "Sujeto"})
        df_plano = df_externo.melt(id_vars="Sujeto", var_name="Fecha", value_name="Turno")
        df_plano["Fecha"] = pd.to_datetime(df_plano["Fecha"])
        df_plano["Turno"] = df_plano["Turno"].fillna("DESCANSO").astype(str).str.strip().str.upper()
        return df_plano
    except Exception as e:
        st.sidebar.error(f"Estructura inválida: {str(e)}")
        return pd.DataFrame()

def ejecutar_auditoria_completa(df_plano, config_horas):
    df_aud = df_plano.copy()
    df_aud["Fecha"] = pd.to_datetime(df_aud["Fecha"])
    cob = df_aud.groupby(["Fecha", "Turno"]).size().unstack(fill_value=0)
    for c in ["T1", "T2", "T3", "T4", "RELEVO", "DESCANSO", "COMPENSADO", "DISPONIBLE"]:
        if c not in cob.columns: cob[c] = 0
    return cob

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
            
            if t_anterior in ["T3", "T4"] and t_actual in ["T1", "T2", "DISPONIBLE"]: 
                alertas.append({"Sujeto": sujeto, "Mensaje": f"🚨 **Violación de Descanso Circadiano ({t_anterior} -> {t_actual})** en '{sujeto}' el {fecha_act.strftime('%Y-%m-%d')}."})
            elif t_anterior == "T2" and t_actual == "T1":
                alertas.append({"Sujeto": sujeto, "Mensaje": f"⚠️ **Transición Corta Inválida (T2 -> T1)** en '{sujeto}' el {fecha_act.strftime('%Y-%m-%d')}."})
    return alertas

def generar_reporte_detallado(df_final, config_horas, config_descansos, activar_t4=False):
    df_emp = cargar_excel("empleados_grupos.xlsx")
    if df_emp.empty: return pd.DataFrame()
    
    filas_reporte = []
    df_final['Fecha'] = pd.to_datetime(df_final['Fecha'])
    df_sub = df_emp[df_emp['GrupoAsignado'].isin(GRUPOS_TEC)].copy()
    df_sub['idx_cargo'] = df_sub.groupby(['GrupoAsignado', 'Cargo']).cumcount()
    
    col_cedula = 'Cedula' if 'Cedula' in df_sub.columns else ('Cédula' if 'Cédula' in df_sub.columns else None)

    for _, emp in df_sub.iterrows():
        g_pertenece = emp['GrupoAsignado']
        cargo_actual = emp['Cargo']
        nombre_real = emp['Nombre']
        idx_persona_cargo = emp['idx_cargo']
        cedula_real = str(emp[col_cedula]) if col_cedula else "N/A"
        
        malla_bloque = df_final[df_final['Sujeto'] == g_pertenece]
            
        for _, m_fila in malla_bloque.iterrows():
            turno = m_fila['Turno']
            fecha_dt = m_fila['Fecha']
            fecha_str = fecha_dt.strftime('%Y-%m-%d')
            es_fin_semana = (fecha_dt.weekday() in [5, 6])
            
            if turno == "DISPONIBLE":
                if activar_t4 and not es_fin_semana:
                    turnos_reparto_apoyo = ["T1", "T2", "T3"]
                else:
                    turnos_reparto_apoyo = ["T1", "T2"]
                turno = turnos_reparto_apoyo[idx_persona_cargo % len(turnos_reparto_apoyo)]

            if "m_personas_editada" in st.session_state and (nombre_real, fecha_str) in st.session_state.m_personas_editada:
                turno = st.session_state.m_personas_editada[(nombre_real, fecha_str)]

            info_turno = config_horas.get(turno, {"Inicio": "OFF", "Fin": "OFF"})
            ini = info_turno.get("Inicio", "OFF")
            fin = info_turno.get("Fin", "OFF")

            h_prog, h_extra, h_noc = calcular_metricas_reforma(ini, fin, fecha_dt)

            filas_reporte.append({
                "Fecha": fecha_str, 
                "Cedula": cedula_real,
                "Nombre": nombre_real, 
                "Cargo": cargo_actual, 
                "Grupo Asignado": g_pertenece,
                "Día Descanso Asignado": config_descansos.get(g_pertenece, "Domingo"),
                "Turno realizado": turno, 
                "Hora inicio": ini, 
                "Hora fin": fin, 
                "Horas Programado": h_prog,
                "Horas Extras": h_extra,
                "Recargos Nocturnos": h_noc,
                "Mes": fecha_dt.strftime('%B'), 
                "Semana": fecha_dt.isocalendar()[1]
            })
    return pd.DataFrame(filas_reporte)

# =========================================================
# 6. POP-UP FLOTANTE CONTROLADO CON VALIDADOR DE RESTRICCIONES
# =========================================================
@st.dialog("🛠️ Forzar Cambio de Turno Específico", width="small")
def popup_forzar_ajuste_fecha(fecha_solicitada, opciones_sujetos, es_modo_persona=False):
    st.markdown(f"📅 **Fecha de Operación:** `{fecha_solicitada}`")
    sujeto_sel = st.selectbox("🎯 Seleccione el Elemento a Modificar:", opciones_sujetos)
    opciones_turnos = ["T1", "T2", "T3", "T4", "RELEVO", "DESCANSO", "COMPENSADO", "DISPONIBLE"]
    nuevo_turno = st.selectbox("🆕 Turno Destino Asignado:", opciones_turnos, index=0)
    
    if st.button("💾 Guardar y Re-calcular Malla"):
        fecha_actual_dt = pd.to_datetime(fecha_solicitada)
        fecha_ayer_str = (fecha_actual_dt - timedelta(days=1)).strftime('%Y-%m-%d')
        
        turno_ayer = "DESCANSO"
        if es_modo_persona:
            if "m_personas_editada" in st.session_state and (sujeto_sel, fecha_ayer_str) in st.session_state.m_personas_editada:
                turno_ayer = st.session_state.m_personas_editada[(sujeto_sel, fecha_ayer_str)]
        else:
            if "ajustes_manuales" in st.session_state and (sujeto_sel, fecha_ayer_str) in st.session_state.ajustes_manuales:
                turno_ayer = st.session_state.ajustes_manuales[(sujeto_sel, fecha_ayer_str)]

        # 🚨 RESTRICCIÓN RADICAL EN EL POP-UP MANUAL
        if turno_ayer in ["T3", "T4"] and nuevo_turno in ["T1", "T2", "DISPONIBLE"]:
            st.error(f"❌ **Bloqueo de Seguridad Circadiana ({turno_ayer} ➡️ {nuevo_turno}):** El sistema no permite programar un turno diurno inmediatamente después de una jornada nocturna o de madrugada. Forzaría un salto descendente peligroso.")
            return

        if turno_ayer == "T2" and nuevo_turno == "T1":
            st.error("❌ **Bloqueo de Dirección:** Las transiciones de turnos deben ser estrictamente ascendentes hacia adelante (T2 no puede bajar a T1).")
            return

        if es_modo_persona: 
            st.session_state.m_personas_editada[(sujeto_sel, fecha_solicitada)] = nuevo_turno
        else: 
            st.session_state.ajustes_manuales[(sujeto_sel, fecha_solicitada)] = nuevo_turno
            
        st.success("¡Turno validado y registrado exitosamente!")
        st.rerun()

# =========================================================
# 7. INTERFAZ OPERATIVA PRINCIPAL
# =========================================================
def pantalla_programador():
    if "ajustes_manuales" not in st.session_state: st.session_state.ajustes_manuales = {}
    if "m_personas_editada" not in st.session_state: st.session_state.m_personas_editada = {}

    st.sidebar.markdown("---")
    st.sidebar.subheader("📥 Carga de Mallas Externas")
    archivo_malla = st.sidebar.file_uploader("Arrastra aquí el Excel de la Malla (.xlsx):", type=["xlsx", "xls"])
    
    if archivo_malla is not None:
        try:
            df_cargado_raw = pd.read_excel(archivo_malla)
            if st.sidebar.button("🔄 Importar y Evaluar Malla"):
                df_aplanado = procesar_archivo_malla_externa(df_cargado_raw)
                if not df_aplanado.empty:
                    st.session_state.ajustes_manuales = {}
                    st.session_state.m_personas_editada = {}
                    for _, row in df_aplanado.iterrows():
                        f_str = pd.to_datetime(row["Fecha"]).strftime('%Y-%m-%d')
                        st.session_state.ajustes_manuales[(row["Sujeto"], f_str)] = row["Turno"]
                    st.sidebar.success("✅ Malla importada con éxito.")
                    st.rerun()
        except Exception as e: st.sidebar.error(f"Error de lectura: {str(e)}")

    st.markdown("### ⚙️ Panel de Parámetros Avanzados de Cuadrilla")
    conceder_compensatorio = st.checkbox("⚖️ Otorgar días Compensatorios por Cobertura Dominical (Reforma Laboral)", value=True)
    tipo_ciclo_descanso = st.selectbox("🔄 Ciclo de Rotación Temporal para los días de Descanso Base:", options=["Fijo sin rotación", "Mensual", "Trimestral"])
    
    activar_t4 = st.toggle("⚡ Activar Esquema de Cuadrilla Eficiente (T4 - 7 Horas L-V)", value=False)

    with st.expander("⏰ Configuración Rangos de Jornada", expanded=False):
        config_h = {}
        t_l = ["T1", "T2", "T3", "T4", "RELEVO", "DISPONIBLE"]
        
        def_h = {
            "T1": [time(4,0), time(11,0)], 
            "T2": [time(11,0), time(18,0)], 
            "T3": [time(15,0), time(22,0)], 
            "T4": [time(21,0), time(4,0)], 
            "RELEVO": [time(8,0), time(15,0)], 
            "DISPONIBLE": [time(8,0), time(15,0)]
        }
        cols = st.columns(3)
        for i, t in enumerate(t_l):
            with cols[i%3]:
                ini = st.time_input(f"Inicia {t}", def_h[t][0], key=f"i{t}"); fin = st.time_input(f"Fin {t}", def_h[t][1], key=f"f{t}")
                config_h[t] = {"Inicio": ini.strftime("%H:%M"), "Fin": fin.strftime("%H:%M")}
        config_h["DESCANSO"] = config_h["COMPENSADO"] = {"Inicio": "OFF", "Fin": "OFF"}

    st.write("---")
    c1, c2 = st.columns(2)
    inicio, fin = c1.date_input("Inicio Planificación", date(2026, 7, 1)), c2.date_input("Fin Planificación", date(2026, 12, 31))
    cols = st.columns(4)
    desc_data = {"Grupo 1": cols[0].selectbox("Descanso G1", DIAS_ES, index=4), "Grupo 2": cols[1].selectbox("Descanso G2", DIAS_ES, index=5), "Grupo 3": cols[2].selectbox("Descanso G3", DIAS_ES, index=6), "Grupo 4": cols[3].selectbox("Descanso G4", DIAS_ES, index=0)}

    if 'm_base' not in st.session_state:
        st.session_state.m_base = generar_malla_tecnicos_avanzado(inicio, fin, desc_data, conceder_compensatorio, tipo_ciclo_descanso, activar_t4)

    if st.button("🚀 GENERAR MALLA CON REGLAS Y ROTACIÓN DE DESCANSOS"):
        st.session_state.ajustes_manuales = {}
        st.session_state.m_personas_editada = {}
        st.session_state.m_base = generar_malla_tecnicos_avanzado(inicio, fin, desc_data, conceder_compensatorio, tipo_ciclo_descanso, activar_t4)

    if 'm_base' in st.session_state and not st.session_state.m_base.empty:
        df_final = generar_malla_tecnicos_avanzado(inicio, fin, desc_data, conceder_compensatorio, tipo_ciclo_descanso, activar_t4)
        df_audit = df_final.copy()
        df_audit["Fecha"] = pd.to_datetime(df_audit["Fecha"])
        
        cob = ejecutar_auditoria_completa(df_audit, config_h)
        
        fechas_novedad = []
        for d_f in cob.index:
            es_f_s = (d_f.weekday() in [5, 6])
            if cob.at[d_f, "T1"] == 0 or cob.at[d_f, "T2"] == 0:
                fechas_novedad.append(d_f)
            elif es_f_s and cob.at[d_f, "T3"] == 0:
                fechas_novedad.append(d_f)
            elif not es_f_s and activar_t4 and (cob.at[d_f, "T3"] == 0 or cob.at[d_f, "T4"] == 0):
                fechas_novedad.append(d_f)
            elif not es_f_s and not activar_t4 and cob.at[d_f, "T3"] == 0:
                fechas_novedad.append(d_f)
        
        fechas_novedad = sorted(list(set(fechas_novedad)))
        
        if fechas_novedad: st.error(f"⚠️ **Novedad en Cobertura:** Hay {len(fechas_novedad)} días desprotegidos.")
        else: st.success("✅ **Malla 100% Protegida:** Todos los días cumplen con el soporte operativo requerido sin novedad.")
            
        st.write("---")
        st.subheader("📋 Malla de Turnos Operativa por Grupo (Macro)")
        
        pivot_grupo = df_final.pivot(index="Sujeto", columns="Fecha", values="Turno").fillna("DESCANSO")
        pivot_grupo.columns = [p.strftime('%Y-%m-%d') if isinstance(p, (datetime, date, pd.Timestamp)) else str(p) for p in pivot_grupo.columns]
        
        fila_semaforo = {}
        dias_criticos_lista = []
        for col_fecha in pivot_grupo.columns:
            col_dt = pd.to_datetime(col_fecha)
            es_f_s = (col_dt.weekday() in [5, 6])
            t1_ok = cob.at[col_dt, "T1"] > 0 if col_dt in cob.index else False
            t2_ok = cob.at[col_dt, "T2"] > 0 if col_dt in cob.index else False
            t3_ok = cob.at[col_dt, "T3"] > 0 if col_dt in cob.index else False
            t4_ok = cob.at[col_dt, "T4"] > 0 if col_dt in cob.index else False
            
            if activar_t4 and not es_f_s:
                status_hoy = "✅ OK 24/7" if (t1_ok and t2_ok and t3_ok and t4_ok) else "❌ FALTA TURNO"
            else:
                status_hoy = "✅ OK 24/7" if (t1_ok and t2_ok and t3_ok) else "❌ FALTA TURNO"
                
            fila_semaforo[col_fecha] = status_hoy
            if status_hoy == "❌ FALTA TURNO": dias_criticos_lista.append(col_fecha)
                
        df_semaforo_row = pd.DataFrame([fila_semaforo], index=["🔍 AUDITORÍA 24/7"])
        pivot_g_completa = pd.concat([pivot_grupo, df_semaforo_row])
        st.dataframe(style_malla(pivot_g_completa), use_container_width=True)

        st.write("---")
        st.subheader("👤 Malla de Turnos Detallada por Persona (Desglosada)")
        rep_maestro_base = generar_reporte_detallado(df_final, config_h, desc_data, activar_t4)
        
        if not rep_maestro_base.empty:
            pivot_persona = rep_maestro_base.pivot(index=["Grupo Asignado", "Nombre"], columns="Fecha", values="Turno realizado").fillna("DESCANSO")
            pivot_persona.columns = [p.strftime('%Y-%m-%d') if isinstance(p, (datetime, date, pd.Timestamp)) else str(p) for p in pivot_persona.columns]
            st.dataframe(style_malla(pivot_persona), use_container_width=True)

        # =========================================================
        # 🛠️ PANEL DE CONTROL TRANSACCIONAL
        # =========================================================
        st.write("---")
        st.subheader("⚙️ Panel de Gestión y Corrección de Turnos")
        opt_b_modo = st.radio("🎯 Nivel de Cobertura a Modificar:", ["Ajustar Grupo (Macro)", "Ajustar Empleado (Micro)"], horizontal=True)
        lista_nombres_unicos = sorted(list(rep_maestro_base["Nombre"].unique())) if not rep_maestro_base.empty else []

        if dias_criticos_lista:
            st.markdown(f"🚨 **Días con huecos operativos detectados ({len(dias_criticos_lista)}):**")
            cols_botones = st.columns(min(len(dias_criticos_lista), 5))
            for idx_b, f_critica in enumerate(dias_criticos_lista[:15]):
                with cols_botones[idx_b % 5]:
                    if st.button(f"🛠️ Corregir {f_critica[5:]}", key=f"btn_crit_{f_critica}"):
                        opciones_s = lista_nombres_unicos if opt_b_modo == "Ajustar Empleado (Micro)" else GRUPOS_TEC
                        popup_forzar_ajuste_fecha(f_critica, opciones_s, es_modo_persona=(opt_b_modo == "Ajustar Empleado (Micro)"))
        else:
            st.success("🎉 ¡Excelente! No hay días desprotegidos en el semestre actual.")
            
        with st.expander("🔍 Forzar cambio en cualquier otra fecha de la Malla (Planificación libre)"):
            c_f1, c_f2 = st.columns(2)
            f_libre_sel = c_f1.selectbox("Seleccione la Fecha:", list(pivot_grupo.columns), key="f_libre_dropdown")
            if c_f2.button("⚙️ Abrir Gestor de Turno para esta Fecha", use_container_width=True):
                opciones_s = lista_nombres_unicos if opt_b_modo == "Ajustar Empleado (Micro)" else GRUPOS_TEC
                popup_forzar_ajuste_fecha(f_libre_sel, opciones_s, es_modo_persona=(opt_b_modo == "Ajustar Empleado (Micro)"))

        # =========================================================
        # 📊 PANEL DE GRÁFICOS Y ANALÍTICA AVANZADA
        # =========================================================
        st.write("---")
        st.subheader("📈 Cuadro de Mando, Gráficos y Métricas de Auditoría")
        
        t_dash, t_fatiga, t_nomina = st.tabs(["📊 Gráficos Analíticos", "⚠️ Alarmas de Fatiga", "📋 Reporte Nómina Completo"])
        
        with t_dash:
            c_g1, c_g2 = st.columns(2)
            with c_g1:
                st.markdown("#### 📅 Descansos y Compensados al Mes por Grupo")
                df_descansos = rep_maestro_base[rep_maestro_base["Turno realizado"].isin(["DESCANSO", "COMPENSADO"])]
                if not df_descansos.empty:
                    df_d_g = df_descansos.groupby(["Mes", "Grupo Asignado", "Turno realizado"]).size().unstack(fill_value=0).reset_index()
                    for c_req in ["DESCANSO", "COMPENSADO"]:
                        if c_req not in df_d_g.columns: df_d_g[c_req] = 0
                    st.bar_chart(df_d_g, x="Grupo Asignado", y=["DESCANSO", "COMPENSADO"], stack=False)
                else: st.caption("Sin datos de francos en el rango temporal.")
                
            with c_g2:
                st.markdown("#### ⏳ Horas Laboradas por Semana y Grupo")
                df_h_g = rep_maestro_base.groupby(["Semana", "Grupo Asignado"])["Horas Programado"].sum().unstack(fill_value=0)
                st.line_chart(df_h_g)
                
            c_g3, c_g4 = st.columns(2)
            with c_g3:
                st.markdown("#### 🕒 Distribución de Recargos Nocturnos por Cuadrilla")
                df_rec_g = rep_maestro_base.groupby("Grupo Asignado")["Recargos Nocturnos"].sum().reset_index()
                st.bar_chart(df_rec_g, x="Grupo Asignado", y="Recargos Nocturnos", color="#9B59B6")
                
            with c_g4:
                st.markdown("#### ⚠️ Acumulado Horas Extras Semanales (Reforma 7h)")
                df_ext_g = rep_maestro_base.groupby("Semana")["Horas Extras"].sum()
                st.line_chart(df_ext_g)

            st.markdown("#### 🔄 Rotación de Turnos Operativos Semanales")
            df_rot = rep_maestro_base[rep_maestro_base["Turno realizado"].isin(["T1", "T2", "T3", "T4", "DISPONIBLE"])]
            if not df_rot.empty:
                df_rot_piv = df_rot.groupby(["Semana", "Grupo Asignado", "Turno realizado"]).size().unstack(fill_value=0).reset_index()
                st.dataframe(df_rot_piv, use_container_width=True)

        with t_fatiga:
            lista_alertas = verificar_alarmas_cambios_drasticos(df_audit)
            if lista_alertas:
                for al in lista_alertas: st.markdown(al["Mensaje"])
            else: st.success("✅ Estructura libre de alertas de fatiga.")
            
        with t_nomina:
            if not rep_maestro_base.empty:
                columnas_ordenadas_solicitadas = [
                    "Fecha", "Cedula", "Nombre", "Cargo", "Grupo Asignado", 
                    "Día Descanso Asignado", "Turno realizado", 
                    "Hora inicio", "Hora fin", "Horas Programado", 
                    "Horas Extras", "Recargos Nocturnos"
                ]
                df_reporte_ordenado = rep_maestro_base[columnas_ordenadas_solicitadas]
                st.dataframe(df_reporte_ordenado, use_container_width=True)
                
                r_col1, r_col2 = st.columns(2)
                with r_col1:
                    resumen_persona = rep_maestro_base.groupby(["Cedula", "Nombre"])[["Horas Programado", "Horas Extras", "Recargos Nocturnos"]].sum().reset_index()
                    st.markdown("**💰 Consolidado Acumulado por Colaborador:**")
                    st.dataframe(resumen_persona, use_container_width=True)
                with r_col2:
                    resumen_grupo = rep_maestro_base.groupby("Grupo Asignado")[["Horas Programado", "Horas Extras", "Recargos Nocturnos"]].sum().reset_index()
                    st.markdown("**📦 Consolidado Total por Grupo:**")
                    st.dataframe(resumen_grupo, use_container_width=True)
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer: 
                    df_reporte_ordenado.to_excel(writer, sheet_name="Detalle_Dias", index=False)
                    resumen_persona.to_excel(writer, sheet_name="Total_Persona", index=False)
                    resumen_grupo.to_excel(writer, sheet_name="Total_Grupo", index=False)
                st.download_button("📥 Descargar Reporte Nómina Maestro (.xlsx)", output.getvalue(), f"Nomina_Reforma_Laboral_{date.today()}.xlsx")
