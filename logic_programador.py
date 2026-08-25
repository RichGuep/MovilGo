import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date, time
import holidays
import io
import os
import json
import base64
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# =========================================================
# 1. CONSTANTES, ESTILOS Y CONTROL DE FESTIVOS
# =========================================================
DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
INICIALES = {"Lunes": "L", "Martes": "M", "Miércoles": "X", "Jueves": "J", "Viernes": "V", "Sábado": "S", "Domingo": "D"}
festivos_co = holidays.Colombia(years=range(2025, 2030))
GRUPOS_TEC = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]

COLORES_MAP = {
    "T1": "#D6EAF8", "T2": "#D5F5E3", "T3": "#FADBD8", "T4": "#FCF3CF",
    "SOPORTE": "#E8DAEF", "FLOTANTE": "#E8DAEF", "DISPONIBLE": "#EAEDED",
    "DESCANSO": "#1B2631", "COMPENSADO": "#2E4053",
    "✅ OK 24/7": "#2ECC71", "❌ FALTA TURNO": "#E74C3C"
}

def style_malla_abordaje(df_pivot):
    styles = pd.DataFrame('', index=df_pivot.index, columns=df_pivot.columns)
    color_map = {"T1": "#D6EAF8", "T2": "#D5F5E3", "FLOTANTE": "#E8DAEF", "DESCANSO": "#1B2631"}
    for col in df_pivot.columns:
        es_fin_semana = False
        try:
            if pd.to_datetime(col).weekday() in [5, 6]: es_fin_semana = True
        except: pass
        for idx in df_pivot.index:
            val = str(df_pivot.at[idx, col]).strip()
            bg = color_map.get(val, "#1B2631")
            txt = "white" if val == "DESCANSO" else "#17202A"
            border = "1.5px solid #7F8C8D" if es_fin_semana else "0.5px solid #D5DBDB"
            
            # Nuevos colores para la auditoría
            if "✅ OK" in val: bg = "#2ECC71"; txt = "white"
            elif "❌ FALTA" in val: bg = "#E74C3C"; txt = "white"
            elif "🛌" in val: bg = "#F5B041"; txt = "#17202A"; border = "1px solid #17202A"

            styles.at[idx, col] = f'background-color: {bg}; color: {txt}; font-weight: 700; border: {border};'
    return df_pivot.style.apply(lambda _: styles, axis=None)

# =========================================================
# 2. CONECTIVIDAD BASE DE DATOS E HISTÓRICOS
# =========================================================
url_db = os.getenv("DATABASE_URL", "sqlite:///movilgo_local.db").replace('"', '').replace("'", "")
engine = create_engine(url_db)

def guardar_tabla(df, nombre_tabla):
    try:
        df.to_sql(nombre_tabla, engine, if_exists="replace", index=False)
        return True
    except Exception as e:
        st.error(f"Error guardando tabla '{nombre_tabla}' en BD: {e}")
        return False

def verificar_existencia_malla(nombre_tabla, inicio, fin):
    inicio_str = inicio.strftime('%Y-%m-%d')
    fin_str = fin.strftime('%Y-%m-%d')
    try:
        df = pd.read_sql(f"SELECT * FROM {nombre_tabla}", engine)
        df['Fecha_str'] = pd.to_datetime(df['Fecha']).dt.strftime('%Y-%m-%d')
        mask = (df['Fecha_str'] >= inicio_str) & (df['Fecha_str'] <= fin_str)
        return mask.any()
    except:
        return False

def guardar_malla_historico(df, nombre_tabla, inicio, fin):
    inicio_str = inicio.strftime('%Y-%m-%d')
    fin_str = fin.strftime('%Y-%m-%d')
    try:
        try:
            df_existente = pd.read_sql(f"SELECT * FROM {nombre_tabla}", engine)
            df_existente['Fecha_str'] = pd.to_datetime(df_existente['Fecha']).dt.strftime('%Y-%m-%d')
            mask = ~((df_existente['Fecha_str'] >= inicio_str) & (df_existente['Fecha_str'] <= fin_str))
            df_limpio = df_existente[mask].drop(columns=['Fecha_str'])
        except:
            df_limpio = pd.DataFrame()

        df_nuevo = df.copy()
        df_nuevo['Fecha'] = pd.to_datetime(df_nuevo['Fecha']).dt.strftime('%Y-%m-%d')
        df_final = pd.concat([df_limpio, df_nuevo], ignore_index=True)
        
        df_final.to_sql(nombre_tabla, engine, if_exists="replace", index=False)
        return True
    except Exception as e:
        st.error(f"Error guardando histórico: {e}")
        return False

def cargar_excel(nombre_archivo):
    try:
        if nombre_archivo == "empleados_grupos.xlsx":
            return pd.read_sql("SELECT * FROM cable_personal", engine)
        elif nombre_archivo == "empleados.xlsx":
            if os.path.exists("empleados.xlsx"):
                return pd.read_excel("empleados.xlsx")
            else:
                return pd.DataFrame()
    except Exception: 
        return pd.DataFrame()

with engine.begin() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS programacion_turnos (
            sujeto VARCHAR(100),
            fecha VARCHAR(20),
            turno VARCHAR(20),
            PRIMARY KEY (sujeto, fecha)
        )
    """))

def cargar_empleados_bd():
    try: return pd.read_sql("SELECT * FROM cable_personal", engine)
    except Exception: return pd.DataFrame()

def cargar_ajustes_bd():
    try:
        df = pd.read_sql("SELECT * FROM programacion_turnos", engine)
        ajustes = {}
        for _, row in df.iterrows():
            ajustes[(row['sujeto'], row['fecha'])] = row['turno']
        return ajustes
    except Exception: return {}

def guardar_ajuste_bd(sujeto, fecha, turno):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM programacion_turnos WHERE sujeto = :s AND fecha = :f"), {"s": sujeto, "f": fecha})
        conn.execute(text("INSERT INTO programacion_turnos (sujeto, fecha, turno) VALUES (:s, :f, :t)"), {"s": sujeto, "f": fecha, "t": turno})

def limpiar_y_guardar_malla_bd(ajustes_dict):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM programacion_turnos"))
        for (sujeto, fecha), turno in ajustes_dict.items():
            conn.execute(text("INSERT INTO programacion_turnos (sujeto, fecha, turno) VALUES (:s, :f, :t)"), {"s": sujeto, "f": fecha, "t": turno})

def cargar_ajustes_a_session():
    ajustes_db = cargar_ajustes_bd()
    st.session_state.ajustes_manuales = {}
    st.session_state.m_personas_editada = {}
    for (sujeto, fecha), turno in ajustes_db.items():
        if sujeto in GRUPOS_TEC or sujeto == "Abordaje":
            st.session_state.ajustes_manuales[(sujeto, fecha)] = turno
        else:
            st.session_state.m_personas_editada[(sujeto, fecha)] = turno

# =========================================================
# 2.5 UTILIDADES HTML / PDF / MAILING (¡NUEVO!)
# =========================================================
def generar_html_imprimible(df_pivot, titulo):
    html_content = f"""
    <html>
    <head>
        <title>{titulo}</title>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 20px; }}
            h1 {{ color: #1E3D59; text-align: center; }}
            table {{ border-collapse: collapse; width: 100%; font-size: 10px; }}
            th, td {{ border: 1px solid #ddd; padding: 6px; text-align: center; }}
            th {{ background-color: #1E3D59; color: white; }}
            .DESCANSO {{ background-color: #1B2631; color: white; font-weight: bold; }}
            .COMPENSADO {{ background-color: #2E4053; color: white; font-weight: bold; }}
        </style>
    </head>
    <body>
        <h1>{titulo}</h1>
        <p>Generado el: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        {df_pivot.to_html(classes='table', border=0)}
        <script>
            document.querySelectorAll('td').forEach(function(td) {{
                if(td.innerText.trim() === 'DESCANSO') td.className = 'DESCANSO';
                if(td.innerText.trim() === 'COMPENSADO') td.className = 'COMPENSADO';
            }});
        </script>
    </body>
    </html>
    """
    b64 = base64.b64encode(html_content.encode()).decode()
    href = f'<a href="data:text/html;base64,{b64}" download="Malla_{titulo.replace(" ", "_")}.html" target="_blank" style="text-decoration:none; color:white; background-color:#1E3D59; padding:8px 12px; border-radius:8px;">📄 Exportar Malla a PDF/HTML (Ctrl+P)</a>'
    return href

def enviar_correos_masivos(df_reporte, df_personal, mes_anio, remitente, password):
    if 'Fecha' in df_reporte.columns:
        df_reporte['Fecha_str'] = pd.to_datetime(df_reporte['Fecha']).dt.strftime('%d-%b')
    else:
        return False, "Error: El reporte no tiene columna de Fecha."

    col_nombre = 'Nombre' if 'Nombre' in df_reporte.columns else 'Sujeto'
    # Busca la columna de turno en el reporte generado
    col_turno = 'Turno realizado' if 'Turno realizado' in df_reporte.columns else 'Turno'

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(remitente, password)
    except Exception as e:
        return False, f"Error de conexión SMTP: {e}"

    enviados = 0
    for _, emp in df_personal.iterrows():
        nombre = emp['Nombre']
        email_destino = emp.get('Email', emp.get('Correo', None))
        
        if pd.isna(email_destino) or "@" not in str(email_destino): continue

        malla_empleado = df_reporte[df_reporte[col_nombre] == nombre]
        if malla_empleado.empty: continue
        
        tabla_turnos = "<table style='border-collapse: collapse; width: 100%;'><tr><th style='border: 1px solid #ddd; padding: 8px; background-color:#1E3D59; color:white;'>Fecha</th><th style='border: 1px solid #ddd; padding: 8px; background-color:#1E3D59; color:white;'>Turno Asignado</th></tr>"
        for _, row in malla_empleado.iterrows():
            turno_val = row[col_turno]
            color_bg = "#f2f2f2" if turno_val in ["DESCANSO", "COMPENSADO"] else "#ffffff"
            tabla_turnos += f"<tr style='background-color: {color_bg};'><td style='border: 1px solid #ddd; padding: 8px;'>{row['Fecha_str']}</td><td style='border: 1px solid #ddd; padding: 8px;'><b>{turno_val}</b></td></tr>"
        tabla_turnos += "</table>"

        html = f"""
        <html>
          <body>
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">
                <div style="background-color: #1E3D59; padding: 20px; text-align: center;">
                    <h2 style="color: white; margin: 0;">MovilGo - Operaciones Cablemovil</h2>
                </div>
                <div style="padding: 20px;">
                    <p>Hola <b>{nombre}</b>,</p>
                    <p>Tu programación operativa para el periodo <b>{mes_anio}</b> ha sido publicada oficialmente. A continuación, el detalle de tus turnos:</p>
                    <br>{tabla_turnos}<br>
                    <p style="font-size: 12px; color: #7f8c8d;">Recuerda presentarte a tu turno con anticipación. Este es un correo automático generado por MovilGo.</p>
                </div>
            </div>
          </body>
        </html>
        """
        msg = MIMEMultipart("alternative")
        msg['Subject'] = f"📅 Tu Programación de Turnos - {mes_anio}"
        msg['From'] = remitente
        msg['To'] = email_destino
        msg.attach(MIMEText(html, "html"))
        
        try:
            server.sendmail(remitente, email_destino, msg.as_string())
            enviados += 1
        except: pass

    server.quit()
    return True, f"Se enviaron {enviados} correos exitosamente."

# =========================================================
# 3. GESTIÓN DE PERSONAL
# =========================================================
def asignar_grupos_automatico(df):
    df = df.copy()
    if 'GrupoAsignado' in df.columns: df = df.drop(columns=['GrupoAsignado'])
    
    supervisores = df[df['Cargo'].str.contains('Supervisor', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    df_ops = df[~df['Cargo'].str.contains('Supervisor', case=False, na=False)]
    
    m = df_ops[df_ops['Cargo'].str.contains('Master', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    ta = df_ops[df_ops['Cargo'].str.contains('Tecnico A', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    tb = df_ops[df_ops['Cargo'].str.contains('Tecnico B', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    
    res = []
    for i, g in enumerate(GRUPOS_TEC):
        if i < len(supervisores):
            temp_sup = supervisores.iloc[[i]].copy(); temp_sup['GrupoAsignado'] = g; res.append(temp_sup)
        if i < len(m):
            temp_m = m.iloc[[i]].copy(); temp_m['GrupoAsignado'] = g; res.append(temp_m)
            
        temp_ta = ta.iloc[i*7:(i+1)*7].copy(); temp_ta['GrupoAsignado'] = g
        temp_tb = tb.iloc[i*3:(i+1)*3].copy(); temp_tb['GrupoAsignado'] = g
        res.extend([temp_ta, temp_tb])
        
    abo = df[df['Cargo'].str.contains('Abordaje', case=False, na=False)].copy()
    abo['GrupoAsignado'] = "Abordaje"
    res.append(abo)
    
    mask_core = df['Cargo'].str.contains('Supervisor|Master|Tecnico|Técnico|Abordaje', case=False, na=False)
    otros = df[~mask_core].copy()
    otros['GrupoAsignado'] = "None"
    res.append(otros)
    
    return pd.concat(res).reset_index(drop=True)

def pantalla_personal():
    st.subheader("👥 Gestión de Plantilla Operativa (Cablemovil)")
    
    if 'df_pers_ready' not in st.session_state:
        st.session_state.df_pers_ready = pd.DataFrame()

    st.markdown("#### 1. Importar Personal Nuevo (Excel)")
    archivo_excel = st.file_uploader("📥 Arrastra aquí tu archivo Excel de empleados (.xlsx o .xls)", type=["xlsx", "xls"])
    
    c1, c2, c3 = st.columns(3)
    
    with c1:
        if st.button("📥 1. Cargar Excel Subido", use_container_width=True):
            if archivo_excel is not None:
                try:
                    df = pd.read_excel(archivo_excel)
                    # Estandariza la columna de correo
                    if 'Correo' in df.columns: df.rename(columns={'Correo': 'Email'}, inplace=True)
                    if 'Email' not in df.columns: df['Email'] = ""
                    
                    if not df.empty: 
                        st.session_state.df_pers_ready = df
                        st.success("✅ Excel cargado exitosamente en memoria.")
                except Exception as e:
                    st.error(f"Error leyendo el archivo Excel: {e}")
            else:
                st.warning("⚠️ Por favor, arrastra un archivo en la caja superior primero.")
                
    with c2:
        if st.button("🗄️ 2. Cargar Personal de BD", use_container_width=True):
            df_bd = cargar_empleados_bd()
            if not df_bd.empty:
                st.session_state.df_pers_ready = df_bd
                st.success("✅ Plantilla operativa actual cargada desde PostgreSQL.")
            else:
                st.info("⚠️ No hay personal guardado en la Base de Datos aún.")
                
    with c3:
        if st.button("🎲 3. Auto-Asignar Grupos", use_container_width=True):
            if not st.session_state.df_pers_ready.empty:
                st.session_state.df_pers_ready = asignar_grupos_automatico(st.session_state.df_pers_ready)
                st.success("✅ Distribución de cuadrillas generada automáticamente.")
            else:
                st.error("⚠️ Carga personal primero (desde el Excel o la BD) antes de clasificar.")

    if not st.session_state.df_pers_ready.empty:
        st.markdown("---")
        st.markdown("#### 2. Revisión y Asignación de Grupos")
        st.info("Edita los nombres de los grupos manualmente o revisa la auto-asignación antes de guardar.")
        
        if 'GrupoAsignado' not in st.session_state.df_pers_ready.columns:
            st.session_state.df_pers_ready['GrupoAsignado'] = "None"
        if 'Email' not in st.session_state.df_pers_ready.columns: 
            st.session_state.df_pers_ready['Email'] = ""
            
        st.session_state.df_pers_ready['GrupoAsignado'] = st.session_state.df_pers_ready['GrupoAsignado'].fillna("None").astype(str)
        
        df_edit = st.data_editor(
            st.session_state.df_pers_ready,
            use_container_width=True,
            column_config={
                "GrupoAsignado": st.column_config.TextColumn("📦 Grupo Asignado (Ej: Grupo 1, Almacen A)", required=True),
                "Email": st.column_config.TextColumn("✉️ Correo para Notificaciones")
            },
            key="personal_dropdown_v20"
        )
        
        if st.button("💾 Guardar Estructura Definitiva en BD", type="primary"):
            st.session_state.df_pers_ready = df_edit
            if guardar_tabla(df_edit, "cable_personal"):
                st.success("🎉 ¡Personal guardado exitosamente en PostgreSQL (Tabla: cable_personal)!")
# =========================================================
# 4. MOTOR DE ASIGNACIÓN TÉCNICOS (DINÁMICO)
# =========================================================

def crear_personal_tecnicos_dinamico(q_sup, q_mas, q_ta, q_tb):
    filas = []
    roles = [("Supervisor", q_sup), ("Master", q_mas), ("Tecnico A", q_ta), ("Tecnico B", q_tb)]
    
    for rol, qty in roles:
        for i in range(qty):
            # Repartimos equitativamente en los 4 grupos
            grupo = GRUPOS_TEC[i % 4]
            filas.append({"Nombre": f"{rol}_{i+1:02d}", "Cargo": rol, "Grupo": grupo})
            
    return pd.DataFrame(filas)

def generar_malla_tecnicos_avanzado(inicio, fin, df_personal, descansos_iniciales, conceder_compensatorio, tipo_ciclo_descanso, activar_t4=False):
    if df_personal.empty: return pd.DataFrame()
    
    filas = []
    deudas = {g: 0 for g in GRUPOS_TEC}
    
    turnos_historia = {g: i for i, g in enumerate(GRUPOS_TEC)} 
    ayer_descanso = {g: False for g in GRUPOS_TEC}
    
    # Filtrar solo los días permitidos por el usuario para la rotación
    dias_permitidos = []
    for d in DIAS_ES: # Orden cronológico L-D
        if d in descansos_iniciales.values() and d not in dias_permitidos:
            dias_permitidos.append(d)
    if not dias_permitidos: dias_permitidos = DIAS_ES
    
    for fecha in pd.date_range(inicio, fin):
        dia_n = DIAS_ES[fecha.weekday()]
        sem = fecha.isocalendar()[1]
        delta_meses = (fecha.year - inicio.year) * 12 + (fecha.month - inicio.month)
        fecha_str = fecha.strftime('%Y-%m-%d')
        es_fin_semana = (fecha.weekday() in [5, 6])
        mes_str = fecha.strftime('%Y-%m') # Agrupador mensual
        
        if tipo_ciclo_descanso == "Mensual": desplazamiento = delta_meses
        elif tipo_ciclo_descanso == "Trimestral": desplazamiento = delta_meses // 3
        else: desplazamiento = 0
            
        descansos_vivos = {}
        for g in GRUPOS_TEC:
            d_name = descansos_iniciales[g]
            if d_name in dias_permitidos:
                idx_inicial = dias_permitidos.index(d_name)
                # La rotación matemática se encierra en los días permitidos
                idx_rotado = (idx_inicial + desplazamiento) % len(dias_permitidos)
                descansos_vivos[g] = dias_permitidos[idx_rotado]
            else:
                descansos_vivos[g] = d_name

        asig_grupos = {}
        gps_h = [g for g, d in descansos_vivos.items() if d == dia_n]
        if len(gps_h) > 1:
            idx = sem % len(gps_h)
            d_r = gps_h[idx]
            asig_grupos[d_r] = "DESCANSO"
            for g in gps_h: 
                if g != d_r and conceder_compensatorio: deudas[g] += 1
        elif len(gps_h) == 1: 
            asig_grupos[gps_h[0]] = "DESCANSO"
        
        if 0 <= fecha.weekday() <= 4 and conceder_compensatorio:
            g_d = sorted([g for g, d in deudas.items() if d > 0 and g not in asig_grupos], key=lambda x: deudas[x], reverse=True)
            if g_d: 
                asig_grupos[g_d[0]] = "COMPENSADO"
                deudas[g_d[0]] -= 1

        activos = [g for g in GRUPOS_TEC if g not in asig_grupos]
        
        for g in activos:
            if ayer_descanso[g]: turnos_historia[g] = (turnos_historia[g] + 1) % 4
                
        asignacion_hoy = {}
        usados = set()
        
        for g in activos:
            deseado = turnos_historia[g]
            if deseado < 3 and deseado not in usados:
                asignacion_hoy[g] = deseado
                usados.add(deseado)
                
        faltantes = [t for t in [0, 1, 2] if t not in usados]
        libres = [g for g in activos if g not in asignacion_hoy]
        
        for g in libres:
            if faltantes:
                asignado = faltantes.pop(0)
                asignacion_hoy[g] = asignado
                turnos_historia[g] = asignado 
            else:
                asignacion_hoy[g] = 3
                turnos_historia[g] = 3
                
        turnos_map = {
            0: "T1", 1: "T2", 2: "T3", 
            3: "T4" if (activar_t4 and not es_fin_semana) else "DISPONIBLE"
        }
        
        for g in GRUPOS_TEC:
            if g in asig_grupos:
                turno_final = asig_grupos[g]
                ayer_descanso[g] = True
            else:
                turno_final = turnos_map[asignacion_hoy[g]]
                ayer_descanso[g] = False
                
            asig_grupos[g] = turno_final 

        # EXPANSIÓN A PERSONAL INDIVIDUAL
        for _, p in df_personal.iterrows():
            nombre = p["Nombre"]
            grupo = p["Grupo"]
            t_final = asig_grupos.get(grupo, "DESCANSO")
            
            # Prioridad 1: Ajuste a la persona (Micro)
            if "m_personas_editada" in st.session_state and (nombre, fecha_str) in st.session_state.m_personas_editada:
                t_final = st.session_state.m_personas_editada[(nombre, fecha_str)]
            # Prioridad 2: Ajuste a todo el grupo (Macro)
            elif "ajustes_manuales" in st.session_state and (grupo, fecha_str) in st.session_state.ajustes_manuales:
                t_final = st.session_state.ajustes_manuales[(grupo, fecha_str)]
                
            filas.append({
                "Fecha": fecha, "Mes": mes_str, "Grupo": grupo, "Nombre": nombre, "Cargo": p["Cargo"], 
                "Descanso_Base": descansos_iniciales.get(grupo, "Domingo"), 
                "Descanso_Actual": descansos_vivos.get(grupo, "Domingo"), 
                "Turno": t_final
            })
            
    return pd.DataFrame(filas)

# =========================================================
# 5. CÁLCULO DE RECARGOS Y REPORTES (TÉCNICOS)
# =========================================================
def obtener_minutos_desde_time(objeto_hora):
    if objeto_hora is None: return None
    if isinstance(objeto_hora, time): return objeto_hora.hour * 60 + objeto_hora.minute
    s = str(objeto_hora).strip().upper()
    if s in ["OFF", "NAN", ""]: return None
    for fmt in ("%H:%M:%S", "%H:%M"):
        try: return datetime.strptime(s, fmt).hour * 60 + datetime.strptime(s, fmt).minute
        except: pass
    return None

def calcular_metricas_reforma(inicio_str, fin_str, fecha_ts):
    if pd.isna(inicio_str) or pd.isna(fin_str): return 0.0, 0.0, 0.0
    s_ini = str(inicio_str).strip().upper()
    s_fin = str(fin_str).strip().upper()
    if "OFF" in s_ini or "OFF" in s_fin: return 0.0, 0.0, 0.0

    min_inicio = obtener_minutos_desde_time(inicio_str)
    min_fin = obtener_minutos_desde_time(fin_str)
    if min_inicio is None or min_fin is None: return 0.0, 0.0, 0.0

    minutos_totales = min_fin - min_inicio if min_fin >= min_inicio else (1440 - min_inicio) + min_fin
    total_horas = minutos_totales / 60.0
    
    horas_extras = 0.0 if (inicio_str == "06:30" and fin_str == "13:30") or (inicio_str == "13:30" and fin_str == "20:30") else max(0.0, total_horas - 7.0)
    
    minutos_nocturnos = sum(1 for min_actual in range(int(min_inicio), int(min_inicio + minutos_totales)) if (min_actual % 1440) >= 1140 or (min_actual % 1440) < 360)
    return round(total_horas, 2), round(horas_extras, 2), round(minutos_nocturnos / 60.0, 2)

def procesar_archivo_malla_externa(df_externo):
    try:
        columna_clave = df_externo.columns[0]
        df_externo = df_externo.rename(columns={columna_clave: "Sujeto"})
        df_plano = df_externo.melt(id_vars="Sujeto", var_name="Fecha", value_name="Turno")
        df_plano["Fecha"] = pd.to_datetime(df_plano["Fecha"])
        df_plano["Turno"] = df_plano["Turno"].fillna("DESCANSO").astype(str).str.strip().str.upper()
        return df_plano
    except Exception as e:
        st.sidebar.error(f"Estructura inválida: {str(e)}")
        return pd.DataFrame()

def ejecutar_auditoria_completa(df_plano):
    df_aud = df_plano.copy()
    df_aud["Fecha"] = pd.to_datetime(df_aud["Fecha"])
    cob = df_aud.groupby(["Fecha", "Turno"]).size().unstack(fill_value=0)
    for c in ["T1", "T2", "T3", "T4", "DESCANSO", "COMPENSADO", "DISPONIBLE"]:
        if c not in cob.columns: cob[c] = 0
    return cob

# 🟢 MODIFICADA PARA EXTRAER SUJETO Y FECHA EXACTA
def verificar_alarmas_cambios_drasticos(df_plano):
    df_plano = df_plano.sort_values(by=["Nombre", "Fecha"])
    alertas = []
    for sujeto, group in df_plano.groupby("Nombre"):
        lista_turnos = group["Turno"].tolist()
        lista_fechas = group["Fecha"].tolist()
        for i in range(1, len(lista_turnos)):
            t_anterior = lista_turnos[i-1]
            t_actual = lista_turnos[i]
            fecha_act = lista_fechas[i]
            
            if t_anterior in ["T3", "T4"] and t_actual in ["T1", "T2", "DISPONIBLE"]: 
                alertas.append({
                    "Mensaje": f"🚨 **Violación Circadiana ({t_anterior} -> {t_actual})** en '{sujeto}' el {fecha_act.strftime('%Y-%m-%d')}.",
                    "Sujeto": sujeto,
                    "Fecha": fecha_act.strftime('%Y-%m-%d')
                })
            elif t_anterior == "T2" and t_actual == "T1":
                alertas.append({
                    "Mensaje": f"⚠️ **Transición Corta Inválida (T2 -> T1)** en '{sujeto}' el {fecha_act.strftime('%Y-%m-%d')}.",
                    "Sujeto": sujeto,
                    "Fecha": fecha_act.strftime('%Y-%m-%d')
                })
    return alertas

def generar_reporte_detallado(df_final, config_horas):
    filas_reporte = []
    df_final['Fecha'] = pd.to_datetime(df_final['Fecha'])

    for _, m_fila in df_final.iterrows():
        turno_asignado = m_fila['Turno']
        fecha_dt = m_fila['Fecha']
        fecha_str = fecha_dt.strftime('%Y-%m-%d')

        info_turno = config_horas.get(turno_asignado, {"Inicio": "OFF", "Fin": "OFF"})
        ini = info_turno.get("Inicio", "OFF")
        fin = info_turno.get("Fin", "OFF")

        h_prog, h_extra, h_noc = calcular_metricas_reforma(ini, fin, fecha_dt)

        filas_reporte.append({
            "Fecha": fecha_str, "Nombre": m_fila['Nombre'], "Cargo": m_fila['Cargo'], 
            "Grupo Asignado": m_fila['Grupo'], "Descanso Actual": m_fila.get('Descanso_Actual', 'Domingo'),
            "Turno realizado": turno_asignado, "Hora inicio": ini, "Hora fin": fin, 
            "Horas Programado": h_prog, "Horas Extras": h_extra, "Recargos Nocturnos": h_noc,
            "Mes": fecha_dt.strftime('%Y-%m'), "Semana": fecha_dt.isocalendar()[1]
        })
    return pd.DataFrame(filas_reporte)

# 🟢 MODIFICADA PARA INCLUIR CONTEXTO VISUAL
@st.dialog("🛠️ Gestor de Turno y Contexto Operativo", width="large")
def popup_forzar_ajuste_fecha(fecha_solicitada, df_context=pd.DataFrame(), sujeto_predef=None):
    st.markdown(f"### 📅 Fecha de Operación a corregir: `{fecha_solicitada}`")

    # 1. 🟢 TABLA DE CONTEXTO (3 DÍAS ANTES Y DESPUÉS)
    if not df_context.empty:
        st.markdown("##### 🔎 Contexto de la Operación")
        fecha_dt = pd.to_datetime(fecha_solicitada)
        f_ini = fecha_dt - timedelta(days=3)
        f_fin = fecha_dt + timedelta(days=3)
        
        mask = (df_context['Fecha'] >= f_ini) & (df_context['Fecha'] <= f_fin)
        df_filtro = df_context[mask].copy()
        
        if not df_filtro.empty:
            pivot_ctx = df_filtro.pivot_table(index=["Grupo", "Nombre"], columns="Fecha", values="Turno", aggfunc='first').fillna("DESCANSO")
            pivot_ctx.columns = [p.strftime('%Y-%m-%d') for p in pivot_ctx.columns]
            st.dataframe(style_malla_tecnicos(pivot_ctx), use_container_width=True)
        st.write("---")

    # 2. 🟢 SELECTOR MACRO/MICRO INTEGRADO
    tipo_ajuste = st.radio("🎯 Nivel de Ajuste:", ["Ajustar Empleado (Micro)", "Ajustar Grupo Completo (Macro)"], horizontal=True)
    
    if tipo_ajuste == "Ajustar Empleado (Micro)":
        opciones_sujetos = sorted(list(df_context["Nombre"].unique())) if not df_context.empty else []
        es_modo_persona = True
    else:
        opciones_sujetos = GRUPOS_TEC
        es_modo_persona = False
        
    # Lógica para pre-seleccionar inteligentemente
    idx_def = 0
    if sujeto_predef in opciones_sujetos:
        idx_def = opciones_sujetos.index(sujeto_predef)
    elif sujeto_predef and not es_modo_persona and not df_context.empty:
        # Si venimos de una alarma (sujeto_predef = Persona) pero cambiamos a Macro, deduce el Grupo
        try:
            grupo_deducido = df_context[df_context["Nombre"] == sujeto_predef]["Grupo"].iloc[0]
            if grupo_deducido in opciones_sujetos:
                idx_def = opciones_sujetos.index(grupo_deducido)
        except: pass

    # 3. 🟢 FORMULARIO DE CORRECCIÓN
    c1, c2 = st.columns(2)
    sujeto_sel = c1.selectbox("Elemento a Modificar:", opciones_sujetos, index=idx_def)
    opciones_turnos = ["T1", "T2", "T3", "T4", "DESCANSO", "COMPENSADO", "DISPONIBLE"]
    nuevo_turno = c2.selectbox("🆕 Turno Destino Asignado:", opciones_turnos, index=0)
    
    if st.button("🔄 Aplicar a Previsualización", use_container_width=True):
        fecha_actual_dt = pd.to_datetime(fecha_solicitada)
        fecha_ayer_str = (fecha_actual_dt - timedelta(days=1)).strftime('%Y-%m-%d')
        
        turno_ayer = "DESCANSO"
        dict_revisar = st.session_state.m_personas_editada if es_modo_persona else st.session_state.ajustes_manuales
        if (sujeto_sel, fecha_ayer_str) in dict_revisar:
            turno_ayer = dict_revisar[(sujeto_sel, fecha_ayer_str)]

        if turno_ayer in ["T3", "T4"] and nuevo_turno in ["T1", "T2", "DISPONIBLE"]:
            st.error(f"❌ **Cambio Denegado por Fatiga Crítica:** No se permite pasar de un turno Nocturno ({turno_ayer}) a turnos diurnos ({nuevo_turno}) sin un día intermedio de descanso.")
            return
        if turno_ayer == "T2" and nuevo_turno == "T1":
            st.error("❌ **Cambio Denegado:** Transición descendente corta inválida (T2 -> T1).")
            return

        guardar_ajuste_bd(sujeto_sel, fecha_solicitada, nuevo_turno)

        if es_modo_persona: st.session_state.m_personas_editada[(sujeto_sel, fecha_solicitada)] = nuevo_turno
        else: st.session_state.ajustes_manuales[(sujeto_sel, fecha_solicitada)] = nuevo_turno
            
        st.success("¡Turno validado en memoria! No olvides Guardar la Malla Definitiva.")
        st.rerun()

def style_malla_tecnicos(df_pivot):
    styles = pd.DataFrame('', index=df_pivot.index, columns=df_pivot.columns)
    color_map = {
        "T1": "#D6EAF8", "T2": "#D5F5E3", "T3": "#FADBD8", "T4": "#FCF3CF", 
        "DISPONIBLE": "#EAEDED", "FLOTANTE": "#E8DAEF", "DESCANSO": "#1B2631", "COMPENSADO": "#2E4053"
    }
    for col in df_pivot.columns:
        es_fin_semana = "🏖️" in str(col)
        es_festivo = "🇨🇴" in str(col)
        
        for idx in df_pivot.index:
            val = str(df_pivot.at[idx, col]).strip()
            
            if val == "": 
                bg = "#FFFFFF"; txt = "#FFFFFF"; border = "none"
            else:
                bg = color_map.get(val, "#1B2631") if val in color_map else "#FFFFFF"
                if "✅ OK" in val: bg = "#2ECC71"; txt = "white"
                elif "❌ FALTA" in val: bg = "#E74C3C"; txt = "white"
                else: txt = "white" if val in ["DESCANSO", "COMPENSADO"] else "#17202A"
                
                border = "1.5px solid #7F8C8D" if es_fin_semana else "0.5px solid #D5DBDB"
                if es_festivo: border = "2px solid #E67E22" 

            styles.at[idx, col] = f'background-color: {bg}; color: {txt}; font-weight: 700; border: {border};'
    return df_pivot.style.apply(lambda _: styles, axis=None)


# =========================================================
# 7. INTERFAZ OPERATIVA PRINCIPAL (TÉCNICOS)
# =========================================================
def pantalla_programador():
    if "ajustes_manuales" not in st.session_state: st.session_state.ajustes_manuales = {}
    if "m_personas_editada" not in st.session_state: st.session_state.m_personas_editada = {}

    st.sidebar.markdown("---")
    st.sidebar.subheader("📥 Carga de Mallas Externas")
    archivo_malla = st.sidebar.file_uploader("Arrastra aquí el Excel de la Malla (.xlsx):", type=["xlsx", "xls"])
    if archivo_malla is not None:
        try:
            df_cargado_raw = pd.read_excel(archivo_malla)
            if st.sidebar.button("🔄 Importar a Histórico BD"):
                df_aplanado = procesar_archivo_malla_externa(df_cargado_raw)
                if not df_aplanado.empty:
                    guardar_malla_historico(df_aplanado, "cable_malla_tecnicos", df_aplanado['Fecha'].min(), df_aplanado['Fecha'].max())
                    st.sidebar.success("✅ Malla histórica importada y guardada en BD con éxito.")
                    st.rerun()
        except Exception as e: st.sidebar.error(f"Error de lectura: {str(e)}")

    st.markdown("## ⚙️ Panel de Programación - Cuadrilla Técnica")

    # 1. GENERACIÓN DE PLANTA DINÁMICA
    st.subheader("1. Estructura de Personal y Grupos")
    c1, c2, c3, c4 = st.columns(4)
    q_sup = c1.number_input("Supervisores", 0, 20, 4)
    q_mas = c2.number_input("Másters", 0, 20, 4)
    q_ta = c3.number_input("Técnicos A", 0, 50, 28)
    q_tb = c4.number_input("Técnicos B", 0, 50, 12)

    if st.button("🔄 Generar / Reiniciar Lista de Técnicos"):
        st.session_state.df_personal_tec = crear_personal_tecnicos_dinamico(q_sup, q_mas, q_ta, q_tb)
        st.success("Lista generada. Puedes reasignar los grupos manualmente a continuación.")

    if "df_personal_tec" not in st.session_state:
        st.session_state.df_personal_tec = crear_personal_tecnicos_dinamico(q_sup, q_mas, q_ta, q_tb)

    df_pers_editado = st.data_editor(
        st.session_state.df_personal_tec,
        use_container_width=True,
        hide_index=True
    )

    # 2. PARÁMETROS DE OPERACIÓN
    st.write("---")
    st.subheader("2. Parámetros de Operación")
    c_p1, c_p2 = st.columns(2)
    conceder_compensatorio = c_p1.checkbox("⚖️ Otorgar Compensatorios por Trabajo Dominical", value=True)
    valor_hora = c_p2.number_input("💰 Valor Hora Ordinaria ($):", min_value=0, value=6500, step=500, key="vh_tec")

    tipo_ciclo_descanso = st.selectbox("🔄 Rotación Temporal del Día de Descanso Base:", ["Fijo sin rotación", "Mensual", "Trimestral"])
    activar_t4 = st.toggle("⚡ Activar Esquema Eficiente (T4 - 7 Horas L-V)", value=False)

    with st.expander("⏰ Configuración Rangos de Jornada", expanded=False):
        config_h = {}
        t_l = ["T1", "T2", "T3", "DISPONIBLE"] + (["T4"] if activar_t4 else [])
        def_h = {"T1": [time(4,0), time(11,0)], "T2": [time(11,0), time(18,0)], "T3": [time(15,0), time(22,0)], "T4": [time(21,0), time(4,0)], "DISPONIBLE": [time(6,30), time(13,30)]}
        cols = st.columns(3)
        for i, t in enumerate(t_l):
            with cols[i%3]:
                ini = st.time_input(f"Inicia {t}", def_h[t][0], key=f"i{t}")
                fin = st.time_input(f"Fin {t}", def_h[t][1], key=f"f{t}")
                config_h[t] = {"Inicio": ini.strftime("%H:%M"), "Fin": fin.strftime("%H:%M")}
        config_h["DESCANSO"] = config_h["COMPENSADO"] = {"Inicio": "OFF", "Fin": "OFF"}
        if not activar_t4: config_h["T4"] = {"Inicio": "21:00", "Fin": "04:00"}

    # 3. ASIGNACIÓN DE DESCANSOS
    st.write("---")
    c1, c2 = st.columns(2)
    inicio, fin = c1.date_input("Inicio Planificación", date(2026, 7, 1)), c2.date_input("Fin Planificación", date(2026, 12, 31))
    
    st.markdown("**Días de Descanso Base por Grupo:**")
    cols = st.columns(4)
    desc_data = {f"Grupo {i+1}": cols[i].selectbox(f"Descanso G{i+1}", DIAS_ES, index=[4,5,6,0][i]) for i in range(4)}

    # 4. GENERACIÓN DE MALLA
    if 'm_base' not in st.session_state:
        st.session_state.m_base = generar_malla_tecnicos_avanzado(inicio, fin, df_pers_editado, desc_data, conceder_compensatorio, tipo_ciclo_descanso, activar_t4)

    if st.button("👁️ PREVISUALIZAR MALLA (Sin Guardar)"):
        st.session_state.ajustes_manuales = {}
        st.session_state.m_personas_editada = {}
        st.session_state.m_base = generar_malla_tecnicos_avanzado(inicio, fin, df_pers_editado, desc_data, conceder_compensatorio, tipo_ciclo_descanso, activar_t4)

    if 'm_base' in st.session_state and not st.session_state.m_base.empty:
        df_final = generar_malla_tecnicos_avanzado(inicio, fin, df_pers_editado, desc_data, conceder_compensatorio, tipo_ciclo_descanso, activar_t4)
        
        st.write("---")
        st.subheader("💾 Guardar Malla en Histórico BD y Notificar")
        ya_existe = verificar_existencia_malla("cable_malla_tecnicos", inicio, fin)
        
        c_b1, c_b2 = st.columns(2)
        with c_b1:
            if st.button("⚠️ Confirmar y Actualizar Histórico" if ya_existe else "💾 Guardar Malla Definitiva"):
                if guardar_malla_historico(df_final, "cable_malla_tecnicos", inicio, fin):
                    guardar_malla_historico(generar_reporte_detallado(df_final, config_h), "cable_nomina_tecnicos", inicio, fin)
                    st.success("🎉 ¡Malla y Reporte guardados exitosamente!")
        
        with c_b2:
            with st.popover("📩 Enviar Malla por Correo"):
                remitente = st.text_input("Tu Correo Remitente", key="rem_tec")
                password = st.text_input("Contraseña App", type="password", key="pass_tec")
                if st.button("🚀 Enviar Correos"):
                    if remitente and password:
                        with st.spinner("Enviando..."):
                            df_rep = generar_reporte_detallado(df_final, config_h)
                            exito, msj = enviar_correos_masivos(df_rep, df_pers_editado, inicio.strftime('%B %Y'), remitente, password)
                            if exito: st.success(msj)
                            else: st.error(msj)

        # =========================================================
        # 5. UI: PIVOTS Y FORMATO CON MESES / ICONOS
        # =========================================================
        st.write("---")
        st.subheader("📋 Malla Operativa")
        
        meses_disponibles = sorted(df_final['Mes'].unique())
        opciones_mes = ["Todos los meses"] + meses_disponibles
        mes_seleccionado = st.selectbox("📅 Filtrar Malla por Mes:", opciones_mes, key="filtro_mes_tec")

        opt_vista = st.radio("👀 Nivel de Detalle:", ["Vista Macro (Por Grupos)", "Vista Micro (Por Persona)"], horizontal=True)

        if mes_seleccionado != "Todos los meses":
            df_mostrar = df_final[df_final['Mes'] == mes_seleccionado].copy()
            indice_pivot = ["Grupo", "Descanso_Actual"] if opt_vista == "Vista Macro (Por Grupos)" else ["Grupo", "Descanso_Actual", "Cargo", "Nombre"]
        else:
            df_mostrar = df_final.copy()
            indice_pivot = ["Grupo", "Descanso_Base"] if opt_vista == "Vista Macro (Por Grupos)" else ["Grupo", "Descanso_Base", "Cargo", "Nombre"]

        pivot_malla = df_mostrar.pivot_table(index=indice_pivot, columns="Fecha", values="Turno", aggfunc='first').fillna("DESCANSO")
        
        # LÓGICA DE AUDITORÍA DIARIA (SEMAFORO)
        cob = df_mostrar.groupby(["Fecha", "Turno"]).size().unstack(fill_value=0)
        for c in ["T1", "T2", "T3", "T4", "DESCANSO", "COMPENSADO"]:
            if c not in cob.columns: cob[c] = 0
            
        fila_semaforo = {}
        for col_fecha in pivot_malla.columns:
            col_dt = pd.to_datetime(col_fecha)
            es_f_s = (col_dt.weekday() in [5, 6])
            
            if col_dt in cob.index:
                t1_ok = cob.at[col_dt, "T1"] > 0
                t2_ok = cob.at[col_dt, "T2"] > 0
                t3_ok = cob.at[col_dt, "T3"] > 0
                t4_ok = cob.at[col_dt, "T4"] > 0
                hay_descanso_hoy = (cob.at[col_dt, "DESCANSO"] > 0 or cob.at[col_dt, "COMPENSADO"] > 0)
                
                if activar_t4 and not es_f_s and not hay_descanso_hoy:
                    status = "✅ OK 24/7" if (t1_ok and t2_ok and t3_ok and t4_ok) else "❌ FALTA TURNO"
                else:
                    status = "✅ OK 24/7" if (t1_ok and t2_ok and t3_ok) else "❌ FALTA TURNO"
                fila_semaforo[col_fecha] = status
            else:
                fila_semaforo[col_fecha] = "❌ FALTA TURNO"

        idx_len = len(pivot_malla.index.names) if isinstance(pivot_malla.index, pd.MultiIndex) else 1
        idx_tuple = tuple(["🔍 AUDITORÍA"] + ["-"] * (idx_len - 1)) if idx_len > 1 else "🔍 AUDITORÍA 24/7"
        
        df_sem_row = pd.DataFrame([fila_semaforo], index=[idx_tuple])
        pivot_completo = pd.concat([pivot_malla, df_sem_row])

        DIAS_CORTOS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
        nuevas_cols = []
        for col in pivot_completo.columns:
            if isinstance(col, (datetime, date, pd.Timestamp)):
                dt = pd.to_datetime(col)
                dia_str = DIAS_CORTOS[dt.weekday()]
                fecha_str = dt.strftime('%d-%b')
                
                if dt in festivos_co: nuevas_cols.append(f"{fecha_str} ({dia_str}) 🇨🇴")
                elif dt.weekday() in [5, 6]: nuevas_cols.append(f"{fecha_str} ({dia_str}) 🏖️")
                else: nuevas_cols.append(f"{fecha_str} ({dia_str})")
            else:
                nuevas_cols.append(str(col))
        
        pivot_completo.columns = nuevas_cols
        
        st.markdown(generar_html_imprimible(pivot_malla, f"Malla Técnicos - {mes_seleccionado}"), unsafe_allow_html=True)
        st.dataframe(style_malla_tecnicos(pivot_completo), use_container_width=True)

        st.write("---")
        st.subheader("⚙️ Panel de Gestión y Corrección")
        # El radio button de Macro/Micro se movió al interior del Popup, limpiando la UI externa.
        
        with st.expander("🔍 Forzar cambio libre en cualquier fecha de la Malla"):
            c_f1, c_f2 = st.columns(2)
            fechas_unicas = sorted([d.strftime('%Y-%m-%d') for d in pd.to_datetime(df_final['Fecha'].unique())])
            f_libre_sel = c_f1.selectbox("Seleccione la Fecha:", fechas_unicas, key="f_libre_dropdown_tec")
            if c_f2.button("⚙️ Abrir Gestor de Turno para esta Fecha", use_container_width=True):
                # 🟢 Lanza popup y envía el dataframe final para dar contexto
                popup_forzar_ajuste_fecha(f_libre_sel, df_context=df_final)

        st.write("---")
        t_dash, t_fatiga, t_nomina, t_hist, t_audit = st.tabs(["📊 Dashboard de Costos", "⚠️ Alarmas de Fatiga", "📋 Reporte Nómina", "🗄️ Consultar Histórico BD", "🔎 Auditoría Personal"])
        rep_maestro = generar_reporte_detallado(df_final, config_h)

        with t_dash:
            if not rep_maestro.empty:
                t_hrs = rep_maestro['Horas Programado'].sum()
                t_ext = rep_maestro['Horas Extras'].sum()
                costo_base = t_hrs * valor_hora
                costo_extras = t_ext * (valor_hora * 1.25)
                
                c_m1, c_m2, c_m3 = st.columns(3)
                c_m1.metric("💰 Costo Proyectado Base", f"${costo_base:,.0f} COP")
                c_m2.metric("📈 Costo Proyectado Extras", f"${costo_extras:,.0f} COP")
                c_m3.metric("⏱️ Total Horas Operativas", f"{t_hrs:,.0f} h")
                
                rep_maestro['Costo Total ($)'] = (rep_maestro['Horas Programado'] * valor_hora) + (rep_maestro['Horas Extras'] * valor_hora * 1.25)
                st.bar_chart(rep_maestro.groupby("Nombre")['Costo Total ($)'].sum().reset_index(), x="Nombre", y="Costo Total ($)")
            
        with t_fatiga:
            lista_alertas = verificar_alarmas_cambios_drasticos(df_final)
            if lista_alertas:
                # 🟢 NUEVO DISEÑO: Botón directo en la alarma pre-llenando el empleado y la fecha
                for idx_al, al in enumerate(lista_alertas):
                    c_al1, c_al2 = st.columns([5, 1])
                    c_al1.warning(al["Mensaje"])
                    if c_al2.button("🛠️ Corregir", key=f"btn_corr_fatiga_tec_{idx_al}"):
                        popup_forzar_ajuste_fecha(
                            al["Fecha"], 
                            df_context=df_final, 
                            sujeto_predef=al["Sujeto"]
                        )
            else: st.success("✅ Estructura libre de alertas de fatiga.")
            
        with t_nomina:
            st.dataframe(rep_maestro, use_container_width=True)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer: 
                rep_maestro.to_excel(writer, sheet_name="Detalle", index=False)
            st.download_button("📥 Descargar Nómina", output.getvalue(), f"Nomina_Tecnicos_{date.today()}.xlsx")

        with t_hist:
            try:
                df_hist = pd.read_sql("SELECT * FROM cable_malla_tecnicos", engine)
                df_hist['Fecha_str'] = pd.to_datetime(df_hist['Fecha']).dt.strftime('%Y-%m-%d')
                c_h1, c_h2 = st.columns(2)
                h_ini = c_h1.date_input("Desde:", inicio, key="h_ini_t")
                h_fin = c_h2.date_input("Hasta:", fin, key="h_fin_t")
                df_filtrado = df_hist[(df_hist['Fecha_str'] >= h_ini.strftime('%Y-%m-%d')) & (df_hist['Fecha_str'] <= h_fin.strftime('%Y-%m-%d'))]
                if not df_filtrado.empty:
                    pivot_h = df_filtrado.pivot_table(index=["Grupo", "Nombre"], columns="Fecha", values="Turno", aggfunc='first').fillna("DESCANSO")
                    pivot_h.columns = [p.strftime('%Y-%m-%d') for p in pivot_h.columns]
                    st.dataframe(style_malla_tecnicos(pivot_h), use_container_width=True)
            except: st.info("BD vacía.")

        with t_audit:
            st.markdown("#### 🔎 Auditoría de Turnos y Descansos por Mes")
            if not df_final.empty:
                df_audit_per = df_final.copy()
                
                audit_pivot = df_audit_per.pivot_table(
                    index=['Mes', 'Grupo', 'Nombre', 'Cargo'], 
                    columns='Turno', 
                    aggfunc='size', 
                    fill_value=0
                ).reset_index()
                
                posibles_turnos = ["T1", "T2", "T3", "T4", "DISPONIBLE", "DESCANSO", "COMPENSADO"]
                for c in posibles_turnos:
                    if c not in audit_pivot.columns: audit_pivot[c] = 0
                        
                cols_order = ['Mes', 'Grupo', 'Nombre', 'Cargo'] + posibles_turnos
                audit_pivot = audit_pivot[cols_order]
                
                st.dataframe(audit_pivot, use_container_width=True)
                
                output_audit = io.BytesIO()
                with pd.ExcelWriter(output_audit, engine='openpyxl') as writer: 
                    audit_pivot.to_excel(writer, sheet_name="Auditoria_Mensual", index=False)
                st.download_button("📥 Descargar Auditoría", output_audit.getvalue(), f"Auditoria_Mensual_Tecnicos_{date.today()}.xlsx")

# =========================================================
# 8. MOTOR Y PANEL DE ABORDAJE (AUDITORÍA DINÁMICA DE FLOTANTES)
# =========================================================

def crear_personal_abordaje_dinamico(total_personas, num_flotantes, dias_permitidos):
    filas = []
    num_regulares = total_personas - num_flotantes
    
    dias = dias_permitidos if dias_permitidos else ["Domingo"]
    
    for i in range(num_regulares):
        dia_asignado = dias[i % len(dias)]
        filas.append({"Nombre": f"Abordaje_{i+1:02d}", "Rol": "Regular", "Descanso_Base": dia_asignado})
    
    for i in range(num_flotantes):
        filas.append({"Nombre": f"Flotante_{i+1:02d}", "Rol": "Flotante", "Descanso_Base": "Flotante"})
        
    return pd.DataFrame(filas)

def generar_malla_abordaje_avanzada(inicio, fin, df_personal, config_flotantes, req_t1, req_t2, req_f, rotacion_descanso, rotacion_turnos, activar_finde_largo=False, max_descansos=6, dias_permitidos=None):
    filas = []
    turno_actual = {}
    dias_en_turno = {}
    ayer_fue_descanso = {}
    
    debe_compensado = {} 
    dias_consecutivos = {} 
    cancelados_mes = {}    
    
    if not dias_permitidos: dias_permitidos = DIAS_ES
    current_month = inicio.month
    
    for idx, row in df_personal.iterrows():
        nombre = row["Nombre"]
        turno_actual[nombre] = "T1" if idx % 2 == 0 else "T2"
        dias_en_turno[nombre] = 0
        ayer_fue_descanso[nombre] = False
        debe_compensado[nombre] = False 
        dias_consecutivos[nombre] = 0
        cancelados_mes[nombre] = 0

    for fecha in pd.date_range(inicio, fin):
        if fecha.month != current_month:
            current_month = fecha.month
            for n in cancelados_mes: cancelados_mes[n] = 0

        dia_n = DIAS_ES[fecha.weekday()]
        fecha_str = fecha.strftime('%Y-%m-%d')
        mes_str = fecha.strftime('%Y-%m') 
        week = fecha.isocalendar()[1] 
        delta_meses = (fecha.year - inicio.year) * 12 + (fecha.month - inicio.month)
        desp_desc = delta_meses if rotacion_descanso == "Mensual" else (delta_meses // 3 if rotacion_descanso == "Trimestral" else 0)
        
        asig_hoy = {}
        descansos_teoricos = []
        activos_teoricos = []
        inmunes = set() 
        descanso_real_del_mes = {} 
        
        for _, p in df_personal.iterrows():
            nombre = p["Nombre"]
            descanso_base = p["Descanso_Base"]
            es_descanso = False
            dia_asignado_actual = "Flotante"
            
            if dias_consecutivos[nombre] >= 6:
                es_descanso = True
                inmunes.add(nombre)
            
            if p["Rol"] == "Flotante":
                dia_descanso_f = config_flotantes["dia_base"]
                if config_flotantes["rotacion"] != "Fijo":
                    if dia_descanso_f in dias_permitidos:
                        idx_f = dias_permitidos.index(dia_descanso_f)
                        dia_descanso_f = dias_permitidos[(idx_f + desp_desc) % len(dias_permitidos)]
                    else:
                        idx_f = DIAS_ES.index(dia_descanso_f)
                        dia_descanso_f = DIAS_ES[(idx_f + desp_desc) % 7]
                    
                dia_asignado_actual = dia_descanso_f
                idx_ref = dias_permitidos.index(dia_descanso_f) if dia_descanso_f in dias_permitidos else 0
                es_finde_largo = activar_finde_largo and dia_n in ["Sábado", "Domingo"] and (week + idx_ref) % 5 == 0
                
                if dia_descanso_f == dia_n or es_finde_largo: es_descanso = True
            else:
                if descanso_base in dias_permitidos:
                    idx_desc = dias_permitidos.index(descanso_base)
                    dia_calculado = dias_permitidos[(idx_desc + desp_desc) % len(dias_permitidos)]
                elif descanso_base in DIAS_ES: 
                    idx_desc = DIAS_ES.index(descanso_base)
                    dia_calculado = DIAS_ES[(idx_desc + desp_desc) % 7]
                else:
                    idx_desc = 0
                    dia_calculado = "Domingo"
                    
                dia_asignado_actual = dia_calculado
                es_finde_largo = activar_finde_largo and dia_n in ["Sábado", "Domingo"] and (week + idx_desc) % 5 == 0
                if dia_calculado == dia_n or es_finde_largo: es_descanso = True
                    
            descanso_real_del_mes[nombre] = dia_asignado_actual
            
            if es_descanso: 
                descansos_teoricos.append(nombre)
                if p["Rol"] == "Flotante" and config_flotantes.get("proteger", False):
                    inmunes.add(nombre)
            elif nombre not in inmunes: 
                activos_teoricos.append(nombre)

        flotantes_nombres = df_personal[df_personal["Rol"] == "Flotante"]["Nombre"].tolist()
        regulares_nombres = df_personal[df_personal["Rol"] == "Regular"]["Nombre"].tolist()

        act_f = [n for n in activos_teoricos if n in flotantes_nombres]
        desc_f = [n for n in descansos_teoricos if n in flotantes_nombres]
        act_r = [n for n in activos_teoricos if n in regulares_nombres]
        desc_r = [n for n in descansos_teoricos if n in regulares_nombres]

        def reclutar_personal(activos_list, descansos_list, requerimiento):
            disponibles = [n for n in descansos_list if n not in inmunes]
            disponibles.sort(key=lambda x: (cancelados_mes[x], dias_consecutivos[x]))
            
            while len(activos_list) < requerimiento and disponibles:
                drafted = disponibles.pop(0)
                descansos_list.remove(drafted)
                activos_list.append(drafted)
                if dia_n == descanso_real_del_mes[drafted]:
                    debe_compensado[drafted] = True
                    cancelados_mes[drafted] += 1

        while (len(desc_f) + len(desc_r)) > max_descansos:
            disp_f = [n for n in desc_f if n not in inmunes]
            disp_r = [n for n in desc_r if n not in inmunes]
            disp_total = disp_f + disp_r
            
            if not disp_total: break 
            
            disp_total.sort(key=lambda x: (cancelados_mes[x], dias_consecutivos[x]))
            drafted = disp_total[0]
            
            if drafted in desc_f:
                desc_f.remove(drafted)
                act_f.append(drafted)
            else:
                desc_r.remove(drafted)
                act_r.append(drafted)
                
            if dia_n == descanso_real_del_mes[drafted]:
                debe_compensado[drafted] = True
                cancelados_mes[drafted] += 1

        reclutar_personal(act_f, desc_f, req_f)
            
        while len(act_f) > req_f and (len(desc_f) + len(desc_r)) < max_descansos:
            con_deuda = sorted([n for n in act_f if debe_compensado[n]], key=lambda x: dias_consecutivos[x], reverse=True)
            if not con_deuda: break
            beneficiado = con_deuda[0]
            act_f.remove(beneficiado)
            desc_f.append(beneficiado) 
            asig_hoy[beneficiado] = "COMPENSADO"
            debe_compensado[beneficiado] = False

        for n in act_f: asig_hoy[n] = "FLOTANTE"
        for n in desc_f: 
            if n not in asig_hoy: asig_hoy[n] = "DESCANSO"

        req_reg = req_t1 + req_t2
        reclutar_personal(act_r, desc_r, req_reg)

        while len(act_r) > req_reg and (len(desc_f) + len(desc_r)) < max_descansos:
            con_deuda = sorted([n for n in act_r if debe_compensado[n]], key=lambda x: dias_consecutivos[x], reverse=True)
            if not con_deuda: break
            beneficiado = con_deuda[0]
            act_r.remove(beneficiado)
            desc_r.append(beneficiado) 
            asig_hoy[beneficiado] = "COMPENSADO"
            debe_compensado[beneficiado] = False

        for n in desc_r: 
            if n not in asig_hoy: asig_hoy[n] = "DESCANSO"

        faltan_t1 = req_t1
        faltan_t2 = req_t2
        flexibles = []
        
        for p in act_r:
            t_previo = turno_actual[p]
            if not ayer_fue_descanso[p] and 0 < dias_en_turno[p] < 4:
                asig_hoy[p] = t_previo
                if t_previo == "T1": faltan_t1 -= 1
                else: faltan_t2 -= 1
            elif t_previo == "T2" and not ayer_fue_descanso[p]:
                asig_hoy[p] = "T2"
                faltan_t2 -= 1
            else:
                flexibles.append(p)
                
        for p in flexibles:
            t_previo = turno_actual[p]
            t_deseado = "T2" if (ayer_fue_descanso[p] and t_previo == "T1") or not ayer_fue_descanso[p] else "T1"
                
            if t_deseado == "T1" and faltan_t1 > 0: asig_hoy[p] = "T1"; faltan_t1 -= 1
            elif t_deseado == "T2" and faltan_t2 > 0: asig_hoy[p] = "T2"; faltan_t2 -= 1
            else:
                if faltan_t1 > 0: asig_hoy[p] = "T1"; faltan_t1 -= 1
                elif faltan_t2 > 0: asig_hoy[p] = "T2"; faltan_t2 -= 1
                else: asig_hoy[p] = t_previo

        for _, p in df_personal.iterrows():
            nombre = p["Nombre"]
            t_final = asig_hoy.get(nombre, "DESCANSO")
            
            if "ajustes_manuales_abo" in st.session_state and (nombre, fecha_str) in st.session_state.ajustes_manuales_abo:
                t_final = st.session_state.ajustes_manuales_abo[(nombre, fecha_str)]
            
            if t_final in ["DESCANSO", "COMPENSADO"]:
                ayer_fue_descanso[nombre] = True
                dias_en_turno[nombre] = 0
                dias_consecutivos[nombre] = 0 
            else:
                dias_consecutivos[nombre] += 1 
                if turno_actual[nombre] == t_final: dias_en_turno[nombre] += 1
                else: dias_en_turno[nombre] = 1
                turno_actual[nombre] = t_final
                ayer_fue_descanso[nombre] = False

            filas.append({"Fecha": fecha, "Mes": mes_str, "Descanso_Base": p["Descanso_Base"], "Descanso_Actual": descanso_real_del_mes[nombre], "Nombre": nombre, "Turno": t_final})
            
    return pd.DataFrame(filas)

def style_malla_abordaje(df_pivot):
    styles = pd.DataFrame('', index=df_pivot.index, columns=df_pivot.columns)
    color_map = {"T1": "#D6EAF8", "T2": "#D5F5E3", "FLOTANTE": "#E8DAEF", "DESCANSO": "#1B2631", "COMPENSADO": "#2E4053"}
    for col in df_pivot.columns:
        es_fin_semana = "🏖️" in str(col)
        es_festivo = "🇨🇴" in str(col)
        
        for idx in df_pivot.index:
            val = str(df_pivot.at[idx, col]).strip()
            
            if val == "": 
                bg = "#FFFFFF"; txt = "#FFFFFF"; border = "none"
            else:
                bg = color_map.get(val, "#1B2631") if val in color_map else "#FFFFFF"
                if "✅ OK" in val: bg = "#2ECC71"; txt = "white"
                elif "❌ FALTA" in val: bg = "#E74C3C"; txt = "white"
                elif "🛌" in val: bg = "#F5B041"; txt = "#17202A"
                else: txt = "white" if val in ["DESCANSO", "COMPENSADO"] else "#17202A"
                
                border = "1.5px solid #7F8C8D" if es_fin_semana else "0.5px solid #D5DBDB"
                if es_festivo: border = "2px solid #E67E22" 

            styles.at[idx, col] = f'background-color: {bg}; color: {txt}; font-weight: 700; border: {border};'
    return df_pivot.style.apply(lambda _: styles, axis=None)

def calcular_metricas_abordaje(turno):
    if turno == "T1": return "04:30", "13:30", 8.0, 0.0, 1.5 
    if turno == "T2": return "13:30", "22:30", 8.0, 0.0, 1.5 
    if turno == "FLOTANTE": return "08:00", "17:00", 8.0, 0.0, 0.0 
    return "OFF", "OFF", 0.0, 0.0, 0.0 

def generar_reporte_abordaje(df_final):
    filas = []
    df_final['Fecha'] = pd.to_datetime(df_final['Fecha'])
    for _, row in df_final.iterrows():
        fecha_dt = row['Fecha']
        turno = row['Turno']
        ini, fin, h_prog, h_extra, h_noc = calcular_metricas_abordaje(turno)
        filas.append({
            "Fecha": fecha_dt.strftime('%Y-%m-%d'), "Nombre": row['Nombre'], "Descanso Actual": row['Descanso_Actual'], "Turno": turno,
            "Hora inicio": ini, "Hora fin": fin, "Horas Programadas": h_prog, "Horas Extras": h_extra,
            "Recargos Nocturnos": h_noc, "Mes": fecha_dt.strftime('%Y-%m'), "Semana": fecha_dt.isocalendar()[1]
        })
    return pd.DataFrame(filas)

# 🟢 MODIFICADA PARA PERMITIR QUE FLOTANTE REQ = 0 EN SU DÍA DE DESCANSO
def verificar_alarmas_abordaje(df_final, req_t1, req_t2, req_f, activar_finde_largo, dias_permitidos):
    df_plano = df_final.sort_values(by=["Nombre", "Fecha"])
    alertas = []
    
    for sujeto, group in df_plano.groupby("Nombre"):
        lista_turnos = group["Turno"].tolist()
        lista_fechas = group["Fecha"].tolist()
        for i in range(1, len(lista_turnos)):
            if lista_turnos[i-1] == "T2" and lista_turnos[i] == "T1":
                alertas.append({
                    "Mensaje": f"🚨 **Transición Crítica Ilegal (T2 -> T1)** para **{sujeto}** el día {lista_fechas[i].strftime('%Y-%m-%d')}.",
                    "Sujeto": sujeto,
                    "Fecha": lista_fechas[i].strftime('%Y-%m-%d')
                })
                
    df_plano["Fecha"] = pd.to_datetime(df_plano["Fecha"])
    cob = df_plano.groupby(["Fecha", "Turno"]).size().unstack(fill_value=0)
    for c in ["T1", "T2", "FLOTANTE"]:
        if c not in cob.columns: cob[c] = 0
        
    for d_f in cob.index:
        dia_n = DIAS_ES[d_f.weekday()]
        week = d_f.isocalendar()[1]
        mes_str_col = d_f.strftime('%Y-%m')
        
        # 🟢 Evaluar si HOY es el día de descanso oficial de los flotantes
        flotantes_df = df_plano[(df_plano['Descanso_Base'] == 'Flotante') & (df_plano['Mes'] == mes_str_col)]
        req_f_hoy = req_f
        if not flotantes_df.empty:
            dia_descanso_f = flotantes_df.iloc[0]['Descanso_Actual']
            idx_ref = dias_permitidos.index(dia_descanso_f) if dia_descanso_f in dias_permitidos else 0
            es_finde_largo = activar_finde_largo and dia_n in ["Sábado", "Domingo"] and (week + idx_ref) % 5 == 0
            
            # Si a los flotantes les toca descansar hoy, el requerimiento operativo de flotantes es CERO
            if dia_n == dia_descanso_f or es_finde_largo:
                req_f_hoy = 0

        faltan = []
        if cob.at[d_f, "T1"] < req_t1: faltan.append(f"T1 ({cob.at[d_f, 'T1']}/{req_t1})")
        if cob.at[d_f, "T2"] < req_t2: faltan.append(f"T2 ({cob.at[d_f, 'T2']}/{req_t2})")
        if cob.at[d_f, "FLOTANTE"] < req_f_hoy: faltan.append(f"FLOTANTES ({cob.at[d_f, 'FLOTANTE']}/{req_f_hoy})")
        
        if faltan:
            alertas.append({
                "Mensaje": f"⚠️ **Falta Cobertura Operativa el {d_f.strftime('%Y-%m-%d')}:** Hay déficit en {', '.join(faltan)}.",
                "Sujeto": None,
                "Fecha": d_f.strftime('%Y-%m-%d')
            })
            
    return alertas

@st.dialog("🛠️ Gestor de Turno y Contexto Operativo (Abordaje)", width="large")
def popup_forzar_ajuste_fecha_abo(fecha_solicitada, opciones_sujetos, sujeto_predef=None, df_context=pd.DataFrame()):
    st.markdown(f"### 📅 Fecha de Operación a corregir: `{fecha_solicitada}`")

    if not df_context.empty:
        st.markdown("##### 🔎 Contexto de la Operación")
        fecha_dt = pd.to_datetime(fecha_solicitada)
        f_ini = fecha_dt - timedelta(days=3)
        f_fin = fecha_dt + timedelta(days=3)
        
        mask = (df_context['Fecha'] >= f_ini) & (df_context['Fecha'] <= f_fin)
        df_filtro = df_context[mask].copy()
        
        if not df_filtro.empty:
            pivot_ctx = df_filtro.pivot_table(index=["Descanso_Actual", "Nombre"], columns="Fecha", values="Turno", aggfunc='first').fillna("DESCANSO")
            pivot_ctx.columns = [p.strftime('%Y-%m-%d') for p in pivot_ctx.columns]
            st.dataframe(style_malla_abordaje(pivot_ctx), use_container_width=True)
        st.write("---")

    idx_def = opciones_sujetos.index(sujeto_predef) if sujeto_predef in opciones_sujetos else 0
    
    c1, c2 = st.columns(2)
    sujeto_sel = c1.selectbox("🎯 Empleado a Modificar:", opciones_sujetos, index=idx_def)
    nuevo_turno = c2.selectbox("🆕 Turno Destino Asignado:", ["T1", "T2", "FLOTANTE", "DESCANSO", "COMPENSADO"], index=0)
    
    if st.button("🔄 Aplicar a Previsualización", use_container_width=True):
        st.session_state.ajustes_manuales_abo[(sujeto_sel, fecha_solicitada)] = nuevo_turno
        st.success("¡Turno validado en memoria!")
        st.rerun()

def pantalla_abordaje():
    if "ajustes_manuales_abo" not in st.session_state: st.session_state.ajustes_manuales_abo = {}
    st.markdown("## 🚀 Panel de Programación - Abordaje Operativo")

    # =========================================================
    # 1. GESTIÓN DE PLANTA Y ASIGNACIÓN DE DESCANSOS
    # =========================================================
    st.subheader("1. Estructura de Personal y Descansos")
    c1, c2 = st.columns(2)
    total_p = c1.number_input("Total Planta (Regulares + Flotantes)", 10, 100, 28)
    num_flotantes = c2.number_input("Cantidad de Flotantes", 0, 20, 4)
    
    st.markdown("Selecciona en qué días quieres que el personal regular rote su descanso. El sistema repartirá la planta de forma equitativa:")
    dias_permitidos = st.multiselect("Días de Descanso a repartir (Regulares):", DIAS_ES, default=["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"])

    if st.button("🔄 Generar / Reiniciar Lista de Personal Base"):
        st.session_state.df_personal_abo = crear_personal_abordaje_dinamico(total_p, num_flotantes, dias_permitidos)
        st.success("Lista generada. Puedes ajustar los descansos base manualmente a continuación.")

    if "df_personal_abo" not in st.session_state:
        st.session_state.df_personal_abo = crear_personal_abordaje_dinamico(total_p, num_flotantes, dias_permitidos)

    st.markdown("Revisa o edita individualmente el día de descanso base de cada persona:")
    df_pers_editado = st.data_editor(
        st.session_state.df_personal_abo,
        use_container_width=True,
        hide_index=True
    )

    # =========================================================
    # 2. REQUERIMIENTOS Y ROTACIONES
    # =========================================================
    st.write("---")
    st.subheader("2. Parámetros de Operación y Rotación")
    
    c_req1, c_req2, c_req3, c_req4 = st.columns(4)
    req_t1 = c_req1.number_input("Cobertura Requerida T1", 1, 50, 11)
    req_t2 = c_req2.number_input("Cobertura Requerida T2", 1, 50, 11)
    req_f = c_req3.number_input("Cobertura Flotantes", 0, 50, 4)
    max_desc = c_req4.number_input("Límite Max. Descansos/Día", 1, 30, 6)

    c_i, c_f, c_v = st.columns(3)
    inicio = c_i.date_input("Inicio Planificación", date(2026, 7, 1), key="i_abo")
    fin = c_f.date_input("Fin Planificación", date(2026, 12, 31), key="f_abo")
    valor_hora = c_v.number_input("💰 Valor Hora Ordinaria ($):", min_value=0, value=6500, step=500, key="vh_abo")

    c_rot1, c_rot2 = st.columns(2)
    rotacion_turnos = c_rot1.selectbox("🔄 Rotación de Turnos (T1/T2):", ["Semanal", "Quincenal", "Mensual"], help="Se priorizan bloques para evitar fatiga.")
    rotacion_descanso = c_rot2.selectbox("🔄 Rotación de Descanso (Regulares):", ["Fijo sin rotación", "Mensual", "Trimestral", "Semestral"])

    st.markdown("**🔸 Personal Flotante:**")
    c_flo1, c_flo2 = st.columns(2)
    rot_flotantes = c_flo1.radio("Descanso de Flotantes:", ["Fijo", "Rotativo"], horizontal=True)
    dia_base_flotantes = c_flo2.selectbox("Día de Descanso Base (Flotantes):", DIAS_ES, index=6)
    
    proteger_f = st.checkbox("🛡️ Blindar descanso de Flotantes (Evita que el sistema los obligue a trabajar en su día libre si falta cobertura)", value=True)
    config_flotantes = {"rotacion": rot_flotantes, "dia_base": dia_base_flotantes, "proteger": proteger_f}

    # =========================================================
    # 3. GENERACIÓN Y GUARDADO DE MALLA
    # =========================================================
    st.write("---")
    activar_finde_largo = st.toggle("🎉 Otorgar Fin de Semana Libre (Sáb y Dom) cada 5 semanas", value=False)
    
    if st.button("👁️ PREVISUALIZAR MALLA (Sin Guardar)"):
        st.session_state.m_base_abo = generar_malla_abordaje_avanzada(
            inicio, fin, df_pers_editado, config_flotantes, 
            req_t1, req_t2, req_f, rotacion_descanso, rotacion_turnos, activar_finde_largo, max_desc, dias_permitidos
        )
        
    if 'm_base_abo' in st.session_state and not st.session_state.m_base_abo.empty:
        df_final = generar_malla_abordaje_avanzada(
            inicio, fin, df_pers_editado, config_flotantes, 
            req_t1, req_t2, req_f, rotacion_descanso, rotacion_turnos, activar_finde_largo, max_desc, dias_permitidos
        )
        st.session_state.m_base_abo = df_final
        
        st.write("---")
        st.subheader("💾 Guardar Malla y Notificar")
        ya_existe = verificar_existencia_malla("cable_malla_abordaje", inicio, fin)
        
        c_b1, c_b2 = st.columns(2)
        with c_b1:
            if st.button("⚠️ Confirmar y Actualizar Histórico" if ya_existe else "💾 Guardar Malla Definitiva"):
                if guardar_malla_historico(df_final, "cable_malla_abordaje", inicio, fin):
                    guardar_malla_historico(generar_reporte_abordaje(df_final), "cable_nomina_abordaje", inicio, fin)
                    st.success("🎉 ¡Malla y Nómina de Abordaje guardados exitosamente!")
        
        with c_b2:
            with st.popover("📩 Enviar Malla por Correo"):
                remitente = st.text_input("Tu Correo Remitente", key="rem_abo")
                password = st.text_input("Contraseña de Aplicación", type="password", key="pass_abo")
                if st.button("🚀 Confirmar y Enviar", key="btn_env_abo"):
                    if remitente and password:
                        with st.spinner("Enviando correos..."):
                            df_rep = generar_reporte_abordaje(df_final)
                            exito, msj = enviar_correos_masivos(df_rep, cargar_empleados_bd(), inicio.strftime('%B %Y'), remitente, password)
                            if exito: st.success(msj)
                            else: st.error(msj)
                    else: st.warning("Completa credenciales.")
                
        # =========================================================
        # 4. UI: PIVOT, FORZADO DE TURNOS Y DASHBOARD
        # =========================================================
        st.write("---")
        st.subheader("👤 Malla de Turnos Detallada por Mes y Persona")
        
        meses_disponibles = sorted(df_final['Mes'].unique())
        opciones_mes = ["Todos los meses"] + meses_disponibles
        mes_seleccionado = st.selectbox("📅 Filtrar Malla por Mes:", opciones_mes)

        if mes_seleccionado != "Todos los meses":
            df_mostrar = df_final[df_final['Mes'] == mes_seleccionado].copy()
            indice_pivot = ["Descanso_Actual", "Nombre"]
        else:
            df_mostrar = df_final.copy()
            indice_pivot = ["Descanso_Base", "Nombre"]

        pivot_persona = df_mostrar.pivot(index=indice_pivot, columns="Fecha", values="Turno").fillna("")
        
        cob = df_mostrar.groupby(["Fecha", "Turno"]).size().unstack(fill_value=0)
        for c in ["T1", "T2", "FLOTANTE", "DESCANSO", "COMPENSADO"]:
            if c not in cob.columns: cob[c] = 0
            
        fila_semaforo = {}
        fila_descansos = {}
        for col_fecha in pivot_persona.columns:
            col_dt = pd.to_datetime(col_fecha)
            dia_n = DIAS_ES[col_dt.weekday()]
            week = col_dt.isocalendar()[1]
            mes_str_col = col_dt.strftime('%Y-%m')

            if col_dt in cob.index:
                t1_val = cob.at[col_dt, "T1"]
                t2_val = cob.at[col_dt, "T2"]
                f_val = cob.at[col_dt, "FLOTANTE"]
                desc_val = cob.at[col_dt, "DESCANSO"] + cob.at[col_dt, "COMPENSADO"]
                
                # 🟢 Calcular el requerimiento dinámico para Flotantes
                flotantes_df = df_mostrar[(df_mostrar['Descanso_Base'] == 'Flotante') & (df_mostrar['Mes'] == mes_str_col)]
                req_f_hoy = req_f
                if not flotantes_df.empty:
                    dia_descanso_f = flotantes_df.iloc[0]['Descanso_Actual']
                    idx_ref = dias_permitidos.index(dia_descanso_f) if dia_descanso_f in dias_permitidos else 0
                    es_finde_largo = activar_finde_largo and dia_n in ["Sábado", "Domingo"] and (week + idx_ref) % 5 == 0
                    if dia_n == dia_descanso_f or es_finde_largo:
                        req_f_hoy = 0
                
                status = "✅ OK" if (t1_val >= req_t1 and t2_val >= req_t2 and f_val >= req_f_hoy) else "❌ FALTA TURNO"
                fila_semaforo[col_fecha] = status
                fila_descansos[col_fecha] = f"🛌 {desc_val} Descansos"
            else:
                fila_semaforo[col_fecha] = "❌ FALTA TURNO"
                fila_descansos[col_fecha] = "🛌 0 Descansos"

        df_sem_row = pd.DataFrame([fila_semaforo], index=[("🔍 AUDITORÍA", "COBERTURA 24/7")])
        df_desc_row = pd.DataFrame([fila_descansos], index=[("🔍 AUDITORÍA", "TOTAL DESCANSOS")])
        
        pivot_completo = pd.concat([pivot_persona, df_sem_row, df_desc_row])
        
        DIAS_CORTOS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
        nuevas_cols = []
        for col in pivot_completo.columns:
            if isinstance(col, (datetime, date, pd.Timestamp)):
                dt = pd.to_datetime(col)
                dia_str = DIAS_CORTOS[dt.weekday()]
                fecha_str = dt.strftime('%d-%b')
                
                if dt in festivos_co: nuevas_cols.append(f"{fecha_str} ({dia_str}) 🇨🇴")
                elif dt.weekday() in [5, 6]: nuevas_cols.append(f"{fecha_str} ({dia_str}) 🏖️")
                else: nuevas_cols.append(f"{fecha_str} ({dia_str})")
            else:
                nuevas_cols.append(str(col))
        
        pivot_completo.columns = nuevas_cols
        
        st.markdown(generar_html_imprimible(pivot_persona, f"Malla Abordaje - {mes_seleccionado}"), unsafe_allow_html=True)
        st.dataframe(style_malla_abordaje(pivot_completo), use_container_width=True)
        
        st.write("---")
        with st.expander("🔍 Forzar cambio libre en cualquier fecha de la Malla"):
            c_f1, c_f2 = st.columns(2)
            fechas_unicas = sorted([d.strftime('%Y-%m-%d') for d in pd.to_datetime(df_final['Fecha'].unique())])
            f_libre_sel = c_f1.selectbox("Seleccione la Fecha:", fechas_unicas, key="f_libre_dropdown_abo")
            if c_f2.button("⚙️ Abrir Gestor de Turno", use_container_width=True):
                popup_forzar_ajuste_fecha_abo(f_libre_sel, sorted(list(df_final["Nombre"].unique())), df_context=df_final)

        st.write("---")
        t_dash, t_fatiga, t_nomina, t_hist, t_audit = st.tabs(["📊 Dashboard de Costos", "⚠️ Alarmas (Fatiga y Cobertura)", "📋 Reporte Nómina", "🗄️ Histórico BD", "🔎 Auditoría Personal"])
        rep_maestro_abo = generar_reporte_abordaje(df_final)
        
        with t_dash:
            if not rep_maestro_abo.empty:
                total_horas = rep_maestro_abo['Horas Programadas'].sum()
                total_extras = rep_maestro_abo['Horas Extras'].sum()
                
                costo_base = total_horas * valor_hora
                costo_extras = total_extras * (valor_hora * 1.25)
                
                c_m1, c_m2, c_m3 = st.columns(3)
                c_m1.metric("💰 Costo Proyectado Base", f"${costo_base:,.0f} COP")
                c_m2.metric("📈 Costo Proyectado Extras", f"${costo_extras:,.0f} COP")
                c_m3.metric("⏱️ Total Horas Operativas", f"{total_horas:,.0f} h")
                
                st.markdown("#### Proyección de Costos por Empleado")
                rep_maestro_abo['Costo Total ($)'] = (rep_maestro_abo['Horas Programadas'] * valor_hora) + (rep_maestro_abo['Horas Extras'] * valor_hora * 1.25)
                st.bar_chart(rep_maestro_abo.groupby("Nombre")['Costo Total ($)'].sum().reset_index(), x="Nombre", y="Costo Total ($)")

        with t_fatiga:
            # 🟢 PASAMOS VARIABLES ADICIONALES PARA LA LÓGICA DE DÍAS PERMITIDOS Y FINDE LARGO
            lista_alertas = verificar_alarmas_abordaje(df_final, req_t1, req_t2, req_f, activar_finde_largo, dias_permitidos)
            if lista_alertas:
                for idx_al, al in enumerate(lista_alertas):
                    c_al1, c_al2 = st.columns([5, 1])
                    c_al1.warning(al["Mensaje"])
                    if c_al2.button("🛠️ Corregir", key=f"btn_corr_fatiga_abo_{idx_al}"):
                        popup_forzar_ajuste_fecha_abo(
                            al["Fecha"], 
                            sorted(list(df_final["Nombre"].unique())), 
                            sujeto_predef=al["Sujeto"], 
                            df_context=df_final
                        )
            else: st.success("✅ Estructura perfecta. Libre de alertas de fatiga y con 100% de cobertura.")
            
        with t_nomina:
            st.dataframe(rep_maestro_abo, use_container_width=True)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer: 
                rep_maestro_abo.to_excel(writer, sheet_name="Detalle_Abordaje", index=False)
            st.download_button("📥 Descargar Reporte Nómina", output.getvalue(), f"Nomina_Abordaje_{date.today()}.xlsx")
            
        with t_hist:
            try:
                df_hist_full = pd.read_sql("SELECT * FROM cable_malla_abordaje", engine)
                df_hist_full['Fecha_str'] = pd.to_datetime(df_hist_full['Fecha']).dt.strftime('%Y-%m-%d')
                c_h1, c_h2 = st.columns(2)
                h_ini = c_h1.date_input("Desde:", inicio, key="h_ini_a")
                h_fin = c_h2.date_input("Hasta:", fin, key="h_fin_a")
                df_filtrado = df_hist_full[(df_hist_full['Fecha_str'] >= h_ini.strftime('%Y-%m-%d')) & (df_hist_full['Fecha_str'] <= h_fin.strftime('%Y-%m-%d'))].drop(columns=['Fecha_str'])
                if not df_filtrado.empty:
                    pivot_h = df_filtrado.pivot(index="Nombre", columns="Fecha", values="Turno").fillna("DESCANSO")
                    pivot_h.columns = [p.strftime('%Y-%m-%d') for p in pivot_h.columns]
                    st.dataframe(style_malla_abordaje(pivot_h), use_container_width=True)
            except: st.info("BD vacía.")
            
        with t_audit:
            st.markdown("#### 🔎 Auditoría de Turnos y Descansos por Mes")
            if not df_final.empty:
                df_audit_per = df_final.copy()
                df_audit_per['Mes'] = pd.to_datetime(df_audit_per['Fecha']).dt.strftime('%Y-%m')
                
                audit_pivot = df_audit_per.pivot_table(
                    index=['Mes', 'Nombre'], 
                    columns='Turno', 
                    aggfunc='size', 
                    fill_value=0
                ).reset_index()
                
                for c in ["T1", "T2", "FLOTANTE", "DESCANSO", "COMPENSADO"]:
                    if c not in audit_pivot.columns: audit_pivot[c] = 0
                        
                cols_order = ['Mes', 'Nombre', 'T1', 'T2', 'FLOTANTE', 'DESCANSO', 'COMPENSADO']
                audit_pivot = audit_pivot[cols_order]
                
                st.dataframe(audit_pivot, use_container_width=True)
                
                output_audit = io.BytesIO()
                with pd.ExcelWriter(output_audit, engine='openpyxl') as writer: 
                    audit_pivot.to_excel(writer, sheet_name="Auditoria_Mensual", index=False)
                st.download_button("📥 Descargar Auditoría", output_audit.getvalue(), f"Auditoria_Mensual_Abordaje_{date.today()}.xlsx")
# =========================================================
# 9. MOTOR Y PANEL PARA OTROS CARGOS (ULTIMATE EDITION)
# =========================================================
def generar_malla_generica(inicio, fin, sujetos, turnos_nombres, req_turnos_lv, req_turnos_sd, descansos_iniciales, conceder_comp, tipo_ciclo, tipo_rotacion, accion_sobrante):
    filas = []
    deudas = {s: 0 for s in sujetos}

    for fecha in pd.date_range(inicio, fin):
        dia_n = DIAS_ES[fecha.weekday()]
        sem = fecha.isocalendar()[1]
        delta_meses = (fecha.year - inicio.year) * 12 + (fecha.month - inicio.month)
        fecha_str = fecha.strftime('%Y-%m-%d')
        is_weekend = fecha.weekday() >= 5

        if tipo_ciclo == "Mensual": desplazamiento = delta_meses
        elif tipo_ciclo == "Trimestral": desplazamiento = delta_meses // 3
        else: desplazamiento = 0
            
        if tipo_rotacion == "Semanal": delta_rot = sem
        elif tipo_rotacion == "Quincenal": delta_rot = sem // 2
        elif tipo_rotacion == "Mensual": delta_rot = delta_meses
        else: delta_rot = 0

        descansos_vivos = {}
        for s in sujetos:
            idx_inicial = DIAS_ES.index(descansos_iniciales[s])
            descansos_vivos[s] = DIAS_ES[(idx_inicial + desplazamiento) % len(DIAS_ES)]
            
        deseados = {}
        for idx_s, s in enumerate(sujetos):
            deseados[s] = turnos_nombres[(idx_s + delta_rot) % len(turnos_nombres)]

        asig_hoy = {}
        # 1. Asignar Descansos Base
        for s, d in descansos_vivos.items():
            if d == dia_n: asig_hoy[s] = "DESCANSO"

        # 2. Otorgar Compensatorios (Solo de Lunes a Viernes)
        if not is_weekend and conceder_comp:
            s_con_deuda = sorted([s for s, d in deudas.items() if d > 0 and s not in asig_hoy], key=lambda x: deudas[x], reverse=True)
            for s in s_con_deuda:
                asig_hoy[s] = "COMPENSADO"
                deudas[s] -= 1

        activos = [s for s in sujetos if s not in asig_hoy]

        # 3. Llenar cuotas diarias (Rescate Operativo)
        turnos_asignados_hoy = {}
        for t_name in turnos_nombres:
            req = req_turnos_sd[t_name] if is_weekend else req_turnos_lv[t_name]
            pool = [s for s in activos if deseados[s] == t_name]
            asignados = 0

            # 3a. Llenar con el pool ideal
            for s in list(pool):
                if asignados < req:
                    turnos_asignados_hoy[s] = t_name
                    activos.remove(s)
                    asignados += 1

            # 3b. Llenar con disponibles
            while asignados < req and activos:
                s = activos.pop(0)
                turnos_asignados_hoy[s] = t_name
                asignados += 1
                
            # 3c. RESCATE DE EMERGENCIA
            if asignados < req:
                compensados_hoy = [s for s, t in asig_hoy.items() if t == "COMPENSADO"]
                while asignados < req and compensados_hoy:
                    s = compensados_hoy.pop(0)
                    del asig_hoy[s]
                    deudas[s] += 1 
                    turnos_asignados_hoy[s] = t_name
                    asignados += 1
            
            # 3d. RESCATE EXTREMO
            if asignados < req:
                descansos_hoy = [s for s, t in asig_hoy.items() if t == "DESCANSO"]
                while asignados < req and descansos_hoy:
                    s = descansos_hoy.pop(0)
                    del asig_hoy[s]
                    deudas[s] += 1
                    turnos_asignados_hoy[s] = t_name
                    asignados += 1
                    
            # 3e. ALERTA DE HUECO OPERATIVO PENDIENTE CUBRIR
            if asignados < req:
                faltan = req - asignados
                filas.append({"Fecha": fecha, "Sujeto": f"⚠️ PENDIENTE CUBRIR (Faltan {faltan})", "Turno": t_name})

        # 4. Asignar excedentes
        for s in activos:
            if accion_sobrante == "Asignar a DESCANSO": turnos_asignados_hoy[s] = "DESCANSO"
            else: turnos_asignados_hoy[s] = "SOPORTE"

        # 5. Generación de Deuda Dominical
        if dia_n == "Domingo" and conceder_comp:
            for s in sujetos:
                if s in turnos_asignados_hoy and turnos_asignados_hoy[s] not in ["DESCANSO", "COMPENSADO"]:
                    deudas[s] += 1

        for s, t in turnos_asignados_hoy.items(): asig_hoy[s] = t

        # 6. Volcado a Filas y Ajustes Manuales
        for s in sujetos:
            turno_final = asig_hoy.get(s, "DESCANSO")
            if "ajustes_manuales_otros" in st.session_state and (s, fecha_str) in st.session_state.ajustes_manuales_otros:
                turno_final = st.session_state.ajustes_manuales_otros[(s, fecha_str)]
            filas.append({"Fecha": fecha, "Sujeto": s, "Turno": turno_final})

    return pd.DataFrame(filas)

def generar_reporte_generico(df_final, config_h, df_emp_cargo, modo_prog, descansos_iniciales):
    filas_reporte = []
    # Ignoramos la fila de "Pendiente" para la nómina
    df_reales = df_final[~df_final['Sujeto'].str.contains("PENDIENTE", na=False)].copy()
    df_reales['Fecha'] = pd.to_datetime(df_reales['Fecha'])
    
    for _, emp in df_emp_cargo.iterrows():
        nombre = emp['Nombre']
        grupo = emp['GrupoAsignado']
        cargo = emp['Cargo']
        cedula = emp.get('Cedula', 'N/A')
        
        sujeto_busqueda = grupo if modo_prog == "Por Grupos (Se programa al grupo y los miembros heredan el turno)" else nombre
        malla_bloque = df_reales[df_reales['Sujeto'] == sujeto_busqueda]
        
        for _, m_fila in malla_bloque.iterrows():
            turno = m_fila['Turno']
            fecha_dt = m_fila['Fecha']
            fecha_str = fecha_dt.strftime('%Y-%m-%d')
            
            if "ajustes_manuales_otros" in st.session_state and (nombre, fecha_str) in st.session_state.ajustes_manuales_otros:
                turno = st.session_state.ajustes_manuales_otros[(nombre, fecha_str)]
                
            info_turno = config_h.get(turno, {"Inicio": "OFF", "Fin": "OFF", "Almuerzo": False})
            ini = info_turno.get("Inicio", "OFF")
            fin = info_turno.get("Fin", "OFF")
            descuenta_almuerzo = info_turno.get("Almuerzo", False)

            h_prog, h_extra, h_noc = calcular_metricas_reforma(ini, fin, fecha_dt)
            
            if descuenta_almuerzo and h_prog > 0:
                h_prog = max(0.0, h_prog - 1.0)
                h_extra = max(0.0, h_prog - 7.0)

            filas_reporte.append({
                "Fecha": fecha_str, "Cedula": cedula, "Nombre": nombre, "Grupo": grupo, "Cargo": cargo, 
                "Día Descanso Asignado": descansos_iniciales.get(sujeto_busqueda, "N/A"), "Turno realizado": turno, 
                "Hora inicio": ini, "Hora fin": fin, "Horas Programadas": h_prog, "Horas Extras": h_extra,
                "Recargos Nocturnos": h_noc, "Mes": fecha_dt.strftime('%B'), "Semana": fecha_dt.isocalendar()[1]
            })
    return pd.DataFrame(filas_reporte)

def verificar_alarmas_otros(df_final):
    df_reales = df_final[~df_final['Sujeto'].str.contains("PENDIENTE", na=False)].copy()
    df_plano = df_reales.sort_values(by=["Sujeto", "Fecha"])
    alertas = []
    for sujeto, group in df_plano.groupby("Sujeto"):
        lista_turnos = group["Turno"].tolist()
        lista_fechas = group["Fecha"].tolist()
        for i in range(1, len(lista_turnos)):
            t_ant = lista_turnos[i-1]
            t_act = lista_turnos[i]
            
            if t_ant == "Turno 2" and t_act == "Turno 1":
                alertas.append({"Mensaje": f"⚠️ **Transición Corta (Turno 2 -> Turno 1):** El empleado **{sujeto}** empalma muy rápido el día {lista_fechas[i].strftime('%Y-%m-%d')}."})
            elif t_ant in ["Turno 3", "Turno 4", "Turno 5"] and t_act in ["Turno 1", "Turno 2", "SOPORTE"]:
                alertas.append({"Mensaje": f"🚨 **Violación Descanso Circadiano ({t_ant} -> {t_act}):** El empleado **{sujeto}** pasa a turno de día sin descanso el {lista_fechas[i].strftime('%Y-%m-%d')}."})
    return alertas

@st.dialog("🛠️ Forzar Cambio de Turno (Otros Cargos)", width="small")
def popup_forzar_ajuste_fecha_otros(fecha_solicitada, opciones_sujetos, opciones_turnos):
    st.markdown(f"📅 **Fecha de Operación:** `{fecha_solicitada}`")
    sujeto_sel = st.selectbox("🎯 Seleccione el Empleado a Modificar:", opciones_sujetos)
    nuevo_turno = st.selectbox("🆕 Turno Destino Asignado:", opciones_turnos + ["DESCANSO", "COMPENSADO", "SOPORTE"], index=0)
    
    if st.button("🔄 Aplicar a Previsualización"):
        st.session_state.ajustes_manuales_otros[(sujeto_sel, fecha_solicitada)] = nuevo_turno
        st.success("¡Turno validado en memoria!")
        st.rerun()

def pantalla_otros_cargos():
    if "ajustes_manuales_otros" not in st.session_state: st.session_state.ajustes_manuales_otros = {}
    st.markdown("## 📦 Programación - Otras Áreas Operativas")
    st.info("Configura mallas detalladas de turnos con cuotas L-V y Fines de Semana independientes.")

    df_emp = cargar_empleados_bd()
    if df_emp.empty:
        st.warning("No hay personal registrado en la Base de Datos. Ve a la pestaña 'Personal' primero.")
        return

    cargos_core = ["Tecnico Master", "Tecnico A", "Tecnico B", "Personal de Abordaje", "Supervisor"]
    cargos_disponibles = [c for c in df_emp['Cargo'].unique() if c not in cargos_core]
    
    if not cargos_disponibles:
        st.warning("⚠️ No se encontraron cargos adicionales en tu base de datos.")
        cargos_disponibles = df_emp['Cargo'].unique().tolist() 

    c_cargo, c_turnos = st.columns(2)
    cargo_sel = c_cargo.selectbox("🎯 Selecciona el Cargo a Programar:", cargos_disponibles)
    num_turnos = c_turnos.number_input("Cantidad de Turnos (Rotativos):", 1, 10, 1)

    df_cargo = df_emp[df_emp['Cargo'] == cargo_sel]
    
    st.write("---")
    modo_prog = st.radio("🎯 Nivel de Programación:", ["Por Individuo (Cada persona tiene su rotación)", "Por Grupos (Se programa al grupo y los miembros heredan el turno)"])
    
    if modo_prog == "Por Grupos (Se programa al grupo y los miembros heredan el turno)":
        sujetos_a_programar = [g for g in df_cargo['GrupoAsignado'].unique() if g != "None" and str(g).strip() != ""]
        if not sujetos_a_programar:
            st.error(f"❌ No hay grupos asignados para el cargo '{cargo_sel}'. Ve a la pestaña 'Personal' y asígnales un Grupo.")
            return
    else:
        sujetos_a_programar = df_cargo['Nombre'].tolist()

    if not sujetos_a_programar:
        st.error(f"No hay sujetos a programar bajo el cargo '{cargo_sel}'.")
        return

    st.markdown(f"### ⚙️ Configurar Horarios y Cuotas para {cargo_sel}")
    st.caption(f"👥 Total de elementos a programar: **{len(sujetos_a_programar)}**")
    
    # 🌟 INPUT PARA DASHBOARDS
    valor_hora = st.number_input("💰 Valor Hora Ordinaria Proyectada ($):", min_value=0, value=6500, step=500, key="vh_ot")
    
    config_h = {}
    req_turnos_lv = {}
    req_turnos_sd = {}
    cols_t = st.columns(num_turnos)
    turnos_nombres = []
    
    for i in range(num_turnos):
        t_name = f"Turno {i+1}"
        turnos_nombres.append(t_name)
        with cols_t[i % len(cols_t)]:
            st.markdown(f"**{t_name}**")
            ini = st.time_input(f"Inicia {t_name}", time(8,0), key=f"ot_i_{i}", label_visibility="collapsed")
            fin = st.time_input(f"Fin {t_name}", time(17,0), key=f"ot_f_{i}", label_visibility="collapsed")
            
            c_req1, c_req2 = st.columns(2)
            req_lv = c_req1.number_input("Req L-V:", 0, 50, 1, key=f"ot_rlv_{i}")
            req_sd = c_req2.number_input("Req S-D:", 0, 50, 0, key=f"ot_rsd_{i}")
            
            almuerzo = st.checkbox("Descuenta 1h Almuerzo", value=True, key=f"alm_{i}")
            config_h[t_name] = {"Inicio": ini.strftime("%H:%M"), "Fin": fin.strftime("%H:%M"), "Almuerzo": almuerzo}
            req_turnos_lv[t_name] = req_lv
            req_turnos_sd[t_name] = req_sd
            
    st.write("---")
    st.markdown("**¿Qué hacer con el personal sobrante si la cuota es menor a la cantidad de empleados activos?**")
    accion_sobrante = st.radio("Acción para el excedente:", ["Asignar a turno SOPORTE (Horario de Oficina)", "Asignar a DESCANSO"], horizontal=True)

    if accion_sobrante == "Asignar a turno SOPORTE (Horario de Oficina)":
        c_sop1, c_sop2, c_sop3 = st.columns(3)
        sop_ini = c_sop1.time_input("Inicia SOPORTE", time(8,0))
        sop_fin = c_sop2.time_input("Fin SOPORTE", time(17,0))
        sop_alm = c_sop3.checkbox("SOPORTE descuenta almuerzo", value=True)
        config_h["SOPORTE"] = {"Inicio": sop_ini.strftime("%H:%M"), "Fin": sop_fin.strftime("%H:%M"), "Almuerzo": sop_alm}
    else:
        config_h["SOPORTE"] = {"Inicio": "OFF", "Fin": "OFF", "Almuerzo": False}
        
    config_h["DESCANSO"] = config_h["COMPENSADO"] = {"Inicio": "OFF", "Fin": "OFF", "Almuerzo": False}

    st.markdown("### 📅 Días de Descanso y Rotación")
    c_rot1, c_rot2, c_rot3 = st.columns(3)
    conceder_comp = c_rot1.checkbox("⚖️ Otorgar Compensatorios (Si trabajan Domingo)", value=True, key="comp_otros")
    tipo_ciclo = c_rot2.selectbox("🔄 Ciclo de Rotación Descanso:", ["Fijo sin rotación", "Mensual", "Trimestral"], key="ciclo_otros")
    tipo_rotacion = c_rot3.selectbox("🔄 Rotación de Turnos:", ["Semanal", "Quincenal", "Mensual", "Turno Fijo"], key="rot_turnos_otros")
    
    st.markdown("**Asigna el Día de Descanso Base individual:**")
    cols_d = st.columns(4)
    desc_data = {}
    for idx, sujeto in enumerate(sujetos_a_programar):
        desc_data[sujeto] = cols_d[idx % 4].selectbox(sujeto, DIAS_ES, index=6, key=f"desc_ot_{idx}")

    st.markdown("---")
    c_i, c_f = st.columns(2)
    inicio = c_i.date_input("Inicio Planificación", date(2026, 7, 1), key="i_ot")
    fin = c_f.date_input("Fin Planificación", date(2026, 12, 31), key="f_ot")

    total_req_lv = sum(req_turnos_lv.values())
    total_req_sd = sum(req_turnos_sd.values())
    
    if total_req_lv > len(sujetos_a_programar) or total_req_sd > len(sujetos_a_programar):
        st.warning(f"⚠️ **Nota de Rescate:** La cobertura requerida es mayor a la cantidad de empleados disponibles. El sistema cancelará descansos y generará compensatorios automáticamente.")
        
    if st.button(f"👁️ PREVISUALIZAR MALLA DE {cargo_sel.upper()}"):
        st.session_state.ajustes_manuales_otros = {}
        st.session_state.m_base_otros = generar_malla_generica(inicio, fin, sujetos_a_programar, turnos_nombres, req_turnos_lv, req_turnos_sd, desc_data, conceder_comp, tipo_ciclo, tipo_rotacion, accion_sobrante)

    if 'm_base_otros' in st.session_state and not st.session_state.m_base_otros.empty:
        df_final = generar_malla_generica(inicio, fin, sujetos_a_programar, turnos_nombres, req_turnos_lv, req_turnos_sd, desc_data, conceder_comp, tipo_ciclo, tipo_rotacion, accion_sobrante)
        
        st.write("---")
        st.subheader(f"💾 Guardar Malla de {cargo_sel} en BD y Notificar")
        tabla_malla = f"cable_malla_{cargo_sel.lower().replace(' ', '_')}"
        tabla_nom = f"cable_nomina_{cargo_sel.lower().replace(' ', '_')}"
        
        ya_existe = verificar_existencia_malla(tabla_malla, inicio, fin)
        
        c_b1, c_b2 = st.columns(2)
        with c_b1:
            if btn_save := st.button("⚠️ Confirmar y Actualizar Histórico" if ya_existe else "💾 Guardar Malla Definitiva"):
                if guardar_malla_historico(df_final, tabla_malla, inicio, fin):
                    rep_temp = generar_reporte_generico(df_final, config_h, df_cargo, modo_prog, desc_data)
                    guardar_malla_historico(rep_temp, tabla_nom, inicio, fin)
                    st.success(f"🎉 ¡Malla y Nómina guardadas exitosamente!")
        
        with c_b2:
            with st.popover("📩 Enviar Malla por Correo"):
                rem = st.text_input("Tu Correo Remitente", key="rem_ot")
                pwd = st.text_input("Contraseña App", type="password", key="pw_ot")
                if st.button("🚀 Enviar Correos"):
                    if rem and pwd:
                        with st.spinner("Enviando..."):
                            df_rep = generar_reporte_generico(df_final, config_h, df_cargo, modo_prog, desc_data)
                            exito, msj = enviar_correos_masivos(df_rep, cargar_empleados_bd(), inicio.strftime('%B %Y'), rem, pwd)
                            if exito: st.success(msj)
                            else: st.error(msj)

        st.write("---")
        st.subheader("📋 Malla de Turnos Operativa")
        pivot_h = df_final.pivot(index="Sujeto", columns="Fecha", values="Turno").fillna("DESCANSO")
        pivot_h.columns = [p.strftime('%Y-%m-%d') if isinstance(p, (datetime, date, pd.Timestamp)) else str(p) for p in pivot_h.columns]
        
        st.markdown(generar_html_imprimible(pivot_h, f"Malla Operativa - {cargo_sel}"), unsafe_allow_html=True)
        st.dataframe(style_malla(pivot_h), use_container_width=True)

        st.write("---")
        with st.expander("🔍 Forzar cambio individual en cualquier fecha", expanded=False):
            c_f1, c_f2 = st.columns(2)
            f_libre_sel = c_f1.selectbox("Seleccione la Fecha:", list(pivot_h.columns), key="f_drop_otros")
            if c_f2.button("⚙️ Abrir Gestor de Turno", use_container_width=True, key="btn_gestor_otros"):
                popup_forzar_ajuste_fecha_otros(f_libre_sel, df_cargo['Nombre'].tolist(), turnos_nombres)

        st.write("---")
        st.subheader("📈 Cuadro de Mando y Auditoría")
        t_dash, t_fatiga, t_nomina, t_hist = st.tabs(["📊 Dashboard de Costos", "⚠️ Alarmas de Fatiga", "📋 Reporte Nómina", "🗄️ Histórico BD"])
        
        rep_maestro = generar_reporte_generico(df_final, config_h, df_cargo, modo_prog, desc_data)

        with t_dash:
            if not rep_maestro.empty:
                t_hrs = rep_maestro['Horas Programadas'].sum()
                t_ext = rep_maestro['Horas Extras'].sum()
                
                c_m1, c_m2, c_m3 = st.columns(3)
                c_m1.metric("💰 Costo Proyectado Base", f"${(t_hrs * valor_hora):,.0f} COP")
                c_m2.metric("📈 Costo Proyectado Extras", f"${(t_ext * valor_hora * 1.25):,.0f} COP")
                c_m3.metric("⏱️ Total Horas", f"{t_hrs:,.0f} h")
                
                rep_maestro['Costo Total ($)'] = (rep_maestro['Horas Programadas'] * valor_hora) + (rep_maestro['Horas Extras'] * valor_hora * 1.25)
                st.bar_chart(rep_maestro.groupby("Nombre")['Costo Total ($)'].sum().reset_index(), x="Nombre", y="Costo Total ($)")
                
        with t_fatiga:
            lista_alertas = verificar_alarmas_otros(df_final)
            if lista_alertas:
                for al in lista_alertas: st.warning(al["Mensaje"])
            else: st.success("✅ Libre de alertas de fatiga.")

        with t_nomina:
            st.dataframe(rep_maestro, use_container_width=True)
            
        with t_hist:
            try:
                df_hist_full = pd.read_sql(f"SELECT * FROM {tabla_malla}", engine)
                if not df_hist_full.empty:
                    df_hist_full['Fecha_str'] = pd.to_datetime(df_hist_full['Fecha']).dt.strftime('%Y-%m-%d')
                    c_h1, c_h2 = st.columns(2)
                    h_ini = c_h1.date_input("Desde:", inicio, key=f"h_ini_{cargo_sel}")
                    h_fin = c_h2.date_input("Hasta:", fin, key=f"h_fin_{cargo_sel}")
                    mask = (df_hist_full['Fecha_str'] >= h_ini.strftime('%Y-%m-%d')) & (df_hist_full['Fecha_str'] <= h_fin.strftime('%Y-%m-%d'))
                    df_filtrado = df_hist_full[mask].drop(columns=['Fecha_str'])
                    if not df_filtrado.empty:
                        pivot_hist = df_filtrado.pivot(index="Sujeto", columns="Fecha", values="Turno").fillna("DESCANSO")
                        pivot_hist.columns = [p.strftime('%Y-%m-%d') for p in pivot_hist.columns]
                        st.dataframe(style_malla(pivot_hist), use_container_width=True)
            except: st.info(f"La BD para {cargo_sel} aún no ha sido creada.")
