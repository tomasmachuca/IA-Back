
README — Front-end + CLIPS (CLIPSpy)

1) Instalar dependencias (recomendado: entorno virtual)
   py -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt

2) Ubicar tu archivo .clp (por defecto usa tpo_gastronomico_v3_2.clp en el mismo directorio padre).
   Si lo tenés en otra carpeta, exportá CLP_PATH:
   set CLP_PATH=C:\Users\tomas\...\tpo_gastronomico_v3_2.clp

3) Levantar el server
   uvicorn app.main:app --reload

4) Abrir el front-end
   http://127.0.0.1:8000/

Notas:
- El motor carga el .clp y hace (reset) en cada request.
- Podés enviar restaurantes desde el front (JSON) o dejar que el .clp tenga deffacts.
- Si CLIPSpy no instala, alternativa: crear un wrapper que invoque clips.exe por subprocess (te puedo dejar un ejemplo).

