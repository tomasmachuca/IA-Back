
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

class Usuario(BaseModel):
    id: str = "u1"
    cocinas_favoritas: List[str] = ["italiana", "pizza"]
    picante: str = "bajo"
    presupuesto: float = 18
    tiempo_max: float = 15
    movilidad: str = "a_pie"
    restricciones: List[str] = []
    diversidad: str = "media"
    wg: float = 0.35
    wp: float = 0.20
    wd: float = 0.25
    wq: float = 0.15
    wa: float = 0.05
    direccion: Optional[str] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None

class Contexto(BaseModel):
    clima: str = "lluvia"
    dia: str = "viernes"
    franja: str = "cena"
    grupo: str = "pareja"

class Restaurante(BaseModel):
    id: str
    nombre: str
    cocinas: List[str]
    precio_pp: float
    rating: float
    n_resenas: float
    atributos: List[str] = []
    reserva: str = "si"
    abierto: str = "si"
    direccion: Optional[str] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    tiempo_min: Optional[float] = None  # Se calcula dinámicamente

class RequestBody(BaseModel):
    usuario: Usuario
    contexto: Contexto
    restaurantes: List[Restaurante] = []

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
    u = body.usuario.dict()
    c = body.contexto.dict()
    rs = [r.dict() for r in body.restaurantes]
    
    # Cargar restaurantes desde archivo para tener las direcciones completas
    restaurantes_completos = await load_restaurantes()
    # Crear un mapa por ID para acceso rápido
    restaurantes_map = {r["id"]: r for r in restaurantes_completos}
    
    # Si se enviaron restaurantes, actualizar con los datos completos (direcciones y coordenadas)
    actualizado_archivo = False
    if rs:
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
        rs = restaurantes_completos.copy()
    
    # Si hay dirección del usuario, calcular tiempos reales (siempre recalcular si hay dirección)
    if u.get('direccion') and GOOGLE_MAPS_API_KEY:
        modo = "walking" if u.get('movilidad') == "a_pie" else "driving"
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
    
    # Log de dirección recibida para debug
    if u.get('direccion') or u.get('latitud') or u.get('longitud'):
        print(f"DEBUG: Dirección recibida - {u.get('direccion', 'N/A')}")
        if u.get('latitud') and u.get('longitud'):
            print(f"DEBUG: Coordenadas - Lat: {u.get('latitud')}, Lon: {u.get('longitud')}")
    
    recs = engine.recommend(usuario=u, contexto=c, restaurantes=rs if rs else None)
    
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
