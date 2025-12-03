import os
import json
import asyncio
import aiohttp
import re
from datetime import datetime
import logging
import random
from urllib.parse import quote

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GestorImagenesProductos:
    """
    Gestor SIMPLE - Va directamente a Google Images y extrae URLs reales
    """
    
    def __init__(self, directorio_imagenes: str = None, github_token: str = None, github_repo: str = None):
        self.cache_memoria = {}
        logger.info("✅ Gestor inicializado (Google Images - URLs reales)")

    # -------------------------------------------------------------------------
    # 🔍 EXTRAER URL DE GOOGLE IMAGES
    # -------------------------------------------------------------------------
    async def buscar_imagen_google_direct(self, termino: str, session: aiohttp.ClientSession) -> str:
        """
        Va a Google Images y extrae la URL de la primera imagen
        """
        try:
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # Headers que parecen un navegador real
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "es-ES,es;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            }
            
            # URL directa de Google Images
            termino_encoded = quote(termino)
            url = f"https://www.google.com/search?q={termino_encoded}&tbm=isch&hl=es"
            
            logger.info(f"   Buscando en Google Images...")
            
            try:
                async with session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=20),
                    ssl=False
                ) as resp:
                    
                    if resp.status != 200:
                        logger.debug(f"Google respondió: {resp.status}")
                        return None
                    
                    html = await resp.text()
                    
                    # =====================================================
                    # EXTRAE URLs REALES DE IMÁGENES DEL HTML
                    # =====================================================
                    
                    # Patrón 1: URLs en atributos data-src
                    pattern1 = r'data-src="([^"]*\.(?:jpg|jpeg|png|gif|webp)[^"]*)"'
                    matches = re.findall(pattern1, html, re.IGNORECASE)
                    
                    if matches:
                        for url_img in matches:
                            if url_img.startswith('http') and len(url_img) < 500:
                                logger.info(f"   ✅ URL extraída (data-src)")
                                return url_img
                    
                    # Patrón 2: URLs en img src
                    pattern2 = r'src="([^"]*\.(?:jpg|jpeg|png|gif|webp)[^"]*)"'
                    matches = re.findall(pattern2, html, re.IGNORECASE)
                    
                    if matches:
                        for url_img in matches:
                            if url_img.startswith('http') and 'google' not in url_img and len(url_img) < 500:
                                logger.info(f"   ✅ URL extraída (src)")
                                return url_img
                    
                    # Patrón 3: URLs en JSON dentro de script tags
                    pattern3 = r'"(https://[^"]*\.(?:jpg|jpeg|png|gif|webp)[^"]*)"'
                    matches = re.findall(pattern3, html, re.IGNORECASE)
                    
                    if matches:
                        for url_img in matches:
                            if 'google' not in url_img and len(url_img) < 500:
                                logger.info(f"   ✅ URL extraída (JSON)")
                                return url_img
                    
                    # Patrón 4: URLs sin protocolo pero claramente imágenes
                    pattern4 = r'(?:https?://)?([a-zA-Z0-9\-._~:/?#\[\]@!$&\'()*+,;=]+\.(?:jpg|jpeg|png|gif|webp))(?:["\'\s]|$)'
                    matches = re.findall(pattern4, html, re.IGNORECASE)
                    
                    if matches:
                        for url_img in matches:
                            if url_img.startswith('http'):
                                logger.info(f"   ✅ URL extraída (pattern4)")
                                return url_img
                    
                    logger.debug("No se encontró URL en HTML de Google")
                    return None
                    
            except asyncio.TimeoutError:
                logger.debug("Timeout en Google Images")
                return None
            except Exception as e:
                logger.debug(f"Error obteniendo HTML: {str(e)[:80]}")
                return None
        
        except Exception as e:
            logger.debug(f"Error general: {str(e)[:80]}")
            return None

    # -------------------------------------------------------------------------
    # 🔍 PROCESAR PRODUCTO
    # -------------------------------------------------------------------------
    async def procesar_producto(self, codigo: str, nombre: str, session: aiohttp.ClientSession) -> dict:
        """
        Busca imagen en Google Images y extrae URL real
        """
        
        termino = nombre.strip() if nombre else ""

        if not termino or len(termino) < 2:
            return {
                "Codigo": codigo,
                "imagen": {"existe": False, "url_github": None}
            }

        termino_limpio = termino.lstrip('/').strip()[:100]
        logger.info(f"🔍 {codigo}: '{termino_limpio[:50]}'")

        # Buscar en Google Images
        url_img = await self.buscar_imagen_google_direct(termino_limpio, session)
        
        if url_img:
            logger.info(f"   ✅ Encontrada: {url_img[:70]}...")
            return {
                "Codigo": codigo,
                "imagen": {"existe": True, "url_github": url_img, "fuente": "google_images"}
            }

        logger.info("   ❌ Sin resultados")
        return {
            "Codigo": codigo,
            "imagen": {"existe": False, "url_github": None}
        }

    # -------------------------------------------------------------------------
    # 🔁 PROCESAR LOTES
    # -------------------------------------------------------------------------
    async def procesar_lote_productos(
        self,
        productos: list[dict],
        max_concurrentes: int = 2,  # Bajo para no sobrecargar Google
        productos_por_lote: int = 25,
        pausa_entre_lotes: int = 120
    ) -> list[dict]:
        
        total = len(productos)
        resultados = []
        
        logger.info(f"\n🚀 INICIANDO PROCESAMIENTO DE {total} PRODUCTOS")
        logger.info(f"   ⚙️ Fuente: Google Images (URLs reales)")
        logger.info(f"   ⚙️ Concurrentes: {max_concurrentes}")

        timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=15)
        
        connector = aiohttp.TCPConnector(limit_per_host=2, ssl=False)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            for i in range(0, total, productos_por_lote):
                lote = productos[i:i + productos_por_lote]
                lote_num = (i // productos_por_lote) + 1
                lotes_totales = (total // productos_por_lote) + (1 if total % productos_por_lote else 0)

                logger.info(f"\n{'='*60}")
                logger.info(f"📦 LOTE {lote_num}/{lotes_totales} - {len(lote)} productos")
                logger.info(f"{'='*60}")

                semaforo = asyncio.Semaphore(max_concurrentes)

                async def procesar_con_limite(prod):
                    async with semaforo:
                        try:
                            return await self.procesar_producto(
                                prod.get("Codigo", ""),
                                prod.get("Nombre", ""),
                                session
                            )
                        except Exception as e:
                            logger.error(f"❌ {prod.get('Codigo')}: {str(e)[:50]}")
                            return {
                                "Codigo": prod.get("Codigo"),
                                "imagen": {"existe": False, "url_github": None}
                            }

                tareas = [procesar_con_limite(p) for p in lote]
                lote_result = await asyncio.gather(*tareas, return_exceptions=True)
                lote_result = [r for r in lote_result if isinstance(r, dict)]
                resultados.extend(lote_result)

                encontradas = sum(1 for r in lote_result if r.get('imagen', {}).get('existe'))

                logger.info(f"\n✅ Lote {lote_num} completado")
                logger.info(f"   Procesados: {len(lote_result)}/{len(lote)}")
                logger.info(f"   Encontradas: {encontradas}")
                logger.info(f"   Total acumulado: {len(resultados)}/{total}")

                if (i + productos_por_lote) < total:
                    logger.info(f"⏸️ Pausa {pausa_entre_lotes}s antes del siguiente lote...")
                    await asyncio.sleep(pausa_entre_lotes)

        logger.info(f"\n{'='*60}")
        logger.info("🎉 PROCESAMIENTO COMPLETADO")
        total_encontradas = sum(1 for r in resultados if r.get('imagen', {}).get('existe'))
        tasa = (total_encontradas/len(resultados)*100) if resultados else 0
        logger.info(f"   Total procesados: {len(resultados)}")
        logger.info(f"   Imágenes encontradas: {total_encontradas}")
        logger.info(f"   Tasa éxito: {tasa:.1f}%")
        logger.info(f"{'='*60}\n")
        
        return resultados

    # -------------------------------------------------------------------------
    # 📊 PROGRESO
    # -------------------------------------------------------------------------
    def obtener_progreso(self) -> dict:
        return {
            "procesados": 0,
            "total": 0,
            "porcentaje": 0,
            "ultimo_lote": 0
        }