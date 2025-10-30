
# app/engine.py
# Lightweight CLIPS engine wrapper using clipspy
# pip install clipspy
from clips import Environment, Symbol

class ClipsRecommender:
    def __init__(self, clp_path: str):
        self.clp_path = clp_path
        self.env = Environment()
        # Cargar el archivo CLIPS una sola vez al inicializar
        self.env.load(self.clp_path)
        self.env.reset()

    def reset_env(self):
        self.env.reset()
        print("DEBUG: Hechos en el entorno CLIPS después de reset:")
        for f in self.env.facts():
            print(f"  {f}")
        
        # Los deffacts demo ya se cargan con el load inicial, pero si existen
        # y se quieren asertar explícitamente en cada reset:
        # self.env.run() # Disparar deffacts demo si no se asertan hechos dinámicamente

    def assert_fact(self, template: str, slots: dict):
        # Build a fact string like: (usuario (id u1) (presupuesto 18) ...)
        parts = [template]
        for k, v in slots.items():
            # Filtrar campos None (opcionales)
            if v is None:
                continue
            
            # Filtrar strings vacíos si el campo tiene default vacío en CLIPS
            if isinstance(v, str) and v == "":
                continue
            
            if isinstance(v, (int, float)):
                parts.append(f'({k} {v})')
            elif isinstance(v, (list, tuple)):
                atoms = " ".join(map(str, v))
                parts.append(f'({k} {atoms})')
            else:
                # quote strings with spaces, leave symbols without quotes
                s = str(v)
                if any(ch.isspace() for ch in s) or s.startswith('"'):
                    parts.append(f'({k} "{s}")')
                else:
                    parts.append(f'({k} {s})')
        fact_str = "(" + " ".join(parts) + ")"
        fact = self.env.assert_string(fact_str)
        print(f"DEBUG: Asertado: {fact_str}") # Añadir este print
        return fact

    def run(self, max_steps: int = 0):
        # 0 means no limit
        return self.env.run(max_steps)

    def get_recommendations(self):
        # Read acum + restaurante to return id, nombre, U, justifs
        recs = []
        for f in self.env.facts():
            if f.template.name == "acum":
                rest_id = str(f["rest"])
                U = float(f["U"])
                justifs = list(f["justifs"])
                # find restaurant name
                nombre = rest_id
                for g in self.env.facts():
                    if g.template.name == "restaurante" and str(g["id"]) == rest_id:
                        nombre = str(g["nombre"])
                        break
                recs.append({"id": rest_id, "nombre": nombre, "U": U, "justifs": justifs})
        # sort by U desc
        recs.sort(key=lambda x: x["U"], reverse=True)
        return recs

    def recommend(self, usuario: dict, contexto: dict, restaurantes: list = None):
        self.reset_env()
        print(f"DEBUG: Usuario recibido: {usuario}")
        print(f"DEBUG: Contexto recibido: {contexto}")
        print(f"DEBUG: Restaurantes recibidos: {restaurantes}")

        self.assert_fact("usuario", usuario)
        self.assert_fact("contexto", contexto)
        if restaurantes:
            for r in restaurantes:
                self.assert_fact("restaurante", r)
        # NOTA: Ya no hay deffacts demo en el .clp, por lo que siempre
        # debes enviar restaurantes desde el frontend.

        print("DEBUG: Hechos asertados antes de run:")
        for f in self.env.facts():
            print(f"  {f}")

        self.run(max_steps=10000) # Aumentar el límite de disparos de reglas

        print("DEBUG: Hechos en el entorno CLIPS después de run:")
        for f in self.env.facts():
            print(f"  {f}")

        recs = self.get_recommendations()
        print(f"DEBUG: Recomendaciones generadas: {recs}")
        return recs
