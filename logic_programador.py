import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import holidays
import io
from github import Github

# =========================================================
# 1. CONFIGURACIÓN Y CONSTANTES
# =========================================================
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

# =========================================================
# 2. CONECTIVIDAD GITHUB
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
# 3. ESTILOS Y AUDITORÍA DETALLADA
# =========================================================
def style_malla(df_pivot):
    def apply_styles(val):
        bg = COLORES_MAP.get(val, "")
        txt = "white" if val == "DESCANSO" else "#17202A"
        return f'background-color: {bg}; color: {txt}; font-weight: 700; border: 0.5px solid #D5DBDB' if bg else ''
    return df_pivot.style.map(apply_styles)

def ejecutar_auditoria_completa(df, tipo):
    df = df.copy()
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    errores = []

    # Cobertura por turnos
    t1 = df[df["Turno"] == "T1"].groupby("Fecha").size()
    t2 = df[df["Turno"] == "T2"].groupby("Fecha").size()
    t3 = df[df["Turno"] == "T3"].groupby("Fecha").size()
    
    if tipo == "Técnicos":
        cobertura = t1 + t2 + t3
        for f, c in cobertura.items():
            if c < 3: errores.append(f"❌ Cobertura insuficiente {f.date()} ({c}/3)")
    else:
        # Auditoría de Abordaje: 10 personas por turno T1 y T2
        for f in t1.index:
            if t1.get(f,0) != 10: errores.append(f"⚠️ {f.date()}: T1 debe tener 10 personas (Hay {t1.get(f,0)})")
            if t2.get(f,0) != 10: errores.append(f"⚠️ {f.date()}: T2 debe tener 10 personas (Hay {t2.get(f,0)})")
        cobertura = t1 + t2

    # Métricas de Equidad
    equidad = df.groupby(["Sujeto", "Turno"]).size().unstack(fill_value=0)
    for c in ["DESCANSO", "COMPENSADO", "T1", "T2", "T3"]:
        if c not in equidad.columns: equidad[c] = 0
    equidad["Días_Trabajados"] = equidad.drop(columns=["DESCANSO", "COMPENSADO"], errors='ignore').sum(axis=1)
    
    return errores, cobertura, equidad

# =========================================================
# 4. GENERACIÓN TÉCNICOS (ORIGINAL + EQUIDAD)
# =========================================================
def generar_malla_tecnicos(inicio, fin, descansos_ley):
    filas = []
    deudas_comp = {g: 0 for g in GRUPOS_TEC}
    for fecha in pd.date_range(inicio, fin):
        dia_idx = fecha.weekday(); dia_nombre = DIAS_ES[dia_idx]; sem_num = fecha.isocalendar()[1]
        asignados = {}
        
        gps_hoy = [g for g, d in descansos_ley.items() if d == dia_nombre]
        if len(gps_hoy) > 1:
            idx = sem_num % len(gps_hoy)
            desc = gps_hoy[idx]; asignados[desc] = "DESCANSO"
            for g in gps_hoy: 
                if g != desc: deudas_comp[g] += 1
        elif len(gps_hoy) == 1:
            asignados[gps_hoy[0]] = "DESCANSO"

        activos = [g for g in GRUPOS_TEC if g not in asignados]
        offset = sem_num % len(GRUPOS_TEC)
        activos_rotados = sorted(activos, key=lambda x: (GRUPOS_TEC.index(x) + offset) % len(GRUPOS_TEC))

        if 0 <= dia_idx <= 4 and len(asignados) == 0:
            cands = sorted(activos_rotados, key=lambda x: deudas_comp[x], reverse=True)
            if cands and deudas_comp[cands[0]] > 0:
                sel = cands[0]; asignados[sel] = "COMPENSADO"; deudas_comp[sel] -= 1; activos_rotados.remove(sel)

        turnos_op = ["T3", "T2", "T1", "T1 APOYO"]
        for g in activos_rotados:
            for t in turnos_op:
                if t not in asignados.values():
                    asignados[g] = t; break
            if g not in asignados: asignados[g] = "T1 APOYO"

        for g in GRUPOS_TEC:
            filas.append({"Fecha": fecha, "Sujeto": g, "Turno": asignados.get(g, "DESCANSO")})
    return pd.DataFrame(filas)

# =========================================================
# 5. GENERACIÓN ABORDAJE (BLOQUE SÓLIDO + ROTACIÓN)
# =========================================================
def generar_malla_abordaje(inicio, fin, desc_cfg, ciclo):
    filas = []
    for fecha in pd.date_range(inicio, fin):
        dia_n = DIAS_ES[fecha.weekday()]; sem_num = fecha.isocalendar()[1]
        gps_descansan = [g for g in GRUPOS_ABO if desc_cfg.get(g) == dia_n]
        
        # Lógica de Bloque: El turno se decide por Grupo, no por Persona
        if ciclo == "Diario": offset = (fecha - pd.to_datetime(inicio)).days
        elif ciclo == "Quincenal": offset = sem_num // 2
        else: offset = fecha.month
        
        gps_activos = [g for g in GRUPOS_ABO if g not in gps_descansan]
        gps_rotados = sorted(gps_activos, key=lambda g: (GRUPOS_ABO.index(g) + offset) % 5)
        
        asig_bloque = {}
        # Asignar 2 grupos a T1 (10 personas) y 2 a T2 (10 personas)
        if len(gps_rotados) >= 2:
            for _ in range(2): asig_bloque[gps_rotados.pop(0)] = "T1"
        if len(gps_rotados) >= 2:
            for _ in range(2): asig_bloque[gps_rotados.pop(0)] = "T2"
        
        # El grupo restante (si hay) hace RELEVO/DISPONIBLE en bloque
        gp_sobrante = gps_rotados[0] if gps_rotados else None

        for g in GRUPOS_ABO:
            turno_base = asig_bloque.get(g, "DESCANSO")
            if g == gp_sobrante: turno_base = "RELEVO"
            
            for p in PERSONAL_ABO[g]:
                filas.append({
                    "Fecha": fecha, "Sujeto": p, 
                    "Turno": turno_base if g not in gps_descansan else "DESCANSO"
                })
    return pd.DataFrame(filas)

# =========================================================
# 6. INTERFAZ MAESTRA (PROGRAMADOR)
# =========================================================
def pantalla_programador():
    st.sidebar.markdown("---")
    tipo = st.sidebar.radio("🔧 Configuración de Malla", ["Técnicos", "Abordaje"])
    
    with st.container(border=True):
        c1, c2 = st.columns(2)
        inicio = c1.date_input("Fecha Inicio", date.today())
        fin = c2.date_input("Fecha Fin", date.today() + timedelta(days=21))
        
        desc_input = {}
        lista_g = GRUPOS_TEC if tipo == "Técnicos" else GRUPOS_ABO
        cols = st.columns(len(lista_g))
        for i, g in enumerate(lista_g):
            desc_input[g] = cols[i].selectbox(f"Libra {g}", DIAS_ES, index=(5 if i<2 else 6) if tipo == "Técnicos" else i%7)
        
        ciclo = "Fijo"
        if tipo == "Abordaje":
            ciclo = st.selectbox("Ciclo de Rotación Grupal", ["Diario", "Quincenal", "Mensual"], index=1)

    if st.button(f"⚡ Generar y Optimizar {tipo}", use_container_width=True):
        st.session_state[f"m_{tipo}"] = generar_malla_tecnicos(inicio, fin, desc_input) if tipo == "Técnicos" else generar_malla_abordaje(inicio, fin, desc_input, ciclo)

    key = f"m_{tipo}"
    if key in st.session_state:
        df_base = st.session_state[key].copy()
        df_base["Label"] = df_base["Fecha"].apply(lambda x: f"{INICIALES[DIAS_ES[x.weekday()]]} {x.strftime('%d/%m')}")
        pivot = df_base.pivot(index="Sujeto", columns="Label", values="Turno")
        
        # Orden cronológico
        sorted_cols = sorted(pivot.columns, key=lambda x: datetime.strptime(x.split(" ")[1] + f"/{date.today().year}", '%d/%m/%Y'))
        pivot = pivot[sorted_cols]

        st.subheader("📝 Editor de Turnos (Sincronizado)")
        config_cols = {str(c): st.column_config.SelectboxColumn(options=OPCIONES_TURNOS, width="small") for c in pivot.columns}
        df_edit = st.data_editor(style_malla(pivot), use_container_width=True, column_config=config_cols)

        # Procesamiento Auditoría
        df_final = df_edit.reset_index().melt(id_vars="Sujeto", var_name="Label", value_name="Turno")
        map_fechas = dict(zip(df_base["Label"], df_base["Fecha"]))
        df_final["Fecha"] = df_final["Label"].map(map_fechas)
        errs, cob, equidad = ejecutar_auditoria_completa(df_final, tipo)

        st.divider()
        st.subheader("📊 Análisis de Equidad y Sobrecarga")
        col1, col2 = st.columns(2)
        with col1:
            st.dataframe(equidad.style.highlight_max(axis=0, color='#FADBD8').format(precision=0), use_container_width=True)
        with col2:
            st.bar_chart(equidad[["T1", "T2", "T3"]] if "T3" in equidad.columns else equidad[["T1", "T2"]])

        # Acciones: Guardar y Descargar
        f1, f2 = st.columns(2)
        with f1:
            if st.button("💾 Guardar en GitHub", use_container_width=True):
                guardar_github(df_final, f"malla_{tipo.lower()}.xlsx"); st.success("Sincronizado")
        with f2:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_edit.to_excel(writer, sheet_name='Malla')
                equidad.to_excel(writer, sheet_name='Equidad')
                pd.DataFrame(errs, columns=["Alertas"]).to_excel(writer, sheet_name='Auditoria', index=False)
            st.download_button("📥 Descargar Escenario Completo", output.getvalue(), f"Reporte_{tipo}.xlsx", use_container_width=True)

        if errs:
            with st.expander("🚨 Registro de Alertas de Auditoría", expanded=True):
                for e in errs: st.error(e)
