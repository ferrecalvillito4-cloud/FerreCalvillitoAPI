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

# =============================
# 🔧 Inicialización
# =============================

def inicializar_github(directorio_datos):
    """Inicializa las variables globales de GitHub"""
    global data_dir, PRODUCTOS_LOCAL_FILE
    
    data_dir = directorio_datos
    PRODUCTOS_LOCAL_FILE = os.path.join(data_dir, "productos_github.json")
    
    print(f"\n{'='*70}")
    print(f"🔐 INICIALIZANDO GITHUB PERSISTENCE")
    print(f"   Token: {'✅' if GITHUB_TOKEN else '❌'}")
    print(f"   Owner: {GITHUB_OWNER}")
    print(f"   Repo: {GITHUB_REPO}")
    print(f"   Archivo local: {PRODUCTOS_LOCAL_FILE}")
    print(f"{'='*70}\n")
    
    if not GITHUB_TOKEN:
        print("⚠️ GITHUB_TOKEN no configurado - usando solo persistencia local")
    
    if not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)


# =============================
# 📥 CARGAR DESDE GITHUB
# =============================

def cargar_productos_github():
    """
    Carga los productos desde GitHub.
    Si falla, intenta usar la copia local.
    Si todo falla, devuelve lista vacía.
    """
    print(f"\n{'='*70}")
    print(f"📥 CARGANDO PRODUCTOS DESDE GITHUB")
    print(f"   Timestamp: {datetime.now().isoformat()}")
    
    # Intentar desde GitHub
    if GITHUB_TOKEN and GITHUB_OWNER and GITHUB_REPO:
        try:
            print(f"   Intentando GitHub...")
            url = f"{GITHUB_API_URL}/productos.json"
            headers = {
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3.raw"
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                productos = response.json()
                print(f"✅ Cargados {len(productos)} productos desde GitHub")
                
                # Guardar copia local como fallback
                _guardar_copia_local(productos)
                
                print(f"{'='*70}\n")
                return productos if isinstance(productos, list) else []
            
            elif response.status_code == 404:
                print(f"   ⚠️ Archivo no existe en GitHub (404)")
            else:
                print(f"   ⚠️ Error GitHub ({response.status_code}): {response.text[:100]}")
        
        except requests.exceptions.Timeout:
            print(f"   ⚠️ Timeout conectando a GitHub")
        except Exception as e:
            print(f"   ⚠️ Error conectando a GitHub: {e}")
    
    # Fallback a copia local
    print(f"   Intentando copia local...")
    if os.path.exists(PRODUCTOS_LOCAL_FILE):
        try:
            with open(PRODUCTOS_LOCAL_FILE, "r", encoding="utf-8") as f:
                productos = json.load(f)
            print(f"✅ Cargados {len(productos)} productos desde copia local")
            print(f"{'='*70}\n")
            return productos if isinstance(productos, list) else []
        except Exception as e:
            print(f"   ⚠️ Error cargando copia local: {e}")
    
    # Todo falló
    print(f"❌ No se pudo cargar productos - devolviendo lista vacía")
    print(f"{'='*70}\n")
    return []


# =============================
# 📤 GUARDAR EN GITHUB
# =============================

def guardar_productos_github(productos):
    """
    Guarda los productos en GitHub.
    Realiza backup local de todos modos.
    """
    print(f"\n{'='*70}")
    print(f"📤 GUARDANDO PRODUCTOS EN GITHUB")
    print(f"   Total productos: {len(productos)}")
    print(f"   Timestamp: {datetime.now().isoformat()}")
    
    # 1️⃣ Guardar copia local primero (siempre)
    _guardar_copia_local(productos)
    print(f"   ✅ Copia local guardada")
    
    # 2️⃣ Si no hay token, no hacer más
    if not GITHUB_TOKEN or not GITHUB_OWNER or not GITHUB_REPO:
        print(f"⚠️ Sin credenciales de GitHub - solo persistencia local")
        print(f"{'='*70}\n")
        return False
    
    # 3️⃣ Intentar guardar en GitHub
    try:
        print(f"   Intentando GitHub...")
        
        # Obtener SHA del archivo actual (para actualizar)
        sha = _obtener_sha_archivo("productos.json")
        
        # Preparar contenido
        contenido_json = json.dumps(productos, indent=2, ensure_ascii=False)
        contenido_b64 = base64.b64encode(contenido_json.encode()).decode()
        
        url = f"{GITHUB_API_URL}/productos.json"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        payload = {
            "message": f"🔄 Actualización de productos - {datetime.now().isoformat()}",
            "content": contenido_b64,
            "branch": "main"
        }
        
        # Si existe, agregar SHA para actualizar
        if sha:
            payload["sha"] = sha
        
        response = requests.put(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code in [200, 201]:
            print(f"✅ Productos guardados en GitHub exitosamente")
            print(f"   Respuesta: {response.status_code}")
            print(f"{'='*70}\n")
            return True
        else:
            print(f"⚠️ Error GitHub ({response.status_code})")
            print(f"   Respuesta: {response.text[:200]}")
            print(f"{'='*70}\n")
            return False
    
    except Exception as e:
        print(f"❌ Error guardando en GitHub: {e}")
        print(f"⚠️ Persistencia local disponible")
        print(f"{'='*70}\n")
        return False


# =============================
# 🔧 FUNCIONES AUXILIARES
# =============================

def _obtener_sha_archivo(nombre_archivo):
    """Obtiene el SHA del archivo actual en GitHub (para actualizaciones)"""
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


def _guardar_copia_local(productos):
    """Guarda una copia local de los productos como fallback"""
    try:
        if not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
        
        with open(PRODUCTOS_LOCAL_FILE, "w", encoding="utf-8") as f:
            json.dump(productos, f, indent=2, ensure_ascii=False)
    
    except Exception as e:
        print(f"   ⚠️ Error guardando copia local: {e}")


# =============================
# 🔍 DEBUG
# =============================

def debug_estado_github():
    """Muestra el estado de la conexión con GitHub"""
    return {
        "token": "✅" if GITHUB_TOKEN else "❌",
        "owner": GITHUB_OWNER,
        "repo": GITHUB_REPO,
        "archivo_local": PRODUCTOS_LOCAL_FILE,
        "existe_local": os.path.exists(PRODUCTOS_LOCAL_FILE) if PRODUCTOS_LOCAL_FILE else False
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