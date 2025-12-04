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
        Busca imágenes en Pexels
        """
        if not termino:
            return None
            
        try:
            # Espera aleatoria para evitar rate limiting
            await asyncio.sleep(random.uniform(0.3, 0.6))
            
            headers = {
                "Authorization": self.pexels_key,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            params = {
                "query": termino,
                "per_page": 5,  # Obtener varias opciones
                "orientation": "square",  # Mejor para productos
                "size": "medium"
            }
            
            logger.debug(f"   Buscando en Pexels: '{termino}'")
            
            async with session.get(
                "https://api.pexels.com/v1/search",
                headers=headers,
                params=params,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                
                if resp.status == 200:
                    data = await resp.json()
                    
                    if data.get("photos") and len(data["photos"]) > 0:
                        # Tomar la primera imagen
                        img = data["photos"][0]
                        url = img.get("src", {}).get("large")
                        
                        if url and url.startswith("http"):
                            logger.info(f"   ✅ Imagen encontrada: {termino}")
                            return url
                    else:
                        logger.debug(f"   ⚠️ Sin resultados para: {termino}")
                        return None
                
                elif resp.status == 429:
                    logger.warning("   ⚠️ Rate limit alcanzado, esperando...")
                    await asyncio.sleep(2)
                    return None
                
                else:
                    logger.debug(f"   ⚠️ Status {resp.status} para: {termino}")
                    return None
                    
        except asyncio.TimeoutError:
            logger.debug(f"   ⏱️ Timeout para: {termino}")
            return None
        except Exception as e:
            logger.debug(f"   ❌ Error: {str(e)[:80]}")
            return None

    # -------------------------------------------------------------------------
    # 🔍 PROCESAR PRODUCTO
    # -------------------------------------------------------------------------
    async def procesar_producto(self, codigo: str, nombre: str, session: aiohttp.ClientSession) -> dict:
        """
        Procesa un producto y obtiene su imagen
        """
        # Validar que el nombre no esté vacío
        nombre_limpio = nombre.strip() if nombre else ""

        if not nombre_limpio or len(nombre_limpio) < 2:
            logger.debug(f"⏭️ {codigo}: Sin nombre válido, omitiendo...")
            return {
                "Codigo": codigo,
                "imagen": {"existe": False, "url_github": None}
            }

        logger.info(f"🔍 {codigo}: '{nombre_limpio[:60]}'")

        # 1. Extraer término de búsqueda
        termino = self.extraer_termino_busqueda(nombre_limpio)
        
        if not termino:
            logger.info("   ❌ No se pudo extraer término de búsqueda")
            return {
                "Codigo": codigo,
                "imagen": {"existe": False, "url_github": None}
            }

        # 2. Buscar imagen con el término principal
        url_img = await self.buscar_imagen_pexels(termino, session)
        
        if url_img:
            logger.info(f"   ✅ Imagen encontrada")
            return {
                "Codigo": codigo,
                "imagen": {
                    "existe": True, 
                    "url_github": url_img, 
                    "fuente": "pexels",
                    "termino_busqueda": termino
                }
            }

        # 3. Intentar con término alternativo (primera palabra significativa)
        palabras = [p for p in nombre_limpio.split() if len(p) >= 3]
        if len(palabras) > 1:
            termino_alt = palabras[0].lower()
            if termino_alt != termino:  # Evitar buscar lo mismo dos veces
                logger.debug(f"   🔄 Intentando término alternativo: '{termino_alt}'")
                url_img = await self.buscar_imagen_pexels(termino_alt, session)
                
                if url_img:
                    logger.info(f"   ✅ Imagen encontrada (alternativo)")
                    return {
                        "Codigo": codigo,
                        "imagen": {
                            "existe": True, 
                            "url_github": url_img, 
                            "fuente": "pexels",
                            "termino_busqueda": termino_alt
                        }
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
        productos_por_lote: int = 50,
        pausa_entre_lotes: int = 30
    ) -> list[dict]:
        
        total = len(productos)
        resultados = []
        
        logger.info(f"\n🚀 INICIANDO PROCESAMIENTO DE {total} PRODUCTOS")
        logger.info(f"   ⚙️ Fuente: Pexels API")
        logger.info(f"   ⚙️ Concurrentes: {max_concurrentes}")
        logger.info(f"   ⚙️ Productos por lote: {productos_por_lote}")

        timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=15)
        connector = aiohttp.TCPConnector(limit_per_host=3, ssl=False)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            for i in range(0, total, productos_por_lote):
                lote = productos[i:i + productos_por_lote]
                lote_num = (i // productos_por_lote) + 1
                lotes_totales = (total + productos_por_lote - 1) // productos_por_lote

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

                # Pausa entre lotes (excepto el último)
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