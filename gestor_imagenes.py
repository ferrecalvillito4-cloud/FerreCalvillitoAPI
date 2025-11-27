import os
import json
import asyncio
import aiohttp
import re
from datetime import datetime
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GestorImagenesProductos:
    def __init__(self, directorio_imagenes: str):
        self.directorio_imagenes = directorio_imagenes
        Path(directorio_imagenes).mkdir(parents=True, exist_ok=True)
        self.cache_file = os.path.join(directorio_imagenes, "descargadas.json")
        self.cache = self._cargar_cache()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

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
        query = nombre_producto.replace(" ", "+")
        url = f"https://www.bing.com/images/search?q={query}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, timeout=10) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        imagenes = re.findall(r'"murl":"([^"]+)"', html)
                        if imagenes:
                            return imagenes[0]
        except Exception as e:
            logger.error(f"Error buscando en Bing: {e}")
        
        return None

    async def descargar_imagen(self, url_imagen: str, nombre_archivo: str) -> str:
        ruta_local = os.path.join(self.directorio_imagenes, f"{nombre_archivo}.jpg")
        
        if os.path.exists(ruta_local):
            return ruta_local
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url_imagen, headers=self.headers, timeout=15) as resp:
                    if resp.status == 200:
                        contenido = await resp.read()
                        if contenido[:4] in [b'\xff\xd8\xff\xe0', b'\x89PNG', b'GIF8', b'RIFF']:
                            with open(ruta_local, 'wb') as f:
                                f.write(contenido)
                            logger.info(f"✅ Imagen descargada: {nombre_archivo}.jpg")
                            return ruta_local
        except Exception as e:
            logger.error(f"Error descargando imagen: {e}")
        
        return None

    async def procesar_producto(self, codigo: str, nombre: str) -> dict:
        if codigo in self.cache:
            ruta = self.cache[codigo]['ruta']
            if os.path.exists(ruta):
                return {
                    "codigo": codigo,
                    "url_local": f"/static/imagenes/{os.path.basename(ruta)}",
                    "fuente": "cache",
                    "existe": True
                }
        
        logger.info(f"🔍 Buscando imagen para: {nombre}")
        url_imagen = await self.buscar_imagen_bing(nombre)
        
        if not url_imagen:
            return {
                "codigo": codigo,
                "url_local": None,
                "fuente": "ninguna",
                "existe": False
            }
        
        ruta_descargada = await self.descargar_imagen(url_imagen, codigo)
        
        if ruta_descargada:
            self.cache[codigo] = {
                "nombre": nombre,
                "ruta": ruta_descargada,
                "fecha": datetime.now().isoformat()
            }
            self._guardar_cache()
            
            return {
                "codigo": codigo,
                "url_local": f"/static/imagenes/{os.path.basename(ruta_descargada)}",
                "fuente": "bing",
                "existe": True
            }
        
        return {
            "codigo": codigo,
            "url_local": None,
            "fuente": "error_descarga",
            "existe": False
        }
    
    async def procesar_producto(self, codigo: str, nombre: str) -> dict:
        if codigo in self.cache:
           ruta = self.cache[codigo]['ruta']
        if os.path.exists(ruta):
            return {
                "codigo": codigo,
                "url_local": f"/static/imagenes/{os.path.basename(ruta)}",
                "fuente": "cache",
                "existe": True
            }
    
        logger.info(f"🔍 Buscando imagen para: {nombre}")
        url_imagen = await self.buscar_imagen_bing(nombre)
    
        if not url_imagen:
           return {
            "codigo": codigo,
            "url_local": None,
            "fuente": "ninguna",
            "existe": False
        }
    
        ruta_descargada = await self.descargar_imagen(url_imagen, codigo)
    
        if ruta_descargada:
         self.cache[codigo] = {
            "nombre": nombre,
            "ruta": ruta_descargada,
            "fecha": datetime.now().isoformat()
         }
        self._guardar_cache()
        
        # 🆕 GUARDAR EN GITHUB AUTOMÁTICAMENTE
        try:
            import github_persistence as gh
            gh.guardar_imagen_github(codigo, ruta_descargada)
        except Exception as e:
            logger.warning(f"⚠️ No se guardó en GitHub: {e}")
        
        return {
            "codigo": codigo,
            "url_local": f"/static/imagenes/{os.path.basename(ruta_descargada)}",
            "fuente": "bing",
            "existe": True
        }
    
        return {
        "codigo": codigo,
        "url_local": None,
        "fuente": "error_descarga",
        "existe": False
        }

    async def procesar_lote_productos(self, productos: list[dict], max_concurrentes: int = 3) -> list[dict]:
        semaforo = asyncio.Semaphore(max_concurrentes)
        
        async def procesar_con_semaforo(producto):
            async with semaforo:
                codigo = producto.get('Codigo')
                nombre = producto.get('Nombre')
                resultado_imagen = await self.procesar_producto(codigo, nombre)
                return {**producto, "imagen": resultado_imagen}
        
        tareas = [procesar_con_semaforo(p) for p in productos]
        resultados = await asyncio.gather(*tareas, return_exceptions=True)
        return [r for r in resultados if not isinstance(r, Exception)]