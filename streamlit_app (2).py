import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import hashlib
import uuid
import random
import io
import json
from datetime import date, datetime, timedelta
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

# ── Configuración de página ───────────────────────────────────────────────────
st.set_page_config(
    page_title="Sistema Polvorín Minero",
    page_icon="🧨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.semaforo-verde  {background:#C6EFCE;border-radius:12px;padding:20px;text-align:center;font-size:1.5em;font-weight:bold;color:#1F5C1F;border:2px solid #1F5C1F;}
.semaforo-amarillo{background:#FFEB9C;border-radius:12px;padding:20px;text-align:center;font-size:1.5em;font-weight:bold;color:#7F6000;border:2px solid #BF8F00;}
.semaforo-rojo   {background:#FFCCCC;border-radius:12px;padding:20px;text-align:center;font-size:1.5em;font-weight:bold;color:#C00000;border:2px solid #C00000;}
.alerta-critica  {background:#FFCCCC;border-left:5px solid #C00000;padding:10px 14px;border-radius:4px;margin:4px 0;}
.alerta-alta     {background:#FFEB9C;border-left:5px solid #BF8F00;padding:10px 14px;border-radius:4px;margin:4px 0;}
.alerta-media    {background:#FFF2CC;border-left:5px solid #7F6000;padding:10px 14px;border-radius:4px;margin:4px 0;}
.alerta-ok       {background:#C6EFCE;border-left:5px solid #1F5C1F;padding:10px 14px;border-radius:4px;margin:4px 0;}
.kpi-card        {background:white;border-radius:10px;padding:16px;box-shadow:0 2px 8px rgba(0,0,0,0.08);margin-bottom:8px;}
.barra-cap       {background:#eee;border-radius:6px;height:22px;margin:4px 0;}
.barra-fill-ok   {background:#1F5C1F;height:22px;border-radius:6px;}
.barra-fill-warn {background:#BF8F00;height:22px;border-radius:6px;}
.barra-fill-crit {background:#C00000;height:22px;border-radius:6px;}
.rol-badge       {display:inline-block;padding:3px 10px;border-radius:12px;font-size:0.8em;font-weight:bold;}
.rol-admin       {background:#1F3864;color:white;}
.rol-jefe        {background:#2E75B6;color:white;}
.rol-operario    {background:#70AD47;color:white;}
.rol-lectura     {background:#999;color:white;}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# BASE DE DATOS SQLITE
# ══════════════════════════════════════════════════════════════════════════════
DB_PATH = "polvorin.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS usuarios (
        id TEXT PRIMARY KEY, nombre TEXT, usuario TEXT UNIQUE,
        pin_hash TEXT, rol TEXT, licencia_venc TEXT, activo INTEGER DEFAULT 1
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS inventario (
        id_lote TEXT PRIMARY KEY, explosivo TEXT, tipo TEXT,
        cantidad INTEGER, unidad TEXT, peso_kg_total REAL,
        fecha_ingreso TEXT, fecha_vencimiento TEXT,
        proveedor TEXT, n_guia TEXT, operador TEXT,
        almacen TEXT, qr_data TEXT, estado TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS movimientos (
        id_mov TEXT PRIMARY KEY, id_lote TEXT, explosivo TEXT,
        tipo_mov TEXT, cantidad INTEGER, fecha_hora TEXT,
        operador TEXT, destino TEXT, n_orden TEXT,
        turno TEXT, observaciones TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS accesos (
        id TEXT PRIMARY KEY, operador TEXT, tipo TEXT,
        fecha_hora TEXT, motivo TEXT, turno TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS turnos (
        id TEXT PRIMARY KEY, jefe TEXT, tipo TEXT,
        inicio TEXT, fin TEXT, estado TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS viajes (
        id_viaje TEXT PRIMARY KEY, vehiculo TEXT, ruta TEXT,
        operador TEXT, explosivo TEXT, cantidad INTEGER,
        inicio TEXT, fin TEXT, dist_km REAL,
        t_esperado INTEGER, t_real INTEGER, demora INTEGER,
        estado TEXT, turno TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS condiciones (
        id TEXT PRIMARY KEY, fecha_hora TEXT,
        temp_sec REAL, hum_sec REAL,
        temp_prim REAL, hum_prim REAL
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS auditorias (
        id TEXT PRIMARY KEY, fecha TEXT, operador TEXT,
        explosivo TEXT, cantidad_sistema INTEGER,
        cantidad_real INTEGER, diferencia INTEGER,
        estado TEXT, observaciones TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS vehiculos (
        id TEXT PRIMARY KEY, patente TEXT, modelo TEXT,
        rev_tecnica TEXT, permiso TEXT, estado TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS proveedores (
        id TEXT PRIMARY KEY, nombre TEXT, rut TEXT,
        contacto TEXT, habilitado INTEGER DEFAULT 1
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS kpis (
        id TEXT PRIMARY KEY, nombre TEXT, area TEXT,
        valor_base REAL, meta_6m REAL, meta_12m REAL,
        unidad TEXT, descripcion TEXT
    )""")

    conn.commit()
    conn.close()
    _seed_data()

def hash_pin(pin):
    return hashlib.sha256(str(pin).encode()).hexdigest()

def _seed_data():
    conn = get_conn()
    c = conn.cursor()

    # Usuarios de prueba
    usuarios = [
        ("USR-001","Carlos Administrador","admin","1234","administrador",
         str(date.today()+timedelta(days=365))),
        ("USR-002","Roberto Jefe","jefe_turno","5678","jefe_turno",
         str(date.today()+timedelta(days=180))),
        ("USR-003","Juan Operario","operario1","9012","operario",
         str(date.today()+timedelta(days=90))),
        ("USR-004","Ana Operaria","operario2","3456","operario",
         str(date.today()+timedelta(days=200))),
        ("USR-005","Pedro Inspector","inspector","7890","solo_lectura",
         str(date.today()+timedelta(days=500))),
        # Operario con licencia vencida para pruebas
        ("USR-006","Luis Vencido","operario3","1111","operario",
         str(date.today()-timedelta(days=10))),
    ]
    for u in usuarios:
        c.execute("INSERT OR IGNORE INTO usuarios VALUES (?,?,?,?,?,?,1)",
                  (u[0],u[1],u[2],hash_pin(u[3]),u[4],u[5]))

    # Inventario simulado
    hoy = date.today()
    lotes = [
        ("ANFO-2026-001","ANFO","Secundario",18,"saco",450.0,
         str(hoy-timedelta(days=45)),str(hoy+timedelta(days=320)),
         "Enaex S.A.","GU-2026-0041","operario1","Container secundarios","","Vigente"),
        ("ANFO-2026-002","ANFO","Secundario",3,"saco",75.0,
         str(hoy-timedelta(days=400)),str(hoy-timedelta(days=35)),
         "Enaex S.A.","GU-2025-0098","operario1","Container secundarios","","Vencido"),
        ("EMUL-2026-001","Emulsion","Secundario",12,"caja",240.0,
         str(hoy-timedelta(days=20)),str(hoy+timedelta(days=160)),
         "Orica Chile","GU-2026-0051","operario2","Container secundarios","","Vigente"),
        ("EMUL-2026-002","Emulsion","Secundario",8,"caja",160.0,
         str(hoy-timedelta(days=160)),str(hoy+timedelta(days=15)),
         "Enaex S.A.","GU-2026-0028","operario2","Container secundarios","","Por vencer"),
        ("MECH-2026-001","Mecha de seguridad","Secundario",1,"rollo",5.0,
         str(hoy-timedelta(days=90)),str(hoy+timedelta(days=640)),
         "Famesa","GU-2026-0019","operario1","Container secundarios","","Stock bajo"),
        ("FULM-2026-001","Fulminante N8","Primario",5,"caja",2.5,
         str(hoy-timedelta(days=45)),str(hoy+timedelta(days=320)),
         "Famesa","GU-2026-0035","operario1","Boveda enterrada (primarios)","","Vigente"),
    ]
    for l in lotes:
        c.execute("INSERT OR IGNORE INTO inventario VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", l)

    # Movimientos simulados
    movs = [
        ("MOV-001","ANFO-2026-001","ANFO","Ingreso",18,
         str(hoy-timedelta(days=45))+" 08:30","operario1","-","GU-2026-0041","Mañana",""),
        ("MOV-002","ANFO-2026-001","ANFO","Despacho",5,
         str(hoy-timedelta(days=15))+" 07:00","operario1",
         "Tronadura Nivel 1","ORD-2026-012","Mañana",""),
        ("MOV-003","EMUL-2026-001","Emulsion","Ingreso",12,
         str(hoy-timedelta(days=20))+" 09:00","operario2","-","GU-2026-0051","Tarde",""),
        ("MOV-004","FULM-2026-001","Fulminante N8","Ingreso",5,
         str(hoy-timedelta(days=45))+" 10:00","operario1","-","GU-2026-0035","Mañana",
         "Almacenado en boveda primarios"),
    ]
    for m in movs:
        c.execute("INSERT OR IGNORE INTO movimientos VALUES (?,?,?,?,?,?,?,?,?,?,?)", m)

    # Vehículos
    vehs = [
        ("VEH-001","PAT-001","Camión F-150",
         str(hoy+timedelta(days=120)),str(hoy+timedelta(days=90)),"Operativo"),
        ("VEH-002","PAT-002","Camioneta Hilux",
         str(hoy-timedelta(days=5)),str(hoy+timedelta(days=60)),"Rev. técnica vencida"),
        ("VEH-003","PAT-003","Camión Mercedes",
         str(hoy+timedelta(days=200)),str(hoy+timedelta(days=150)),"Operativo"),
    ]
    for v in vehs:
        c.execute("INSERT OR IGNORE INTO vehiculos VALUES (?,?,?,?,?,?)", v)

    # Proveedores
    provs = [
        ("PROV-001","Enaex S.A.","76.456.789-0","contacto@enaex.cl",1),
        ("PROV-002","Orica Chile","76.123.456-7","chile@orica.com",1),
        ("PROV-003","Famesa","76.789.012-3","ventas@famesa.cl",1),
        ("PROV-004","Maxam Chile","76.321.654-9","info@maxam.cl",1),
        ("PROV-005","Proveedor No Habilitado","12.345.678-9","noauth@test.cl",0),
    ]
    for p in provs:
        c.execute("INSERT OR IGNORE INTO proveedores VALUES (?,?,?,?,?)", p)

    # KPIs
    kpis = [
        ("KPI-001","% lotes con vencimiento registrado","Inventario",
         60,90,100,"%","Porcentaje de lotes con fecha de vencimiento correctamente registrada"),
        ("KPI-002","% despachos con orden de retiro","Inventario",
         40,85,100,"%","Porcentaje de despachos respaldados por orden formal"),
        ("KPI-003","Tiempo inventario físico","Inventario",
         45,20,10,"min","Tiempo promedio para realizar conteo físico completo"),
        ("KPI-004","Discrepancias por auditoría","Inventario",
         8,3,0,"N°/mes","Número de discrepancias detectadas por auditoría mensual"),
        ("KPI-005","% lotes vencidos detectados a tiempo","Seguridad",
         30,80,100,"%","Porcentaje de lotes vencidos detectados antes de ser usados"),
        ("KPI-006","Tiempo generación reporte AF","Seguridad",
         120,15,5,"min","Tiempo para generar reporte para Autoridad Fiscalizadora"),
        ("KPI-007","% cumplimiento libro control DGMN","Seguridad",
         50,90,100,"%","Porcentaje de registros del libro control correctamente completados"),
        ("KPI-008","% viajes en tiempo","Traslados",
         55,80,90,"%","Porcentaje de traslados completados dentro del tiempo esperado"),
        ("KPI-009","Tiempo promedio despacho","Traslados",
         25,12,8,"min","Tiempo desde solicitud hasta salida del polvorín"),
        ("KPI-010","Alertas ambientales sin respuesta","Ambiental",
         0,2,0,"N°/mes","Alertas de condición ambiental sin respuesta en plazo"),
    ]
    for k in kpis:
        c.execute("INSERT OR IGNORE INTO kpis VALUES (?,?,?,?,?,?,?,?)", k)

    # Condiciones ambientales simuladas
    ahora = datetime.now()
    for h in range(24):
        dt = ahora - timedelta(hours=23-h)
        cid = "COND-"+str(h).zfill(3)
        c.execute("INSERT OR IGNORE INTO condiciones VALUES (?,?,?,?,?,?)",
                  (cid, dt.strftime("%Y-%m-%d %H:%M"),
                   round(random.uniform(14,38),1), round(random.uniform(45,85),1),
                   round(random.uniform(10,26),1), round(random.uniform(40,70),1)))

    # Viajes simulados
    rutas_data = {
        "Polvorin → Nivel 1":   (3.2,12),
        "Polvorin → Nivel 2":   (4.8,18),
        "Polvorin → Banco Norte":(2.1,8),
        "Polvorin → Banco Sur":  (5.5,20),
    }
    for i in range(10):
        ruta_n = random.choice(list(rutas_data.keys()))
        dist, t_esp = rutas_data[ruta_n]
        demora = random.choices([0, random.randint(2,15)], weights=[70,30])[0]
        t_real = t_esp + demora
        dt_s = ahora - timedelta(hours=random.randint(1,72))
        vid = "VJ-"+str(i+1).zfill(3)
        c.execute("INSERT OR IGNORE INTO viajes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (vid, random.choice(["PAT-001","PAT-003"]), ruta_n,
                   random.choice(["operario1","operario2"]),
                   random.choice(["ANFO","Emulsion"]),
                   random.randint(1,5),
                   dt_s.strftime("%Y-%m-%d %H:%M"),
                   (dt_s+timedelta(minutes=t_real)).strftime("%Y-%m-%d %H:%M"),
                   dist, t_esp, t_real, demora,
                   "Con demora" if demora>0 else "En tiempo", "Mañana"))

    conn.commit()
    conn.close()

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN NORMATIVA
# ══════════════════════════════════════════════════════════════════════════════
EXPLOSIVOS_CFG = {
    "ANFO":               {"tipo":"Secundario","unidad":"saco",  "peso_kg":25.0,"stock_min":5, "vida_dias":365,"almacen":"Container secundarios","temp_max":35,"hum_max":70},
    "Emulsion":           {"tipo":"Secundario","unidad":"caja",  "peso_kg":20.0,"stock_min":3, "vida_dias":180,"almacen":"Container secundarios","temp_max":30,"hum_max":65},
    "Mecha de seguridad": {"tipo":"Secundario","unidad":"rollo", "peso_kg":5.0, "stock_min":2, "vida_dias":730,"almacen":"Container secundarios","temp_max":40,"hum_max":75},
    "Fulminante N8":      {"tipo":"Primario",  "unidad":"caja",  "peso_kg":0.5, "stock_min":2, "vida_dias":365,"almacen":"Boveda enterrada (primarios)","temp_max":30,"hum_max":60},
}

CAPACIDADES = {
    "Container secundarios":       {"kg_max":3500,"dist_m":50},
    "Boveda enterrada (primarios)":{"kg_max":400, "dist_m":25},
}

RUTAS = {
    "Polvorin → Nivel 1":    {"dist_km":3.2,"tiempo_min":12,"limite_kmh":30},
    "Polvorin → Nivel 2":    {"dist_km":4.8,"tiempo_min":18,"limite_kmh":30},
    "Polvorin → Banco Norte":{"dist_km":2.1,"tiempo_min":8, "limite_kmh":25},
    "Polvorin → Banco Sur":  {"dist_km":5.5,"tiempo_min":20,"limite_kmh":30},
    "Polvorin → Rajo":       {"dist_km":7.2,"tiempo_min":28,"limite_kmh":35},
}

ROLES = {
    "administrador":{"label":"Administrador","color":"rol-admin","permisos":["todo"]},
    "jefe_turno":   {"label":"Jefe de Turno","color":"rol-jefe", "permisos":["operar","reportes","kpis","config_turno"]},
    "operario":     {"label":"Operario",      "color":"rol-operario","permisos":["operar"]},
    "solo_lectura": {"label":"Inspector",     "color":"rol-lectura","permisos":["ver"]},
}

MAX_PERSONAS = 5

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def puede(permiso):
    rol = st.session_state.get("rol","")
    perms = ROLES.get(rol,{}).get("permisos",[])
    return "todo" in perms or permiso in perms

def turno_activo():
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM turnos WHERE estado='Activo' ORDER BY inicio DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return row

def personas_dentro():
    conn = get_conn()
    hoy_str = str(date.today())
    ingresos = conn.execute(
        "SELECT COUNT(*) FROM accesos WHERE tipo='Ingreso' AND fecha_hora LIKE ?",
        (hoy_str+"%",)
    ).fetchone()[0]
    egresos = conn.execute(
        "SELECT COUNT(*) FROM accesos WHERE tipo='Egreso' AND fecha_hora LIKE ?",
        (hoy_str+"%",)
    ).fetchone()[0]
    conn.close()
    return max(0, ingresos - egresos)

def peso_en_almacen(almacen):
    conn = get_conn()
    rows = conn.execute(
        "SELECT peso_kg_total FROM inventario WHERE almacen=? AND estado NOT IN ('Vencido')",
        (almacen,)
    ).fetchall()
    conn.close()
    return sum(r[0] for r in rows)

def get_inv():
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM inventario", conn)
    conn.close()
    return df

def get_movs():
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM movimientos ORDER BY fecha_hora DESC", conn)
    conn.close()
    return df

def get_viajes():
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM viajes ORDER BY inicio DESC", conn)
    conn.close()
    return df

def get_condiciones():
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM condiciones ORDER BY fecha_hora", conn)
    conn.close()
    return df

def clasificar(row):
    exp = str(row.get("explosivo",""))
    cfg = EXPLOSIVOS_CFG.get(exp,{})
    hoy = date.today()
    est = []
    try:
        fv = date.fromisoformat(str(row["fecha_vencimiento"]))
        d  = (fv-hoy).days
        if d<0:     est.append("Vencido")
        elif d<=30: est.append("Por vencer")
    except: pass
    try:
        if int(row["cantidad"])<cfg.get("stock_min",0): est.append("Stock bajo")
    except: pass
    if str(row.get("almacen",""))!=cfg.get("almacen",""): est.append("Almacen incorrecto")
    return " | ".join(est) if est else "Vigente"

def generar_alertas():
    inv = get_inv()
    alertas = []
    hoy = date.today()
    for _,row in inv.iterrows():
        exp  = str(row["explosivo"])
        cfg  = EXPLOSIVOS_CFG.get(exp,{})
        lote = str(row["id_lote"])
        try:
            fv = date.fromisoformat(str(row["fecha_vencimiento"]))
            d  = (fv-hoy).days
            if d<0:
                alertas.append({"gravedad":"CRITICA","icono":"🚨","lote":lote,"exp":exp,
                    "msg":"Lote VENCIDO hace "+str(abs(d))+" días",
                    "accion":"Destrucción autorizada — Ley Armas Cap. VIII"})
            elif d<=30:
                alertas.append({"gravedad":"ALTA","icono":"⚠️","lote":lote,"exp":exp,
                    "msg":"Vence en "+str(d)+" días",
                    "accion":"Notificar a Autoridad Fiscalizadora (DGMN)"})
        except: pass
        try:
            if int(row["cantidad"])<cfg.get("stock_min",0):
                alertas.append({"gravedad":"MEDIA","icono":"⚡","lote":lote,"exp":exp,
                    "msg":"Stock bajo: "+str(row["cantidad"])+" / mín "+str(cfg.get("stock_min",""))+" "+cfg.get("unidad",""),
                    "accion":"Solicitar reabastecimiento"})
        except: pass
        if str(row.get("almacen",""))!=cfg.get("almacen",""):
            alertas.append({"gravedad":"CRITICA","icono":"🚨","lote":lote,"exp":exp,
                "msg":"Almacén incorrecto: "+str(row.get("almacen","")),
                "accion":"Reubicar — DS 132 / Ley 17.798"})
    for alm,cap in CAPACIDADES.items():
        peso = peso_en_almacen(alm)
        pct  = peso/cap["kg_max"]*100
        if pct>=100:
            alertas.append({"gravedad":"CRITICA","icono":"🚨","lote":"-","exp":alm,
                "msg":"Capacidad MÁXIMA superada: "+str(round(peso,1))+" kg / "+str(cap["kg_max"])+" kg",
                "accion":"Bloquear ingresos hasta reducir stock"})
        elif pct>=90:
            alertas.append({"gravedad":"ALTA","icono":"⚠️","lote":"-","exp":alm,
                "msg":"Capacidad al "+str(round(pct,1))+"% — límite próximo",
                "accion":"Planificar despacho antes de nuevo ingreso"})
    cond = get_condiciones()
    if not cond.empty:
        ult = cond.iloc[-1]
        checks = [
            ("temp_sec","Container secundarios",35,"temperatura","°C"),
            ("hum_sec", "Container secundarios",70,"humedad","%"),
            ("temp_prim","Bóveda primarios",30,"temperatura","°C"),
            ("hum_prim", "Bóveda primarios",60,"humedad","%"),
        ]
        for col,alm,lim,tipo,uni in checks:
            if ult[col]>lim:
                alertas.append({"gravedad":"ALTA","icono":"⚠️","lote":"-","exp":alm,
                    "msg":tipo.capitalize()+" alta: "+str(ult[col])+uni+" (máx "+str(lim)+uni+")",
                    "accion":"Revisar ventilación/temperatura del almacén"})
    personas = personas_dentro()
    if personas>=MAX_PERSONAS:
        alertas.append({"gravedad":"ALTA","icono":"⚠️","lote":"-","exp":"Control Acceso",
            "msg":str(personas)+" personas dentro (máx "+str(MAX_PERSONAS)+")",
            "accion":"Esperar a que salga personal antes de ingresar"})
    conn = get_conn()
    vehs = pd.read_sql("SELECT * FROM vehiculos", conn)
    conn.close()
    for _,v in vehs.iterrows():
        try:
            frt = date.fromisoformat(str(v["rev_tecnica"]))
            if (frt-hoy).days<0:
                alertas.append({"gravedad":"ALTA","icono":"⚠️","lote":v["patente"],"exp":"Vehículo",
                    "msg":"Rev. técnica vencida: "+str(v["patente"])+" "+str(v["modelo"]),
                    "accion":"No asignar traslados hasta renovar revisión"})
        except: pass
    return alertas

def estado_semaforo(alertas):
    if any(a["gravedad"]=="CRITICA" for a in alertas): return "rojo"
    if any(a["gravedad"]=="ALTA"    for a in alertas): return "amarillo"
    return "verde"

def barra_capacidad(almacen):
    cap  = CAPACIDADES[almacen]
    peso = peso_en_almacen(almacen)
    pct  = min(round(peso/cap["kg_max"]*100,1),100)
    color = "crit" if pct>=100 else ("warn" if pct>=90 else "ok")
    return peso, cap["kg_max"], pct, color

# ══════════════════════════════════════════════════════════════════════════════
# AUTENTICACIÓN
# ══════════════════════════════════════════════════════════════════════════════
def pantalla_login():
    st.markdown("## 🧨 Sistema de Gestión de Polvorín Minero")
    st.markdown("**Universidad Andrés Bello · Memoria de Título 2026**")
    st.divider()
    col1,col2,col3 = st.columns([1,1.2,1])
    with col2:
        st.markdown("### 🔐 Iniciar sesión")
        with st.form("login"):
            usuario = st.text_input("Usuario")
            pin     = st.text_input("PIN", type="password",
                                    placeholder="4-6 dígitos")
            submit  = st.form_submit_button("Ingresar", type="primary",
                                            use_container_width=True)
        if submit:
            if not usuario or not pin:
                st.error("Ingresa usuario y PIN.")
                return
            conn = get_conn()
            row  = conn.execute(
                "SELECT * FROM usuarios WHERE usuario=? AND pin_hash=? AND activo=1",
                (usuario.strip(), hash_pin(pin.strip()))
            ).fetchone()
            conn.close()
            if not row:
                st.error("❌ Usuario o PIN incorrectos.")
                return
            cols = ["id","nombre","usuario","pin_hash","rol","licencia_venc","activo"]
            u    = dict(zip(cols, row))
            if u["rol"]=="operario":
                try:
                    lv = date.fromisoformat(str(u["licencia_venc"]))
                    if (lv-date.today()).days<0:
                        st.error("🚫 Licencia de manipulador vencida el "+str(lv)+".\n"
                                 "Contacte al administrador para actualizar.")
                        return
                except: pass
            st.session_state["autenticado"] = True
            st.session_state["usuario"]     = u["usuario"]
            st.session_state["nombre"]      = u["nombre"]
            st.session_state["rol"]         = u["rol"]
            st.session_state["id_usuario"]  = u["id"]
            st.session_state["licencia_venc"]= u["licencia_venc"]
            st.rerun()

        st.divider()
        st.markdown("**Usuarios de prueba:**")
        data_prueba = {
            "Rol":["Administrador","Jefe de Turno","Operario","Inspector","Op. Lic. Vencida"],
            "Usuario":["admin","jefe_turno","operario1","inspector","operario3"],
            "PIN":["1234","5678","9012","7890","1111"],
        }
        st.dataframe(pd.DataFrame(data_prueba), hide_index=True, use_container_width=True)
        st.caption("⚠️ Solo para demostración. Cambie credenciales en producción.")

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
def sidebar():
    with st.sidebar:
        rol_cfg = ROLES.get(st.session_state["rol"],{})
        st.markdown("### 🧨 Polvorín Minero")
        st.markdown('<span class="rol-badge '+rol_cfg.get("color","")+
                    '">'+rol_cfg.get("label","")+'</span> '+
                    st.session_state["nombre"], unsafe_allow_html=True)
        turno = turno_activo()
        if turno:
            st.success("🕐 Turno "+turno[3]+" activo")
        else:
            st.warning("⏸ Sin turno activo")
        st.divider()

        alertas = generar_alertas()
        sem = estado_semaforo(alertas)
        nc  = len([a for a in alertas if a["gravedad"]=="CRITICA"])
        na  = len([a for a in alertas if a["gravedad"]=="ALTA"])
        if sem=="rojo":
            st.error("🚨 "+str(nc)+" alerta(s) crítica(s)")
        elif sem=="amarillo":
            st.warning("⚠️ "+str(na)+" alerta(s) alta(s)")
        else:
            st.success("✅ Sin alertas críticas")

        opciones = ["🏠 Estado General"]
        if puede("operar") or puede("ver"):
            opciones += ["📥 Inventario","🚨 Alertas","🚪 Accesos",
                         "🌡️ Condiciones","🚛 Traslados"]
        if puede("reportes") or puede("todo"):
            opciones += ["📋 Reportes","📊 KPIs"]
        if puede("todo"):
            opciones += ["🔍 Auditoría","🏢 Administración"]
        opciones += ["📖 Manual","💬 Asistente"]

        modulo = st.radio("Módulo", opciones, label_visibility="collapsed")
        st.divider()
        if st.button("🚪 Cerrar sesión", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()
        st.caption("DS 132 · Ley 17.798 · DGMN 003048/2020")
    return modulo

# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO: ESTADO GENERAL (DASHBOARD)
# ══════════════════════════════════════════════════════════════════════════════
def mod_dashboard():
    st.title("🏠 Estado General del Polvorín")
    st.caption("Actualizado: "+datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    alertas  = generar_alertas()
    sem      = estado_semaforo(alertas)
    personas = personas_dentro()
    inv      = get_inv()

    # Semáforo
    textos = {
        "verde":    "🟢 TODO EN ORDEN",
        "amarillo": "🟡 ATENCIÓN REQUERIDA",
        "rojo":     "🔴 ACCIÓN INMEDIATA",
    }
    st.markdown('<div class="semaforo-'+sem+'">'+textos[sem]+'</div>',
                unsafe_allow_html=True)
    st.markdown("")

    # Métricas
    nc = len([a for a in alertas if a["gravedad"]=="CRITICA"])
    na = len([a for a in alertas if a["gravedad"]=="ALTA"])
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("📦 Lotes activos",
              len(inv[~inv["estado"].str.contains("Vencido",na=False)]))
    c2.metric("👷 Personas dentro",  str(personas)+"/"+str(MAX_PERSONAS),
              delta_color="inverse" if personas>=MAX_PERSONAS else "normal")
    c3.metric("🚨 Alertas críticas", nc,
              delta_color="inverse" if nc>0 else "normal")
    c4.metric("⚠️ Alertas altas",    na,
              delta_color="inverse" if na>0 else "normal")
    turno = turno_activo()
    c5.metric("🕐 Turno", turno[3] if turno else "Sin turno")

    st.divider()
    col_a, col_b = st.columns([1,1])

    with col_a:
        st.subheader("⚖️ Capacidad de almacenes")
        for alm in CAPACIDADES:
            peso,kg_max,pct,color = barra_capacidad(alm)
            st.markdown("**"+alm+"**")
            st.markdown(
                '<div class="barra-cap"><div class="barra-fill-'+color+
                '" style="width:'+str(pct)+'%"></div></div>',
                unsafe_allow_html=True)
            st.caption(str(round(peso,1))+" kg / "+str(kg_max)+" kg · "+str(pct)+"%")

        st.subheader("🌡️ Condiciones actuales")
        cond = get_condiciones()
        if not cond.empty:
            ult = cond.iloc[-1]
            cc1,cc2,cc3,cc4 = st.columns(4)
            cc1.metric("Temp. Container", str(ult["temp_sec"])+"°C",
                       delta="⚠️" if ult["temp_sec"]>35 else "✓",
                       delta_color="inverse" if ult["temp_sec"]>35 else "normal")
            cc2.metric("Hum. Container",  str(ult["hum_sec"])+"%",
                       delta="⚠️" if ult["hum_sec"]>70 else "✓",
                       delta_color="inverse" if ult["hum_sec"]>70 else "normal")
            cc3.metric("Temp. Bóveda",    str(ult["temp_prim"])+"°C",
                       delta="⚠️" if ult["temp_prim"]>30 else "✓",
                       delta_color="inverse" if ult["temp_prim"]>30 else "normal")
            cc4.metric("Hum. Bóveda",     str(ult["hum_prim"])+"%",
                       delta="⚠️" if ult["hum_prim"]>60 else "✓",
                       delta_color="inverse" if ult["hum_prim"]>60 else "normal")

    with col_b:
        st.subheader("🚨 Alertas activas")
        if not alertas:
            st.markdown('<div class="alerta-ok">✅ Sin alertas activas</div>',
                        unsafe_allow_html=True)
        for a in alertas[:8]:
            cls = ("alerta-critica" if a["gravedad"]=="CRITICA" else
                   "alerta-alta"    if a["gravedad"]=="ALTA"    else "alerta-media")
            st.markdown(
                '<div class="'+cls+'"><b>'+a["icono"]+" "+a["gravedad"]+
                '</b> · '+a["lote"]+' — '+a["exp"]+'<br>'
                '<small>'+a["msg"]+'</small><br>'
                '<small><i>→ '+a["accion"]+'</i></small></div>',
                unsafe_allow_html=True)

        st.subheader("📊 Stock por explosivo")
        if not inv.empty:
            res = inv.groupby("explosivo").agg(
                Unidades=("cantidad","sum"),
                Lotes=("id_lote","count"),
                Peso_kg=("peso_kg_total","sum")
            ).reset_index()
            st.dataframe(res, use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO: INVENTARIO
# ══════════════════════════════════════════════════════════════════════════════
def mod_inventario():
    st.title("📥 Inventario y Kardex")
    if not puede("operar"):
        st.warning("Solo lectura — sin permisos de operación.")

    tab1,tab2,tab3,tab4 = st.tabs([
        "📦 Inventario","➕ Ingreso","📤 Despacho","↩️ Devolución"
    ])

    with tab1:
        inv = get_inv()
        inv["estado_calc"] = inv.apply(clasificar, axis=1)
        fil = st.selectbox("Filtrar",
            ["Todos"]+sorted(inv["estado_calc"].unique().tolist()))
        df_f = inv if fil=="Todos" else inv[inv["estado_calc"]==fil]
        st.dataframe(df_f.drop(columns=["qr_data"],errors="ignore"),
                     use_container_width=True, hide_index=True)
        st.caption("Total: "+str(len(df_f))+" lotes")
        st.subheader("📋 Libro de control (movimientos)")
        movs = get_movs()
        st.dataframe(movs, use_container_width=True, hide_index=True)

    with tab2:
        if not puede("operar"):
            st.info("Sin permiso para registrar ingresos.")
            return
        st.subheader("Registrar nuevo lote")
        # Verificar turno
        turno = turno_activo()
        if not turno:
            st.warning("⚠️ No hay turno activo. El jefe de turno debe iniciar el turno primero.")
        conn2 = get_conn()
        provs_hab = pd.read_sql(
            "SELECT nombre FROM proveedores WHERE habilitado=1", conn2
        )["nombre"].tolist()
        conn2.close()
        with st.form("form_ing"):
            c1,c2 = st.columns(2)
            exp   = c1.selectbox("Explosivo",list(EXPLOSIVOS_CFG.keys()))
            cant  = c2.number_input("Cantidad",min_value=1,value=5)
            c3,c4 = st.columns(2)
            prov  = c3.selectbox("Proveedor habilitado",provs_hab)
            guia  = c4.text_input("N° Guía","GU-"+str(date.today().year)+"-")
            c5,c6 = st.columns(2)
            f_venc= c5.date_input("Fecha vencimiento",
                                  value=date.today()+timedelta(days=365))
            oper  = c6.text_input("Operador",st.session_state["nombre"])
            obs   = st.text_area("Observaciones",height=60)
            sub   = st.form_submit_button("✅ Registrar ingreso",type="primary")

        if sub:
            cfg = EXPLOSIVOS_CFG[exp]
            peso_nuevo = int(cant)*cfg["peso_kg"]
            peso_actual= peso_en_almacen(cfg["almacen"])
            kg_max     = CAPACIDADES[cfg["almacen"]]["kg_max"]
            if peso_actual+peso_nuevo > kg_max:
                st.error("🚫 BLOQUEADO: La capacidad máxima del "+cfg["almacen"]+
                         " se superaría.\n\nActual: "+str(round(peso_actual,1))+" kg · "+
                         "Nuevo lote: "+str(round(peso_nuevo,1))+" kg · "+
                         "Máximo: "+str(kg_max)+" kg.\n\n"+
                         "Espere a que haya espacio disponible antes de ingresar.")
            else:
                pref  = exp[:4].upper().replace(" ","_")
                id_l  = pref+"-"+str(date.today().year)+"-"+uuid.uuid4().hex[:4].upper()
                qr_d  = json.dumps({"id":id_l,"exp":exp,"cant":int(cant),
                                    "venc":str(f_venc),"alm":cfg["almacen"]})
                conn2 = get_conn()
                conn2.execute(
                    "INSERT INTO inventario VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (id_l,exp,cfg["tipo"],int(cant),cfg["unidad"],
                     round(peso_nuevo,2),str(date.today()),str(f_venc),
                     prov,guia,oper,cfg["almacen"],qr_d,"Vigente"))
                conn2.execute(
                    "INSERT INTO movimientos VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    ("MOV-"+uuid.uuid4().hex[:6].upper(),id_l,exp,"Ingreso",
                     int(cant),datetime.now().strftime("%Y-%m-%d %H:%M"),
                     oper,"-",guia,
                     turno[3] if turno else "Sin turno",obs))
                conn2.commit(); conn2.close()
                st.success("✅ Lote "+id_l+" registrado en "+cfg["almacen"])
                st.info("📱 QR generado internamente. ID: "+id_l)
                st.rerun()

    with tab3:
        if not puede("operar"):
            st.info("Sin permiso para registrar despachos.")
            return
        st.subheader("Registrar despacho (FIFO automático)")
        st.info("El sistema selecciona automáticamente el lote más antiguo por explosivo (FIFO normativo).")
        inv2 = get_inv()
        inv2_vig = inv2[~inv2["estado"].str.contains("Vencido",na=False)]

        with st.form("form_desp"):
            c1,c2 = st.columns(2)
            exp_d = c1.selectbox("Explosivo",list(EXPLOSIVOS_CFG.keys()))
            # FIFO: lote más antiguo de ese explosivo
            lotes_exp = inv2_vig[inv2_vig["explosivo"]==exp_d].sort_values("fecha_ingreso")
            if lotes_exp.empty:
                c2.warning("Sin stock vigente para "+exp_d)
                lote_fifo = None
            else:
                lote_fifo = lotes_exp.iloc[0]
                c2.info("Lote FIFO: "+str(lote_fifo["id_lote"])+
                        " · "+str(lote_fifo["cantidad"])+" "+str(lote_fifo["unidad"])+
                        " · Ingresó: "+str(lote_fifo["fecha_ingreso"]))
            c3,c4 = st.columns(2)
            cant_d= c3.number_input("Cantidad",min_value=1,
                                    max_value=int(lote_fifo["cantidad"]) if lote_fifo is not None else 1)
            dest  = c4.selectbox("Destino",list(RUTAS.keys()))
            c5,c6 = st.columns(2)
            conn3 = get_conn()
            vehs_ok = pd.read_sql(
                "SELECT patente FROM vehiculos WHERE estado='Operativo'",conn3
            )["patente"].tolist()
            conn3.close()
            veh   = c5.selectbox("Vehículo operativo",vehs_ok if vehs_ok else ["Sin vehículos operativos"])
            orden = c6.text_input("N° Orden","ORD-"+str(date.today().year)+"-")
            obs_d = st.text_area("Observaciones",height=50)
            sub_d = st.form_submit_button("📤 Confirmar despacho",type="primary")

        if sub_d and lote_fifo is not None:
            turno2 = turno_activo()
            conn3  = get_conn()
            conn3.execute(
                "UPDATE inventario SET cantidad=cantidad-?, peso_kg_total=peso_kg_total-? WHERE id_lote=?",
                (int(cant_d),
                 round(int(cant_d)*EXPLOSIVOS_CFG[exp_d]["peso_kg"],2),
                 lote_fifo["id_lote"]))
            conn3.execute(
                "INSERT INTO movimientos VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                ("MOV-"+uuid.uuid4().hex[:6].upper(),
                 lote_fifo["id_lote"],exp_d,"Despacho",int(cant_d),
                 datetime.now().strftime("%Y-%m-%d %H:%M"),
                 st.session_state["nombre"],dest,orden,
                 turno2[3] if turno2 else "Sin turno",obs_d))
            r = RUTAS[dest]
            conn3.execute(
                "INSERT INTO viajes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("VJ-"+uuid.uuid4().hex[:5].upper(),veh,dest,
                 st.session_state["nombre"],exp_d,int(cant_d),
                 datetime.now().strftime("%Y-%m-%d %H:%M"),
                 (datetime.now()+timedelta(minutes=r["tiempo_min"])).strftime("%Y-%m-%d %H:%M"),
                 r["dist_km"],r["tiempo_min"],r["tiempo_min"],0,
                 "En tiempo",turno2[3] if turno2 else "Sin turno"))
            conn3.commit(); conn3.close()
            st.success("✅ Despacho registrado. Viaje iniciado hacia "+dest+
                       " · Tiempo estimado: "+str(r["tiempo_min"])+" min.")
            st.rerun()

    with tab4:
        if not puede("operar"):
            st.info("Sin permiso para registrar devoluciones.")
            return
        st.subheader("Registrar devolución de explosivos no usados")
        st.info("Use este módulo para reingresar material no utilizado en tronadura. NO es un ingreso nuevo.")
        inv3  = get_inv()
        lotes = inv3["id_lote"].tolist()
        with st.form("form_dev"):
            c1,c2 = st.columns(2)
            lote_d= c1.selectbox("Lote a devolver",lotes)
            cant_v= c2.number_input("Cantidad a devolver",min_value=1,value=1)
            motivo= st.text_area("Motivo de devolución (tronadura, lote, observaciones)",height=70)
            sub_v = st.form_submit_button("↩️ Registrar devolución",type="primary")
        if sub_v:
            turno3= turno_activo()
            conn4 = get_conn()
            row_l = conn4.execute(
                "SELECT explosivo FROM inventario WHERE id_lote=?",
                (lote_d,)
            ).fetchone()
            if row_l:
                exp_v = row_l[0]
                pku   = EXPLOSIVOS_CFG.get(exp_v,{}).get("peso_kg",0)
                conn4.execute(
                    "UPDATE inventario SET cantidad=cantidad+?, peso_kg_total=peso_kg_total+? WHERE id_lote=?",
                    (int(cant_v),round(int(cant_v)*pku,2),lote_d))
                conn4.execute(
                    "INSERT INTO movimientos VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    ("MOV-"+uuid.uuid4().hex[:6].upper(),lote_d,exp_v,"Devolucion",
                     int(cant_v),datetime.now().strftime("%Y-%m-%d %H:%M"),
                     st.session_state["nombre"],"-","DEV-"+uuid.uuid4().hex[:4].upper(),
                     turno3[3] if turno3 else "Sin turno",motivo))
                conn4.commit()
            conn4.close()
            st.success("✅ Devolución de "+str(cant_v)+" unidades registrada en lote "+lote_d)
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO: ALERTAS
# ══════════════════════════════════════════════════════════════════════════════
def mod_alertas():
    st.title("🚨 Alertas del Sistema")
    alertas = generar_alertas()
    nc = len([a for a in alertas if a["gravedad"]=="CRITICA"])
    na = len([a for a in alertas if a["gravedad"]=="ALTA"])
    nm = len([a for a in alertas if a["gravedad"]=="MEDIA"])
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Total",len(alertas))
    c2.metric("🚨 Críticas",nc)
    c3.metric("⚠️ Altas",   na)
    c4.metric("⚡ Medias",  nm)
    st.divider()
    fil = st.selectbox("Filtrar",["Todas","CRITICA","ALTA","MEDIA"])
    af  = alertas if fil=="Todas" else [a for a in alertas if a["gravedad"]==fil]
    if not af:
        st.markdown('<div class="alerta-ok">✅ Sin alertas en esta categoría</div>',
                    unsafe_allow_html=True)
    for a in af:
        cls = ("alerta-critica" if a["gravedad"]=="CRITICA" else
               "alerta-alta"    if a["gravedad"]=="ALTA"    else "alerta-media")
        st.markdown(
            '<div class="'+cls+'">'+
            '<b>'+a["icono"]+" "+a["gravedad"]+'</b> &nbsp;|&nbsp; '+
            '<b>Ref:</b> '+a["lote"]+' &nbsp;|&nbsp; <b>Área:</b> '+a["exp"]+'<br>'+
            '<b>Detalle:</b> '+a["msg"]+'<br>'+
            '<b>Acción normativa:</b> <i>'+a["accion"]+'</i></div>',
            unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO: ACCESOS
# ══════════════════════════════════════════════════════════════════════════════
def mod_accesos():
    st.title("🚪 Control de Acceso al Polvorín")
    personas = personas_dentro()
    t1,t2,t3 = st.tabs(["📋 Registro","➕ Nuevo acceso","🔄 Turno"])

    with t1:
        c1,c2,c3 = st.columns(3)
        c1.metric("Personas dentro ahora", str(personas)+"/"+str(MAX_PERSONAS),
                  delta_color="inverse" if personas>=MAX_PERSONAS else "normal")
        conn = get_conn()
        acc  = pd.read_sql("SELECT * FROM accesos ORDER BY fecha_hora DESC LIMIT 50",conn)
        hoy_acc = pd.read_sql(
            "SELECT COUNT(*) as n FROM accesos WHERE fecha_hora LIKE ?",
            conn,(str(date.today())+"%",)
        ).iloc[0]["n"]
        conn.close()
        c2.metric("Accesos hoy",int(hoy_acc))
        c3.metric("Límite normativo",str(MAX_PERSONAS)+" personas")
        if personas>=MAX_PERSONAS:
            st.error("🚫 Límite de personas alcanzado. Espere a que salga personal.")
        st.dataframe(acc,use_container_width=True,hide_index=True)

    with t2:
        if not puede("operar"):
            st.info("Sin permiso.")
            return
        personas2 = personas_dentro()
        with st.form("form_acc"):
            c1,c2 = st.columns(2)
            conn2 = get_conn()
            ops   = pd.read_sql(
                "SELECT nombre FROM usuarios WHERE rol='operario' AND activo=1",conn2
            )["nombre"].tolist()
            conn2.close()
            oper  = c1.selectbox("Operador",ops)
            tipo  = c2.selectbox("Tipo",["Ingreso","Egreso"])
            motivo= st.selectbox("Motivo",
                ["Despacho","Inventario","Inspección","Recepción","Otro"])
            sub   = st.form_submit_button("✅ Registrar",type="primary")
        if sub:
            if tipo=="Ingreso" and personas2>=MAX_PERSONAS:
                st.error("🚫 BLOQUEADO: Límite de "+str(MAX_PERSONAS)+
                         " personas simultáneas alcanzado.\n"+
                         "Espere a que salga personal antes de ingresar.")
            else:
                turno4= turno_activo()
                conn2 = get_conn()
                conn2.execute(
                    "INSERT INTO accesos VALUES (?,?,?,?,?,?)",
                    (uuid.uuid4().hex[:8].upper(),oper,tipo,
                     datetime.now().strftime("%Y-%m-%d %H:%M"),
                     motivo,turno4[3] if turno4 else "Sin turno"))
                conn2.commit(); conn2.close()
                st.success("✅ "+tipo+" de "+oper+" registrado.")
                st.rerun()

    with t3:
        st.subheader("Gestión de turno")
        if not (puede("operar") and st.session_state["rol"] in ["jefe_turno","administrador"]):
            st.info("Solo el jefe de turno puede gestionar turnos.")
            return
        turno5= turno_activo()
        if turno5:
            st.success("🕐 Turno "+turno5[3]+" activo desde "+str(turno5[4]))
            if st.button("⏹ Cerrar turno actual",type="secondary"):
                conn3=get_conn()
                conn3.execute(
                    "UPDATE turnos SET fin=?, estado='Cerrado' WHERE id=?",
                    (datetime.now().strftime("%Y-%m-%d %H:%M"),turno5[0]))
                conn3.commit(); conn3.close()
                st.success("Turno cerrado.")
                st.rerun()
        else:
            with st.form("form_turno"):
                tipo_t= st.selectbox("Tipo de turno",["Mañana","Tarde","Noche"])
                sub_t = st.form_submit_button("▶️ Iniciar turno",type="primary")
            if sub_t:
                conn3=get_conn()
                conn3.execute(
                    "INSERT INTO turnos VALUES (?,?,?,?,?,?)",
                    (uuid.uuid4().hex[:8].upper(),st.session_state["nombre"],
                     tipo_t,datetime.now().strftime("%Y-%m-%d %H:%M"),"",
                     "Activo"))
                conn3.commit(); conn3.close()
                st.success("✅ Turno "+tipo_t+" iniciado.")
                st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO: CONDICIONES AMBIENTALES
# ══════════════════════════════════════════════════════════════════════════════
def mod_condiciones():
    st.title("🌡️ Condiciones Ambientales")
    st.caption("Prototipo: datos simulados. En producción: conectar sensores IoT vía API.")
    if st.button("🔄 Actualizar lecturas"):
        conn=get_conn()
        conn.execute(
            "INSERT INTO condiciones VALUES (?,?,?,?,?,?)",
            ("COND-"+uuid.uuid4().hex[:6].upper(),
             datetime.now().strftime("%Y-%m-%d %H:%M"),
             round(random.uniform(14,38),1),round(random.uniform(45,85),1),
             round(random.uniform(10,26),1),round(random.uniform(40,70),1)))
        conn.commit(); conn.close()
        st.rerun()
    cond = get_condiciones()
    if cond.empty:
        st.info("Sin datos de condiciones.")
        return
    ult = cond.iloc[-1]
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("🌡️ Temp. Container",str(ult["temp_sec"])+"°C",
              delta="⚠️ Alta" if ult["temp_sec"]>35 else "✓",
              delta_color="inverse" if ult["temp_sec"]>35 else "normal")
    c2.metric("💧 Hum. Container",str(ult["hum_sec"])+"%",
              delta="⚠️ Alta" if ult["hum_sec"]>70 else "✓",
              delta_color="inverse" if ult["hum_sec"]>70 else "normal")
    c3.metric("🌡️ Temp. Bóveda",str(ult["temp_prim"])+"°C",
              delta="⚠️ Alta" if ult["temp_prim"]>30 else "✓",
              delta_color="inverse" if ult["temp_prim"]>30 else "normal")
    c4.metric("💧 Hum. Bóveda",str(ult["hum_prim"])+"%",
              delta="⚠️ Alta" if ult["hum_prim"]>60 else "✓",
              delta_color="inverse" if ult["hum_prim"]>60 else "normal")
    st.divider()
    st.subheader("📈 Histórico 24 horas")
    col_l,col_r = st.columns(2)
    with col_l:
        st.markdown("**Container Secundarios**")
        st.line_chart(cond.set_index("fecha_hora")[["temp_sec","hum_sec"]].tail(24))
    with col_r:
        st.markdown("**Bóveda Primarios**")
        st.line_chart(cond.set_index("fecha_hora")[["temp_prim","hum_prim"]].tail(24))
    st.subheader("📋 Límites normativos")
    lim_df = pd.DataFrame([
        {"Explosivo":k,"Temp. máx (°C)":v["temp_max"],"Hum. máx (%)":v["hum_max"],"Almacén":v["almacen"]}
        for k,v in EXPLOSIVOS_CFG.items()
    ])
    st.dataframe(lim_df,use_container_width=True,hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO: TRASLADOS
# ══════════════════════════════════════════════════════════════════════════════
def mod_traslados():
    st.title("🚛 Flota y Traslados")
    viajes = get_viajes()
    t1,t2,t3 = st.tabs(["📋 Viajes","🚗 Vehículos","📊 Optimización"])

    with t1:
        c1,c2,c3 = st.columns(3)
        c1.metric("Total viajes",len(viajes))
        c2.metric("En tiempo",
                  len(viajes[viajes["estado"]=="En tiempo"]) if not viajes.empty else 0)
        c3.metric("Con demora",
                  len(viajes[viajes["estado"]=="Con demora"]) if not viajes.empty else 0,
                  delta_color="inverse")
        fil = st.selectbox("Filtrar",["Todos","En tiempo","Con demora"])
        df_f= viajes if fil=="Todos" else viajes[viajes["estado"]==fil]
        st.dataframe(df_f,use_container_width=True,hide_index=True)

    with t2:
        conn=get_conn()
        vehs=pd.read_sql("SELECT * FROM vehiculos",conn)
        conn.close()
        st.dataframe(vehs,use_container_width=True,hide_index=True)
        st.caption("⚠️ Vehículos con revisión técnica vencida no pueden transportar explosivos — DS 132.")
        if puede("todo"):
            st.subheader("Actualizar revisión técnica")
            with st.form("form_veh"):
                patente=st.selectbox("Patente",vehs["patente"].tolist())
                nueva_rt=st.date_input("Nueva fecha rev. técnica",
                                       value=date.today()+timedelta(days=365))
                sub_veh=st.form_submit_button("Actualizar")
            if sub_veh:
                conn=get_conn()
                conn.execute(
                    "UPDATE vehiculos SET rev_tecnica=?, estado='Operativo' WHERE patente=?",
                    (str(nueva_rt),patente))
                conn.commit(); conn.close()
                st.success("✅ Revisión técnica actualizada.")
                st.rerun()

    with t3:
        st.subheader("Análisis de optimización por ruta")
        if viajes.empty:
            st.info("Sin datos de viajes.")
            return
        rows=[]
        for rn,r in RUTAS.items():
            vr=viajes[viajes["ruta"]==rn]
            tp=vr["t_real"].mean() if not vr.empty else r["tiempo_min"]
            dp=vr["demora"].mean()  if not vr.empty else 0
            ok=len(vr[vr["estado"]=="En tiempo"])/len(vr)*100 if not vr.empty else 100
            rows.append({"Ruta":rn,"Dist.(km)":r["dist_km"],
                         "T.esp.(min)":r["tiempo_min"],
                         "T.prom.(min)":round(tp,1),
                         "Demora prom.(min)":round(dp,1),
                         "% en tiempo":str(round(ok,0))+"%",
                         "Vel.lím.(km/h)":r["limite_kmh"]})
        df_opt=pd.DataFrame(rows)
        st.dataframe(df_opt,use_container_width=True,hide_index=True)
        idx_min=df_opt["Demora prom.(min)"].idxmin()
        idx_max=df_opt["Demora prom.(min)"].idxmax()
        st.success("✅ Ruta más eficiente: "+df_opt.loc[idx_min,"Ruta"])
        st.warning("⚠️ Ruta con mayor demora: "+df_opt.loc[idx_max,"Ruta"])

# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO: REPORTES
# ══════════════════════════════════════════════════════════════════════════════
def mod_reportes():
    import openpyxl
    from openpyxl.styles import PatternFill,Font,Alignment,Border,Side
    from openpyxl.utils import get_column_letter
    st.title("📋 Reportes")
    st.info("Reportes listos para entregar a la Autoridad Fiscalizadora (DGMN/SERNAGEOMIN).")
    tipo  = st.selectbox("Tipo de reporte",[
        "Reporte mensual completo","Reporte de discrepancias",
        "Reporte de movimientos","Reporte de condiciones","Reporte de flota"])
    periodo=st.date_input("Período",value=date.today())
    if st.button("📥 Generar reporte Excel",type="primary"):
        inv    = get_inv()
        inv["estado_calc"]=inv.apply(clasificar,axis=1)
        movs   = get_movs()
        viajes = get_viajes()
        cond   = get_condiciones()
        alertas= generar_alertas()
        output = io.BytesIO()
        wb=openpyxl.Workbook()
        HF=PatternFill("solid",fgColor="1F3864")
        FF=Font(bold=True,color="FFFFFF",size=10)
        BD=Border(left=Side(style="thin"),right=Side(style="thin"),
                  top=Side(style="thin"),bottom=Side(style="thin"))
        FILL={"CRITICA":PatternFill("solid",fgColor="FFCCCC"),
              "ALTA":   PatternFill("solid",fgColor="FFEB9C"),
              "VIGENTE":PatternFill("solid",fgColor="C6EFCE"),
              "VENCIDO":PatternFill("solid",fgColor="FFCCCC"),}

        def escribir(ws,df,titulo,sub=""):
            ws.append([titulo])
            ws.cell(1,1).font=Font(bold=True,size=13,color="1F3864")
            ws.append([sub or "Generado: "+datetime.now().strftime("%Y-%m-%d %H:%M")])
            ws.cell(2,1).font=Font(italic=True,size=10,color="595959")
            ws.append([])
            ws.append(list(df.columns))
            for ci,_ in enumerate(df.columns,1):
                c=ws.cell(4,ci); c.fill=HF; c.font=FF; c.border=BD
                c.alignment=Alignment(horizontal="center",wrap_text=True)
            for ri,row in enumerate(df.itertuples(index=False),5):
                for ci,val in enumerate(row,1):
                    c=ws.cell(ri,ci,value=str(val) if val is not None else "")
                    c.border=BD; c.alignment=Alignment(wrap_text=True,vertical="center")
                    vs=str(val).upper()
                    for k,f in FILL.items():
                        if k in vs: c.fill=f; break
            for col in ws.columns:
                ml=max((len(str(c.value)) if c.value else 0) for c in col)
                ws.column_dimensions[get_column_letter(col[0].column)].width=min(ml+4,40)

        ws1=wb.active; ws1.title="Inventario"
        escribir(ws1,inv.drop(columns=["qr_data"],errors="ignore"),
                 "INVENTARIO — "+str(periodo))
        if tipo in ["Reporte mensual completo","Reporte de movimientos"]:
            ws2=wb.create_sheet("Movimientos")
            escribir(ws2,movs,"MOVIMIENTOS — "+str(periodo))
        if tipo in ["Reporte mensual completo","Reporte de discrepancias"]:
            ws3=wb.create_sheet("Alertas")
            df_a=(pd.DataFrame(alertas) if alertas
                  else pd.DataFrame(columns=["gravedad","lote","exp","msg","accion"]))
            escribir(ws3,df_a,"ALERTAS Y DISCREPANCIAS — "+str(periodo))
        if tipo in ["Reporte mensual completo","Reporte de condiciones"]:
            ws4=wb.create_sheet("Condiciones")
            escribir(ws4,cond,"CONDICIONES AMBIENTALES — "+str(periodo))
        if tipo in ["Reporte mensual completo","Reporte de flota"]:
            ws5=wb.create_sheet("Flota")
            escribir(ws5,viajes,"FLOTA Y TRASLADOS — "+str(periodo))
        ws_r=wb.create_sheet("Resumen Ejecutivo")
        def ce(kw):
            if "estado_calc" not in inv.columns: return "N/A"
            return len(inv[inv["estado_calc"].str.contains(kw,na=False)])
        nc2=len([a for a in alertas if a["gravedad"]=="CRITICA"])
        for fila in [
            ["REPORTE OFICIAL — POLVORÍN MINERO",""],
            ["Período",str(periodo)],
            ["Generado",datetime.now().strftime("%Y-%m-%d %H:%M")],["",""],
            ["INVENTARIO",""],
            ["Total lotes",len(inv)],["Vigentes",ce("Vigente")],
            ["Vencidos",ce("Vencido")],["Por vencer",ce("Por vencer")],["",""],
            ["ALERTAS",""],["Total",len(alertas)],["Críticas",nc2],["",""],
            ["TRASLADOS",""],["Total viajes",len(viajes)],
            ["Con demora",len(viajes[viajes["estado"]=="Con demora"]) if not viajes.empty else 0],
            ["",""],["NORMATIVA APLICABLE",""],
            ["DS 132 SERNAGEOMIN","Reglamento de Seguridad Minera"],
            ["Ley 17.798","Control de Armas y Explosivos"],
            ["DGMN 003048/2020","Almacenamiento productos Ley 17.798"],
        ]:
            ws_r.append(fila)
        ws_r["A1"].font=Font(bold=True,size=13,color="1F3864")
        ws_r.column_dimensions["A"].width=35
        ws_r.column_dimensions["B"].width=45
        wb.save(output); output.seek(0)
        st.download_button(
            label="📥 Descargar "+tipo,data=output,
            file_name="reporte_polvorin_"+str(periodo)+".xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.success("✅ Reporte generado.")

# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO: KPIs
# ══════════════════════════════════════════════════════════════════════════════
def mod_kpis():
    st.title("📊 KPIs — Indicadores de Desempeño")
    st.info("Comparación entre línea base (sin sistema), meta a 6 meses y meta a 12 meses.")
    conn=get_conn()
    kpis=pd.read_sql("SELECT * FROM kpis",conn)
    conn.close()
    if kpis.empty:
        st.info("Sin KPIs configurados.")
        return
    areas=kpis["area"].unique().tolist()
    for area in areas:
        st.subheader("📌 Área: "+area)
        df_a=kpis[kpis["area"]==area]
        for _,k in df_a.iterrows():
            with st.expander(k["nombre"]+" ("+k["unidad"]+")"):
                st.caption(k["descripcion"])
                c1,c2,c3 = st.columns(3)
                c1.metric("📍 Línea base",str(k["valor_base"])+" "+k["unidad"])
                c2.metric("🎯 Meta 6 meses",str(k["meta_6m"])+" "+k["unidad"],
                          delta=str(round(k["meta_6m"]-k["valor_base"],1))+" "+k["unidad"])
                c3.metric("🏆 Meta 12 meses",str(k["meta_12m"])+" "+k["unidad"],
                          delta=str(round(k["meta_12m"]-k["valor_base"],1))+" "+k["unidad"])
                prog_df=pd.DataFrame({
                    "Etapa":["Línea base","Meta 6m","Meta 12m"],
                    k["nombre"]:[k["valor_base"],k["meta_6m"],k["meta_12m"]]
                })
                st.bar_chart(prog_df.set_index("Etapa"))
    st.divider()
    st.subheader("📋 Tabla resumen de todos los KPIs")
    st.dataframe(kpis.drop(columns=["id"],errors="ignore"),
                 use_container_width=True,hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO: AUDITORÍA
# ══════════════════════════════════════════════════════════════════════════════
def mod_auditoria():
    st.title("🔍 Auditoría Física")
    st.info("Conteo físico mensual. El sistema compara con el registro digital y detecta discrepancias.")
    conn=get_conn()
    aud=pd.read_sql("SELECT * FROM auditorias ORDER BY fecha DESC",conn)
    conn.close()
    t1,t2=st.tabs(["📋 Historial","➕ Nuevo conteo"])
    with t1:
        if aud.empty:
            st.info("Sin auditorías registradas.")
        else:
            st.dataframe(aud,use_container_width=True,hide_index=True)
    with t2:
        if not puede("todo"):
            st.info("Solo el administrador puede realizar auditorías.")
            return
        inv=get_inv()
        st.markdown("**Ingresa el conteo físico real para cada explosivo:**")
        with st.form("form_aud"):
            conteos={}
            for exp in EXPLOSIVOS_CFG:
                stock_sis=int(inv[inv["explosivo"]==exp]["cantidad"].sum())
                conteos[exp]=st.number_input(
                    exp+" (sistema: "+str(stock_sis)+" "+EXPLOSIVOS_CFG[exp]["unidad"]+")",
                    min_value=0,value=stock_sis)
            obs_a=st.text_area("Observaciones generales",height=60)
            sub_a=st.form_submit_button("✅ Confirmar conteo",type="primary")
        if sub_a:
            conn=get_conn()
            for exp,cnt_real in conteos.items():
                stock_sis=int(inv[inv["explosivo"]==exp]["cantidad"].sum())
                diff=cnt_real-stock_sis
                est="Aprobada" if diff==0 else ("Discrepancia leve" if abs(diff)<=2 else "Discrepancia crítica")
                conn.execute(
                    "INSERT INTO auditorias VALUES (?,?,?,?,?,?,?,?,?)",
                    (uuid.uuid4().hex[:8].upper(),str(date.today()),
                     st.session_state["nombre"],exp,stock_sis,cnt_real,diff,est,obs_a))
            conn.commit(); conn.close()
            st.success("✅ Auditoría registrada.")
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO: ADMINISTRACIÓN
# ══════════════════════════════════════════════════════════════════════════════
def mod_admin():
    st.title("🏢 Administración del Sistema")
    if not puede("todo"):
        st.error("Acceso restringido al administrador.")
        return
    t1,t2,t3,t4=st.tabs(["👷 Usuarios","🏢 Proveedores","⚙️ Configuración","🔑 Credenciales"])
    with t1:
        conn=get_conn()
        users=pd.read_sql(
            "SELECT id,nombre,usuario,rol,licencia_venc,activo FROM usuarios",conn)
        conn.close()
        st.dataframe(users,use_container_width=True,hide_index=True)
        st.subheader("Actualizar licencia de manipulador")
        with st.form("form_lic"):
            uid=st.selectbox("Usuario",users["usuario"].tolist())
            nueva_lic=st.date_input("Nueva fecha vencimiento licencia",
                                    value=date.today()+timedelta(days=365))
            sub_lic=st.form_submit_button("Actualizar")
        if sub_lic:
            conn=get_conn()
            conn.execute(
                "UPDATE usuarios SET licencia_venc=? WHERE usuario=?",
                (str(nueva_lic),uid))
            conn.commit(); conn.close()
            st.success("✅ Licencia actualizada.")
            st.rerun()
        st.subheader("Crear nuevo usuario")
        with st.form("form_usr"):
            c1,c2=st.columns(2)
            n_nom=c1.text_input("Nombre completo")
            n_usr=c2.text_input("Usuario")
            c3,c4=st.columns(2)
            n_pin=c3.text_input("PIN",type="password")
            n_rol=c4.selectbox("Rol",["operario","jefe_turno","solo_lectura"])
            n_lic=st.date_input("Vencimiento licencia",
                                 value=date.today()+timedelta(days=365))
            sub_usr=st.form_submit_button("Crear usuario")
        if sub_usr:
            conn=get_conn()
            conn.execute("INSERT INTO usuarios VALUES (?,?,?,?,?,?,1)",
                         ("USR-"+uuid.uuid4().hex[:6].upper(),
                          n_nom,n_usr,hash_pin(n_pin),n_rol,str(n_lic)))
            conn.commit(); conn.close()
            st.success("✅ Usuario "+n_usr+" creado.")
            st.rerun()

    with t2:
        conn=get_conn()
        provs=pd.read_sql("SELECT * FROM proveedores",conn)
        conn.close()
        st.dataframe(provs,use_container_width=True,hide_index=True)
        st.subheader("Agregar proveedor habilitado")
        with st.form("form_prov"):
            c1,c2=st.columns(2)
            p_nom=c1.text_input("Nombre proveedor")
            p_rut=c2.text_input("RUT")
            p_cont=st.text_input("Contacto/email")
            sub_p=st.form_submit_button("Agregar")
        if sub_p:
            conn=get_conn()
            conn.execute("INSERT INTO proveedores VALUES (?,?,?,?,1)",
                         ("PROV-"+uuid.uuid4().hex[:6].upper(),p_nom,p_rut,p_cont))
            conn.commit(); conn.close()
            st.success("✅ Proveedor "+p_nom+" agregado.")
            st.rerun()

    with t3:
        st.subheader("Parámetros normativos del polvorín")
        cfg_df=pd.DataFrame([
            {"Explosivo":k,"Tipo":v["tipo"],"Unidad":v["unidad"],
             "Peso/ud(kg)":v["peso_kg"],"Stock mín":v["stock_min"],
             "Vida útil(d)":v["vida_dias"],"Almacén":v["almacen"],
             "Temp.máx(°C)":v["temp_max"],"Hum.máx(%)":v["hum_max"]}
            for k,v in EXPLOSIVOS_CFG.items()
        ])
        st.dataframe(cfg_df,use_container_width=True,hide_index=True)
        st.subheader("Capacidades máximas (fórmula S = 1,5 · ∛W)")
        cap_df=pd.DataFrame([
            {"Almacén":k,"Kg máx":v["kg_max"],"Distancia seg.(m)":v["dist_m"],
             "Alerta 90%(kg)":round(v["kg_max"]*0.9,1),
             "Bloqueo 100%(kg)":v["kg_max"]}
            for k,v in CAPACIDADES.items()
        ])
        st.dataframe(cap_df,use_container_width=True,hide_index=True)
        st.subheader("Rutas de traslado")
        rut_df=pd.DataFrame([
            {"Ruta":k,"Dist.(km)":v["dist_km"],
             "T.esperado(min)":v["tiempo_min"],"Vel.lím.(km/h)":v["limite_kmh"]}
            for k,v in RUTAS.items()
        ])
        st.dataframe(rut_df,use_container_width=True,hide_index=True)

    with t4:
        st.subheader("🔑 Credenciales de acceso del sistema")
        st.warning("⚠️ Esta sección solo es visible para el administrador. Cambie estos datos en producción.")
        cred=pd.DataFrame([
            {"Rol":"Administrador","Usuario":"admin","PIN":"1234",
             "Nota":"Acceso total al sistema"},
            {"Rol":"Jefe de Turno","Usuario":"jefe_turno","PIN":"5678",
             "Nota":"Gestión operativa y reportes"},
            {"Rol":"Operario","Usuario":"operario1","PIN":"9012",
             "Nota":"Licencia vigente — operaciones diarias"},
            {"Rol":"Operario","Usuario":"operario2","PIN":"3456",
             "Nota":"Licencia vigente — operaciones diarias"},
            {"Rol":"Inspector","Usuario":"inspector","PIN":"7890",
             "Nota":"Solo lectura — sin operaciones"},
            {"Rol":"Operario (lic. vencida)","Usuario":"operario3","PIN":"1111",
             "Nota":"Bloqueado — licencia vencida hace 10 días"},
        ])
        st.dataframe(cred,use_container_width=True,hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO: MANUAL
# ══════════════════════════════════════════════════════════════════════════════
def mod_manual():
    st.title("📖 Manual de Usuario")
    t1,t2,t3=st.tabs(["🚀 Guía rápida","📚 Tutoriales","📘 Glosario minero"])
    with t1:
        st.subheader("Operaciones más comunes")
        ops=[
            ("📥 Registrar ingreso de material",
             ["1. Ir a Inventario → Ingreso",
              "2. Seleccionar el explosivo y cantidad",
              "3. Ingresar proveedor habilitado y N° de guía",
              "4. Confirmar fecha de vencimiento",
              "5. El sistema verifica capacidad disponible y registra automáticamente"]),
            ("📤 Despachar explosivos",
             ["1. Ir a Inventario → Despacho",
              "2. Seleccionar el tipo de explosivo",
              "3. El sistema selecciona automáticamente el lote más antiguo (FIFO)",
              "4. Ingresar destino, vehículo y N° de orden",
              "5. El sistema registra el viaje y actualiza el inventario"]),
            ("🚪 Registrar ingreso al polvorín",
             ["1. Ir a Accesos → Nuevo acceso",
              "2. Seleccionar operador y tipo (Ingreso/Egreso)",
              "3. El sistema verifica que no se superen 5 personas simultáneas",
              "4. Confirmar y registrar"]),
            ("📋 Generar reporte para la AF",
             ["1. Ir a Reportes",
              "2. Seleccionar tipo de reporte y período",
              "3. Hacer clic en Generar reporte Excel",
              "4. Descargar y entregar a la Autoridad Fiscalizadora"]),
        ]
        for titulo,pasos in ops:
            with st.expander(titulo):
                for p in pasos:
                    st.markdown("- "+p)
    with t2:
        st.subheader("¿Cómo funciona el sistema?")
        tutoriales=[
            ("🔐 Sistema de autenticación",
             "Cada usuario accede con su nombre de usuario y PIN. Los operarios deben tener licencia de manipulador vigente. Si la licencia vence, el sistema bloquea el acceso hasta que el administrador la actualice. El sistema registra qué usuario realizó cada operación."),
            ("⚖️ Control de capacidad máxima",
             "El sistema calcula en tiempo real cuántos kg hay en cada almacén. Cuando se alcanza el 90% de la capacidad, emite una alerta amarilla. Al llegar al 100%, bloquea nuevos ingresos hasta que haya espacio disponible. Los cálculos se basan en la fórmula legal S = 1,5 · ∛W del DS 132."),
            ("📦 FIFO normativo",
             "Al despachar, el sistema selecciona automáticamente el lote más antiguo de cada explosivo. Esto evita que material vencido quede olvidado en el fondo del almacén. No se puede seleccionar manualmente un lote más nuevo si hay uno más antiguo disponible."),
            ("🚨 Sistema de alertas",
             "Las alertas se generan automáticamente sin intervención del operario. Se clasifican en críticas (acción inmediata, color rojo), altas (acción urgente, color amarillo) y medias (seguimiento, color anaranjado). Cada alerta incluye la normativa que la respalda y la acción recomendada."),
            ("🔍 Auditoría física",
             "Una vez al mes el administrador realiza un conteo físico. El sistema compara el conteo real con el registro digital. Si hay diferencias, genera automáticamente un informe de discrepancias con clasificación de gravedad."),
        ]
        for titulo,desc in tutoriales:
            with st.expander(titulo):
                st.markdown(desc)
    with t3:
        st.subheader("Términos del sistema en lenguaje de faena")
        glos=[
            ("ANFO","Mezcla de Nitrato de Amonio y Petróleo (Fuel Oil). Explosivo secundario de uso masivo en tronadura."),
            ("Emulsión","Explosivo industrial de alta potencia y resistencia al agua. Usado en condiciones adversas."),
            ("Fulminante N°8","Detonador primario. Inicia la detonación de los explosivos secundarios."),
            ("FIFO","First In, First Out — Primero que entra, primero que sale. Sistema de rotación de inventario que obliga a usar el material más antiguo antes que el más nuevo."),
            ("Lote","Conjunto de explosivos de un mismo tipo ingresado en una misma recepción, identificado con un código único."),
            ("Guía de despacho","Documento del proveedor que acompaña cada entrega de explosivos. Debe coincidir con lo recibido."),
            ("AF / Autoridad Fiscalizadora","DGMN (Dirección General de Movilización Nacional) o SERNAGEOMIN según corresponda. Organismo que supervisa y autoriza el uso de explosivos."),
            ("Libro de control","Registro obligatorio de todos los movimientos de explosivos. Debe presentarse mensualmente a la AF."),
            ("Manipulador de explosivos","Persona certificada por Sernageomin para operar con explosivos. Debe tener licencia vigente."),
            ("Consumidor habitual","Empresa o persona que usa explosivos regularmente en su operación. Requiere inscripción permanente ante la AF."),
            ("DS 132","Decreto Supremo N°132 de Sernageomin. Reglamento de Seguridad Minera que regula el almacenamiento y uso de explosivos en minería."),
        ]
        for term,defin in glos:
            with st.expander("📘 "+term):
                st.markdown(defin)

# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO: ASISTENTE IA
# ══════════════════════════════════════════════════════════════════════════════
def mod_asistente():
    st.title("💬 Asistente de Apoyo")
    st.warning("⚠️ Este asistente entrega **solo orientación**. Toda decisión debe ser tomada por el operador responsable certificado. No reemplaza el criterio técnico ni la autoridad del manipulador de explosivos.")
    st.divider()
    if "mensajes" not in st.session_state:
        st.session_state["mensajes"] = []

    preguntas_rapidas=[
        "¿Qué hago con un lote vencido?",
        "¿Cuántas personas pueden ingresar al polvorín?",
        "¿Cómo registro una devolución?",
        "¿Cuándo debo notificar a la Autoridad Fiscalizadora?",
        "¿Qué es el FIFO y por qué es obligatorio?",
        "¿Qué dice el DS 132 sobre capacidad máxima?",
    ]

    respuestas_base={
        "lote vencido":"Según la Ley 17.798 (Cap. VIII), un explosivo vencido debe ser destruido por combustión, explosión o detonación controlada, autorizada por la Autoridad Fiscalizadora. El manipulador debe dejar constancia en un acta. En el sistema, el lote aparece como 'Vencido' y queda bloqueado para despacho.",
        "personas":"El límite es 5 personas simultáneas dentro del polvorín, según la normativa vigente. El sistema bloquea automáticamente el registro de nuevos ingresos al alcanzar ese límite. Además, ninguna persona debe permanecer sola dentro del recinto.",
        "devolución":"Use el módulo Inventario → Devolución. Ingrese el lote original, la cantidad a devolver y el motivo. Este registro es diferente a un ingreso nuevo y queda registrado en el libro de control con el tipo 'Devolucion'.",
        "autoridad fiscalizadora":"Debe notificarse a la AF ante: lotes próximos a vencer (menos de 30 días), solicitudes de destrucción de explosivos vencidos, discrepancias significativas en el inventario, y presentación del libro de control mensual. La Resolución DGMN 003048/2020 establece los plazos específicos.",
        "fifo":"FIFO (First In, First Out) es el principio de rotación que obliga a usar primero el material más antiguo. En polvorines es obligatorio para evitar que explosivos vencidos permanezcan almacenados. El sistema lo aplica automáticamente al seleccionar el lote con fecha de ingreso más antigua al despachar.",
        "capacidad máxima":"La capacidad máxima se calcula con la fórmula S = 1,5 · ∛W, donde S es la distancia de seguridad en metros y W es el peso en kg. Despejando W: W = (S/1,5)³. Para el caso hipotético: Container secundarios = 3.500 kg (S=50m), Bóveda primarios = 400 kg (S=25m). El sistema alerta al 90% y bloquea al 100%.",
    }

    col1,col2=st.columns([2,1])
    with col2:
        st.markdown("**Preguntas frecuentes:**")
        for pq in preguntas_rapidas:
            if st.button(pq,use_container_width=True,key="pq_"+pq[:20]):
                st.session_state["mensajes"].append({"rol":"usuario","texto":pq})
                resp="No tengo información específica sobre eso. Consulte el Manual o al jefe de turno."
                for clave,rta in respuestas_base.items():
                    if any(w in pq.lower() for w in clave.split()):
                        resp=rta; break
                st.session_state["mensajes"].append({"rol":"asistente","texto":resp})
                st.rerun()

    with col1:
        for msg in st.session_state["mensajes"]:
            if msg["rol"]=="usuario":
                st.markdown("**👷 Tú:** "+msg["texto"])
            else:
                st.markdown("**🤖 Asistente:** "+msg["texto"])
        st.divider()
        with st.form("form_chat",clear_on_submit=True):
            preg=st.text_input("Tu pregunta:",placeholder="Ej: ¿Qué hago si el sensor marca temperatura alta?")
            sub_chat=st.form_submit_button("Enviar →")
        if sub_chat and preg.strip():
            st.session_state["mensajes"].append({"rol":"usuario","texto":preg})
            resp="No tengo información específica sobre eso. Consulte el Manual de usuario o contacte al jefe de turno."
            for clave,rta in respuestas_base.items():
                if any(w in preg.lower() for w in clave.split()):
                    resp=rta; break
            st.session_state["mensajes"].append({"rol":"asistente","texto":resp})
            st.rerun()
        if st.button("Limpiar conversación",type="secondary"):
            st.session_state["mensajes"]=[]
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
init_db()

if not st.session_state.get("autenticado"):
    pantalla_login()
else:
    modulo = sidebar()
    if   "Estado General" in modulo: mod_dashboard()
    elif "Inventario"     in modulo: mod_inventario()
    elif "Alertas"        in modulo: mod_alertas()
    elif "Accesos"        in modulo: mod_accesos()
    elif "Condiciones"    in modulo: mod_condiciones()
    elif "Traslados"      in modulo: mod_traslados()
    elif "Reportes"       in modulo: mod_reportes()
    elif "KPIs"           in modulo: mod_kpis()
    elif "Auditoría"      in modulo: mod_auditoria()
    elif "Administración" in modulo: mod_admin()
    elif "Manual"         in modulo: mod_manual()
    elif "Asistente"      in modulo: mod_asistente()
