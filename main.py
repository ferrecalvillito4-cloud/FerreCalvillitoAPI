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
import traceback
from datetime import datetime
import contactos_persistencia as contactos

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
    Recibe lista de productos desde el admin y PERSISTE en productos.json
    """
    print(f"\n{'='*60}")
    print(f"📤 ADMIN UPLOAD - RECIBIDO DESDE ADMIN")
    print(f"   Timestamp: {datetime.now().isoformat()}")
    print(f"   Tipo: {type(data)}")
    print(f"   Cantidad: {len(data)}")
    
    if not data:
        print(f"❌ Lista vacía recibida")
        print(f"{'='*60}\n")
        return {"ok": False, "error": "Lista de productos vacía"}
    
    # Mostrar primer item para verificación
    if data:
        print(f"   Primer item: {data[0]}")
        print(f"   Campos: {list(data[0].keys())}")
    
    try:
        # ✅ 1. Actualizar variable global (también guarda)
        productos_module.actualizar_productos_api(data)
        print(f"✅ Actualización completada")
        
        # ✅ 2. Verificación post-guardado
        productos_guardados = productos_module.obtener_productos_api()
        print(f"✅ Verificación: {len(productos_guardados)} productos en memoria")
        
        # ✅ 3. Verificación del archivo
        if os.path.exists(productos_module.PRODUCTOS_FILE):
            with open(productos_module.PRODUCTOS_FILE, "r", encoding="utf-8") as f:
                contenido_archivo = json.load(f)
            print(f"✅ Archivo verificado: {len(contenido_archivo)} productos")
        
        print(f"{'='*60}\n")
        
        return {
            "ok": True,
            "mensaje": f"✅ {len(data)} productos recibidos y guardados",
            "guardados": len(productos_guardados),
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        print(f"❌ Error durante guardado: {e}")
        print(f"   Stack: {traceback.format_exc()}")
        print(f"{'='*60}\n")
        return {
            "ok": False,
            "error": str(e),
            "tipo": type(e).__name__
        }


# =============================
# 🔍 ENDPOINT DE DEBUG (opcional pero muy útil)
# =============================
@app.get("/debug/productos-estado")
async def debug_productos_estado():
    """
    Muestra el estado actual de productos en memoria y en archivo
    """
    try:
        productos_memoria = productos_module.obtener_productos_api()
        
        archivo_existe = os.path.exists(productos_module.PRODUCTOS_FILE)
        productos_archivo = []
        if archivo_existe:
            with open(productos_module.PRODUCTOS_FILE, "r", encoding="utf-8") as f:
                productos_archivo = json.load(f)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "memoria": {
                "total": len(productos_memoria),
                "primero": productos_memoria[0] if productos_memoria else None,
                "archivo_path": productos_module.PRODUCTOS_FILE
            },
            "archivo": {
                "existe": archivo_existe,
                "total": len(productos_archivo),
                "primero": productos_archivo[0] if productos_archivo else None
            },
            "sincronizado": len(productos_memoria) == len(productos_archivo)
        }
    except Exception as e:
        return {"error": str(e)}


# =============================
# 🧹 LIMPIAR PRODUCTOS (admin)
# =============================
@app.delete("/api/productos/limpiar")
async def limpiar_productos():
    """
    ⚠️ CUIDADO: Elimina TODOS los productos
    """
    productos_module.limpiar_productos()
    return {"ok": True, "mensaje": "Todos los productos han sido eliminados"}


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
    """
    Página de redirección automática a móvil o laptop
    """
    html_path = os.path.join(static_dir, "redirect.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read(), media_type="text/html; charset=utf-8")
    
    # Si no existe redirect.html, mostrar versión laptop por defecto
    laptop_path = os.path.join(static_dir, "index.html")
    if os.path.exists(laptop_path):
        with open(laptop_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read(), media_type="text/html; charset=utf-8")
    
    return HTMLResponse("<h1>Bienvenido a Ferre-Calvillito API</h1>")

# =============================
# 📱 Acceso directo a versiones
# =============================
@app.get("/mobile", response_class=HTMLResponse)
async def index_mobile():
    """Fuerza la versión móvil"""
    html_path = os.path.join(static_dir, "index-mobile.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read(), media_type="text/html; charset=utf-8")
    return HTMLResponse("<h1>Error: index-mobile.html no encontrado</h1>", status_code=404)

@app.get("/desktop", response_class=HTMLResponse)
async def index_desktop():
    """Fuerza la versión desktop/laptop"""
    html_path = os.path.join(static_dir, "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read(), media_type="text/html; charset=utf-8")
    return HTMLResponse("<h1>Error: index.html no encontrado</h1>", status_code=404)

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

class MensajeRequest(BaseModel):
    usuario: str
    tipo: str
    mensaje: str
    origen: str = "usuario"
    destinatario: str = None

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
    """Obtiene todas las direcciones (desde archivo persistente)"""
    try:
        dirs = contactos.obtener_direcciones()
        print(f"📍 GET /direcciones - Devolviendo {len(dirs)} direcciones")
        return JSONResponse(
            content=dirs,
            media_type="application/json; charset=utf-8"
        )
    except Exception as e:
        print(f"❌ Error en GET /direcciones: {e}")
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )

@app.get("/direcciones/{id}")
async def obtener_direccion(id: str):
    """Obtiene una dirección específica por ID"""
    try:
        dirs = contactos.obtener_direcciones()
        direccion = next((d for d in dirs if d.get("id") == id), None)
        
        if not direccion:
            return JSONResponse(
                {"error": "Dirección no encontrada"},
                status_code=404
            )
        
        return JSONResponse(content=direccion)
    except Exception as e:
        print(f"❌ Error en GET /direcciones/{id}: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/direcciones")
async def agregar_direccion(data: Direccion):
    """Agrega una nueva dirección y la PERSISTE"""
    try:
        print(f"\n📍 POST /direcciones")
        print(f"   Calle: {data.calle}")
        print(f"   Número: {data.numero}")
        
        nueva_dir = contactos.agregar_direccion(
            calle=data.calle,
            numero=data.numero,
            colonia=data.colonia,
            ciudad=data.ciudad,
            estado=data.estado,
            cp=data.cp
        )
        
        return JSONResponse(
            content={
                "ok": True,
                "mensaje": "Dirección agregada correctamente",
                "direccion": nueva_dir
            },
            status_code=201
        )
    except Exception as e:
        print(f"❌ Error en POST /direcciones: {e}")
        return JSONResponse(
            {"ok": False, "error": str(e)},
            status_code=500
        )


@app.put("/direcciones/{id}")
async def actualizar_direccion(id: str, data: Direccion):
    """Actualiza una dirección existente y la PERSISTE"""
    try:
        print(f"\n📍 PUT /direcciones/{id}")
        print(f"   Nueva calle: {data.calle}")
        
        direccion = contactos.actualizar_direccion(
            id_dir=id,
            calle=data.calle,
            numero=data.numero,
            colonia=data.colonia,
            ciudad=data.ciudad,
            estado=data.estado,
            cp=data.cp
        )
        
        if not direccion:
            return JSONResponse(
                {"error": "Dirección no encontrada"},
                status_code=404
            )
        
        return JSONResponse(
            content={
                "ok": True,
                "mensaje": "Dirección actualizada correctamente",
                "direccion": direccion
            }
        )
    except Exception as e:
        print(f"❌ Error en PUT /direcciones/{id}: {e}")
        return JSONResponse(
            {"ok": False, "error": str(e)},
            status_code=500
        )

@app.delete("/direcciones/{id}")
async def eliminar_direccion(id: str):
    """Elimina una dirección y PERSISTE el cambio"""
    try:
        print(f"\n📍 DELETE /direcciones/{id}")
        
        # Verificar que existe
        dirs = contactos.obtener_direcciones()
        if not any(d.get("id") == id for d in dirs):
            return JSONResponse(
                {"error": "Dirección no encontrada"},
                status_code=404
            )
        
        contactos.eliminar_direccion(id)
        
        return JSONResponse(
            content={
                "ok": True,
                "mensaje": "Dirección eliminada correctamente"
            }
        )
    except Exception as e:
        print(f"❌ Error en DELETE /direcciones/{id}: {e}")
        return JSONResponse(
            {"ok": False, "error": str(e)},
            status_code=500
        )

# =============================
# ENDPOINTS DE TELÉFONOS
# =============================
@app.get("/telefonos")
async def obtener_telefonos():
    """Obtiene todos los teléfonos (desde archivo persistente)"""
    try:
        tels = contactos.obtener_telefonos()
        print(f"📞 GET /telefonos - Devolviendo {len(tels)} teléfonos")
        return JSONResponse(
            content=tels,
            media_type="application/json; charset=utf-8"
        )
    except Exception as e:
        print(f"❌ Error en GET /telefonos: {e}")
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )

@app.get("/telefonos/{id}")
async def obtener_telefono(id: str):
    """Obtiene un teléfono específico por ID"""
    try:
        tels = contactos.obtener_telefonos()
        telefono = next((t for t in tels if t.get("id") == id), None)
        
        if not telefono:
            return JSONResponse(
                {"error": "Teléfono no encontrado"},
                status_code=404
            )
        
        return JSONResponse(content=telefono)
    except Exception as e:
        print(f"❌ Error en GET /telefonos/{id}: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/telefonos")
async def agregar_telefono(data: Telefono):
    """Agrega un nuevo teléfono y lo PERSISTE"""
    try:
        print(f"\n📞 POST /telefonos")
        print(f"   Número: {data.numero}")
        print(f"   Descripción: {data.descripcion}")
        
        nuevo_tel = contactos.agregar_telefono(
            numero=data.numero,
            descripcion=data.descripcion
        )
        
        return JSONResponse(
            content={
                "ok": True,
                "mensaje": "Teléfono agregado correctamente",
                "telefono": nuevo_tel
            },
            status_code=201
        )
    except Exception as e:
        print(f"❌ Error en POST /telefonos: {e}")
        return JSONResponse(
            {"ok": False, "error": str(e)},
            status_code=500
        )

@app.put("/telefonos/{id}")
async def actualizar_telefono(id: str, data: Telefono):
    """Actualiza un teléfono existente y lo PERSISTE"""
    try:
        print(f"\n📞 PUT /telefonos/{id}")
        print(f"   Nuevo número: {data.numero}")
        
        telefono = contactos.actualizar_telefono(
            id_tel=id,
            numero=data.numero,
            descripcion=data.descripcion
        )
        
        if not telefono:
            return JSONResponse(
                {"error": "Teléfono no encontrado"},
                status_code=404
            )
        
        return JSONResponse(
            content={
                "ok": True,
                "mensaje": "Teléfono actualizado correctamente",
                "telefono": telefono
            }
        )
    except Exception as e:
        print(f"❌ Error en PUT /telefonos/{id}: {e}")
        return JSONResponse(
            {"ok": False, "error": str(e)},
            status_code=500
        )

@app.delete("/telefonos/{id}")
async def eliminar_telefono(id: str):
    """Elimina un teléfono y PERSISTE el cambio"""
    try:
        print(f"\n📞 DELETE /telefonos/{id}")
        
        # Verificar que existe
        tels = contactos.obtener_telefonos()
        if not any(t.get("id") == id for t in tels):
            return JSONResponse(
                {"error": "Teléfono no encontrado"},
                status_code=404
            )
        
        contactos.eliminar_telefono(id)
        
        return JSONResponse(
            content={
                "ok": True,
                "mensaje": "Teléfono eliminado correctamente"
            }
        )
    except Exception as e:
        print(f"❌ Error en DELETE /telefonos/{id}: {e}")
        return JSONResponse(
            {"ok": False, "error": str(e)},
            status_code=500
        )

@app.get("/debug/contactos-estado")
async def debug_contactos_estado():
    """Muestra el estado actual de direcciones y teléfonos"""
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
                "sincronizado": len(dirs_mem) == len(dirs_arch),
                "primero": dirs_mem[0] if dirs_mem else None
            },
            "telefonos": {
                "memoria": len(tels_mem),
                "archivo": len(tels_arch),
                "sincronizado": len(tels_mem) == len(tels_arch),
                "primero": tels_mem[0] if tels_mem else None
            }
        }
    except Exception as e:
        return {"error": str(e)}

# =============================
# 🚀 Evento de inicio (ACTUALIZADO)
# =============================
@app.on_event("startup")
async def startup_event():
    print("\n🚀 Ferre-Calvillito API iniciada correctamente")
    print(f"📁 Ruta base: {os.path.dirname(__file__)}")
    
    # ✅ Cargar TODO desde archivos persistentes
    contactos.cargar_direcciones()
    contactos.cargar_telefonos()
    cargar_productos_api()
    
    limpiar_mensajes_antiguos()
    asyncio.create_task(tarea_limpieza_periodica())
    
    print("✅ API lista\n")
