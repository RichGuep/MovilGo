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
    """Aplica colores a la tabla del editor de turnos."""
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
    if fecha.weekday() == 5: return "Sábado"
    if fecha.weekday() == 6: return "Domingo"
    return "Hábil"

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
        st.toast(f"✅ {nombre_archivo} sincronizado.")
    except:
        repo.create_file(nombre_archivo, "Create", buffer.getvalue())
        st.toast(f"🆕 {nombre_archivo} creado.")

# =========================================================
# 4. GESTIÓN DE PERSONAL (CUOTAS)
# =========================================================
def asignar_grupos_automatico(df):
    df = df.copy()
    if 'GrupoAsignado' in df.columns: df = df.drop(columns=['GrupoAsignado'])
    
    m = df[df['Cargo'].str.contains('Master', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    ta = df[df['Cargo'].str.contains('Tecnico A', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    tb = df[df['Cargo'].str.contains('Tecnico B', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    
    res = []
    # Técnicos: Cuotas 2, 7, 3
    for i, g in enumerate(GRUPOS_TEC):
        temp_m = m.iloc[i*2:(i+1)*2].copy(); temp_m['GrupoAsignado'] = g
        temp_ta = ta.iloc[i*7:(i+1)*7].copy(); temp_ta['GrupoAsignado'] = g
        temp_tb = tb.iloc[i*3:(i+1)*3].copy(); temp_tb['GrupoAsignado'] = g
        res.extend([temp_m, temp_ta, temp_tb])

    # Abordaje: Se marca como bloque "Abordaje" para gestión individual
    abo = df[df['Cargo'].str.contains('Auxiliar|Abordaje', case=False, na=False)].copy()
    abo['GrupoAsignado'] = "Abordaje"
    res.append(abo)

    return pd.concat(res).reset_index(drop=True)

def pantalla_personal():
    st.subheader("👥 Gestión de Personal y Cuotas")
    if st.button("📥 Importar empleados.xlsx"):
        df = cargar_excel("empleados.xlsx")
        if not df.empty: 
            st.session_state.df_pers = df
            st.success("Personal cargado.")
    if 'df_pers' in st.session_state:
        if st.button("🎲 Asignar Grupos Técnicos"):
            st.session_state.df_pers_ready = asignar_grupos_automatico(st.session_state.df_pers)
            st.balloons()
        if 'df_pers_ready' in st.session_state:
            df_edit = st.data_editor(st.session_state.df_pers_ready, use_container_width=True)
            if st.button("💾 Guardar Estructura"):
                guardar_github(df_edit, "empleados_grupos.xlsx")

# =========================================================
# 5. MOTORES DE MALLAS Y AUDITORÍA
# =========================================================
def ejecutar_auditoria(df, tipo):
    df = df.copy(); df["Fecha"] = pd.to_datetime(df["Fecha"])
    errores = []
    t1 = df[df["Turno"] == "T1"].groupby("Fecha").size()
    t2 = df[df["Turno"] == "T2"].groupby("Fecha").size()
    if tipo == "Técnicos":
        t3 = df[df["Turno"] == "T3"].groupby("Fecha").size()
        cob = t1 + t2 + t3
        for f, c in cob.items():
            if c < 3: errores.append(f"❌ Cobertura insuficiente {f.date()}")
    else: 
        cob = t1 + t2 # Cobertura Abordaje (T1+T2)

    equidad = df.groupby(["Sujeto", "Turno"]).size().unstack(fill_value=0)
    for c in ["T1", "T2", "T3", "DESCANSO", "COMPENSADO", "DISPONIBLE"]:
        if c not in equidad.columns: equidad[c] = 0
    return errores, cob, equidad

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
        elif len(gps_h) == 1:
            asig[gps_h[0]] = "DESCANSO"

        if 0 <= fecha.weekday() <= 4:
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
    """NUEVO: Motor Abordaje Individual (10 T1, 10 T2, 7 Disponible)"""
    df_emp = cargar_excel("empleados_grupos.xlsx")
    personal = df_emp[df_emp['GrupoAsignado'] == "Abordaje"]['Nombre'].tolist()
    if not personal: return pd.DataFrame()
    
    filas = []
    for fecha in pd.date_range(inicio, fin):
        dia_n = DIAS_ES[fecha.weekday()]; sem = fecha.isocalendar()[1]
        # Rotación para equidad semanal
        idx_rot = (sem + fecha.month) % len(personal)
        p_lista = personal[idx_rot:] + personal[:idx_rot]
        
        asig = {}
        # 1. Descansos (Mitad Sábado / Mitad Domingo)
        mitad = len(p_lista) // 2
        if dia_n == "Sábado":
            for p in p_lista[:mitad]: asig[p] = "DESCANSO"
        elif dia_n == "Domingo":
            for p in p_lista[mitad:]: asig[p] = "DESCANSO"
            
        # 2. Asignar Cupos (10 T1, 10 T2, Resto DISPONIBLE)
        libres = [p for p in p_lista if p not in asig]
        for i, p in enumerate(libres):
            if i < 10: asig[p] = "T1"
            elif i < 20: asig[p] = "T2"
            else: asig[p] = "DISPONIBLE"
            
        for p in personal:
            filas.append({"Fecha": fecha, "Sujeto": p, "Turno": asig.get(p, "T1")})
    return pd.DataFrame(filas)

def generar_malla_transaccional(df_final, tipo, config_horas):
    df_empleados = cargar_excel("empleados_grupos.xlsx")
    if df_empleados.empty: return pd.DataFrame()
    
    # Cruce inteligente para Técnicos (por grupo) o Abordaje (por nombre)
    if tipo == "Técnicos":
        detallada = pd.merge(df_final, df_empleados[['Nombre', 'Cargo', 'GrupoAsignado']], 
                             left_on="Sujeto", right_on="GrupoAsignado", how="inner")
    else:
        detallada = pd.merge(df_final, df_empleados[['Nombre', 'Cargo']], 
                             left_on="Sujeto", right_on="Nombre", how="inner")

    detallada["Hora Inicio"] = detallada["Turno"].apply(lambda x: config_horas.get(x, {}).get("Inicio", "OFF"))
    detallada["Hora Fin"] = detallada["Turno"].apply(lambda x: config_horas.get(x, {}).get("Fin", "OFF"))
    detallada["Horas Prog."] = detallada.apply(calcular_horas_turno, axis=1)
    detallada["Tipo Día"] = detallada["Fecha"].apply(obtener_tipo_dia)
    
    return detallada[["Fecha", "Tipo Día", "Nombre", "Cargo", "Turno", "Hora Inicio", "Hora Fin", "Horas Prog."]]

# =========================================================
# 6. PANTALLA PROGRAMADOR
# =========================================================
def pantalla_programador():
    tipo = st.sidebar.radio("Módulo", ["Técnicos", "Abordaje"])
    
    with st.expander("⏰ Configuración de Horas"):
        config_h = {}
        t_l = ["T1", "T2", "T3", "RELEVO", "T1 APOYO", "DISPONIBLE"]
        def_h = {"T1": [time(6,0), time(14,0)], "T2": [time(14,0), time(22,0)], "T3": [time(22,0), time(6,0)], 
                 "RELEVO": [time(8,0), time(16,0)], "T1 APOYO": [time(7,0), time(15,0)], "DISPONIBLE": [time(0,0), time(0,0)]}
        cols = st.columns(3)
        for i, t in enumerate(t_l):
            with cols[i%3]:
                ini = st.time_input(f"Inicia {t}", def_h[t][0], key=f"i{t}", step=60)
                fin = st.time_input(f"Fin {t}", def_h[t][1], key=f"f{t}", step=60)
                config_h[t] = {"Inicio": ini.strftime("%H:%M"), "Fin": fin.strftime("%H:%M")}
        config_h["DESCANSO"] = config_h["COMPENSADO"] = {"Inicio": "OFF", "Fin": "OFF"}

    c1, c2 = st.columns(2)
    inicio = c1.date_input("Inicio", date.today())
    fin = c2.date_input("Fin", date.today() + timedelta(days=21))
    
    if tipo == "Técnicos":
        desc_i = {}
        cols_d = st.columns(len(GRUPOS_TEC))
        for i, g in enumerate(GRUPOS_TEC):
            desc_i[g] = cols_d[i].selectbox(f"Descanso {g}", DIAS_ES, index=i%7)

    if st.button("🚀 Generar Malla"):
        if tipo == "Técnicos":
            st.session_state.m_tec = generar_malla_tecnicos(inicio, fin, desc_i)
        else:
            st.session_state.m_abo = generar_malla_abordaje_individual(inicio, fin)

    m_key = "m_tec" if tipo == "Técnicos" else "m_abo"
    if m_key in st.session_state:
        df_base = st.session_state[m_key].copy()
        df_base["Label"] = df_base["Fecha"].apply(lambda x: f"{INICIALES[DIAS_ES[x.weekday()]]} {x.strftime('%d/%m')}")
        pivot = df_base.pivot(index="Sujeto", columns="Label", values="Turno").fillna("DESCANSO")
        sorted_cols = sorted(pivot.columns, key=lambda x: datetime.strptime(x.split(" ")[1] + "/2026", '%d/%m/%Y'))
        
        st.subheader(f"📝 Editor Maestro - {tipo}")
        df_edit = st.data_editor(style_malla(pivot[sorted_cols]), use_container_width=True)
        
        df_final = df_edit.reset_index().melt(id_vars="Sujeto", var_name="Label", value_name="Turno")
        df_final["Fecha"] = df_final["Label"].apply(lambda x: datetime.strptime(x.split(" ")[1] + "/2026", '%d/%m/%Y'))
        
        malla_det = generar_malla_transaccional(df_final, tipo, config_h)
        errs, cob, equidad = ejecutar_auditoria(df_final, tipo)
        
        st.subheader("📋 Malla Detallada")
        st.dataframe(malla_det, use_container_width=True)
        st.subheader("📊 Métricas de Equilibrio y Cobertura")
        a1, a2 = st.columns(2)
        with a1: st.dataframe(equidad.style.background_gradient(cmap="Blues"), use_container_width=True)
        with a2: st.area_chart(cob)
        if not errs: st.success("✅ Escenario Validado")
        else:
            for e in errs: st.error(e)
