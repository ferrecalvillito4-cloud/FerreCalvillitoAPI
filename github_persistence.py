import os
import json
import base64
from datetime import datetime
import requests
from dotenv import load_dotenv

# =============================
# 🔐 Configuración GitHub
# =============================
load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_OWNER = os.getenv("GITHUB_OWNER")
GITHUB_REPO = os.getenv("GITHUB_REPO")
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents"

# =============================
# 📁 Variables locales
# =============================
data_dir = None
PRODUCTOS_LOCAL_FILE = None
DIRECCIONES_LOCAL_FILE = None
TELEFONOS_LOCAL_FILE = None
IMAGENES_LOCAL_DIR = None
IMAGENES_GITHUB_DIR = "imagenes"  # Carpeta en GitHub

# =============================
# 🔧 Inicialización
# =============================

def inicializar_github(directorio_datos):
    """Inicializa las variables globales de GitHub"""
    global data_dir, PRODUCTOS_LOCAL_FILE, DIRECCIONES_LOCAL_FILE, TELEFONOS_LOCAL_FILE, IMAGENES_LOCAL_DIR
    
    data_dir = directorio_datos
    PRODUCTOS_LOCAL_FILE = os.path.join(data_dir, "productos_github.json")
    DIRECCIONES_LOCAL_FILE = os.path.join(data_dir, "direcciones_github.json")
    TELEFONOS_LOCAL_FILE = os.path.join(data_dir, "telefonos_github.json")
    IMAGENES_LOCAL_DIR = os.path.join(data_dir, "imagenes")
    
    print(f"\n{'='*70}")
    print(f"🔐 INICIALIZANDO GITHUB PERSISTENCE")
    print(f"   Token: {'✅' if GITHUB_TOKEN else '❌'}")
    print(f"   Owner: {GITHUB_OWNER}")
    print(f"   Repo: {GITHUB_REPO}")
    print(f"   Productos: {PRODUCTOS_LOCAL_FILE}")
    print(f"   Direcciones: {DIRECCIONES_LOCAL_FILE}")
    print(f"   Teléfonos: {TELEFONOS_LOCAL_FILE}")
    print(f"   Imágenes: {IMAGENES_LOCAL_DIR}")
    print(f"{'='*70}\n")
    
    if not GITHUB_TOKEN:
        print("⚠️ GITHUB_TOKEN no configurado - usando solo persistencia local")


# =============================
# 📥 CARGAR DESDE GITHUB
# =============================

def cargar_productos_github():
    """Carga los productos desde GitHub"""
    return _cargar_desde_github("productos.json", PRODUCTOS_LOCAL_FILE)

def cargar_direcciones_github():
    """Carga las direcciones desde GitHub"""
    return _cargar_desde_github("direcciones.json", DIRECCIONES_LOCAL_FILE)

def cargar_telefonos_github():
    """Carga los teléfonos desde GitHub"""
    return _cargar_desde_github("telefonos.json", TELEFONOS_LOCAL_FILE)


def _cargar_desde_github(nombre_archivo, archivo_local):
    """
    Función genérica para cargar desde GitHub con fallback local
    """
    print(f"\n{'='*70}")
    print(f"📥 CARGANDO {nombre_archivo.upper()} DESDE GITHUB")
    print(f"   Timestamp: {datetime.now().isoformat()}")
    
    # Intentar desde GitHub
    if GITHUB_TOKEN and GITHUB_OWNER and GITHUB_REPO:
        try:
            print(f"   Intentando GitHub...")
            url = f"{GITHUB_API_URL}/{nombre_archivo}"
            headers = {
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3.raw"
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                datos = response.json()
                print(f"✅ Cargados desde GitHub")
                
                # Guardar copia local como fallback
                _guardar_copia_local(datos, archivo_local)
                
                print(f"{'='*70}\n")
                return datos if isinstance(datos, list) else []
            
            elif response.status_code == 404:
                print(f"   ⚠️ Archivo no existe en GitHub (404)")
            else:
                print(f"   ⚠️ Error GitHub ({response.status_code})")
        
        except Exception as e:
            print(f"   ⚠️ Error conectando a GitHub: {e}")
    
    # Fallback a copia local
    print(f"   Intentando copia local...")
    if os.path.exists(archivo_local):
        try:
            with open(archivo_local, "r", encoding="utf-8") as f:
                datos = json.load(f)
            print(f"✅ Cargados desde copia local")
            print(f"{'='*70}\n")
            return datos if isinstance(datos, list) else []
        except Exception as e:
            print(f"   ⚠️ Error: {e}")
    
    # Todo falló
    print(f"❌ No se pudo cargar - devolviendo lista vacía")
    print(f"{'='*70}\n")
    return []


# =============================
# 📤 GUARDAR EN GITHUB
# =============================

def guardar_productos_github(productos):
    """Guarda los productos en GitHub"""
    return _guardar_en_github(productos, "productos.json", PRODUCTOS_LOCAL_FILE)

def guardar_direcciones_github(direcciones):
    """Guarda las direcciones en GitHub"""
    return _guardar_en_github(direcciones, "direcciones.json", DIRECCIONES_LOCAL_FILE)

def guardar_telefonos_github(telefonos):
    """Guarda los teléfonos en GitHub"""
    return _guardar_en_github(telefonos, "telefonos.json", TELEFONOS_LOCAL_FILE)


def _guardar_en_github(datos, nombre_archivo, archivo_local):
    """
    Función genérica para guardar en GitHub con fallback local
    """
    print(f"\n{'='*70}")
    print(f"📤 GUARDANDO {nombre_archivo.upper()} EN GITHUB")
    print(f"   Total items: {len(datos)}")
    print(f"   Timestamp: {datetime.now().isoformat()}")
    
    # 1️⃣ Guardar copia local primero (siempre)
    _guardar_copia_local(datos, archivo_local)
    print(f"   ✅ Copia local guardada")
    
    # 2️⃣ Si no hay token, no hacer más
    if not GITHUB_TOKEN or not GITHUB_OWNER or not GITHUB_REPO:
        print(f"⚠️ Sin credenciales de GitHub - solo persistencia local")
        print(f"{'='*70}\n")
        return False
    
    # 3️⃣ Intentar guardar en GitHub
    try:
        print(f"   Intentando GitHub...")
        
        # Obtener SHA del archivo actual
        sha = _obtener_sha_archivo(nombre_archivo)
        
        # Preparar contenido
        contenido_json = json.dumps(datos, indent=2, ensure_ascii=False)
        contenido_b64 = base64.b64encode(contenido_json.encode()).decode()
        
        url = f"{GITHUB_API_URL}/{nombre_archivo}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        payload = {
            "message": f"🔄 Actualización de {nombre_archivo} - {datetime.now().isoformat()}",
            "content": contenido_b64,
            "branch": "main"
        }
        
        if sha:
            payload["sha"] = sha
        
        response = requests.put(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code in [200, 201]:
            print(f"✅ Guardado en GitHub exitosamente")
            print(f"{'='*70}\n")
            return True
        else:
            print(f"⚠️ Error GitHub ({response.status_code})")
            print(f"{'='*70}\n")
            return False
    
    except Exception as e:
        print(f"❌ Error: {e}")
        print(f"⚠️ Persistencia local disponible")
        print(f"{'='*70}\n")
        return False


# =============================
# 🖼️ GUARDAR IMÁGENES EN GITHUB
# =============================

def guardar_imagen_github(codigo_producto, ruta_imagen_local):
    """
    Guarda una imagen de producto en GitHub
    
    Args:
        codigo_producto: Código del producto (ej: "001")
        ruta_imagen_local: Ruta local de la imagen (ej: "data/imagenes/001.jpg")
    
    Returns:
        True si se guardó exitosamente, False en caso contrario
    """
    
    if not os.path.exists(ruta_imagen_local):
        print(f"⚠️ Imagen no encontrada: {ruta_imagen_local}")
        return False
    
    if not GITHUB_TOKEN or not GITHUB_OWNER or not GITHUB_REPO:
        print(f"⚠️ Sin credenciales de GitHub - imagen no guardada en repositorio")
        return False
    
    try:
        print(f"\n📤 Subiendo imagen: {codigo_producto}.jpg a GitHub...")
        
        # Leer imagen
        with open(ruta_imagen_local, "rb") as f:
            contenido_img = f.read()
        
        # Convertir a base64
        contenido_b64 = base64.b64encode(contenido_img).decode()
        
        # Ruta en GitHub
        nombre_archivo = f"{IMAGENES_GITHUB_DIR}/{codigo_producto}.jpg"
        url = f"{GITHUB_API_URL}/{nombre_archivo}"
        
        # Obtener SHA si ya existe
        sha = _obtener_sha_archivo(nombre_archivo)
        
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        payload = {
            "message": f"🖼️ Imagen producto {codigo_producto} - {datetime.now().isoformat()}",
            "content": contenido_b64,
            "branch": "main"
        }
        
        if sha:
            payload["sha"] = sha
        
        response = requests.put(url, headers=headers, json=payload, timeout=15)
        
        if response.status_code in [200, 201]:
            print(f"✅ Imagen guardada en GitHub")
            return True
        else:
            print(f"⚠️ Error GitHub al guardar imagen ({response.status_code})")
            return False
    
    except Exception as e:
        print(f"❌ Error guardando imagen: {e}")
        return False


def guardar_lote_imagenes_github(imagenes_dict):
    """
    Guarda múltiples imágenes en GitHub
    
    Args:
        imagenes_dict: Dict con {codigo_producto: ruta_local}
    
    Returns:
        Dict con resultados {codigo_producto: True/False}
    """
    print(f"\n{'='*70}")
    print(f"🖼️ GUARDANDO LOTE DE IMÁGENES EN GITHUB")
    print(f"   Total: {len(imagenes_dict)}")
    print(f"{'='*70}")
    
    resultados = {}
    
    for codigo, ruta in imagenes_dict.items():
        resultado = guardar_imagen_github(codigo, ruta)
        resultados[codigo] = resultado
    
    exitosas = sum(1 for v in resultados.values() if v)
    print(f"\n✅ {exitosas}/{len(imagenes_dict)} imágenes guardadas")
    print(f"{'='*70}\n")
    
    return resultados


# =============================
# 🔧 FUNCIONES AUXILIARES
# =============================

def _obtener_sha_archivo(nombre_archivo):
    """Obtiene el SHA del archivo actual en GitHub"""
    try:
        url = f"{GITHUB_API_URL}/{nombre_archivo}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            return response.json().get("sha")
        
        return None
    
    except Exception as e:
        print(f"   ⚠️ No se pudo obtener SHA: {e}")
        return None


def _guardar_copia_local(datos, archivo_local):
    """Guarda una copia local como fallback"""
    try:
        if not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
        
        with open(archivo_local, "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=2, ensure_ascii=False)
    
    except Exception as e:
        print(f"   ⚠️ Error guardando local: {e}")


# =============================
# 🔍 DEBUG
# =============================

def debug_estado_github():
    """Muestra el estado de la conexión con GitHub"""
    return {
        "token": "✅" if GITHUB_TOKEN else "❌",
        "owner": GITHUB_OWNER,
        "repo": GITHUB_REPO,
        "productos_local": os.path.exists(PRODUCTOS_LOCAL_FILE) if PRODUCTOS_LOCAL_FILE else False,
        "direcciones_local": os.path.exists(DIRECCIONES_LOCAL_FILE) if DIRECCIONES_LOCAL_FILE else False,
        "telefonos_local": os.path.exists(TELEFONOS_LOCAL_FILE) if TELEFONOS_LOCAL_FILE else False,
        "imagenes_local": os.path.exists(IMAGENES_LOCAL_DIR) if IMAGENES_LOCAL_DIR else False
    }


# =============================
# 🧹 Inicialización automática
# =============================
print(f"\n{'#'*70}")
print(f"# MÓDULO github_persistence CARGADO")
print(f"# GitHub Owner: {GITHUB_OWNER}")
print(f"# GitHub Repo: {GITHUB_REPO}")
print(f"# Token disponible: {'✅' if GITHUB_TOKEN else '❌'}")
print(f"{'#'*70}\n")