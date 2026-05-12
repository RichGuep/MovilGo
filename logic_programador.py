import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import holidays
import io
from github import Github

# =========================================================
# 1. CONFIGURACIÓN, ESTILOS Y CONSTANTES
# =========================================================
st.set_page_config(page_title="MovilGo Optimizer Enterprise Pro v5.0", layout="wide")

# Estética Profesional
st.markdown("""
    <style>
    .stApp { background-color: #F4F7F9; }
    .main-header { font-size: 28px; font-weight: bold; color: #1E3A8A; margin-bottom: 20px; }
    .metric-container { background-color: white; padding: 15px; border-radius: 10px; border: 1px solid #E2E8F0; }
    [data-testid="stDataEditor"] { border: 1px solid #DEE2E6; border-radius: 12px; }
    </style>
    """, unsafe_allow_html=True)

DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
INICIALES = {"Lunes": "L", "Martes": "M", "Miércoles": "X", "Jueves": "J", "Viernes": "V", "Sábado": "S", "Domingo": "D"}
festivos_co = holidays.Colombia()

GRUPOS_TEC = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]
GRUPOS_ABO = ["Abordaje G1", "Abordaje G2", "Abordaje G3", "Abordaje G4", "Abordaje G5"]
PERSONAL_ABO = {g: [f"Abordaje {g[-2:]}-{i+1:02d}" for i in range(5)] for g in GRUPOS_ABO}
OPCIONES_TURNOS = ["T1", "T2", "T3", "RELEVO", "DISPONIBLE", "T1 APOYO", "DESCANSO", "COMPENSADO"]

COLORES_MAP = {
    "T1": "#D6EAF8", "T2": "#D5F5E3", "T3": "#FADBD8",
    "RELEVO": "#E8DAEF", "DISPONIBLE": "#EAEDED",
    "T1 APOYO": "#EBF5FB", "DESCANSO": "#1B2631", "COMPENSADO": "#FDEBD0"
}

def style_malla(df_pivot):
    def apply_styles(val):
        bg = COLORES_MAP.get(val, "")
        txt = "white" if val == "DESCANSO" else "#17202A"
        return f'background-color: {bg}; color: {txt}; font-weight: 600; border: 0.1px solid #D5DBDB' if bg else ''
    return df_pivot.style.map(apply_styles)

# =========================================================
# 2. CONECTIVIDAD Y PERSISTENCIA (GITHUB)
# =========================================================
def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets: return None
        return Github(st.secrets["GITHUB_TOKEN"]).get_repo("RichGuep/movilgo")
    except: return None

def guardar_github(df, nombre_archivo):
    repo = conectar_github()
    if not repo: return
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    try:
        file = repo.get_contents(nombre_archivo)
        repo.update_file(nombre_archivo, f"Update {datetime.now()}", buffer.getvalue(), file.sha)
    except:
        repo.create_file(nombre_archivo, "Create", buffer.getvalue())

# =========================================================
# 3. AUDITORÍA, EQUIDAD Y DESCARGA
# =========================================================
def calcular_metricas_comportamiento(df):
    # Resumen cuantitativo por Grupo/Persona
    resumen = df.groupby(["Sujeto", "Turno"]).size().unstack(fill_value=0)
    columnas_clave = ["DESCANSO", "COMPENSADO", "T1", "T2", "T3"]
    for col in columnas_clave:
        if col not in resumen.columns: resumen[col] = 0
    
    resumen["Días_Trabajados"] = resumen.drop(columns=["DESCANSO", "COMPENSADO"], errors='ignore').sum(axis=1)
    return resumen

def ejecutar_auditoria(df, tipo):
    errores = []
    df = df.copy()
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    
    # Cobertura
    if tipo == "Técnicos":
        cobertura = df[df["Turno"].isin(["T1","T2","T3"])].groupby("Fecha").size()
        for f, c in cobertura.items():
            if c < 3: errores.append(f"❌ Cobertura Técnica insuficiente {f.date()} ({c}/3)")
    else:
        t1 = df[df["Turno"] == "T1"].groupby("Fecha").size()
        t2 = df[df["Turno"] == "T2"].groupby("Fecha").size()
        cobertura = t1 + t2
        for f in t1.index:
            if t1.get(f,0) != 10 or t2.get(f,0) != 10: 
                errores.append(f"⚠️ Desbalance en Abordaje {f.date()}")

    metricas = calcular_metricas_comportamiento(df)
    return errores, cobertura, metricas

def generar_excel_pro(df_edit, errs, cob, equidad):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_edit.to_excel(writer, sheet_name='Malla_Editable')
        equidad.to_excel(writer, sheet_name='Analisis_Equidad')
        pd.DataFrame(errs, columns=["Alertas"]).to_excel(writer, sheet_name='Auditoria', index=False)
        cob.reset_index().to_excel(writer, sheet_name='Cobertura_Diaria', index=False)
        for sheet in writer.sheets.values(): sheet.set_column('A:Z', 18)
    return output.getvalue()

# =========================================================
# 4. LÓGICAS DE GENERACIÓN (ALGORITMOS ORIGINALES)
# =========================================================
def generar_malla_tecnicos(inicio, fin, descansos_ley):
    filas = []
    deudas_comp = {g: 0 for g in GRUPOS_TEC}
    u_turno = {g: "DESCANSO" for g in GRUPOS_TEC}
    c_bloque = {g: 0 for g in GRUPOS_TEC}
    conflictos = {dia: [g for g, d in descansos_ley.items() if d == dia] for dia in DIAS_ES}

    for fecha in pd.date_range(inicio, fin):
        dia_idx = fecha.weekday(); dia_nombre = DIAS_ES[dia_idx]; sem_num = fecha.isocalendar()[1]
        asignados = {}
        gps_dia = conflictos[dia_nombre]
        
        if len(gps_dia) > 1:
            idx = sem_num % len(gps_dia)
            descansador = gps_dia[idx]; asignados[descansador] = "DESCANSO"
            for g in gps_dia: 
                if g != descansador: deudas_comp[g] += 1
        elif len(gps_dia) == 1:
            asignados[gps_dia[0]] = "DESCANSO"

        activos = [g for g in GRUPOS_TEC if g not in asignados]
        if 0 <= dia_idx <= 4 and len(asignados) == 0:
            cands_comp = sorted(activos, key=lambda x: deudas_comp[x], reverse=True)
            if deudas_comp[cands_comp[0]] > 0:
                sel = cands_comp[0]; asignados[sel] = "COMPENSADO"; deudas_comp[sel] -= 1; activos.remove(sel)

        for t in ["T3", "T2", "T1"]:
            for g in activos[:]:
                if u_turno[g] == t and c_bloque[g] < 4:
                    asignados[g] = t; c_bloque[g] += 1; activos.remove(g)
            if t not in asignados.values() and activos:
                posibles = [g for g in activos if not (t in ["T1", "T2"] and u_turno[g] == "T3")]
                sel = posibles[0] if posibles else activos[0]
                asignados[sel] = t; u_turno[sel] = t; c_bloque[sel] = 1; activos.remove(sel)

        for g in activos:
            asignados[g] = "DESCANSO" if u_turno[g] == "T3" else "T1 APOYO"
            c_bloque[g] = 0

        for g in GRUPOS_TEC:
            u_turno[g] = asignados.get(g, "T1 APOYO")
            filas.append({"Fecha": fecha, "Sujeto": g, "Turno": asignados.get(g, "T1 APOYO")})
    return pd.DataFrame(filas)

def generar_malla_abordaje(inicio, fin, desc_cfg, ciclo):
    filas = []
    for fecha in pd.date_range(inicio, fin):
        dia_nombre = DIAS_ES[fecha.weekday()]
        gps_descansan = [g for g in GRUPOS_ABO if desc_cfg.get(g) == dia_nombre]
        
        if ciclo == "Diario": seed = (fecha - pd.to_datetime(inicio)).days
        elif ciclo == "Quincenal": seed = (fecha.day-1)//15 + (fecha.month*10)
        else: seed = fecha.month + (fecha.year*12)
        
        gps_ord = sorted(GRUPOS_ABO, key=lambda g: (hash(g) + seed) % 100)
        disponibles_hoy = [g for g in gps_ord if g not in gps_descansan]
        
        asig_gps = {}
        for _ in range(min(2, len(disponibles_hoy))): asig_gps[disponibles_hoy.pop(0)] = "T1"
        for _ in range(min(2, len(disponibles_hoy))): asig_gps[disponibles_hoy.pop(0)] = "T2"
        gp_sobrante = disponibles_hoy[0] if disponibles_hoy else None
        
        for g in GRUPOS_ABO:
            turno_base = asig_gps.get(g, "DESCANSO")
            for i, p in enumerate(PERSONAL_ABO[g]):
                ft = turno_base
                if g == gp_sobrante: ft = "RELEVO" if i == 0 else "DISPONIBLE"
                elif g in gps_descansan: ft = "DESCANSO"
                filas.append({"Fecha": fecha, "Sujeto": p, "Turno": ft})
    return pd.DataFrame(filas)

# =========================================================
# 5. INTERFAZ DE USUARIO (PANTALLA PRINCIPAL)
# =========================================================
def pantalla_programador():
    st.sidebar.markdown("## MovilGo Enterprise")
    tipo = st.sidebar.radio("Sección", ["Técnicos", "Abordaje"])
    
    st.markdown(f"<div class='main-header'>📅 Panel de Control: {tipo}</div>", unsafe_allow_html=True)
    
    with st.container(border=True):
        c1, c2 = st.columns(2)
        inicio = c1.date_input("Inicio", date.today())
        fin = c2.date_input("Fin", date.today() + timedelta(days=21))

        descansos = {}
        if tipo == "Técnicos":
            cols = st.columns(4)
            for i, g in enumerate(GRUPOS_TEC): 
                descansos[g] = cols[i].selectbox(f"Día Descanso {g}", DIAS_ES, index=(5 if i<2 else 6))
            ciclo = "Fijo"
        else:
            cr, cd = st.columns([1,3])
            ciclo = cr.selectbox("Rotación Bloques", ["Diario", "Quincenal", "Mensual"])
            cols_a = cd.columns(5)
            for i, g in enumerate(GRUPOS_ABO): 
                descansos[g] = cols_a[i].selectbox(g, DIAS_ES, index=i)

    if st.button(f"🚀 Generar y Optimizar {tipo}", use_container_width=True):
        df = generar_malla_tecnicos(inicio, fin, descansos) if tipo == "Técnicos" else generar_malla_abordaje(inicio, fin, descansos, ciclo)
        st.session_state[f"m_{tipo}"] = df

    key = f"m_{tipo}"
    if key in st.session_state:
        df_view = st.session_state[key].copy()
        df_view["Label"] = df_view["Fecha"].apply(lambda x: f"{INICIALES[DIAS_ES[x.weekday()]]} {x.strftime('%d/%m')}")
        pivot = df_view.pivot(index="Sujeto", columns="Label", values="Turno")
        
        # Ordenar columnas por fecha real
        sorted_cols = sorted(pivot.columns, key=lambda x: datetime.strptime(x.split(" ")[1] + f"/{date.today().year}", '%d/%m/%Y'))
        pivot = pivot[sorted_cols]

        st.subheader("📝 Editor de Turnos")
        config_cols = {str(c): st.column_config.SelectboxColumn(options=OPCIONES_TURNOS, width="small") for c in pivot.columns}
        df_edit = st.data_editor(style_malla(pivot), use_container_width=True, column_config=config_cols)

        # Recalcular métricas tras edición
        df_final = df_edit.reset_index().melt(id_vars="Sujeto", var_name="Label", value_name="Turno")
        map_fechas = dict(zip(df_view["Label"], df_view["Fecha"]))
        df_final["Fecha"] = df_final["Label"].map(map_fechas)
        errs, cob, equidad = ejecutar_auditoria(df_final, tipo)

        st.divider()
        st.subheader("📊 Métricas de Comportamiento y Sobrecarga")
        col_eq1, col_eq2 = st.columns([1, 1])
        
        with col_eq1:
            st.markdown("**Resumen de Turnos por Grupo**")
            st.dataframe(equidad.style.background_gradient(cmap='Blues'), use_container_width=True)
        with col_eq2:
            st.markdown("**Rotación Operativa (T1/T2/T3)**")
            st.bar_chart(equidad[["T1", "T2", "T3"]] if "T3" in equidad.columns else equidad[["T1", "T2"]])

        # Acciones Finales
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            if st.button("💾 Sincronizar con GitHub", use_container_width=True):
                st.session_state[key] = df_final
                guardar_github(df_final, f"malla_{tipo.lower()}.xlsx")
                st.success("Sincronizado")
        with col_f2:
            excel_data = generar_excel_pro(df_edit, errs, cob, equidad)
            st.download_button("📥 Descargar Escenario Completo", excel_data, f"Reporte_{tipo}.xlsx", use_container_width=True)

        st.divider()
        st.subheader("📈 Cobertura y Alertas")
        a1, a2 = st.columns([1, 2])
        with a1:
            if errs:
                for e in errs: st.error(e)
            else: st.success("Malla sin conflictos.")
        with a2:
            st.area_chart(cob)

if __name__ == "__main__":
    pantalla_programador()
