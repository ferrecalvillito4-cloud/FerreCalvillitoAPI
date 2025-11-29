import os
import json
import threading
from datetime import datetime, timedelta
from uuid import uuid4
import asyncio
import traceback

# Importar módulos de persistencia
import productos_api as productos_module
import contactos_persistencia as contactos
import github_persistence as gh
from fastapi import FastAPI, Request, Body
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel, Field
from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv
import fdb
import asyncio
from gestor_imagenes import GestorImagenesProductos

# =============================
# 🚀 Inicialización principal
# =============================
load_dotenv()

# =============================
# 📁 Rutas de archivos (PRIMERO)
# =============================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "conexion_actual.txt")
PRODUCTOS_FILE = os.path.join(SCRIPT_DIR, "productos.json")
DIRECCIONES_FILE = os.path.join(SCRIPT_DIR, "direcciones.json")
TELEFONOS_FILE = os.path.join(SCRIPT_DIR, "telefonos.json")
BACKUP_DIR = os.path.join(SCRIPT_DIR, "backups")
DATA_DIR = os.path.join(SCRIPT_DIR, "data")

# Crear directorios necesarios
os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# =============================
# 📁 Archivos estáticos
# =============================
static_dir = os.path.join(SCRIPT_DIR, "static")
os.makedirs(static_dir, exist_ok=True)

# =============================
# 🚀 Crear aplicación FastAPI
# =============================
app = FastAPI(title="Ferre-Calvillito API")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# =============================
# 🔒 Configuración de CORS
# =============================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================
# 🧠 Middleware de Sesión
# =============================
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "clave_super_secreta_123")
)

# =============================
# 🖼️ CONFIGURACIÓN DE IMÁGENES
# =============================
IMAGENES_DIR = os.path.join(SCRIPT_DIR, "imagenes_productos")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")  # formato: usuario/repo

gestor_imagenes = None

# =============================
# 🔐 Configuración OAuth con Google
# =============================
oauth = OAuth()
oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

# =============================
# 🔥 Cargar cliente Firebird
# =============================
try:
    dll_path = os.path.join(SCRIPT_DIR, "fbclient.dll")
    if os.path.exists(dll_path):
        fdb.load_api(dll_path)
        print(f"🧩 fbclient.dll cargado desde: {dll_path}")
    else:
        print("⚠️ No se encontró fbclient.dll en el directorio del proyecto.")
except Exception as e:
    print("❌ Error al cargar fbclient.dll:", e)

# =============================
# 🧠 Estado Global
# =============================
mensajes: list[dict] = []
direcciones: list[dict] = []
telefonos: list[dict] = []
productos_api: list[dict] = []

# =============================
# 🧠 Leer cadena de conexión
# =============================
def leer_cadena_conexion():
    if not os.path.exists(CONFIG_PATH):
        return None
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        contenido = f.read().strip()
    if not contenido:
        return None
    partes = {k.strip().lower(): v.strip() for k, v in (s.split("=", 1) for s in contenido.split(";") if "=" in s)}
    return partes if "database" in partes else None

# =============================
# 🗑️ Limpieza de mensajes
# =============================
def limpiar_mensajes_antiguos():
    """Elimina mensajes con más de 30 días de antigüedad"""
    global mensajes
    fecha_limite = datetime.now() - timedelta(days=30)
    cantidad_inicial = len(mensajes)
    
    mensajes = [
        m for m in mensajes 
        if m.get("fecha") and m["fecha"] > fecha_limite
    ]
    
    cantidad_eliminada = cantidad_inicial - len(mensajes)
    if cantidad_eliminada > 0:
        print(f"🗑️ Eliminados {cantidad_eliminada} mensajes antiguos (>30 días)")
    
    return cantidad_eliminada

async def tarea_limpieza_periodica():
    """Ejecuta la limpieza cada 24 horas"""
    while True:
        await asyncio.sleep(86400)  # 24 horas
        limpiar_mensajes_antiguos()

# =============================
# 🚀 EVENTO DE STARTUP (CORREGIDO)
# =============================

@app.on_event("startup")
async def startup_event():
    """✅ STARTUP COMPLETAMENTE FUNCIONAL"""
    global productos_api, direcciones, telefonos, mensajes, gestor_imagenes
    
    print("\n" + "="*80)
    print("🚀 INICIANDO FERRE-CALVILLITO API")
    print("="*80)
    
    try:
        # 1️⃣ Inicializar GitHub
        print("\n📦 PASO 1: Inicializando GitHub Persistence...")
        gh.inicializar_github(DATA_DIR)
        print("   ✅ GitHub Persistence inicializado")
        
        # 1.5️⃣ Inicializar Gestor de Imágenes
        print("\n🖼️ PASO 1.5: Inicializando Gestor de Imágenes...")
        try:
            gestor_imagenes = GestorImagenesProductos(
                directorio_imagenes=IMAGENES_DIR,
                github_token=GITHUB_TOKEN,
                github_repo=GITHUB_REPO
            )
            print(f"   ✅ Gestor de Imágenes inicializado")
            print(f"   📁 Directorio: {IMAGENES_DIR}")
            print(f"   🔐 GitHub: {GITHUB_REPO or 'No configurado'}")
        except Exception as e:
            print(f"   ⚠️ Error inicializando imágenes: {e}")
            gestor_imagenes = None
        
        # 2️⃣ Inicializar módulo de productos
        print("\n📊 PASO 2: Inicializando módulo de productos...")
        try:
            productos_module.cargar_productos_api()
            print(f"   ✅ Módulo de productos inicializado")
        except Exception as e:
            print(f"   ⚠️ Error: {e}")
        
        # 2B️⃣ Cargar productos desde GitHub
        print("\n📊 PASO 2B: Cargando productos...")
        try:
            productos_api = gh.cargar_productos_github()
            print(f"   ✅ {len(productos_api)} productos cargados")
        except Exception as e:
            print(f"   ⚠️ Error: {e}")
            productos_api = []
        
        # 3️⃣ Cargar direcciones
        print("\n📍 PASO 3: Cargando direcciones...")
        try:
            contactos.cargar_direcciones()
            direcciones = contactos.obtener_direcciones()
            print(f"   ✅ {len(direcciones)} direcciones cargadas")
        except Exception as e:
            print(f"   ⚠️ Error: {e}")
            direcciones = []
        
        # 4️⃣ Cargar teléfonos
        print("\n📞 PASO 4: Cargando teléfonos...")
        try:
            contactos.cargar_telefonos()
            telefonos = contactos.obtener_telefonos()
            print(f"   ✅ {len(telefonos)} teléfonos cargados")
        except Exception as e:
            print(f"   ⚠️ Error: {e}")
            telefonos = []
        
        # 5️⃣ Limpiar mensajes
        print("\n💬 PASO 5: Limpiando mensajes...")
        limpiar_mensajes_antiguos()
        print(f"   ✅ Mensajes: {len(mensajes)} activos")
        
        # 6️⃣ Iniciar tareas periódicas
        print("\n⏱️ PASO 6: Iniciando tareas periódicas...")
        asyncio.create_task(tarea_limpieza_periodica())
        print("   ✅ Tarea de limpieza programada (cada 24h)")
        
        # 7️⃣ Resumen
        print("\n" + "="*80)
        print("✅ API LISTA PARA USAR")
        print("="*80)
        print(f"📊 Productos: {len(productos_api)}")
        print(f"🖼️ Imágenes descargadas: {len([p for p in productos_api if p.get('imagen', {}).get('url_github')])}")
        print(f"📍 Direcciones: {len(direcciones)}")
        print(f"📞 Teléfonos: {len(telefonos)}")
        print(f"💬 Mensajes: {len(mensajes)}")
        print(f"📁 Base: {SCRIPT_DIR}")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"\n❌ ERROR EN STARTUP:")
        print(f"{traceback.format_exc()}\n")

# =============================
# 🛌 EVENTO DE SHUTDOWN
# =============================

@app.on_event("shutdown")
async def shutdown_event():
    """Se ejecuta al apagar la API"""
    print("\n🛑 APAGANDO FERRE-CALVILLITO API")
    print("   ✅ Limpieza completada\n")

# =============================
# 🏠 ENDPOINTS BÁSICOS
# =============================

@app.get("/", response_class=HTMLResponse)
async def index():
    """Página de redirección automática"""
    html_path = os.path.join(static_dir, "redirect.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read(), media_type="text/html; charset=utf-8")
    
    laptop_path = os.path.join(static_dir, "index.html")
    if os.path.exists(laptop_path):
        with open(laptop_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read(), media_type="text/html; charset=utf-8")
    
    return HTMLResponse("<h1>Bienvenido a Ferre-Calvillito API</h1>")

@app.get("/mobile", response_class=HTMLResponse)
async def index_mobile():
    """Versión móvil"""
    html_path = os.path.join(static_dir, "index-mobile.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read(), media_type="text/html; charset=utf-8")
    return HTMLResponse("<h1>Error: index-mobile.html no encontrado</h1>", status_code=404)

@app.get("/desktop", response_class=HTMLResponse)
async def index_desktop():
    """Versión desktop"""
    html_path = os.path.join(static_dir, "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read(), media_type="text/html; charset=utf-8")
    return HTMLResponse("<h1>Error: index.html no encontrado</h1>", status_code=404)

# =============================
# 📦 PRODUCTOS
# =============================

@app.get("/producto")
async def obtener_productos():
    """Devuelve todos los productos CON IMÁGENES desde GitHub"""
    productos = gh.cargar_productos_github()
    
    # Asegurar que cada producto tenga estructura de imagen
    for prod in productos:
        if not prod.get('imagen'):
            prod['imagen'] = {
                'existe': False,
                'url_github': None
            }
    
    cant_con_imagen = len([p for p in productos if p.get('imagen', {}).get('existe')])
    print(f"🔍 GET /producto")
    print(f"   Total: {len(productos)}")
    print(f"   Con imagen: {cant_con_imagen}")
    
    return JSONResponse(
        content=productos,
        media_type="application/json; charset=utf-8"
    )

@app.get("/api/productos/{codigo}/imagen")
async def obtener_imagen_producto(codigo: str):
    """Obtiene la URL de imagen de un producto específico"""
    producto = next(
        (p for p in productos_api if p.get('Codigo') == codigo),
        None
    )
    
    if not producto:
        return JSONResponse({"error": "Producto no encontrado"}, status_code=404)
    
    imagen = producto.get('imagen', {})
    
    return JSONResponse({
        "codigo": codigo,
        "nombre": producto.get('Nombre'),
        "descripcion": producto.get('Descripcion'),
        "existe": imagen.get('existe', False),
        "url_github": imagen.get('url_github'),
        "fuente": imagen.get('fuente', 'sin_descripcion')
    })

@app.post("/api/productos/procesar-imagenes-manual")
async def procesar_imagenes_manual():
    """Procesa imágenes manualmente de todos los productos con descripción"""
    
    if not gestor_imagenes:
        return {"ok": False, "error": "Gestor de imágenes no inicializado"}
    
    # Filtrar productos con descripción
    productos_con_desc = [
        p for p in productos_api 
        if p.get('Descripcion') and p['Descripcion'].strip()
    ]
    
    if not productos_con_desc:
        return {"ok": False, "error": "No hay productos con descripción"}
    
    # Procesar en background
    asyncio.create_task(procesar_imagenes_background(productos_con_desc))
    
    return {
        "ok": True,
        "mensaje": f"Procesando {len(productos_con_desc)} imágenes",
        "procesando": len(productos_con_desc)
    }

@app.post("/api/productos/admin-upload")
async def admin_upload_productos(data: list[dict]):
    """Admin upload de productos + PROCESAR IMÁGENES AUTOMÁTICAMENTE"""
    global productos_api
    
    print(f"\n{'='*60}")
    print(f"📤 ADMIN UPLOAD - PRODUCTOS + IMÁGENES")
    print(f"   Cantidad: {len(data)}")
    
    if not data:
        return {"ok": False, "error": "Lista vacía"}
    
    try:
        # 1️⃣ Actualizar memoria
        productos_api = data
        
        # 2️⃣ Guardar en GitHub
        gh.guardar_productos_github(data)
        
        # 3️⃣ PROCESAR IMÁGENES AUTOMÁTICAMENTE
        print(f"\n🖼️ Iniciando procesamiento de imágenes...")
        
        if gestor_imagenes:
            # Filtrar productos CON descripción (solo estos buscan imagen)
            productos_con_desc = [
                p for p in data 
                if p.get('Descripcion') and p['Descripcion'].strip()
            ]
            
            print(f"   📦 Productos con descripción: {len(productos_con_desc)}")
            
            if productos_con_desc:
                try:
                    # Procesar en segundo plano
                    asyncio.create_task(
                        procesar_imagenes_background(productos_con_desc)
                    )
                    print(f"   ⏳ Procesando imágenes en segundo plano...")
                except Exception as e:
                    print(f"   ⚠️ Error inicializando procesamiento: {e}")
        
        print(f"✅ Productos guardados en GitHub")
        print(f"{'='*60}\n")
        
        return {
            "ok": True,
            "mensaje": f"✅ {len(data)} productos guardados",
            "guardados": len(data),
            "con_descripcion": len([p for p in data if p.get('Descripcion')]),
            "procesando_imagenes": True,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        print(f"❌ Error: {e}\n")
        return {"ok": False, "error": str(e)}
    
async def procesar_imagenes_background(productos_con_desc):
    global productos_api

    if not gestor_imagenes:
        print("❌ Gestor no disponible")
        return

    print("Procesando imágenes...")

    try:
        # Guarda TODOS los productos en un diccionario indexado por código
        productos_completos = {p["Codigo"]: p for p in productos_api}

        # Procesa solo los necesarios
        resultados = await gestor_imagenes.procesar_lote_productos(
            productos_con_desc,
            max_concurrentes=10
        )

        # Actualiza solo las imágenes, sin reemplazar la lista completa
        for prod in resultados:
            codigo = prod.get("Codigo")

            if not codigo:
                continue

            url_img = prod.get("imagen", {}).get("url_github")

            if not url_img:
                continue

            if codigo in productos_completos:
                productos_completos[codigo]["imagen"] = {
                    "existe": True,
                    "url_github": url_img
                }

        # Ya acabamos: convertimos el diccionario a lista
        productos_actualizados = list(productos_completos.values())

        # Y AHORA SÍ guardamos todos
        gh.guardar_productos_github(productos_actualizados)

        # Actualizamos la variable global
        productos_api = productos_actualizados

    except Exception as e:
        print("Error:", e)

@app.get("/api/productos/progreso-imagenes")
async def progreso_imagenes():
    """
    Muestra el progreso del procesamiento de imágenes
    Útil para monitorear mientras se descargan
    """
    productos = gh.cargar_productos_github()
    
    total = len(productos)
    con_descripcion = len([p for p in productos if p.get('Descripcion', '').strip()])
    con_imagen = len([p for p in productos if p.get('imagen', {}).get('existe')])
    sin_imagen_con_desc = len([
        p for p in productos 
        if p.get('Descripcion', '').strip() 
        and not p.get('imagen', {}).get('existe')
    ])
    
    porcentaje = round((con_imagen / con_descripcion * 100), 2) if con_descripcion > 0 else 0
    
    # Mensaje personalizado
    if sin_imagen_con_desc == 0:
        mensaje = "✅ Todas las imágenes han sido descargadas"
    elif con_imagen == 0:
        mensaje = "⏳ Iniciando descarga de imágenes..."
    else:
        mensaje = f"⏳ Descargando imágenes... {con_imagen}/{con_descripcion}"
    
    return {
        "mensaje": mensaje,
        "total_productos": total,
        "con_descripcion": con_descripcion,
        "con_imagen": con_imagen,
        "pendientes": sin_imagen_con_desc,
        "porcentaje_completado": porcentaje,
        "estado": "completo" if sin_imagen_con_desc == 0 else "en_progreso",
        "tiempo_estimado_min": round((sin_imagen_con_desc / 3) * 10 / 60, 1)  # Estimación
    }

@app.get("/debug/productos-estado")
async def debug_productos_estado():
    """Debug de estado de productos"""
    productos = gh.cargar_productos_github()
    return {
        "timestamp": datetime.now().isoformat(),
        "productos_memoria": len(productos_api),
        "github_estado": gh.debug_estado_github(),
        "primero": productos[0] if productos else None
    }

@app.delete("/api/productos/limpiar")
async def limpiar_productos():
    """⚠️ Elimina TODOS los productos"""
    productos_module.limpiar_productos()
    return {"ok": True, "mensaje": "Todos los productos han sido eliminados"}

# =============================
# 🔐 OAUTH GOOGLE
# =============================

@app.get("/auth/google/login")
async def login_google(request: Request):
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:5000/auth/google/callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth/google/callback")
async def auth_google_callback(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
        user = token.get("userinfo")
    except Exception as e:
        return JSONResponse({"error": f"Error al autenticar: {str(e)}"}, status_code=500)

    if not user:
        return JSONResponse({"error": "No se pudo obtener el usuario"}, status_code=400)

    # Guardar usuario localmente
    users_path = os.path.join(SCRIPT_DIR, "usuarios.json")
    users = []
    if os.path.exists(users_path):
        try:
            with open(users_path, "r", encoding="utf-8") as f:
                users = json.load(f)
        except:
            users = []

    if not any(u["email"] == user["email"] for u in users):
        users.append({
            "nombre": user["name"],
            "email": user["email"],
            "foto": user.get("picture", "")
        })
        with open(users_path, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=2, ensure_ascii=False)

    html = f"""
    <script>
        localStorage.setItem('usuario', JSON.stringify({{
            nombre: "{user['name']}",
            correo: "{user['email']}",
            foto: "{user.get('picture', '')}"
        }}));
        window.location.href = "/";
    </script>
    """
    return HTMLResponse(content=html)

# =============================
# 💬 MENSAJES
# =============================

class Mensaje(BaseModel):
    usuario: str
    tipo: str
    mensaje: str
    origen: str = "usuario"
    destinatario: str = None

@app.post("/api/mensajes/enviar")
async def enviar_mensaje(data: Mensaje):
    origen = data.origen or "usuario"
    destinatario = data.destinatario
    if origen == "usuario" and not destinatario:
        destinatario = "admin"

    registro = {
        "id": str(uuid4()),
        "usuario": data.usuario,
        "tipo": data.tipo,
        "mensaje": data.mensaje,
        "origen": origen,
        "destinatario": destinatario,
        "leido": False,
        "fecha": datetime.now()
    }

    mensajes.append(registro)
    print(f"📤 Mensaje enviado: {registro}")
    return {"ok": True, "mensaje": "Mensaje enviado correctamente"}

@app.get("/api/mensajes/recibir")
async def recibir_mensajes(usuario: str = None, tipo: str = None):
    """Devuelve mensajes filtrados"""
    print(f"🔍 Recibiendo mensajes - Usuario: {usuario}, Tipo: {tipo}")
    
    filtrados = mensajes.copy()
    
    if tipo:
        filtrados = [m for m in filtrados if m.get("tipo") == tipo]
    
    if usuario:
        filtrados = [
            m for m in filtrados
            if m.get("usuario") == usuario or m.get("destinatario") == usuario or m.get("origen") == usuario
        ]
    
    resultado = []
    for m in filtrados:
        msg_dict = m.copy()
        if isinstance(msg_dict.get("fecha"), datetime):
            msg_dict["fecha"] = msg_dict["fecha"].isoformat()
        resultado.append(msg_dict)
    
    return resultado

@app.get("/api/mensajes/contadores")
async def contadores(usuario: str):
    no_leidos_preguntas = sum(
        1 for m in mensajes if m.get("destinatario") == usuario and not m.get("leido") and m.get("tipo") == "pregunta"
    )
    no_leidos_sugerencias = sum(
        1 for m in mensajes if m.get("destinatario") == usuario and not m.get("leido") and m.get("tipo") == "sugerencia"
    )
    total = no_leidos_preguntas + no_leidos_sugerencias
    return {
        "noLeidosPreguntas": no_leidos_preguntas,
        "noLeidosSugerencias": no_leidos_sugerencias,
        "total": total
    }

@app.post("/api/mensajes/marcar-leido")
async def marcar_leido(data: dict = Body(...)):
    usuario = data.get("usuario")
    ids = data.get("ids", [])

    if not usuario:
        return {"ok": False, "error": "Falta el campo 'usuario'"}

    marcados = 0
    for m in mensajes:
        if (
            m.get("destinatario") == usuario
            and not m.get("leido")
            and (not ids or m.get("id") in ids)
        ):
            m["leido"] = True
            marcados += 1

    return {"ok": True, "marcados": marcados}

@app.post("/api/mensajes/limpiar-antiguos")
async def limpiar_antiguos_manual():
    cantidad = limpiar_mensajes_antiguos()
    return {
        "ok": True,
        "mensaje": f"Se eliminaron {cantidad} mensajes con más de 30 días",
        "eliminados": cantidad
    }

@app.get("/api/mensajes/estadisticas")
async def estadisticas_mensajes():
    ahora = datetime.now()
    antiguos = sum(1 for m in mensajes if (ahora - m.get("fecha", ahora)).days > 30)
    
    return {
        "total": len(mensajes),
        "antiguos_30_dias": antiguos,
        "activos": len(mensajes) - antiguos
    }

# =============================
# 🔄 CONFIGURACIÓN DE BD
# =============================

class ConexionRequest(BaseModel):
    Cadena: str = Field(..., alias="cadena")
    class Config:
        populate_by_name = True

@app.post("/configuracion/cambiarBD")
async def cambiar_bd(data: ConexionRequest):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(data.Cadena.strip())
    return {"mensaje": "Cadena de conexión guardada correctamente"}

@app.get("/configuracion/rutaActual")
async def ruta_actual():
    if not os.path.exists(CONFIG_PATH):
        return JSONResponse({"error": "No hay conexión configurada"}, status_code=404)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return {"cadena": f.read().strip()}

# =============================
# 📍 DIRECCIONES
# =============================

class Direccion(BaseModel):
    calle: str
    numero: str
    colonia: str
    ciudad: str
    estado: str
    cp: str

@app.get("/direcciones")
async def obtener_direcciones():
    try:
        dirs = contactos.obtener_direcciones()
        print(f"📍 GET /direcciones - Devolviendo {len(dirs)} direcciones")
        return JSONResponse(content=dirs, media_type="application/json; charset=utf-8")
    except Exception as e:
        print(f"❌ Error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/direcciones/{id}")
async def obtener_direccion(id: str):
    try:
        dirs = contactos.obtener_direcciones()
        direccion = next((d for d in dirs if d.get("id") == id), None)
        if not direccion:
            return JSONResponse({"error": "No encontrada"}, status_code=404)
        return JSONResponse(content=direccion)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/direcciones")
async def agregar_direccion(data: Direccion):
    try:
        nueva_dir = contactos.agregar_direccion(
            calle=data.calle, numero=data.numero, colonia=data.colonia,
            ciudad=data.ciudad, estado=data.estado, cp=data.cp
        )
        # 🔄 Guardar en GitHub
        dirs = contactos.obtener_direcciones()
        gh.guardar_direcciones_github(dirs)
        
        return JSONResponse(content={"ok": True, "direccion": nueva_dir}, status_code=201)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.put("/direcciones/{id}")
async def actualizar_direccion(id: str, data: Direccion):
    try:
        direccion = contactos.actualizar_direccion(
            id_dir=id, calle=data.calle, numero=data.numero, colonia=data.colonia,
            ciudad=data.ciudad, estado=data.estado, cp=data.cp
        )
        if not direccion:
            return JSONResponse({"error": "No encontrada"}, status_code=404)
        
        # 🔄 Guardar en GitHub
        dirs = contactos.obtener_direcciones()
        gh.guardar_direcciones_github(dirs)
        
        return JSONResponse(content={"ok": True, "direccion": direccion})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.delete("/direcciones/{id}")
async def eliminar_direccion(id: str):
    try:
        dirs = contactos.obtener_direcciones()
        if not any(d.get("id") == id for d in dirs):
            return JSONResponse({"error": "No encontrada"}, status_code=404)
        contactos.eliminar_direccion(id)
        
        # 🔄 Guardar en GitHub
        dirs_actualizado = contactos.obtener_direcciones()
        gh.guardar_direcciones_github(dirs_actualizado)
        
        return JSONResponse(content={"ok": True, "mensaje": "Eliminada"})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

# =============================
# 📞 TELÉFONOS
# =============================

class Telefono(BaseModel):
    numero: str
    descripcion: str = ""

@app.get("/telefonos")
async def obtener_telefonos():
    try:
        tels = contactos.obtener_telefonos()
        print(f"📞 GET /telefonos - Devolviendo {len(tels)} teléfonos")
        return JSONResponse(content=tels, media_type="application/json; charset=utf-8")
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/telefonos/{id}")
async def obtener_telefono(id: str):
    try:
        tels = contactos.obtener_telefonos()
        telefono = next((t for t in tels if t.get("id") == id), None)
        if not telefono:
            return JSONResponse({"error": "No encontrado"}, status_code=404)
        return JSONResponse(content=telefono)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/telefonos")
async def agregar_telefono(data: Telefono):
    try:
        nuevo_tel = contactos.agregar_telefono(numero=data.numero, descripcion=data.descripcion)
        
        # 🔄 GUARDAR EN GITHUB
        tels = contactos.obtener_telefonos()
        gh.guardar_telefonos_github(tels)
        print(f"✅ Teléfono guardado en GitHub")
        
        return JSONResponse(content={"ok": True, "telefono": nuevo_tel}, status_code=201)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.put("/telefonos/{id}")
async def actualizar_telefono(id: str, data: Telefono):
    try:
        telefono = contactos.actualizar_telefono(id_tel=id, numero=data.numero, descripcion=data.descripcion)
        if not telefono:
            return JSONResponse({"error": "No encontrado"}, status_code=404)
        
        # 🔄 GUARDAR EN GITHUB
        tels = contactos.obtener_telefonos()
        gh.guardar_telefonos_github(tels)
        print(f"✅ Teléfono actualizado en GitHub")
        
        return JSONResponse(content={"ok": True, "telefono": telefono})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.delete("/telefonos/{id}")
async def eliminar_telefono(id: str):
    try:
        tels = contactos.obtener_telefonos()
        if not any(t.get("id") == id for t in tels):
            return JSONResponse({"error": "No encontrado"}, status_code=404)
        contactos.eliminar_telefono(id)
        
        # 🔄 GUARDAR EN GITHUB
        tels_actualizado = contactos.obtener_telefonos()
        gh.guardar_telefonos_github(tels_actualizado)
        print(f"✅ Teléfono eliminado de GitHub")
        
        return JSONResponse(content={"ok": True, "mensaje": "Eliminado"})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.post("/api/productos/actualizar-imagen")
async def actualizar_imagen_producto(data: dict):
    """
    Recibe:
    {
        "Codigo": "ABC123",
        "imagen": {
            "existe": true,
            "url_github": "https://...."
        }
    }
    Y actualiza SOLO ese producto.
    """

    codigo = data.get("Codigo")
    nueva_img = data.get("imagen")

    if not codigo or not nueva_img:
        return JSONResponse(
            {"ok": False, "error": "Faltan datos"},
            status_code=400
        )

    global productos_api

    # Buscar el producto
    encontrado = False
    for prod in productos_api:
        if prod.get("Codigo") == codigo:
            # crear campo si no existe
            if "imagen" not in prod:
                prod["imagen"] = {}

            prod["imagen"]["existe"] = nueva_img.get("existe", False)
            prod["imagen"]["url_github"] = nueva_img.get("url_github")
            prod["imagen"]["fuente"] = "manual"
            encontrado = True
            break

    if not encontrado:
        return JSONResponse(
            {"ok": False, "error": "Producto no encontrado"},
            status_code=404
        )

    # Guardar en GitHub
    gh.guardar_productos_github(productos_api)

    return {"ok": True, "mensaje": "Imagen actualizada correctamente"}

# =============================
# 🔍 DEBUG
# =============================

@app.get("/debug/contactos-estado")
async def debug_contactos_estado():
    try:
        dirs_mem = contactos.obtener_direcciones()
        tels_mem = contactos.obtener_telefonos()
        
        dirs_arch = []
        if os.path.exists(contactos.DIRECCIONES_FILE):
            with open(contactos.DIRECCIONES_FILE, "r", encoding="utf-8") as f:
                dirs_arch = json.load(f)
        
        tels_arch = []
        if os.path.exists(contactos.TELEFONOS_FILE):
            with open(contactos.TELEFONOS_FILE, "r", encoding="utf-8") as f:
                tels_arch = json.load(f)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "direcciones": {
                "memoria": len(dirs_mem),
                "archivo": len(dirs_arch),
                "sincronizado": len(dirs_mem) == len(dirs_arch)
            },
            "telefonos": {
                "memoria": len(tels_mem),
                "archivo": len(tels_arch),
                "sincronizado": len(tels_mem) == len(tels_arch)
            }
        }
    except Exception as e:
        return {"error": str(e)}