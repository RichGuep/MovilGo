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
# Ahora Abordaje solo tiene 2 grupos grandes
GRUPOS_ABO = ["Abordaje G1", "Abordaje G2"] 

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
# 4. GESTIÓN DE PERSONAL (CUOTAS Y DIVISION ABORDAJE)
# =========================================================
def asignar_grupos_automatico(df):
    df = df.copy()
    if 'GrupoAsignado' in df.columns: df = df.drop(columns=['GrupoAsignado'])
    
    # 1. TÉCNICOS: Cuota 2 Master, 7 Tec A, 3 Tec B
    masters = df[df['Cargo'].str.contains('Master', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    tecs_a = df[df['Cargo'].str.contains('Tecnico A', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    tecs_b = df[df['Cargo'].str.contains('Tecnico B', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    
    res = []
    for i, g in enumerate(GRUPOS_TEC):
        temp_m = masters.iloc[i*2:(i+1)*2].copy(); temp_m['GrupoAsignado'] = g
        temp_ta = tecs_a.iloc[i*7:(i+1)*7].copy(); temp_ta['GrupoAsignado'] = g
        temp_tb = tecs_b.iloc[i*3:(i+1)*3].copy(); temp_tb['GrupoAsignado'] = g
        res.extend([temp_m, temp_ta, temp_tb])

    # 2. ABORDAJE: División en 2 bloques (14 y 13 personas)
    abo_total = df[df['Cargo'].str.contains('Auxiliar|Abordaje', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    mitad = 14 if len(abo_total) >= 27 else len(abo_total) // 2
    
    g1_abo = abo_total.iloc[:mitad].copy(); g1_abo['GrupoAsignado'] = "Abordaje G1"
    g2_abo = abo_total.iloc[mitad:].copy(); g2_abo['GrupoAsignado'] = "Abordaje G2"
    res.extend([g1_abo, g2_abo])

    return pd.concat(res).reset_index(drop=True)

def pantalla_personal():
    st.subheader("👥 Configuración de Planta y Grupos")
    if st.button("📥 Importar empleados.xlsx"):
        df = cargar_excel("empleados.xlsx")
        if not df.empty: 
            st.session_state.df_pers = df
            st.success("Personal cargado correctamente.")
    
    if 'df_pers' in st.session_state:
        if st.button("🎲 Generar Asignación Aleatoria (2 Grupos Abordaje / 4 Grupos Técnicos)"):
            st.session_state.df_pers_ready = asignar_grupos_automatico(st.session_state.df_pers)
            st.balloons()
        
        if 'df_pers_ready' in st.session_state:
            df_edit = st.data_editor(st.session_state.df_pers_ready, use_container_width=True)
            if st.button("💾 Guardar Estructura"):
                guardar_github(df_edit, "empleados_grupos.xlsx")

# =========================================================
# 5. MOTORES DE MALLA Y AUDITORÍA
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
        elif len(gps_h) == 1:
            asig[gps_h[0]] = "DESCANSO"

        if 0 <= fecha.weekday() <= 4: # Lógica Compensatorios L-V
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

def generar_malla_abordaje(inicio, fin):
    """Motor Abordaje: Alternancia Sábado/Domingo entre G1 y G2."""
    filas = []
    for fecha in pd.date_range(inicio, fin):
        dia_n = DIAS_ES[fecha.weekday()]; sem = fecha.isocalendar()[1]
        asig = {}
        # Alternamos cada semana quién descansa Sábado y quién Domingo
        invertir = sem % 2 == 0
        
        if dia_n == "Sábado":
            asig["Abordaje G1"] = "DESCANSO" if not invertir else "T1"
            asig["Abordaje G2"] = "DESCANSO" if invertir else "T1"
        elif dia_n == "Domingo":
            asig["Abordaje G1"] = "DESCANSO" if invertir else "T1"
            asig["Abordaje G2"] = "DESCANSO" if not invertir else "T1"
        else:
            # Lunes a Viernes rotan T1 y T2
            asig["Abordaje G1"] = "T1" if sem % 2 == 0 else "T2"
            asig["Abordaje G2"] = "T2" if sem % 2 == 0 else "T1"
            
        for g in GRUPOS_ABO:
            filas.append({"Fecha": fecha, "Sujeto": g, "Turno": asig.get(g)})
    return pd.DataFrame(filas)

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
    else: cob = t1 + t2
    
    equidad = df.groupby(["Sujeto", "Turno"]).size().unstack(fill_value=0)
    for c in ["T1", "T2", "T3", "DESCANSO", "COMPENSADO"]:
        if c not in equidad.columns: equidad[c] = 0
    return errores, cob, equidad

def generar_malla_transaccional(df_final, tipo, config_horas):
    df_empleados = cargar_excel("empleados_grupos.xlsx")
    if df_empleados.empty: return pd.DataFrame()
    detallada = pd.merge(df_final, df_empleados[['Nombre', 'Cargo', 'GrupoAsignado']], 
                         left_on="Sujeto", right_on="GrupoAsignado", how="inner")
    detallada["Hora Inicio"] = detallada["Turno"].apply(lambda x: config_horas.get(x, {}).get("Inicio", "OFF"))
    detallada["Hora Fin"] = detallada["Turno"].apply(lambda x: config_horas.get(x, {}).get("Fin", "OFF"))
    detallada["Horas Prog."] = detallada.apply(calcular_horas_turno, axis=1)
    detallada["Tipo Día"] = detallada["Fecha"].apply(obtener_tipo_dia)
    res = detallada[["Fecha", "Tipo Día", "Nombre", "GrupoAsignado", "Cargo", "Turno", "Hora Inicio", "Hora Fin", "Horas Prog."]]
    return res.rename(columns={"GrupoAsignado": "Grupo"}).sort_values(["Fecha", "Grupo", "Nombre"])

# =========================================================
# 6. PANTALLA PROGRAMADOR
# =========================================================
def pantalla_programador():
    tipo = st.sidebar.radio("Módulo", ["Técnicos", "Abordaje"])
    
    with st.expander("⏰ Ajuste de Horas"):
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
    if tipo == "Técnicos":
        cols_d = st.columns(len(GRUPOS_TEC))
        for i, g in enumerate(GRUPOS_TEC):
            desc_i[g] = cols_d[i].selectbox(f"Descanso {g}", DIAS_ES, index=i%7)

    if st.button("🚀 Generar Malla"):
        if tipo == "Técnicos":
            st.session_state[f"m_{tipo}"] = generar_malla_tecnicos(inicio, fin, desc_i)
        else:
            st.session_state[f"m_{tipo}"] = generar_malla_abordaje(inicio, fin)

    if f"m_{tipo}" in st.session_state:
        df_base = st.session_state[f"m_{tipo}"].copy()
        df_base["Label"] = df_base["Fecha"].apply(lambda x: f"{INICIALES[DIAS_ES[x.weekday()]]} {x.strftime('%d/%m')}")
        pivot = df_base.pivot(index="Sujeto", columns="Label", values="Turno").fillna("DESCANSO")
        sorted_cols = sorted(pivot.columns, key=lambda x: datetime.strptime(x.split(" ")[1] + "/2026", '%d/%m/%Y'))
        
        st.subheader("📝 Editor Maestro")
        df_edit = st.data_editor(style_malla(pivot[sorted_cols]), use_container_width=True)
        
        df_final = df_edit.reset_index().melt(id_vars="Sujeto", var_name="Label", value_name="Turno")
        df_final["Fecha"] = df_final["Label"].apply(lambda x: datetime.strptime(x.split(" ")[1] + "/2026", '%d/%m/%Y'))
        
        malla_det = generar_malla_transaccional(df_final, tipo, config_h)
        errs, cob, equidad = ejecutar_auditoria(df_final, tipo)
        
        st.subheader("📋 Malla Detallada por Persona")
        st.dataframe(malla_det, use_container_width=True)
        
        st.subheader("📊 Métricas de Equilibrio")
        a1, a2 = st.columns(2)
        with a1: st.dataframe(equidad.style.background_gradient(cmap="Blues"), use_container_width=True)
        with a2: st.area_chart(cob)
        
        if not errs: st.success("✅ Escenario Validado 2026")
        else:
            for e in errs: st.error(e)
