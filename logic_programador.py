import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import holidays
import io
from github import Github

# =========================================================
# CONFIGURACIÓN Y ESTILOS AVANZADOS
# =========================================================
st.set_page_config(page_title="MovilGo Optimizer Enterprise Pro v5.0", layout="wide")

# Inyección de CSS para mejorar la estética general
st.markdown("""
    <style>
    .stApp { background-color: #F4F7F9; }
    .main-header { font-size: 28px; font-weight: bold; color: #1E3A8A; margin-bottom: 20px; }
    [data-testid="stMetricValue"] { font-size: 24px; color: #1E40AF; }
    .stButton>button { border-radius: 8px; font-weight: 600; transition: all 0.3s; }
    .stButton>button:hover { transform: scale(1.02); box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
    [data-testid="stDataEditor"] { border: 1px solid #DEE2E6; border-radius: 12px; overflow: hidden; }
    </style>
    """, unsafe_allow_html=True)

DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
INICIALES = {"Lunes": "L", "Martes": "M", "Miércoles": "X", "Jueves": "J", "Viernes": "V", "Sábado": "S", "Domingo": "D"}
festivos_co = holidays.Colombia()

GRUPOS_TEC = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]
GRUPOS_ABO = ["Abordaje G1", "Abordaje G2", "Abordaje G3", "Abordaje G4", "Abordaje G5"]
PERSONAL_ABO = {g: [f"Abordaje {g[-2:]}-{i+1:02d}" for i in range(5)] for g in GRUPOS_ABO}

OPCIONES_TURNOS = ["T1", "T2", "T3", "RELEVO", "DISPONIBLE", "T1 APOYO", "DESCANSO", "COMPENSADO"]

# Paleta de colores refinada
COLORES_MAP = {
    "T1": "#D6EAF8", "T2": "#D5F5E3", "T3": "#FADBD8",
    "RELEVO": "#E8DAEF", "DISPONIBLE": "#EAEDED",
    "T1 APOYO": "#EBF5FB", "DESCANSO": "#1B2631", "COMPENSADO": "#FDEBD0"
}

def style_malla(df_pivot):
    def apply_styles(val):
        bg = COLORES_MAP.get(val, "")
        txt = "white" if val == "DESCANSO" else "#17202A"
        return f'background-color: {bg}; color: {txt}; font-weight: 500; border: 0.1px solid #D5DBDB' if bg else ''
    
    return df_pivot.style.map(apply_styles)

# =========================================================
# CONECTIVIDAD GITHUB (ORIGINAL)
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
# NUEVA FUNCIÓN DE DESCARGA INTEGRAL
# =========================================================
def generar_reporte_completo(df_malla, errores, cobertura):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Pestaña 1: La Malla Editada
        df_malla.to_excel(writer, sheet_name='Malla_Final')
        
        # Pestaña 2: Auditoría y Errores
        df_err = pd.DataFrame(errores, columns=["Alerta de Auditoría"])
        df_err.to_excel(writer, sheet_name='Auditoria_Revision', index=False)
        
        # Pestaña 3: Métricas de Cobertura
        df_cob = cobertura.reset_index()
        df_cob.columns = ["Fecha", "Personal_Activo"]
        df_cob.to_excel(writer, sheet_name='Metricas_Cobertura', index=False)
        
        # Ajuste automático de columnas en Excel
        for sheet in writer.sheets.values():
            sheet.set_column('A:Z', 18)
            
    return output.getvalue()

# =========================================================
# AUDITORÍA (ORIGINAL)
# =========================================================
def ejecutar_auditoria(df, tipo):
    errores = []
    df = df.copy()
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    
    if tipo == "Técnicos":
        cobertura = df[df["Turno"].isin(["T1","T2","T3"])].groupby("Fecha").size()
        for f, c in cobertura.items():
            if c < 3: errores.append(f"❌ Cobertura Técnica insuficiente {f.date()} ({c}/3)")
        ausentes = df[df["Turno"].isin(["DESCANSO", "COMPENSADO"])].groupby("Fecha").size()
        for f, c in ausentes.items():
            if c > 1: errores.append(f"🚨 Exclusión: {c} grupos fuera el {f.date()}. Máx 1.")
    else:
        t1 = df[df["Turno"] == "T1"].groupby("Fecha").size()
        t2 = df[df["Turno"] == "T2"].groupby("Fecha").size()
        relevo = df[df["Turno"] == "RELEVO"].groupby("Fecha").size()
        cobertura = t1 + t2
        for f in t1.index:
            if t1.get(f,0) != 10: errores.append(f"⚠️ {f.date()}: T1 debe ser 10 (Hay {t1.get(f,0)})")
            if t2.get(f,0) != 10: errores.append(f"⚠️ {f.date()}: T2 debe ser 10 (Hay {t2.get(f,0)})")
            if relevo.get(f,0) != 1: errores.append(f"⚠️ {f.date()}: Falta RELEVO")
            
    return errores, cobertura

# =========================================================
# LÓGICAS DE GENERACIÓN (ORIGINALES)
# =========================================================
def generar_malla_tecnicos(inicio, fin, descansos_ley):
    filas = []
    deudas_comp = {g: 0 for g in GRUPOS_TEC}
    u_turno = {g: "DESCANSO" for g in GRUPOS_TEC}
    c_bloque = {g: 0 for g in GRUPOS_TEC}
    conflictos = {dia: [g for g, d in descansos_ley.items() if d == dia] for dia in DIAS_ES}

    for fecha in pd.date_range(inicio, fin):
        dia_idx = fecha.weekday()
        dia_nombre = DIAS_ES[dia_idx]
        sem_num = fecha.isocalendar()[1]
        asignados = {}
        
        gps_dia = conflictos[dia_nombre]
        if len(gps_dia) > 1:
            idx = sem_num % len(gps_dia)
            descansador = gps_dia[idx]
            asignados[descansador] = "DESCANSO"
            for g in gps_dia: 
                if g != descansador: deudas_comp[g] += 1
        elif len(gps_dia) == 1:
            asignados[gps_dia[0]] = "DESCANSO"

        activos = [g for g in GRUPOS_TEC if g not in asignados]
        if 0 <= dia_idx <= 4 and len(asignados) == 0:
            cands_comp = sorted(activos, key=lambda x: deudas_comp[x], reverse=True)
            if deudas_comp[cands_comp[0]] > 0:
                sel = cands_comp[0]
                asignados[sel] = "COMPENSADO"; deudas_comp[sel] -= 1; activos.remove(sel)

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
        gps_activos = [g for g in GRUPOS_ABO if g not in gps_descansan]
        
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
                if g == gp_sobrante:
                    ft = "RELEVO" if i == 0 else "DISPONIBLE"
                elif g in gps_descansan:
                    ft = "DESCANSO"
                filas.append({"Fecha": fecha, "Sujeto": p, "Turno": ft})
    return pd.DataFrame(filas)

# =========================================================
# INTERFAZ (MEJORADA)
# =========================================================
def pantalla_programador():
    st.sidebar.markdown("### 🚀 MovilGo Pro v5.0")
    tipo = st.sidebar.radio("Navegación", ["Técnicos", "Abordaje"])
    
    st.markdown(f"<div class='main-header'>📅 Planificación Operativa: {tipo}</div>", unsafe_allow_html=True)
    
    with st.container(border=True):
        c1, c2 = st.columns(2)
        inicio = c1.date_input("Fecha Inicio", date.today())
        fin = c2.date_input("Fecha Término", date.today() + timedelta(days=21))

        descansos = {}
        if tipo == "Técnicos":
            cols = st.columns(4)
            for i, g in enumerate(GRUPOS_TEC): 
                descansos[g] = cols[i].selectbox(f"Día Descanso {g}", DIAS_ES, index=(5 if i<2 else 6))
            ciclo = "Fijo"
        else:
            cr, cd = st.columns([1,3])
            ciclo = cr.selectbox("Modo Rotación", ["Diario", "Quincenal", "Mensual"])
            cols_a = cd.columns(5)
            for i, g in enumerate(GRUPOS_ABO): 
                descansos[g] = cols_a[i].selectbox(g, DIAS_ES, index=i)

    if st.button(f"✨ Ejecutar Algoritmo {tipo}", use_container_width=True):
        df = generar_malla_tecnicos(inicio, fin, descansos) if tipo == "Técnicos" else generar_malla_abordaje(inicio, fin, descansos, ciclo)
        st.session_state[f"m_{tipo}"] = df

    key = f"m_{tipo}"
    if key in st.session_state:
        df_view = st.session_state[key].copy()
        df_view["Label"] = df_view["Fecha"].apply(lambda x: f"{INICIALES[DIAS_ES[x.weekday()]]} {x.strftime('%d/%m')}")
        pivot = df_view.pivot(index="Sujeto", columns="Label", values="Turno")
        
        # Mantener orden cronológico
        sorted_cols = sorted(pivot.columns, key=lambda x: datetime.strptime(x.split(" ")[1] + f"/{date.today().year}", '%d/%m/%Y'))
        pivot = pivot[sorted_cols]

        st.subheader("📝 Edición de Turnos y Supervisión")
        config_cols = {str(c): st.column_config.SelectboxColumn(options=OPCIONES_TURNOS, width="small") for c in pivot.columns}
        
        # DATA EDITOR CON ESTILO
        df_edit = st.data_editor(style_malla(pivot), use_container_width=True, column_config=config_cols, height=400)

        # Reconstrucción de DF para validaciones
        df_final = df_edit.reset_index().melt(id_vars="Sujeto", var_name="Label", value_name="Turno")
        # Mapear las fechas originales
        map_fechas = dict(zip(df_view["Label"], df_view["Fecha"]))
        df_final["Fecha"] = df_final["Label"].map(map_fechas)

        col_save1, col_save2 = st.columns(2)
        with col_save1:
            if st.button("💾 Guardar Cambios en GitHub", use_container_width=True):
                st.session_state[key] = df_final
                guardar_github(df_final, f"malla_{tipo.lower()}.xlsx")
                st.toast("✅ Sincronizado con GitHub", icon="☁️")

        with col_save2:
            # BOTÓN DE DESCARGA COMPLETO
            errs, cob = ejecutar_auditoria(df_final, tipo)
            reporte_excel = generar_reporte_completo(df_edit, errs, cob)
            st.download_button(
                label="📥 Descargar Escenario Completo (Excel)",
                data=reporte_excel,
                file_name=f"Reporte_{tipo}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        st.divider()
        a1, a2 = st.columns([1, 2])
        with a1:
            st.metric("Total Alertas", len(errs))
            with st.container(height=300, border=True):
                if errs:
                    for e in errs: st.error(e)
                else: st.success("✅ Malla perfecta según normativa.")
        with a2:
            st.subheader("📈 Visualización de Cobertura")
            st.area_chart(cob, color="#2563EB")

if __name__ == "__main__":
    pantalla_programador()
