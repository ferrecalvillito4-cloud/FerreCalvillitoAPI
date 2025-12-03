import os
import json
import asyncio
import aiohttp
import re
from datetime import datetime
import logging
import random
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GestorImagenesProductos:
    """
    Gestor ACTUALIZADO de imágenes que realmente funciona.
    Usa duckduckgo-search (librería oficial).
    """
    
    def __init__(self, directorio_imagenes: str = None, github_token: str = None, github_repo: str = None):
        self.cache_memoria = {}
        logger.info("✅ Gestor de imágenes inicializado")
        
        # Intentar importar la librería correcta
        try:
            from duckduckgo_search import DDGS
            self.ddgs = DDGS()
            self.tiene_ddgs = True
            logger.info("   ✅ duckduckgo-search disponible")
        except ImportError:
            self.tiene_ddgs = False
            logger.warning("   ⚠️ Instala: pip install duckduckgo-search")

    # -------------------------------------------------------------------------
    # 🔍 BUSCADOR ACTUALIZADO - USA duckduckgo-search
    # -------------------------------------------------------------------------
    async def buscar_imagen_duckduckgo(self, termino: str, session: aiohttp.ClientSession) -> str:
        """
        Versión FUNCIONAL 2025 usando duckduckgo-search
        """
        if not self.tiene_ddgs:
            logger.error("duckduckgo-search no está instalado")
            return None

        try:
            # Pequeña pausa para evitar bloqueos
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # Usar la librería en thread para no bloquear async
            loop = asyncio.get_event_loop()
            
            def buscar_sync():
                try:
                    results = self.ddgs.images(
                        keywords=termino,
                        region="es-es",
                        safesearch="moderate",
                        max_results=5
                    )
                    
                    if results and len(results) > 0:
                        # Retornar la primera imagen válida
                        for img in results:
                            url = img.get('image') or img.get('url')
                            if url and url.startswith('http'):
                                return url
                    return None
                except Exception as e:
                    logger.debug(f"Error en búsqueda: {e}")
                    return None
            
            # Ejecutar en thread pool para no bloquear
            url_img = await loop.run_in_executor(None, buscar_sync)
            
            if url_img:
                logger.info(f"   ✅ URL encontrada: {url_img[:80]}...")
            
            return url_img

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

        termino_limpio = termino.lstrip('/').strip()[:100]  # Max 100 chars
        logger.info(f"🔍 {codigo}: '{termino_limpio[:60]}'")

        # Buscar imagen
        url_img = await self.buscar_imagen_duckduckgo(termino_limpio, session)

        if url_img:
            logger.info("   ✅ Encontrada")
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
    # 🔁 PROCESAR LOTES
    # -------------------------------------------------------------------------
    async def procesar_lote_productos(
        self,
        productos: list[dict],
        max_concurrentes: int = 2,  # REDUCIDO de 3 a 2
        productos_por_lote: int = 30,  # REDUCIDO de 50 a 30
        pausa_entre_lotes: int = 180  # AUMENTADO de 120 a 180
    ) -> list[dict]:
        
        total = len(productos)
        resultados = []
        
        logger.info(f"\n🚀 INICIANDO PROCESAMIENTO DE {total} PRODUCTOS")
        logger.info(f"   ⚙️ Concurrentes: {max_concurrentes}, Por lote: {productos_por_lote}")

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            for i in range(0, total, productos_por_lote):
                lote = productos[i:i + productos_por_lote]
                lote_num = (i // productos_por_lote) + 1

                logger.info(f"\n{'='*60}")
                logger.info(f"📦 LOTE {lote_num} - {len(lote)} productos")
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
                            logger.error(f"❌ Error procesando {prod.get('Codigo')}: {e}")
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
                logger.info(f"   Imágenes encontradas: {encontradas}")
                logger.info(f"   Total acumulado: {len(resultados)}/{total}")

                # Pausa entre lotes
                if (i + productos_por_lote) < total:
                    logger.info(f"\n⏸️ Pausa de {pausa_entre_lotes}s antes del siguiente lote...")
                    await asyncio.sleep(pausa_entre_lotes)

        logger.info(f"\n{'='*60}")
        logger.info("🎉 PROCESAMIENTO COMPLETADO")
        total_encontradas = sum(1 for r in resultados if r.get('imagen', {}).get('existe'))
        logger.info(f"   Total procesados: {len(resultados)}")
        logger.info(f"   Imágenes encontradas: {total_encontradas}")
        logger.info(f"   Tasa éxito: {(total_encontradas/len(resultados)*100):.1f}%" if resultados else "N/A")
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