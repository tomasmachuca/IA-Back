"""
Script para probar las APIs de Google Maps
Ejecutar: python test_google_api.py
"""
import os
import asyncio
import httpx
from pathlib import Path
from dotenv import load_dotenv

# Cargar .env desde el directorio del script
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")

async def test_geocoding():
    """Prueba la API de Geocoding"""
    if not API_KEY:
        print("[ERROR] GOOGLE_MAPS_API_KEY no configurada")
        return False
    
    print(f"\n[1] Probando Geocoding API...")
    print(f"   API Key: {API_KEY[:20]}...{API_KEY[-10:]}")
    
    direccion = "Av. Santa Fe 1234, Palermo, CABA"
    
    try:
        async with httpx.AsyncClient() as client:
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {
                "address": direccion,
                "key": API_KEY,
                "language": "es"
            }
            response = await client.get(url, params=params)
            data = response.json()
            
            status = data.get("status")
            print(f"   Status: {status}")
            
            if status == "OK":
                location = data["results"][0]["geometry"]["location"]
                print(f"   [OK] Exito! Coordenadas: ({location['lat']}, {location['lng']})")
                return True
            elif status == "REQUEST_DENIED":
                error_msg = data.get("error_message", "Sin mensaje de error")
                print(f"   [ERROR] {error_msg}")
                print(f"   [INFO] Posibles causas:")
                print(f"      - La API Key no es valida")
                print(f"      - La API 'Geocoding API' no esta habilitada")
                print(f"      - La API Key tiene restricciones que bloquean este uso")
            else:
                print(f"   [ERROR] {status}")
                if data.get("error_message"):
                    print(f"   Mensaje: {data.get('error_message')}")
            
    except Exception as e:
        print(f"   [EXCEPTION] {e}")
    
    return False

async def test_distance_matrix():
    """Prueba la API de Distance Matrix"""
    if not API_KEY:
        print("[ERROR] GOOGLE_MAPS_API_KEY no configurada")
        return False
    
    print(f"\n[2] Probando Distance Matrix API...")
    
    origen = "Dorrego, Quilmes"
    destino = "Av. Santa Fe 1234, Palermo, CABA"
    
    try:
        async with httpx.AsyncClient() as client:
            url = "https://maps.googleapis.com/maps/api/distancematrix/json"
            params = {
                "origins": origen,
                "destinations": destino,
                "mode": "walking",
                "key": API_KEY,
                "language": "es"
            }
            response = await client.get(url, params=params)
            data = response.json()
            
            status = data.get("status")
            print(f"   Status: {status}")
            
            if status == "OK" and data.get("rows"):
                elements = data["rows"][0].get("elements", [])
                if elements and elements[0].get("status") == "OK":
                    duration = elements[0].get("duration", {}).get("value", 0)
                    distance = elements[0].get("distance", {}).get("value", 0)
                    print(f"   [OK] Exito! Tiempo: {duration/60:.1f} min, Distancia: {distance/1000:.1f} km")
                    return True
                else:
                    print(f"   [ERROR] Error en elemento: {elements[0].get('status') if elements else 'No elements'}")
            elif status == "REQUEST_DENIED":
                error_msg = data.get("error_message", "Sin mensaje de error")
                print(f"   [ERROR] {error_msg}")
                print(f"   [INFO] Posibles causas:")
                print(f"      - La API Key no es valida")
                print(f"      - La API 'Distance Matrix API' no esta habilitada")
                print(f"      - La API Key tiene restricciones que bloquean este uso")
            else:
                print(f"   [ERROR] {status}")
                if data.get("error_message"):
                    print(f"   Mensaje: {data.get('error_message')}")
            
    except Exception as e:
        print(f"   [EXCEPTION]制作 {e}")
    
    return False

async def main():
    print("=" * 60)
    print("PRUEBA DE GOOGLE MAPS APIs")
    print("=" * 60)
    
    if not API_KEY:
        print("\n[ERROR] No se encontro GOOGLE_MAPS_API_KEY")
        print(f"   Buscando .env en: {env_path}")
        if env_path.exists():
            print(f"   [OK] Archivo .env existe")
            print(f"   Contenido: {env_path.read_text()[:50]}...")
        else:
            print(f"   [ERROR] Archivo .env NO existe en {env_path}")
        print("\n   Asegurate de que el archivo .env existe y contiene:")
        print("   GOOGLE_MAPS_API_KEY=tu_api_key_aqui")
        return
    
    print(f"\n[OK] API Key encontrada: {API_KEY[:20]}...{API_KEY[-10:]}")
    
    # Probar APIs
    geocoding_ok = await test_geocoding()
    distance_ok = await test_distance_matrix()
    
    print("\n" + "=" * 60)
    print("RESUMEN:")
    print(f"   Geocoding API: {'[OK]' if geocoding_ok else '[FALLA]'}")
    print(f"   Distance Matrix API: {'[OK]' if distance_ok else '[FALLA]'}")
    print("=" * 60)
    
    if not geocoding_ok or not distance_ok:
        print("\n[INFO] PARA HABILITAR LAS APIs EN GOOGLE CLOUD:")
        print("   1. Ve a https://console.cloud.google.com/")
        print("   2. Selecciona tu proyecto")
        print("   3. Ve a 'APIs & Services' > 'Library'")
        print("   4. Busca y habilita:")
        print("      - Geocoding API")
        print("      - Distance Matrix API")
        print("   5. Espera unos minutos para que se propague el cambio")
        print("\n   Tambien verifica en 'APIs & Services' > 'Credentials':")
        print("   - Que tu API Key no tenga restricciones muy estrictas")
        print("   - O si tiene restricciones, que permita estas APIs")

if __name__ == "__main__":
    asyncio.run(main())
