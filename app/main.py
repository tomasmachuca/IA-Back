
# app/main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from copy import deepcopy
import math
import os

from .engine import ClipsRecommender
from fastapi.middleware.cors import CORSMiddleware

CLP_PATH = os.environ.get("CLP_PATH", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tpo_gastronomico_v3_2.clp")))

app = FastAPI(title="CLIPS Recommender API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8080",
        "http://localhost:8080",
    ], # Permitir front en 127.0.0.1:8080/localhost:8080
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = ClipsRecommender(CLP_PATH)

# Dataset base de restaurantes (se usa si el front no envía lista)
BASE_RESTAURANTS: List[Dict[str, Any]] = [
    {
        "id": "r1", "nombre": "Obelisco Pizza", "cocinas": ["pizza", "italiana"],
        "precio_pp": 15000, "rating": 4.5, "n_resenas": 200,
        "atributos": ["accesible", "rampa"], "reserva": "si", "tiempo_min": 10, "abierto": "si",
        "lat": -34.6037, "lon": -58.3816,
    },
    {
        "id": "r2", "nombre": "Palermo Sushi", "cocinas": ["japonesa", "sushi"],
        "precio_pp": 22000, "rating": 4.6, "n_resenas": 180,
        "atributos": ["accesible"], "reserva": "si", "tiempo_min": 12, "abierto": "si",
        "lat": -34.5880, "lon": -58.4300,
    },
    {
        "id": "r3", "nombre": "Recoleta Bistró", "cocinas": ["francesa", "moderna"],
        "precio_pp": 28000, "rating": 4.7, "n_resenas": 250,
        "atributos": ["menu_braille"], "reserva": "si", "tiempo_min": 14, "abierto": "si",
        "lat": -34.5886, "lon": -58.3974,
    },
    {
        "id": "r4", "nombre": "San Telmo Parrilla", "cocinas": ["parrilla", "argentina"],
        "precio_pp": 20000, "rating": 4.3, "n_resenas": 320,
        "atributos": ["accesible", "lengua_de_senas"], "reserva": "no", "tiempo_min": 16, "abierto": "si",
        "lat": -34.6229, "lon": -58.3730,
    },
    {
        "id": "r5", "nombre": "Belgrano Trattoria", "cocinas": ["italiana", "pasta"],
        "precio_pp": 18000, "rating": 4.4, "n_resenas": 150,
        "atributos": ["rampa", "bano_accesible"], "reserva": "si", "tiempo_min": 18, "abierto": "si",
        "lat": -34.5622, "lon": -58.4563,
    },
    {
        "id": "r6", "nombre": "Puerto Madero Mar", "cocinas": ["pescados", "mariscos"],
        "precio_pp": 30000, "rating": 4.6, "n_resenas": 210,
        "atributos": ["accesible"], "reserva": "si", "tiempo_min": 15, "abierto": "si",
        "lat": -34.6079, "lon": -58.3625,
    },
    {
        "id": "r7", "nombre": "Caballito Casa de Comida", "cocinas": ["casera", "empanadas"],
        "precio_pp": 12000, "rating": 4.1, "n_resenas": 95,
        "atributos": [], "reserva": "no", "tiempo_min": 20, "abierto": "si",
        "lat": -34.6180, "lon": -58.4420,
    },
    {
        "id": "r8", "nombre": "Solano Grill", "cocinas": ["parrilla", "argentina"],
        "precio_pp": 14000, "rating": 4.0, "n_resenas": 80,
        "atributos": ["accesible"], "reserva": "no", "tiempo_min": 35, "abierto": "si",
        "lat": -34.7830, "lon": -58.3110,
    },
]

class Usuario(BaseModel):
    id: str = "u1"
    cocinas_favoritas: List[str] = ["italiana", "pizza"]
    picante: str = "bajo"
    presupuesto: float = 18
    tiempo_max: float = 15
    movilidad: str = "a_pie"
    restricciones: List[str] = []
    diversidad: str = "media"
    lat: Optional[float] = None
    lon: Optional[float] = None
    discapacidad: List[str] = []
    wg: float = 0.35
    wp: float = 0.20
    wd: float = 0.25
    wq: float = 0.15
    wa: float = 0.05

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
    tiempo_min: float = 10
    abierto: str = "si"
    lat: Optional[float] = None
    lon: Optional[float] = None

class RequestBody(BaseModel):
    usuario: Usuario
    contexto: Optional[Contexto] = None
    restaurantes: Optional[List[Restaurante]] = None

@app.post("/api/recommend")
async def api_recommend(request: Request):
    payload = await request.json()

    # Extraer secciones tolerando formatos flexibles
    raw_usuario = payload.get("usuario", {})
    raw_contexto = payload.get("contexto", {})
    raw_restaurantes = payload.get("restaurantes", []) or []

    # Normalizaciones de usuario
    def _as_list(x):
        if x is None:
            return []
        if isinstance(x, list):
            return x
        if isinstance(x, str):
            # separar por coma si parece lista
            parts = [p.strip() for p in x.split(",")]
            return [p for p in parts if p]
        return [x]

    def _as_list_empty_if_no(x):
        if x is None:
            return []
        if isinstance(x, bool):
            return [] if x is False else []
        if isinstance(x, (int, float)):
            return []
        s = str(x).strip().lower()
        if s in ("", "no", "ninguna", "ninguno", "none", "null", "false", "0"):
            return []
        return _as_list(x)

    def _as_float(x, default=None):
        if x is None:
            return default
        if isinstance(x, (int, float)):
            return float(x)
        try:
            return float(str(x).replace(",", "."))
        except Exception:
            return default

    def _as_symbol_yes_no(x, default="si"):
        if isinstance(x, bool):
            return "si" if x else "no"
        s = str(x).strip().lower()
        if s in ("si", "sí", "yes", "y", "true", "1"):
            return "si"
        if s in ("no", "false", "0"):
            return "no"
        return default

    u = {
        "id": raw_usuario.get("id", "u1"),
        "cocinas_favoritas": _as_list(raw_usuario.get("cocinas_favoritas")),
        "picante": raw_usuario.get("picante", "bajo"),
        "presupuesto": _as_float(raw_usuario.get("presupuesto"), 18.0),
        "tiempo_max": _as_float(raw_usuario.get("tiempo_max"), 15.0),
        "movilidad": raw_usuario.get("movilidad", "a_pie"),
        "restricciones": _as_list_empty_if_no(raw_usuario.get("restricciones")),
        "diversidad": raw_usuario.get("diversidad", "media"),
        "wg": _as_float(raw_usuario.get("wg"), 0.35),
        "wp": _as_float(raw_usuario.get("wp"), 0.20),
        "wd": _as_float(raw_usuario.get("wd"), 0.25),
        "wq": _as_float(raw_usuario.get("wq"), 0.15),
        "wa": _as_float(raw_usuario.get("wa"), 0.05),
    }

    # Campos auxiliares no enviados a CLIPS
    u_lat = _as_float(raw_usuario.get("lat"))
    u_lon = _as_float(raw_usuario.get("lon"))
    discapacidad_val = raw_usuario.get("discapacidad")
    discapacidad_list = _as_list(discapacidad_val)

    # Contexto con defaults
    c_model = Contexto(**{
        "clima": str(raw_contexto.get("clima", "lluvia")),
        "dia": str(raw_contexto.get("dia", "viernes")),
        "franja": str(raw_contexto.get("franja", "cena")),
        "grupo": str(raw_contexto.get("grupo", "pareja")),
    })
    c = c_model.dict()

    # Restaurantes normalizados
    rs = []
    for rr in raw_restaurantes:
        r = {
            "id": rr.get("id"),
            "nombre": rr.get("nombre", rr.get("id", "")),
            "cocinas": _as_list(rr.get("cocinas")),
            "precio_pp": _as_float(rr.get("precio_pp"), 0.0),
            "rating": _as_float(rr.get("rating"), 0.0),
            "n_resenas": _as_float(rr.get("n_resenas"), 0.0),
            "atributos": [str(a) for a in _as_list(rr.get("atributos"))],
            "reserva": _as_symbol_yes_no(rr.get("reserva", "si")),
            "tiempo_min": _as_float(rr.get("tiempo_min"), 10.0),
            "abierto": _as_symbol_yes_no(rr.get("abierto", "si")),
        }
        r_lat = _as_float(rr.get("lat"))
        r_lon = _as_float(rr.get("lon"))
        r["_lat"] = r_lat
        r["_lon"] = r_lon
        rs.append(r)

    # Si no hay restaurantes enviados por el front, usar el dataset base
    if not rs:
        for rr in deepcopy(BASE_RESTAURANTS):
            rr["_lat"] = rr.get("lat")
            rr["_lon"] = rr.get("lon")
            rs.append(rr)

    # Si no llegan restaurantes, devolver respuesta clara
    if not rs:
        print("WARN: No se recibieron restaurantes en el payload.")
        return JSONResponse([], status_code=200)

    # Pre-filtrar por accesibilidad si corresponde
    user_needs_access = bool(discapacidad_list)
    if user_needs_access:
        before = len(rs)
        rs_filtered = []

        def _norm_attr(a: str) -> str:
            return str(a).strip().lower().replace(" ", "_")

        ACCESS_MAP = {
            "motriz": {
                "accesible", "rampa", "silla_de_ruedas", "apto_silla_de_ruedas", "baño_accesible",
                "bano_accesible", "entrada_sin_escalones"
            },
            "visual": {
                "braille", "menu_braille", "senaletica_braille", "asistencia_visual"
            },
            "auditiva": {
                "lengua_de_senas", "lsa", "subtitulado", "bucle_magnetico"
            },
        }

        needs = {_norm_attr(n) for n in discapacidad_list}
        attrs_per_rest = [({_norm_attr(a) for a in r.get("atributos", [])}, r) for r in rs]

        def _matches(attrs: set, needs: set) -> bool:
            if "accesible" in attrs:
                return True
            for need in needs:
                tags = ACCESS_MAP.get(need, set())
                if attrs.intersection(tags):
                    return True
            return False

        for attrs, r in attrs_per_rest:
            if _matches(attrs, needs):
                rs_filtered.append(r)

        after = len(rs_filtered)
        if after == 0:
            print(f"WARN: {before} restaurantes fueron filtrados por accesibilidad y no quedó ninguno. Se omite filtro para no retornar vacío.")
        else:
            rs = rs_filtered

    if not rs:
        print("WARN: No hay restaurantes para procesar luego de filtros/calculos.")
        return JSONResponse([], status_code=200)

    # Calcular tiempo_min dinámico usando coordenadas si están disponibles
    user_lat = u_lat
    user_lon = u_lon
    movilidad = str(u.get("movilidad") or "a_pie")
    if user_lat is not None and user_lon is not None:
        for r in rs:
            r_lat = r.get("_lat")
            r_lon = r.get("_lon")
            if r_lat is not None and r_lon is not None:
                # Distancia en km y tiempo estimado en minutos
                distancia_km = _haversine_km(user_lat, user_lon, r_lat, r_lon)
                r["distancia_km"] = round(distancia_km, 3)
                r["tiempo_min"] = _compute_travel_minutes(user_lat, user_lon, r_lat, r_lon, movilidad)

    # Filtrar campos para CLIPS (los templates no incluyen lat/lon/discapacidad)
    allowed_usuario = {
        "id", "cocinas_favoritas", "picante", "presupuesto", "tiempo_max",
        "movilidad", "restricciones", "diversidad", "wg", "wp", "wd", "wq", "wa"
    }
    allowed_restaurante = {
        "id", "nombre", "cocinas", "precio_pp", "rating", "n_resenas",
        "atributos", "reserva", "tiempo_min", "abierto", "lat", "lon"
    }
    u_clips = {k: v for k, v in u.items() if k in allowed_usuario}
    rs_clips = [{k: v for k, v in r.items() if k in allowed_restaurante} for r in rs]
    recs = engine.recommend(usuario=u_clips, contexto=c, restaurantes=rs_clips if rs_clips else None)
    
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
        
        # Incluir distancia si fue calculada
        dist_raw = original_rest.get('distancia_km')
        if dist_raw is not None:
            rec['distancia_km'] = dist_raw

        # Incluir coordenadas del restaurante si existen
        rest_lat = original_rest.get('_lat')
        rest_lon = original_rest.get('_lon')
        if rest_lat is not None and rest_lon is not None:
            rec['lat'] = rest_lat
            rec['lon'] = rest_lon
            
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

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def _compute_travel_minutes(lat1: float, lon1: float, lat2: float, lon2: float, movilidad: str) -> float:
    distance_km = _haversine_km(lat1, lon1, lat2, lon2)
    movilidad_l = (movilidad or "a_pie").lower()
    if movilidad_l in ("a_pie", "pie", "walk", "walking"):
        speed_kmh = 5.0
    elif movilidad_l in ("bici", "bicicleta", "bike", "cycling"):
        speed_kmh = 15.0
    elif movilidad_l in ("auto", "car", "vehiculo"):
        speed_kmh = 30.0
    else:
        speed_kmh = 5.0
    minutes = (distance_km / max(speed_kmh, 0.1)) * 60.0
    return round(minutes, 1)
