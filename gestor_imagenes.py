import os
import json
import asyncio
import aiohttp
from datetime import datetime
import logging
import random
import shutil

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GestorImagenesProductos:
    """
    Gestor GRATIS - Usa Bing Images (sin API key)
    """
    
    def __init__(self, directorio_imagenes: str = None, github_token: str = None, github_repo: str = None):
        self.cache_memoria = {}
        logger.info("✅ Gestor de imágenes inicializado (Bing Images - Gratis)")
        
        try:
            from bing_image_downloader import downloader
            self.downloader = downloader
            self.tiene_bing = True
            logger.info("   ✅ bing-image-downloader disponible")
        except ImportError:
            self.tiene_bing = False
            logger.warning("   ⚠️ Instala: pip install bing-image-downloader")

    # -------------------------------------------------------------------------
    # 🔍 BUSCADOR BING IMAGES (GRATIS)
    # -------------------------------------------------------------------------
    async def buscar_imagen_bing(self, termino: str) -> str:
        """
        Descarga imagen de Bing Images - Sin costo
        """
        if not self.tiene_bing:
            return None

        try:
            await asyncio.sleep(random.uniform(0.2, 0.6))
            
            loop = asyncio.get_event_loop()
            
            def buscar_sync():
                try:
                    # Nombre limpio para la carpeta
                    nombre_limpio = "".join(c for c in termino if c.isalnum() or c.isspace())[:30]
                    output_dir = "temp_imagenes"
                    
                    # Crear directorio temporal
                    os.makedirs(output_dir, exist_ok=True)
                    
                    # Descargar 1 imagen
                    self.downloader.download(
                        termino,
                        limit=1,
                        output_dir=output_dir,
                        adult_filter_off=True,
                        force_replace=False,
                        timeout=10,
                        verbose=False,
                        chromedriver=None  # Sin selenium
                    )
                    
                    # Buscar la imagen descargada
                    carpeta = os.path.join(output_dir, nombre_limpio)
                    
                    # Si no está con el nombre limpio, buscar directorios
                    if not os.path.exists(carpeta):
                        # Listar todos los directorios en output_dir
                        dirs = [d for d in os.listdir(output_dir) if os.path.isdir(os.path.join(output_dir, d))]
                        if dirs:
                            carpeta = os.path.join(output_dir, dirs[0])
                    
                    if os.path.exists(carpeta):
                        archivos = os.listdir(carpeta)
                        if archivos:
                            # Obtener ruta de la imagen
                            img_path = os.path.join(carpeta, archivos[0])
                            
                            # Leer como ruta local (será servida desde GitHub)
                            # Por ahora retornar la ruta local
                            if os.path.isfile(img_path):
                                logger.info(f"   ✅ Imagen descargada: {img_path}")
                                return f"file://{img_path}"
                    
                    return None
                    
                except Exception as e:
                    logger.debug(f"Error Bing: {str(e)[:100]}")
                    return None
            
            # Ejecutar en thread (no bloquea async)
            url_img = await asyncio.wait_for(
                loop.run_in_executor(None, buscar_sync),
                timeout=25
            )
            
            return url_img

        except asyncio.TimeoutError:
            logger.debug(f"Timeout en búsqueda: {termino[:40]}")
            return None
        except Exception as e:
            logger.debug(f"Error general: {str(e)[:100]}")
            return None

    # -------------------------------------------------------------------------
    # 🔍 PROCESAR PRODUCTO
    # -------------------------------------------------------------------------
    async def procesar_producto(self, codigo: str, nombre: str, session: aiohttp.ClientSession) -> dict:
        """
        Busca imagen de Bing
        """
        
        termino = nombre.strip() if nombre else ""

        if not termino or len(termino) < 2:
            return {
                "Codigo": codigo,
                "imagen": {"existe": False, "url_github": None}
            }

        termino_limpio = termino.lstrip('/').strip()[:80]
        logger.info(f"🔍 {codigo}: '{termino_limpio[:50]}'")

        # Buscar en Bing
        url_img = await self.buscar_imagen_bing(termino_limpio)
        
        if url_img and url_img.startswith("file://"):
            logger.info(f"   ✅ Encontrada")
            return {
                "Codigo": codigo,
                "imagen": {"existe": True, "url_github": url_img, "fuente": "bing"}
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
        max_concurrentes: int = 2,  # Reducido (Bing es lento)
        productos_por_lote: int = 15,  # Lotes pequeños
        pausa_entre_lotes: int = 120  # Pausa entre lotes
    ) -> list[dict]:
        
        total = len(productos)
        resultados = []
        
        logger.info(f"\n🚀 INICIANDO PROCESAMIENTO DE {total} PRODUCTOS")
        logger.info(f"   ⚙️ Fuente: Bing Images (GRATIS)")
        logger.info(f"   ⚙️ Concurrentes: {max_concurrentes}, Por lote: {productos_por_lote}")

        timeout = aiohttp.ClientTimeout(total=40, connect=10, sock_read=10)
        
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
                logger.info(f"   Encontradas en este lote: {encontradas}")
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
        
        # Limpiar archivos temporales
        if os.path.exists("temp_imagenes"):
            try:
                shutil.rmtree("temp_imagenes")
                logger.info("🗑️ Archivos temporales limpios")
            except:
                pass
        
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