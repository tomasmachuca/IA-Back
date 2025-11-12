# Sistema de Recomendación de Restaurantes - Arquitectura Híbrida

## 📋 Índice

1. [Introducción](#introducción)
2. [Arquitectura del Sistema](#arquitectura-del-sistema)
3. [Cómo Funciona CLIPS](#cómo-funciona-clips)
4. [Conexión Backend-Frontend](#conexión-backend-frontend)
5. [Flujo de Datos](#flujo-de-datos)
6. [Sistema de Aprendizaje con Redes Neuronales](#sistema-de-aprendizaje-con-redes-neuronales)
7. [Instalación y Uso](#instalación-y-uso)

---

## Introducción

Este sistema es una **arquitectura híbrida** que combina:
- **Sistema Experto basado en reglas (CLIPS)**: Para lógica de recomendación basada en reglas explícitas
- **Red Neuronal (Machine Learning)**: Para optimizar los pesos del sistema experto aprendiendo de las preferencias del usuario

El objetivo es recomendar restaurantes personalizados considerando múltiples criterios: gustos, presupuesto, distancia, calidad, disponibilidad y restricciones alimentarias.

---

## Arquitectura del Sistema

```
┌─────────────────┐
│   Frontend      │  (IA-Front)
│   (HTML/JS)     │
└────────┬────────┘
         │ HTTP POST /api/recommend
         ▼
┌─────────────────────────────────────┐
│         Backend (FastAPI)           │
│  ┌───────────────────────────────┐  │
│  │  main.py                      │  │
│  │  - Recibe request             │  │
│  │  - Preprocesa datos           │  │
│  │  - Calcula tiempos (Google)   │  │
│  └───────────┬───────────────────┘  │
│              │                       │
│  ┌───────────▼───────────────────┐  │
│  │  WeightOptimizerNN            │  │
│  │  (Red Neuronal)               │  │
│  │  - Optimiza pesos wg,wp,wd... │  │
│  └───────────┬───────────────────┘  │
│              │                       │
│  ┌───────────▼───────────────────┐  │
│  │  ClipsRecommender             │  │
│  │  (engine.py)                  │  │
│  │  - Carga .clp                 │  │
│  │  - Ejecuta motor CLIPS        │  │
│  └───────────┬───────────────────┘  │
│              │                       │
│  ┌───────────▼───────────────────┐  │
│  │  tpo_gastronomico_v3_2.clp    │  │
│  │  (Sistema Experto)            │  │
│  │  - Reglas de filtrado         │  │
│  │  - Reglas de puntuación       │  │
│  │  - Reglas de penalización     │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
         │
         │ Feedback del usuario
         ▼
┌─────────────────────────────────────┐
│  /api/feedback                      │
│  - Guarda feedback                  │
│  - Entrena red neuronal             │
│  - Actualiza modelo                 │
└─────────────────────────────────────┘
```

---

## Cómo Funciona CLIPS

### ¿Qué es CLIPS?

CLIPS (C Language Integrated Production System) es un sistema experto basado en reglas. Funciona con un **motor de inferencia** que:

1. **Evalúa condiciones** (lado izquierdo de las reglas)
2. **Ejecuta acciones** (lado derecho de las reglas) cuando las condiciones se cumplen
3. **Repite** hasta que no hay más reglas activables

### Componentes del Sistema CLIPS

#### 1. Templates (Estructuras de Datos)

El sistema define 4 templates principales:

**`usuario`**: Representa las preferencias del usuario
- `cocinas_favoritas`: Lista de cocinas preferidas (ej: [italiana, mexicana])
- `presupuesto`: Presupuesto máximo en pesos
- `tiempo_max`: Tiempo máximo de viaje en minutos
- `restricciones`: Lista de restricciones (vegano, celiaco, etc.)
- `wg, wp, wd, wq, wa`: Pesos para cada criterio (deben sumar 1.0)
  - `wg`: Peso para gustos/afinidad
  - `wp`: Peso para precio
  - `wd`: Peso para distancia/cercanía
  - `wq`: Peso para calidad/rating
  - `wa`: Peso para disponibilidad

**`restaurante`**: Representa cada restaurante
- `id`, `nombre`, `cocinas`, `precio_pp`, `rating`, `n_resenas`
- `atributos`: Lista de características (vegano, sin_tacc, accesible, etc.)
- `tiempo_min`: Tiempo de viaje calculado desde la ubicación del usuario
- `abierto`: si/no (calculado dinámicamente según horarios)
- `reserva`, `pet_friendly`, `estacionamiento_propio`, etc.

**`contexto`**: Condiciones externas
- `clima`: templado, lluvia, calor, frio
- `dia`: lunes, martes, ..., domingo
- `franja`: desayuno, almuerzo, cena

**Templates de control**:
- `descartar`: Marca restaurantes que no cumplen requisitos obligatorios
- `puntaje`: Guarda el puntaje de cada criterio (evita recalcular)
- `acum`: Acumula el puntaje total `U` para cada restaurante
- `listo`: Marca restaurantes procesados completamente

#### 2. Reglas del Sistema (Orden de Ejecución)

Las reglas se ejecutan por **prioridad** (salience). Mayor número = mayor prioridad.

##### FASE 1: Inicialización (Salience 60)

```clips
(defrule inicializa-acum-por-restaurante
  (declare (salience 60))
  ?r <- (restaurante (id ?id))
  (not (acum (rest ?id)))
=>
  (assert (acum (rest ?id) (U 0.0) (justifs)))
)
```

**Qué hace**: Crea un acumulador con puntaje inicial `U = 0.0` para cada restaurante.

##### FASE 2: Filtros Obligatorios (Salience 50)

Estas reglas **descartan** restaurantes que no cumplen requisitos obligatorios:

- **`filtro-cerrado`**: Si usuario quiere solo abiertos y restaurante está cerrado → descarta
- **`filtro-dietas-sin-tacc`**: Si usuario requiere sin TACC y restaurante no lo tiene → descarta
- **`filtro-movilidad-reducida`**: Si usuario tiene movilidad reducida y restaurante no es accesible → descarta
- **`filtro-pet-friendly`**: Si usuario necesita pet friendly y restaurante no lo es → descarta
- **`filtro-restricciones-vegano/vegetariano/celiaco/lactosa`**: Filtran por restricciones alimentarias
- **`filtro-requiere-reserva-si/no`**: Filtran según preferencia de reserva

**Ejemplo**:
```clips
(defrule filtro-cerrado
  (declare (salience 50))
  (usuario (solo_abiertos si))
  (restaurante (id ?r) (abierto no))
=>
  (assert (descartar (rest ?r) (razon "cerrado en esta franja")))
)
```

##### FASE 3: Ajustes de Contexto (Salience 10)

```clips
(defrule contexto-lluvia-aumenta-cercania
  (declare (salience 10))
  (contexto (clima lluvia))
  ?u <- (usuario (wd ?wd))
=>
  (bind ?nuevo (+ ?wd 0.10))
  (modify ?u (wd (min 1.0 ?nuevo)))
)
```

**Qué hace**: Si está lloviendo, aumenta el peso de cercanía (`wd`) en 0.10, porque en lluvia la distancia es más importante.

##### FASE 4: Puntuación (Salience 0)

Estas reglas calculan el puntaje por cada criterio y lo suman al acumulador `U`:

**`puntuar-afinidad`**: Calcula coincidencia de cocinas usando coeficiente de Jaccard
- Si usuario tiene [italiana, mexicana] y restaurante tiene [italiana, japonesa]
- Coincidencias: 1 (italiana)
- Total único: 3 (italiana, mexicana, japonesa)
- Puntaje: 1/3 = 0.33
- Incremento: `U += wg * 0.33`

**`puntuar-precio`**: Normaliza precio inversamente (menor precio = mayor puntaje)
- Si presupuesto = 5000 y precio = 3000
- Puntaje = 1.0 - (3000/5000) = 0.4
- Incremento: `U += wp * 0.4`

**`puntuar-cercania`**: Similar a precio, normaliza tiempo inversamente
- Si tiempo_max = 30 y tiempo_min = 15
- Puntaje = 1.0 - (15/30) = 0.5
- Incremento: `U += wd * 0.5`

**`puntuar-calidad`**: Combina rating y cantidad de reseñas
- Solo puntúa si rating >= 3.5 y n_resenas >= 10
- Usa función `agregar-calidad` que combina rating normalizado con sqrt(reseñas normalizadas)
- Incremento: `U += wq * calidad`

**`puntuar-disponibilidad`**: Solo en franja "cena"
- Si acepta reserva: puntaje = 1.0
- Si no acepta reserva: puntaje = 0.3
- Incremento: `U += wa * disponibilidad`

##### FASE 5: Penalizaciones (Salience 0)

En lugar de descartar, estas reglas **restan puntos**:

**`penalizar-presupuesto-excedido`**: Si precio excede presupuesto
- Calcula exceso como fracción: `exceso = (precio - presupuesto) / presupuesto`
- Penalización = `min(0.3, exceso * 0.5)` (máximo 30% del peso wp)
- Resta: `U -= wp * penalizacion`

**`penalizar-sin-estacionamiento`**: Si usuario usa auto/moto y restaurante no tiene estacionamiento
- Penalización fija: -0.15
- Resta: `U -= 0.15`

##### FASE 6: Ranking (Salience 10 y 5)

**`marcar-listo`**: Marca restaurantes válidos como procesados

**`reporte-final`**: Imprime el ranking ordenado por `U` descendente

### Ejemplo Completo de Ejecución

**Datos de entrada**:
- Usuario: presupuesto=5000, tiempo_max=30, cocinas_favoritas=[italiana, mexicana], wg=0.3, wp=0.25, wd=0.2, wq=0.15, wa=0.1
- Restaurante: nombre="La Pizzería", precio_pp=3000, tiempo_min=15, rating=4.5, n_resenas=100, cocinas=[italiana], abierto=si, reserva=si
- Contexto: clima=templado, franja=cena

**Proceso**:
1. Inicializa: `acum(r1, U=0.0)`
2. Filtros: Pasa (está abierto)
3. Puntuación:
   - Afinidad: `U += 0.3 * 0.5 = 0.15` → `U = 0.15`
   - Precio: `U += 0.25 * 0.4 = 0.10` → `U = 0.25`
   - Cercanía: `U += 0.2 * 0.5 = 0.10` → `U = 0.35`
   - Calidad: `U += 0.15 * 0.636 ≈ 0.095` → `U = 0.445`
   - Disponibilidad: `U += 0.1 * 1.0 = 0.1` → `U = 0.545`
4. Penalizaciones: Ninguna
5. Resultado: `U = 0.545` (puntaje final)

---

## Conexión Backend-Frontend

### Endpoints de la API

#### 1. `POST /api/recommend` - Obtener Recomendaciones

**Request Body**:
```json
{
  "usuario": {
    "id": "u1",
    "cocinas_favoritas": ["italiana", "pizza"],
    "presupuesto": 5000,
    "tiempo_max": 30,
    "movilidad": "a_pie",
    "restricciones": ["vegano"],
    "wg": 0.35,
    "wp": 0.20,
    "wd": 0.25,
    "wq": 0.15,
    "wa": 0.05,
    "direccion": "Av. Corrientes 1234, Buenos Aires",
    "solo_abiertos": "si"
  },
  "contexto": {
    "clima": "lluvia",
    "dia": "viernes",
    "franja": "cena"
  },
  "restaurantes": [
    {
      "id": "r1",
      "nombre": "La Pizzería",
      "cocinas": ["italiana"],
      "precio_pp": 3000,
      "rating": 4.5,
      "n_resenas": 100,
      "atributos": ["vegano"],
      "reserva": "si",
      "abierto": "si",
      "direccion": "Av. Santa Fe 2000",
      "horario_apertura": "19:00",
      "horario_cierre": "00:00"
    }
  ],
  "usar_pesos_optimizados": true
}
```

**Response**:
```json
[
  {
    "id": "r1",
    "nombre": "La Pizzería",
    "U": 0.545,
    "justifs": ["afinidad=0.5", "precio=0.4", "cercania=0.5", "calidad=0.636", "disp=1.0"],
    "precio_pp": 3000,
    "rating": 4.5,
    "tiempo_min": 15,
    "direccion": "Av. Santa Fe 2000",
    "latitud": -34.6037,
    "longitud": -58.3816
  }
]
```

#### 2. `POST /api/feedback` - Enviar Feedback

**Request Body**:
```json
{
  "usuario": { ... },
  "contexto": { ... },
  "restaurante_seleccionado": { ... },
  "restaurantes_rechazados": [ ... ],
  "razones_preferencia": ["precio", "distancia", "abierto"]
}
```

**Response**:
```json
{
  "message": "Feedback recibido y procesado correctamente",
  "modelo_actualizado": true,
  "total_feedbacks": 7
}
```

#### 3. `GET /api/restaurantes` - Obtener Todos los Restaurantes

#### 4. `POST /api/restaurantes` - Guardar Restaurantes

#### 5. `POST /api/restaurantes/calcular-tiempos` - Calcular Tiempos de Viaje

---

## Flujo de Datos

### 1. Usuario Completa Formulario (Frontend)

El usuario ingresa:
- Presupuesto, tiempo máximo, cocinas favoritas
- Restricciones alimentarias
- Dirección (opcional)
- Preferencias de movilidad

### 2. Frontend Envía Request a Backend

```javascript
// recommender.js
const response = await fetch('http://localhost:8000/api/recommend', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    usuario: usuarioData,
    contexto: contextoData,
    restaurantes: restaurantesData,
    usar_pesos_optimizados: true
  })
})
```

### 3. Backend Preprocesa Datos (main.py)

**Paso 3.1: Optimización de Pesos con Red Neuronal**

Si `usar_pesos_optimizados = true`:
```python
# main.py línea 324
pesos_optimizados = nn_optimizer.predict_weights(u, restaurante_ejemplo, c)
u['wg'] = pesos_optimizados['wg']
u['wp'] = pesos_optimizados['wp']
# ... etc
```

La red neuronal predice los pesos óptimos basándose en:
- Características del usuario
- Características del restaurante de ejemplo
- Contexto
- Historial de feedbacks anteriores

**Paso 3.2: Carga y Enriquecimiento de Restaurantes**

```python
# Carga restaurantes desde restaurantes.json
restaurantes_completos = await load_restaurantes()

# Si no tienen coordenadas, geocodifica direcciones
if not r.get("latitud"):
    coords = await geocodificar_direccion(r["direccion"])
    r["latitud"] = coords[0]
    r["longitud"] = coords[1]
```

**Paso 3.3: Cálculo de Tiempos de Viaje (Google Maps API)**

Si el usuario tiene dirección:
```python
# main.py línea 412
tiempo = await calcular_tiempo_google_maps(
    usuario_direccion, 
    restaurante_direccion, 
    modo  # walking, driving, bicycling, transit
)
r["tiempo_min"] = tiempo
```

**Paso 3.4: Verificación de Horarios**

```python
# main.py línea 426
r["abierto"] = verificar_horario_abierto(
    r.get("horario_apertura"), 
    r.get("horario_cierre")
)
```

**Paso 3.5: Filtrado Pre-CLIPS**

Filtra restaurantes por:
- `rating_minimo`
- `solo_abiertos`
- `tiempo_espera_max`
- `tipo_comida_preferido`
- `estacionamiento_requerido`

### 4. Ejecución del Motor CLIPS (engine.py)

**Paso 4.1: Reset del Entorno**

```python
# engine.py línea 94
self.reset_env()  # Limpia hechos anteriores
```

**Paso 4.2: Aserción de Hechos**

```python
# engine.py línea 99-103
self.assert_fact("usuario", usuario)
self.assert_fact("contexto", contexto)
for r in restaurantes:
    self.assert_fact("restaurante", r)
```

**Paso 4.3: Ejecución del Motor**

```python
# engine.py línea 111
self.run(max_steps=10000)  # Ejecuta hasta 10000 reglas
```

El motor CLIPS:
1. Evalúa todas las reglas
2. Selecciona reglas activables (condiciones cumplidas)
3. Ejecuta reglas por prioridad (salience)
4. Repite hasta que no hay más reglas activables

**Paso 4.4: Extracción de Resultados**

```python
# engine.py línea 117
recs = self.get_recommendations()
```

Lee todos los hechos `acum` que no estén descartados, ordena por `U` descendente.

### 5. Formateo y Respuesta

```python
# main.py línea 490-547
formatted_recs = []
for rec in recs:
    # Agrega datos originales del restaurante
    # Formatea precio, rating, etc.
    formatted_recs.append(rec)

return JSONResponse(formatted_recs)
```

### 6. Frontend Muestra Resultados

El frontend recibe el array de recomendaciones ordenado y las muestra al usuario.

### 7. Usuario Selecciona Restaurante (Feedback)

Cuando el usuario selecciona un restaurante, el frontend envía feedback:

```javascript
// recommender.js
await fetch('http://localhost:8000/api/feedback', {
  method: 'POST',
  body: JSON.stringify({
    usuario: currentUsuarioData,
    contexto: contextoData,
    restaurante_seleccionado: selectedRestaurant,
    restaurantes_rechazados: rejectedRestaurants,
    razones_preferencia: ["precio", "distancia"]
  })
})
```

---

## Sistema de Aprendizaje con Redes Neuronales

### Arquitectura de la Red Neuronal

La red neuronal (`WeightOptimizerNN`) tiene la siguiente arquitectura:

```
Entrada (5 características)
    ↓
Capa Oculta (8 neuronas, ReLU)
    ↓
Capa de Salida (5 pesos normalizados)
    ↓
Salida: [wg, wp, wd, wq, wa]
```

### Características de Entrada (Features)

La función `extract_features()` extrae 5 características normalizadas [0-1]:

1. **Feature 0 - Afinidad**: Coeficiente de Jaccard entre cocinas favoritas y cocinas del restaurante
   ```python
   cocinas_comunes / total_cocinas_unicas
   ```

2. **Feature 1 - Precio Relativo**: Precio del restaurante relativo al presupuesto
   ```python
   precio_relativo = min(precio_pp / presupuesto, 2.0)
   feature = 1.0 - (precio_relativo - 1.0) if precio_relativo > 1.0 else precio_relativo
   ```

3. **Feature 2 - Cercanía**: Tiempo relativo al tiempo máximo
   ```python
   tiempo_relativo = min(tiempo_min / tiempo_max, 2.0)
   feature = 1.0 - (tiempo_relativo - 1.0) if tiempo_relativo > 1.0 else tiempo_relativo
   ```

4. **Feature 3 - Calidad**: Rating normalizado [1-5] → [0-1]
   ```python
   feature = (rating - 1) / 4
   ```

5. **Feature 4 - Disponibilidad**: Score combinado de abierto, reserva, clima
   ```python
   score = 0.0
   if abierto == 'si': score += 0.5
   if reserva == 'si' and franja == 'cena': score += 0.3
   if clima == 'lluvia' and muy_cerca: score += 0.2
   feature = min(1.0, score)
   ```

### Forward Pass (Predicción)

```python
def forward(self, X):
    # Capa oculta
    Z1 = X @ W1 + b1
    A1 = ReLU(Z1)  # max(0, Z1)
    
    # Capa de salida
    Z2 = A1 @ W2 + b2
    
    # Normalización con softmax (para que sumen 1.0)
    weights = softmax(Z2)
    
    return weights
```

### Entrenamiento con Feedback

#### Paso 1: Cálculo de Pesos Ideales

Cuando el usuario envía feedback, el sistema calcula los **pesos ideales** que deberían haberse usado:

```python
def compute_ideal_weights_from_feedback(...):
    ideal_weights = [0.35, 0.20, 0.25, 0.15, 0.05]  # Valores por defecto
    
    # Si hay razones explícitas, ajustar pesos
    if 'precio' in razones_preferencia:
        ideal_weights[1] += 0.15  # Aumentar wp
    if 'distancia' in razones_preferencia:
        ideal_weights[2] += 0.15  # Aumentar wd
    # ... etc
    
    # Comparar restaurante seleccionado vs rechazados
    features_sel = extract_features(usuario, seleccionado, contexto)
    features_rej = promedio(extract_features(usuario, rechazado, contexto) for rechazado in rechazados)
    
    diffs = features_sel - features_rej
    # Si el seleccionado es mejor en una característica, aumentar su peso
    for i, diff in enumerate(diffs):
        if diff > 0.2:  # Diferencia significativa
            ideal_weights[i] += 0.05
    
    # Normalizar para que sumen 1.0
    ideal_weights = ideal_weights / sum(ideal_weights)
    
    return ideal_weights
```

#### Paso 2: Backpropagation

```python
def train_from_feedback(...):
    # Extraer características
    X = extract_features(usuario, seleccionado, contexto)
    
    # Calcular pesos ideales
    y_true = compute_ideal_weights_from_feedback(...)
    
    # Predecir pesos actuales
    y_pred, A1, Z1 = forward(X)
    
    # Calcular error
    error = y_pred - y_true
    
    # Backpropagation
    backward(X, y_pred, y_true, A1, Z1)
    
    # Guardar feedback en historial
    save_feedback(...)
```

#### Paso 3: Actualización de Pesos

```python
def backward(X, y_pred, y_true, A1, Z1):
    # Error en salida
    dZ2 = y_pred - y_true
    
    # Gradientes capa de salida
    dW2 = (1/m) * A1.T @ dZ2
    db2 = (1/m) * sum(dZ2)
    
    # Backprop a capa oculta
    dA1 = dZ2 @ W2.T
    dZ1 = dA1 * (Z1 > 0)  # Derivada de ReLU
    
    # Gradientes capa oculta
    dW1 = (1/m) * X.T @ dZ1
    db1 = (1/m) * sum(dZ1)
    
    # Actualizar pesos
    W2 -= learning_rate * dW2
    b2 -= learning_rate * db2
    W1 -= learning_rate * dW1
    b1 -= learning_rate * db1
```

### Persistencia del Modelo

- **Historial de Feedbacks**: Se guarda en `user_feedback_history.json`
- **Modelo de la Red**: Se guarda en `nn_model.json` (cada 5 feedbacks)

### Ejemplo de Aprendizaje

**Escenario**: Usuario selecciona restaurante porque es barato y está cerca.

1. **Feedback recibido**:
   - Restaurante seleccionado: precio=2000, tiempo_min=10
   - Restaurantes rechazados: precio=6000, tiempo_min=30
   - Razones: ["precio", "distancia"]

2. **Cálculo de pesos ideales**:
   - `wp` aumenta en 0.15 (razón: precio)
   - `wd` aumenta en 0.15 (razón: distancia)
   - Comparación: seleccionado es mejor en precio y distancia
   - Pesos ideales: `[0.30, 0.35, 0.30, 0.10, 0.05]` (normalizados)

3. **Entrenamiento**:
   - La red ajusta sus pesos para predecir mejor estos pesos ideales
   - En futuras recomendaciones, dará más importancia a precio y distancia

4. **Resultado**:
   - La próxima vez que un usuario similar busque, la red sugerirá pesos que prioricen precio y distancia

---

## Instalación y Uso

### Requisitos

- Python 3.8+
- CLIPSpy (wrapper de CLIPS para Python)
- Google Maps API Key (opcional, para cálculo de tiempos)

### Instalación

```bash
# Crear entorno virtual
python -m venv .venv

# Activar entorno virtual
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

### Configuración

1. Crear archivo `.env` en el directorio raíz:
```
GOOGLE_MAPS_API_KEY=tu_api_key_aqui
CLP_PATH=tpo_gastronomico_v3_2.clp
```

2. Asegurarse de que `restaurantes.json` existe (o se creará automáticamente)

### Ejecución

```bash
# Iniciar servidor
uvicorn app.main:app --reload

# El servidor estará disponible en:
# http://localhost:8000
```

### Estructura de Archivos

```
IA-Back/
├── app/
│   ├── main.py              # API FastAPI, endpoints, preprocesamiento
│   ├── engine.py            # Wrapper de CLIPS, ejecución del motor
│   └── neural_network.py    # Red neuronal para optimización de pesos
├── tpo_gastronomico_v3_2.clp  # Sistema experto CLIPS
├── restaurantes.json        # Base de datos de restaurantes
├── user_feedback_history.json  # Historial de feedbacks
├── nn_model.json            # Modelo entrenado de la red neuronal
├── requirements.txt         # Dependencias Python
└── README.md               # Esta documentación
```

---

## Resumen

Este sistema combina:

1. **Sistema Experto (CLIPS)**: Lógica basada en reglas explícitas para filtrar y puntuar restaurantes
2. **Red Neuronal**: Aprende de las preferencias del usuario para optimizar los pesos del sistema experto
3. **Integración con APIs Externas**: Google Maps para cálculo de tiempos y geocodificación
4. **Arquitectura Híbrida**: Lo mejor de ambos mundos - reglas interpretables + aprendizaje adaptativo

El resultado es un sistema de recomendación que:
- Es **transparente** (las reglas son explícitas)
- Es **adaptativo** (aprende de cada interacción)
- Es **personalizado** (ajusta pesos según preferencias)
- Es **robusto** (filtra por requisitos obligatorios)

---

## Referencias

- [CLIPS Documentation](https://clipsrules.sourceforge.io/)
- [CLIPSpy Documentation](https://github.com/noxdafox/clipspy)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Google Maps API](https://developers.google.com/maps)

