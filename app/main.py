
# app/main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os
import json
import httpx
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno desde .env - buscar explícitamente en el directorio del proyecto
BASE_DIR = Path(__file__).parent.parent  # Directorio IA-Back
ENV_FILE = BASE_DIR / ".env"
load_dotenv(ENV_FILE)

from .engine import ClipsRecommender
from .neural_network import WeightOptimizerNN
from fastapi.middleware.cors import CORSMiddleware

CLP_PATH = os.environ.get("CLP_PATH", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tpo_gastronomico_v3_2.clp")))
RESTAURANTES_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "restaurantes.json"))
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")

# Debug: Verificar si la API key se cargó correctamente
print(f"DEBUG: Buscando .env en: {ENV_FILE}")
print(f"DEBUG: .env existe: {ENV_FILE.exists()}")
if GOOGLE_MAPS_API_KEY:
    print(f"DEBUG: Google Maps API Key cargada correctamente (longitud: {len(GOOGLE_MAPS_API_KEY)} caracteres)")
    print(f"DEBUG: API Key: {GOOGLE_MAPS_API_KEY[:20]}...{GOOGLE_MAPS_API_KEY[-10:]}")
else:
    print("WARNING: Google Maps API Key NO encontrada en variables de entorno")
    if ENV_FILE.exists():
        try:
            env_content = ENV_FILE.read_text(encoding='utf-8-sig')  # utf-8-sig maneja BOM
            print(f"DEBUG: Contenido del .env (primeros 100 chars): {env_content[:100]}")
        except Exception as e:
            print(f"DEBUG: Error leyendo .env: {e}")

app = FastAPI(title="CLIPS Recommender API")

# Almacenamiento simple de restaurantes en archivo JSON
async def load_restaurantes():
    """Carga restaurantes y geocodifica direcciones si no tienen coordenadas"""
    if Path(RESTAURANTES_FILE).exists():
        with open(RESTAURANTES_FILE, 'r', encoding='utf-8') as f:
            restaurantes = json.load(f)
    else:
        restaurantes = []
    
    # Geocodificar direcciones que no tengan coordenadas
    actualizado = False
    for r in restaurantes:
        if r.get("direccion") and (not r.get("latitud") or not r.get("longitud") or r.get("latitud") == 0.0 or r.get("longitud") == 0.0):
            coords = await geocodificar_direccion(r["direccion"])
            if coords:
                r["latitud"] = coords[0]
                r["longitud"] = coords[1]
                actualizado = True
                print(f"DEBUG: Coordenadas agregadas para {r.get('nombre')}: ({coords[0]}, {coords[1]})")
    
    # Guardar si se actualizó
    if actualizado:
        save_restaurantes(restaurantes)
    
    return restaurantes

def save_restaurantes(restaurantes):
    with open(RESTAURANTES_FILE, 'w', encoding='utf-8') as f:
        json.dump(restaurantes, f, ensure_ascii=False, indent=2)

async def geocodificar_direccion(direccion: str) -> Optional[tuple]:
    """Convierte una dirección a coordenadas (lat, lon) usando Google Maps Geocoding API"""
    if not GOOGLE_MAPS_API_KEY:
        print("WARNING: GOOGLE_MAPS_API_KEY no configurada")
        return None
    
    try:
        async with httpx.AsyncClient() as client:
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {
                "address": direccion,
                "key": GOOGLE_MAPS_API_KEY,
                "language": "es"
            }
            print(f"DEBUG: Geocodificando dirección: {direccion}")
            response = await client.get(url, params=params)
            data = response.json()
            
            if data.get("status") == "OK" and data.get("results"):
                location = data["results"][0]["geometry"]["location"]
                lat = location["lat"]
                lon = location["lng"]
                print(f"DEBUG: Coordenadas obtenidas - Lat: {lat}, Lon: {lon}")
                return (lat, lon)
            else:
                print(f"DEBUG: Error geocodificando - Status: {data.get('status')}, Error: {data.get('error_message', 'N/A')}")
    except Exception as e:
        print(f"Error geocodificando dirección: {e}")
        import traceback
        traceback.print_exc()
    return None

def verificar_horario_abierto(horario_apertura: Optional[str], horario_cierre: Optional[str]) -> str:
    """Verifica si el restaurante está abierto ahora basado en horarios HH:MM"""
    if not horario_apertura or not horario_cierre:
        return "si"  # Si no hay horarios, asumimos que está abierto
    
    from datetime import datetime
    ahora = datetime.now()
    hora_actual = ahora.hour * 60 + ahora.minute  # Minutos desde medianoche
    
    try:
        partes_apertura = horario_apertura.split(':')
        partes_cierre = horario_cierre.split(':')
        minutos_apertura = int(partes_apertura[0]) * 60 + int(partes_apertura[1])
        minutos_cierre = int(partes_cierre[0]) * 60 + int(partes_cierre[1])
        
        # Manejar horarios que cruzan medianoche (ej: 22:00 - 02:00)
        if minutos_cierre < minutos_apertura:
            # Cruza medianoche
            if hora_actual >= minutos_apertura or hora_actual < minutos_cierre:
                return "si"
        else:
            # Horario normal
            if minutos_apertura <= hora_actual < minutos_cierre:
                return "si"
        
        return "no"
    except Exception:
        # Si hay error parseando, asumimos que está abierto
        return "si"

async def calcular_tiempo_google_maps(origen_direccion: str, destino_direccion: str, modo: str = "walking") -> Optional[float]:
    """Calcula el tiempo de viaje usando Google Maps Distance Matrix API"""
    if not GOOGLE_MAPS_API_KEY:
        print("WARNING: GOOGLE_MAPS_API_KEY no configurada")
        return None
    
    try:
        async with httpx.AsyncClient() as client:
            url = "https://maps.googleapis.com/maps/api/distancematrix/json"
            params = {
                "origins": origen_direccion,
                "destinations": destino_direccion,
                "mode": modo,
                "key": GOOGLE_MAPS_API_KEY,
                "language": "es"
            }
            print(f"DEBUG: Llamando Google Maps API - Origen: {origen_direccion}, Destino: {destino_direccion}, Modo: {modo}")
            response = await client.get(url, params=params)
            data = response.json()
            
            print(f"DEBUG: Respuesta Google Maps - Status: {data.get('status')}")
            
            if data.get("status") == "OK" and data.get("rows"):
                elements = data["rows"][0].get("elements", [])
                if elements and elements[0].get("status") == "OK":
                    duration = elements[0].get("duration", {}).get("value", 0)  # en segundos
                    minutos = duration / 60  # convertir a minutos
                    print(f"DEBUG: Tiempo calculado: {minutos:.2f} minutos ({duration} segundos)")
                    return minutos
                else:
                    print(f"DEBUG: Error en elemento - Status: {elements[0].get('status') if elements else 'No elements'}")
            else:
                print(f"DEBUG: Error en respuesta - Status: {data.get('status')}, Error messages: {data.get('error_message', 'N/A')}")
    except Exception as e:
        print(f"Error calculando tiempo con Google Maps: {e}")
        import traceback
        traceback.print_exc()
    return None

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://192.168.0.24:3000",  # IP local para acceso desde otros dispositivos
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "PUT", "DELETE"],
    allow_headers=["*"],
)

engine = ClipsRecommender(CLP_PATH)

# Inicializar red neuronal para optimización de pesos
nn_optimizer = WeightOptimizerNN(learning_rate=0.01)

class Usuario(BaseModel):
    id: str = "u1"
    cocinas_favoritas: List[str] = ["italiana", "pizza"]
    picante: str = "bajo"
    presupuesto: float = 18
    tiempo_max: float = 15
    movilidad: str = "a_pie"  # a_pie, auto, moto, bicicleta, transporte_publico
    restricciones: List[str] = []  # vegano, vegetariano, celiaco, intolerancia_lactosa, kosher, fit
    diversidad: str = "media"
    wg: float = 0.35
    wp: float = 0.20
    wd: float = 0.25
    wq: float = 0.15
    wa: float = 0.05
    direccion: Optional[str] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    movilidad_reducida: Optional[str] = None  # si, no
    rating_minimo: Optional[float] = None  # mínimo de estrellas requerido (0-5)
    requiere_reserva: Optional[str] = None  # si, no
    solo_abiertos: Optional[str] = None  # si, no
    tiempo_espera_max: Optional[float] = None  # tiempo máximo de espera aceptable (min)
    tipo_comida_preferido: Optional[str] = None  # comida_rapida, gourmet, fine_dining, casual, bar, cafeteria
    estacionamiento_requerido: Optional[str] = None  # si, no

class Contexto(BaseModel):
    clima: str = "lluvia"
    dia: str = "viernes"
    franja: str = "cena"

class Restaurante(BaseModel):
    id: str
    nombre: str
    cocinas: List[str]
    precio_pp: float
    rating: float
    n_resenas: float
    atributos: List[str] = []  # vegano, vegetariano, celiaco, sin_tacc, intolerancia_lactosa, kosher, fit
    reserva: str = "si"  # si, no
    abierto: str = "si"  # si, no (actualizado dinámicamente según horarios)
    direccion: Optional[str] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    tiempo_min: Optional[float] = None  # Se calcula dinámicamente
    tiempo_espera: Optional[float] = None  # Tiempo promedio de espera en minutos
    pet_friendly: Optional[str] = None  # si, no
    estacionamiento_propio: Optional[str] = None  # si, no
    tipo_comida: Optional[str] = None  # comida_rapida, gourmet, casual, fine_dining
    horario_apertura: Optional[str] = None  # Formato HH:MM (ej: "09:00")
    horario_cierre: Optional[str] = None  # Formato HH:MM (ej: "23:00")

class RequestBody(BaseModel):
    usuario: Usuario
    contexto: Contexto
    restaurantes: List[Restaurante] = []
    usar_pesos_optimizados: bool = True  # Por defecto usar pesos optimizados por IA

@app.get("/api/restaurantes")
async def get_restaurantes():
    """Obtener todos los restaurantes"""
    restaurantes = await load_restaurantes()
    return JSONResponse(restaurantes)

@app.post("/api/restaurantes")
async def create_restaurantes(restaurantes: List[Restaurante]):
    """Guardar lista de restaurantes y geocodificar direcciones si no tienen coordenadas"""
    restaurantes_dict = [r.dict() for r in restaurantes]
    
    # Geocodificar direcciones que no tengan coordenadas
    for r in restaurantes_dict:
        if r.get("direccion") and (not r.get("latitud") or not r.get("longitud") or r.get("latitud") == 0.0 or r.get("longitud") == 0.0):
            coords = await geocodificar_direccion(r["direccion"])
            if coords:
                r["latitud"] = coords[0]
                r["longitud"] = coords[1]
                print(f"DEBUG: Coordenadas agregadas para {r.get('nombre')}: ({coords[0]}, {coords[1]})")
    
    save_restaurantes(restaurantes_dict)
    return JSONResponse({"message": "Restaurantes guardados", "count": len(restaurantes_dict)})

class CalcularTiemposRequest(BaseModel):
    usuario_direccion: str
    modo: str = "walking"

@app.post("/api/restaurantes/calcular-tiempos")
async def calcular_tiempos(request: CalcularTiemposRequest):
    """Calcular tiempos de viaje desde la dirección del usuario a todos los restaurantes"""
    restaurantes = await load_restaurantes()
    usuario_direccion = request.usuario_direccion
    modo = request.modo
    
    if not usuario_direccion:
        return JSONResponse({"error": "Dirección del usuario requerida"}, status_code=400)
    
    restaurantes_con_tiempos = []
    print(f"DEBUG: Calculando tiempos para {len(restaurantes)} restaurantes desde '{usuario_direccion}'")
    for r in restaurantes:
        if r.get("direccion"):
            tiempo = await calcular_tiempo_google_maps(usuario_direccion, r["direccion"], modo)
            r_con_tiempo = r.copy()
            r_con_tiempo["tiempo_min"] = tiempo if tiempo else 999
            print(f"DEBUG: Restaurante {r.get('nombre')} ({r.get('direccion')}) - tiempo: {r_con_tiempo['tiempo_min']} min")
            restaurantes_con_tiempos.append(r_con_tiempo)
        else:
            r_con_tiempo = r.copy()
            r_con_tiempo["tiempo_min"] = 999
            print(f"DEBUG: Restaurante {r.get('nombre')} - sin dirección, tiempo: 999 min")
            restaurantes_con_tiempos.append(r_con_tiempo)
    
    return JSONResponse(restaurantes_con_tiempos)

@app.post("/api/recommend")
async def api_recommend(body: RequestBody):
    print("=" * 80)
    print("DEBUG: /api/recommend llamado")
    print(f"DEBUG: Restaurantes recibidos en el request: {len(body.restaurantes)}")
    
    u = body.usuario.dict()
    c = body.contexto.dict()
    rs = [r.dict() for r in body.restaurantes]
    
    print(f"DEBUG: Usuario - presupuesto: {u.get('presupuesto')}, tiempo_max: {u.get('tiempo_max')}")
    print(f"DEBUG: Restaurantes iniciales: {len(rs)}")
    
    # Optimizar pesos usando red neuronal solo si el usuario lo permite
    usar_pesos_optimizados = body.usar_pesos_optimizados if hasattr(body, 'usar_pesos_optimizados') else True
    
    if usar_pesos_optimizados and rs and len(rs) > 0:
        try:
            # Usar el primer restaurante como ejemplo para extraer características
            restaurante_ejemplo = rs[0]
            pesos_optimizados = nn_optimizer.predict_weights(u, restaurante_ejemplo, c)
            
            # Usar pesos optimizados por la red neuronal
            # La NN aprende de los feedbacks pasados y ajusta los pesos para mejorar recomendaciones
            pesos_originales = {
                'wg': u.get('wg'),
                'wp': u.get('wp'),
                'wd': u.get('wd'),
                'wq': u.get('wq'),
                'wa': u.get('wa')
            }
            
            u['wg'] = pesos_optimizados['wg']
            u['wp'] = pesos_optimizados['wp']
            u['wd'] = pesos_optimizados['wd']
            u['wq'] = pesos_optimizados['wq']
            u['wa'] = pesos_optimizados['wa']
            
            print(f"DEBUG: Pesos originales del usuario - wg:{pesos_originales['wg']}, wp:{pesos_originales['wp']}, wd:{pesos_originales['wd']}, wq:{pesos_originales['wq']}, wa:{pesos_originales['wa']}")
            print(f"DEBUG: Pesos utilizados (optimizados por NN) - wg:{u['wg']:.3f}, wp:{u['wp']:.3f}, wd:{u['wd']:.3f}, wq:{u['wq']:.3f}, wa:{u['wa']:.3f}")
        except Exception as e:
            print(f"DEBUG: Error optimizando pesos con red neuronal: {e}")
            import traceback
            traceback.print_exc()
            # Continuar con pesos por defecto si hay error
            print(f"DEBUG: Usando pesos por defecto (error en NN) - wg:{u.get('wg', 0.35):.3f}, wp:{u.get('wp', 0.20):.3f}, wd:{u.get('wd', 0.25):.3f}, wq:{u.get('wq', 0.15):.3f}, wa:{u.get('wa', 0.05):.3f}")
    else:
        if not usar_pesos_optimizados:
            print(f"DEBUG: Usuario desactivó pesos optimizados - usando pesos por defecto del usuario")
        else:
            print(f"DEBUG: Sin restaurantes disponibles - usando pesos por defecto del usuario")
        print(f"DEBUG: Pesos utilizados (por defecto) - wg:{u.get('wg', 0.35):.3f}, wp:{u.get('wp', 0.20):.3f}, wd:{u.get('wd', 0.25):.3f}, wq:{u.get('wq', 0.15):.3f}, wa:{u.get('wa', 0.05):.3f}")
    
    # Cargar restaurantes desde archivo para tener las direcciones completas
    restaurantes_completos = await load_restaurantes()
    # Crear un mapa por ID para acceso rápido
    restaurantes_map = {r["id"]: r for r in restaurantes_completos}
    
    # Si se enviaron restaurantes, actualizar con los datos completos (direcciones y coordenadas)
    # Si no se enviaron restaurantes o el array está vacío, cargar todos del archivo
    actualizado_archivo = False
    if rs and len(rs) > 0:
        print(f"DEBUG: Actualizando {len(rs)} restaurantes con datos del archivo")
        for r in rs:
            if r["id"] in restaurantes_map:
                # Actualizar con datos del archivo (dirección y coordenadas)
                r_completo = restaurantes_map[r["id"]]
                r["direccion"] = r_completo.get("direccion")
                # Copiar coordenadas si existen en el archivo
                if r_completo.get("latitud") and r_completo.get("longitud"):
                    r["latitud"] = r_completo.get("latitud")
                    r["longitud"] = r_completo.get("longitud")
                elif r.get("direccion") and (not r.get("latitud") or not r.get("longitud") or r.get("latitud") == 0.0 or r.get("longitud") == 0.0):
                    # Si no tiene coordenadas, geocodificar ahora
                    coords = await geocodificar_direccion(r["direccion"])
                    if coords:
                        r["latitud"] = coords[0]
                        r["longitud"] = coords[1]
                        # Actualizar también en el archivo para futuras cargas
                        r_completo["latitud"] = coords[0]
                        r_completo["longitud"] = coords[1]
                        actualizado_archivo = True
                # Si ya tiene tiempo_min calculado y direccion, mantenerlo
                if not r.get("tiempo_min") and r.get("direccion"):
                    r["tiempo_min"] = None  # Se calculará abajo
        # Guardar coordenadas actualizadas si se geocodificaron
        if actualizado_archivo:
            save_restaurantes(restaurantes_completos)
    else:
        print(f"DEBUG: No se enviaron restaurantes o array vacío, cargando {len(restaurantes_completos)} del archivo")
        rs = restaurantes_completos.copy()
    
    # Mapear movilidad a modo de Google Maps API
    modo_map = {
        "a_pie": "walking",
        "auto": "driving",
        "moto": "driving",  # Google Maps no tiene modo específico para moto
        "bicicleta": "bicycling",
        "transporte_publico": "transit"
    }
    
    # Si hay dirección del usuario, calcular tiempos reales (siempre recalcular si hay dirección)
    if u.get('direccion') and GOOGLE_MAPS_API_KEY:
        modo = modo_map.get(u.get('movilidad', 'a_pie'), 'walking')
        print(f"DEBUG: Calculando tiempos para {len(rs)} restaurantes desde '{u['direccion']}' en modo {modo}")
        for r in rs:
            if r.get("direccion"):
                # Siempre recalcular si hay dirección del restaurante
                tiempo = await calcular_tiempo_google_maps(u['direccion'], r["direccion"], modo)
                r["tiempo_min"] = tiempo if tiempo else 999
                print(f"DEBUG: Restaurante {r.get('nombre')} ({r.get('direccion')}) - tiempo_min: {r['tiempo_min']}")
            elif not r.get("tiempo_min"):
                r["tiempo_min"] = 999
                print(f"DEBUG: Restaurante {r.get('nombre')} - sin dirección, tiempo_min: 999")
    else:
        # Si no hay dirección, establecer tiempos por defecto
        for r in rs:
            if not r.get("tiempo_min"):
                r["tiempo_min"] = 999
    
    # Verificar horarios y actualizar campo "abierto" dinámicamente
    for r in rs:
        if r.get("horario_apertura") and r.get("horario_cierre"):
            r["abierto"] = verificar_horario_abierto(r.get("horario_apertura"), r.get("horario_cierre"))
            print(f"DEBUG: Restaurante {r.get('nombre')} - horarios {r.get('horario_apertura')}-{r.get('horario_cierre')} -> abierto: {r['abierto']}")
    
    # Filtrar restaurantes por rating_minimo si está especificado
    if u.get('rating_minimo') is not None:
        rating_min = float(u.get('rating_minimo', 0))
        rs = [r for r in rs if r.get('rating', 0) >= rating_min]
        print(f"DEBUG: Filtrados restaurantes por rating_minimo >= {rating_min}, quedan {len(rs)} restaurantes")
    
    # Filtrar restaurantes por solo_abiertos si está especificado
    solo_abiertos_val = u.get('solo_abiertos')
    print(f"DEBUG: solo_abiertos recibido: '{solo_abiertos_val}' (tipo: {type(solo_abiertos_val)})")
    if solo_abiertos_val == 'si':
        cantidad_antes = len(rs)
        rs = [r for r in rs if r.get('abierto') == 'si']
        print(f"DEBUG: Filtrados restaurantes por solo_abiertos=si ({cantidad_antes} -> {len(rs)}), quedan {len(rs)} restaurantes")
    elif solo_abiertos_val == 'no':
        print(f"DEBUG: solo_abiertos=no, NO se filtrarán restaurantes por estado de apertura (mostrar todos)")
    else:
        print(f"DEBUG: solo_abiertos no especificado o vacío, NO se filtrarán restaurantes por estado de apertura")
    
    # Filtrar restaurantes por tiempo_espera_max si está especificado
    if u.get('tiempo_espera_max') is not None:
        tiempo_max = float(u.get('tiempo_espera_max', 999))
        rs = [r for r in rs if (r.get('tiempo_espera') is None or r.get('tiempo_espera', 0) <= tiempo_max)]
        print(f"DEBUG: Filtrados restaurantes por tiempo_espera <= {tiempo_max}, quedan {len(rs)} restaurantes")
    
    # Filtrar restaurantes por tipo_comida_preferido si está especificado
    if u.get('tipo_comida_preferido'):
        tipo_pref = u.get('tipo_comida_preferido')
        rs = [r for r in rs if r.get('tipo_comida') == tipo_pref]
        print(f"DEBUG: Filtrados restaurantes por tipo_comida={tipo_pref}, quedan {len(rs)} restaurantes")
    
    # Filtrar restaurantes por estacionamiento_requerido si está especificado
    if u.get('estacionamiento_requerido'):
        est_req = u.get('estacionamiento_requerido')
        if est_req == 'si':
            rs = [r for r in rs if r.get('estacionamiento_propio') == 'si']
        elif est_req == 'no':
            rs = [r for r in rs if r.get('estacionamiento_propio') != 'si']
        print(f"DEBUG: Filtrados restaurantes por estacionamiento_requerido={est_req}, quedan {len(rs)} restaurantes")
    
    # Log de dirección recibida para debug
    if u.get('direccion') or u.get('latitud') or u.get('longitud'):
        print(f"DEBUG: Dirección recibida - {u.get('direccion', 'N/A')}")
        if u.get('latitud') and u.get('longitud'):
            print(f"DEBUG: Coordenadas - Lat: {u.get('latitud')}, Lon: {u.get('longitud')}")
    
    print(f"DEBUG: Total restaurantes ANTES de llamar al motor CLIPS: {len(rs)}")
    if len(rs) == 0:
        print("ERROR: No hay restaurantes para procesar. Los filtros eliminaron todos los restaurantes.")
        return JSONResponse([], status_code=200)  # Devolver array vacío en lugar de error
    
    recs = engine.recommend(usuario=u, contexto=c, restaurantes=rs if rs else None)
    
    print(f"DEBUG: Recomendaciones generadas por CLIPS: {len(recs)}")
    if len(recs) == 0:
        print("WARNING: El motor CLIPS no generó ninguna recomendación.")
        print("DEBUG: Verificar que los restaurantes cumplan con las reglas del motor CLIPS.")
    
    # Crear un mapa de restaurantes para acceder fácilmente a sus datos originales
    restaurantes_map = {r["id"]: r for r in rs}

    formatted_recs = []
    for rec in recs:
        original_rest = restaurantes_map.get(rec['id'], {})
        
        # Incluir precio_pp original y formateado
        precio_pp_raw = original_rest.get('precio_pp')
        if precio_pp_raw is not None:
            rec['precio_pp'] = precio_pp_raw # Incluir el original
            rec['precio_pp_formato'] = _format_price_level(precio_pp_raw)
        
        # Incluir rating original y formateado a estrellas
        rating_raw = original_rest.get('rating')
        if rating_raw is not None:
            rec['rating'] = rating_raw # Incluir el original
            rec['rating_estrellas'] = _format_rating_stars(rating_raw)
        
        # Incluir tiempo_min calculado
        tiempo_min_raw = original_rest.get('tiempo_min')
        if tiempo_min_raw is not None:
            rec['tiempo_min'] = tiempo_min_raw
        
        # Incluir coordenadas
        if original_rest.get('latitud') and original_rest.get('longitud'):
            rec['latitud'] = original_rest.get('latitud')
            rec['longitud'] = original_rest.get('longitud')
        
        # Incluir TODOS los campos de restaurante (incluidos los opcionales)
        # Campos obligatorios
        if 'nombre' in original_rest:
            rec['nombre'] = original_rest['nombre']
        if 'cocinas' in original_rest:
            rec['cocinas'] = original_rest['cocinas']
        if 'atributos' in original_rest:
            rec['atributos'] = original_rest['atributos']
        if 'reserva' in original_rest:
            rec['reserva'] = original_rest['reserva']
        
        # Campos opcionales nuevos
        if original_rest.get('tiempo_espera') is not None:
            rec['tiempo_espera'] = original_rest.get('tiempo_espera')
        if original_rest.get('pet_friendly'):
            rec['pet_friendly'] = original_rest.get('pet_friendly')
        if original_rest.get('estacionamiento_propio'):
            rec['estacionamiento_propio'] = original_rest.get('estacionamiento_propio')
        if original_rest.get('tipo_comida'):
            rec['tipo_comida'] = original_rest.get('tipo_comida')
        if original_rest.get('horario_apertura'):
            rec['horario_apertura'] = original_rest.get('horario_apertura')
        if original_rest.get('horario_cierre'):
            rec['horario_cierre'] = original_rest.get('horario_cierre')
        # Incluir abierto (ya actualizado dinámicamente)
        if original_rest.get('abierto'):
            rec['abierto'] = original_rest.get('abierto')
        # Incluir dirección y coordenadas
        if original_rest.get('direccion'):
            rec['direccion'] = original_rest.get('direccion')
            
        formatted_recs.append(rec)

    return JSONResponse(formatted_recs)

def _format_price_level(price: float) -> str:
    if price <= 15000:
        return "$"
    elif price <= 25000:
        return "$$"
    else:
        return "$$$"

def _format_rating_stars(rating: float) -> str:
    num_stars = round(rating)
    return "⭐" * num_stars + "☆" * (5 - num_stars)

# Endpoint para recibir feedback del usuario y entrenar la red neuronal
class FeedbackRequest(BaseModel):
    usuario: Usuario
    contexto: Contexto
    restaurante_seleccionado: Restaurante
    restaurantes_rechazados: List[Restaurante] = []
    razones_preferencia: List[str] = []  # precio, distancia, calidad, gustos, abierto, reserva, caracteristicas, otro

@app.post("/api/feedback")
async def api_feedback(body: FeedbackRequest):
    """
    Endpoint para recibir feedback del usuario y entrenar la red neuronal.
    
    Se llama cuando el usuario selecciona un restaurante de las recomendaciones.
    La red neuronal aprende de estas interacciones para mejorar futuras recomendaciones.
    """
    try:
        u = body.usuario.dict()
        c = body.contexto.dict()
        restaurante_sel = body.restaurante_seleccionado.dict()
        restaurantes_rej = [r.dict() for r in body.restaurantes_rechazados]
        razones = body.razones_preferencia
        
        print(f"DEBUG: Feedback recibido - Razones: {razones}")
        
        # Entrenar la red neuronal con el feedback
        nn_optimizer.train_from_feedback(u, restaurante_sel, restaurantes_rej, c, razones)
        
        # Guardar modelo actualizado periódicamente (cada 5 feedbacks)
        history = nn_optimizer.load_history()
        feedback_count = len(history.get('feedbacks', []))
        if feedback_count % 5 == 0:
            try:
                nn_optimizer.save_model()
                print(f"DEBUG: Modelo guardado después de {feedback_count} feedbacks")
            except Exception as e:
                print(f"DEBUG: Error guardando modelo: {e}")
        
        return JSONResponse({
            "message": "Feedback recibido y procesado correctamente",
            "modelo_actualizado": True,
            "total_feedbacks": feedback_count
        })
    except Exception as e:
        print(f"DEBUG: Error procesando feedback: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "message": f"Error procesando feedback: {str(e)}",
            "modelo_actualizado": False
        }, status_code=500)
