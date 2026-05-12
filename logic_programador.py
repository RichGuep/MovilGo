import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import holidays
import io
from github import Github

# =========================================================
# CONFIGURACIÓN Y CONSTANTES
# =========================================================
st.set_page_config(page_title="MovilGo Optimizer Enterprise Pro", layout="wide")

DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
INICIALES = {"Lunes": "L", "Martes": "M", "Miércoles": "X", "Jueves": "J", "Viernes": "V", "Sábado": "S", "Domingo": "D"}
festivos_co = holidays.Colombia()

GRUPOS_TEC = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]
GRUPOS_ABO = ["Abordaje G1", "Abordaje G2", "Abordaje G3", "Abordaje G4", "Abordaje G5"]
PERSONAL_ABO = {g: [f"Abordaje {g[-2:]}-{i+1:02d}" for i in range(5)] for g in GRUPOS_ABO}

OPCIONES_TURNOS = ["T1", "T2", "T3", "RELEVO", "DISPONIBLE", "T1 APOYO", "DESCANSO", "COMPENSADO"]

# =========================================================
# CONECTIVIDAD Y ESTILOS
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

COLORES_MAP = {
    "T1": "#D6EAF8", "T2": "#D5F5E3", "T3": "#FADBD8",
    "RELEVO": "#E8DAEF", "DISPONIBLE": "#EAEDED",
    "T1 APOYO": "#EBF5FB", "DESCANSO": "#2C3E50", "COMPENSADO": "#FDEBD0"
}

def style_malla(df_pivot):
    def apply_styles(val):
        bg = COLORES_MAP.get(val, "")
        txt = "white" if val == "DESCANSO" else "black"
        return f'background-color: {bg}; color: {txt}' if bg else ''
    def highlight_special_days(col):
        try:
            fecha_str = col.name.split(" - ")[1]
            f_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            if f_obj.weekday() >= 5 or f_obj in festivos_co:
                return ['background-color: #FEF5E7; border-bottom: 2px solid #E67E22;' for _ in col]
        except: pass
        return ['' for _ in col]
    return df_pivot.style.map(apply_styles).apply(highlight_special_days, axis=0)

# =========================================================
# AUDITORÍA DE REVISIÓN
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
        cobertura = t1 + t2
        for f in t1.index:
            if t1.get(f,0) < 10: errores.append(f"⚠️ {f.date()}: Falta T1")
            if t2.get(f,0) < 10: errores.append(f"⚠️ {f.date()}: Falta T2")
            
    return errores, cobertura

# =========================================================
# LÓGICAS DE GENERACIÓN
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
        while len(gps_activos) < 4 and gps_descansan: gps_activos.append(gps_descansan.pop(0))

        if ciclo == "Diario": seed = (fecha - pd.to_datetime(inicio)).days
        elif ciclo == "Quincenal": seed = (fecha.day-1)//15 + (fecha.month*10)
        else: seed = fecha.month + (fecha.year*12)
        
        gps_ord = sorted(gps_activos, key=lambda g: (hash(g) + seed) % 100)
        asig_gps = {}
        for _ in range(min(2, len(gps_ord))): asig_gps[gps_ord.pop(0)] = "T1"
        for _ in range(min(2, len(gps_ord))): asig_gps[gps_ord.pop(0)] = "T2"
        gp_sobrante = gps_ord[0] if gps_ord else None
        
        for g in GRUPOS_ABO:
            turno_gp = asig_gps.get(g, "DESCANSO")
            for i, p in enumerate(PERSONAL_ABO[g]):
                ft = turno_gp
                if g == gp_sobrante: ft = "RELEVO" if i == 0 else "DISPONIBLE"
                elif g in gps_descansan: ft = "DESCANSO"
                filas.append({"Fecha": fecha, "Sujeto": p, "Turno": ft})
    return pd.DataFrame(filas)

# =========================================================
# INTERFAZ
# =========================================================
def pantalla_programador():
    st.sidebar.title("MovilGo Pro Enterprise")
    tipo = st.sidebar.radio("Sección", ["Técnicos", "Abordaje"])
    
    st.header(f"📅 Gestión: {tipo}")
    c1, c2 = st.columns(2)
    inicio = c1.date_input("Desde", date.today())
    fin = c2.date_input("Hasta", date.today() + timedelta(days=30))

    descansos = {}
    ciclo = "Diario"
    if tipo == "Técnicos":
        cols = st.columns(4)
        for i, g in enumerate(GRUPOS_TEC): descansos[g] = cols[i].selectbox(f"{g}", DIAS_ES, index=(5 if i<2 else 6))
    else:
        cr, cd = st.columns([1,3])
        ciclo = cr.selectbox("Rotación de Bloques", ["Diario", "Quincenal", "Mensual"])
        cols_a = cd.columns(5)
        for i, g in enumerate(GRUPOS_ABO): descansos[g] = cols_a[i].selectbox(g, DIAS_ES, index=i)

    if st.button(f"🚀 Generar Malla {tipo}"):
        df = generar_malla_tecnicos(inicio, fin, descansos) if tipo == "Técnicos" else generar_malla_abordaje(inicio, fin, descansos, ciclo)
        st.session_state[f"m_{tipo}"] = df

    key = f"m_{tipo}"
    if key in st.session_state:
        df_view = st.session_state[key].copy()
        df_view["Label"] = df_view["Fecha"].apply(lambda x: f"{INICIALES[DIAS_ES[x.weekday()]]} - {x.strftime('%Y-%m-%d')}")
        pivot = df_view.pivot(index="Sujeto", columns="Label", values="Turno")
        sorted_cols = sorted(pivot.columns, key=lambda x: x.split(" - ")[1])
        pivot = pivot[sorted_cols]

        st.subheader("📝 Editor Pro")
        config_cols = {str(c): st.column_config.SelectboxColumn(options=OPCIONES_TURNOS, width="small") for c in pivot.columns}
        df_edit = st.data_editor(style_malla(pivot), use_container_width=True, column_config=config_cols)

        if st.button("💾 Guardar y Auditar"):
            df_final = df_edit.reset_index().melt(id_vars="Sujeto", var_name="Label", value_name="Turno")
            df_final["Fecha"] = pd.to_datetime(df_final["Label"].apply(lambda x: x.split(" - ")[1]))
            st.session_state[key] = df_final
            guardar_github(df_final, f"malla_{tipo.lower()}.xlsx")
            st.toast("✅ Sincronizado")

        # PANEL DE ALERTAS Y MÉTRICAS
        st.divider()
        errs, cob = ejecutar_auditoria(st.session_state[key], tipo)
        a1, a2 = st.columns([1, 2])
        with a1:
            st.metric("Alertas de Revisión", len(errs))
            with st.container(height=300):
                if errs:
                    for e in errs: st.error(e)
                else: st.success("✅ Malla sin conflictos.")
        with a2:
            st.subheader("📈 Cobertura")
            st.line_chart(cob)

if __name__ == "__main__":
    pantalla_programador()
