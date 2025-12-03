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
    Gestor CON IA - HuggingFace API para extraer URLs de imágenes automáticamente
    """
    
    def __init__(self, directorio_imagenes: str = None, github_token: str = None, github_repo: str = None):
        self.cache_memoria = {}
        self.hf_token = os.getenv("HUGGINGFACE_TOKEN")
        self.pexels_key = os.getenv("PEXELS_API_KEY", "7uKpeg5kqPkJgnpyd4Uq5F6kSj0rt5GJH9RPZLJbqN2i6hfWBfO3IdeZ")
        logger.info("✅ Gestor inicializado (HuggingFace IA + Pexels API)")

    # -------------------------------------------------------------------------
    # 🤖 USAR IA PARA EXTRAER MEJOR BÚSQUEDA
    # -------------------------------------------------------------------------
    async def extraer_termino_ia(self, nombre_producto: str, session: aiohttp.ClientSession) -> str:
        """
        Usa HuggingFace IA para extraer el mejor término de búsqueda del nombre del producto
        """
        try:
            await asyncio.sleep(random.uniform(0.2, 0.4))
            
            headers = {
                "Authorization": f"Bearer {self.hf_token}",
                "Content-Type": "application/json"
            }
            
            # Prompt para extraer palabra clave
            prompt = f"""Dado este nombre de producto de ferretería, extrae UNA SOLA palabra clave en INGLÉS que describe mejor el producto para buscar imágenes.

Producto: {nombre_producto}

Responde SOLO con la palabra, nada más. Ejemplo:
- "MARTILLO 5LB SURTEK" → hammer
- "ZAPAPICO 7LB" → pickaxe
- "CERA LIQUIDA BLANCA" → wax
- "TUBO PVC 2 PULGADAS" → pipe
- "CABLE ELECTRICO" → electrical wire

Palabra clave:"""
            
            payload = {
                "inputs": prompt,
                "parameters": {
                    "max_length": 50,
                    "temperature": 0.3
                }
            }
            
            async with session.post(
                "https://api-inference.huggingface.co/models/meta-llama/Llama-2-7b-chat-hf",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                
                if resp.status == 200:
                    try:
                        data = await resp.json()
                        
                        if isinstance(data, list) and len(data) > 0:
                            texto = data[0].get("generated_text", "")
                            
                            # Extraer solo la última línea (la respuesta)
                            lineas = texto.split("\n")
                            respuesta = lineas[-1].strip().lower()
                            
                            # Limpiar
                            respuesta = respuesta.replace("palabra clave:", "").replace(":", "").strip()
                            
                            if respuesta and len(respuesta) > 1:
                                logger.debug(f"   IA extrajo: '{respuesta}'")
                                return respuesta
                    except Exception as e:
                        logger.debug(f"Error parseando IA: {str(e)[:80]}")
                        return None
                
                return None
                    
        except asyncio.TimeoutError:
            logger.debug("Timeout HuggingFace IA")
            return None
        except Exception as e:
            logger.debug(f"Error HuggingFace: {str(e)[:80]}")
            return None

    # -------------------------------------------------------------------------
    # 🔍 BUSCAR EN PEXELS
    # -------------------------------------------------------------------------
    async def buscar_imagen_pexels(self, termino: str, session: aiohttp.ClientSession) -> str:
        """
        Busca imágenes en Pexels con término extraído por IA
        """
        try:
            await asyncio.sleep(random.uniform(0.2, 0.5))
            
            headers = {
                "Authorization": self.pexels_key,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
            
            params = {
                "query": termino,
                "per_page": 1,
                "orientation": "portrait",
                "size": "medium"
            }
            
            async with session.get(
                "https://api.pexels.com/v1/search",
                headers=headers,
                params=params,
                timeout=aiohttp.ClientTimeout(total=12)
            ) as resp:
                
                if resp.status == 200:
                    try:
                        data = await resp.json()
                        
                        if data.get("photos") and len(data["photos"]) > 0:
                            img = data["photos"][0]
                            url = img.get("src", {}).get("large")
                            
                            if url and url.startswith("http"):
                                logger.info(f"   ✅ Imagen encontrada (término: '{termino}')")
                                return url
                    except Exception as e:
                        logger.debug(f"Error Pexels: {str(e)[:80]}")
                        return None
                
                return None
                    
        except Exception as e:
            logger.debug(f"Error búsqueda: {str(e)[:80]}")
            return None

    # -------------------------------------------------------------------------
    # 🔍 PROCESAR PRODUCTO
    # -------------------------------------------------------------------------
    async def procesar_producto(self, codigo: str, nombre: str, session: aiohttp.ClientSession) -> dict:
        """
        1. Usa IA para extraer mejor término de búsqueda
        2. Busca imagen en Pexels
        3. Retorna URL o nada
        """
        
        nombre_limpio = nombre.strip() if nombre else ""

        if not nombre_limpio or len(nombre_limpio) < 2:
            return {
                "Codigo": codigo,
                "imagen": {"existe": False, "url_github": None}
            }

        logger.info(f"🔍 {codigo}: '{nombre_limpio[:50]}'")

        # 1. Extraer término con IA
        termino_ia = await self.extraer_termino_ia(nombre_limpio, session)
        
        if not termino_ia:
            logger.info("   ❌ IA no extrajo término")
            return {
                "Codigo": codigo,
                "imagen": {"existe": False, "url_github": None}
            }

        # 2. Buscar imagen con término extraído
        url_img = await self.buscar_imagen_pexels(termino_ia, session)
        
        if url_img:
            logger.info(f"   ✅ Encontrada")
            return {
                "Codigo": codigo,
                "imagen": {"existe": True, "url_github": url_img, "fuente": "pexels_ia"}
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
        max_concurrentes: int = 2,  # Reducido (IA es lenta)
        productos_por_lote: int = 20,  # Lotes pequeños
        pausa_entre_lotes: int = 45
    ) -> list[dict]:
        
        total = len(productos)
        resultados = []
        
        logger.info(f"\n🚀 INICIANDO PROCESAMIENTO DE {total} PRODUCTOS")
        logger.info(f"   ⚙️ Fuente: HuggingFace IA + Pexels API")
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
                logger.info(f"   Tasa éxito: {(encontradas/len(lote_result)*100):.1f}%" if lote_result else "0%")

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