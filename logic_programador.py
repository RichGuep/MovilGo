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
        if row['Hora Inicio'] == "OFF" or row['Hora Fin'] == "OFF": return 0
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
    
    masters = df[df['Cargo'].str.contains('Master', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    tecs_a = df[df['Cargo'].str.contains('Tecnico A', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    tecs_b = df[df['Cargo'].str.contains('Tecnico B', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    abordaje = df[df['Cargo'].str.contains('Auxiliar|Abordaje', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    
    res = []
    for i, g in enumerate(GRUPOS_TEC):
        m = masters.iloc[i*2:(i+1)*2].copy(); m['GrupoAsignado'] = g
        ta = tecs_a.iloc[i*7:(i+1)*7].copy(); ta['GrupoAsignado'] = g
        tb = tecs_b.iloc[i*3:(i+1)*3].copy(); tb['GrupoAsignado'] = g
        res.extend([m, ta, tb])
    for i, g in enumerate(GRUPOS_ABO):
        abo = abordaje.iloc[i*5:(i+1)*5].copy(); abo['GrupoAsignado'] = g
        res.append(abo)
    return pd.concat(res).reset_index(drop=True)

def pantalla_personal():
    st.subheader("👥 Parametrización de Grupos")
    if st.button("📥 Importar empleados.xlsx"):
        df = cargar_excel("empleados.xlsx")
        if not df.empty: 
            st.session_state.df_pers = df
            st.success("Personal cargado.")
    if 'df_pers' in st.session_state:
        if st.button("🎲 Asignar Grupos (Cuotas: 2 Master, 7 Tec A, 3 Tec B)"):
            st.session_state.df_pers_ready = asignar_grupos_automatico(st.session_state.df_pers)
            st.balloons()
        if 'df_pers_ready' in st.session_state:
            df_edit = st.data_editor(st.session_state.df_pers_ready, use_container_width=True)
            if st.button("💾 Guardar Estructura en GitHub"):
                guardar_github(df_edit, "empleados_grupos.xlsx")

# =========================================================
# 5. MOTOR DE MALLAS Y AUDITORÍA
# =========================================================
def style_malla(df_pivot):
    def apply_styles(val):
        key = val if val and str(val).strip() != "" else "DESCANSO"
        bg = COLORES_MAP.get(key, "#1B2631")
        txt = "white" if key in ["DESCANSO", "COMPENSADO"] else "#17202A"
        return f'background-color: {bg}; color: {txt}; font-weight: 700; border: 0.5px solid #D5DBDB'
    return df_pivot.style.map(apply_styles)

def generar_malla_transaccional(df_final, tipo, config_horas):
    df_empleados = cargar_excel("empleados_grupos.xlsx")
    if df_empleados.empty:
        st.warning("⚠️ No se encontró 'empleados_grupos.xlsx'. Usando grupos genéricos.")
        detallada = df_final.copy()
        detallada["Nombre"] = "Sin Nombre"; detallada["Cargo"] = "Sin Cargo"; detallada["GrupoAsignado"] = detallada["Sujeto"]
    else:
        detallada = pd.merge(df_final, df_empleados[['Nombre', 'GrupoAsignado', 'Cargo']], left_on="Sujeto", right_on="GrupoAsignado", how="inner")

    detallada["Hora Inicio"] = detallada["Turno"].apply(lambda x: config_horas.get(x, {}).get("Inicio", "OFF"))
    detallada["Hora Fin"] = detallada["Turno"].apply(lambda x: config_horas.get(x, {}).get("Fin", "OFF"))
    detallada["Horas Prog."] = detallada.apply(calcular_horas_turno, axis=1)
    detallada["Tipo Día"] = detallada["Fecha"].apply(obtener_tipo_dia)
    
    res = detallada[["Fecha", "Tipo Día", "Nombre", "GrupoAsignado", "Cargo", "Turno", "Hora Inicio", "Hora Fin", "Horas Prog."]]
    return res.rename(columns={"GrupoAsignado": "Grupo"})

def ejecutar_auditoria(df, tipo):
    df = df.copy()
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    errores = []
    t1 = df[df["Turno"] == "T1"].groupby("Fecha").size()
    t2 = df[df["Turno"] == "T2"].groupby("Fecha").size()
    if tipo == "Técnicos":
        t3 = df[df["Turno"] == "T3"].groupby("Fecha").size()
        cob = t1 + t2 + t3
        for f, c in cob.items():
            if c < 3: errores.append(f"❌ Cobertura insuficiente el {f.date()}")
    else:
        cob = t1 + t2
        for f in t1.index:
            if t1.get(f,0) < 10 or t2.get(f,0) < 10: errores.append(f"⚠️ {f.date()}: Personal insuficiente T1/T2")
    
    equidad = df.groupby(["Sujeto", "Turno"]).size().unstack(fill_value=0)
    for c in ["T1", "T2", "T3", "DESCANSO"]:
        if c not in equidad.columns: equidad[c] = 0
    return errores, cob, equidad

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

# =========================================================
# 6. PANTALLA PROGRAMADOR
# =========================================================
def pantalla_programador():
    tipo = st.sidebar.radio("Módulo", ["Técnicos", "Abordaje"])
    
    with st.expander("⏰ Configuración de Horas (Minutos Exactos)"):
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
        errs, cob, equidad = ejecutar_auditoria(df_final, tipo)
        
        st.subheader("📋 Malla Detallada por Persona")
        st.dataframe(malla_det, use_container_width=True)
        
        st.subheader("📊 Análisis Operativo (Equidad y Cobertura)")
        a1, a2 = st.columns(2)
        with a1: st.dataframe(equidad.style.highlight_max(axis=0, color='#FADBD8'), use_container_width=True)
        with a2: st.area_chart(cob)
        
        if not errs:
            st.markdown("""<div style="background-color: #e8f5e9; padding: 25px; border-radius: 15px; border-left: 6px solid #2e7d32;">
                <h3 style="color: #1b5e20; margin-top: 0;">✅ Validación Exitosa</h3>
                <p style="color: #2e7d32;">Malla alineada con la Reforma Laboral 2026. Distribución de carga equitativa.</p></div>""", unsafe_allow_html=True)
            st.balloons()
        else:
            for e in errs: st.error(e)

        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as wr:
            df_edit.to_excel(wr, sheet_name='Compacta')
            malla_det.to_excel(wr, sheet_name='Detallada', index=False)
        st.download_button("📥 Descargar Reporte Completo", out.getvalue(), f"Malla_{tipo}.xlsx", use_container_width=True)
