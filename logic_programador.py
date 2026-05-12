import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date, time
import holidays
import io
from github import Github

# =========================================================
# 1. CONFIGURACIÓN, CONSTANTES Y FESTIVOS
# =========================================================
DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
INICIALES = {"Lunes": "L", "Martes": "M", "Miércoles": "X", "Jueves": "J", "Viernes": "V", "Sábado": "S", "Domingo": "D"}
festivos_co = holidays.Colombia()

GRUPOS_TEC = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]
GRUPOS_ABO = ["Abordaje G1", "Abordaje G2", "Abordaje G3", "Abordaje G4", "Abordaje G5"]

COLORES_MAP = {
    "T1": "#D6EAF8", "T2": "#D5F5E3", "T3": "#FADBD8",
    "RELEVO": "#E8DAEF", "DISPONIBLE": "#EAEDED",
    "T1 APOYO": "#EBF5FB", "DESCANSO": "#1B2631", "COMPENSADO": "#2E4053"
}

# =========================================================
# 2. FUNCIONES DE APOYO (FECHAS Y CÁLCULOS)
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
# 4. GESTIÓN DE PERSONAL (ASIGNACIÓN POR CUOTAS)
# =========================================================
def asignar_grupos_automatico(df):
    df = df.copy()
    if 'GrupoAsignado' in df.columns: df = df.drop(columns=['GrupoAsignado'])
    
    # Segmentación por cargo según requerimiento
    m = df[df['Cargo'].str.contains('Master', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    ta = df[df['Cargo'].str.contains('Tecnico A', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    tb = df[df['Cargo'].str.contains('Tecnico B', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    abo = df[df['Cargo'].str.contains('Auxiliar|Abordaje', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    
    res = []
    # Técnicos: Cuota 2, 7, 3 por grupo
    for i, g in enumerate(GRUPOS_TEC):
        temp_m = m.iloc[i*2:(i+1)*2].copy(); temp_m['GrupoAsignado'] = g
        temp_ta = ta.iloc[i*7:(i+1)*7].copy(); temp_ta['GrupoAsignado'] = g
        temp_tb = tb.iloc[i*3:(i+1)*3].copy(); temp_tb['GrupoAsignado'] = g
        res.extend([temp_m, temp_ta, temp_tb])
    # Abordaje: 5 por grupo
    for i, g in enumerate(GRUPOS_ABO):
        temp_abo = abo.iloc[i*5:(i+1)*5].copy(); temp_abo['GrupoAsignado'] = g
        res.append(temp_abo)
    return pd.concat(res).reset_index(drop=True)

def pantalla_personal():
    st.subheader("👥 Gestión de Personal y Cuotas")
    if st.button("📥 Importar empleados.xlsx"):
        df = cargar_excel("empleados.xlsx")
        if not df.empty: 
            st.session_state.df_pers = df
            st.success("Personal cargado.")
    if 'df_pers' in st.session_state:
        if st.button("🎲 Asignar Grupos Aleatorios"):
            st.session_state.df_pers_ready = asignar_grupos_automatico(st.session_state.df_pers)
            st.balloons()
        if 'df_pers_ready' in st.session_state:
            df_edit = st.data_editor(st.session_state.df_pers_ready, use_container_width=True)
            if st.button("💾 Guardar Estructura en GitHub"):
                guardar_github(df_edit, "empleados_grupos.xlsx")

# =========================================================
# 5. MOTOR DE MALLAS (CON LÓGICA DE COMPENSATORIO L-V)
# =========================================================
def generar_malla_tecnicos(inicio, fin, descansos_ley):
    filas = []
    deudas_compensatorio = {g: 0 for g in GRUPOS_TEC}
    
    for fecha in pd.date_range(inicio, fin):
        dia_n = DIAS_ES[fecha.weekday()]; sem = fecha.isocalendar()[1]
        asig = {}
        
        # 1. Chequeo de Descanso Programado (Ley)
        gps_que_deben_descansar = [g for g, d in descansos_ley.items() if d == dia_n]
        
        if len(gps_que_deben_descansar) > 1:
            idx = sem % len(gps_que_deben_descansar)
            g_descansa = gps_que_deben_descansar[idx]
            asig[g_descansa] = "DESCANSO"
            for g in gps_que_deben_descansar:
                if g != g_descansa: deudas_compensatorio[g] += 1 # Genera deuda
        elif len(gps_que_deben_descansar) == 1:
            asig[gps_que_deben_descansar[0]] = "DESCANSO"

        # 2. PAGO DE COMPENSATORIOS (Prioridad Lunes a Viernes)
        if 0 <= fecha.weekday() <= 4:
            gps_con_deuda = [g for g, d in deudas_compensatorio.items() if d > 0 and g not in asig]
            if gps_con_deuda:
                g_comp = sorted(gps_con_deuda, key=lambda x: deudas_compensatorio[x], reverse=True)[0]
                asig[g_comp] = "COMPENSADO"
                deudas_compensatorio[g_comp] -= 1

        # 3. Asignación de Turnos Operativos
        activos = [g for g in GRUPOS_TEC if g not in asig]
        off = sem % 4
        act_r = sorted(activos, key=lambda x: (GRUPOS_TEC.index(x) + off) % 4)
        
        turnos_op = ["T3", "T2", "T1", "T1 APOYO"]
        for g in act_r:
            for t in turnos_op:
                if t not in asig.values():
                    asig[g] = t; break
            if g not in asig: asig[g] = "T1 APOYO"
            
        for g in GRUPOS_TEC:
            filas.append({"Fecha": fecha, "Sujeto": g, "Turno": asig.get(g, "DESCANSO")})
    return pd.DataFrame(filas)

def generar_malla_transaccional(df_final, tipo, config_horas):
    df_empleados = cargar_excel("empleados_grupos.xlsx")
    if df_empleados.empty:
        st.warning("⚠️ Primero guarde los grupos en 'Personal'.")
        return pd.DataFrame()
    
    detallada = pd.merge(df_final, df_empleados[['Nombre', 'Cargo', 'GrupoAsignado']], 
                         left_on="Sujeto", right_on="GrupoAsignado", how="inner")
    
    detallada["Hora Inicio"] = detallada["Turno"].apply(lambda x: config_horas.get(x, {}).get("Inicio", "OFF"))
    detallada["Hora Fin"] = detallada["Turno"].apply(lambda x: config_horas.get(x, {}).get("Fin", "OFF"))
    detallada["Horas Prog."] = detallada.apply(calcular_horas_turno, axis=1)
    detallada["Tipo Día"] = detallada["Fecha"].apply(obtener_tipo_dia)
    
    res = detallada[["Fecha", "Tipo Día", "Nombre", "GrupoAsignado", "Cargo", "Turno", "Hora Inicio", "Hora Fin", "Horas Prog."]]
    return res.rename(columns={"GrupoAsignado": "Grupo"}).sort_values(["Fecha", "Grupo"])

# =========================================================
# 6. ESTILOS Y AUDITORÍA
# =========================================================
def style_malla(df_pivot):
    def apply_styles(val):
        key = val if val and str(val).strip() != "" else "DESCANSO"
        bg = COLORES_MAP.get(key, "#1B2631")
        txt = "white" if key in ["DESCANSO", "COMPENSADO"] else "#17202A"
        return f'background-color: {bg}; color: {txt}; font-weight: 700; border: 0.5px solid #D5DBDB'
    return df_pivot.style.map(apply_styles)

def ejecutar_auditoria(df, tipo):
    df = df.copy(); df["Fecha"] = pd.to_datetime(df["Fecha"])
    errores = []
    t1 = df[df["Turno"] == "T1"].groupby("Fecha").size()
    t2 = df[df["Turno"] == "T2"].groupby("Fecha").size()
    if tipo == "Técnicos":
        t3 = df[df["Turno"] == "T3"].groupby("Fecha").size()
        cob = t1 + t2 + t3
        for f, c in cob.items():
            if c < 3: errores.append(f"❌ Cobertura crítica {f.date()}")
    else: cob = t1 + t2
    
    equidad = df.groupby(["Sujeto", "Turno"]).size().unstack(fill_value=0)
    for c in ["T1", "T2", "T3", "DESCANSO", "COMPENSADO"]:
        if c not in equidad.columns: equidad[c] = 0
    return errores, cob, equidad

# =========================================================
# 7. INTERFAZ PROGRAMADOR
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
    
    desc_i = {}
    lista_g = GRUPOS_TEC if tipo == "Técnicos" else GRUPOS_ABO
    cols_d = st.columns(len(lista_g))
    for i, g in enumerate(lista_g):
        desc_i[g] = cols_d[i].selectbox(f"Descanso {g}", DIAS_ES, index=i%7)

    if st.button("🚀 Generar Malla"):
        if tipo == "Técnicos":
            st.session_state[f"m_{tipo}"] = generar_malla_tecnicos(inicio, fin, desc_i)
        else:
            from logic_programador import generar_malla_abordaje
            st.session_state[f"m_{tipo}"] = generar_malla_abordaje(inicio, fin, desc_i, "Quincenal")

    if f"m_{tipo}" in st.session_state:
        df_base = st.session_state[f"m_{tipo}"].copy()
        df_base["Label"] = df_base["Fecha"].apply(lambda x: f"{INICIALES[DIAS_ES[x.weekday()]]} {x.strftime('%d/%m')}")
        pivot = df_base.pivot(index="Sujeto", columns="Label", values="Turno").fillna("DESCANSO")
        sorted_cols = sorted(pivot.columns, key=lambda x: datetime.strptime(x.split(" ")[1] + "/2026", '%d/%m/%Y'))
        
        st.subheader("📝 Editor de Turnos")
        df_edit = st.data_editor(style_malla(pivot[sorted_cols]), use_container_width=True)
        
        df_final = df_edit.reset_index().melt(id_vars="Sujeto", var_name="Label", value_name="Turno")
        df_final["Fecha"] = df_final["Label"].apply(lambda x: datetime.strptime(x.split(" ")[1] + "/2026", '%d/%m/%Y'))
        
        malla_det = generar_malla_transaccional(df_final, tipo, config_h)
        errs, cob, equidad = ejecutar_auditoria(df_final, tipo)
        
        st.subheader("📋 Malla Detallada")
        st.dataframe(malla_det, use_container_width=True)
        st.subheader("📊 Métricas")
        a1, a2 = st.columns(2)
        with a1: st.dataframe(equidad.style.highlight_max(axis=0, color='#FADBD8'), use_container_width=True)
        with a2: st.area_chart(cob)
        if not errs: st.success("✅ Escenario Validado 2026")
        else:
            for e in errs: st.error(e)

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
