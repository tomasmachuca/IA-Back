
# app/neural_network.py
# Red Neuronal para optimizar los pesos del Sistema Experto
# Arquitectura híbrida: Sistema Experto + Aprendizaje Automático

import numpy as np
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

class WeightOptimizerNN:
    """
    Red Neuronal Simple para aprender y optimizar los pesos del Sistema Experto.
    
    Arquitectura:
    - Capa de entrada: características del usuario y restaurante (5 características principales)
    - Capa oculta: 8 neuronas con activación ReLU
    - Capa de salida: 5 pesos normalizados (wg, wp, wd, wq, wa)
    
    Entrenamiento:
    - Aprende de las interacciones del usuario (restaurantes seleccionados vs no seleccionados)
    - Ajusta los pesos para mejorar las recomendaciones futuras
    """
    
    def __init__(self, learning_rate: float = 0.01):
        self.learning_rate = learning_rate
        self.history_file = Path(__file__).parent.parent / "user_feedback_history.json"
        self.model_file = Path(__file__).parent.parent / "nn_model.json"
        
        # Inicializar pesos de la red neuronal (Xavier initialization)
        # Capa oculta: 8 neuronas
        self.W1 = np.random.randn(5, 8) * np.sqrt(2.0 / 5)  # Input (5 features) -> Hidden (8 neurons)
        self.b1 = np.zeros((1, 8))
        
        # Capa de salida: 5 pesos
        self.W2 = np.random.randn(8, 5) * np.sqrt(2.0 / 8)  # Hidden (8) -> Output (5 weights)
        self.b2 = np.zeros((1, 5))
        
        # Cargar modelo si existe
        self.load_model_if_exists()
        
    def extract_features(self, usuario: Dict, restaurante: Dict, contexto: Dict) -> np.ndarray:
        """
        Extrae características normalizadas del usuario, restaurante y contexto.
        Retorna un vector de 5 características principales.
        """
        features = np.zeros(5)
        
        # Feature 1: Afinidad (coincidencia de cocinas)
        if usuario.get('cocinas_favoritas') and restaurante.get('cocinas'):
            cocinas_comunes = len([c for c in usuario['cocinas_favoritas'] if c in restaurante['cocinas']])
            total_cocinas = len(set(usuario['cocinas_favoritas'] + restaurante['cocinas']))
            features[0] = cocinas_comunes / max(total_cocinas, 1)  # Normalizado [0-1]
        
        # Feature 2: Precio relativo al presupuesto
        if usuario.get('presupuesto') and restaurante.get('precio_pp'):
            precio_relativo = min(restaurante['precio_pp'] / max(usuario['presupuesto'], 1), 2.0)
            features[1] = 1.0 - (precio_relativo - 1.0) if precio_relativo > 1.0 else precio_relativo  # Normalizado [0-1]
            features[1] = max(0, min(1, features[1]))  # Clip a [0,1]
        
        # Feature 3: Cercanía (tiempo relativo)
        if usuario.get('tiempo_max') and restaurante.get('tiempo_min'):
            tiempo_relativo = min(restaurante['tiempo_min'] / max(usuario['tiempo_max'], 1), 2.0)
            features[2] = 1.0 - (tiempo_relativo - 1.0) if tiempo_relativo > 1.0 else tiempo_relativo  # Normalizado [0-1]
            features[2] = max(0, min(1, features[2]))  # Clip a [0,1]
        
        # Feature 4: Calidad (rating normalizado)
        if restaurante.get('rating'):
            features[3] = (restaurante['rating'] - 1) / 4  # Normalizar rating [1-5] a [0-1]
        
        # Feature 5: Disponibilidad y contexto
        disp_score = 0.0
        if restaurante.get('abierto') == 'si':
            disp_score += 0.5
        if restaurante.get('reserva') == 'si' and contexto.get('franja') == 'cena':
            disp_score += 0.3
        if contexto.get('clima') == 'lluvia':  # Preferir cercanos en lluvia
            if features[2] > 0.7:  # Muy cerca
                disp_score += 0.2
        features[4] = min(1.0, disp_score)  # Normalizado [0-1]
        
        return features.reshape(1, -1)  # Reshape a (1, 5) para batch processing
    
    def forward(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Forward pass de la red neuronal.
        Retorna los 5 pesos optimizados (wg, wp, wd, wq, wa) normalizados.
        """
        # Capa oculta con ReLU
        Z1 = np.dot(X, self.W1) + self.b1
        A1 = np.maximum(0, Z1)  # ReLU activation
        
        # Capa de salida
        Z2 = np.dot(A1, self.W2) + self.b2
        
        # Normalizar pesos usando softmax para que sumen 1.0
        # Pero primero aplicar exp para hacer positivos
        exp_Z2 = np.exp(Z2 - np.max(Z2, axis=1, keepdims=True))  # Numeric stability
        weights = exp_Z2 / np.sum(exp_Z2, axis=1, keepdims=True)
        
        return weights, A1, Z1  # Retornar también activaciones para backprop
    
    def predict_weights(self, usuario: Dict, restaurante_ejemplo: Dict, contexto: Dict) -> Dict[str, float]:
        """
        Predice los pesos óptimos para un usuario dado.
        Usa el restaurante de ejemplo para extraer características representativas.
        """
        features = self.extract_features(usuario, restaurante_ejemplo, contexto)
        weights, _, _ = self.forward(features)
        
        # Retornar como diccionario con nombres
        return {
            'wg': float(weights[0][0]),  # Peso para gustos/afinidad
            'wp': float(weights[0][1]),  # Peso para precio
            'wd': float(weights[0][2]),  # Peso para distancia/cercanía
            'wq': float(weights[0][3]),  # Peso para calidad/rating
            'wa': float(weights[0][4])   # Peso para disponibilidad
        }
    
    def backward(self, X: np.ndarray, y_pred: np.ndarray, y_true: np.ndarray, A1: np.ndarray, Z1: np.ndarray):
        """
        Backpropagation para ajustar los pesos de la red.
        
        y_true: pesos ideales (derivados del feedback del usuario)
        y_pred: pesos predichos por la red
        """
        m = X.shape[0]  # Batch size
        
        # Error en la salida (pérdida: diferencia entre pesos predichos e ideales)
        dZ2 = y_pred - y_true
        
        # Gradientes capa de salida
        dW2 = (1/m) * np.dot(A1.T, dZ2)
        db2 = (1/m) * np.sum(dZ2, axis=0, keepdims=True)
        
        # Backprop a capa oculta
        dA1 = np.dot(dZ2, self.W2.T)
        dZ1 = dA1 * (Z1 > 0)  # Derivada de ReLU
        
        # Gradientes capa oculta
        dW1 = (1/m) * np.dot(X.T, dZ1)
        db1 = (1/m) * np.sum(dZ1, axis=0, keepdims=True)
        
        # Actualizar pesos
        self.W2 -= self.learning_rate * dW2
        self.b2 -= self.learning_rate * db2
        self.W1 -= self.learning_rate * dW1
        self.b1 -= self.learning_rate * db1
    
    def compute_ideal_weights_from_feedback(
        self, 
        usuario: Dict, 
        restaurante_seleccionado: Dict,
        restaurantes_rechazados: List[Dict],
        contexto: Dict,
        razones_preferencia: List[str] = None
    ) -> np.ndarray:
        """
        Calcula los pesos ideales basado en el feedback del usuario.
        
        Lógica: Si el usuario seleccionó un restaurante con alta afinidad,
        deberíamos dar más peso a wg. Si rechazó restaurantes caros,
        deberíamos dar más peso a wp, etc.
        
        Ahora también usa razones_preferencia para ajustar más precisamente los pesos.
        """
        # Inicializar pesos ideales (empiezan con valores por defecto)
        ideal_weights = np.array([0.35, 0.20, 0.25, 0.15, 0.05])
        
        # Si hay razones explícitas del usuario, usarlas para ajustar pesos
        if razones_preferencia and len(razones_preferencia) > 0:
            for razon in razones_preferencia:
                if razon == 'precio':
                    ideal_weights[1] += 0.15  # Aumentar peso de precio (wp)
                elif razon == 'distancia':
                    ideal_weights[2] += 0.15  # Aumentar peso de distancia (wd)
                elif razon == 'calidad':
                    ideal_weights[3] += 0.15  # Aumentar peso de calidad (wq)
                elif razon == 'gustos':
                    ideal_weights[0] += 0.15  # Aumentar peso de gustos (wg)
                elif razon == 'abierto':
                    ideal_weights[4] += 0.10  # Aumentar peso de disponibilidad (wa)
                elif razon == 'reserva':
                    ideal_weights[4] += 0.08  # Aumentar peso de disponibilidad (wa)
                elif razon == 'caracteristicas':
                    # Las características pueden afectar varios pesos
                    ideal_weights[4] += 0.05  # Disponibilidad
        
        # Analizar restaurante seleccionado
        features_sel = self.extract_features(usuario, restaurante_seleccionado, contexto).flatten()
        
        # Analizar restaurantes rechazados (promedio)
        if restaurantes_rechazados:
            features_rej = np.mean([
                self.extract_features(usuario, r, contexto).flatten() 
                for r in restaurantes_rechazados
            ], axis=0)
            
            # Ajustar pesos ideales: dar más peso a características donde el seleccionado es mejor
            diffs = features_sel - features_rej
            
            # Aumentar peso de características donde el seleccionado es significativamente mejor
            for i, diff in enumerate(diffs):
                if diff > 0.2:  # Diferencia significativa
                    ideal_weights[i] += 0.05
                elif diff < -0.2:  # El rechazado era mejor aquí
                    ideal_weights[i] -= 0.02
        
        # Si no hay rechazados y no hay razones explícitas, usar características del seleccionado para ajustar
        elif not razones_preferencia or len(razones_preferencia) == 0:
            # Si tiene alta afinidad, aumentar wg
            if features_sel[0] > 0.7:
                ideal_weights[0] += 0.1
            # Si tiene buen precio, aumentar wp
            if features_sel[1] > 0.7:
                ideal_weights[1] += 0.05
            # Si está cerca, aumentar wd
            if features_sel[2] > 0.7:
                ideal_weights[2] += 0.05
            # Si tiene buen rating, aumentar wq
            if features_sel[3] > 0.7:
                ideal_weights[3] += 0.05
        
        # Normalizar para que sumen 1.0
        ideal_weights = np.maximum(ideal_weights, 0.01)  # Evitar pesos negativos o cero
        ideal_weights = ideal_weights / np.sum(ideal_weights)
        
        return ideal_weights.reshape(1, -1)
    
    def train_from_feedback(
        self,
        usuario: Dict,
        restaurante_seleccionado: Dict,
        restaurantes_rechazados: List[Dict],
        contexto: Dict,
        razones_preferencia: List[str] = None
    ):
        """
        Entrena la red neuronal con feedback del usuario.
        """
        # Extraer características
        X = self.extract_features(usuario, restaurante_seleccionado, contexto)
        
        # Calcular pesos ideales (ahora con razones de preferencia)
        y_true = self.compute_ideal_weights_from_feedback(
            usuario, restaurante_seleccionado, restaurantes_rechazados, contexto, razones_preferencia
        )
        
        # Predecir pesos actuales
        y_pred, A1, Z1 = self.forward(X)
        
        # Backpropagation
        self.backward(X, y_pred, y_true, A1, Z1)
        
        # Guardar feedback en historial
        self.save_feedback(usuario, restaurante_seleccionado, restaurantes_rechazados, contexto, razones_preferencia)
    
    def save_feedback(
        self,
        usuario: Dict,
        restaurante_seleccionado: Dict,
        restaurantes_rechazados: List[Dict],
        contexto: Dict,
        razones_preferencia: List[str] = None
    ):
        """Guarda el feedback en el historial para análisis posterior."""
        from datetime import datetime
        
        feedback = {
            'usuario_id': usuario.get('id', 'anonymous'),
            'restaurante_seleccionado': restaurante_seleccionado.get('id'),
            'restaurantes_rechazados': [r.get('id') for r in restaurantes_rechazados],
            'contexto': contexto,
            'razones_preferencia': razones_preferencia or [],
            'timestamp': datetime.now().isoformat()
        }
        
        history = self.load_history()
        history['feedbacks'].append(feedback)
        
        # Limitar historial a 1000 entradas
        if len(history['feedbacks']) > 1000:
            history['feedbacks'] = history['feedbacks'][-1000:]
        
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error guardando historial: {e}")
    
    def load_history(self) -> Dict:
        """Carga el historial de feedbacks."""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {'feedbacks': []}
    
    def save_model(self, filepath: str = None):
        """Guarda los pesos de la red neuronal."""
        if filepath is None:
            filepath = self.model_file
            
        model_data = {
            'W1': self.W1.tolist(),
            'b1': self.b1.tolist(),
            'W2': self.W2.tolist(),
            'b2': self.b2.tolist()
        }
        try:
            with open(filepath, 'w') as f:
                json.dump(model_data, f, indent=2)
            print(f"Modelo guardado en {filepath}")
        except Exception as e:
            print(f"Error guardando modelo: {e}")
    
    def load_model_if_exists(self):
        """Carga los pesos de la red neuronal si existe el archivo."""
        if self.model_file.exists():
            try:
                with open(self.model_file, 'r') as f:
                    model_data = json.load(f)
                    self.W1 = np.array(model_data['W1'])
                    self.b1 = np.array(model_data['b1'])
                    self.W2 = np.array(model_data['W2'])
                    self.b2 = np.array(model_data['b2'])
                print(f"Modelo cargado desde {self.model_file}")
            except Exception as e:
                print(f"Error cargando modelo: {e}")

