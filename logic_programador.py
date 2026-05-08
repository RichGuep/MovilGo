import streamlit as st
import pandas as pd
import io
import holidays
import random
from datetime import datetime, timedelta
from github import Github

# --- 1. ESTILOS Y COLORES ---
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

# --- 2. LOGICA DE SALUD ---
def es_cambio_saludable(ayer, hoy):
    if ayer in ["DESC", "COMP", "OFF"] or hoy in ["DESC", "COMP", "OFF"]: return True
    jerarquia = {"T1": 1, "T2": 2, "T3": 3}
    return jerarquia.get(hoy, 0) >= jerarquia.get(ayer, 0)

def detectar_novedades(df):
    novedades = []
    if df.empty: return novedades
    for g in df['Grupo'].unique():
        g_data = df[df['Grupo'] == g].sort_values('Fecha_Raw')
        for i in range(1, len(g_data)):
            ayer, hoy = g_data.iloc[i-1]['Turno'], g_data.iloc[i]['Turno']
            if not es_cambio_saludable(ayer, hoy):
                novedades.append({"Grupo": g, "Fecha_Col": g_data.iloc[i]['Fecha_Col'], "Motivo": f"Salto {ayer}->{hoy}"})
    return novedades

# --- 3. MOTOR DE GENERACIÓN (EL HIBRIDO) ---
def pantalla_programador():
    st.title("🛡️ Programador Maestro V8.0")
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

    with st.container(border=True):
        st.subheader("⚙️ Configuración Staffing")
        c1, c2, c3 = st.columns(3)
        req_m = c1.number_input("Masters", 1, 10, 3)
        req_ta = c2.number_input("Téc A", 1, 20, 7)
        req_tb = c3.number_input("Téc B", 1, 20, 2)

    f_ini = st.date_input("Inicio", datetime.now())
    f_fin = st.date_input("Fin", datetime.now() + timedelta(days=28))

    if st.button("🚀 Generar Malla Inteligente"):
        from app import conectar_github, obtener_estado_inicial # Evitar circular import
        repo = conectar_github()
        estado = obtener_estado_inicial(repo)
        
        lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
        resultados = []
        
        # Recuperamos memoria de tu lógica original
        mem_t = {g: estado[g]["u"] for g in grupos_n}
        mem_n = {g: estado[g]["n"] for g in grupos_n}
        deudas = {g: estado[g]["d"] for g in grupos_n}
        co_h = holidays.Colombia(years=[2024, 2025, 2026])

        for fecha in lista_fechas:
            fecha_dt = pd.to_datetime(fecha); dia_idx = fecha_dt.weekday()
            sem_iso = fecha_dt.isocalendar()[1]; es_fest = fecha_dt in co_h
            col_name = f"{fecha_dt.strftime('%a %d/%m')}{' 🇨🇴' if es_fest else ''}"

            # REGLA 1: Libranza automática por bloques (Tu lógica original)
            libranza = None
            if dia_idx == 5: # Sábado
                libranza = "Grupo 1" if sem_iso % 2 == 0 else "Grupo 2"
                deudas["Grupo 2" if sem_iso % 2 == 0 else "Grupo 1"] += 1
            elif dia_idx == 6: # Domingo
                libranza = "Grupo 3" if sem_iso % 2 == 0 else "Grupo 4"
                deudas["Grupo 4" if sem_iso % 2 == 0 else "Grupo 3"] += 1
            else:
                # Cobro de deudas entre semana
                for g in sorted(grupos_n, key=lambda x: deudas[x], reverse=True):
                    if deudas[g] > 0 and mem_t[g] != "T3":
                        libranza = g; deudas[g] -= 1; break

            # REGLA 2: Asignación Saludable
            activos = [g for g in grupos_n if g != libranza]
            turnos_hoy = {}
            for g in activos:
                idx_g = grupos_n.index(g)
                t_sug = ["T1", "T2", "T3"][(idx_g + sem_iso) % 3]
                
                # Validación de Salud (Tu lógica es_cambio_saludable)
                if not es_cambio_saludable(mem_t[g], t_sug): t_sug = mem_t[g]
                # Límite de 6 noches (Tu lógica mem_n)
                if mem_n[g] >= 6 and t_sug == "T3": t_sug = "T1"
                turnos_hoy[g] = t_sug

            # REGLA 3: Motor Cobertura (Asegurar T1, T2, T3)
            for tr in ["T1", "T2", "T3"]:
                if tr not in turnos_hoy.values() and activos:
                    for gf in activos:
                        if list(turnos_hoy.values()).count(turnos_hoy[gf]) > 1:
                            if es_cambio_saludable(mem_t[gf], tr):
                                turnos_hoy[gf] = tr; break
            
            for g in grupos_n:
                t_f = ("DESC" if dia_idx >= 5 else "COMP") if g == libranza else turnos_hoy.get(g, "T1")
                n_a = mem_n[g] + 1 if t_f == "T3" else 0
                resultados.append({
                    "Grupo": g, "Fecha_Col": col_name, "Turno": t_f, "Fecha_Raw": fecha_dt,
                    "Noches_Acum": n_a, "Deuda_Compensatorio": deudas[g],
                    "M_Req": req_m, "TA_Req": req_ta, "TB_Req": req_tb
                })
                mem_t[g] = t_f; mem_n[g] = n_a

        st.session_state.malla_generada = pd.DataFrame(resultados)
        st.rerun()

    # --- 4. EDITOR Y LOCALIZADOR ---
    if st.session_state.get('malla_generada') is not None:
        df_v = st.session_state.malla_generada
        novedades = detectar_novedades(df_v)
        coords_error = [(n['Grupo'], n['Fecha_Col']) for n in novedades]

        st.subheader("🚩 Panel de Corrección")
        col_nav, col_filtro = st.columns([2, 1])
        with col_nav:
            if novedades:
                err_sel = st.selectbox("Ubicar error:", novedades, format_func=lambda x: f"{x['Grupo']} - {x['Fecha_Col']} ({x['Motivo']})")
            else: st.success("✅ Malla Saludable y Cubierta.")
        with col_filtro:
            focus = st.toggle("🎯 Ver solo días con novedades")

        matriz = df_v.pivot(index="Grupo", columns="Fecha_Col", values="Turno").reindex(columns=df_v["Fecha_Col"].unique())
        if focus and novedades:
            matriz = matriz[[n['Fecha_Col'] for n in novedades]]

        config_col = {c: st.column_config.SelectboxColumn(options=["T1", "T2", "T3", "DESC", "COMP"], width="small") for c in matriz.columns}
        st.data_editor(matriz.style.pipe(aplicar_estilos_malla, errores_coords=coords_error), column_config=config_col, use_container_width=True)
