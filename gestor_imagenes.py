import os
import json
import asyncio
import aiohttp
import re
from datetime import datetime
from pathlib import Path
import logging
import base64
import httpx

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

    async def buscar_imagen_bing(self, nombre_producto: str, session: aiohttp.ClientSession = None) -> str:
        """
        Buscar imagen en Bing con varios fallbacks.
        Devuelve la primera URL válida o None.
        """
        query = nombre_producto.replace(" ", "+")
        url = f"https://www.bing.com/images/search?q={query}&qft=+filterui:imagesize-large"  # pedimos imágenes grandes
        close_session = False
        if session is None:
            session = aiohttp.ClientSession()
            close_session = True

        try:
            async with session.get(url, headers={**self.headers, "Accept-Language": "es-ES,es;q=0.9"}) as resp:
                if resp.status != 200:
                    logger.warning(f"bing status {resp.status} para {nombre_producto}")
                    return None
                html = await resp.text()
        except Exception as e:
            logger.error(f"Error petición Bing: {e}")
            if close_session:
                await session.close()
            return None

        # Estrategia 1: buscar "murl":"http..." (JSON incrustado)
        patterns = [
            r'"murl":"(https?://[^"]+)"',
            r'"imageUrl":"(https?://[^"]+)"',
            r'"thumbUrl":"(https?://[^"]+)"',
            r'src=\"(https?://[^"\']+\.(?:jpg|jpeg|png|gif))\"',         # <img src=...>
            r'data-src=\"(https?://[^"\']+\.(?:jpg|jpeg|png|gif))\"',    # data-src=
            r'\"viewUrl\":\"(https?://[^\"]+)\"',
        ]

        candidatos = []
        for pat in patterns:
            encontrados = re.findall(pat, html)
            if encontrados:
                candidatos.extend(encontrados)

        # Normalizar y probar candidatos (truncar parámetros largos)
        def clean_url(u):
            # quitar barras dobles y espacios codificados raros
            u = u.replace('\\/', '/')
            # algunas urls vienen con caracteres escapados
            return u

        for u in candidatos:
            url_limpia = clean_url(u)
            # simple filtrado: debe empezar con http y terminar con extensión o contener imagen
            if re.match(r'https?://', url_limpia):
                # preferir urls con extensiones explícitas
                if re.search(r'\.(jpg|jpeg|png|gif)(?:\?|$)', url_limpia, re.IGNORECASE):
                    if close_session:
                        await session.close()
                    logger.info(f"✅ Bing candidate (ext): {url_limpia}")
                    return url_limpia

        # Si no hay candidatos con extensión, intentar verificar otros candidatos probando HEAD/GET
        for u in candidatos:
            url_limpia = clean_url(u)
            try:
                async with session.get(url_limpia, headers=self.headers, timeout=10) as r2:
                    if r2.status == 200:
                        ctype = r2.headers.get('Content-Type','').lower()
                        if 'image' in ctype:
                            if close_session:
                                await session.close()
                            logger.info(f"✅ Bing candidate (content-type): {url_limpia}")
                            return url_limpia
            except Exception:
                continue

        # Último intento: buscar <a class="iusc" ...> que contiene metadata con "m"
        # la data aparece en atributos tipo: m="{... 'murl':'https://...' ...}"
        extra = re.findall(r'<a[^>]+class="iusc"[^>]+m="([^"]+)"', html)
        for mdata_esc in extra:
            # mdata_esc viene con comillas escapadas. intentar extraer murl dentro.
            mdata = mdata_esc.replace('&quot;', '"')
            m = re.search(r"'murl':'(https?://[^']+)'", mdata)
            if m:
                url_limpia = m.group(1)
                if close_session:
                    await session.close()
                logger.info(f"✅ Bing candidate (iusc): {url_limpia}")
                return url_limpia

        if close_session:
            await session.close()
        logger.warning(f"⚠️ No se encontraron URLs para {nombre_producto}")
        return None

    async def descargar_imagen(self, url_imagen: str, nombre_archivo: str, session: aiohttp.ClientSession = None) -> bytes:
        """
        Descarga la imagen y retorna bytes. Mejor validación de magic bytes y Content-Type.
        """
        close_session = False
        if session is None:
            session = aiohttp.ClientSession()
            close_session = True

        try:
            async with session.get(url_imagen, headers=self.headers, timeout=20) as resp:
                if resp.status != 200:
                    logger.warning(f"Descarga {nombre_archivo} status {resp.status}")
                    if close_session:
                        await session.close()
                    return None

                contenido = await resp.read()

                # primero revisar header
                ctype = resp.headers.get("Content-Type", "").lower()
                if "image" in ctype:
                    # validación adicional por magic bytes (más flexible)
                    if contenido.startswith(b'\xff\xd8') or contenido.startswith(b'\x89PNG') or contenido[:4] in (b'GIF8', b'RIFF'):
                        if close_session:
                            await session.close()
                        logger.info(f"✅ Imagen descargada y validada: {nombre_archivo}")
                        return contenido
                    else:
                        # si el header dice image pero magic bytes no convencionales, igual aceptar con advertencia
                        logger.warning(f"Advertencia: Content-Type image pero magic bytes desconocidos para {nombre_archivo}")
                        if len(contenido) > 100:  # heurística: suficiente tamaño
                            if close_session:
                                await session.close()
                            return contenido
                else:
                    # fallback: intentar deducir por magic bytes
                    if contenido.startswith(b'\xff\xd8') or contenido.startswith(b'\x89PNG') or contenido[:4] in (b'GIF8', b'RIFF'):
                        if close_session:
                            await session.close()
                        logger.info(f"✅ Imagen descargada por magic bytes: {nombre_archivo}")
                        return contenido

        except Exception as e:
            logger.error(f"❌ Error descargando {url_imagen}: {e}")

        if close_session:
            await session.close()
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

        if not descripcion or descripcion.strip() == "":
          logger.warning(f"⚠️ Sin descripción para {codigo}, no se busca imagen.")
          return {
            "codigo": codigo,
            "nombre": nombre,
            "descripcion": None,
            "url_github": None,
            "fuente": "sin_descripcion",
            "existe": False
        }

        logger.info(f"🔍 Buscando URL de imagen para: {descripcion}")

    # Buscar URL en Bing
        url_imagen = await self.buscar_imagen_bing(descripcion)

        if not url_imagen:
           logger.warning(f"⚠️ No se encontró imagen para {descripcion}")
        return {
            "codigo": codigo,
            "nombre": nombre,
            "descripcion": descripcion,
            "url_github": None,
            "fuente": "ninguna",
            "existe": False
        }

        logger.info(f"✅ URL encontrada: {url_imagen}")

    # GUARDAR EN CACHE COMO C#
        self.cache[codigo] = {
        "nombre": nombre,
        "descripcion": descripcion,
        "url_github": url_imagen,
        "fecha": datetime.now().isoformat()
        }
        self._guardar_cache()

    # 🔥 RETORNAR FORMATO COMPATIBLE CON C#
        return {
        "codigo": codigo,
        "nombre": nombre,
        "descripcion": descripcion,
        "url_github": url_imagen,
        "fuente": "url_internet",
        "existe": True
    }

    async def procesar_lote_productos(self, productos: list[dict], max_concurrentes: int = 3) -> list[dict]:
      """Procesa múltiples productos de forma concurrente, obteniendo solo URL de internet."""
      semaforo = asyncio.Semaphore(max_concurrentes)

      async def procesar_con_semaforo(producto):
        async with semaforo:
            codigo = producto.get("Codigo")
            nombre = producto.get("Nombre")
            descripcion = producto.get("Descripcion")

            resultado = await self.procesar_producto(codigo, nombre, descripcion)

            # ESTRUCTURA final EXACTA:
            return {
                **producto,
                "imagen": {
                    "existe": resultado["existe"],
                    "url_github": resultado["url_github"],  # es URL pública real
                    "fuente": resultado["fuente"]
                }
            }
        tareas = [procesar_con_semaforo(p) for p in productos]
        resultados = await asyncio.gather(*tareas, return_exceptions=True)
        return [r for r in resultados if not isinstance(r, Exception)]