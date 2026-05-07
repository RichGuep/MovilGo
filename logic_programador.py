import pandas as pd
import holidays
from datetime import datetime, timedelta

def es_cambio_saludable(ayer, hoy):
    """Garantiza que el cuerpo humano no salte de trasnocho a mañana sin descanso."""
    if ayer in ["DESC", "COMP", "OFF"] or hoy in ["DESC", "COMP", "OFF"]:
        return True
    jerarquia = {"T1": 1, "T2": 2, "T3": 3}
    return jerarquia.get(hoy, 0) >= jerarquia.get(ayer, 0)

def generar_malla_balanceada(f_ini, f_fin, estado_ayer, descansos_config):
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    
    # Conversión de fechas
    f_ini_dt = datetime.combine(f_ini, datetime.min.time()) if not isinstance(f_ini, datetime) else f_ini
    f_fin_dt = datetime.combine(f_fin, datetime.min.time()) if not isinstance(f_fin, datetime) else f_fin
    
    lista_fechas = [f_ini_dt + timedelta(days=x) for x in range((f_fin_dt - f_ini_dt).days + 1)]
    resultados = []
    
    mem_t = {g: estado_ayer[g]["u"] for g in grupos_n}
    mem_n = {g: estado_ayer[g]["n"] for g in grupos_n}
    deudas = {g: estado_ayer[g]["d"] for g in grupos_n}
    
    # Contador de turnos para Auditoría de Equilibrio
    stats_mensuales = {g: {"T1": 0, "T2": 0, "T3": 0} for g in grupos_n}
    co_h = holidays.Colombia(years=[f_ini_dt.year, f_fin_dt.year])

    for fecha_dt in lista_fechas:
        dia_idx = fecha_dt.weekday()
        es_fest = fecha_dt in co_h
        col_name = f"{fecha_dt.strftime('%a %d/%m')}{' 🇨🇴' if es_fest else ''}"

        # 1. Aplicar descanso fijo configurado por el usuario
        libranzas_hoy = [g for g, d in descansos_config.items() if d == dia_idx]
        activos = [g for g in grupos_n if g not in libranzas_hoy]
        
        turnos_hoy = {}
        
        # 2. Asignación con Balanceo (Prioriza al que menos ha trabajado cada turno)
        for t_req in ["T3", "T2", "T1"]:
            candidatos = [g for g in activos if g not in turnos_hoy and es_cambio_saludable(mem_t[g], t_req)]
            
            if t_req == "T3":
                candidatos = [g for g in candidatos if mem_n[g] < 6] # Máximo 6 noches

            if candidatos:
                # REGLA DE EQUILIBRIO: El que menos veces ha hecho este turno en el mes
                elegido = min(candidatos, key=lambda x: stats_mensuales[x][t_req])
                turnos_hoy[elegido] = t_req
                stats_mensuales[elegido][t_req] += 1
            else:
                # Escape: Si hay bloqueo, asignar al azar de los disponibles
                sobrantes = [g for g in activos if g not in turnos_hoy]
                if sobrantes:
                    elegido = sobrantes[0]
                    turnos_hoy[elegido] = t_req
                    stats_mensuales[elegido][t_req] += 1

        # 3. Consolidación
        for g in grupos_n:
            if g in libranzas_hoy: t_f = "DESC"
            elif g in turnos_hoy: t_f = turnos_hoy[g]
            else: t_f = "COMP" # Grupo de apoyo/descanso extra
            
            n_a = mem_n[g] + 1 if t_f == "T3" else 0
            resultados.append({
                "Grupo": g, "Fecha_Col": col_name, "Turno": t_f, 
                "Fecha_Raw": fecha_dt, "Noches_Acum": n_a, "Deuda_Compensatorio": deudas[g]
            })
            mem_t[g] = t_f
            mem_n[g] = n_a

    return pd.DataFrame(resultados)
