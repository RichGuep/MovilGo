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

# Colores de alto contraste para la malla
COLORES_MAP = {
    "T1": "#D6EAF8", "T2": "#D5F5E3", "T3": "#FADBD8",
    "RELEVO": "#E8DAEF", "DISPONIBLE": "#EAEDED",
    "T1 APOYO": "#EBF5FB", "DESCANSO": "#1B2631", "COMPENSADO": "#FDEBD0"
}

# =========================================================
# 2. ESTILOS Y EXPORTACIÓN
# =========================================================
def style_malla(df_pivot):
    def apply_styles(val):
        bg = COLORES_MAP.get(val, "")
        txt = "white" if val == "DESCANSO" else "#17202A"
        return f'background-color: {bg}; color: {txt}; font-weight: 700; border: 0.5px solid #D5DBDB' if bg else ''
    return df_pivot.style.map(apply_styles)

def generar_excel_completo(df_edit, errs, cob, equidad):
    output = io.BytesIO()
    # Requiere xlsxwriter instalado
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_edit.to_excel(writer, sheet_name='Malla_Final')
        equidad.to_excel(writer, sheet_name='Analisis_Equidad')
        pd.DataFrame(errs, columns=["Alertas"]).to_excel(writer, sheet_name='Auditoria', index=False)
        cob.reset_index().to_excel(writer, sheet_name='Cobertura_Diaria', index=False)
        # Auto-ajuste de columnas
        for sheet in writer.sheets.values():
            sheet.set_column('A:Z', 15)
    return output.getvalue()

# =========================================================
# 3. MOTOR DE AUDITORÍA Y COMPORTAMIENTO
# =========================================================
def ejecutar_auditoria(df, tipo):
    df = df.copy()
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    
    # Análisis de Cobertura
    cob = df[df["Turno"].isin(["T1","T2","T3"])].groupby("Fecha").size()
    limite = 3 if tipo == "Técnicos" else 20
    errs = [f"❌ Cobertura insuficiente el {f.date()} (Mín {limite})" for f, c in cob.items() if c < limite]
    
    # Métricas de Equidad y Rotación
    equidad = df.groupby(["Sujeto", "Turno"]).size().unstack(fill_value=0)
    columnas_clave = ["DESCANSO", "COMPENSADO", "T1", "T2", "T3"]
    for c in columnas_clave:
        if c not in equidad.columns: equidad[c] = 0
    
    # Calcular días totales trabajados para ver sobrecarga
    equidad["Total_Operativo"] = equidad[["T1", "T2", "T3"]].sum(axis=1)
    
    return errs, cob, equidad

# =========================================================
# 4. LÓGICA DE GENERACIÓN: TÉCNICOS (ROTACIÓN + LEY)
# =========================================================
def generar_malla_tecnicos(inicio, fin, descansos_ley):
    filas = []
    deudas_comp = {g: 0 for g in GRUPOS_TEC}
    
    for fecha in pd.date_range(inicio, fin):
        dia_idx = fecha.weekday()
        dia_nombre = DIAS_ES[dia_idx]
        sem_num = fecha.isocalendar()[1]
        asignados = {}
        
        # --- A. DESCANSOS LEGALES (Gestión de Colisiones) ---
        gps_programados_descanso = [g for g, d in descansos_ley.items() if d == dia_nombre]
        
        if len(gps_programados_descanso) > 1:
            # Rotación Round-Robin para decidir quién descansa efectivamente
            idx = sem_num % len(gps_programados_descanso)
            descansador_real = gps_programados_descanso[idx]
            asignados[descansador_real] = "DESCANSO"
            # Los otros acumulan deuda de compensatorio
            for g in gps_programados_descanso:
                if g != descansador_real: deudas_comp[g] += 1
        elif len(gps_programados_descanso) == 1:
            asignados[gps_que_descansan_hoy[0]] = "DESCANSO"

        # --- B. PRIORIDAD ROTATIVA SEMANAL (EQUIDAD DE CARGA) ---
        # Este offset hace que el Grupo 1 no sea siempre el primero en recibir T3
        activos = [g for g in GRUPOS_TEC if g not in asignados]
        offset = sem_num % len(GRUPOS_TEC)
        activos_rotados = sorted(activos, key=lambda x: (GRUPOS_TEC.index(x) + offset) % len(GRUPOS_TEC))

        # --- C. PAGO DE COMPENSATORIOS (REFORMA LABORAL) ---
        if 0 <= dia_idx <= 4 and len(asignados) == 0:
            cands_deuda = sorted(activos_rotados, key=lambda x: deudas_comp[x], reverse=True)
            if cands_deuda and deudas_comp[cands_deuda[0]] > 0:
                sel = cands_deuda[0]
                asignados[sel] = "COMPENSADO"
                deudas_comp[sel] -= 1
                activos_rotados.remove(sel)

        # --- D. ASIGNACIÓN DE TURNOS OPERATIVOS ---
        turnos_jerarquia = ["T3", "T2", "T1", "T1 APOYO"]
        for g in activos_rotados:
            for t in turnos_jerarquia:
                if t not in asignados.values():
                    asignados[g] = t
                    break
            if g not in asignados: asignados[g] = "T1 APOYO"

        for g in GRUPOS_TEC:
            filas.append({"Fecha": fecha, "Sujeto": g, "Turno": asignados.get(g, "DESCANSO")})
            
    return pd.DataFrame(filas)

# =========================================================
# 5. LÓGICA DE GENERACIÓN: ABORDAJE
# =========================================================
def generar_malla_abordaje(inicio, fin, desc_cfg, ciclo):
    filas = []
    for fecha in pd.date_range(inicio, fin):
        dia_idx = fecha.weekday()
        dia_n = DIAS_ES[dia_idx]
        gps_desc = [g for g in GRUPOS_ABO if desc_cfg.get(g) == dia_n]
        
        # Seed rotativo según el ciclo elegido
        if ciclo == "Diario": seed = (fecha - pd.to_datetime(inicio)).days
        elif ciclo == "Quincenal": seed = (fecha.day-1)//15 + (fecha.month*10)
        else: seed = fecha.month + (fecha.year*12)
        
        gps_ord = sorted(GRUPOS_ABO, key=lambda g: (hash(g) + seed) % 100)
        disp = [g for g in gps_ord if g not in gps_desc]
        
        asig_grupos = {}
        for _ in range(min(2, len(disp))): asig_grupos[disp.pop(0)] = "T1"
        for _ in range(min(2, len(disp))): asig_grupos[disp.pop(0)] = "T2"
        sobrante = disp[0] if disp else None
        
        for g in GRUPOS_ABO:
            base = asig_grupos.get(g, "DESCANSO")
            for i, p in enumerate(PERSONAL_ABO[g]):
                ft = base
                if g == sobrante: ft = "RELEVO" if i == 0 else "DISPONIBLE"
                elif g in gps_desc: ft = "DESCANSO"
                filas.append({"Fecha": fecha, "Sujeto": p, "Turno": ft})
    return pd.DataFrame(filas)

# =========================================================
# 6. INTERFAZ DE PROGRAMACIÓN (FRONT-END DEL MÓDULO)
# =========================================================
def pantalla_programador():
    st.sidebar.markdown("---")
    tipo = st.sidebar.radio("🔧 Seleccionar Módulo", ["Técnicos", "Abordaje"])
    
    st.subheader(f"📅 Planificador Maestro de {tipo}")
    
    # Configuración de Rango y Descansos
    with st.container(border=True):
        c1, c2 = st.columns(2)
        inicio = c1.date_input("Fecha de Inicio", date.today())
        fin = c2.date_input("Fecha de Finalización", date.today() + timedelta(days=21))
        
        desc_input = {}
        lista_grupos = GRUPOS_TEC if tipo == "Técnicos" else GRUPOS_ABO
        cols = st.columns(len(lista_grupos))
        for i, g in enumerate(lista_grupos):
            desc_input[g] = cols[i].selectbox(f"Libra {g}", DIAS_ES, index=(5 if i<2 else 6) if tipo == "Técnicos" else i%7)
        
        ciclo_abo = "Fijo"
        if tipo == "Abordaje":
            ciclo_abo = st.selectbox("Ciclo de Rotación Grupal", ["Diario", "Quincenal", "Mensual"], index=1)

    if st.button(f"⚡ Generar Malla Equitativa {tipo}", use_container_width=True):
        if tipo == "Técnicos":
            st.session_state[f"m_{tipo}"] = generar_malla_tecnicos(inicio, fin, desc_input)
        else:
            st.session_state[f"m_{tipo}"] = generar_malla_abordaje(inicio, fin, desc_input, ciclo_abo)

    # Visualización y Editor
    key = f"m_{tipo}"
    if key in st.session_state:
        df_base = st.session_state[key].copy()
        df_base["Label"] = df_base["Fecha"].apply(lambda x: f"{INICIALES[DIAS_ES[x.weekday()]]} {x.strftime('%d/%m')}")
        
        pivot = df_base.pivot(index="Sujeto", columns="Label", values="Turno")
        # Ordenar columnas cronológicamente
        pivot = pivot.reindex(sorted(pivot.columns, key=lambda x: datetime.strptime(x.split(" ")[1] + f"/{date.today().year}", '%d/%m/%Y')), axis=1)

        st.subheader("📝 Malla Resultante (Editable)")
        config_cols = {str(c): st.column_config.SelectboxColumn(options=OPCIONES_TURNOS, width="small") for c in pivot.columns}
        df_edit = st.data_editor(style_malla(pivot), use_container_width=True, column_config=config_cols)

        # RECALCULAR MÉTRICAS DESPUÉS DE EDICIÓN
        df_final = df_edit.reset_index().melt(id_vars="Sujeto", var_name="Label", value_name="Turno")
        map_fechas = dict(zip(df_base["Label"], df_base["Fecha"]))
        df_final["Fecha"] = df_final["Label"].map(map_fechas)
        errs, cob, equidad = ejecutar_auditoria(df_final, tipo)

        st.divider()
        st.subheader("📊 Análisis de Equidad y Comportamiento")
        
        col_res1, col_res2 = st.columns([1, 1])
        with col_res1:
            st.write("**Resumen de Turnos y Descansos**")
            st.dataframe(equidad.style.highlight_max(axis=0, color='#FADBD8').format(precision=0), use_container_width=True)
        with col_res2:
            st.write("**Balance de Turnos (T1/T2/T3)**")
            st.bar_chart(equidad[["T1", "T2", "T3"]] if "T3" in equidad.columns else equidad[["T1", "T2"]])

        # Botón de Descarga Unificado
        excel_data = generar_excel_completo(df_edit, errs, cob, equidad)
        st.download_button(
            label="📥 Descargar Escenario con Auditoría (Excel)",
            data=excel_data,
            file_name=f"Malla_MovilGo_{tipo}_{date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

        if errs:
            with st.expander("🚨 Alertas de Auditoría", expanded=True):
                for e in errs: st.error(e)
