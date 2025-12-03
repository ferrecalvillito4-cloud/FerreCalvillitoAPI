import os
import json
import asyncio
import aiohttp
from datetime import datetime
import logging
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GestorImagenesProductos:
    """
    Gestor OPTIMIZADO de imágenes con duckduckgo-search 8.1.1
    """
    
    def __init__(self, directorio_imagenes: str = None, github_token: str = None, github_repo: str = None):
        self.cache_memoria = {}
        logger.info("✅ Gestor de imágenes inicializado")
        
        try:
            from duckduckgo_search import DDGS
            self.ddgs = DDGS(timeout=20)
            self.tiene_ddgs = True
            logger.info("   ✅ duckduckgo-search 8.1.1 disponible")
        except ImportError:
            self.tiene_ddgs = False
            logger.warning("   ⚠️ duckduckgo-search no disponible")

    # -------------------------------------------------------------------------
    # 🔍 BUSCADOR OPTIMIZADO
    # -------------------------------------------------------------------------
    async def buscar_imagen_duckduckgo(self, termino: str, session: aiohttp.ClientSession) -> str:
        """
        Búsqueda optimizada para duckduckgo-search 8.1.1
        """
        if not self.tiene_ddgs:
            return None

        try:
            # Pausa variable para evitar bloqueos
            await asyncio.sleep(random.uniform(0.3, 0.8))
            
            loop = asyncio.get_event_loop()
            
            def buscar_sync():
                try:
                    # Usar method='news' es más rápido que 'images'
                    results = self.ddgs.images(
                        keywords=termino,
                        region="es-es",
                        safesearch="moderate",
                        max_results=3  # Solo 3, es más rápido
                    )
                    
                    if results:
                        for img in results:
                            # Intentar obtener URL
                            url = img.get('image') or img.get('url') or img.get('thumbnail')
                            
                            if url and isinstance(url, str) and url.startswith('http'):
                                # Validar que sea una URL razonable
                                if len(url) < 500 and '://' in url:
                                    return url
                    
                    return None
                except Exception as e:
                    logger.debug(f"Error búsqueda: {e}")
                    return None
            
            # Ejecutar en thread
            url_img = await asyncio.wait_for(
                loop.run_in_executor(None, buscar_sync),
                timeout=15
            )
            
            return url_img

        except asyncio.TimeoutError:
            logger.debug(f"Timeout en búsqueda: {termino[:40]}")
            return None
        except Exception as e:
            logger.debug(f"Error general: {e}")
            return None

    # -------------------------------------------------------------------------
    # 🔍 PROCESAR UN SOLO PRODUCTO
    # -------------------------------------------------------------------------
    async def procesar_producto(self, codigo: str, nombre: str, session: aiohttp.ClientSession) -> dict:
        """Busca URL de imagen para un producto"""
        
        termino = nombre.strip() if nombre else ""

        if not termino or len(termino) < 2:
            return {
                "Codigo": codigo,
                "imagen": {"existe": False, "url_github": None}
            }

        termino_limpio = termino.lstrip('/').strip()[:80]
        logger.info(f"🔍 {codigo}: '{termino_limpio[:50]}'")

        # Buscar imagen
        url_img = await self.buscar_imagen_duckduckgo(termino_limpio, session)

        if url_img:
            logger.info(f"   ✅ {url_img[:70]}...")
            return {
                "Codigo": codigo,
                "imagen": {"existe": True, "url_github": url_img}
            }

        logger.info("   ❌ Sin resultados")
        return {
            "Codigo": codigo,
            "imagen": {"existe": False, "url_github": None}
        }

    # -------------------------------------------------------------------------
    # 🔁 PROCESAR LOTES - OPTIMIZADO
    # -------------------------------------------------------------------------
    async def procesar_lote_productos(
        self,
        productos: list[dict],
        max_concurrentes: int = 4,  # AUMENTADO a 4 (más rápido)
        productos_por_lote: int = 20,  # REDUCIDO a 20 (lotes pequeños = más rápido)
        pausa_entre_lotes: int = 60  # REDUCIDO a 60s
    ) -> list[dict]:
        
        total = len(productos)
        resultados = []
        
        logger.info(f"\n🚀 INICIANDO PROCESAMIENTO DE {total} PRODUCTOS")
        logger.info(f"   ⚙️ Concurrentes: {max_concurrentes}, Por lote: {productos_por_lote}")

        # Timeout más corto para Render
        timeout = aiohttp.ClientTimeout(total=25, connect=10, sock_read=10)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for i in range(0, total, productos_por_lote):
                lote = productos[i:i + productos_por_lote]
                lote_num = (i // productos_por_lote) + 1

                logger.info(f"\n{'='*60}")
                logger.info(f"📦 LOTE {lote_num}/{(total // productos_por_lote) + 1} - {len(lote)} productos")
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

                # Pausa entre lotes (más corta)
                if (i + productos_por_lote) < total:
                    logger.info(f"⏸️ Pausa {pausa_entre_lotes}s...")
                    await asyncio.sleep(pausa_entre_lotes)

        logger.info(f"\n{'='*60}")
        logger.info("🎉 PROCESAMIENTO COMPLETADO")
        total_encontradas = sum(1 for r in resultados if r.get('imagen', {}).get('existe'))
        tasa = (total_encontradas/len(resultados)*100) if resultados else 0
        logger.info(f"   Total: {len(resultados)}")
        logger.info(f"   Encontradas: {total_encontradas}")
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