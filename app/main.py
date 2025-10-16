
# app/main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
from typing import List, Dict, Any
import os

from .engine import ClipsRecommender
from fastapi.middleware.cors import CORSMiddleware

CLP_PATH = os.environ.get("CLP_PATH", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tpo_gastronomico_v3_2.clp")))

app = FastAPI(title="CLIPS Recommender API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://localhost:3000", "http://localhost:8000"], # Ajustado para permitir tu frontend
    allow_credentials=True,
    allow_methods=["*"],
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

class RequestBody(BaseModel):
    usuario: Usuario
    contexto: Contexto
    restaurantes: List[Restaurante] = []

@app.post("/api/recommend")
def api_recommend(body: RequestBody):
    u = body.usuario.dict()
    c = body.contexto.dict()
    rs = [r.dict() for r in body.restaurantes]
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
