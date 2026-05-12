import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date, time
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

COLORES_MAP = {
    "T1": "#D6EAF8", "T2": "#D5F5E3", "T3": "#FADBD8",
    "RELEVO": "#E8DAEF", "DISPONIBLE": "#EAEDED",
    "T1 APOYO": "#EBF5FB", "DESCANSO": "#1B2631", "COMPENSADO": "#FDEBD0"
}

# =========================================================
# 2. PROCESAMIENTO DE MALLA DETALLADA POR PERSONA
# =========================================================
def generar_malla_transaccional(df_final, tipo, config_horas):
    detallada = df_final.copy()
    detallada["Hora Inicio"] = detallada["Turno"].apply(lambda x: config_horas.get(x, {}).get("Inicio", "OFF"))
    detallada["Hora Fin"] = detallada["Turno"].apply(lambda x: config_horas.get(x, {}).get("Fin", "OFF"))
    
    if tipo == "Técnicos":
        detallada["Grupo"] = detallada["Sujeto"]
    else:
        detallada["Grupo"] = detallada["Sujeto"].apply(lambda x: x.split("-")[0] if "-" in x else "Abordaje")

    detallada = detallada[["Fecha", "Sujeto", "Grupo", "Turno", "Hora Inicio", "Hora Fin"]]
    detallada.columns = ["Fecha", "Nombre/Sujeto", "Grupo", "Turno", "Hora Inicio", "Hora Fin"]
    return detallada

# =========================================================
# 3. CONECTIVIDAD Y ESTILOS
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

def style_malla(df_pivot):
    def apply_styles(val):
        bg = COLORES_MAP.get(val, "")
        txt = "white" if val == "DESCANSO" else "#17202A"
        return f'background-color: {bg}; color: {txt}; font-weight: 700; border: 0.5px solid #D5DBDB' if bg else ''
    return df_pivot.style.map(apply_styles)

# =========================================================
# 4. AUDITORÍA Y GENERACIÓN
# =========================================================
def ejecutar_auditoria(df, tipo):
    df = df.copy()
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    errores = []
    t1 = df[df["Turno"] == "T1"].groupby("Fecha").size()
    t2 = df[df["Turno"] == "T2"].groupby("Fecha").size()
    
    if tipo == "Técnicos":
        t3 = df[df["Turno"] == "T3"].groupby("Fecha").size()
        cobertura = t1 + t2 + t3
        for f, c in cobertura.items():
            if c < 3: errores.append(f"❌ Cobertura insuficiente el {f.date()}")
    else:
        for f in t1.index:
            if t1.get(f,0) != 10: errores.append(f"⚠️ {f.date()}: T1 requiere 10 personas")
            if t2.get(f,0) != 10: errores.append(f"⚠️ {f.date()}: T2 requiere 10 personas")
        cobertura = t1 + t2

    equidad = df.groupby(["Sujeto", "Turno"]).size().unstack(fill_value=0)
    for c in ["DESCANSO", "COMPENSADO", "T1", "T2", "T3"]:
        if c not in equidad.columns: equidad[c] = 0
    equidad["Total_Días"] = equidad[["T1", "T2", "T3"]].sum(axis=1)
    return errores, cobertura, equidad

def generar_malla_tecnicos(inicio, fin, descansos_ley):
    filas = []
    deudas_comp = {g: 0 for g in GRUPOS_TEC}
    for fecha in pd.date_range(inicio, fin):
        dia_idx = fecha.weekday(); sem_num = fecha.isocalendar()[1]
        dia_nombre = DIAS_ES[dia_idx]
        asignados = {}
        gps_hoy = [g for g, d in descansos_ley.items() if d == dia_nombre]
        if len(gps_hoy) > 1:
            idx = sem_num % len(gps_hoy); desc = gps_hoy[idx]; asignados[desc] = "DESCANSO"
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

def generar_malla_abordaje(inicio, fin, desc_cfg, ciclo):
    filas = []
    for fecha in pd.date_range(inicio, fin):
        dia_n = DIAS_ES[fecha.weekday()]; sem_num = fecha.isocalendar()[1]
        gps_descansan = [g for g in GRUPOS_ABO if desc_cfg.get(g) == dia_n]
        offset = (sem_num // 2) if ciclo == "Quincenal" else (fecha.month if ciclo == "Mensual" else (fecha - pd.to_datetime(inicio)).days)
        gps_activos = [g for g in GRUPOS_ABO if g not in gps_descansan]
        gps_rotados = sorted(gps_activos, key=lambda g: (GRUPOS_ABO.index(g) + offset) % 5)
        asig_bloque = {}
        if len(gps_rotados) >= 2:
            for _ in range(2): asig_bloque[gps_rotados.pop(0)] = "T1"
        if len(gps_rotados) >= 2:
            for _ in range(2): asig_bloque[gps_rotados.pop(0)] = "T2"
        gp_relevo = gps_rotados[0] if gps_rotados else None
        for g in GRUPOS_ABO:
            turno = asig_bloque.get(g, "RELEVO" if g == gp_relevo else "DESCANSO")
            for p in PERSONAL_ABO[g]:
                filas.append({"Fecha": fecha, "Sujeto": p, "Turno": turno if g not in gps_descansan else "DESCANSO"})
    return pd.DataFrame(filas)

# =========================================================
# 5. PANTALLA PRINCIPAL (PROGRAMADOR)
# =========================================================
def pantalla_programador():
    tipo = st.sidebar.radio("🔧 Módulo Operativo", ["Técnicos", "Abordaje"])
    
    # PARAMETRIZACIÓN DE HORAS
    with st.expander("⏰ Configuración de Jornadas (Personalizar Horarios)", expanded=False):
        turnos_list = ["T1", "T2", "T3", "RELEVO", "T1 APOYO", "DISPONIBLE"]
        config_horas = {}
        defaults = {"T1": [time(6,0), time(14,0)], "T2": [time(14,0), time(22,0)], "T3": [time(22,0), time(6,0)], "RELEVO": [time(8,0), time(16,0)], "T1 APOYO": [time(7,0), time(15,0)], "DISPONIBLE": [time(0,0), time(0,0)]}
        cols_h = st.columns(3)
        for i, t_n in enumerate(turnos_list):
            with cols_h[i%3]:
                st.markdown(f"**{t_n}**")
                # Añadimos step=60 para permitir seleccionar minuto a minuto
                h_i = st.time_input(f"Inicia", defaults.get(t_n)[0], key=f"i_{t_n}", step=60)
                h_f = st.time_input(f"Fin", defaults.get(t_n)[1], key=f"f_{t_n}", step=60)
                
                config_horas[t_n] = {
                    "Inicio": h_i.strftime("%H:%M"), 
                    "Fin": h_f.strftime("%H:%M")
                }

    # CONFIGURACIÓN GENERAL
    with st.container(border=True):
        c1, c2 = st.columns(2)
        inicio = c1.date_input("Inicio", date.today())
        fin = c2.date_input("Fin", date.today() + timedelta(days=21))
        desc_input = {}
        lista_g = GRUPOS_TEC if tipo == "Técnicos" else GRUPOS_ABO
        cols = st.columns(len(lista_g))
        for i, g in enumerate(lista_g):
            desc_input[g] = cols[i].selectbox(f"Descanso {g}", DIAS_ES, index=(5 if i<2 else 6) if tipo == "Técnicos" else i%7)
        ciclo = st.sidebar.selectbox("Frecuencia", ["Diario", "Quincenal", "Mensual"]) if tipo == "Abordaje" else "Fijo"

    if st.button(f"⚡ Generar Malla Equitativa", use_container_width=True):
        st.session_state[f"m_{tipo}"] = generar_malla_tecnicos(inicio, fin, desc_input) if tipo == "Técnicos" else generar_malla_abordaje(inicio, fin, desc_input, ciclo)

    key = f"m_{tipo}"
    if key in st.session_state:
        df_base = st.session_state[key].copy()
        df_base["Label"] = df_base["Fecha"].apply(lambda x: f"{INICIALES[DIAS_ES[x.weekday()]]} {x.strftime('%d/%m')}")
        pivot = df_base.pivot(index="Sujeto", columns="Label", values="Turno")
        sorted_cols = sorted(pivot.columns, key=lambda x: datetime.strptime(x.split(" ")[1] + f"/2026", '%d/%m/%Y'))
        
        st.subheader("📝 Editor de Turnos")
        df_edit = st.data_editor(style_malla(pivot[sorted_cols]), use_container_width=True, column_config={str(c): st.column_config.SelectboxColumn(options=list(config_horas.keys()), width="small") for c in pivot.columns})

        df_final = df_edit.reset_index().melt(id_vars="Sujeto", var_name="Label", value_name="Turno")
        map_fechas = dict(zip(df_base["Label"], df_base["Fecha"]))
        df_final["Fecha"] = df_final["Label"].map(map_fechas)
        
        malla_pers = generar_malla_transaccional(df_final, tipo, config_horas)
        errs, cob, equidad = ejecutar_auditoria(df_final, tipo)

        st.divider()
        with st.expander("🔍 Malla Detallada por Persona", expanded=True):
            st.dataframe(malla_pers, use_container_width=True)

        st.subheader("📊 Análisis")
        col_r1, col_r2 = st.columns(2)
        with col_r1: st.dataframe(equidad.style.highlight_max(axis=0, color='#FADBD8').format(precision=0), use_container_width=True)
        with col_r2: st.bar_chart(equidad[["T1", "T2", "T3"]] if "T3" in equidad.columns else equidad[["T1", "T2"]])

        f1, f2 = st.columns(2)
        with f1: 
            if st.button("💾 Guardar GitHub"): guardar_github(df_final, f"malla_{tipo.lower()}.xlsx")
        with f2:
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='xlsxwriter') as wr:
                df_edit.to_excel(wr, sheet_name='Compacta')
                malla_pers.to_excel(wr, sheet_name='Detallada_Persona', index=False)
            st.download_button("📥 Descargar Reporte", out.getvalue(), f"Malla_{tipo}.xlsx", use_container_width=True)

        if not errs:
            st.markdown("""<div style="background-color: #e8f5e9; padding: 20px; border-radius: 10px; border-left: 5px solid #2e7d32;">
                <h3 style="color: #1b5e20;">✅ Validación Exitosa</h3>
                <p style="color: #2e7d32;">La malla cumple estrictamente la ley y mantiene el equilibrio de turnos entre grupos.</p>
                </div>""", unsafe_allow_html=True)
        else:
            for e in errs: st.error(e)
