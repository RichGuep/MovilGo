import streamlit as st
import pandas as pd
import random
import io
import holidays
from datetime import datetime, timedelta
from github import Github

# --- 1. FUNCIONES DE APOYO ---

def asignar_grupos_aleatorio(df_cable):
    """Mezcla y asigna personal respetando el mix contractual 2-7-3."""
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
        if "GITHUB_TOKEN" not in st.secrets:
            st.error("❌ Token 'GITHUB_TOKEN' no encontrado."); return False
        g = Github(st.secrets["GITHUB_TOKEN"])
        repo = g.get_repo("RichGuep/movilgo")
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        contents = repo.get_contents("empleados.xlsx")
        repo.update_file(path="empleados.xlsx", message="Update Grupos", 
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
        except Exception as e:
            st.error(f"Error: {e}"); return

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("🎲 Mezclar Grupos"):
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

# --- 3. MÓDULO: PROGRAMADOR CON VALIDADOR ---

def pantalla_programador():
    st.title("📅 Programador Operativo 24/7")
    
    if 'df_cable' not in st.session_state:
        st.warning("⚠️ Cargue los grupos primero."); return

    co_holidays = holidays.Colombia(years=[datetime.now().year, datetime.now().year + 1])

    st.subheader("Rango de Programación")
    c_f1, c_f2 = st.columns(2)
    f_inicio = c_f1.date_input("Inicio", datetime.now())
    f_fin = c_f2.date_input("Fin", datetime.now() + timedelta(days=21))

    if st.button("🚀 Generar y Validar Programación"):
        lista_fechas = []
        curr = f_inicio
        while curr <= f_fin:
            lista_fechas.append(curr); curr += timedelta(days=1)

        resultados = []
        grupos_lista = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
        dias_pendientes = {g: 0 for g in grupos_lista}

        for fecha in lista_fechas:
            dia_idx = fecha.weekday()
            num_semana = fecha.isocalendar()[1]
            sem_par = (num_semana % 2 == 0)
            es_festivo = fecha in co_holidays

            grupo_que_libra_hoy = None

            # Asignación de descansos
            if dia_idx == 5: # Sab
                grupo_que_libra_hoy = "Grupo 1" if sem_par else "Grupo 2"
                quien_trabaja = "Grupo 2" if sem_par else "Grupo 1"
                dias_pendientes[quien_trabaja] += 1
            elif dia_idx == 6: # Dom
                grupo_que_libra_hoy = "Grupo 3" if sem_par else "Grupo 4"
                quien_trabaja = "Grupo 4" if sem_par else "Grupo 3"
                dias_pendientes[quien_trabaja] += 1
            else: # Lun-Vie: Compensatorios
                for g in sorted(dias_pendientes, key=dias_pendientes.get, reverse=True):
                    if dias_pendientes[g] > 0:
                        grupo_que_libra_hoy = g
                        dias_pendientes[g] -= 1
                        break

            activos = [g for g in grupos_lista if g != grupo_que_libra_hoy]
            col_name = f"{fecha.strftime('%a %d/%m')}{' 🇨🇴' if es_festivo else ''}"

            for g_name in grupos_lista:
                if g_name == grupo_que_libra_hoy:
                    turno = "DESC" if dia_idx >= 5 else "COMP"
                else:
                    # Turno Estable Semanal
                    idx_grupo = grupos_lista.index(g_name)
                    idx_turno = (idx_grupo + num_semana) % 3
                    turno = ["T1", "T2", "T3"][idx_turno]
                
                resultados.append({"Grupo": g_name, "Fecha_Col": col_name, "Turno": turno, "Fecha_Raw": fecha})

        df_res = pd.DataFrame(resultados)

        # --- SECCIÓN 1: MATRIZ VISUAL ---
        matriz = df_res.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        matriz = matriz.reindex(columns=df_res["Fecha_Col"].unique())

        def style_c(val):
            colors = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#7f7f7f", "DESC": "#ff4b4b", "COMP": "#ffa500"}
            return f'background-color: {colors.get(val, "#31333F")}; color: white; font-weight: bold; border: 1px solid #444'

        st.subheader("📊 Matriz de Turnos")
        st.dataframe(matriz.style.map(style_c), use_container_width=True)

        # --- SECCIÓN 2: VALIDACIÓN Y AUDITORÍA ---
        st.divider()
        st.subheader("🔍 Validador de Cumplimiento")
        
        col_aud1, col_aud2 = st.columns(2)

        with col_aud1:
            st.write("**✅ Cantidad de Descansos Otorgados**")
            # Contar DESC y COMP por grupo
            conteo_descansos = df_res[df_res['Turno'].isin(['DESC', 'COMP'])].groupby(['Grupo', 'Turno']).size().unstack(fill_value=0)
            st.table(conteo_descansos)

        with col_aud2:
            st.write("**🛡️ Verificación de Cobertura Diaria**")
            # Verificar que cada día tenga T1, T2 y T3
            dias_con_error = []
            for fecha_col in df_res["Fecha_Col"].unique():
                turnos_del_dia = df_res[df_res["Fecha_Col"] == fecha_col]["Turno"].values
                for t in ["T1", "T2", "T3"]:
                    if t not in turnos_del_dia:
                        dias_con_error.append(f"{fecha_col} (Falta {t})")

            if not dias_con_error:
                st.success("¡Perfecto! Todos los días tienen cubiertos los turnos T1, T2 y T3.")
            else:
                st.error(f"⚠️ Errores de cobertura en: {', '.join(dias_con_error)}")

        # --- SECCIÓN 3: ALERTAS DE DEUDAS ---
        if any(v > 0 for v in dias_pendientes.values()):
            with st.expander("⚠️ Días de compensatorio pendientes por asignar"):
                for g, d in dias_pendientes.items():
                    if d > 0: st.warning(f"Al **{g}** se le deben {d} día(s) que no alcanzaron a compensarse en el rango seleccionado.")
