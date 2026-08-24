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

def style_malla(df_pivot):
    styles = pd.DataFrame('', index=df_pivot.index, columns=df_pivot.columns)
    for col in df_pivot.columns:
        es_fin_semana = False
        es_festivo = False
        try:
            fecha_dt = pd.to_datetime(col)
            if fecha_dt.weekday() in [5, 6]: es_fin_semana = True
            if fecha_dt in festivos_co: es_festivo = True
        except: pass

        for idx in df_pivot.index:
            val = df_pivot.at[idx, col]
            key = str(val).strip() if val and str(val).strip() != "" else "DESCANSO"
            if key not in COLORES_MAP and "Turno 1" in key: bg = "#D6EAF8"
            elif key not in COLORES_MAP and "Turno 2" in key: bg = "#D5F5E3"
            elif key not in COLORES_MAP and "Turno 3" in key: bg = "#FADBD8"
            else: bg = COLORES_MAP.get(key, "#1B2631")
                
            txt = "white" if key in ["DESCANSO", "COMPENSADO", "✅ OK 24/7", "❌ FALTA TURNO"] else "#17202A"
            
            border_style = "0.5px solid #D5DBDB"
            if es_festivo: border_style = "2px solid #E67E22"
            elif es_fin_semana: border_style = "1.5px solid #7F8C8D"
                
            styles.at[idx, col] = f'background-color: {bg}; color: {txt}; font-weight: 700; border: {border_style};'
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
# 4. MOTOR DE ASIGNACIÓN TÉCNICOS
# =========================================================
def generar_malla_tecnicos_avanzado(inicio, fin, descansos_iniciales, conceder_compensatorio, tipo_ciclo_descanso, activar_t4=False):
    df_emp = cargar_excel("empleados_grupos.xlsx")
    if df_emp.empty: return pd.DataFrame()
    
    filas = []
    deudas = {g: 0 for g in GRUPOS_TEC}
    
    turnos_historia = {g: i for i, g in enumerate(GRUPOS_TEC)} 
    ayer_descanso = {g: False for g in GRUPOS_TEC}
    pool_descansos = DIAS_ES 
    
    for fecha in pd.date_range(inicio, fin):
        dia_n = DIAS_ES[fecha.weekday()]
        sem = fecha.isocalendar()[1]
        delta_meses = (fecha.year - inicio.year) * 12 + (fecha.month - inicio.month)
        fecha_str = fecha.strftime('%Y-%m-%d')
        es_fin_semana = (fecha.weekday() in [5, 6])
        
        if tipo_ciclo_descanso == "Mensual": desplazamiento = delta_meses
        elif tipo_ciclo_descanso == "Trimestral": desplazamiento = delta_meses // 3
        else: desplazamiento = 0
            
        descansos_vivos = {}
        for g in GRUPOS_TEC:
            d_name = descansos_iniciales[g]
            idx_inicial = pool_descansos.index(d_name) if d_name in pool_descansos else 0
            idx_rotado = (idx_inicial + desplazamiento) % len(pool_descansos)
            descansos_vivos[g] = pool_descansos[idx_rotado]

        asig = {}
        gps_h = [g for g, d in descansos_vivos.items() if d == dia_n]
        if len(gps_h) > 1:
            idx = sem % len(gps_h)
            d_r = gps_h[idx]
            asig[d_r] = "DESCANSO"
            for g in gps_h: 
                if g != d_r and conceder_compensatorio: deudas[g] += 1
        elif len(gps_h) == 1: 
            asig[gps_h[0]] = "DESCANSO"
        
        if 0 <= fecha.weekday() <= 4 and conceder_compensatorio:
            g_d = sorted([g for g, d in deudas.items() if d > 0 and g not in asig], key=lambda x: deudas[x], reverse=True)
            if g_d: 
                asig[g_d[0]] = "COMPENSADO"
                deudas[g_d[0]] -= 1

        activos = [g for g in GRUPOS_TEC if g not in asig]
        
        for g in activos:
            if ayer_descanso[g]:
                turnos_historia[g] = (turnos_historia[g] + 1) % 4
                
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
            0: "T1", 
            1: "T2", 
            2: "T3", 
            3: "T4" if (activar_t4 and not es_fin_semana) else "DISPONIBLE"
        }
        
        for g in GRUPOS_TEC:
            if g in asig:
                turno_final = asig[g]
                ayer_descanso[g] = True
            else:
                turno_final = turnos_map[asignacion_hoy[g]]
                ayer_descanso[g] = False
                
            if "ajustes_manuales" in st.session_state and (g, fecha_str) in st.session_state.ajustes_manuales:
                turno_final = st.session_state.ajustes_manuales[(g, fecha_str)]
                
            filas.append({"Fecha": fecha, "Sujeto": g, "Turno": turno_final})
            
    return pd.DataFrame(filas)

# =========================================================
# 5. CÁLCULO DE RECARGOS Y HORAS EXTRAS INTEGRAL (REFORMA)
# =========================================================
def obtener_minutos_desde_time(objeto_hora):
    if objeto_hora is None: return None
    if isinstance(objeto_hora, time): return objeto_hora.hour * 60 + objeto_hora.minute
        
    s = str(objeto_hora).strip().upper()
    if s in ["OFF", "NAN", ""]: return None
        
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.hour * 60 + dt.minute
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

    if min_fin >= min_inicio:
        minutos_totales = min_fin - min_inicio
    else:
        minutos_totales = (1440 - min_inicio) + min_fin
        
    total_horas = minutos_totales / 60.0
    
    if (inicio_str == "06:30" and fin_str == "13:30") or (inicio_str == "13:30" and fin_str == "20:30"):
        horas_extras = 0.0
    else:
        horas_extras = max(0.0, total_horas - 7.0)
    
    minutos_nocturnos = 0
    min_actual = min_inicio
    for _ in range(int(minutos_totales)):
        min_ciclo = min_actual % 1440
        if min_ciclo >= 1140 or min_ciclo < 360: minutos_nocturnos += 1
        min_actual += 1
        
    horas_nocturnas = minutos_nocturnos / 60.0
    return round(total_horas, 2), round(horas_extras, 2), round(horas_nocturnas, 2)

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

def ejecutar_auditoria_completa(df_plano, config_horas):
    df_aud = df_plano.copy()
    df_aud["Fecha"] = pd.to_datetime(df_aud["Fecha"])
    cob = df_aud.groupby(["Fecha", "Turno"]).size().unstack(fill_value=0)
    for c in ["T1", "T2", "T3", "T4", "DESCANSO", "COMPENSADO", "DISPONIBLE"]:
        if c not in cob.columns: cob[c] = 0
    return cob

def verificar_alarmas_cambios_drasticos(df_plano):
    df_plano = df_plano.sort_values(by=["Sujeto", "Fecha"])
    alertas = []
    for sujeto, group in df_plano.groupby("Sujeto"):
        lista_turnos = group["Turno"].tolist()
        lista_fechas = group["Fecha"].tolist()
        for i in range(1, len(lista_turnos)):
            t_anterior = lista_turnos[i-1]
            t_actual = lista_turnos[i]
            fecha_act = lista_fechas[i]
            
            if t_anterior in ["T3", "T4"] and t_actual in ["T1", "T2", "DISPONIBLE"]: 
                alertas.append({"Sujeto": sujeto, "Mensaje": f"🚨 **Violación de Descanso Circadiano ({t_anterior} -> {t_actual})** en '{sujeto}' el {fecha_act.strftime('%Y-%m-%d')}."})
            elif t_anterior == "T2" and t_actual == "T1":
                alertas.append({"Sujeto": sujeto, "Mensaje": f"⚠️ **Transición Corta Inválida (T2 -> T1)** en '{sujeto}' el {fecha_act.strftime('%Y-%m-%d')}."})
    return alertas

def generar_reporte_detallado(df_final, config_horas, config_descansos, activar_t4=False):
    df_emp = cargar_excel("empleados_grupos.xlsx")
    if df_emp.empty: return pd.DataFrame()
    
    filas_reporte = []
    df_final['Fecha'] = pd.to_datetime(df_final['Fecha'])
    df_sub = df_emp[df_emp['GrupoAsignado'].isin(GRUPOS_TEC)].copy()
    df_sub['idx_cargo'] = df_sub.groupby(['GrupoAsignado', 'Cargo']).cumcount()
    
    col_cedula = 'Cedula' if 'Cedula' in df_sub.columns else ('Cédula' if 'Cédula' in df_sub.columns else None)

    for _, emp in df_sub.iterrows():
        g_pertenece = emp['GrupoAsignado']
        cargo_actual = emp['Cargo']
        nombre_real = emp['Nombre']
        cedula_real = str(emp[col_cedula]) if col_cedula else "N/A"
        
        malla_bloque = df_final[df_final['Sujeto'] == g_pertenece]
            
        for _, m_fila in malla_bloque.iterrows():
            turno_asignado = m_fila['Turno']
            fecha_dt = m_fila['Fecha']
            fecha_str = fecha_dt.strftime('%Y-%m-%d')

            if "m_personas_editada" in st.session_state and (nombre_real, fecha_str) in st.session_state.m_personas_editada:
                turno_asignado = st.session_state.m_personas_editada[(nombre_real, fecha_str)]

            info_turno = config_horas.get(turno_asignado, {"Inicio": "OFF", "Fin": "OFF"})
            ini = info_turno.get("Inicio", "OFF")
            fin = info_turno.get("Fin", "OFF")

            h_prog, h_extra, h_noc = calcular_metricas_reforma(ini, fin, fecha_dt)

            filas_reporte.append({
                "Fecha": fecha_str, 
                "Cedula": cedula_real,
                "Nombre": nombre_real, 
                "Cargo": cargo_actual, 
                "Grupo Asignado": g_pertenece,
                "Día Descanso Asignado": config_descansos.get(g_pertenece, "Domingo"),
                "Turno realizado": turno_asignado, 
                "Hora inicio": ini, 
                "Hora fin": fin, 
                "Horas Programado": h_prog,
                "Horas Extras": h_extra,
                "Recargos Nocturnos": h_noc,
                "Mes": fecha_dt.strftime('%B'), 
                "Semana": fecha_dt.isocalendar()[1]
            })
    return pd.DataFrame(filas_reporte)

@st.dialog("🛠️ Forzar Cambio de Turno Específico", width="small")
def popup_forzar_ajuste_fecha(fecha_solicitada, opciones_sujetos, es_modo_persona=False):
    st.markdown(f"📅 **Fecha de Operación:** `{fecha_solicitada}`")
    sujeto_sel = st.selectbox("🎯 Seleccione el Elemento a Modificar:", opciones_sujetos)
    opciones_turnos = ["T1", "T2", "T3", "T4", "DESCANSO", "COMPENSADO", "DISPONIBLE"]
    nuevo_turno = st.selectbox("🆕 Turno Destino Asignado:", opciones_turnos, index=0)
    
    if st.button("🔄 Aplicar a Previsualización"):
        fecha_actual_dt = pd.to_datetime(fecha_solicitada)
        fecha_ayer_str = (fecha_actual_dt - timedelta(days=1)).strftime('%Y-%m-%d')
        
        turno_ayer = "DESCANSO"
        if es_modo_persona:
            if "m_personas_editada" in st.session_state and (sujeto_sel, fecha_ayer_str) in st.session_state.m_personas_editada:
                turno_ayer = st.session_state.m_personas_editada[(sujeto_sel, fecha_ayer_str)]
        else:
            if "ajustes_manuales" in st.session_state and (sujeto_sel, fecha_ayer_str) in st.session_state.ajustes_manuales:
                turno_ayer = st.session_state.ajustes_manuales[(sujeto_sel, fecha_ayer_str)]

        if turno_ayer in ["T3", "T4"] and nuevo_turno in ["T1", "T2", "DISPONIBLE"]:
            st.error(f"❌ **Cambio Denegado por Fatiga Crítica:** No se permite pasar de un turno Nocturno ({turno_ayer}) a turnos diurnos ({nuevo_turno}) sin un día intermedio de descanso.")
            return

        if turno_ayer == "T2" and nuevo_turno == "T1":
            st.error("❌ **Cambio Denegado:** Transición descendente corta inválida (T2 -> T1).")
            return

        guardar_ajuste_bd(sujeto_sel, fecha_solicitada, nuevo_turno)

        if es_modo_persona: 
            st.session_state.m_personas_editada[(sujeto_sel, fecha_solicitada)] = nuevo_turno
        else: 
            st.session_state.ajustes_manuales[(sujeto_sel, fecha_solicitada)] = nuevo_turno
            
        st.success("¡Turno validado en memoria! No olvides Guardar la Malla Definitiva.")
        st.rerun()

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
                    f_min = df_aplanado['Fecha'].min()
                    f_max = df_aplanado['Fecha'].max()
                    guardar_malla_historico(df_aplanado, "cable_malla_tecnicos", f_min, f_max)
                    st.sidebar.success("✅ Malla histórica importada y guardada en BD con éxito.")
                    st.rerun()
        except Exception as e: st.sidebar.error(f"Error de lectura: {str(e)}")

    st.markdown("### ⚙️ Panel de Parámetros Avanzados de Cuadrilla (Técnicos)")
    c_p1, c_p2 = st.columns(2)
    conceder_compensatorio = c_p1.checkbox("⚖️ Otorgar días Compensatorios por Cobertura Dominical (Reforma Laboral)", value=True)
    # 🌟 NUEVO INPUT PARA DASHBOARDS
    valor_hora = c_p2.number_input("💰 Valor Hora Ordinaria Proyectada ($):", min_value=0, value=6500, step=500, key="vh_tec")

    tipo_ciclo_descanso = st.selectbox("🔄 Ciclo de Rotación Temporal para los días de Descanso Base:", options=["Fijo sin rotación", "Mensual", "Trimestral"])
    
    activar_t4 = st.toggle("⚡ Activar Esquema de Cuadrilla Eficiente (T4 - 7 Horas L-V)", value=False, help="Activa el T4 de Lunes a Viernes para optimizar costos de operación y mitigar recargos. Sábados y Domingos regresará automáticamente a esquema T3 para proteger fines de semana.")

    with st.expander("⏰ Configuración Rangos de Jornada", expanded=False):
        config_h = {}
        t_l = ["T1", "T2", "T3", "DISPONIBLE"]
        if activar_t4: 
            t_l.append("T4")
        
        def_h = {
            "T1": [time(4,0), time(11,0)], 
            "T2": [time(11,0), time(18,0)], 
            "T3": [time(15,0), time(22,0)], 
            "T4": [time(21,0), time(4,0)], 
            "DISPONIBLE": [time(6,30), time(13,30)]
        }
        cols = st.columns(3)
        for i, t in enumerate(t_l):
            with cols[i%3]:
                ini = st.time_input(f"Inicia {t}", def_h[t][0], key=f"i{t}")
                fin = st.time_input(f"Fin {t}", def_h[t][1], key=f"f{t}")
                config_h[t] = {"Inicio": ini.strftime("%H:%M"), "Fin": fin.strftime("%H:%M")}
                
        config_h["DESCANSO"] = config_h["COMPENSADO"] = {"Inicio": "OFF", "Fin": "OFF"}
        if not activar_t4:
            config_h["T4"] = {"Inicio": "21:00", "Fin": "04:00"}

    st.write("---")
    c1, c2 = st.columns(2)
    inicio, fin = c1.date_input("Inicio Planificación", date(2026, 7, 1)), c2.date_input("Fin Planificación", date(2026, 12, 31))
    cols = st.columns(4)
    desc_data = {"Grupo 1": cols[0].selectbox("Descanso G1", DIAS_ES, index=4), "Grupo 2": cols[1].selectbox("Descanso G2", DIAS_ES, index=5), "Grupo 3": cols[2].selectbox("Descanso G3", DIAS_ES, index=6), "Grupo 4": cols[3].selectbox("Descanso G4", DIAS_ES, index=0)}

    if 'm_base' not in st.session_state:
        st.session_state.m_base = generar_malla_tecnicos_avanzado(inicio, fin, desc_data, conceder_compensatorio, tipo_ciclo_descanso, activar_t4)

    if st.button("👁️ PREVISUALIZAR MALLA (Sin Guardar)"):
        st.session_state.ajustes_manuales = {}
        st.session_state.m_personas_editada = {}
        st.session_state.m_base = generar_malla_tecnicos_avanzado(inicio, fin, desc_data, conceder_compensatorio, tipo_ciclo_descanso, activar_t4)

    if 'm_base' in st.session_state and not st.session_state.m_base.empty:
        df_final = generar_malla_tecnicos_avanzado(inicio, fin, desc_data, conceder_compensatorio, tipo_ciclo_descanso, activar_t4)
        
        st.write("---")
        st.subheader("💾 Guardar Malla en Histórico BD y Notificar")
        ya_existe = verificar_existencia_malla("cable_malla_tecnicos", inicio, fin)
        
        if ya_existe:
            st.warning(f"⚠️ Atención: Ya existe una malla guardada en BD que choca con las fechas {inicio} a {fin}. Guardar actualizará/sobreescribirá esos días específicos sin borrar el resto.")
        
        c_b1, c_b2 = st.columns(2)
        with c_b1:
            if st.button("⚠️ Confirmar y Actualizar Histórico" if ya_existe else "💾 Guardar Malla Definitiva"):
                if guardar_malla_historico(df_final, "cable_malla_tecnicos", inicio, fin):
                    rep_temp = generar_reporte_detallado(df_final, config_h, desc_data, activar_t4)
                    guardar_malla_historico(rep_temp, "cable_nomina_tecnicos", inicio, fin)
                    st.success("🎉 ¡Malla y Reporte de Nómina guardados/actualizados exitosamente en la Base de Datos!")
        
        # 🌟 NUEVO BOTÓN DE CORREOS
        with c_b2:
            with st.popover("📩 Enviar Malla por Correo"):
                st.info("Ingresa la credencial de tu correo corporativo o cuenta de Gmail.")
                remitente = st.text_input("Tu Correo Remitente", placeholder="admin@cablemovil.com", key="rem_tec")
                password = st.text_input("Contraseña de Aplicación", type="password", key="pass_tec")
                if st.button("🚀 Confirmar y Enviar", key="btn_env_tec"):
                    if remitente and password:
                        with st.spinner("Conectando con el servidor de correos y enviando..."):
                            df_rep = generar_reporte_detallado(df_final, config_h, desc_data, activar_t4)
                            exito, mensaje = enviar_correos_masivos(df_rep, cargar_empleados_bd(), inicio.strftime('%B %Y'), remitente, password)
                            if exito: st.success(mensaje)
                            else: st.error(mensaje)
                    else:
                        st.warning("Completa el correo y la contraseña.")
        
        st.write("---")
        
        df_audit = df_final.copy()
        df_audit["Fecha"] = pd.to_datetime(df_audit["Fecha"])
        cob = ejecutar_auditoria_completa(df_audit, config_h)
        
        fechas_novedad = []
        for d_f in cob.index:
            hay_descanso_hoy = (cob.at[d_f, "DESCANSO"] > 0 or cob.at[d_f, "COMPENSADO"] > 0)
            if cob.at[d_f, "T1"] == 0 or cob.at[d_f, "T2"] == 0 or cob.at[d_f, "T3"] == 0:
                fechas_novedad.append(d_f)
            elif not hay_descanso_hoy and activar_t4 and (d_f.weekday() not in [5, 6]) and cob.at[d_f, "T4"] == 0:
                fechas_novedad.append(d_f)
        
        fechas_novedad = sorted(list(set(fechas_novedad)))
        
        if fechas_novedad: st.error(f"⚠️ **Novedad en Cobertura:** Hay {len(fechas_novedad)} días desprotegidos.")
        else: st.success("✅ **Malla 100% Protegida:** Todos los días cumplen con el soporte operativo requerido sin novedad.")
            
        st.subheader("📋 Malla de Turnos Operativa por Grupo (Macro)")
        pivot_grupo = df_final.pivot(index="Sujeto", columns="Fecha", values="Turno").fillna("DESCANSO")
        pivot_grupo.columns = [p.strftime('%Y-%m-%d') if isinstance(p, (datetime, date, pd.Timestamp)) else str(p) for p in pivot_grupo.columns]
        
        fila_semaforo = {}
        dias_criticos_lista = []
        for col_fecha in pivot_grupo.columns:
            col_dt = pd.to_datetime(col_fecha)
            es_f_s = (col_dt.weekday() in [5, 6])
            hay_descanso_hoy = (cob.at[col_dt, "DESCANSO"] > 0 or cob.at[col_dt, "COMPENSADO"] > 0) if col_dt in cob.index else False
            
            t1_ok = cob.at[col_dt, "T1"] > 0 if col_dt in cob.index else False
            t2_ok = cob.at[col_dt, "T2"] > 0 if col_dt in cob.index else False
            t3_ok = cob.at[col_dt, "T3"] > 0 if col_dt in cob.index else False
            t4_ok = cob.at[col_dt, "T4"] > 0 if col_dt in cob.index else False
            
            if activar_t4 and not es_f_s and not hay_descanso_hoy:
                status_hoy = "✅ OK 24/7" if (t1_ok and t2_ok and t3_ok and t4_ok) else "❌ FALTA TURNO"
            else:
                status_hoy = "✅ OK 24/7" if (t1_ok and t2_ok and t3_ok) else "❌ FALTA TURNO"
                
            fila_semaforo[col_fecha] = status_hoy
            if status_hoy == "❌ FALTA TURNO": dias_criticos_lista.append(col_fecha)
                
        df_semaforo_row = pd.DataFrame([fila_semaforo], index=["🔍 AUDITORÍA 24/7"])
        pivot_g_completa = pd.concat([pivot_grupo, df_semaforo_row])
        
        # 🌟 NUEVO EXPORTADOR HTML/PDF
        st.markdown(generar_html_imprimible(pivot_grupo, f"Malla Operativa (Técnicos Macro) - {inicio.strftime('%b %Y')}"), unsafe_allow_html=True)
        st.dataframe(style_malla(pivot_g_completa), use_container_width=True)

        st.write("---")
        st.subheader("👤 Malla de Turnos Detallada por Persona (Desglosada)")
        rep_maestro_base = generar_reporte_detallado(df_final, config_h, desc_data, activar_t4)
        
        if not rep_maestro_base.empty:
            pivot_persona = rep_maestro_base.pivot(index=["Grupo Asignado", "Nombre"], columns="Fecha", values="Turno realizado").fillna("DESCANSO")
            pivot_persona.columns = [p.strftime('%Y-%m-%d') if isinstance(p, (datetime, date, pd.Timestamp)) else str(p) for p in pivot_persona.columns]
            
            # 🌟 NUEVO EXPORTADOR HTML/PDF
            st.markdown(generar_html_imprimible(pivot_persona, f"Malla Operativa (Técnicos Detalle) - {inicio.strftime('%b %Y')}"), unsafe_allow_html=True)
            st.dataframe(style_malla(pivot_persona), use_container_width=True)

        st.write("---")
        st.subheader("⚙️ Panel de Gestión y Corrección de Turnos")
        opt_b_modo = st.radio("🎯 Nivel de Cobertura a Modificar:", ["Ajustar Grupo (Macro)", "Ajustar Empleado (Micro)"], horizontal=True)
        lista_nombres_unicos = sorted(list(rep_maestro_base["Nombre"].unique())) if not rep_maestro_base.empty else []

        if dias_criticos_lista:
            st.markdown(f"🚨 **Días con huecos operativos detectados ({len(dias_criticos_lista)}):**")
            cols_botones = st.columns(min(len(dias_criticos_lista), 5))
            for idx_b, f_critica in enumerate(dias_criticos_lista[:15]):
                with cols_botones[idx_b % 5]:
                    if st.button(f"🛠️ Corregir {f_critica[5:]}", key=f"btn_crit_{f_critica}"):
                        opciones_s = lista_nombres_unicos if opt_b_modo == "Ajustar Empleado (Micro)" else GRUPOS_TEC
                        popup_forzar_ajuste_fecha(f_critica, opciones_s, es_modo_persona=(opt_b_modo == "Ajustar Empleado (Micro)"))
        else:
            st.success("🎉 ¡Excelente! No hay días desprotegidos en el semestre actual.")
            
        with st.expander("🔍 Forzar cambio en cualquier otra fecha de la Malla (Planificación libre)"):
            c_f1, c_f2 = st.columns(2)
            f_libre_sel = c_f1.selectbox("Seleccione la Fecha:", list(pivot_grupo.columns), key="f_libre_dropdown")
            if c_f2.button("⚙️ Abrir Gestor de Turno para esta Fecha", use_container_width=True):
                opciones_s = lista_nombres_unicos if opt_b_modo == "Ajustar Empleado (Micro)" else GRUPOS_TEC
                popup_forzar_ajuste_fecha(f_libre_sel, opciones_s, es_modo_persona=(opt_b_modo == "Ajustar Empleado (Micro)"))

        st.write("---")
        st.subheader("📈 Cuadro de Mando, Costos y Auditoría")
        
        # 🌟 NUEVAS PESTAÑAS Y DASHBOARD POTENCIADO
        t_dash, t_fatiga, t_nomina, t_hist = st.tabs(["📊 Dashboard de Costos", "⚠️ Alarmas de Fatiga", "📋 Reporte Nómina", "🗄️ Consultar Histórico BD"])
        
        with t_dash:
            if not rep_maestro_base.empty:
                total_horas = rep_maestro_base['Horas Programado'].sum()
                total_extras = rep_maestro_base['Horas Extras'].sum()
                
                costo_base = total_horas * valor_hora
                costo_extras = total_extras * (valor_hora * 1.25) # Proyección 25% de recargo base
                
                c_m1, c_m2, c_m3 = st.columns(3)
                c_m1.metric("💰 Costo Proyectado Base", f"${costo_base:,.0f} COP")
                c_m2.metric("📈 Costo Proyectado Extras", f"${costo_extras:,.0f} COP")
                c_m3.metric("⏱️ Total Horas Operativas", f"{total_horas:,.0f} h")
                
                st.markdown("#### Proyección de Costos por Empleado")
                rep_maestro_base['Costo Total ($)'] = (rep_maestro_base['Horas Programado'] * valor_hora) + (rep_maestro_base['Horas Extras'] * valor_hora * 1.25)
                st.bar_chart(rep_maestro_base.groupby("Nombre")['Costo Total ($)'].sum().reset_index(), x="Nombre", y="Costo Total ($)")
            else: st.info("💡 Faltan datos para graficar.")
            
        with t_fatiga:
            lista_alertas = verificar_alarmas_cambios_drasticos(df_audit)
            if lista_alertas:
                for al in lista_alertas: st.markdown(al["Mensaje"])
            else: st.success("✅ Estructura libre de alertas de fatiga.")
            
        with t_nomina:
            if 'Turno realizado' in rep_maestro_base.columns and not rep_maestro_base.empty:
                cols_existentes = [c for c in ["Fecha", "Cedula", "Nombre", "Cargo", "Grupo Asignado", "Día Descanso Asignado", "Turno realizado", "Hora inicio", "Hora fin", "Horas Programado", "Horas Extras", "Recargos Nocturnos", "Costo Total ($)"] if c in rep_maestro_base.columns]
                df_reporte_ordenado = rep_maestro_base[cols_existentes]
                st.dataframe(df_reporte_ordenado, use_container_width=True)
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer: 
                    df_reporte_ordenado.to_excel(writer, sheet_name="Detalle_Dias", index=False)
                st.download_button("📥 Descargar Reporte Nómina", output.getvalue(), f"Nomina_Técnicos_{date.today()}.xlsx")

        with t_hist:
            st.markdown("#### 🗄️ Motor de Búsqueda Histórica (PostgreSQL)")
            try:
                df_hist_full = pd.read_sql("SELECT * FROM cable_malla_tecnicos", engine)
                if not df_hist_full.empty:
                    df_hist_full['Fecha_str'] = pd.to_datetime(df_hist_full['Fecha']).dt.strftime('%Y-%m-%d')
                    c_h1, c_h2 = st.columns(2)
                    h_ini = c_h1.date_input("Consultar Desde:", inicio, key="h_ini_t")
                    h_fin = c_h2.date_input("Consultar Hasta:", fin, key="h_fin_t")
                    mask = (df_hist_full['Fecha_str'] >= h_ini.strftime('%Y-%m-%d')) & (df_hist_full['Fecha_str'] <= h_fin.strftime('%Y-%m-%d'))
                    df_filtrado = df_hist_full[mask].drop(columns=['Fecha_str'])
                    
                    if not df_filtrado.empty:
                        st.success(f"🔍 Se encontraron {len(df_filtrado)} registros en la BD.")
                        pivot_h = df_filtrado.pivot(index="Sujeto", columns="Fecha", values="Turno").fillna("DESCANSO")
                        pivot_h.columns = [p.strftime('%Y-%m-%d') if isinstance(p, (datetime, date, pd.Timestamp)) else str(p) for p in pivot_h.columns]
                        st.dataframe(style_malla(pivot_h), use_container_width=True)
                    else: st.warning("No hay registros.")
            except: st.info("BD vacía.")

# =========================================================
# 8. MOTOR Y PANEL DE ABORDAJE
# =========================================================
import re

def crear_personal_abordaje(total_personas, lista_grupos, persona_fija):
    filas = []
    num_g = len(lista_grupos)
    nombres_totales = [f"Abordaje_{i+1:02d}" for i in range(total_personas)]
    
    # Separamos al fijo para que no entre en la rotación de los grupos normales
    operativos = [n for n in nombres_totales if n != persona_fija]
    
    for i, nombre in enumerate(operativos):
        filas.append({"Nombre": nombre, "Grupo": lista_grupos[i % num_g]})
        
    if persona_fija and persona_fija != "Ninguno":
        filas.append({"Nombre": persona_fija, "Grupo": "Fijo_Domingo"})
        
    return pd.DataFrame(filas)

def generar_malla_abordaje(inicio, fin, descansos_iniciales, total_personas, req_t1, req_t2, req_f, tipo_ciclo_descanso, tipo_rotacion_turnos, lista_grupos, frec_doble_desc, persona_fija, modo_flotantes):
    df_pers = crear_personal_abordaje(total_personas, lista_grupos, persona_fija)
    filas = []
    dias_unicos_str = [descansos_iniciales.get(g, "Lunes") for g in lista_grupos]
    empleados = df_pers["Nombre"].tolist()
    num_g = len(lista_grupos)
    
    # 🧠 CONTADORES DE REFORMA LABORAL Y MEMORIA
    turno_ayer = {p: "DESCANSO" for p in empleados}
    consecutivos_trabajo = {p: 0 for p in empleados}
    deuda_descanso = {p: 0 for p in empleados}
    descansos_perdidos_mes = {p: 0 for p in empleados}
    mes_actual = inicio.month
    
    # Configurar Flotantes Fijos
    if "Fijos" in modo_flotantes and req_f > 0:
        flotantes_fijos = empleados[-req_f:]
        operativos = [p for p in empleados if p not in flotantes_fijos]
    else:
        flotantes_fijos = []
        operativos = empleados

    for fecha in pd.date_range(inicio, fin):
        # Reiniciar contadores de ley al cambiar de mes
        if fecha.month != mes_actual:
            descansos_perdidos_mes = {p: 0 for p in empleados}
            mes_actual = fecha.month
            
        dia_n = DIAS_ES[fecha.weekday()]
        idx_dia_actual = DIAS_ES.index(dia_n)
        fecha_str = fecha.strftime('%Y-%m-%d')
        delta_meses = (fecha.year - inicio.year) * 12 + (fecha.month - inicio.month)
        sem = fecha.isocalendar()[1]
        
        if tipo_ciclo_descanso == "Mensual": desplazamiento_desc = delta_meses
        elif tipo_ciclo_descanso == "Trimestral": desplazamiento_desc = delta_meses // 3
        elif tipo_ciclo_descanso == "Semestral": desplazamiento_desc = delta_meses // 6
        else: desplazamiento_desc = 0
            
        descansos_hoy_g = []
        for idx_g, g in enumerate(lista_grupos):
            dia_base_str = dias_unicos_str[(idx_g + desplazamiento_desc) % num_g]
            
            es_semana_doble = False
            if frec_doble_desc > 0:
                es_semana_doble = ((sem - idx_g) % frec_doble_desc) == 0
            
            # REGLA 2: Si es semana de bono, el descanso es SOLO Sábado y Domingo
            if es_semana_doble:
                if dia_n in ["Sábado", "Domingo"]:
                    descansos_hoy_g.append(g)
            else:
                if dia_n == dia_base_str:
                    descansos_hoy_g.append(g)
                    
        asig_hoy = {}
        for _, p in df_pers.iterrows():
            if p["Grupo"] == "Fijo_Domingo":
                if dia_n == "Domingo": asig_hoy[p["Nombre"]] = "DESCANSO"
            elif p["Grupo"] in descansos_hoy_g:
                asig_hoy[p["Nombre"]] = "DESCANSO"
                
        # 🎁 REGLA 3: Dar COMPENSADO el fin de semana a los que debamos
        if dia_n in ["Sábado", "Domingo"]:
            for p in empleados:
                if p not in asig_hoy and deuda_descanso[p] > 0:
                    asig_hoy[p] = "COMPENSADO"
                    deuda_descanso[p] -= 1
                    
        activos = [p for p in empleados if p not in asig_hoy]
        req_total = req_t1 + req_t2 + req_f
        
        # ⚖️ REPARADOR DE DÉFICIT OPERATIVO (Generación de deuda)
        if len(activos) < req_total:
            faltan = req_total - len(activos)
            # Solo sacrifica descansos de quienes NO han superado el límite legal del mes
            descansando_norm = [p for p, t in asig_hoy.items() if t == "DESCANSO" and p != persona_fija and descansos_perdidos_mes[p] < 2]
            descansando_norm.sort(key=lambda p: descansos_perdidos_mes[p])
            
            for p in descansando_norm[:faltan]:
                del asig_hoy[p]
                activos.append(p)
                deuda_descanso[p] += 1
                descansos_perdidos_mes[p] += 1
                faltan -= 1
                
            # Si aún así nos faltan (emergencia), quitamos compensados y devolvemos la deuda
            if faltan > 0:
                descansando_comp = [p for p, t in asig_hoy.items() if t == "COMPENSADO" and p != persona_fija]
                for p in descansando_comp[:faltan]:
                    del asig_hoy[p]
                    activos.append(p)
                    deuda_descanso[p] += 1
                    faltan -= 1

        # ⚖️ REPARADOR DE EXCEDENTES
        elif len(activos) > req_total:
            sobrante = len(activos) - req_total
            activos.sort(key=lambda p: consecutivos_trabajo[p], reverse=True)
            for p in activos[:sobrante]:
                asig_hoy[p] = "DESCANSO"
            activos = activos[sobrante:]
            
        # 🔄 ROTACIÓN DE TURNOS
        if tipo_rotacion_turnos == "Semanal": delta_rot = sem
        elif tipo_rotacion_turnos == "Quincenal": delta_rot = sem // 2
        elif tipo_rotacion_turnos == "Mensual": delta_rot = delta_meses
        else: delta_rot = 0
        
        target_shift = {}
        if "Fijos" in modo_flotantes:
            pool_base = ["T1"] * req_t1 + ["T2"] * req_t2
            while len(pool_base) < len(operativos): pool_base.append("T1")
            pool_base = pool_base[:len(operativos)]
            
            desp = (delta_rot * (len(operativos) // 2)) % max(1, len(operativos))
            pool_rotado = pool_base[-desp:] + pool_base[:-desp] if desp > 0 else pool_base
            target_shift = {operativos[i]: pool_rotado[i] for i in range(len(operativos))}
            for f in flotantes_fijos: target_shift[f] = "FLOTANTE"
        else:
            pool_base = ["T1"] * req_t1 + ["T2"] * req_t2 + ["FLOTANTE"] * req_f
            while len(pool_base) < total_personas: pool_base.append("FLOTANTE")
            pool_base = pool_base[:total_personas]
            
            desp = (delta_rot * (total_personas // 2)) % total_personas
            pool_rotado = pool_base[-desp:] + pool_base[:-desp] if desp > 0 else pool_base
            target_shift = {empleados[i]: pool_rotado[i] for i in range(total_personas)}
        
        # 🛡️ INERCIA Y ASIGNACIÓN (Evita cruces dañinos)
        t1_asig, t2_asig, f_asig = 0, 0, 0
        libres_hoy = []
        
        if persona_fija in activos:
            asig_hoy[persona_fija] = "FLOTANTE"
            f_asig += 1
        
        operativos_activos = [p for p in activos if p != persona_fija]
        for p in operativos_activos:
            if turno_ayer[p] in ["T1", "T2", "FLOTANTE"]:
                if "Fijos" in modo_flotantes and p in flotantes_fijos:
                    if f_asig < req_f: asig_hoy[p] = "FLOTANTE"; f_asig += 1
                    else: libres_hoy.append(p)
                elif "Fijos" in modo_flotantes and p in operativos and turno_ayer[p] == "FLOTANTE":
                    libres_hoy.append(p)
                elif turno_ayer[p] == "T1" and t1_asig < req_t1: asig_hoy[p] = "T1"; t1_asig += 1
                elif turno_ayer[p] == "T2" and t2_asig < req_t2: asig_hoy[p] = "T2"; t2_asig += 1
                elif turno_ayer[p] == "FLOTANTE" and f_asig < req_f: asig_hoy[p] = "FLOTANTE"; f_asig += 1
                else: libres_hoy.append(p)
            else:
                libres_hoy.append(p)
                
        faltan_t1 = max(0, req_t1 - t1_asig)
        faltan_t2 = max(0, req_t2 - t2_asig)
        faltan_f = max(0, req_f - f_asig)
        
        for p in libres_hoy:
            pref = target_shift.get(p, "T1")
            asignado = False
            if pref == "T1" and faltan_t1 > 0: asig_hoy[p] = "T1"; faltan_t1 -= 1; asignado = True
            elif pref == "T2" and faltan_t2 > 0: asig_hoy[p] = "T2"; faltan_t2 -= 1; asignado = True
            elif pref == "FLOTANTE" and faltan_f > 0: asig_hoy[p] = "FLOTANTE"; faltan_f -= 1; asignado = True
            
            if not asignado:
                if faltan_t1 > 0: asig_hoy[p] = "T1"
                elif faltan_t2 > 0: asig_hoy[p] = "T2"
                elif faltan_f > 0: asig_hoy[p] = "FLOTANTE"
                
        for p in empleados:
            turno = asig_hoy.get(p, "DESCANSO")
            turno_ayer[p] = turno
            if turno in ["DESCANSO", "COMPENSADO"]: consecutivos_trabajo[p] = 0
            else: consecutivos_trabajo[p] += 1
                
        for _, p in df_pers.iterrows():
            turno_final = asig_hoy.get(p["Nombre"], "DESCANSO")
            if "ajustes_manuales_abo" in st.session_state and (p["Nombre"], fecha_str) in st.session_state.ajustes_manuales_abo:
                turno_final = st.session_state.ajustes_manuales_abo[(p["Nombre"], fecha_str)]
            filas.append({"Fecha": fecha, "Grupo": p["Grupo"], "Nombre": p["Nombre"], "Turno": turno_final})
            
    return pd.DataFrame(filas)

def style_malla_abordaje(df_pivot):
    styles = pd.DataFrame('', index=df_pivot.index, columns=df_pivot.columns)
    color_map = {"T1": "#D6EAF8", "T2": "#D5F5E3", "FLOTANTE": "#E8DAEF", "DESCANSO": "#1B2631", "COMPENSADO": "#2E4053"}
    for col in df_pivot.columns:
        es_fin_semana = "🔴" in str(col)
        for idx in df_pivot.index:
            val = str(df_pivot.at[idx, col]).strip()
            bg = color_map.get(val, "#1B2631")
            txt = "white" if val in ["DESCANSO", "COMPENSADO"] else "#17202A"
            border = "2.5px solid #E74C3C" if es_fin_semana else "0.5px solid #D5DBDB"
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
            "Fecha": fecha_dt.strftime('%Y-%m-%d'), "Nombre": row['Nombre'], "Grupo": row['Grupo'], "Turno": turno,
            "Hora inicio": ini, "Hora fin": fin, "Horas Programadas": h_prog, "Horas Extras": h_extra,
            "Recargos Nocturnos": h_noc, "Mes": fecha_dt.strftime('%B'), "Semana": fecha_dt.isocalendar()[1]
        })
    return pd.DataFrame(filas)

def verificar_alarmas_abordaje(df_final):
    df_plano = df_final.sort_values(by=["Nombre", "Fecha"])
    alertas = []
    for sujeto, group in df_plano.groupby("Nombre"):
        lista_turnos = group["Turno"].tolist()
        lista_fechas = group["Fecha"].tolist()
        for i in range(1, len(lista_turnos)):
            if lista_turnos[i-1] == "T2" and lista_turnos[i] == "T1":
                alertas.append({"Mensaje": f"🚨 **Transición Crítica Ilegal (T2 -> T1)** para **{sujeto}** el día {lista_fechas[i].strftime('%Y-%m-%d')}."})
    return alertas

@st.dialog("🛠️ Forzar Cambio de Turno (Abordaje)", width="small")
def popup_forzar_ajuste_fecha_abo(fecha_solicitada, opciones_sujetos):
    st.markdown(f"📅 **Fecha de Operación:** `{fecha_solicitada}`")
    sujeto_sel = st.selectbox("🎯 Seleccione el Empleado a Modificar:", opciones_sujetos)
    nuevo_turno = st.selectbox("🆕 Turno Destino Asignado:", ["T1", "T2", "FLOTANTE", "DESCANSO", "COMPENSADO"], index=0)
    if st.button("🔄 Aplicar a Previsualización"):
        match = re.search(r'\d{4}-\d{2}-\d{2}', fecha_solicitada)
        fecha_limpia = match.group(0) if match else fecha_solicitada
        st.session_state.ajustes_manuales_abo[(sujeto_sel, fecha_limpia)] = nuevo_turno
        st.success("¡Turno validado en memoria!")
        st.rerun()

def pantalla_abordaje():
    if "ajustes_manuales_abo" not in st.session_state: st.session_state.ajustes_manuales_abo = {}
    st.markdown("## 🚀 Panel de Programación - Abordaje Operativo")

    c_tot, c_grp, c_t1, c_t2, c_f = st.columns(5)
    total_p = c_tot.number_input("Total Planta", 10, 100, 28)
    num_grupos = c_grp.number_input("Cant. de Grupos", 1, 15, 5)
    req_t1 = c_t1.number_input("Cobertura T1", 1, 50, 11)
    req_t2 = c_t2.number_input("Cobertura T2", 1, 50, 11)
    req_f = c_f.number_input("Flotantes", 0, 20, 2)
    
    lista_grupos = [f"Grupo A{i+1}" for i in range(num_grupos)]
    valor_hora = st.number_input("💰 Valor Hora Ordinaria Proyectada ($):", min_value=0, value=6500, step=500, key="vh_abo")
    
    st.markdown("---")
    
    st.markdown("### ⚙️ Configuración de Beneficios y Fijos")
    c_esp1, c_esp2, c_esp3 = st.columns(3)
    modo_flotantes = c_esp1.radio("🔄 Modalidad Turno Flotante:", ["Rotativo (Toda la planta rota)", "Fijos (Personal exclusivo)"], horizontal=True)
    nombres_disponibles = [f"Abordaje_{i+1:02d}" for i in range(total_p)]
    persona_fija = c_esp2.selectbox("🎯 Flotante Fijo Especial (Descansa siempre en Domingo):", ["Ninguno"] + nombres_disponibles)
    
    activar_doble = c_esp3.checkbox("Activar Bono Adicional Sáb/Dom", value=True)
    frec_doble = c_esp3.number_input("Rotación del Bono (Cada X semanas):", 1, 12, 5, disabled=not activar_doble)
    frecuencia_final = frec_doble if activar_doble else 0
    
    st.markdown("---")
    c_i, c_f_col, c_rot, c_rot_turnos = st.columns(4)
    inicio = c_i.date_input("Inicio Planificación", date(2026, 9, 1), key="i_abo")
    fin = c_f_col.date_input("Fin Planificación", date(2026, 9, 30), key="f_abo")
    tipo_ciclo_descanso = c_rot.selectbox("🔄 Ciclo Descanso:", ["Fijo sin rotación", "Mensual", "Trimestral", "Semestral"], key="ciclo_desc_abo")
    tipo_rotacion_turnos = c_rot_turnos.selectbox("🔄 Ciclo Turnos (T1/T2):", ["Fijo sin rotación", "Semanal", "Quincenal", "Mensual", "Bimensual", "Trimestral"], key="ciclo_turn_abo")

    st.markdown("### 📅 Día de Descanso Base por Grupo (De Lunes a Viernes)")
    cols = st.columns(min(num_grupos, 7))
    desc_data = {}
    for i, g in enumerate(lista_grupos):
        desc_data[g] = cols[i % 7].selectbox(f"Desc. {g}", DIAS_ES[:5], index=i % 5, key=f"desc_{g}")
                                  
    if st.button("👁️ PREVISUALIZAR MALLA (Sin Guardar)"):
        st.session_state.m_base_abo = generar_malla_abordaje(inicio, fin, desc_data, total_p, req_t1, req_t2, req_f, tipo_ciclo_descanso, tipo_rotacion_turnos, lista_grupos, frecuencia_final, persona_fija, modo_flotantes)
        
    if 'm_base_abo' in st.session_state and not st.session_state.m_base_abo.empty:
        df_final = generar_malla_abordaje(inicio, fin, desc_data, total_p, req_t1, req_t2, req_f, tipo_ciclo_descanso, tipo_rotacion_turnos, lista_grupos, frecuencia_final, persona_fija, modo_flotantes)
        st.session_state.m_base_abo = df_final
        
        dia_libre_map = {g: desc_data.get(g, "Domingo") for g in lista_grupos}
        dia_libre_map["Fijo_Domingo"] = "Domingo"
        df_final["Descanso Base"] = df_final["Grupo"].map(dia_libre_map)
        
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
                st.info("Ingresa tu credencial SMTP.")
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
                
        st.write("---")
        st.subheader("👤 Malla de Turnos Detallada por Persona y Grupo")
        
        pivot_persona = df_final.pivot(index=["Grupo", "Descanso Base", "Nombre"], columns="Fecha", values="Turno").fillna("DESCANSO")
        
        nuevas_cols = []
        for c in pivot_persona.columns:
            if isinstance(c, (datetime, date, pd.Timestamp)):
                dia_nombre = DIAS_ES[c.weekday()][:3]
                es_finde = c.weekday() in [5, 6]
                marcador = "🔴 " if es_finde else ""
                nuevas_cols.append(f"{marcador}{c.strftime('%Y-%m-%d')} ({dia_nombre})")
            else:
                nuevas_cols.append(str(c))
                
        pivot_persona.columns = nuevas_cols
        
        st.markdown(generar_html_imprimible(pivot_persona, f"Malla Abordaje - {inicio.strftime('%b %Y')}"), unsafe_allow_html=True)
        st.dataframe(style_malla_abordaje(pivot_persona), use_container_width=True)
        
        st.write("---")
        with st.expander("🔍 Forzar cambio en cualquier fecha de la Malla"):
            c_f1, c_f2 = st.columns(2)
            f_libre_sel = c_f1.selectbox("Seleccione la Fecha:", list(pivot_persona.columns), key="f_libre_dropdown_abo")
            if c_f2.button("⚙️ Abrir Gestor de Turno", use_container_width=True):
                popup_forzar_ajuste_fecha_abo(f_libre_sel, sorted(list(df_final["Nombre"].unique())))

        st.write("---")
        t_dash, t_fatiga, t_nomina, t_hist = st.tabs(["📊 Dashboard de Costos", "⚠️ Alarmas de Fatiga", "📋 Reporte Nómina", "🗄️ Consultar Histórico BD"])
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
            lista_alertas = verificar_alarmas_abordaje(df_final)
            if lista_alertas:
                for al in lista_alertas: st.warning(al["Mensaje"])
            else: st.success("✅ Estructura libre de alertas de fatiga.")
            
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
