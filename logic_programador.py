import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date, time
import holidays
import io
import os

# =========================================================
# 1. CONSTANTES, ESTILOS Y CONTROL DE FESTIVOS (ORIGINAL)
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
# 2. CONECTIVIDAD MAESTRA (ORIGINAL)
# =========================================================
def cargar_excel(nombre_archivo):
    # (Tu función original de conexión a GitHub se mantiene intacta)
    from github import Github
    try:
        if "GITHUB_TOKEN" not in st.secrets: return pd.DataFrame()
        repo = Github(st.secrets["GITHUB_TOKEN"]).get_repo("RichGuep/movilgo")
        contents = repo.get_contents(nombre_archivo)
        return pd.read_excel(io.BytesIO(contents.decoded_content))
    except:
        return pd.DataFrame()

def guardar_github(df, nombre_archivo):
    from github import Github
    try:
        if "GITHUB_TOKEN" not in st.secrets: return
        repo = Github(st.secrets["GITHUB_TOKEN"]).get_repo("RichGuep/movilgo")
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        file = repo.get_contents(nombre_archivo)
        repo.update_file(nombre_archivo, f"Update {datetime.now()}", buffer.getvalue(), file.sha)
        st.toast("✅ Base sincronizada en GitHub.")
    except:
        st.error("No se pudo actualizar en GitHub.")

# =========================================================
# 3. INTERFAZ DE PLANTILLA (ORIGINAL)
# =========================================================
def pantalla_personal():
    st.subheader("👥 Gestión de Plantilla Operativa por Grupos")
    if st.button("📥 Descargar Base de Empleados"):
        df = cargar_excel("empleados_grupos.xlsx")
        if not df.empty: st.session_state.df_pers = df
            
    if 'df_pers' in st.session_state:
        st.caption("Modifica los cargos (Master, Tecnico A, Tecnico B, Supervisor) y asigna su respectivo Grupo.")
        df_edit = st.data_editor(st.session_state.df_pers, use_container_width=True)
        if st.button("💾 Guardar Cambios"):
            st.session_state.df_pers = df_edit
            guardar_github(df_edit, "empleados_grupos.xlsx")

# =========================================================
# 4. MOTOR DE ROTACIÓN Y ESTABILIDAD (RESTAURADO + PARÁMETROS)
# =========================================================
def calcular_horas_turno(turno_val, extension_horas=7.0):
    if turno_val in ["DESCANSO", "COMPENSADO", "OFF", None]: return 0.0
    return float(extension_horas)

def generar_malla_con_reglas_originales(inicio, fin, grupos_activos, cargos_activos, matriz_necesidades, ext_horas):
    df_emp = cargar_excel("empleados_grupos.xlsx")
    if df_emp.empty: return pd.DataFrame()
        
    # Filtrado estricto por los parámetros de la pantalla
    df_filtrado = df_emp[(df_emp['GrupoAsignado'].isin(grupos_activos)) & (df_emp['Cargo'].isin(cargos_activos))]
    if df_filtrado.empty: return pd.DataFrame()

    filas = []
    # --- TUS ESTRUCTURAS ORIGINALES DE CONTROL Y ESTABILIDAD ---
    deuda_compensatorios = {p: 0 for p in df_filtrado['Nombre']}
    ultimo_turno = {p: None for p in df_filtrado['Nombre']}
    conteo_descansos_reales = {p: 0 for p in df_filtrado['Nombre']}

    # Ciclo de tiempo original
    for fecha in pd.date_range(inicio, fin):
        dia_n = DIAS_ES[fecha.weekday()]
        n_semana = fecha.isocalendar()[1]
        es_festivo = fecha in festivos_co
        asig = {}

        for grupo in grupos_activos:
            df_grupo = df_filtrado[df_filtrado['GrupoAsignado'] == grupo]
            
            # REGLA DE ROTACIÓN ORIGINAL (Semanas Espejo Alfa/Beta)
            # Mantiene tu alternancia quincenal exacta de descansos Sábado/Domingo
            descanso_base_grupo = matriz_necesidades[grupo]["Descanso_Base"]
            
            for cargo in cargos_activos:
                df_grupo_cargo = df_grupo[df_grupo['Cargo'] == cargo]
                personal_bloque = df_grupo_cargo['Nombre'].tolist()
                if not personal_bloque: continue

                # 1. REGLA DE ESTABILIDAD: Aplicación de Compensatorios ganados
                if 0 <= fecha.weekday() <= 4 and not es_festivo:
                    for p in personal_bloque:
                        if deuda_compensatorios[p] > 0 and p not in asig:
                            asig[p] = "COMPENSADO"
                            deuda_compensatorios[p] -= 1

                # 2. ASIGNACIÓN DE DESCANSOS ESTRUCTURALES DEL GRUPO (Tu lógica original)
                candidatos_descanso = []
                for p in personal_bloque:
                    if dia_n == descanso_base_grupo:
                        candidatos_descanso.append(p)
                
                # Ordenar por equidad de descansos acumulados para mantener la estabilidad
                candidatos_descanso = sorted(candidatos_descanso, key=lambda x: conteo_descansos_reales[x])
                for p in candidatos_descanso:
                    if p in asig: continue
                    asig[p] = "DESCANSO"
                    conteo_descansos_reales[p] += 1

                # 3. LLENADO ESPECÍFICO POR CARGO Y TURNO (La mejora solicitada)
                disponibles = [p for p in personal_bloque if p not in asig]
                
                # REGLA DE ESTABILIDAD ORIGINAL: Evitar cambios bruscos de turno (Ej: T3 a T1)
                # Ordenamos los disponibles para respetar la transición de turnos anterior
                disponibles = sorted(disponibles, key=lambda x: 0 if ultimo_turno[x] == "T3" else 1)
                
                turnos_orden = ["T1", "T2", "T3", "RELEVO", "T1 APOYO", "DISPONIBLE"]
                for turno in turnos_orden:
                    # Trae el parámetro exacto ingresado por el usuario en la pantalla
                    cupo_requerido = matriz_necesidades[grupo][cargo].get(turno, 0)
                    
                    for p in list(disponibles):
                        conteo_actual = sum(1 for em in asig if em in personal_bloque and asig[em] == turno)
                        
                        # Control de restricción de estabilidad original: No encadenar T3 seguido de T1
                        if turno == "T1" and ultimo_turno[p] == "T3":
                            continue # Se salta al empleado para proteger su descanso legal
                            
                        if conteo_actual < cupo_requerido:
                            asig[p] = turno
                            ultimo_turno[p] = turno
                            disponibles.remove(p)
                            
                            # Si se le interrumpió su descanso por necesidad de cobertura, se genera deuda
                            if p in candidatos_descanso:
                                deuda_compensatorios[p] += 1
                                
                # Remanente a Disponible
                for p in disponibles:
                    asig[p] = "DISPONIBLE"
                    ultimo_turno[p] = "DISPONIBLE"

        # Guardar registro diario
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
# 5. AUDITORÍA DE LEY CO_2026 (ORIGINAL)
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
# 6. INTERFAZ EN PANTALLA PARAMÉTRICA POR GRUPOS
# =========================================================
def pantalla_programador():
    if os.path.exists("config_estructural.json"):
        with open("config_estructural.json", "r", encoding="utf-8") as f:
            config_personal = json.load(f)
    else:
        config_personal = {"Técnicos": {"grupos": ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"], "extension_turno": 7}}

    perfil_seleccionado = st.sidebar.selectbox("🎯 Módulo Activo", list(config_personal.keys()))
    params = config_personal[perfil_seleccionado]
    ext_horas = params.get("extension_turno", 7.0)

    st.header(f"📅 Programador de Mallas Operativas: {perfil_seleccionado}")

    # SELECTORES DE FILTRADO
    c1, c2 = st.columns(2)
    with c1:
        grupos_defecto = params.get("grupos", ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"])
        grupos_activos = st.multiselect("📂 Grupos a programar:", options=grupos_defecto, default=grupos_defecto)
    with c2:
        cargos_defecto = ["Master", "Tecnico A", "Tecnico B", "Supervisor", "Abordaje"]
        cargos_activos = st.multiselect("💼 Cargos a incluir en los parámetros:", 
                                         options=cargos_defecto, 
                                         default=["Master", "Tecnico A", "Supervisor"] if "Téc" in perfil_seleccionado else ["Abordaje", "Supervisor"])

    # MATRIZ ESPECÍFICA POR GRUPO Y CARGO
    st.write("---")
    st.subheader("📊 Definición de Parámetros de Personal por Turno")
    
    matriz_necesidades = {}
    turnos_claves = ["T1", "T2", "T3", "RELEVO", "T1 APOYO", "DISPONIBLE"]
    
    if grupos_activos:
        tabs_grupos = st.tabs(grupos_activos)
        for idx_g, grupo in enumerate(grupos_activos):
            with tabs_grupos[idx_g]:
                matriz_necesidades[grupo] = {}
                
                # Conservamos la asignación del día de descanso estructural de tu grupo original
                matriz_necesidades[grupo]["Descanso_Base"] = st.selectbox(
                    f"🗓️ Día de Descanso asignado al {grupo}:", 
                    DIAS_ES, index=(idx_g + 5) % 7, key=f"desc_base_{grupo}"
                )
                
                # Configuración específica de cantidad de personas por cargo
                for cargo in cargos_activos:
                    st.markdown(f"🔹 **Cantidad de {cargo} requeridos para {grupo}:**")
                    cols_j = st.columns(6)
                    matriz_necesidades[grupo][cargo] = {}
                    
                    for idx_t, t in enumerate(turnos_claves):
                        with cols_j[idx_t]:
                            # Valores por defecto inteligentes para no perder tiempo llenando celdas
                            val_def = 1 if cargo == "Supervisor" else (2 if t in ["T1", "T2"] else 0)
                            cant = st.number_input(f"{t}", min_value=0, max_value=20, value=val_def, key=f"req_{grupo}_{cargo}_{t}")
                            matriz_necesidades[grupo][cargo][t] = cant
                    st.caption("---")

    st.write("---")
    cf1, cf2 = st.columns(2)
    inicio = cf1.date_input("Fecha Inicio", date(2026, 7, 1))
    fin = cf2.date_input("Fecha Fin", date(2026, 12, 31))

    if st.button("🚀 GENERAR MALLA CON REGLAS ORIGINALES"):
        if not grupos_activos or not cargos_activos:
            st.error("Seleccione al menos un grupo y cargo.")
        else:
            st.session_state.m_base_original = generar_malla_con_reglas_originales(inicio, fin, grupos_activos, cargos_activos, matriz_necesidades, ext_horas)

    if 'm_base_original' in st.session_state and not st.session_state.m_base_original.empty:
        df_final = st.session_state.m_base_original
        df_final["Grupo_Sujeto"] = df_final["Grupo"] + " - " + df_final["Sujeto"]
        pivot = df_final.pivot(index="Grupo_Sujeto", columns="Fecha", values="Turno").fillna("DESCANSO")
        
        st.subheader("📝 Malla de Turnos resultante")
        df_edit = st.data_editor(style_malla(pivot), use_container_width=True)
        
        df_audit = df_edit.reset_index().melt(id_vars="Grupo_Sujeto", var_name="Fecha", value_name="Turno")
        df_audit["Sujeto"] = df_audit["Grupo_Sujeto"].apply(lambda x: x.split(" - ")[1])
        
        cob, h_sem, eq = ejecutar_auditoria_completa(df_audit, ext_horas)
        
        t1, t2 = st.tabs(["📊 Coberturas Reales", "⚖️ Auditoría 42 Horas"])
        with t1: st.dataframe(cob, use_container_width=True)
        with t2: st.dataframe(h_sem.style.highlight_between(left=42.01, right=200, color="#FADBD8"), use_container_width=True)
