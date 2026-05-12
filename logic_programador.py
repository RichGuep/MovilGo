import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date, time
import holidays
import io
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
    """Aplica el código de colores a la tabla del editor."""
    def apply_styles(val):
        key = val if val and str(val).strip() != "" else "DESCANSO"
        bg = COLORES_MAP.get(key, "#1B2631")
        txt = "white" if key in ["DESCANSO", "COMPENSADO"] else "#17202A"
        return f'background-color: {bg}; color: {txt}; font-weight: 700; border: 0.5px solid #D5DBDB'
    return df_pivot.style.map(apply_styles)

# =========================================================
# 2. FUNCIONES DE APOYO Y CÁLCULOS
# =========================================================
def obtener_tipo_dia(fecha):
    if fecha in festivos_co: return "Festivo"
    return "Sábado" if fecha.weekday() == 5 else "Domingo" if fecha.weekday() == 6 else "Hábil"

def calcular_horas_turno(row):
    try:
        if row['Hora Inicio'] in ["OFF", None] or row['Hora Fin'] in ["OFF", None]: return 0
        fmt = "%H:%M"
        h_ini = datetime.strptime(row['Hora Inicio'], fmt)
        h_fin = datetime.strptime(row['Hora Fin'], fmt)
        if h_fin <= h_ini: h_fin += timedelta(days=1)
        return round((h_fin - h_ini).total_seconds() / 3600, 2)
    except: return 0

# =========================================================
# 3. CONECTIVIDAD GITHUB
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
        st.toast("✅ Sincronización exitosa con GitHub")
    except:
        repo.create_file(nombre_archivo, "Create", buffer.getvalue())
        st.toast("🆕 Archivo creado en GitHub")

# =========================================================
# 4. GESTIÓN DE PERSONAL (PLANTEAMIENTO INDIVIDUAL)
# =========================================================
def asignar_grupos_automatico(df):
    df = df.copy()
    # Limpieza
    if 'GrupoAsignado' in df.columns: df = df.drop(columns=['GrupoAsignado'])
    
    # Técnicos: 2 Master, 7 Tec A, 3 Tec B por grupo
    masters = df[df['Cargo'].str.contains('Master', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    tecs_a = df[df['Cargo'].str.contains('Tecnico A', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    tecs_b = df[df['Cargo'].str.contains('Tecnico B', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    
    res = []
    for i, g in enumerate(GRUPOS_TEC):
        m = masters.iloc[i*2:(i+1)*2].copy(); m['GrupoAsignado'] = g
        ta = tecs_a.iloc[i*7:(i+1)*7].copy(); ta['GrupoAsignado'] = g
        tb = tecs_b.iloc[i*3:(i+1)*3].copy(); tb['GrupoAsignado'] = g
        res.extend([m, ta, tb])

    # Abordaje: Se marca como bloque único para gestión individual posterior
    abo = df[df['Cargo'].str.contains('Auxiliar|Abordaje', case=False, na=False)].copy()
    abo['GrupoAsignado'] = "Abordaje"
    res.append(abo)

    return pd.concat(res).reset_index(drop=True)

def pantalla_personal():
    st.subheader("👥 Gestión de Planta de Personal")
    if st.button("📥 1. Importar empleados.xlsx"):
        df = cargar_excel("empleados.xlsx")
        if not df.empty: 
            st.session_state.df_pers = df
            st.success("Lista de empleados cargada.")
    
    if 'df_pers' in st.session_state:
        if st.button("🎲 2. Asignar Grupos Técnicos y Activar Planta Abordaje"):
            st.session_state.df_pers_ready = asignar_grupos_automatico(st.session_state.df_pers)
        
        if 'df_pers_ready' in st.session_state:
            df_edit = st.data_editor(st.session_state.df_pers_ready, use_container_width=True)
            if st.button("💾 3. Guardar en GitHub"):
                guardar_github(df_edit, "empleados_grupos.xlsx")

# =========================================================
# 5. MOTORES DE GENERACIÓN (INDIVIDUAL Y GRUPAL)
# =========================================================
def generar_malla_tecnicos(inicio, fin, descansos_ley):
    filas = []
    deudas_comp = {g: 0 for g in GRUPOS_TEC}
    for fecha in pd.date_range(inicio, fin):
        dia_n = DIAS_ES[fecha.weekday()]; sem = fecha.isocalendar()[1]
        asig = {}
        gps_h = [g for g, d in descansos_ley.items() if d == dia_n]
        
        if len(gps_h) > 1:
            idx = sem % len(gps_h); d_r = gps_h[idx]; asig[d_r] = "DESCANSO"
            for g in gps_h: 
                if g != d_r: deudas_comp[g] += 1
        elif len(gps_h) == 1: asig[gps_h[0]] = "DESCANSO"

        if 0 <= fecha.weekday() <= 4: # L-V Pago de Deuda
            gps_con_deuda = [g for g, d in deudas_comp.items() if d > 0 and g not in asig]
            if gps_con_deuda:
                g_c = sorted(gps_con_deuda, key=lambda x: deudas_comp[x], reverse=True)[0]
                asig[g_c] = "COMPENSADO"; deudas_comp[g_c] -= 1

        activos = [g for g in GRUPOS_TEC if g not in asig]
        off = sem % 4
        act_r = sorted(activos, key=lambda x: (GRUPOS_TEC.index(x) + off) % 4)
        turnos_op = ["T3", "T2", "T1", "T1 APOYO"]
        for g in act_r:
            for t in turnos_op:
                if t not in asig.values(): asig[g] = t; break
            if g not in asig: asig[g] = "T1 APOYO"
        for g in GRUPOS_TEC: filas.append({"Fecha": fecha, "Sujeto": g, "Turno": asig.get(g, "DESCANSO")})
    return pd.DataFrame(filas)

def generar_malla_abordaje_individual(inicio, fin):
    df_emp = cargar_excel("empleados_grupos.xlsx")
    personal = df_emp[df_emp['GrupoAsignado'] == "Abordaje"]['Nombre'].tolist()
    if not personal: return pd.DataFrame()
    
    filas = []
    for fecha in pd.date_range(inicio, fin):
        dia_n = DIAS_ES[fecha.weekday()]; sem = fecha.isocalendar()[1]
        
        # Rotación semanal para que cambien de turno
        idx_base = (sem + fecha.month) % len(personal)
        p_rotado = personal[idx_base:] + personal[:idx_base]
        
        asig = {}
        # 1. Descansos (Mitad Sábado, Mitad Domingo)
        mitad = len(p_rotado) // 2
        if dia_n == "Sábado":
            for p in p_rotado[:mitad]: asig[p] = "DESCANSO"
        elif dia_n == "Domingo":
            for p in p_rotado[mitad:]: asig[p] = "DESCANSO"
            
        # 2. Llenar cupos: 10 para T1, 10 para T2, 7 Disponibles
        disponibles = [p for p in p_rotado if p not in asig]
        for i, p in enumerate(disponibles):
            if i < 10: asig[p] = "T1"
            elif i < 20: asig[p] = "T2"
            else: asig[p] = "DISPONIBLE"
            
        for p in personal:
            filas.append({"Fecha": fecha, "Sujeto": p, "Turno": asig.get(p, "T1")})
    return pd.DataFrame(filas)

# =========================================================
# 6. PANTALLA PROGRAMADOR
# =========================================================
def pantalla_programador():
    tipo = st.sidebar.radio("Módulo Operativo", ["Técnicos", "Abordaje"])
    
    with st.expander("⏰ Horarios Configurados (2026)"):
        config_h = {"T1":{"Inicio":"06:00","Fin":"14:00"},"T2":{"Inicio":"14:00","Fin":"22:00"},"T3":{"Inicio":"22:00","Fin":"06:00"},
                    "DISPONIBLE":{"Inicio":"08:00","Fin":"16:00"},"DESCANSO":{"Inicio":"OFF","Fin":"OFF"},"COMPENSADO":{"Inicio":"OFF","Fin":"OFF"}}
        st.write(config_h)

    c1, c2 = st.columns(2)
    inicio = c1.date_input("Inicio", date.today()); fin = c2.date_input("Fin", date.today() + timedelta(days=21))
    
    if st.button(f"🚀 Generar Malla {tipo}"):
        if tipo == "Técnicos":
            st.session_state.m_tec = generar_malla_tecnicos(inicio, fin, {"Grupo 1":"Domingo","Grupo 2":"Sábado","Grupo 3":"Lunes","Grupo 4":"Martes"})
        else:
            st.session_state.m_abo = generar_malla_abordaje_individual(inicio, fin)

    m_key = "m_tec" if tipo == "Técnicos" else "m_abo"
    if m_key in st.session_state:
        df_base = st.session_state[m_key].copy()
        df_base["Label"] = df_base["Fecha"].apply(lambda x: f"{INICIALES[DIAS_ES[x.weekday()]]} {x.strftime('%d/%m')}")
        pivot = df_base.pivot(index="Sujeto", columns="Label", values="Turno").fillna("DESCANSO")
        sorted_cols = sorted(pivot.columns, key=lambda x: datetime.strptime(x.split(" ")[1] + "/2026", '%d/%m/%Y'))
        
        st.subheader(f"📝 Edición Individual: {tipo}")
        df_edit = st.data_editor(style_malla(pivot[sorted_cols]), use_container_width=True)
        
        # Auditoría rápida de cupos (solo para Abordaje)
        if tipo == "Abordaje":
            conteo = df_edit.apply(pd.Series.value_counts).T.fillna(0)
            st.write("📊 **Resumen de Cupos Diarios (Abordaje):**")
            st.dataframe(conteo[["T1", "T2", "DISPONIBLE", "DESCANSO"]])
