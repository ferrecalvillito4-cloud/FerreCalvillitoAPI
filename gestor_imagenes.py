import os
import json
import asyncio
import aiohttp
import re
from datetime import datetime
import logging
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GestorImagenesProductos:
    """
    Gestor SIMPLE Y FUNCIONAL - Scraping directo de Google Images
    Funciona en Render sin problemas
    """
    
    def __init__(self, directorio_imagenes: str = None, github_token: str = None, github_repo: str = None):
        self.cache_memoria = {}
        logger.info("✅ Gestor de imágenes inicializado (Google Images - Scraping)")

    # -------------------------------------------------------------------------
    # 🔍 BUSCADOR GOOGLE IMAGES (FUNCIONAL)
    # -------------------------------------------------------------------------
    async def buscar_imagen_google(self, termino: str, session: aiohttp.ClientSession) -> str:
        """
        Extrae URLs directas de Google Images sin API
        """
        try:
            await asyncio.sleep(random.uniform(0.3, 0.8))
            
            # Headers realistas
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            # URL de Google Images
            url = f"https://www.google.com/search?q={termino}&tbm=isch&hl=es"
            
            try:
                async with session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15),
                    allow_redirects=True
                ) as resp:
                    
                    if resp.status != 200:
                        logger.debug(f"Google respondió: {resp.status}")
                        return None
                    
                    html = await resp.text()
                    
                    # Buscar URLs de imágenes en el HTML
                    # Google guarda las imágenes en data atributos
                    pattern = r'"(https://[^"]*\.(?:jpg|jpeg|png|gif|webp))[^"]*"'
                    matches = re.findall(pattern, html, re.IGNORECASE)
                    
                    if matches:
                        # Retornar la primera URL válida
                        for url_img in matches:
                            # Filtrar URLs de Google
                            if 'google' not in url_img and len(url_img) < 500:
                                logger.info(f"   ✅ URL encontrada")
                                return url_img
                    
                    # Alternativa: buscar en script tags
                    script_pattern = r'(?:src|href)=["\']?([^"\'>\s]*\.(?:jpg|jpeg|png|gif|webp))'
                    matches = re.findall(script_pattern, html, re.IGNORECASE)
                    
                    if matches:
                        for url_img in matches:
                            if url_img.startswith('http') and 'google' not in url_img:
                                logger.info(f"   ✅ URL encontrada")
                                return url_img
                    
                    return None
                    
            except asyncio.TimeoutError:
                logger.debug("Timeout en Google")
                return None
            
        except Exception as e:
            logger.debug(f"Error Google: {str(e)[:80]}")
            return None

    # -------------------------------------------------------------------------
    # 🔍 BUSCADOR ALTERNATIVO: UNSPLASH (Sin API key, solo scraping)
    # -------------------------------------------------------------------------
    async def buscar_imagen_unsplash_scrape(self, termino: str, session: aiohttp.ClientSession) -> str:
        """
        Obtiene imágenes de Unsplash sin API key
        """
        try:
            await asyncio.sleep(random.uniform(0.2, 0.5))
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            # URL de búsqueda de Unsplash
            url = f"https://unsplash.com/napi/search/photos?query={termino}&per_page=1"
            
            async with session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                
                if resp.status == 200:
                    try:
                        data = await resp.json()
                        
                        if data.get("results") and len(data["results"]) > 0:
                            img_url = data["results"][0].get("urls", {}).get("regular")
                            
                            if img_url:
                                logger.info(f"   ✅ Unsplash OK")
                                return img_url
                    except:
                        pass
                
                return None
                
        except Exception as e:
            logger.debug(f"Error Unsplash: {str(e)[:80]}")
            return None

    # -------------------------------------------------------------------------
    # 🔍 PROCESAR PRODUCTO - Intenta 2 fuentes
    # -------------------------------------------------------------------------
    async def procesar_producto(self, codigo: str, nombre: str, session: aiohttp.ClientSession) -> dict:
        """
        Busca imagen en Unsplash primero, luego Google
        """
        
        termino = nombre.strip() if nombre else ""

        if not termino or len(termino) < 2:
            return {
                "Codigo": codigo,
                "imagen": {"existe": False, "url_github": None}
            }

        termino_limpio = termino.lstrip('/').strip()[:80]
        logger.info(f"🔍 {codigo}: '{termino_limpio[:50]}'")

        # 1. Intentar Unsplash (API libre, más confiable)
        url_img = await self.buscar_imagen_unsplash_scrape(termino_limpio, session)
        if url_img:
            return {
                "Codigo": codigo,
                "imagen": {"existe": True, "url_github": url_img, "fuente": "unsplash"}
            }

        # 2. Intentar Google Images (fallback)
        url_img = await self.buscar_imagen_google(termino_limpio, session)
        if url_img:
            return {
                "Codigo": codigo,
                "imagen": {"existe": True, "url_github": url_img, "fuente": "google"}
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
        max_concurrentes: int = 3,
        productos_por_lote: int = 30,
        pausa_entre_lotes: int = 90
    ) -> list[dict]:
        
        total = len(productos)
        resultados = []
        
        logger.info(f"\n🚀 INICIANDO PROCESAMIENTO DE {total} PRODUCTOS")
        logger.info(f"   ⚙️ Fuente: Unsplash + Google Images")
        logger.info(f"   ⚙️ Concurrentes: {max_concurrentes}")

        timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=10)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
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
                    logger.info(f"⏸️ Pausa {pausa_entre_lotes}s...")
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