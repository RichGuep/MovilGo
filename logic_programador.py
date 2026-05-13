import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date, time
import holidays
import io
import random
from github import Github

# =========================================================
# 1. CONFIGURACIÓN, CONSTANTES Y ESTILOS
# =========================================================
DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
INICIALES = {"Lunes": "L", "Martes": "M", "Miércoles": "X", "Jueves": "J", "Viernes": "V", "Sábado": "S", "Domingo": "D"}
festivos_co = holidays.Colombia()

GRUPOS_TEC = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]
OPCIONES_TURNOS = ["T1", "T2", "T3", "RELEVO", "DISPONIBLE", "T1 APOYO", "DESCANSO", "COMPENSADO"]

COLORES_MAP = {
    "T1": "#D6EAF8", "T2": "#D5F5E3", "T3": "#FADBD8",
    "RELEVO": "#E8DAEF", "DISPONIBLE": "#EAEDED",
    "T1 APOYO": "#EBF5FB", "DESCANSO": "#2C3E50", "COMPENSADO": "#FDEBD0"
}

def style_malla(df_pivot):
    def apply_styles(val):
        bg = COLORES_MAP.get(val, "")
        txt = "white" if val == "DESCANSO" else "black"
        return f'background-color: {bg}; color: {txt}; font-weight: 700; border: 0.5px solid #D5DBDB' if bg else ''
    
    def highlight_special_days(col):
        try:
            fecha_str = col.name.split(" - ")[1]
            f_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            if f_obj.weekday() >= 5 or f_obj in festivos_co:
                return ['border-bottom: 3px solid #E67E22;' for _ in col]
        except: pass
        return ['' for _ in col]
    
    return df_pivot.style.map(apply_styles).apply(highlight_special_days, axis=0)

# =========================================================
# 2. CONECTIVIDAD GITHUB
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
# 3. MOTORES DE GENERACIÓN (TECNICOS DEUDA / ABORDAJE CUPO)
# =========================================================

def generar_malla_tecnicos(inicio, fin, descansos_ley):
    filas = []
    deudas_comp = {g: 0 for g in GRUPOS_TEC}
    u_turno = {g: "DESCANSO" for g in GRUPOS_TEC}
    c_bloque = {g: 0 for g in GRUPOS_TEC}

    for fecha in pd.date_range(inicio, fin):
        dia_nombre = DIAS_ES[fecha.weekday()]
        asignados = {}
        
        # 1. Candidato a descanso de ley hoy
        debe_descansar = [g for g, d in descansos_ley.items() if d == dia_nombre]
        activos_potenciales = list(GRUPOS_TEC)
        
        # 2. Asignar Descanso de Ley (siempre que queden 3 para T1, T2, T3)
        descansador_hoy = None
        if debe_descansar:
            descansador_hoy = debe_descansar[0]
            asignados[descansador_hoy] = "DESCANSO"
            activos_potenciales.remove(descansador_hoy)
        
        # 3. Pago de Compensados (Solo si sobran grupos y hay deuda)
        if len(activos_potenciales) > 3:
            cands_comp = sorted(activos_potenciales, key=lambda x: deudas_comp[x], reverse=True)
            if deudas_comp[cands_comp[0]] > 0:
                lucky_g = cands_comp[0]
                asignados[lucky_g] = "COMPENSADO"
                deudas_comp[lucky_g] -= 1
                activos_potenciales.remove(lucky_g)

        # 4. Cobertura Blindada T3, T2, T1
        turnos_principales = ["T3", "T2", "T1"]
        # Priorizar continuidad de bloque
        activos_potenciales = sorted(activos_potenciales, key=lambda g: (u_turno[g], c_bloque[g]), reverse=True)
        
        for t in turnos_principales:
            if activos_potenciales:
                # Buscar si alguien ya traía este turno
                sel = next((g for g in activos_potenciales if u_turno[g] == t and c_bloque[g] < 4), activos_potenciales[0])
                asignados[sel] = t
                if u_turno[sel] == t: c_bloque[sel] += 1
                else: c_bloque[sel] = 1
                u_turno[sel] = t
                activos_potenciales.remove(sel)

        # 5. Restantes -> T1 APOYO
        for g in activos_potenciales:
            asignados[g] = "T1 APOYO"
            u_turno[g] = "T1 APOYO"
            c_bloque[g] = 0

        # 6. Registro de Deuda: Si el descansador por ley tuvo que trabajar hoy
        if descansador_hoy and asignados.get(descansador_hoy) in ["T1", "T2", "T3"]:
            deudas_comp[descansador_hoy] += 1

        for g in GRUPOS_TEC:
            filas.append({"Fecha": fecha, "Sujeto": g, "Turno": asignados.get(g, "T1 APOYO")})
            
    return pd.DataFrame(filas)

def generar_malla_abordaje_individual(inicio, fin, d_ba, d_bb):
    df_emp = cargar_excel("empleados_grupos.xlsx")
    personal = df_emp[df_emp['GrupoAsignado'] == "Abordaje"]['Nombre'].tolist() if not df_emp.empty else [f"Asesor {i}" for i in range(1, 26)]
    
    filas = []
    deudas_p = {p: 0 for p in personal}
    mitad = len(personal) // 2
    bloque_a, bloque_b = personal[:mitad], personal[mitad:]
    
    for fecha in pd.date_range(inicio, fin):
        dia_n = DIAS_ES[fecha.weekday()]; sem = fecha.isocalendar()[1]
        asig = {}
        inv = sem % 2 == 0
        d_hoy_a, d_hoy_b = (d_ba, d_bb) if not inv else (d_bb, d_ba)

        if 0 <= fecha.weekday() <= 4:
            p_con_deuda = sorted([p for p in personal if deudas_p[p] > 0], key=lambda x: deudas_p[x], reverse=True)
            for p in p_con_deuda:
                if len(asig) < (len(personal) - 20):
                    asig[p] = "COMPENSADO"; deudas_p[p] -= 1

        for p in bloque_a:
            if dia_n == d_hoy_a and p not in asig: asig[p] = "DESCANSO"
        for p in bloque_b:
            if dia_n == d_hoy_b and p not in asig: asig[p] = "DESCANSO"

        libres = [p for p in personal if p not in asig]
        if len(libres) < 20:
            faltantes = 20 - len(libres)
            candidatos = sorted([p for p in personal if asig.get(p) == "DESCANSO"], key=lambda x: deudas_p[x])
            for i in range(min(faltantes, len(candidatos))):
                p_extra = candidatos[i]
                del asig[p_extra]; libres.append(p_extra); deudas_p[p_extra] += 1

        random.shuffle(libres)
        c1 = c2 = 0
        for p in libres:
            if c1 < 10: asig[p] = "T1"; c1 += 1
            elif c2 < 10: asig[p] = "T2"; c2 += 1
            else: asig[p] = "DISPONIBLE"

        for p in personal: filas.append({"Fecha": fecha, "Sujeto": p, "Turno": asig.get(p, "DESCANSO")})
    return pd.DataFrame(filas)

# =========================================================
# 4. INTERFACES DE PANTALLA
# =========================================================

def pantalla_programador():
    st.title("🚀 MovilGo Optimizer Pro")
    tipo = st.sidebar.radio("Sección", ["Técnicos", "Abordaje"])
    
    c1, c2 = st.columns(2)
    inicio = c1.date_input("Desde", date.today())
    fin = c2.date_input("Hasta", date.today() + timedelta(days=21))

    with st.expander("⚙️ Configuración de Descansos"):
        if tipo == "Técnicos":
            desc_conf = {g: st.selectbox(f"{g}", DIAS_ES, index=(5 if i<2 else 6)) for i, g in enumerate(GRUPOS_TEC)}
        else:
            ca, cb = st.columns(2)
            d_ba = ca.selectbox("Bloque A", DIAS_ES, index=5); d_bb = cb.selectbox("Bloque B", DIAS_ES, index=6)

    if st.button(f"🚀 Generar Malla {tipo}"):
        if tipo == "Técnicos": st.session_state.m_tec = generar_malla_tecnicos(inicio, fin, desc_conf)
        else: st.session_state.m_abo = generar_malla_abordaje_individual(inicio, fin, d_ba, d_bb)

    m_key = "m_tec" if tipo == "Técnicos" else "m_abo"
    if m_key in st.session_state:
        df = st.session_state[m_key]
        df_view = df.copy()
        df_view["Label"] = df_view["Fecha"].apply(lambda x: f"{INICIALES[DIAS_ES[x.weekday()]]} - {x.strftime('%Y-%m-%d')}")
        pivot = df_view.pivot(index="Sujeto", columns="Label", values="Turno").fillna("DESCANSO")
        sorted_cols = sorted(pivot.columns, key=lambda x: x.split(" - ")[1])
        pivot = pivot[sorted_cols]

        st.subheader("📝 Editor Maestro")
        config_cols = {str(c): st.column_config.SelectboxColumn(options=OPCIONES_TURNOS, width="small") for c in pivot.columns}
        df_edit = st.data_editor(style_malla(pivot), use_container_width=True, column_config=config_cols)

        # Auditoría Pro
        st.divider()
        df_final = df_edit.reset_index().melt(id_vars="Sujeto", var_name="Label", value_name="Turno")
        df_final["Fecha"] = pd.to_datetime(df_final["Label"].apply(lambda x: x.split(" - ")[1]))
        
        conteo = df_final.groupby(["Label", "Turno"]).size().unstack(fill_value=0)
        
        col_a, col_b = st.columns([2,1])
        with col_a:
            st.subheader("📊 Resumen de Cobertura")
            if tipo == "Abordaje":
                st.dataframe(conteo[["T1", "T2"]].T if "T1" in conteo.columns else conteo.T, use_container_width=True)
            else:
                st.dataframe(conteo[["T1", "T2", "T3"]].T if "T1" in conteo.columns else conteo.T, use_container_width=True)
        
        with col_b:
            st.subheader("⚖️ Historial / Alertas")
            # Mostrar deudas si existen
            resumen_ind = df_final.groupby(["Sujeto", "Turno"]).size().unstack(fill_value=0)
            if "COMPENSADO" in resumen_ind.columns:
                st.write("Compensados otorgados:")
                st.dataframe(resumen_ind[resumen_ind["COMPENSADO"] > 0]["COMPENSADO"])

        if st.button("💾 Sincronizar con GitHub"):
            guardar_github(df_final, f"malla_{tipo.lower()}.xlsx")

def pantalla_personal():
    st.title("👥 Gestión de Personal")
    df_emp = cargar_excel("empleados_grupos.xlsx")
    df_ed = st.data_editor(df_emp, num_rows="dynamic", use_container_width=True)
    if st.button("💾 Guardar"): guardar_github(df_ed, "empleados_grupos.xlsx")
