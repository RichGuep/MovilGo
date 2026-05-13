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
    return df_pivot.style.map(apply_styles)

# =========================================================
# 2. FUNCIONES DE APOYO Y GITHUB
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

# =========================================================
# 3. MOTOR TÉCNICOS: COMPENSADO POR TRABAJAR EN "DOMINGO DE LEY"
# =========================================================
def generar_malla_tecnicos(inicio, fin, descansos_ley):
    filas = []
    pendientes_semana = {g: 0 for g in GRUPOS_TEC} # Contador de días a compensar
    u_turno = {g: "DESCANSO" for g in GRUPOS_TEC}
    c_bloque = {g: 0 for g in GRUPOS_TEC}

    for fecha in pd.date_range(inicio, fin):
        dia_n = DIAS_ES[fecha.weekday()]
        # Resetear al inicio de cada semana (Lunes)
        if fecha.weekday() == 0: pendientes_semana = {g: 0 for g in GRUPOS_TEC}
        
        asignados = {}
        # Quién debería descansar hoy según su contrato/ley
        quien_debe_descansar_hoy = [g for g, d in descansos_ley.items() if d == dia_n]
        activos_potenciales = list(GRUPOS_TEC)

        # 1. PAGO DE COMPENSADO (Si hay saldo y hay cupo para T1, T2, T3)
        if 0 <= fecha.weekday() <= 4:
            for g in list(activos_potenciales):
                if pendientes_semana[g] > 0 and len(activos_potenciales) > 3:
                    asignados[g] = "COMPENSADO"
                    pendientes_semana[g] -= 1
                    activos_potenciales.remove(g)
                    break

        # 2. ASIGNACIÓN DE DESCANSO DE LEY (Si el cupo lo permite)
        for g_desc en quien_debe_descansar_hoy:
            if g_desc in activos_potenciales:
                if len(activos_potenciales) > 3:
                    asignados[g_desc] = "DESCANSO"
                    activos_potenciales.remove(g_desc)
                else:
                    # TRABAJO FORZOSO EN DÍA DE LEY -> Se genera COMPENSADO inmediato
                    pendientes_semana[g_desc] += 1

        # 3. COBERTURA OPERATIVA (T1, T2, T3)
        turnos_necesarios = ["T3", "T2", "T1"]
        for t in turnos_necesarios:
            if activos_potenciales:
                # Priorizar el grupo que ya venía en ese turno (bloques de 4)
                sel = next((g for g in activos_potenciales if u_turno[g] == t and c_bloque[g] < 4), activos_potenciales[0])
                asignados[sel] = t
                c_bloque[sel] = (c_bloque[sel] + 1) if u_turno[sel] == t else 1
                u_turno[sel] = t
                activos_potenciales.remove(sel)

        # 4. T1 APOYO / RESTANTES
        for g in activos_potenciales:
            asignados[g] = "T1 APOYO"
            u_turno[g] = "T1 APOYO"
            c_bloque[g] = 0

        for g in GRUPOS_TEC:
            filas.append({"Fecha": fecha, "Sujeto": g, "Turno": asignados.get(g, "T1 APOYO")})
            
    return pd.DataFrame(filas)

# =========================================================
# 4. MOTOR ABORDAJE: COMPENSADO POR TRABAJAR EN "DOMINGO DE LEY"
# =========================================================
def generar_malla_abordaje_individual(inicio, fin, d_ba, d_bb):
    df_emp = cargar_excel("empleados_grupos.xlsx")
    personal = df_emp[df_emp['GrupoAsignado'] == "Abordaje"]['Nombre'].tolist() if not df_emp.empty else [f"Asesor {i}" for i in range(1, 26)]
    
    filas = []
    deuda_inmediata = {p: 0 for p in personal}
    mitad = len(personal) // 2
    bloque_a, bloque_b = personal[:mitad], personal[mitad:]
    
    for fecha in pd.date_range(inicio, fin):
        dia_n = DIAS_ES[fecha.weekday()]
        if fecha.weekday() == 0: deuda_inmediata = {p: 0 for p in personal}
        
        asig = {}
        sem_num = fecha.isocalendar()[1]
        inv = (sem_num % 2 == 0)
        d_hoy_a, d_hoy_b = (d_ba, d_bb) if not inv else (d_bb, d_ba)

        # 1. Pago de compensado (L-V)
        if 0 <= fecha.weekday() <= 4:
            for p in personal:
                if deuda_inmediata[p] > 0 and len(asig) < (len(personal) - 20):
                    asig[p] = "COMPENSADO"
                    deuda_inmediata[p] -= 1

        # 2. Descansos de Ley (Día parametrizado)
        for p in personal:
            if p not in asig:
                if (p in bloque_a and dia_n == d_hoy_a) or (p in bloque_b and dia_n == d_hoy_b):
                    asig[p] = "DESCANSO"

        # 3. Cupo 10/10: Si faltan, los que "descansaban" trabajan y cobran compensado
        libres = [p for p in personal if p not in asig]
        if len(libres) < 20:
            faltantes = 20 - len(libres)
            candidatos = [p for p in personal if asig.get(p) == "DESCANSO"]
            for i in range(min(faltantes, len(candidatos))):
                p_extra = candidatos[i]
                del asig[p_extra]
                libres.append(p_extra)
                deuda_inmediata[p_extra] += 1 # Trabajó su Domingo -> Se le debe 1 día

        random.shuffle(libres)
        c1 = c2 = 0
        for p in libres:
            if c1 < 10: asig[p] = "T1"; c1 += 1
            elif c2 < 10: asig[p] = "T2"; c2 += 1
            else: asig[p] = "DISPONIBLE"

        for p in personal: filas.append({"Fecha": fecha, "Sujeto": p, "Turno": asig.get(p, "DESCANSO")})
    return pd.DataFrame(filas)

# =========================================================
# 5. PANTALLA Y AUDITORÍA
# =========================================================
def pantalla_programador():
    st.title("🛡️ Programación y Auditoría MovilGO")
    tipo = st.sidebar.radio("Módulo", ["Técnicos", "Abordaje"])
    
    c1, c2 = st.columns(2)
    inicio = c1.date_input("Desde", date.today())
    fin = c2.date_input("Hasta", date.today() + timedelta(days=21))

    with st.expander("⚙️ Configuración de Descansos de Ley"):
        if tipo == "Técnicos":
            desc_conf = {g: st.selectbox(f"{g}", DIAS_ES, index=(5 if i<2 else 6)) for i, g in enumerate(GRUPOS_TEC)}
        else:
            ca, cb = st.columns(2)
            d_ba = ca.selectbox("Bloque A (Sáb)", DIAS_ES, index=5); d_bb = cb.selectbox("Bloque B (Dom)", DIAS_ES, index=6)

    if st.button("🚀 Generar y Auditar"):
        if tipo == "Técnicos": st.session_state.m_tec = generar_malla_tecnicos(inicio, fin, desc_conf)
        else: st.session_state.m_abo = generar_malla_abordaje_individual(inicio, fin, d_ba, d_bb)

    key = "m_tec" if tipo == "Técnicos" else "m_abo"
    if key in st.session_state:
        df = st.session_state[key]
        pivot = df.pivot(index="Sujeto", columns="Fecha", values="Turno")
        pivot.columns = [f"{INICIALES[DIAS_ES[c.weekday()]]} {c.strftime('%d/%m')}" for c in pivot.columns]
        
        st.subheader("📋 Malla Generada")
        st.data_editor(style_malla(pivot), use_container_width=True)

        # Auditoría de cumplimiento
        st.divider()
        st.subheader("⚖️ Auditoría de Cumplimiento Legal")
        
        # Conteo de compensados
        conteo_turnos = df.groupby(["Sujeto", "Turno"]).size().unstack(fill_value=0)
        
        col_aud1, col_aud2 = st.columns(2)
        with col_aud1:
            st.write("**Reporte de Turnos**")
            st.dataframe(conteo_turnos)
            
        with col_aud2:
            st.write("**Validación de Regla de Descanso**")
            if "COMPENSADO" in conteo_turnos.columns:
                total_c = conteo_turnos["COMPENSADO"].sum()
                st.success(f"Se han asignado {total_c} compensados por trabajo en día de ley.")
            else:
                # Revisar si alguien trabajó su día de ley y NO recibió compensado
                st.warning("No se generaron compensados. Verifique si la cobertura permitió dar el descanso de ley.")

        if st.button("💾 Guardar Malla en GitHub"):
            guardar_github(df, f"malla_{tipo.lower()}.xlsx")
