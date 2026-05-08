import streamlit as st
import pandas as pd
import io
import holidays
import random
from datetime import datetime, timedelta
from github import Github

# --- 1. ESTILOS CON ALTO CONTRASTE ---
def aplicar_estilos_malla(styler, errores_coords):
    colores = {
        "T1": "background-color: #1f77b4; color: white !important;",
        "T2": "background-color: #2ca02c; color: white !important;",
        "T3": "background-color: #4d4d4d; color: white !important;",
        "DESC": "background-color: #d62728; color: white !important;",
        "COMP": "background-color: #ff7f0e; color: white !important;"
    }
    def aplicar_celda(val, row, col):
        base = colores.get(val, "background-color: transparent;")
        if (row, col) in errores_coords:
            base += " border: 3px solid #FFFF00 !important; font-weight: bold; box-shadow: inset 0 0 10px #FFFF00;"
        return base

    return styler.apply(lambda df: pd.DataFrame(
        [[aplicar_celda(df.iloc[r, c], df.index[r], df.columns[c]) 
          for c in range(len(df.columns))] for r in range(len(df.index))],
        index=df.index, columns=df.columns), axis=None)

# --- 2. VALIDACIÓN DE REGLAS DE SUEÑO ---
def es_cambio_saludable(ayer, hoy):
    """Garantiza que nunca se pase de T3 a T1 o T2."""
    if ayer in ["DESC", "COMP", "OFF"] or hoy in ["DESC", "COMP", "OFF"]: return True
    # Jerarquía: T1 (1) -> T2 (2) -> T3 (3). Solo se permite subir o mantenerse.
    jerarquia = {"T1": 1, "T2": 2, "T3": 3}
    return jerarquia.get(hoy, 0) >= jerarquia.get(ayer, 0)

def detectar_novedades(df):
    novedades = []
    if df.empty: return novedades
    # 1. Validar Saltos de Sueño
    for g in df['Grupo'].unique():
        g_data = df[df['Grupo'] == g].sort_values('Fecha_Raw')
        for i in range(1, len(g_data)):
            ayer, hoy = g_data.iloc[i-1]['Turno'], g_data.iloc[i]['Turno']
            if not es_cambio_saludable(ayer, hoy):
                novedades.append({"Grupo": g, "Fecha_Col": g_data.iloc[i]['Fecha_Col'], "Motivo": f"Salto {ayer}->{hoy} (Riesgo Fatiga)"})
    
    # 2. Validar Cobertura T1-T2-T3
    cob = df.groupby(['Fecha_Col', 'Turno'], observed=False).size().unstack(fill_value=0)
    for fecha in cob.index:
        for t in ["T1", "T2", "T3"]:
            if t not in cob.columns or cob.loc[fecha, t] == 0:
                novedades.append({"Grupo": "SISTEMA", "Fecha_Col": fecha, "Motivo": f"Falta cobertura en {t}"})
    return novedades

# --- 3. PANTALLA PRINCIPAL ---
def pantalla_programador():
    st.title("🛡️ Programador Maestro V8.5 - Cobertura Garantizada")
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

    with st.container(border=True):
        st.subheader("⚙️ Configuración de Staffing y Descansos de Ley")
        c_desc, c_staff = st.columns([2, 1])
        with c_desc:
            st.write("**Día de Descanso Parametrizado por Grupo:**")
            cd1, cd2 = st.columns(2)
            d_g1 = cd1.selectbox("Descanso G1", dias_semana, index=5)
            d_g2 = cd2.selectbox("Descanso G2", dias_semana, index=5)
            d_g3 = cd1.selectbox("Descanso G3", dias_semana, index=6)
            d_g4 = cd2.selectbox("Descanso G4", dias_semana, index=6)
            map_desc = {
                "Grupo 1": dias_semana.index(d_g1), "Grupo 2": dias_semana.index(d_g2),
                "Grupo 3": dias_semana.index(d_g3), "Grupo 4": dias_semana.index(d_g4)
            }
        with c_staff:
            st.write("**Personal Requerido por Turno:**")
            req_m = st.number_input("Masters", 1, 10, 3)
            req_ta = st.number_input("Técnicos A", 1, 20, 7)
            req_tb = st.number_input("Técnicos B", 1, 20, 2)

    f_ini = st.date_input("Fecha Inicio Programación", datetime.now())
    f_fin = st.date_input("Fecha Fin Programación", datetime.now() + timedelta(days=28))

    if st.button("🚀 Generar Malla Inteligente y Saludable"):
        from app import conectar_github, obtener_estado_inicial
        repo = conectar_github()
        estado = obtener_estado_inicial(repo)
        
        lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
        resultados = []
        
        mem_t = {g: estado[g]["u"] for g in grupos_n}
        mem_n = {g: estado[g]["n"] for g in grupos_n}
        deudas = {g: estado[g]["d"] for g in grupos_n}
        sem_deuda = {g: estado[g]["sem_d"] for g in grupos_n}
        co_h = holidays.Colombia(years=[2024, 2025, 2026])

        for fecha in lista_fechas:
            fecha_dt = pd.to_datetime(fecha); dia_idx = fecha_dt.weekday()
            n_sem = fecha_dt.isocalendar()[1]; es_fest = fecha_dt in co_h
            col_name = f"{fecha_dt.strftime('%a %d/%m')}{' 🇨🇴' if es_fest else ''}"

            # 1. Determinar quién solicita descanso según parámetro
            solicitan_descanso = [g for g, d_idx in map_desc.items() if d_idx == dia_idx]
            
            # 2. Prioridad: Pagar deudas (Compensatorios) si hay cobertura
            turnos_hoy = {}
            for g in sorted(grupos_n, key=lambda x: deudas[x], reverse=True):
                if deudas[g] > 0 and n_sem > sem_deuda[g] and g not in solicitan_descanso:
                    if len([v for v in turnos_hoy.values() if v == "COMP"]) < 1:
                        turnos_hoy[g] = "COMP"; deudas[g] -= 1; sem_deuda[g] = 0; break

            # 3. GARANTÍA DE TURNOS: Necesitamos mínimo 3 grupos activos para T1, T2, T3
            activos_seguros = [g for g in grupos_n if g not in turnos_hoy and g not in solicitan_descanso]
            
            while len(activos_seguros) < 3 and solicitan_descanso:
                # Sacrificio Equitativo: Trabaja el que menos deudas tenga acumuladas
                sacrificado = sorted(solicitan_descanso, key=lambda x: deudas[x])[0]
                solicitan_descanso.remove(sacrificado)
                deudas[sacrificado] += 1 # Se le debe el día
                sem_deuda[sacrificado] = n_sem
                activos_seguros.append(sacrificado)
            
            for g in solicitan_descanso: turnos_hoy[g] = "DESC"

            # 4. Asignación de Turnos cuidando el sueño (T1->T2->T3)
            turnos_disponibles = ["T1", "T2", "T3"]
            random.shuffle(turnos_disponibles)
            
            for g in activos_seguros:
                idx_g = grupos_n.index(g)
                t_sug = turnos_disponibles.pop(0) if turnos_disponibles else "T1"
                
                # Forzar salud: Si el salto es prohibido, intentar otro turno o mantener anterior
                if not es_cambio_saludable(mem_t[g], t_sug):
                    t_sug = mem_t[g] if mem_t[g] in ["T1", "T2", "T3"] else "T1"
                
                turnos_hoy[g] = t_sug

            for g in grupos_n:
                t_f = turnos_hoy.get(g, "T1")
                n_a = mem_n[g] + 1 if t_f == "T3" else 0
                resultados.append({
                    "Grupo": g, "Fecha_Col": col_name, "Turno": t_f, "Fecha_Raw": fecha_dt,
                    "Noches_Acum": n_a, "Deuda_Compensatorio": deudas[g], "Semana_Deuda": sem_deuda[g],
                    "M_Req": req_m, "TA_Req": req_ta, "TB_Req": req_tb
                })
                mem_t[g] = t_f; mem_n[g] = n_a

        st.session_state.malla_generada = pd.DataFrame(resultados)
        st.rerun()

    # --- 4. EDITOR Y PANEL DE CORRECCIÓN ---
    if st.session_state.get('malla_generada') is not None:
        df_v = st.session_state.malla_generada
        novedades = detectar_novedades(df_v)
        coords_error = [(n['Grupo'], n['Fecha_Col']) for n in novedades]

        st.subheader("🚩 Panel de Corrección de Novedades")
        c_nav, c_foc = st.columns([2, 1])
        if novedades:
            c_nav.warning(f"Se detectaron {len(novedades)} novedades de salud o cobertura.")
            sel_err = c_nav.selectbox("Seleccione error para ubicar:", novedades, format_func=lambda x: f"{x['Grupo']} - {x['Fecha_Col']} ({x['Motivo']})")
            focus = c_foc.toggle("🎯 Ver solo columnas con errores")
        else:
            st.success("✅ Malla 100% Saludable y Cubierta.")
            focus = False

        matriz = df_v.pivot(index="Grupo", columns="Fecha_Col", values="Turno").reindex(columns=df_v["Fecha_Col"].unique())
        if focus and novedades:
            matriz = matriz[[n['Fecha_Col'] for n in novedades]]

        config_col = {c: st.column_config.SelectboxColumn(options=["T1", "T2", "T3", "DESC", "COMP"], width="small") for c in matriz.columns}
        st.data_editor(matriz.style.pipe(aplicar_estilos_malla, errores_coords=coords_error), column_config=config_col, use_container_width=True)
