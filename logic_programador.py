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
# 1. CONSTANTES Y FORMATOS VISUALES
# =========================================================
DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
festivos_co = holidays.Colombia()

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
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer: df.to_excel(writer, index=False)
    try:
        file = repo.get_contents(nombre_archivo)
        repo.update_file(nombre_archivo, f"Update {datetime.now()}", buffer.getvalue(), file.sha)
        st.toast(f"✅ Archivo actualizado en GitHub.")
    except:
        repo.create_file(nombre_archivo, "Create", buffer.getvalue())
        st.toast(f"🆕 Archivo creado en GitHub.")

# =========================================================
# 3. GESTIÓN DE PLANTILLA (RETORNO A GRUPOS)
# =========================================================
def pantalla_personal():
    st.subheader("👥 Gestión de Plantilla Operativa por Grupos")
    
    if st.button("📥 Descargar Base de Empleados desde GitHub"):
        df = cargar_excel("empleados_grupos.xlsx")
        if df.empty: df = cargar_excel("empleados.xlsx")
        if not df.empty: 
            st.session_state.df_pers = df
            st.success("Datos sincronizados con éxito.")
            
    if 'df_pers' in st.session_state:
        st.write("### Editor Maestro de Personal")
        st.caption("Asegúrate de asignar correctamente el 'GrupoAsignado' (Ej: Grupo 1, Grupo 2, Abordaje) y el 'Cargo' (Ej: Master, Tecnico A, Supervisor).")
        
        df_edit = st.data_editor(st.session_state.df_pers, use_container_width=True, key="editor_personal_v2")
        
        if st.button("💾 Guardar Cambios de Personal en GitHub"):
            st.session_state.df_pers = df_edit
            guardar_github(df_edit, "empleados_grupos.xlsx")

# =========================================================
# 4. MOTOR ALGORÍTMICO ORIENTADO A GRUPOS Y CARGOS STRICT
# =========================================================
def calcular_horas_turno(turno_val, extension_horas=7.0):
    if turno_val in ["DESCANSO", "COMPENSADO", "OFF", None]: return 0.0
    return float(extension_horas)

def generar_malla_por_grupos_y_cargos(inicio, fin, grupos_activos, cargos_activos, matriz_necesidades, ext_horas):
    df_emp = cargar_excel("empleados_grupos.xlsx")
    if df_emp.empty: 
        st.error("No se encontró el archivo maestro de personal en GitHub.")
        return pd.DataFrame()
        
    # FILTRADO ESTRICTO: Solo personal de los grupos y cargos seleccionados por pantalla
    df_filtrado = df_emp[
        (df_emp['GrupoAsignado'].isin(grupos_activos)) & 
        (df_emp['Cargo'].isin(cargos_activos))
    ]

    if df_filtrado.empty:
        st.warning("⚠️ No se encontraron empleados que cumplan simultáneamente con los Grupos y Cargos seleccionados.")
        return pd.DataFrame()

    filas = []
    # Control transaccional de compensatorios por persona para cumplir las 42 horas
    cola_compensatorios = {p: [] for p in df_filtrado['Nombre']}
    conteo_descansos_totales = {p: 0 for p in df_filtrado['Nombre']}

    for fecha in pd.date_range(inicio, fin):
        dia_n = DIAS_ES[fecha.weekday()]
        n_semana = fecha.isocalendar()[1]
        asig = {} 
        
        # El algoritmo itera bloque por bloque (Grupo por Grupo)
        for grupo in grupos_activos:
            df_grupo = df_filtrado[df_filtrado['GrupoAsignado'] == grupo]
            
            for cargo in cargos_activos:
                df_grupo_cargo = df_grupo[df_grupo['Cargo'] == cargo]
                personal_bloque = df_grupo_cargo['Nombre'].tolist()
                
                if not personal_bloque: continue
                
                # 1. Aplicar Compensatorios Pendientes (Lunes a Viernes)
                if 0 <= fecha.weekday() <= 4:
                    for p in list(personal_bloque):
                        if p in cola_compensatorios and len(cola_compensatorios[p]) > 0 and p not in asig:
                            asig[p] = "COMPENSADO"
                            cola_compensatorios[p].pop(0)

                # 2. Descanso Estructural (Día Base Elegido para el Grupo)
                dia_descanso_grupo = matriz_necesidades[grupo]["Descanso_Base"]
                
                # Gestión especial para balancear turnos de fin de semana si aplica rotación quincenal
                candidatos_descanso = []
                for p in personal_bloque:
                    if dia_n == dia_descanso_grupo:
                        candidatos_descanso.append(p)
                        
                candidatos_descanso = sorted(candidatos_descanso, key=lambda x: conteo_descansos_totales[x])
                for p in candidatos_descanso:
                    if p in asig: continue
                    asig[p] = "DESCANSO"
                    conteo_descansos_totales[p] += 1

                # 3. Llenado estricto por Turno según las cuotas definidas en la pantalla
                disponibles = [p for p in personal_bloque if p not in asig]
                np.random.seed(fecha.day)
                np.random.shuffle(disponibles)
                
                turnos_definidos = ["T1", "T2", "T3", "RELEVO", "T1 APOYO", "DISPONIBLE"]
                for turno in turnos_definidos:
                    cupo_requerido = matriz_necesidades[grupo][cargo].get(turno, 0)
                    
                    for p in list(disponibles):
                        conteo_actual_turno = sum(1 for emp in asig if emp in personal_bloque and asig[emp] == turno)
                        if conteo_actual_turno < cupo_requerido:
                            asig[p] = turno
                            disponibles.remove(p)
                            
                            # Si tuvo que cubrir un turno en su día de descanso asignado, acumula deuda
                            if p in candidatos_descanso:
                                cola_compensatorios[p].append("DEUDA")
                
                # Quienes sobren quedan Disponibles automáticamente
                for p in disponibles:
                    asig[p] = "DISPONIBLE"

        # Registrar la foto del día para toda la plantilla activa
        for _, row in df_filtrado.iterrows():
            filas.append({
                "Fecha": fecha,
                "Grupo": row['GrupoAsignado'],
                "Sujeto": row['Nombre'],
                "Cargo": row['Cargo'],
                "Turno": asig.get(row['Nombre'], "DESCANSO")
            })

    return pd.DataFrame(filas)

# =========================================================
# 5. AUDITORÍA ADAPTATIVA POR GRUPOS
# =========================================================
def ejecutar_auditoria_completa(df, ext_horas):
    df_aud = df.copy()
    df_aud["Fecha"] = pd.to_datetime(df_aud["Fecha"])
    
    cob = df_aud.groupby(["Fecha", "Turno"]).size().unstack(fill_value=0)
    for c in ["T1", "T2", "DESCANSO", "COMPENSADO", "DISPONIBLE"]:
        if c not in cob.columns: cob[c] = 0
        
    df_aud['Semana'] = df_aud['Fecha'].dt.isocalendar().week
    df_aud['Horas'] = df_aud['Turno'].apply(lambda x: calcular_horas_turno(x, ext_horas))
    h_sem = df_aud.groupby(['Sujeto', 'Semana'])['Horas'].sum().unstack(fill_value=0)
    
    eq_det = df_aud[df_aud['Turno'].isin(["DESCANSO", "COMPENSADO"])].groupby(['Sujeto', 'Turno']).size().unstack(fill_value=0)
    for c in ["DESCANSO", "COMPENSADO"]:
        if c not in eq_det.columns: eq_det[c] = 0
    eq_det["Total Libres"] = eq_det["DESCANSO"] + eq_det["COMPENSADO"]
    
    return cob, h_sem, eq_det

# =========================================================
# 6. INTERFAZ DE PROGRAMACIÓN POR GRUPOS
# =========================================================
def pantalla_programador():
    if os.path.exists("config_estructural.json"):
        with open("config_estructural.json", "r", encoding="utf-8") as f:
            config_personal = json.load(f)
    else:
        st.error("⚠️ Configura los parámetros en la pestaña respectiva primero.")
        return

    perfiles_disponibles = list(config_personal.keys())
    perfil_seleccionado = st.sidebar.selectbox("🎯 Módulo Activo", perfiles_disponibles)
    
    params = config_personal[perfil_seleccionado]
    ext_horas = params.get("extension_turno", 7.0)

    st.header(f"📅 Programador Operativo: {perfil_seleccionado}")

    # 1. SELECTORES FILTRADOS Y ESTRICTOS
    c1, c2 = st.columns(2)
    with c1:
        grupos_defecto = params.get("grupos", ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"])
        grupos_activos = st.multiselect("📂 Seleccione los Grupos a programar hoy:", options=grupos_defecto, default=grupos_defecto)
    with c2:
        cargos_defecto = ["Master", "Tecnico A", "Tecnico B", "Supervisor", "Abordaje"]
        cargos_activos = st.multiselect("💼 Seleccione los Cargos específicos a incluir:", 
                                         options=cargos_defecto, 
                                         default=["Master", "Tecnico A", "Supervisor"] if "Téc" in perfil_seleccionado else ["Abordaje", "Supervisor"])

    # 2. CONSTRUCCIÓN DE LA MATRIZ DINÁMICA DE ENTRADAS INDEXADA POR GRUPO
    st.write("---")
    st.subheader("📊 Cuotas de Cargos y Personal Requerido por Turno")
    
    matriz_necesidades = {}
    turnos_claves = ["T1", "T2", "T3", "RELEVO", "T1 APOYO", "DISPONIBLE"]
    
    # Cada grupo se configura en una pestaña limpia e independiente para evitar mezclas
    if grupos_activos:
        tabs_grupos = st.tabs(grupos_activos)
        for idx_g, grupo in enumerate(grupos_activos):
            with tabs_grupos[idx_g]:
                matriz_necesidades[grupo] = {}
                
                # Configurar el día base de descanso específico para este grupo
                matriz_necesidades[grupo]["Descanso_Base"] = st.selectbox(
                    f"🗓️ Día de Descanso Establecido para {grupo}:", 
                    DIAS_ES, index=(idx_g + 5) % 7, key=f"desc_base_{grupo}"
                )
                
                # Inputs numéricos por cada cargo seleccionado
                for cargo in cargos_activos:
                    st.markdown(f"🔹 **Necesidades de {cargo} (En {grupo}):**")
                    cols_j = st.columns(6)
                    matriz_necesidades[grupo][cargo] = {}
                    
                    for idx_t, t in enumerate(turnos_claves):
                        with cols_j[idx_t]:
                            val_def = 1 if cargo == "Supervisor" else (2 if t in ["T1", "T2"] else 0)
                            cant = st.number_input(f"{t}", min_value=0, max_value=20, value=val_def, key=f"req_{grupo}_{cargo}_{t}")
                            matriz_necesidades[grupo][cargo][t] = cant
                    st.caption("---")

    # 3. CONTROL DE FECHAS
    st.write("---")
    cf1, cf2 = st.columns(2)
    inicio = cf1.date_input("Fecha de Inicio de Planificación", date(2026, 7, 1))
    fin = cf2.date_input("Fecha de Fin de Planificación", date(2026, 12, 31))

    if st.button("🚀 GENERAR MALLA DE TURNOS POR GRUPO"):
        if not grupos_activos or not cargos_activos:
            st.error("⚠️ Debes seleccionar al menos un Grupo y un Cargo para ejecutar el optimizador.")
        else:
            st.session_state.m_base_grupos = generar_malla_por_grupos_y_cargos(inicio, fin, grupos_activos, cargos_activos, matriz_necesidades, ext_horas)

    # 4. RENDERIZACIÓN Y AUDITORÍA DE LA MALLA GENERADA
    if 'm_base_grupos' in st.session_state and not st.session_state.m_base_grupos.empty:
        df_final = st.session_state.m_base_grupos
        
        # Indexamos la matriz visual combinando Grupo y Nombre para que veas la separación clara
        df_final["Grupo_Sujeto"] = df_final["Grupo"] + " - " + df_final["Sujeto"]
        pivot = df_final.pivot(index="Grupo_Sujeto", columns="Fecha", values="Turno").fillna("DESCANSO")
        
        st.subheader("📝 Editor Maestro de la Malla (Agrupado)")
        df_edit = st.data_editor(style_malla(pivot), use_container_width=True)
        
        df_audit = df_edit.reset_index().melt(id_vars="Grupo_Sujeto", var_name="Fecha", value_name="Turno")
        # Recuperar el nombre limpio para las auditorías de horas
        df_audit["Sujeto"] = df_audit["Grupo_Sujeto"].apply(lambda x: x.split(" - ")[1])
        
        cob, h_sem, eq = ejecutar_auditoria_completa(df_audit, ext_horas)
        
        t1, t2, t3 = st.tabs(["📊 Cobertura Lograda", "⚖️ Control Horas Semanales (42h)", "📈 Historial Equidad Descansos"])
        with t1:
            st.dataframe(cob, use_container_width=True)
        with t2:
            st.dataframe(h_sem.style.highlight_between(left=42.01, right=200, color="#FADBD8"), use_container_width=True)
        with t3:
            st.dataframe(eq.style.background_gradient(cmap="Greens", subset=["Total Libres"]), use_container_width=True)
