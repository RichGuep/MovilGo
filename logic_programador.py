import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date, time
import holidays
import io
import json
import os
from github import Github

# =========================================================
# 1. CONFIGURACIÓN, CONSTANTES Y ESTILOS
# =========================================================
DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
INICIALES = {"Lunes": "L", "Martes": "M", "Miércoles": "X", "Jueves": "J", "Viernes": "V", "Sábado": "S", "Domingo": "D"}
festivos_co = holidays.Colombia()

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
# 3. GESTIÓN DE PERSONAL PARAMÉTRICA
# =========================================================
def pantalla_personal():
    st.subheader("👥 Gestión de Plantilla")
    
    # Cargar las áreas parametrizadas dinámicamente desde el JSON
    if os.path.exists("config_estructural.json"):
        with open("config_estructural.json", "r", encoding="utf-8") as f:
            config_personal = json.load(f)
    else:
        st.error("⚠️ Primero debes definir parámetros y perfiles en la pestaña de Configuración.")
        return

    perfiles_disponibles = list(config_personal.keys())
    perfil_seleccionado = st.selectbox("Seleccione el Perfil / Área Operativa a gestionar:", perfiles_disponibles)

    if st.button("📥 Sincronizar Base de Datos de Empleados"):
        df = cargar_excel("empleados.xlsx")
        if not df.empty: 
            st.session_state.df_pers = df
            st.success("Personal descargado desde GitHub.")
            
    if 'df_pers' in st.session_state:
        # Asegurar que exista la columna de segmentación estructural
        if 'Tipo_Personal' not in st.session_state.df_pers.columns:
            st.session_state.df_pers['Tipo_Personal'] = 'Técnicos'
            
        df_filtrado = st.session_state.df_pers[st.session_state.df_pers['Tipo_Personal'] == perfil_seleccionado]
        st.write(f"### Personal asignado a: {perfil_seleccionado} ({len(df_filtrado)} empleados)")
        
        # El usuario puede modificar cargos, nombres o reasignar "Tipo_Personal" in situ
        df_edit = st.data_editor(st.session_state.df_pers, use_container_width=True, key="editor_personal_global")
        
        if st.button("💾 Guardar Cambios de Estructura en GitHub"):
            st.session_state.df_pers = df_edit
            guardar_github(df_edit, "empleados_grupos.xlsx")

# =========================================================
# 4. MOTOR UNIVERSAL DE PROGRAMACIÓN PARAMÉTRICA
# =========================================================
def calcular_horas_turno(turno_val, extension_horas=7.0):
    """Calcula las horas del turno basándose en la parametrización dinámica."""
    if turno_val in ["DESCANSO", "COMPENSADO", "OFF", None]: return 0.0
    return float(extension_horas)

def generar_malla_universal(inicio, fin, perfil, params, descansos_elegidos):
    """
    Motor Algorítmico Único y Agnóstico.
    Aplica las reglas de la reforma laboral sobre cualquier volumen de personal y turnos.
    """
    df_emp = cargar_excel("empleados_grupos.xlsx")
    if df_emp.empty: 
        st.error("No se encontró el archivo 'empleados_grupos.xlsx' en el repositorio.")
        return pd.DataFrame()
        
    # Filtrado estricto por el tipo de personal seleccionado
    if 'Tipo_Personal' in df_emp.columns:
        df_perfil = df_emp[df_emp['Tipo_Personal'] == perfil]
    else:
        # Retrocompatibilidad por si no se ha guardado el archivo nuevo
        df_perfil = df_emp[df_emp['GrupoAsignado'] == perfil] if perfil == "Abordaje" else df_emp[df_emp['GrupoAsignado'].isin(["Grupo 1","Grupo 2","Grupo 3","Grupo 4"])]

    personal = df_perfil['Nombre'].tolist()
    if not personal:
        st.warning(f"No hay empleados asignados al perfil '{perfil}'")
        return pd.DataFrame()

    # Variables paramétricas extraídas del JSON estructural
    ext_turno = params.get("extension_turno", 7.0)
    cupo_por_rol = params.get("personas_por_rol", 5)
    modelo_rotacion = params.get("rotacion", "Quincenal")

    filas = []
    cola_compensatorios = []
    conteo_descansos = {p: 0 for p in personal} 

    # División equitativa de la plantilla en dos subgrupos (Bloques Sólidos de Rotación)
    mitad = len(personal) // 2
    grupo_a = personal[:mitad]
    grupo_b = personal[mitad:]

    for fecha in pd.date_range(inicio, fin):
        dia_n = DIAS_ES[fecha.weekday()]
        n_semana = fecha.isocalendar()[1]
        asig = {}
        
        # 1. REGLA REFORMA LABORAL: Mitigación inmediata de deudas (Lunes a Viernes)
        if 0 <= fecha.weekday() <= 4:
            for p in list(cola_compensatorios):
                if p in personal and p not in asig:
                    asig[p] = "COMPENSADO"
                    cola_compensatorios.remove(p)

        # 2. ROTACIÓN Y EQUIDAD DINÁMICA DE DESCANSOS
        # Determinar el bloque que libra según la paridad de la semana o el modelo
        alternar = (n_semana % 2 == 0) if "Quincenal" in modelo_rotacion or "Semanal" in modelo_rotacion else True
        if alternar:
            sagrados = {"A": descansos_elegidos.get("A", "Sábado"), "B": descansos_elegidos.get("B", "Domingo")}
        else:
            sagrados = {"A": descansos_elegidos.get("B", "Domingo"), "B": descansos_elegidos.get("A", "Sábado")}

        # Localizar candidatos libres del día
        candidatos_hoy = []
        for p in personal:
            es_grupo_a = p in grupo_a
            dia_asignado = sagrados["A"] if es_grupo_a else sagrados["B"]
            
            if dia_n == dia_asignado:
                candidatos_hoy.append(p)

        # Ordenar equitativamente por quien ha descansado menos
        candidatos_hoy = sorted(candidatos_hoy, key=lambda x: conteo_descansos[x])

        for p in candidatos_hoy:
            if p in asig: continue
            asig[p] = "DESCANSO"
            conteo_descansos[p] += 1

        # 3. COBERTURA OPERATIVA PARAMÉTRICA (Llenado dinámico de turnos por cuotas)
        dispos = [p for p in personal if p not in asig]
        np.random.seed(fecha.day)
        np.random.shuffle(dispos)
        
        # Distribución balanceada de cargas entre turnos disponibles principales
        for p in dispos:
            conteo_t1 = list(asig.values()).count("T1")
            conteo_t2 = list(asig.values()).count("T2")
            
            if conteo_t1 < cupo_por_rol: 
                asig[p] = "T1"
            elif conteo_t2 < cupo_por_rol: 
                asig[p] = "T2"
            else: 
                asig[p] = "DISPONIBLE"
                
        # Guardar transacciones del día asegurando que si alguien quedó en el limbo, descanse
        for p in personal:
            turno_final = asig.get(p, "DESCANSO")
            # Trackear si debió descansar pero trabajó por cobertura para compensarlo después
            if turno_final not in ["DESCANSO", "COMPENSADO"] and p in candidatos_hoy:
                if p not in cola_compensatorios: 
                    cola_compensatorios.append(p)
            filas.append({"Fecha": fecha, "Sujeto": p, "Turno": turno_final})

    return pd.DataFrame(filas)

# =========================================================
# 5. AUDITORÍA INTEGRAL ADAPTATIVA
# =========================================================
def ejecutar_auditoria_completa(df, ext_horas=7.0):
    df_aud = df.copy()
    df_aud["Fecha"] = pd.to_datetime(df_aud["Fecha"])
    
    # Cobertura por Turno
    cob = df_aud.groupby(["Fecha", "Turno"]).size().unstack(fill_value=0)
    for c in ["T1", "T2", "DESCANSO", "COMPENSADO", "DISPONIBLE"]:
        if c not in cob.columns: cob[c] = 0
        
    # Horas Semanales Basadas en la Extensión de Turno Parametrizada
    df_aud['Semana'] = df_aud['Fecha'].dt.isocalendar().week
    df_aud['Horas'] = df_aud['Turno'].apply(lambda x: calcular_horas_turno(x, ext_horas))
    h_sem = df_aud.groupby(['Sujeto', 'Semana'])['Horas'].sum().unstack(fill_value=0)
    
    # Métricas de Equidad
    eq_det = df_aud[df_aud['Turno'].isin(["DESCANSO", "COMPENSADO"])].groupby(['Sujeto', 'Turno']).size().unstack(fill_value=0)
    for c in ["DESCANSO", "COMPENSADO"]:
        if c not in eq_det.columns: eq_det[c] = 0
    eq_det["Total Libres"] = eq_det["DESCANSO"] + eq_det["COMPENSADO"]
    
    return cob, h_sem, eq_det

def generar_reporte_detallado(df_final, perfil, config_horas, descansos_elegidos, ext_horas):
    df_emp = cargar_excel("empleados_grupos.xlsx")
    if df_emp.empty: return pd.DataFrame()
    
    det = pd.merge(df_final, df_emp[['Nombre', 'Cargo', 'Tipo_Personal']], left_on="Sujeto", right_on="Nombre", how="inner")
    
    det["Hora Inicio"] = det["Turno"].apply(lambda x: config_horas.get(x, {}).get("Inicio", "OFF"))
    det["Hora Fin"] = det["Turno"].apply(lambda x: config_horas.get(x, {}).get("Fin", "OFF"))
    det["Horas Prog"] = det["Turno"].apply(lambda x: calcular_horas_turno(x, ext_horas))
    
    # Identificar el día asignado base de descanso estructural
    mitad = len(det["Nombre"].unique()) // 2
    lista_nombres = list(det["Nombre"].unique())
    
    def obtener_descanso_base(row):
        try:
            idx = lista_nombres.index(row['Nombre'])
            return descansos_elegidos.get("A", "Sábado") if idx < mitad else descansos_elegidos.get("B", "Domingo")
        except:
            return "N/A"

    det["Día Descanso Base"] = det.apply(obtener_descanso_base, axis=1)
    det = det.rename(columns={"Tipo_Personal": "GrupoAsignado"})
    
    columnas_ordenadas = ["Fecha", "Nombre", "Cargo", "GrupoAsignado", "Día Descanso Base", "Turno", "Hora Inicio", "Hora Fin", "Horas Prog"]
    return det[columnas_ordenadas]

# =========================================================
# 6. INTERFAZ DE USUARIO DEL PROGRAMADOR
# =========================================================
def pantalla_programador():
    # 1. Cargar la parametrización viva del JSON
    if os.path.exists("config_estructural.json"):
        with open("config_estructural.json", "r", encoding="utf-8") as f:
            config_personal = json.load(f)
    else:
        st.error("⚠️ Archivo de parametrización no encontrado. Define perfiles primero.")
        return

    perfiles_disponibles = list(config_personal.keys())
    perfil_seleccionado = st.sidebar.selectbox("🎯 Perfil a Programar", perfiles_disponibles)
    
    params = config_personal[perfil_seleccionado]
    ext_horas = params.get("extension_turno", 7.0)
    cupo_requerido = params.get("personas_por_rol", 5)

    st.caption(f"🚀 **Modo de Operación Atómico:** Aplicando reglas fijas de Reforma Laboral 2026 para el perfil de **{perfil_seleccionado}**.")

    # Formulario dinámico de Horas de Entrada y Salida
    with st.expander(f"⏰ Configurar Rangos de Horas (Jornadas actuales basadas en {ext_horas}h)"):
        config_h = {}
        t_l = ["T1", "T2", "T3", "RELEVO", "T1 APOYO", "DISPONIBLE"]
        
        # Valores de inicio estimados según la duración de la jornada guardada
        def_h = {
            "T1": [time(6,0), time(13,0)], "T2": [time(13,0), time(20,0)], 
            "T3": [time(22,0), time(5,0)], "RELEVO": [time(8,0), time(15,0)], 
            "T1 APOYO": [time(7,0), time(14,0)], "DISPONIBLE": [time(8,0), time(15,0)]
        }
        
        cols = st.columns(3)
        for i, t in enumerate(t_l):
            with cols[i%3]:
                ini = st.time_input(f"Inicia {t}", def_h[t][0], key=f"i{t}")
                fin = st.time_input(f"Fin {t}", def_h[t][1], key=f"f{t}")
                config_h[t] = {"Inicio": ini.strftime("%H:%M"), "Fin": fin.strftime("%H:%M")}
        config_h["DESCANSO"] = config_h["COMPENSADO"] = {"Inicio": "OFF", "Fin": "OFF"}

    c1, c2 = st.columns(2)
    inicio, fin = c1.date_input("Fecha Inicio Planificación", date(2026, 7, 1)), c2.date_input("Fecha Fin Planificación", date(2026, 12, 31))
    
    # Parámetros dinámicos de descansos para los bloques equitativos de la plantilla
    st.subheader("🗓️ Selección de Distribución de Descansos Libres")
    ca, cb = st.columns(2)
    desc_data = {
        "A": ca.selectbox("Día de Descanso Base - Bloque Alfa", DIAS_ES, index=5), 
        "B": cb.selectbox("Día de Descanso Base - Bloque Beta", DIAS_ES, index=6)
    }

    if st.button(f"🚀 GENERAR MALLA AUTOMÁTICA DE {perfil_seleccionado.upper()}"):
        st.session_state.m_base = generar_malla_universal(inicio, fin, perfil_seleccionado, params, desc_data)

    if 'm_base' in st.session_state and not st.session_state.m_base.empty:
        df_final = st.session_state.m_base
        pivot = df_final.pivot(index="Sujeto", columns="Fecha", values="Turno").fillna("DESCANSO")
        
        st.subheader("📝 Editor Maestro Receptivo")
        df_edit = st.data_editor(style_malla(pivot), use_container_width=True)
        
        df_audit = df_edit.reset_index().melt(id_vars="Sujeto", var_name="Fecha", value_name="Turno")
        cob, h_sem, eq = ejecutar_auditoria_completa(df_audit, ext_horas)
        
        t1, t2, t3, t4 = st.tabs(["📊 Cobertura Mínima", "⚖️ Cumplimiento Legal 42h", "📈 Consistencia Simétrica", "📋 Reporte Consolidado Nómina"])
        with t1:
            st.write(f"Target de personal por rol en turnos principales: **{cupo_requerido} trabajadores**")
            st.dataframe(cob.style.map(lambda v: 'background-color: #D5F5E3' if v==cupo_requerido else ('background-color: #FADBD8' if v < cupo_requerido else ''), subset=["T1", "T2"] if "T1" in cob.columns else []), use_container_width=True)
        with t2:
            st.write("Control Semanal de Horas Máximas Ordinarias (Reforma Laboral 2026: Límite 42h):")
            st.dataframe(h_sem.style.highlight_between(left=42.01, right=200, color="#FADBD8"), use_container_width=True)
        with t3:
            st.dataframe(eq.style.background_gradient(cmap="Greens", subset=["Total Libres"]), use_container_width=True)
        with t4:
            rep = generar_reporte_detallado(df_audit, perfil_seleccionado, config_h, desc_data, ext_horas)
            st.dataframe(rep, use_container_width=True)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer: rep.to_excel(writer, index=False)
            st.download_button(f"📥 Descargar Nómina de {perfil_seleccionado}", output.getvalue(), f"Malla_{perfil_seleccionado}_{date.today()}.xlsx")

if __name__ == "__main__":
    pantalla_programador()
