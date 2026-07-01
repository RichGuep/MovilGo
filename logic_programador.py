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
    st.subheader("👥 Gestión de Plantilla Operativa")
    
    if os.path.exists("config_estructural.json"):
        with open("config_estructural.json", "r", encoding="utf-8") as f:
            config_personal = json.load(f)
    else:
        st.error("⚠️ Registra tipos de personal primero en la pestaña '⚙️ Parámetros'.")
        return

    perfiles_disponibles = list(config_personal.keys())
    perfil_seleccionado = st.selectbox("Filtrar visualización por Perfil de Personal:", perfiles_disponibles)

    if st.button("📥 Descargar Base de Empleados desde GitHub"):
        df = cargar_excel("empleados_grupos.xlsx")
        if df.empty:
            df = cargar_excel("empleados.xlsx")
        if not df.empty: 
            st.session_state.df_pers = df
            st.success("Datos sincronizados.")
            
    if 'df_pers' in st.session_state:
        if 'Tipo_Personal' not in st.session_state.df_pers.columns:
            st.session_state.df_pers['Tipo_Personal'] = 'Técnicos'
            
        df_filtrado = st.session_state.df_pers[st.session_state.df_pers['Tipo_Personal'] == perfil_seleccionado]
        st.write(f"### Personal en la categoría: {perfil_seleccionado} ({len(df_filtrado)} empleados)")
        st.caption("💡 Para agregar un Supervisor manual, edita la celda 'Cargo' escribiendo 'Supervisor' y asígnale su 'Tipo_Personal'.")
        
        df_edit = st.data_editor(st.session_state.df_pers, use_container_width=True, key="editor_personal")
        
        if st.button("💾 Guardar Cambios en GitHub"):
            st.session_state.df_pers = df_edit
            guardar_github(df_edit, "empleados_grupos.xlsx")

# =========================================================
# 4. MOTOR UNIVERSAL MATRICIAL POR CARGOS (REFORMA 2026)
# =========================================================
def calcular_horas_turno(turno_val, extension_horas=7.0):
    if turno_val in ["DESCANSO", "COMPENSADO", "OFF", None]: return 0.0
    return float(extension_horas)

def generar_malla_universal_por_cargos(inicio, fin, perfil, params, descansos_elegidos, matriz_necesidades):
    df_emp = cargar_excel("empleados_grupos.xlsx")
    if df_emp.empty: 
        st.error("No se encontró el archivo maestro de personal.")
        return pd.DataFrame()
        
    if 'Tipo_Personal' in df_emp.columns:
        df_perfil = df_emp[df_emp['Tipo_Personal'] == perfil]
    else:
        df_perfil = df_emp[df_emp['GrupoAsignado'] == perfil]

    if df_perfil.empty:
        st.warning(f"No hay empleados registrados bajo la categoría '{perfil}'")
        return pd.DataFrame()

    modelo_rotacion = params.get("rotacion", "Quincenal")
    filas = []
    cola_compensatorios = {cargo: [] for cargo in matriz_necesidades.keys()}
    conteo_descansos = {p: 0 for p in df_perfil['Nombre']}

    for fecha in pd.date_range(inicio, fin):
        dia_n = DIAS_ES[fecha.weekday()]
        n_semana = fecha.isocalendar()[1]
        asig = {} 
        
        for cargo, necesidades in matriz_necesidades.items():
            personal_cargo = df_perfil[df_perfil['Cargo'].str.contains(cargo, case=False, na=False)]['Nombre'].tolist()
            if not personal_cargo:
                continue
                
            # 1. Pago de compensatorios L-V (Reforma Laboral)
            if 0 <= fecha.weekday() <= 4:
                for p in list(cola_compensatorios[cargo]):
                    if p in personal_cargo and p not in asig:
                        asig[p] = "COMPENSADO"
                        cola_compensatorios[cargo].remove(p)

            # 2. Distribución de descansos en bloques
            mitad = len(personal_cargo) // 2
            g_alfa = personal_cargo[:mitad]
            g_beta = personal_cargo[mitad:]
            
            alternar = (n_semana % 2 == 0) if "Quincenal" in modelo_rotacion else True
            if alternar:
                sagrados = {"A": descansos_elegidos.get("A", "Sábado"), "B": descansos_elegidos.get("B", "Domingo")}
            else:
                sagrados = {"A": descansos_elegidos.get("B", "Domingo"), "B": descansos_elegidos.get("A", "Sábado")}

            candidatos_descanso = []
            for p in personal_cargo:
                es_alfa = p in g_alfa
                dia_libre = sagrados["A"] if es_alfa else sagrados["B"]
                if dia_n == dia_libre:
                    candidatos_descanso.append(p)
            
            candidatos_descanso = sorted(candidatos_descanso, key=lambda x: conteo_descansos[x])
            for p in candidatos_descanso:
                if p in asig: continue
                asig[p] = "DESCANSO"
                conteo_descansos[p] += 1

            # 3. Llenado según matriz ingresada por pantalla
            disponibles = [p for p in personal_cargo if p not in asig]
            np.random.seed(fecha.day)
            np.random.shuffle(disponibles)
            
            for turno, cupo_requerido in necesidades.items():
                if cupo_requerido == 0: continue
                
                for p in list(disponibles):
                    conteo_actual_turno = sum(1 for emp in asig if emp in personal_cargo and asig[emp] == turno)
                    if conteo_actual_turno < cupo_requerido:
                        asig[p] = turno
                        disponibles.remove(p)
                        
                        if p in candidatos_descanso:
                            if p not in cola_compensatorios[cargo]:
                                cola_compensatorios[cargo].append(p)
            
            for p in disponibles:
                asig[p] = "DISPONIBLE"

        for p in df_perfil['Nombre']:
            filas.append({"Fecha": fecha, "Sujeto": p, "Turno": asig.get(p, "DESCANSO")})

    return pd.DataFrame(filas)

# =========================================================
# 5. AUDITORÍA INTEGRAL ADAPTATIVA
# =========================================================
def ejecutar_auditoria_completa(df, ext_horas=7.0):
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

def generar_reporte_detallado(df_final, perfil, config_horas, descansos_elegidos, ext_horas):
    df_emp = cargar_excel("empleados_grupos.xlsx")
    if df_emp.empty: return pd.DataFrame()
    
    det = pd.merge(df_final, df_emp[['Nombre', 'Cargo', 'Tipo_Personal']], left_on="Sujeto", right_on="Nombre", how="inner")
    
    det["Hora Inicio"] = det["Turno"].apply(lambda x: config_horas.get(x, {}).get("Inicio", "OFF"))
    det["Hora Fin"] = det["Turno"].apply(lambda x: config_horas.get(x, {}).get("Fin", "OFF"))
    det["Horas Prog"] = det["Turno"].apply(lambda x: calcular_horas_turno(x, ext_horas))
    
    lista_nombres = list(det["Nombre"].unique())
    mitad = len(lista_nombres) // 2
    
    def obtener_descanso_base(row):
        try:
            idx = lista_nombres.index(row['Nombre'])
            return descansos_elegidos.get("A", "Sábado") if idx < mitad else descansos_elegidos.get("B", "Domingo")
        except: return "N/A"

    det["Día Descanso Base"] = det.apply(obtener_descanso_base, axis=1)
    det = det.rename(columns={"Tipo_Personal": "GrupoAsignado"})
    
    columnas_ordenadas = ["Fecha", "Nombre", "Cargo", "GrupoAsignado", "Día Descanso Base", "Turno", "Hora Inicio", "Hora Fin", "Horas Prog"]
    return det[columnas_ordenadas]

# =========================================================
# 6. INTERFAZ DE USUARIO DEL PROGRAMADOR
# =========================================================
def pantalla_programador():
    if os.path.exists("config_estructural.json"):
        with open("config_estructural.json", "r", encoding="utf-8") as f:
            config_personal = json.load(f)
    else:
        st.error("⚠️ Archivo de parametrización no encontrado.")
        return

    perfiles_disponibles = list(config_personal.keys())
    perfil_seleccionado = st.sidebar.selectbox("🎯 Módulo de Personal", perfiles_disponibles)
    
    params = config_personal[perfil_seleccionado]
    ext_horas = params.get("extension_turno", 7.0)

    # NUEVO: Configuración Dinámica Matricial por Cargo y Turno
    with st.expander("📊 Configuración de Cargos y Personal Requerido por Turno", expanded=True):
        cargos_defecto = ["Master", "Tecnico A", "Tecnico B", "Supervisor", "Abordaje"]
        cargos_seleccionados = st.multiselect(
            "💼 Cargos activos a incluir en este ciclo de malla:",
            options=cargos_defecto,
            default=["Master", "Tecnico A", "Supervisor"] if perfil_seleccionado == "Técnicos" else ["Abordaje", "Supervisor"]
        )
        
        st.markdown("##### 👥 Cantidad de personas requeridas por Turno:")
        turnos_claves = ["T1", "T2", "T3", "RELEVO", "T1 APOYO", "DISPONIBLE"]
        matriz_necesidades = {}
        
        for cargo in cargos_seleccionados:
            st.markdown(f"**Cargo: {cargo}**")
            cols_j = st.columns(6)
            matriz_necesidades[cargo] = {}
            for idx, t in enumerate(turnos_claves):
                with cols_j[idx]:
                    val_def = 1 if cargo == "Supervisor" else (2 if t in ["T1", "T2"] else 0)
                    cant = st.number_input(f"{t}", min_value=0, max_value=50, value=val_def, key=f"req_{cargo}_{t}")
                    matriz_necesidades[cargo][t] = cant
            st.divider()

    # Rango de Horarios Fijos Informativos/Edición
    with st.expander(f"⏰ Rangos de Horarios de los Bloques (Base: {ext_horas}h)"):
        config_h = {}
        def_h = {
            "T1": [time(6,0), time(13,0)], "T2": [time(13,0), time(20,0)], 
            "T3": [time(22,0), time(5,0)], "RELEVO": [time(8,0), time(15,0)], 
            "T1 APOYO": [time(7,0), time(14,0)], "DISPONIBLE": [time(8,0), time(15,0)]
        }
        cols = st.columns(3)
        for i, t in enumerate(turnos_claves):
            with cols[i%3]:
                ini = st.time_input(f"Inicia {t}", def_h[t][0], key=f"i{t}")
                fin = st.time_input(f"Fin {t}", def_h[t][1], key=f"f{t}")
                config_h[t] = {"Inicio": ini.strftime("%H:%M"), "Fin": fin.strftime("%H:%M")}
        config_h["DESCANSO"] = config_h["COMPENSADO"] = {"Inicio": "OFF", "Fin": "OFF"}

    c1, c2 = st.columns(2)
    inicio, fin = c1.date_input("Fecha Inicio Plan", date(2026, 7, 1)), c2.date_input("Fecha Fin Plan", date(2026, 12, 31))
    
    st.subheader("🗓️ Distribución de Descansos Libres")
    ca, cb = st.columns(2)
    desc_data = {
        "A": ca.selectbox("Día Descanso - Bloque Alfa", DIAS_ES, index=5), 
        "B": cb.selectbox("Día Descanso - Bloque Beta", DIAS_ES, index=6)
    }

    if st.button(f"🚀 GENERAR MALLA PARAMÉTRICA DE {perfil_seleccionado.upper()}"):
        if not matriz_necesidades:
            st.error("Debes seleccionar al menos un cargo para programar.")
        else:
            st.session_state.m_base = generar_malla_universal_por_cargos(inicio, fin, perfil_seleccionado, params, desc_data, matriz_necesidades)

    if 'm_base' in st.session_state and not st.session_state.m_base.empty:
        df_final = st.session_state.m_base
        pivot = df_final.pivot(index="Sujeto", columns="Fecha", values="Turno").fillna("DESCANSO")
        
        st.subheader("📝 Editor Maestro Receptivo")
        df_edit = st.data_editor(style_malla(pivot), use_container_width=True)
        
        df_audit = df_edit.reset_index().melt(id_vars="Sujeto", var_name="Fecha", value_name="Turno")
        cob, h_sem, eq = ejecutar_auditoria_completa(df_audit, ext_horas)
        
        t1, t2, t3, t4 = st.tabs(["📊 Cobertura Mínima", "⚖️ Cumplimiento 42h", "📈 Consistencia Simétrica", "📋 Reporte Nómina"])
        with t1:
            demanda_t1 = sum(matriz_necesidades[c].get("T1", 0) for c in matriz_necesidades)
            demanda_t2 = sum(matriz_necesidades[c].get("T2", 0) for c in matriz_necesidades)
            st.info(f"🎯 Meta diaria calculada: {demanda_t1} personas en T1 y {demanda_t2} personas en T2.")
            st.dataframe(cob.style.map(lambda v: 'background-color: #D5F5E3' if v >= demanda_t1 else 'background-color: #FADBD8', subset=["T1"] if "T1" in cob.columns else []), use_container_width=True)
        with t2:
            st.dataframe(h_sem.style.highlight_between(left=42.01, right=200, color="#FADBD8"), use_container_width=True)
        with t3:
            st.dataframe(eq.style.background_gradient(cmap="Greens", subset=["Total Libres"]), use_container_width=True)
        with t4:
            rep = generar_reporte_detallado(df_audit, perfil_seleccionado, config_h, desc_data, ext_horas)
            st.dataframe(rep, use_container_width=True)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer: rep.to_excel(writer, index=False)
            st.download_button(f"📥 Descargar Nómina {perfil_seleccionado}", output.getvalue(), f"Malla_{perfil_seleccionado}_{date.today()}.xlsx")

if __name__ == "__main__":
    pantalla_programador()
