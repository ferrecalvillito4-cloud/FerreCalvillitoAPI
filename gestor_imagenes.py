import os
import json
import asyncio
import aiohttp
import re
from datetime import datetime
from pathlib import Path
import logging
import base64

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GestorImagenesProductos:
    def __init__(self, directorio_imagenes: str, github_token: str = None, github_repo: str = None):
        self.directorio_imagenes = directorio_imagenes
        Path(directorio_imagenes).mkdir(parents=True, exist_ok=True)
        self.cache_file = os.path.join(directorio_imagenes, "descargadas.json")
        self.cache = self._cargar_cache()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # ✅ CONFIGURACIÓN GITHUB
        self.github_token = github_token
        self.github_repo = github_repo  # formato: "usuario/repo"
        self.github_branch = "main"

    def _cargar_cache(self) -> dict:
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _guardar_cache(self):
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, indent=2, ensure_ascii=False)

    async def buscar_imagen_bing(self, nombre_producto: str) -> str:
        """Busca imagen en Bing usando el nombre del producto"""
        query = nombre_producto.replace(" ", "+")
        url = f"https://www.bing.com/images/search?q={query}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, timeout=10) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        imagenes = re.findall(r'"murl":"([^"]+)"', html)
                        if imagenes:
                            logger.info(f"✅ Imagen encontrada para: {nombre_producto}")
                            return imagenes[0]
        except Exception as e:
            logger.error(f"❌ Error buscando en Bing: {e}")
        
        return None

    async def descargar_imagen(self, url_imagen: str, nombre_archivo: str) -> bytes:
        """Descarga la imagen y retorna los bytes (sin guardar localmente)"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url_imagen, headers=self.headers, timeout=15) as resp:
                    if resp.status == 200:
                        contenido = await resp.read()
                        
                        # Validar que sea una imagen real
                        if contenido[:4] in [b'\xff\xd8\xff\xe0', b'\x89PNG', b'GIF8', b'RIFF']:
                            logger.info(f"✅ Imagen descargada: {nombre_archivo}")
                            return contenido
        except Exception as e:
            logger.error(f"❌ Error descargando imagen: {e}")
        
        return None

    async def guardar_en_github(self, codigo: str, contenido_imagen: bytes, nombre_archivo: str) -> str:
        """Guarda la imagen en GitHub y retorna la URL"""
        if not self.github_token or not self.github_repo:
            logger.warning("⚠️ Token de GitHub o repo no configurado")
            return None
        
        try:
            # Convertir imagen a base64
            contenido_base64 = base64.b64encode(contenido_imagen).decode('utf-8')
            
            # URL de GitHub API
            url_github = f"https://api.github.com/repos/{self.github_repo}/contents/imagenes_productos/{codigo}.jpg"
            
            headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            payload = {
                "message": f"Subir imagen del producto {codigo}",
                "content": contenido_base64,
                "branch": self.github_branch
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.put(url_github, json=payload, headers=headers, timeout=15) as resp:
                    if resp.status in [201, 200]:
                        respuesta = await resp.json()
                        url_directa = respuesta['content']['download_url']
                        logger.info(f"✅ Imagen guardada en GitHub: {url_directa}")
                        return url_directa
                    else:
                        error = await resp.text()
                        logger.error(f"❌ Error GitHub ({resp.status}): {error}")
        except Exception as e:
            logger.error(f"❌ Error guardando en GitHub: {e}")
        
        return None

    async def procesar_producto(self, codigo: str, nombre: str, descripcion: str = None) -> dict:
        """
        Procesa un producto:
        1. Verifica que haya descripción - SI NO HAY, NO BUSCA IMAGEN
        2. Busca imagen en Bing usando la descripción
        3. Descarga la imagen
        4. Guarda en GitHub
        5. Retorna URL de GitHub
        """
        
        # ✅ SI NO HAY DESCRIPCIÓN, NO BUSCAR IMAGEN
        if not descripcion or descripcion.strip() == "":
            logger.warning(f"⚠️ Sin descripción para {codigo} - Imagen no descargada")
            return {
                "codigo": codigo,
                "nombre": nombre,
                "descripcion": None,
                "url_github": None,
                "fuente": "sin_descripcion",
                "existe": False
            }
        
        logger.info(f"🔍 Buscando imagen para: {descripcion}")
        
        # Verificar cache
        if codigo in self.cache:
            url_github = self.cache[codigo].get('url_github')
            if url_github:
                logger.info(f"📦 Imagen en cache: {codigo}")
                return {
                    "codigo": codigo,
                    "nombre": nombre,
                    "descripcion": descripcion,
                    "url_github": url_github,
                    "fuente": "cache",
                    "existe": True
                }
        
        # Buscar imagen usando descripción
        url_imagen = await self.buscar_imagen_bing(descripcion)
        if not url_imagen:
            logger.warning(f"⚠️ No se encontró imagen para: {descripcion}")
            return {
                "codigo": codigo,
                "nombre": nombre,
                "descripcion": descripcion,
                "url_github": None,
                "fuente": "ninguna",
                "existe": False
            }
        
        # Descargar imagen
        contenido_imagen = await self.descargar_imagen(url_imagen, codigo)
        if not contenido_imagen:
            logger.error(f"❌ Error descargando imagen para: {codigo}")
            return {
                "codigo": codigo,
                "nombre": nombre,
                "descripcion": descripcion,
                "url_github": None,
                "fuente": "error_descarga",
                "existe": False
            }
        
        # Guardar en GitHub
        url_github = await self.guardar_en_github(codigo, contenido_imagen, f"{codigo}.jpg")
        
        if url_github:
            # Guardar en cache
            self.cache[codigo] = {
                "nombre": nombre,
                "descripcion": descripcion,
                "url_github": url_github,
                "fecha": datetime.now().isoformat()
            }
            self._guardar_cache()
            
            return {
                "codigo": codigo,
                "nombre": nombre,
                "descripcion": descripcion,
                "url_github": url_github,
                "fuente": "github",
                "existe": True
            }
        
        return {
            "codigo": codigo,
            "nombre": nombre,
            "descripcion": descripcion,
            "url_github": None,
            "fuente": "error_github",
            "existe": False
        }

    async def procesar_lote_productos(self, productos: list[dict], max_concurrentes: int = 3) -> list[dict]:
        """Procesa múltiples productos de forma concurrente"""
        semaforo = asyncio.Semaphore(max_concurrentes)
        
        async def procesar_con_semaforo(producto):
            async with semaforo:
                codigo = producto.get('Codigo')
                nombre = producto.get('Nombre')
                descripcion = producto.get('Descripcion', None)  # ✅ LEER DESCRIPCIÓN
                resultado_imagen = await self.procesar_producto(codigo, nombre, descripcion)
                return {**producto, "imagen": resultado_imagen}
        
        tareas = [procesar_con_semaforo(p) for p in productos]
        resultados = await asyncio.gather(*tareas, return_exceptions=True)
        return [r for r in resultados if not isinstance(r, Exception)]

# ✅ EJEMPLO DE USO:
"""
async def main():
    gestor = GestorImagenesProductos(
        directorio_imagenes="./imagenes",
        github_token="tu_token_github",
        github_repo="tu_usuario/tu_repo"
    )
    
    productos = [
        {"Codigo": "001", "Nombre": "Martillo", "Descripcion": "Martillo de acero inoxidable"},
        {"Codigo": "002", "Nombre": "Clavo", "Descripcion": ""},  # Sin descripción
        {"Codigo": "003", "Nombre": "Tornillo"},  # Sin descripción
    ]
    
    resultados = await gestor.procesar_lote_productos(productos)
    print(json.dumps(resultados, indent=2, ensure_ascii=False))

# asyncio.run(main())
"""