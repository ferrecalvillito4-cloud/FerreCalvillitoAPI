import os
import json
import asyncio
import aiohttp
import re
from datetime import datetime
from pathlib import Path
import logging
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GestorImagenesProductos:
    def __init__(self, directorio_imagenes: str, github_token: str = None, github_repo: str = None):
        self.directorio_imagenes = directorio_imagenes
        Path(directorio_imagenes).mkdir(parents=True, exist_ok=True)
        self.cache_file = os.path.join(directorio_imagenes, "descargadas.json")
        self.progreso_file = os.path.join(directorio_imagenes, "progreso.json")
        self.cache = self._cargar_cache()
        self.progreso = self._cargar_progreso()
        
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
    
    def _cargar_progreso(self) -> dict:
        """Carga el progreso del procesamiento"""
        if os.path.exists(self.progreso_file):
            try:
                with open(self.progreso_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {"procesados": 0, "total": 0, "ultimo_lote": 0}
        return {"procesados": 0, "total": 0, "ultimo_lote": 0}
    
    def _guardar_progreso(self):
        """Guarda el progreso"""
        with open(self.progreso_file, 'w', encoding='utf-8') as f:
            json.dump(self.progreso, f, indent=2)

    def _get_headers(self) -> dict:
        """Retorna headers aleatorios para evitar detección"""
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15'
        ]
        
        return {
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }

    async def buscar_imagen_google(self, nombre_producto: str, session: aiohttp.ClientSession) -> str:
        """Busca la primera imagen en Google Images"""
        try:
            # Delay aleatorio entre 3-7 segundos
            await asyncio.sleep(random.uniform(3, 7))
            
            query = nombre_producto.replace(" ", "+")
            url = f"https://www.google.com/search?q={query}&tbm=isch&hl=es"
            
            logger.info(f"🔍 Buscando: {nombre_producto}")
            
            async with session.get(url, headers=self._get_headers(), timeout=20) as resp:
                if resp.status != 200:
                    logger.warning(f"⚠️ Google status {resp.status}")
                    return None
                
                html = await resp.text()
            
            # Patrones para extraer URLs
            patrones = [
                r'"(https://[^"]+\.(?:jpg|jpeg|png|webp|gif))"',
                r'src="(https://[^"]+\.(?:jpg|jpeg|png|webp))"',
                r'\["(https://[^"]+\.(?:jpg|jpeg|png|webp))"',
            ]
            
            for patron in patrones:
                matches = re.findall(patron, html, re.IGNORECASE)
                for url_imagen in matches:
                    # Filtrar URLs de Google
                    if any(x in url_imagen for x in ['google.com', 'gstatic.com', 'googleusercontent']):
                        continue
                    
                    if re.search(r'\.(jpg|jpeg|png|webp|gif)($|\?)', url_imagen, re.IGNORECASE):
                        logger.info(f"✅ Imagen encontrada")
                        return url_imagen
            
            logger.warning(f"⚠️ No se encontró imagen")
            return None
            
        except asyncio.TimeoutError:
            logger.error(f"⏱️ Timeout para: {nombre_producto}")
            return None
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            return None

    async def verificar_url_imagen(self, url: str, session: aiohttp.ClientSession) -> bool:
        """Verifica que la URL sea accesible"""
        try:
            async with session.head(url, headers=self._get_headers(), timeout=10) as resp:
                if resp.status == 200:
                    content_type = resp.headers.get('Content-Type', '').lower()
                    return 'image' in content_type
        except:
            pass
        return False

    async def procesar_producto(self, codigo: str, nombre: str, descripcion: str, session: aiohttp.ClientSession) -> dict:
        """Procesa un solo producto"""
        
        # Si ya está en caché, usar ese
        if codigo in self.cache:
            cached = self.cache[codigo]
            logger.info(f"📦 {codigo}: Usando caché")
            return {
                "codigo": codigo,
                "nombre": nombre,
                "descripcion": descripcion,
                "url_github": cached.get("url_github"),
                "existe": bool(cached.get("url_github")),
                "fuente": "cache"
            }
        
        termino = descripcion if descripcion and descripcion.strip() else nombre
        
        if not termino or termino.strip() == "":
            return {
                "codigo": codigo,
                "nombre": nombre,
                "descripcion": descripcion,
                "url_github": None,
                "existe": False,
                "fuente": "sin_descripcion"
            }
        
        # Buscar imagen
        url_imagen = await self.buscar_imagen_google(termino, session)
        
        # Verificar que funcione
        if url_imagen:
            if not await self.verificar_url_imagen(url_imagen, session):
                logger.warning(f"⚠️ URL no válida")
                url_imagen = None
        
        # Guardar en caché
        if url_imagen:
            self.cache[codigo] = {
                "nombre": nombre,
                "descripcion": descripcion,
                "url_github": url_imagen,
                "fecha": datetime.now().isoformat()
            }
            self._guardar_cache()
            logger.info(f"✅ {codigo}: Guardado")
        
        return {
            "codigo": codigo,
            "nombre": nombre,
            "descripcion": descripcion,
            "url_github": url_imagen,
            "existe": bool(url_imagen),
            "fuente": "google" if url_imagen else "no_encontrada"
        }

    async def procesar_lote_productos(
        self, 
        productos: list[dict], 
        max_concurrentes: int = 2,
        productos_por_lote: int = 50,
        pausa_entre_lotes: int = 120  # 2 minutos
    ) -> list[dict]:
        """
        Procesa productos en lotes pequeños con pausas largas
        
        Args:
            productos: Lista de productos
            max_concurrentes: Búsquedas simultáneas (2 recomendado)
            productos_por_lote: Productos por lote (50 recomendado)
            pausa_entre_lotes: Segundos entre lotes (120 = 2 minutos)
        """
        
        total_productos = len(productos)
        self.progreso["total"] = total_productos
        
        logger.info(f"\n{'='*60}")
        logger.info(f"🚀 INICIANDO PROCESAMIENTO POR LOTES")
        logger.info(f"   Total productos: {total_productos}")
        logger.info(f"   Productos por lote: {productos_por_lote}")
        logger.info(f"   Pausa entre lotes: {pausa_entre_lotes}s ({pausa_entre_lotes//60} min)")
        logger.info(f"   Tiempo estimado: {(total_productos / productos_por_lote) * (pausa_entre_lotes / 60):.1f} min")
        logger.info(f"{'='*60}\n")
        
        resultados_totales = []
        num_lotes = (total_productos + productos_por_lote - 1) // productos_por_lote
        
        async with aiohttp.ClientSession() as session:
            for i in range(0, total_productos, productos_por_lote):
                lote_num = (i // productos_por_lote) + 1
                lote = productos[i:i + productos_por_lote]
                
                logger.info(f"\n📦 LOTE {lote_num}/{num_lotes} ({len(lote)} productos)")
                logger.info(f"   Progreso global: {i}/{total_productos} ({(i/total_productos*100):.1f}%)")
                
                # Procesar lote con semáforo
                semaforo = asyncio.Semaphore(max_concurrentes)
                
                async def procesar_con_semaforo(producto):
                    async with semaforo:
                        resultado = await self.procesar_producto(
                            producto.get("Codigo"),
                            producto.get("Nombre"),
                            producto.get("Descripcion"),
                            session
                        )
                        
                        return {
                            **producto,
                            "imagen": {
                                "existe": resultado["existe"],
                                "url_github": resultado["url_github"],
                                "fuente": resultado.get("fuente", "no_encontrada")
                            }
                        }
                
                tareas = [procesar_con_semaforo(p) for p in lote]
                resultados = await asyncio.gather(*tareas, return_exceptions=True)
                
                # Filtrar errores
                resultados_validos = [r for r in resultados if not isinstance(r, Exception)]
                resultados_totales.extend(resultados_validos)
                
                # Actualizar progreso
                self.progreso["procesados"] = i + len(lote)
                self.progreso["ultimo_lote"] = lote_num
                self._guardar_progreso()
                
                exitosos = sum(1 for r in resultados_validos if r.get("imagen", {}).get("existe"))
                logger.info(f"   ✅ Lote completado: {exitosos}/{len(lote)} con imagen")
                
                # Pausa entre lotes (excepto en el último)
                if i + productos_por_lote < total_productos:
                    logger.info(f"   ⏸️ Esperando {pausa_entre_lotes}s antes del siguiente lote...")
                    logger.info(f"   ⏱️ Siguiente lote: {datetime.now().strftime('%H:%M:%S')}")
                    await asyncio.sleep(pausa_entre_lotes)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"✅ PROCESAMIENTO COMPLETADO")
        logger.info(f"   Total procesados: {len(resultados_totales)}")
        logger.info(f"   Con imagen: {sum(1 for r in resultados_totales if r.get('imagen', {}).get('existe'))}")
        logger.info(f"{'='*60}\n")
        
        return resultados_totales

    def obtener_progreso(self) -> dict:
        """Retorna el progreso actual"""
        return {
            "procesados": self.progreso.get("procesados", 0),
            "total": self.progreso.get("total", 0),
            "porcentaje": round((self.progreso.get("procesados", 0) / max(self.progreso.get("total", 1), 1)) * 100, 2),
            "ultimo_lote": self.progreso.get("ultimo_lote", 0)
        }