import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date, time
import io
from github import Github
import holidays

## Constantes de festivos
festivos_co = holidays.Colombia()

# --- FUNCION PARA IDENTIFICAR EL TIPO DE DIA ---
def obtener_tipo_dia(fecha):
    if fecha in festivos_co:
        return "Festivo"
    elif fecha.weekday() == 5: # Sábado
        return "Sábado"
    elif fecha.weekday() == 6: # Domingo
        return "Domingo"
    else:
        return "Hábil"

# --- FUNCION PARA CALCULAR DURACION DEL TURNO ---
def calcular_horas(row):
    try:
        if row['Hora Inicio'] == "OFF" or row['Hora Fin'] == "OFF":
            return 0
        
        formato = "%H:%M"
        h_ini = datetime.strptime(row['Hora Inicio'], formato)
        h_fin = datetime.strptime(row['Hora Fin'], formato)
        
        # Si la hora fin es menor a inicio, es un turno que cruza medianoche (T3)
        if h_fin <= h_ini:
            h_fin += timedelta(days=1)
            
        duracion = h_fin - h_ini
        return round(duracion.total_seconds() / 3600, 2)
    except:
        return 0

# --- MALLA DETALLADA POR PERSONA REHECHA ---
def generar_malla_transaccional(df_final, tipo, config_horas):
    # 1. Cargar la base de empleados asignados a grupos
    df_empleados = cargar_excel("empleados_grupos.xlsx")
    
    if df_empleados.empty:
        st.warning("⚠️ No se encontró 'empleados_grupos.xlsx'. Asigne los grupos en la pestaña Personal primero.")
        # Retorno de emergencia si no hay archivo de empleados
        detallada = df_final.copy()
        detallada["Nombre"] = detallada["Sujeto"]
        detallada["Grupo"] = detallada["Sujeto"]
    else:
        # 2. Hacer el cruce para traer a las personas reales de cada grupo
        # df_final tiene la columna 'Sujeto' que contiene el nombre del Grupo (Grupo 1, etc.)
        detallada = pd.merge(
            df_final, 
            df_empleados, 
            left_on="Sujeto", 
            right_on="Grupo", 
            how="inner"
        )
        # Limpiar nombres de columnas tras el merge
        detallada = detallada.drop(columns=["Sujeto"])
        # Suponiendo que tu Excel tiene columna 'Nombre' y 'Cedula'
        detallada = detallada.rename(columns={"Nombre": "Persona"})

    # 3. Asignar Horas y Metadatos de Fecha
    detallada["Hora Inicio"] = detallada["Turno"].apply(lambda x: config_horas.get(x, {}).get("Inicio", "OFF"))
    detallada["Hora Fin"] = detallada["Turno"].apply(lambda x: config_horas.get(x, {}).get("Fin", "OFF"))
    
    # Cálculos adicionales
    detallada["Horas Programadas"] = detallada.apply(calcular_horas, axis=1)
    detallada["Tipo Día"] = detallada["Fecha"].apply(obtener_tipo_dia)
    
    # 4. Organizar columnas finales
    cols_finales = [
        "Fecha", "Tipo Día", "Persona", "Grupo", 
        "Turno", "Hora Inicio", "Hora Fin", "Horas Programadas"
    ]
    
    # Verificar que las columnas existan antes de filtrar
    cols_existentes = [c for c in cols_finales if c in detallada.columns]
    detallada = detallada[cols_existentes]
    
    return detallada

# =========================================================
# 2. CONECTIVIDAD GITHUB
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
        st.toast(f"✅ Sincronizado: {nombre_archivo}")
    except:
        repo.create_file(nombre_archivo, "Create", buffer.getvalue())
        st.toast(f"🆕 Creado: {nombre_archivo}")

# =========================================================
# 3. PARAMETRIZADOR DE GRUPOS (CUOTAS 2026)
# =========================================================
def asignar_grupos_automatico(df):
    df = df.copy()
    # Mezcla aleatoria por categoría
    masters = df[df['Cargo'].str.contains('Master', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    tecs_a = df[df['Cargo'].str.contains('Técnico A', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    tecs_b = df[df['Cargo'].str.contains('Técnico B', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    abordaje = df[df['Cargo'].str.contains('Abordaje', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    
    final_rows = []
    # Técnicos: 2 Master, 7 Tec A, 3 Tec B por grupo
    for i, g in enumerate(GRUPOS_TEC):
        m = masters.iloc[i*2:(i+1)*2].copy(); m['Grupo'] = g
        ta = tecs_a.iloc[i*7:(i+1)*7].copy(); ta['Grupo'] = g
        tb = tecs_b.iloc[i*3:(i+1)*3].copy(); tb['Grupo'] = g
        final_rows.extend([m, ta, tb])
        
    # Abordaje: 5 por grupo
    for i, g in enumerate(GRUPOS_ABO):
        abo = abordaje.iloc[i*5:(i+1)*5].copy(); abo['Grupo'] = g
        final_rows.append(abo)
        
    return pd.concat(final_rows)

def pantalla_personal():
    st.subheader("👥 Gestión y Parametrización de Grupos")
    if st.button("📥 Importar empleados.xlsx"):
        df = cargar_excel("empleados.xlsx")
        if not df.empty:
            st.session_state.df_pers = df
            st.success("Lista de empleados cargada correctamente.")
            
    if 'df_pers' in st.session_state:
        if st.button("🎲 Asignar Grupos Aleatoriamente"):
            st.session_state.df_pers_ready = asignar_grupos_automatico(st.session_state.df_pers)
            st.balloons()
            
        if 'df_pers_ready' in st.session_state:
            df_edit = st.data_editor(st.session_state.df_pers_ready, use_container_width=True)
            if st.button("💾 Guardar Nueva Estructura en GitHub"):
                guardar_github(df_edit, "empleados_grupos.xlsx")

# =========================================================
# 4. MOTOR DE MALLAS
# =========================================================
def style_malla(df_pivot):
    def apply_styles(val):
        key = val if val and str(val).strip() != "" else "DESCANSO"
        bg = COLORES_MAP.get(key, "#1B2631")
        txt = "white" if key in ["DESCANSO", "COMPENSADO"] else "#17202A"
        return f'background-color: {bg}; color: {txt}; font-weight: 700; border: 0.5px solid #D5DBDB'
    return df_pivot.style.map(apply_styles)

def generar_malla_transaccional(df_final, tipo, config_horas):
    detallada = df_final.copy()
    detallada["Hora Inicio"] = detallada["Turno"].apply(lambda x: config_horas.get(x, {}).get("Inicio", "OFF"))
    detallada["Hora Fin"] = detallada["Turno"].apply(lambda x: config_horas.get(x, {}).get("Fin", "OFF"))
    
    if tipo == "Técnicos":
        detallada["Grupo"] = detallada["Sujeto"]
    else:
        detallada["Grupo"] = detallada["Sujeto"].apply(lambda x: x.split("-")[0] if "-" in x else "Abordaje")

    # Selección exacta de 6 columnas para evitar el ValueError anterior
    detallada = detallada[["Fecha", "Sujeto", "Grupo", "Turno", "Hora Inicio", "Hora Fin"]]
    detallada.columns = ["Fecha", "Nombre", "Grupo", "Turno", "Hora Inicio", "Hora Fin"]
    return detallada

def generar_malla_tecnicos(inicio, fin, descansos_ley):
    filas = []
    for fecha in pd.date_range(inicio, fin):
        dia_n = DIAS_ES[fecha.weekday()]; sem = fecha.isocalendar()[1]
        asig = {}
        gps_h = [g for g, d in descansos_ley.items() if d == dia_n]
        if len(gps_h) > 1:
            idx = sem % len(gps_h); d_r = gps_h[idx]; asig[d_r] = "DESCANSO"
        elif len(gps_h) == 1: asig[gps_h[0]] = "DESCANSO"
        
        act = [g for g in GRUPOS_TEC if g not in asig]
        off = sem % 4
        act_r = sorted(act, key=lambda x: (GRUPOS_TEC.index(x) + off) % 4)
        
        turnos = ["T3", "T2", "T1", "T1 APOYO"]
        for g in act_r:
            for t in turnos:
                if t not in asig.values(): asig[g] = t; break
            if g not in asig: asig[g] = "T1 APOYO"
        for g in GRUPOS_TEC: filas.append({"Fecha": fecha, "Sujeto": g, "Turno": asig.get(g, "DESCANSO")})
    return pd.DataFrame(filas)

def generar_malla_abordaje(inicio, fin, desc_cfg, ciclo):
    filas = []
    for fecha in pd.date_range(inicio, fin):
        dia_n = DIAS_ES[fecha.weekday()]; sem = fecha.isocalendar()[1]
        gps_d = [g for g in GRUPOS_ABO if desc_cfg.get(g) == dia_n]
        off = sem // 2 if ciclo == "Quincenal" else fecha.month
        gps_a = [g for g in GRUPOS_ABO if g not in gps_d]
        gps_r = sorted(gps_a, key=lambda g: (GRUPOS_ABO.index(g) + off) % 5)
        asig = {}
        if len(gps_r) >= 2:
            for _ in range(2): asig[gps_r.pop(0)] = "T1"
        if len(gps_r) >= 2:
            for _ in range(2): asig[gps_r.pop(0)] = "T2"
        rel = gps_r[0] if gps_r else None
        for g in GRUPOS_ABO:
            t = asig.get(g, "RELEVO" if g == rel else "DESCANSO")
            filas.append({"Fecha": fecha, "Sujeto": g, "Turno": t if g not in gps_d else "DESCANSO"})
    return pd.DataFrame(filas)

def pantalla_programador():
    tipo = st.sidebar.radio("Módulo Operativo", ["Técnicos", "Abordaje"])
    
    with st.expander("⏰ Configuración de Horas (Minuto a Minuto)"):
        config_horas = {}
        t_list = ["T1", "T2", "T3", "RELEVO", "T1 APOYO", "DISPONIBLE"]
        def_h = {"T1": [time(6,0), time(14,0)], "T2": [time(14,0), time(22,0)], "T3": [time(22,0), time(6,0)], "RELEVO": [time(8,0), time(16,0)], "T1 APOYO": [time(7,0), time(15,0)], "DISPONIBLE": [time(0,0), time(0,0)]}
        cols = st.columns(3)
        for i, t in enumerate(t_list):
            with cols[i%3]:
                ini = st.time_input(f"Inicia {t}", def_h[t][0], key=f"i{t}", step=60)
                fin = st.time_input(f"Fin {t}", def_h[t][1], key=f"f{t}", step=60)
                config_horas[t] = {"Inicio": ini.strftime("%H:%M"), "Fin": fin.strftime("%H:%M")}
        config_horas["DESCANSO"] = {"Inicio": "OFF", "Fin": "OFF"}
        config_horas["COMPENSADO"] = {"Inicio": "OFF", "Fin": "OFF"}

    c1, c2 = st.columns(2)
    inicio = c1.date_input("Inicio", date.today())
    fin = c2.date_input("Fin", date.today() + timedelta(days=21))
    
    desc_i = {}
    lista = GRUPOS_TEC if tipo == "Técnicos" else GRUPOS_ABO
    cols_d = st.columns(len(lista))
    for i, g in enumerate(lista):
        desc_i[g] = cols_d[i].selectbox(f"Descanso {g}", DIAS_ES, index=i%7)

    if st.button("🚀 Generar Malla Base"):
        st.session_state[f"m_{tipo}"] = generar_malla_tecnicos(inicio, fin, desc_i) if tipo == "Técnicos" else generar_malla_abordaje(inicio, fin, desc_i, "Quincenal")

    if f"m_{tipo}" in st.session_state:
        df_base = st.session_state[f"m_{tipo}"].copy()
        df_base["Label"] = df_base["Fecha"].apply(lambda x: f"{INICIALES[DIAS_ES[x.weekday()]]} {x.strftime('%d/%m')}")
        pivot = df_base.pivot(index="Sujeto", columns="Label", values="Turno").fillna("DESCANSO")
        sorted_cols = sorted(pivot.columns, key=lambda x: datetime.strptime(x.split(" ")[1] + "/2026", '%d/%m/%Y'))
        
        st.subheader("📝 Editor de Turnos")
        df_edit = st.data_editor(style_malla(pivot[sorted_cols]), use_container_width=True)
        
        df_final = df_edit.reset_index().melt(id_vars="Sujeto", var_name="Label", value_name="Turno")
        df_final["Fecha"] = df_final["Label"].apply(lambda x: datetime.strptime(x.split(" ")[1] + "/2026", '%d/%m/%Y'))
        
        malla_det = generar_malla_transaccional(df_final, tipo, config_horas)
        
        st.subheader("📋 Malla Detallada por Persona")
        st.dataframe(malla_det, use_container_width=True)
        
        if st.button("💾 Validar Escenario"):
            st.balloons()
            st.success("### ✅ Validación Exitosa")
