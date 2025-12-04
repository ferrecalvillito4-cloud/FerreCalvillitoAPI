import os
import asyncio
import aiohttp
from datetime import datetime
import logging
import random
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GestorImagenesProductos:
    """
    Gestor de imágenes usando Pexels API
    """
    
    def __init__(self, directorio_imagenes: str = None, github_token: str = None, github_repo: str = None):
        self.cache_memoria = {}
        self.pexels_key = os.getenv("PEXELS_API_KEY", "7uKpeg5kqPkJgnpyd4Uq5F6kSj0rt5GJH9RPZLJbqN2i6hfWBfO3IdeZ")
        logger.info("✅ Gestor inicializado (Pexels API)")

    # -------------------------------------------------------------------------
    # 🔍 EXTRAER TÉRMINO DE BÚSQUEDA
    # -------------------------------------------------------------------------
    def extraer_termino_busqueda(self, nombre_producto: str) -> str:
        """
        Extrae el mejor término de búsqueda del nombre del producto
        usando reglas simples pero efectivas
        """
        if not nombre_producto or not nombre_producto.strip():
            return None
        
        # Limpiar el nombre
        nombre = nombre_producto.upper().strip()
        
        # Diccionario COMPLETO de términos de ferretería a inglés
        traduccion = {
            # Herramientas manuales
            "MARTILLO": "hammer",
            "DESTORNILLADOR": "screwdriver",
            "DESARMADOR": "screwdriver",
            "PINZA": "pliers",
            "ALICATE": "pliers",
            "LLAVE": "wrench",
            "TALADRO": "drill",
            "SIERRA": "saw",
            "SERRUCHO": "handsaw",
            "PALA": "shovel",
            "ZAPAPICO": "pickaxe",
            "ZAPA-PICO": "pickaxe",
            "PICO": "pickaxe",
            "HACHA": "axe",
            "MACHETE": "machete",
            "CUCHILLO": "knife",
            "TIJERA": "scissors",
            "BROCHA": "brush",
            "RODILLO": "paint roller",
            "ESPATULA": "spatula",
            "NIVEL": "level",
            "CINTA": "tape",
            "METRO": "tape measure",
            "FLEXOMETRO": "tape measure",
            "CARRETILLA": "wheelbarrow",
            "RASTRILLO": "rake",
            "AZADON": "hoe",
            "ZAPATO": "safety shoe",
            "ZAPAPICO": "pickaxe",
            
            # Herramientas eléctricas
            "TALADRO": "drill",
            "ESMERIL": "grinder",
            "PULIDORA": "polisher",
            "LIJADORA": "sander",
            "CALADORA": "jigsaw",
            "ROTOMARTILLO": "rotary hammer",
            "AMOLADORA": "angle grinder",
            
            # Materiales eléctricos
            "CABLE": "electrical wire",
            "ALAMBRE": "wire",
            "FOCO": "light bulb",
            "BOMBILLA": "light bulb",
            "LAMPARA": "lamp",
            "APAGADOR": "light switch",
            "INTERRUPTOR": "switch",
            "CONTACTO": "outlet",
            "ENCHUFE": "plug",
            "EXTENSION": "extension cord",
            "CINTA AISLANTE": "electrical tape",
            "SOCKET": "socket",
            "TOMA": "outlet",
            "CLAVIJA": "plug",
            "CHALUPA": "electrical box",
            "REGISTRO": "electrical box",
            "ZAPATA": "terminal connector",
            "TERMINAL": "terminal",
            
            # Plomería y tubería
            "TUBO": "pipe",
            "TUBERIA": "pipe",
            "CODO": "elbow fitting",
            "CONECTOR": "connector",
            "VALVULA": "valve",
            "LLAVE DE PASO": "faucet",
            "GRIFO": "faucet",
            "PVC": "pvc pipe",
            "COBRE": "copper pipe",
            "MANGUERA": "hose",
            "COLADERA": "drain",
            "SIFON": "trap",
            "REDUCCION": "reducer fitting",
            "BUSHING": "bushing",
            "NIPLE": "nipple fitting",
            "COPLE": "coupling",
            "TAPON": "pipe cap",
            "YEE": "wye fitting",
            "TEE": "tee fitting",
            "BRIDA": "flange",
            "ABRAZADERA": "pipe clamp",
            "ASPERSOR": "sprinkler",
            
            # Fijación y sujeción
            "TORNILLO": "screw",
            "CLAVO": "nail",
            "PERNO": "bolt",
            "TUERCA": "nut",
            "ARANDELA": "washer",
            "TAQUETE": "anchor",
            "ANCLA": "anchor",
            "RONDANA": "washer",
            "REMACHE": "rivet",
            "GRAPA": "staple",
            "GANCHO": "hook",
            "ALCAYATA": "screw hook",
            
            # Cerrajería
            "BISAGRA": "hinge",
            "CERRADURA": "lock",
            "CANDADO": "padlock",
            "CHAPA": "door lock",
            "ALDABA": "latch",
            "MANIJA": "handle",
            "PERILLA": "knob",
            "PICAPORTE": "latch",
            "CILINDRO": "lock cylinder",
            "PASADOR": "bolt latch",
            
            # Pintura y acabados
            "PINTURA": "paint",
            "BARNIZ": "varnish",
            "SELLADOR": "sealant",
            "SILICÓN": "silicone",
            "SILICON": "silicone",
            "CERA": "wax",
            "THINNER": "paint thinner",
            "SOLVENTE": "solvent",
            "REMOVEDOR": "paint remover",
            "MASILLA": "putty",
            "RESANADOR": "spackle",
            "ESTUCO": "stucco",
            "PASTA": "filler paste",
            "LACA": "lacquer",
            "ESMALTE": "enamel paint",
            
            # Adhesivos
            "PEGAMENTO": "glue",
            "ADHESIVO": "adhesive",
            "RESISTOL": "glue",
            "KOLA LOKA": "super glue",
            "CEMENTO": "cement",
            "SOLDADURA": "welding",
            
            # Materiales de construcción
            "ARENA": "sand",
            "GRAVA": "gravel",
            "CEMENTO": "cement",
            "CAL": "lime",
            "YESO": "plaster",
            "TABIQUE": "brick",
            "BLOCK": "concrete block",
            "LADRILLO": "brick",
            "VARILLA": "rebar",
            "ALAMBRE": "wire",
            "MALLA": "mesh",
            
            # Seguridad y protección
            "GUANTE": "glove",
            "CASCO": "helmet",
            "LENTE": "safety glasses",
            "TAPABOCA": "face mask",
            "CUBREBOCA": "face mask",
            "CHALECO": "safety vest",
            "ARNES": "safety harness",
            "ZAPATO": "safety shoe",
            "BOTA": "boot",
            
            # Limpieza y mantenimiento
            "ESCOBA": "broom",
            "TRAPEADOR": "mop",
            "CUBETA": "bucket",
            "BOTE": "container",
            "CHAROLA": "tray",
            "JERGA": "cleaning cloth",
            "FIBRA": "scrubber",
            "ESPONJA": "sponge",
            "CEPILLO": "brush",
            "RECOGEDOR": "dustpan",
            "JALADOR": "squeegee",
            "DETERGENTE": "detergent",
            "CLORO": "bleach",
            "DESENGRASANTE": "degreaser",
            "ACEITERA": "oil can",
            
            # Jardinería
            "MANGUERA": "garden hose",
            "RASTRILLO": "rake",
            "PALA": "shovel",
            "TIJERAS": "pruning shears",
            "MACETA": "flower pot",
            "REGADERA": "watering can",
            "ASPERSOR": "sprinkler",
            "CARRETILLA": "wheelbarrow",
            
            # Medición
            "METRO": "tape measure",
            "NIVEL": "level",
            "ESCUADRA": "square",
            "REGLA": "ruler",
            "CALIBRADOR": "caliper",
            "PLOMADA": "plumb bob",
            
            # Otros productos comunes
            "CADENA": "chain",
            "SOGA": "rope",
            "CUERDA": "rope",
            "RESORTE": "spring",
            "BISAGRA": "hinge",
            "POLEA": "pulley",
            "RODAJA": "caster wheel",
            "RUEDA": "wheel",
            "LIJA": "sandpaper",
            "DISCO": "disc",
            "BROCA": "drill bit",
            "CINCEL": "chisel",
            "FORMÓN": "chisel",
            "LIMA": "file",
            "SEGUETA": "hacksaw",
            "ARCO": "hacksaw frame",
            "EXTENSIÓN": "extension cord",
            "MULTICONTACTO": "power strip",
            "REGULADOR": "voltage regulator",
            "TRANSFORMADOR": "transformer",
            "BATERÍA": "battery",
            "PILA": "battery",
            "LINTERNA": "flashlight",
            "FOCO LED": "led bulb",
            "REFLECTOR": "floodlight",
            "TIRA LED": "led strip"
        }
        
        # Buscar coincidencias en el diccionario (buscar la coincidencia más larga primero)
        coincidencias = []
        for palabra_esp, palabra_eng in traduccion.items():
            if palabra_esp in nombre:
                coincidencias.append((len(palabra_esp), palabra_eng))
        
        # Si encontramos coincidencias, usar la más larga (más específica)
        if coincidencias:
            coincidencias.sort(reverse=True)
            termino = coincidencias[0][1]
            logger.debug(f"   Término encontrado: '{termino}'")
            return termino
        
        # Si no se encuentra, intentar extraer palabras significativas
        # Eliminar caracteres especiales y números
        nombre_limpio = re.sub(r'[^A-Z\s]', ' ', nombre)
        palabras = [p for p in nombre_limpio.split() if len(p) >= 3]
        
        if palabras:
            # Tomar la primera palabra significativa
            termino = palabras[0].lower()
            logger.debug(f"   Término extraído: '{termino}'")
            return termino
        
        # Si todo falla, retornar None
        logger.debug(f"   No se pudo extraer término")
        return None

    # -------------------------------------------------------------------------
    # 🔍 BUSCAR EN PEXELS
    # -------------------------------------------------------------------------
    async def buscar_imagen_pexels(self, termino: str, session: aiohttp.ClientSession) -> str:
        """
        Busca imágenes en Pexels con timeout agresivo
        """
        if not termino:
            return None
            
        try:
            # Espera mínima para evitar rate limiting
            await asyncio.sleep(random.uniform(0.1, 0.3))
            
            headers = {
                "Authorization": self.pexels_key,
                "User-Agent": "Mozilla/5.0"
            }
            
            params = {
                "query": termino,
                "per_page": 1,  # Solo 1 para ser más rápido
                "orientation": "square"
            }
            
            logger.debug(f"   🔎 Buscando: '{termino}'")
            
            async with session.get(
                "https://api.pexels.com/v1/search",
                headers=headers,
                params=params,
                timeout=aiohttp.ClientTimeout(total=8, connect=3, sock_read=5)  # Timeout más agresivo
            ) as resp:
                
                if resp.status == 200:
                    data = await resp.json()
                    
                    if data.get("photos") and len(data["photos"]) > 0:
                        img = data["photos"][0]
                        url = img.get("src", {}).get("large")
                        
                        if url and url.startswith("http"):
                            logger.info(f"   ✅ Encontrada")
                            return url
                    
                    logger.debug(f"   ⚠️ Sin resultados")
                    return None
                
                elif resp.status == 429:
                    logger.warning("   ⚠️ Rate limit - pausando 3s")
                    await asyncio.sleep(3)
                    return None
                
                else:
                    logger.debug(f"   ⚠️ Status {resp.status}")
                    return None
                    
        except asyncio.TimeoutError:
            logger.warning(f"   ⏱️ Timeout (8s)")
            return None
        except Exception as e:
            logger.error(f"   ❌ Error: {str(e)[:60]}")
            return None

    # -------------------------------------------------------------------------
    # 🔍 PROCESAR PRODUCTO
    # -------------------------------------------------------------------------
    async def procesar_producto(self, codigo: str, nombre: str, session: aiohttp.ClientSession) -> dict:
        """
        Procesa un producto y obtiene su imagen CON TIMEOUT
        """
        # Validar que el nombre no esté vacío
        nombre_limpio = nombre.strip() if nombre else ""

        if not nombre_limpio or len(nombre_limpio) < 2:
            return {
                "Codigo": codigo,
                "imagen": {"existe": False, "url_github": None}
            }

        logger.info(f"🔍 {codigo}: '{nombre_limpio[:40]}'")

        # 1. Extraer término de búsqueda
        termino = self.extraer_termino_busqueda(nombre_limpio)
        
        if not termino:
            logger.info("   ❌ Sin término")
            return {
                "Codigo": codigo,
                "imagen": {"existe": False, "url_github": None}
            }

        # 2. Buscar imagen con timeout total de 10 segundos
        try:
            url_img = await asyncio.wait_for(
                self.buscar_imagen_pexels(termino, session),
                timeout=10.0
            )
            
            if url_img:
                return {
                    "Codigo": codigo,
                    "imagen": {
                        "existe": True, 
                        "url_github": url_img, 
                        "fuente": "pexels",
                        "termino_busqueda": termino
                    }
                }
        except asyncio.TimeoutError:
            logger.warning(f"   ⏱️ Timeout total (10s)")

        logger.info("   ❌ Sin imagen")
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
        max_concurrentes: int = 5,  # Aumentado
        productos_por_lote: int = 50,
        pausa_entre_lotes: int = 15  # Reducido
    ) -> list[dict]:
        
        total = len(productos)
        resultados = []
        
        logger.info(f"\n{'='*60}")
        logger.info(f"🚀 PROCESANDO {total} PRODUCTOS")
        logger.info(f"   ⚙️ Fuente: Pexels API")
        logger.info(f"   ⚙️ Concurrentes: {max_concurrentes}")
        logger.info(f"   ⚙️ Lote: {productos_por_lote}")
        logger.info(f"{'='*60}")

        timeout = aiohttp.ClientTimeout(total=15, connect=5, sock_read=8)
        connector = aiohttp.TCPConnector(
            limit=20, 
            limit_per_host=5, 
            ttl_dns_cache=300,
            ssl=False
        )
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            for i in range(0, total, productos_por_lote):
                lote = productos[i:i + productos_por_lote]
                lote_num = (i // productos_por_lote) + 1
                lotes_totales = (total + productos_por_lote - 1) // productos_por_lote

                logger.info(f"\n📦 LOTE {lote_num}/{lotes_totales} ({len(lote)} productos)")

                semaforo = asyncio.Semaphore(max_concurrentes)

                async def procesar_con_limite(prod):
                    async with semaforo:
                        try:
                            # Timeout por producto: 15 segundos máximo
                            return await asyncio.wait_for(
                                self.procesar_producto(
                                    prod.get("Codigo", ""),
                                    prod.get("Nombre", ""),
                                    session
                                ),
                                timeout=15.0
                            )
                        except asyncio.TimeoutError:
                            codigo = prod.get('Codigo', 'UNKNOWN')
                            logger.error(f"⏱️ {codigo}: Timeout (15s)")
                            return {
                                "Codigo": codigo,
                                "imagen": {"existe": False, "url_github": None}
                            }
                        except Exception as e:
                            codigo = prod.get('Codigo', 'UNKNOWN')
                            logger.error(f"❌ {codigo}: {str(e)[:40]}")
                            return {
                                "Codigo": codigo,
                                "imagen": {"existe": False, "url_github": None}
                            }

                tareas = [procesar_con_limite(p) for p in lote]
                lote_result = await asyncio.gather(*tareas, return_exceptions=True)
                lote_result = [r for r in lote_result if isinstance(r, dict)]
                resultados.extend(lote_result)

                encontradas = sum(1 for r in lote_result if r.get('imagen', {}).get('existe'))

                logger.info(f"✅ Completado: {len(lote_result)}/{len(lote)} | Encontradas: {encontradas} ({(encontradas/len(lote_result)*100):.1f}%)" if lote_result else "⚠️ Sin resultados")

                # Pausa entre lotes
                if (i + productos_por_lote) < total:
                    logger.info(f"⏸️ Pausa {pausa_entre_lotes}s...\n")
                    await asyncio.sleep(pausa_entre_lotes)

        logger.info(f"\n{'='*60}")
        logger.info("🎉 COMPLETADO")
        total_encontradas = sum(1 for r in resultados if r.get('imagen', {}).get('existe'))
        tasa = (total_encontradas/len(resultados)*100) if resultados else 0
        logger.info(f"   Procesados: {len(resultados)}")
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