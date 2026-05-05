import streamlit as st
import pandas as pd
import io
import holidays
from datetime import datetime, timedelta
from github import Github

# --- 1. FUNCIONES DE APOYO ---

def asignar_grupos_aleatorio(df_cable):
    df = df_cable.copy()
    masters = df[df['Cargo'].str.contains('Master', case=False, na=False)].sample(frac=1).to_dict('records')
    tecnicos_a = df[df['Cargo'].str.contains('Tecnico A', case=False, na=False)].sample(frac=1).to_dict('records')
    tecnicos_b = df[df['Cargo'].str.contains('Tecnico B', case=False, na=False)].sample(frac=1).to_dict('records')

    grupos_finales = []
    num_grupo = 1
    while len(masters) >= 2 and len(tecnicos_a) >= 7 and len(tecnicos_b) >= 3:
        for _ in range(2): 
            p = masters.pop(); p['Grupo'] = f"Grupo {num_grupo}"; grupos_finales.append(p)
        for _ in range(7): 
            p = tecnicos_a.pop(); p['Grupo'] = f"Grupo {num_grupo}"; grupos_finales.append(p)
        for _ in range(3): 
            p = tecnicos_b.pop(); p['Grupo'] = f"Grupo {num_grupo}"; grupos_finales.append(p)
        num_grupo += 1

    sobrantes = masters + tecnicos_a + tecnicos_b
    for s in sobrantes: s['Grupo'] = "Reserva"
    grupos_finales.extend(sobrantes)
    return pd.DataFrame(grupos_finales)

def guardar_en_github(df):
    try:
        g = Github(st.secrets["GITHUB_TOKEN"])
        repo = g.get_repo("RichGuep/movilgo")
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        contents = repo.get_contents("empleados.xlsx")
        repo.update_file(path="empleados.xlsx", message="Sincronización Estable", 
                         content=output.getvalue(), sha=contents.sha, branch="main")
        return True
    except Exception as e:
        st.error(f"❌ Error GitHub: {e}"); return False

# --- 2. MÓDULO: GESTIÓN DE GRUPOS ---

def pantalla_gestion_grupos():
    st.title("👥 Gestión de Grupos - Cablemovil")
    if 'df_cable' not in st.session_state:
        try:
            df_full = pd.read_excel("empleados.xlsx")
            df_full.columns = df_full.columns.str.strip()
            mapeo = {'Cedula': 'cedu', 'Nombre': 'nomb', 'Cargo': 'carg', 'Empresa': 'empr'}
            for oficial, clave in mapeo.items():
                col = [c for c in df_full.columns if clave in c.lower()]
                if col: df_full = df_full.rename(columns={col[0]: oficial})
            df_c = df_full[df_full['Empresa'].str.contains('Cablemovil', case=False, na=False)].copy()
            if 'Grupo' not in df_c.columns: df_c['Grupo'] = "Sin Asignar"
            st.session_state.df_cable = df_c
        except Exception as e: st.error(f"Error: {e}"); return

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("🎲 Mezclar Grupos Aleatorio"):
            st.session_state.df_cable = asignar_grupos_aleatorio(st.session_state.df_cable)
            st.rerun()
    with c2:
        if st.button("💾 Guardar en GitHub"):
            if guardar_en_github(st.session_state.df_cable): st.success("¡Sincronizado!")
    with c3:
        if st.button("🗑️ Reset"):
            st.session_state.df_cable['Grupo'] = "Sin Asignar"; st.rerun()
    
    df_edit = st.data_editor(st.session_state.df_cable[['Cedula', 'Nombre', 'Cargo', 'Grupo']], use_container_width=True, hide_index=True)
    if st.button("Aplicar Cambios Manuales"):
        st.session_state.df_cable.update(df_edit); st.success("Cambios aplicados")

# --- 3. PROGRAMADOR ESTABLE 24/7 ---

def pantalla_programador():
    st.title("📅 Programador Operativo 24/7")
    
    if 'df_cable' not in st.session_state:
        st.warning("⚠️ Cargue los grupos primero."); return

    co_holidays = holidays.Colombia(years=[2024, 2025, 2026])

    st.subheader("Rango de Programación")
    c_f1, c_f2 = st.columns(2)
    f_inicio = c_f1.date_input("Inicio", datetime.now())
    f_fin = c_f2.date_input("Fin", datetime.now() + timedelta(days=21))

    if st.button("🚀 Generar Programación"):
        # Barra de progreso simple
        bar = st.progress(0)
        
        lista_fechas = []
        curr = f_inicio
        while curr <= f_fin:
            lista_fechas.append(curr); curr += timedelta(days=1)

        resultados = []
        grupos = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
        deudas = {g: 0 for g in grupos}
        historial = {g: "DESC" for g in grupos}

        for i, fecha in enumerate(lista_fechas):
            bar.progress((i + 1) / len(lista_fechas))
            
            dia_idx = fecha.weekday()
            sem_iso = fecha.isocalendar()[1]
            es_festivo = fecha in co_holidays
            col_name = f"{fecha.strftime('%a %d/%m')}{' 🇨🇴' if es_festivo else ''}"

            # 1. Libranzas
            libranza = None
            if dia_idx == 5: # Sab
                libranza = "Grupo 1" if sem_iso % 2 == 0 else "Grupo 2"
                deudas["Grupo 2" if sem_iso % 2 == 0 else "Grupo 1"] += 1
            elif dia_idx == 6: # Dom
                libranza = "Grupo 3" if sem_iso % 2 == 0 else "Grupo 4"
                deudas["Grupo 4" if sem_iso % 2 == 0 else "Grupo 3"] += 1
            else:
                # Compensatorios (Prioridad: no darlo justo después de T3)
                for g in sorted(deudas, key=deudas.get, reverse=True):
                    if deudas[g] > 0 and historial[g] != "T3":
                        libranza = g
                        deudas[g] -= 1
                        break

            # 2. Asignación de Turnos (Protección T3->T1 integrada)
            activos = [g for g in grupos if g != libranza]
            turnos_hoy = {}
            
            for g in activos:
                idx_g = grupos.index(g)
                # Turno estable semanal
                t_sug = ["T1", "T2", "T3"][(idx_g + sem_iso) % 3]
                
                # Bloqueo Salud: No T1/T2 después de T3
                if historial[g] == "T3" and t_sug in ["T1", "T2"]:
                    t_sug = "T3"
                turnos_hoy[g] = t_sug

            # 3. Ajuste de Cobertura (Garantizar T1, T2, T3 y solo un T3)
            # Primero: Limitar a un solo T3 (el que venga de amanecida tiene prioridad para quedarse en T3)
            actuales = list(turnos_hoy.values())
            while actuales.count("T3") > 1:
                for g in activos:
                    if turnos_hoy[g] == "T3" and historial[g] != "T3" and actuales.count("T3") > 1:
                        turnos_hoy[g] = "T2" # Mover a Tarde (más seguro que T1)
                        actuales = list(turnos_hoy.values())
            
            # Segundo: Asegurar que existan T1, T2, T3
            for tr in ["T1", "T2", "T3"]:
                if tr not in actuales:
                    for g in activos:
                        if actuales.count(turnos_hoy[g]) > 1:
                            # Validar que el cambio no viole salud
                            if not (historial[g] == "T3" and tr == "T1"):
                                turnos_hoy[g] = tr
                                actuales = list(turnos_hoy.values())
                                break

            # 4. Registro
            for g in grupos:
                t_final = ("DESC" if dia_idx >= 5 else "COMP") if g == libranza else turnos_hoy.get(g, "T1")
                resultados.append({"Grupo": g, "Fecha_Col": col_name, "Turno": t_final})
                historial[g] = t_final

        bar.empty()
        
        # --- RENDERIZADO ---
        df_res = pd.DataFrame(resultados)
        matriz = df_res.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        matriz = matriz.reindex(columns=df_res["Fecha_Col"].unique())
        
        def color_t(val):
            c = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#7f7f7f", "DESC": "#ff4b4b", "COMP": "#ffa500"}
            return f'background-color: {c.get(val, "#31333F")}; color: white; font-weight: bold; border: 1px solid #444'

        st.subheader("📊 Matriz de Turnos")
        st.dataframe(matriz.style.map(color_t), use_container_width=True)

        # --- VALIDADOR ---
        st.divider()
        st.subheader("🔍 Validador de Auditoría")
        c1, c2 = st.columns(2)
        with c1:
            st.write("**✅ Descansos Otorgados**")
            st.table(df_res[df_res['Turno'].isin(['DESC', 'COMP'])].groupby(['Grupo', 'Turno']).size().unstack(fill_value=0))
        with c2:
            st.write("**🛡️ Auditoría de Cobertura**")
            errores = []
            for fc in df_res["Fecha_Col"].unique():
                tv = df_res[df_res["Fecha_Col"] == fc]["Turno"].values
                for t in ["T1", "T2", "T3"]:
                    if t not in tv: errores.append(f"{fc}({t})")
            
            # Verificación salud
            for g in grupos:
                h = df_res[df_res["Grupo"] == g]["Turno"].tolist()
                for i in range(1, len(h)):
                    if h[i-1] == "T3" and h[i] == "T1": errores.append(f"⚠️ {g}(T3->T1)")

            if not errores: st.success("¡Operación Segura y Completa!")
            else: st.error(f"Alertas: {', '.join(errores)}")
