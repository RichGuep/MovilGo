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
# 3. MOTOR TÉCNICOS: COMPENSADO INMEDIATO
# =========================================================
def generar_malla_tecnicos(inicio, fin, descansos_ley):
    filas = []
    # Diccionario para saber quién trabajó en su descanso y debe compensar en la semana actual
    pendientes_semana = {g: False for g in GRUPOS_TEC}
    u_turno = {g: "DESCANSO" for g in GRUPOS_TEC}
    c_bloque = {g: 0 for g in GRUPOS_TEC}

    for fecha in pd.date_range(inicio, fin):
        dia_n = DIAS_ES[fecha.weekday()]
        # Resetear pendientes si es Lunes (nueva semana)
        if fecha.weekday() == 0: pendientes_semana = {g: False for g in GRUPOS_TEC}
        
        asignados = {}
        debe_descansar = [g for g, d in descansos_ley.items() if d == dia_n]
        activos_potenciales = list(GRUPOS_TEC)

        # 1. Prioridad: Asignar COMPENSADO si alguien trabajó el fin de semana o su día previo
        if 0 <= fecha.weekday() <= 4:
            for g in activos_potenciales[:]:
                if pendientes_semana[g] and len(activos_potenciales) > 3:
                    asignados[g] = "COMPENSADO"
                    pendientes_semana[g] = False
                    activos_potenciales.remove(g)
                    break

        # 2. Descanso de Ley (Si no está compensando ya)
        if debe_descansar and debe_descansar[0] in activos_potenciales:
            descansador = debe_descansar[0]
            # Si hay 4 grupos, puede descansar. Si solo hay 3, DEBE TRABAJAR y genera deuda.
            if len(activos_potenciales) > 3:
                asignados[descansador] = "DESCANSO"
                activos_potenciales.remove(descansador)
            else:
                pendientes_semana[descansador] = True # Se activa compensado inmediato

        # 3. Cobertura Blindada T3, T2, T1
        for t in ["T3", "T2", "T1"]:
            if activos_potenciales:
                sel = next((g for g in activos_potenciales if u_turno[g] == t and c_bloque[g] < 4), activos_potenciales[0])
                asignados[sel] = t
                c_bloque[sel] = (c_bloque[sel] + 1) if u_turno[sel] == t else 1
                u_turno[sel] = t
                activos_potenciales.remove(sel)

        for g in activos_potenciales:
            asignados[g] = "T1 APOYO"
            u_turno[g] = "T1 APOYO"
            c_bloque[g] = 0

        for g in GRUPOS_TEC:
            filas.append({"Fecha": fecha, "Sujeto": g, "Turno": asignados.get(g, "T1 APOYO")})
            
    return pd.DataFrame(filas)

# =========================================================
# 4. MOTOR ABORDAJE: CUPO 10/10 Y COMPENSADO EXPRESS
# =========================================================
def generar_malla_abordaje_individual(inicio, fin, d_ba, d_bb):
    df_emp = cargar_excel("empleados_grupos.xlsx")
    personal = df_emp[df_emp['GrupoAsignado'] == "Abordaje"]['Nombre'].tolist() if not df_emp.empty else [f"Asesor {i}" for i in range(1, 26)]
    
    filas = []
    pendientes_p = {p: False for p in personal}
    mitad = len(personal) // 2
    bloque_a, bloque_b = personal[:mitad], personal[mitad:]
    
    for fecha in pd.date_range(inicio, fin):
        dia_n = DIAS_ES[fecha.weekday()]
        if fecha.weekday() == 0: pendientes_p = {p: False for p in personal}
        
        asig = {}
        inv = (fecha.isocalendar()[1] % 2 == 0)
        d_hoy_a, d_hoy_b = (d_ba, d_bb) if not inv else (d_bb, d_ba)

        # 1. Compensado inmediato (L-V)
        if 0 <= fecha.weekday() <= 4:
            for p in personal:
                if pendientes_p[p] and len(asig) < (len(personal) - 20):
                    asig[p] = "COMPENSADO"
                    pendientes_p[p] = False

        # 2. Descansos teóricos
        for p in personal:
            if p not in asig:
                if (p in bloque_a and dia_n == d_hoy_a) or (p in bloque_b and dia_n == d_hoy_b):
                    asig[p] = "DESCANSO"

        # 3. Asegurar Cupo 10/10
        libres = [p for p in personal if p not in asig]
        if len(libres) < 20:
            faltantes = 20 - len(libres)
            candidatos = [p for p in personal if asig.get(p) == "DESCANSO"]
            for i in range(min(faltantes, len(candidatos))):
                p_extra = candidatos[i]
                del asig[p_extra]
                libres.append(p_extra)
                pendientes_p[p_extra] = True # Genera compensado para mañana u otro día de la semana

        random.shuffle(libres)
        c1 = c2 = 0
        for p in libres:
            if c1 < 10: asig[p] = "T1"; c1 += 1
            elif c2 < 10: asig[p] = "T2"; c2 += 1
            else: asig[p] = "DISPONIBLE"

        for p in personal: filas.append({"Fecha": fecha, "Sujeto": p, "Turno": asig.get(p, "DESCANSO")})
    return pd.DataFrame(filas)

# =========================================================
# 5. PANTALLA Y AUDITORÍA COMPLETA
# =========================================================
def pantalla_programador():
    st.title("🛡️ Auditoría y Programación MovilGO")
    tipo = st.sidebar.radio("Módulo", ["Técnicos", "Abordaje"])
    
    c1, c2 = st.columns(2)
    inicio = c1.date_input("Desde", date.today())
    fin = c2.date_input("Hasta", date.today() + timedelta(days=21))

    with st.expander("⚙️ Configuración de Descansos"):
        if tipo == "Técnicos":
            desc_conf = {g: st.selectbox(f"{g}", DIAS_ES, index=(5 if i<2 else 6)) for i, g in enumerate(GRUPOS_TEC)}
        else:
            ca, cb = st.columns(2)
            d_ba = ca.selectbox("Bloque A (Sáb)", DIAS_ES, index=5); d_bb = cb.selectbox("Bloque B (Dom)", DIAS_ES, index=6)

    if st.button(f"🚀 Generar y Auditar {tipo}"):
        if tipo == "Técnicos": st.session_state.m_tec = generar_malla_tecnicos(inicio, fin, desc_conf)
        else: st.session_state.m_abo = generar_malla_abordaje_individual(inicio, fin, d_ba, d_bb)

    key = "m_tec" if tipo == "Técnicos" else "m_abo"
    if key in st.session_state:
        df = st.session_state[key]
        pivot = df.pivot(index="Sujeto", columns="Fecha", values="Turno")
        pivot.columns = [f"{INICIALES[DIAS_ES[c.weekday()]]} {c.strftime('%d/%m')}" for c in pivot.columns]
        
        st.subheader("📋 Malla Generada")
        st.data_editor(style_malla(pivot), use_container_width=True)

        # --- AUDITORÍA DE EQUILIBRIO ---
        st.divider()
        st.subheader("⚖️ Auditoría de Equilibrio y Ley")
        
        # 1. Verificación de Compensados Inmediatos
        resumen = df.groupby(["Sujeto", "Turno"]).size().unstack(fill_value=0)
        
        col_a, col_b = st.columns(2)
        with col_a:
            st.write("**Conteo de Turnos por Persona**")
            st.dataframe(resumen)
        
        with col_b:
            # Alerta si alguien trabajó fin de semana y no tiene un COMPENSADO en la tabla
            st.write("**Estado de Alertas**")
            conteo_dias = df.groupby("Fecha")["Turno"].value_counts().unstack(fill_value=0)
            
            if tipo == "Abordaje":
                incumplimiento = conteo_dias[(conteo_dias["T1"] < 10) | (conteo_dias["T2"] < 10)]
                if not incumplimiento.empty:
                    st.error(f"⚠️ Hay {len(incumplimiento)} días con cupo incompleto.")
                else:
                    st.success("✅ Cupo 10/10 garantizado todos los días.")
            
            if "COMPENSADO" in resumen.columns:
                st.info(f"ℹ️ Se han otorgado {resumen['COMPENSADO'].sum()} días compensados inmediatos.")
            else:
                st.warning("⚠️ No se detectaron compensados otorgados. Verifique si hubo trabajo en domingo.")

        if st.button("💾 Finalizar y Guardar"):
            guardar_github(df, f"malla_{tipo.lower()}.xlsx")
            st.success("Archivo guardado en GitHub.")

def pantalla_personal():
    st.title("👥 Personal")
    df_emp = cargar_excel("empleados_grupos.xlsx")
    df_ed = st.data_editor(df_emp, num_rows="dynamic", use_container_width=True)
    if st.button("Guardar"): guardar_github(df_ed, "empleados_grupos.xlsx")
