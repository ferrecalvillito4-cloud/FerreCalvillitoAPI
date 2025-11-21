from fastapi import FastAPI, Request, Body
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel, Field
from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv
import fdb
import itsdangerous
import os
import json
from datetime import datetime, timedelta
from uuid import uuid4
import asyncio
import productos_api as productos_module
from productos_api import cargar_productos_api, guardar_productos_api, PRODUCTOS_FILE
import productos_api as productos_module

# =============================
# 🚀 Inicialización principal
# =============================
app = FastAPI(title="Ferre-Calvillito API")
load_dotenv()

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

@app.post("/api/productos/admin-upload")
async def admin_upload_productos(data: list[dict]):
    """
    Recibe lista de productos desde el admin y reemplaza la base interna del API.
    """
    print(f"\n{'='*60}")
    print(f"📤 RECIBIDO DATOS DE ADMIN:")
    print(f"   Tipo: {type(data)}")
    print(f"   Cantidad: {len(data)}")
    if data:
        print(f"   Primer item: {data[0]}")
    
    # ✅ Actualizar la variable global en el módulo
    productos_module.productos_api = data
    print(f"✅ Variable global actualizada con {len(data)} items")
    
    # ✅ GUARDAR EN ARCHIVO
    try:
        productos_module.guardar_productos_api()
        print(f"💾 Archivo guardado correctamente")
    except Exception as e:
        print(f"❌ Error al guardar: {e}")
        return {"ok": False, "error": str(e)}
    
    print(f"{'='*60}\n")
    
    return {
        "ok": True, 
        "mensaje": f"{len(data)} productos actualizados en la API",
        "guardados": len(productos_module.productos_api)
    }


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
    users_path = os.path.join(os.path.dirname(__file__), "usuarios.json")
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
# 📁 Archivos estáticos
# =============================
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "conexion_actual.txt")

# =============================
# 🔥 Cargar cliente Firebird
# =============================
try:
    dll_path = os.path.join(os.path.dirname(__file__), "fbclient.dll")
    if os.path.exists(dll_path):
        fdb.load_api(dll_path)
        print(f"🧩 fbclient.dll cargado desde: {dll_path}")
    else:
        print("⚠️ No se encontró fbclient.dll en el directorio del proyecto.")
except Exception as e:
    print("❌ Error al cargar fbclient.dll:", e)

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
# 🏠 Página principal
# =============================
@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = os.path.join(static_dir, "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read(), media_type="text/html; charset=utf-8")
    return HTMLResponse("<h1>Bienvenido a Ferre-Calvillito API</h1>")

# =============================
# 📦 Productos
# =============================
@app.get("/producto")
async def obtener_productos():
    """
    Devuelve todos los productos
    """
    productos = productos_module.obtener_productos_api()
    print(f"🔍 GET /producto - Devolviendo {len(productos)} productos")
    return JSONResponse(
        content=productos, 
        media_type="application/json; charset=utf-8"
    )

# ================================
# 💬 Mensajes de usuario
# ================================
class Mensaje(BaseModel):
    usuario: str             # quien envía
    tipo: str                # "pregunta" o "sugerencia"
    mensaje: str             # contenido
    origen: str = "usuario"  # "usuario" o "admin"
    destinatario: str = None # opcional: para admin, a quién responde

# Lista temporal para mensajes
mensajes: list[dict] = []

# =============================
# 🗑️ Limpieza automática de mensajes antiguos
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
        await asyncio.sleep(86400)  # 24 horas en segundos
        limpiar_mensajes_antiguos()

@app.post("/api/mensajes/enviar")
async def enviar_mensaje(data: Mensaje):
    origen = getattr(data, "origen", None) or "usuario"
    destinatario = getattr(data, "destinatario", None)
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
    """
    Devuelve los mensajes filtrados por tipo.
    Si no hay usuario, devuelve TODOS los mensajes del tipo especificado.
    """
    print(f"🔍 Recibiendo mensajes - Usuario: {usuario}, Tipo: {tipo}")
    print(f"📊 Total mensajes en memoria: {len(mensajes)}")
    
    filtrados = mensajes.copy()
    
    # Si hay tipo, filtrar por tipo
    if tipo:
        filtrados = [m for m in filtrados if m.get("tipo") == tipo]
        print(f"📋 Después de filtrar por tipo '{tipo}': {len(filtrados)} mensajes")
    
    # Si hay usuario, filtrar por participación del usuario
    if usuario:
        filtrados = [
            m for m in filtrados
            if m.get("usuario") == usuario or m.get("destinatario") == usuario or m.get("origen") == usuario
        ]
        print(f"👤 Después de filtrar por usuario '{usuario}': {len(filtrados)} mensajes")
    
    # Convertir datetime a string para JSON
    resultado = []
    for m in filtrados:
        msg_dict = m.copy()
        if isinstance(msg_dict.get("fecha"), datetime):
            msg_dict["fecha"] = msg_dict["fecha"].isoformat()
        resultado.append(msg_dict)
    
    print(f"✅ Devolviendo {len(resultado)} mensajes")
    return resultado

# =============================
# 🔄 Configuración de BD
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
    """
    Marca como leídos los mensajes enviados al usuario.
    Espera un JSON con:
    {
        "usuario": "correo@ejemplo.com",
        "ids": [opcional]  // si no hay IDs, marca todos los mensajes no leídos del usuario
    }
    """
    usuario = data.get("usuario")
    ids = data.get("ids", [])

    if not usuario:
        return {"ok": False, "error": "Falta el campo 'usuario'"}

    # Marcar los mensajes
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

# =============================
# 🛠️ Endpoint manual de limpieza (opcional)
# =============================
@app.post("/api/mensajes/limpiar-antiguos")
async def limpiar_antiguos_manual():
    """Endpoint para ejecutar manualmente la limpieza de mensajes antiguos"""
    cantidad = limpiar_mensajes_antiguos()
    return {
        "ok": True,
        "mensaje": f"Se eliminaron {cantidad} mensajes con más de 30 días de antigüedad",
        "eliminados": cantidad
    }

@app.get("/api/mensajes/estadisticas")
async def estadisticas_mensajes():
    """Muestra estadísticas de los mensajes"""
    ahora = datetime.now()
    antiguos = sum(1 for m in mensajes if (ahora - m.get("fecha", ahora)).days > 30)
    
    return {
        "total": len(mensajes),
        "antiguos_30_dias": antiguos,
        "activos": len(mensajes) - antiguos
    }

# ================================
# 📍 Gestión de Direcciones
# ================================
class Direccion(BaseModel):
    calle: str
    numero: str
    colonia: str
    ciudad: str
    estado: str
    cp: str

# Lista temporal para direcciones (similar a mensajes)
direcciones: list[dict] = []

# ================================
# 📞 Gestión de Teléfonos
# ================================
class Telefono(BaseModel):
    numero: str
    descripcion: str = ""

# Lista temporal para teléfonos
telefonos: list[dict] = []

PRODUCTOS_FILE = os.path.join(os.path.dirname(__file__), "productos.json")
DIRECCIONES_FILE = os.path.join(os.path.dirname(__file__), "direcciones.json")
TELEFONOS_FILE = os.path.join(os.path.dirname(__file__), "telefonos.json")
# Al inicio del archivo, junto con las otras listas
DIRECCIONES_FILE = os.path.join(os.path.dirname(__file__), "direcciones.json")
TELEFONOS_FILE = os.path.join(os.path.dirname(__file__), "telefonos.json")

# Cargar datos al inicio
def cargar_datos():
    global direcciones, telefonos

    # Cargar direcciones
    if os.path.exists(DIRECCIONES_FILE):
        try:
            with open(DIRECCIONES_FILE, "r", encoding="utf-8") as f:
                direcciones = json.load(f)
            print(f"📍 Cargadas {len(direcciones)} direcciones")
        except Exception as e:
            direcciones = []
            print(f"⚠️ Error al cargar direcciones.json: {e}")
    else:
        direcciones = []

    # Cargar teléfonos
    if os.path.exists(TELEFONOS_FILE):
        try:
            with open(TELEFONOS_FILE, "r", encoding="utf-8") as f:
                telefonos = json.load(f)
            print(f"📞 Cargados {len(telefonos)} teléfonos")
        except Exception as e:
            telefonos = []
            print(f"⚠️ Error al cargar telefonos.json: {e}")
    else:
        telefonos = []

# Guardar datos
def guardar_direcciones():
    with open(DIRECCIONES_FILE, "w", encoding="utf-8") as f:
        json.dump(direcciones, f, indent=2, ensure_ascii=False, default=str)

def guardar_telefonos():
    with open(TELEFONOS_FILE, "w", encoding="utf-8") as f:
        json.dump(telefonos, f, indent=2, ensure_ascii=False, default=str)

# =============================
# ENDPOINTS DE DIRECCIONES
# =============================
@app.get("/direcciones")
async def obtener_direcciones():
    """Obtiene todas las direcciones"""
    return direcciones

@app.get("/direcciones/{id}")
async def obtener_direccion(id: str):
    """Obtiene una dirección específica por ID"""
    direccion = next((d for d in direcciones if d.get("id") == id), None)
    if not direccion:
        return JSONResponse({"error": "Dirección no encontrada"}, status_code=404)
    return direccion

@app.post("/direcciones")
async def agregar_direccion(data: Direccion):
    """Agrega una nueva dirección"""
    nueva_direccion = {
        "id": str(uuid4()),
        "calle": data.calle,
        "numero": data.numero,
        "colonia": data.colonia,
        "ciudad": data.ciudad,
        "estado": data.estado,
        "cp": data.cp,
        "fecha_creacion": datetime.now().isoformat()
    }
    direcciones.append(nueva_direccion)
    guardar_direcciones()
    print(f"📍 Dirección agregada: {nueva_direccion}")
    return {"ok": True, "mensaje": "Dirección agregada correctamente", "direccion": nueva_direccion}

@app.put("/direcciones/{id}")
async def actualizar_direccion(id: str, data: Direccion):
    """Actualiza una dirección existente"""
    direccion = next((d for d in direcciones if d.get("id") == id), None)
    if not direccion:
        return JSONResponse({"error": "Dirección no encontrada"}, status_code=404)
    
    direccion.update({
        "calle": data.calle,
        "numero": data.numero,
        "colonia": data.colonia,
        "ciudad": data.ciudad,
        "estado": data.estado,
        "cp": data.cp,
        "fecha_actualizacion": datetime.now().isoformat()
    })
    
    guardar_direcciones()
    print(f"📝 Dirección actualizada: {direccion}")
    return {"ok": True, "mensaje": "Dirección actualizada correctamente", "direccion": direccion}

@app.delete("/direcciones/{id}")
async def eliminar_direccion(id: str):
    """Elimina una dirección"""
    global direcciones
    direccion = next((d for d in direcciones if d.get("id") == id), None)
    if not direccion:
        return JSONResponse({"error": "Dirección no encontrada"}, status_code=404)
    
    direcciones = [d for d in direcciones if d.get("id") != id]
    guardar_direcciones()
    print(f"🗑️ Dirección eliminada: {id}")
    return {"ok": True, "mensaje": "Dirección eliminada correctamente"}

# =============================
# ENDPOINTS DE TELÉFONOS
# =============================
@app.get("/telefonos")
async def obtener_telefonos():
    """Obtiene todos los teléfonos"""
    return telefonos

@app.get("/telefonos/{id}")
async def obtener_telefono(id: str):
    """Obtiene un teléfono específico por ID"""
    telefono = next((t for t in telefonos if t.get("id") == id), None)
    if not telefono:
        return JSONResponse({"error": "Teléfono no encontrado"}, status_code=404)
    return telefono

@app.post("/telefonos")
async def agregar_telefono(data: Telefono):
    """Agrega un nuevo teléfono"""
    nuevo_telefono = {
        "id": str(uuid4()),
        "numero": data.numero,
        "descripcion": data.descripcion,
        "fecha_creacion": datetime.now().isoformat()
    }
    telefonos.append(nuevo_telefono)
    guardar_telefonos()
    print(f"📞 Teléfono agregado: {nuevo_telefono}")
    return {"ok": True, "mensaje": "Teléfono agregado correctamente", "telefono": nuevo_telefono}

@app.put("/telefonos/{id}")
async def actualizar_telefono(id: str, data: Telefono):
    """Actualiza un teléfono existente"""
    telefono = next((t for t in telefonos if t.get("id") == id), None)
    if not telefono:
        return JSONResponse({"error": "Teléfono no encontrado"}, status_code=404)
    
    telefono.update({
        "numero": data.numero,
        "descripcion": data.descripcion,
        "fecha_actualizacion": datetime.now().isoformat()
    })
    
    guardar_telefonos()
    print(f"📝 Teléfono actualizado: {telefono}")
    return {"ok": True, "mensaje": "Teléfono actualizado correctamente", "telefono": telefono}

@app.delete("/telefonos/{id}")
async def eliminar_telefono(id: str):
    """Elimina un teléfono"""
    global telefonos
    telefono = next((t for t in telefonos if t.get("id") == id), None)
    if not telefono:
        return JSONResponse({"error": "Teléfono no encontrado"}, status_code=404)
    
    telefonos = [t for t in telefonos if t.get("id") != id]
    guardar_telefonos()
    print(f"🗑️ Teléfono eliminado: {id}")
    return {"ok": True, "mensaje": "Teléfono eliminado correctamente"}

# =============================
# 🚀 Evento de inicio (ACTUALIZADO)
# =============================
@app.on_event("startup")
async def startup_event():
    print("\n🚀 Ferre-Calvillito API iniciada correctamente")
    print(f"📁 Ruta base: {os.path.dirname(__file__)}")
    print(f"📁 PRODUCTOS_FILE: {productos_module.PRODUCTOS_FILE}")
    print(f"   Existe: {os.path.exists(productos_module.PRODUCTOS_FILE)}")
    
    cargar_datos()            # 🔹 Cargar direcciones y teléfonos
    cargar_productos_api()    # 🔹 Cargar productos del archivo
    
    # 🔍 DEBUG: Ver estado inicial
    print(f"📦 Productos cargados en startup: {len(productos_module.productos_api)}")
    if productos_module.productos_api:
        print(f"   Primer producto: {productos_module.productos_api[0]}")
    
    limpiar_mensajes_antiguos()  # 🔹 Limpiar mensajes antiguos al inicio
    asyncio.create_task(tarea_limpieza_periodica())  # 🔹 Tarea periódica de limpieza
    
    print("✅ API lista\n")
