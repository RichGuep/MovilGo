import streamlit as st
import pandas as pd
import io
import holidays
import random
from datetime import datetime, timedelta
from github import Github

# --- 1. ESTILOS Y RESALTADO DE ERRORES ---
def aplicar_estilos_malla(styler, errores_coords):
    colores = {
        "T1": "background-color: #1f77b4; color: white;",
        "T2": "background-color: #2ca02c; color: white;",
        "T3": "background-color: #4d4d4d; color: white;",
        "DESC": "background-color: #d62728; color: white;",
        "COMP": "background-color: #ff7f0e; color: white;"
    }

    def aplicar_celda(val, row_name, col_name):
        estilo = colores.get(val, "background-color: transparent; color: inherit;")
        if (row_name, col_name) in errores_coords:
            # Resaltado en amarillo neón para errores de salud o cobertura
            estilo += "border: 3px solid #FFFF00 !important; font-weight: bold; color: #FFFF00 !important; box-shadow: inset 0 0 10px #000;"
        return estilo

    return styler.apply(lambda df: pd.DataFrame(
        [[aplicar_celda(df.iloc[r, c], df.index[r], df.columns[c]) 
          for c in range(len(df.columns))] 
         for r in range(len(df.index))],
        index=df.index, columns=df.columns), axis=None)

# --- 2. DETECTOR DE NOVEDADES Y MÉTRICAS DE SALUD ---
def detectar_novedades(df):
    novedades = []
    # 1. Errores de Salud (Saltos Prohibidos T3 -> T1/T2)
    for g in df['Grupo'].unique():
        g_data = df[df['Grupo'] == g].sort_values('Fecha_Raw')
        for i in range(1, len(g_data)):
            ayer, hoy = g_data.iloc[i-1]['Turno'], g_data.iloc[i]['Turno']
            # REGLA DE ORO: Después de T3 debe haber mínimo 24h de descanso o seguir en T3
            if ayer == "T3" and hoy in ["T1", "T2"]:
                novedades.append({
                    "Grupo": g, 
                    "Fecha_Col": g_data.iloc[i]['Fecha_Col'], 
                    "Motivo": f"FATIGA: Salto {ayer}->{hoy} (Sin descanso legal)",
                    "Tipo": "Salud"
                })
    
    # 2. Errores de Cobertura Operativa
    cob = df.groupby(['Fecha_Col', 'Turno'], observed=False).size().unstack(fill_value=0)
    for fecha in cob.index:
        for t in ["T1", "T2", "T3"]:
            if t not in cob.columns or cob.loc[fecha, t] == 0:
                novedades.append({
                    "Grupo": "SISTEMA", 
                    "Fecha_Col": fecha, 
                    "Motivo": f"DESABASTECIMIENTO: Falta turno {t}",
                    "Tipo": "Cobertura"
                })
    return novedades

# --- 3. PANTALLA PRINCIPAL ---
def pantalla_programador():
    st.title("🛡️ Programador Maestro MovilGo V7.2")
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

    with st.container(border=True):
        st.subheader("⚙️ Staffing y Reglas de Sueño")
        c_desc, c_staff = st.columns([2, 1])
        with c_desc:
            st.write("**Descansos Fijos Independientes:**")
            cd1, cd2 = st.columns(2)
            d_g1 = cd1.selectbox("Descanso G1", dias_semana, index=5)
            d_g2 = cd2.selectbox("Descanso G2", dias_semana, index=5)
            d_g3 = cd1.selectbox("Descanso G3", dias_semana, index=6)
            d_g4 = cd2.selectbox("Descanso G4", dias_semana, index=6)
            map_idx = {"Grupo 1": dias_semana.index(d_g1), "Grupo 2": dias_semana.index(d_g2), 
                       "Grupo 3": dias_semana.index(d_g3), "Grupo 4": dias_semana.index(d_g4)}
        with c_staff:
            rm = st.number_input("Masters Req.", 1, 10, 3)
            rta = st.number_input("Téc A Req.", 1, 20, 7)
            rtb = st.number_input("Téc B Req.", 1, 20, 2)

    f_ini = st.date_input("Inicio", datetime.now())
    f_fin = st.date_input("Fin", datetime.now() + timedelta(days=28))

    if st.button("🚀 Generar Malla Saludable"):
        # (Lógica de conexión y estado inicial omitida para brevedad, igual a la anterior)
        lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
        resultados = []
        
        # Simulación de memoria de turnos para validar salud
        mem_t = {g: "DESC" for g in grupos_n} 
        deudas = {g: 0 for g in grupos_n}
        sem_deuda = {g: 0 for g in grupos_n}

        for fecha in lista_fechas:
            fecha_dt = pd.to_datetime(fecha); n_sem = fecha_dt.isocalendar()[1]
            dia_idx = fecha_dt.weekday(); col_name = fecha_dt.strftime('%a %d/%m')
            
            turnos_hoy = {}
            quieren_fijo = [g for g, d_idx in map_idx.items() if d_idx == dia_idx]
            
            # --- MOTOR DE SALUD: VALIDACIÓN DE SUEÑO ---
            for g in grupos_n:
                if mem_t[g] == "T3":
                    # Si ayer fue noche, hoy OBLIGATORIO debe ser DESC o COMP (o seguir en T3 si es bloque)
                    # No permitimos saltar a T1 o T2
                    if g not in quieren_fijo:
                        turnos_hoy[g] = "COMP"
                        deudas[g] = max(0, deudas[g]-1)
            
            # Compensación Inmediata de deudas
            for g in grupos_n:
                if g not in turnos_hoy and deudas[g] > 0 and n_sem > sem_deuda[g] and g not in quieren_fijo:
                    if "COMP" not in turnos_hoy.values():
                        turnos_hoy[g] = "COMP"; deudas[g] -= 1; sem_deuda[g] = 0

            # Garantizar Cobertura: Mínimo 3 grupos activos
            activos = [g for g in grupos_n if g not in turnos_hoy and g not in quieren_fijo]
            while len(activos) < 3 and quieren_fijo:
                sacrificado = quieren_fijo.pop(0); deudas[sacrificado] += 1
                sem_deuda[sacrificado] = n_sem; activos.append(sacrificado)
            
            for g in quieren_fijo: turnos_hoy[g] = "DESC"
            
            # Asignación de Turnos Operativos con protección de salto
            t_op = ["T1", "T2", "T3"]
            random.shuffle(t_op)
            for g in activos:
                if g not in turnos_hoy:
                    t_valido = [t for t in t_op if not (mem_t[g] == "T3" and t in ["T1", "T2"])]
                    if t_valido:
                        sel_t = t_valido.pop(0)
                        turnos_hoy[g] = sel_t
                        t_op.remove(sel_t)
                    else:
                        turnos_hoy[g] = "DESC" # Fail-safe de salud

            for g in grupos_n:
                mem_t[g] = turnos_hoy.get(g, "T1")
                resultados.append({
                    "Grupo": g, "Fecha_Col": col_name, "Turno": mem_t[g], "Fecha_Raw": fecha_dt, 
                    "Deuda_Compensatorio": deudas[g], "Semana_Deuda": sem_deuda[g], 
                    "M_Req": rm, "TA_Req": rta, "TB_Req": rtb
                })

        st.session_state.malla_generada = pd.DataFrame(resultados)
        st.rerun()

    # --- DASHBOARD DE MÉTRICAS Y AUDITORÍA ---
    if st.session_state.get('malla_generada') is not None:
        df_v = st.session_state.malla_generada
        novedades = detectar_novedades(df_v)
        coords_error = [(n['Grupo'], n['Fecha_Col']) for n in novedades]

        st.divider()
        st.subheader("📊 Dashboard de Validación y Auditoría")
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Cobertura T1-T2-T3", "100%" if not any(n['Tipo'] == "Cobertura" for n in novedades) else "⚠️ HUECOS")
        m2.metric("Alertas Fatiga", len([n for n in novedades if n['Tipo'] == "Salud"]), delta_color="inverse")
        m3.metric("Equidad Noches", f"{df_v[df_v['Turno']=='T3'].groupby('Grupo').size().std():.2f} (σ)")
        m4.metric("Descansos Cumplidos", f"{len(df_v[df_v['Turno'].isin(['DESC','COMP'])])}")

        # --- EDITOR CON MAPA DE CALOR ---
        st.info("💡 Las celdas con **borde amarillo** representan violaciones a la ley de descanso o falta de personal.")
        matriz = df_v.pivot(index="Grupo", columns="Fecha_Col", values="Turno").reindex(columns=df_v["Fecha_Col"].unique())
        
        config_col = {c: st.column_config.SelectboxColumn(options=["T1", "T2", "T3", "DESC", "COMP"]) for c in matriz.columns}
        st.data_editor(matriz.style.pipe(aplicar_estilos_malla, errores_coords=coords_error), column_config=config_col, use_container_width=True)

        if novedades:
            with st.expander("🔍 Ver Detalle de Novedades"):
                st.table(pd.DataFrame(novedades))
