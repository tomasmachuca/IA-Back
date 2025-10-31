
(deftemplate usuario
  (slot id)
  (multislot cocinas_favoritas)
  (slot picante (default medio))
  (slot presupuesto (type NUMBER))
  (slot tiempo_max (type NUMBER))
  (slot movilidad (default a_pie))
  (multislot restricciones)
  (slot diversidad (default media))
  (slot wg (type NUMBER))
  (slot wp (type NUMBER))
  (slot wd (type NUMBER))
  (slot wq (type NUMBER))
  (slot wa (type NUMBER))
  (slot direccion (default ""))
  (slot latitud (type NUMBER) (default 0.0))
  (slot longitud (type NUMBER) (default 0.0))
  (slot movilidad_reducida (default ""))
  (slot rating_minimo (type NUMBER) (default 0.0))
  (slot requiere_reserva (default ""))
  (slot solo_abiertos (default ""))
  (slot tiempo_espera_max (type NUMBER) (default 999.0))
  (slot tipo_comida_preferido (default ""))
  (slot estacionamiento_requerido (default ""))
)

(deftemplate contexto
  (slot clima (default templado))
  (slot dia (default viernes))
  (slot franja (default cena))
)

(deftemplate restaurante
  (slot id)
  (slot nombre)
  (multislot cocinas)
  (slot precio_pp (type NUMBER))
  (slot rating (type NUMBER))
  (slot n_resenas (type NUMBER))
  (multislot atributos)
  (slot reserva (type SYMBOL))
  (slot tiempo_min (type NUMBER))
  (slot abierto (type SYMBOL))
  (slot direccion (default ""))
  (slot latitud (type NUMBER) (default 0.0))
  (slot longitud (type NUMBER) (default 0.0))
  (slot tiempo_espera (type NUMBER) (default 0.0))
  (slot pet_friendly (type SYMBOL))
  (slot estacionamiento_propio (type SYMBOL))
  (slot tipo_comida (default ""))
  (slot horario_apertura (default ""))
  (slot horario_cierre (default ""))
)

(deftemplate descartar (slot rest) (slot razon))
(deftemplate puntaje   (slot rest) (slot criterio) (slot valor (type NUMBER)) (slot just))
(deftemplate acum      (slot rest) (slot U (type NUMBER) (default 0.0)) (multislot justifs))
(deftemplate listo     (slot rest))

; ---------- FUNCIONES AUX ----------
(deffunction normalizar-inversa (?x ?max)
  (if (<= ?x 0) then (return 1.0))
  (if (<= ?x ?max) then (return (- 1.0 (/ ?x (+ ?max 0.0001)))))
  (return 0.0)
)

(deffunction agregar-calidad (?ra ?n)
  (bind ?nr (min 1.0 (/ ?n 200.0)))
  (return (* (/ ?ra 5.0) (sqrt ?nr)))
)

(deffunction tiene-cocinas-no-coincidentes (?fav-list ?rest-list)
  (foreach ?fav-cuisine ?fav-list
    (if (member$ ?fav-cuisine ?rest-list) then
      (return FALSE) ; Encontró una coincidencia, así que NO tiene cocinas no coincidentes
    )
  )
  (return TRUE) ; No encontró ninguna coincidencia después de revisar todas, así que SÍ tiene cocinas no coincidentes
)

; ---------- INIT ----------
(defrule inicializa-acum-por-restaurante
  (declare (salience 60))
  ?r <- (restaurante (id ?id))
  (not (acum (rest ?id)))
=>
  (assert (acum (rest ?id) (U 0.0) (justifs)))
)

; ---------- FILTROS (alta prioridad) ----------
(defrule filtro-cerrado
  (declare (salience 50))
  (restaurante (id ?r) (abierto no))
=>
  (assert (descartar (rest ?r) (razon "cerrado en esta franja")))
)

(defrule filtro-dietas-sin-tacc
  (declare (salience 50))
  (usuario (restricciones $?rs))
  (test (member$ sin_tacc ?rs))
  (restaurante (id ?r) (atributos $?a))
  (test (not (member$ sin_tacc ?a)))
=>
  (assert (descartar (rest ?r) (razon "no apto sin TACC")))
)

; filtro-presupuesto eliminado - ahora se penaliza en la puntuación en lugar de descartar

(defrule filtro-movilidad-reducida
  (declare (salience 50))
  (usuario (movilidad_reducida si))
  (restaurante (id ?r) (atributos $?a))
  (test (not (member$ accesible ?a)))
=>
  (assert (descartar (rest ?r) (razon "no es accesible para movilidad reducida")))
)

(defrule filtro-pet-friendly
  (declare (salience 50))
  (usuario (restricciones $?rs))
  (test (member$ pet_friendly ?rs))
  (restaurante (id ?r) (pet_friendly ?pf))
  (test (neq ?pf si))
=>
  (assert (descartar (rest ?r) (razon "no es pet friendly")))
)

; filtro-estacionamiento eliminado - ahora se penaliza en la puntuación en lugar de descartar

(defrule filtro-restricciones-vegano
  (declare (salience 50))
  (usuario (restricciones $?rs))
  (test (member$ vegano ?rs))
  (restaurante (id ?r) (atributos $?a))
  (test (not (member$ vegano ?a)))
=>
  (assert (descartar (rest ?r) (razon "no tiene opciones veganas")))
)

(defrule filtro-restricciones-vegetariano
  (declare (salience 50))
  (usuario (restricciones $?rs))
  (test (member$ vegetariano ?rs))
  (restaurante (id ?r) (atributos $?a))
  (test (not (or (member$ vegetariano ?a) (member$ vegano ?a))))
=>
  (assert (descartar (rest ?r) (razon "no tiene opciones vegetarianas")))
)

(defrule filtro-restricciones-celiaco
  (declare (salience 50))
  (usuario (restricciones $?rs))
  (test (member$ celiaco ?rs))
  (restaurante (id ?r) (atributos $?a))
  (test (not (or (member$ celiaco ?a) (member$ sin_tacc ?a))))
=>
  (assert (descartar (rest ?r) (razon "no apto para celiacos")))
)

(defrule filtro-restricciones-lactosa
  (declare (salience 50))
  (usuario (restricciones $?rs))
  (test (member$ intolerancia_lactosa ?rs))
  (restaurante (id ?r) (atributos $?a))
  (test (not (member$ sin_lactosa ?a)))
=>
  (assert (descartar (rest ?r) (razon "no apto para intolerancia a la lactosa")))
)

(defrule filtro-requiere-reserva-si
  (declare (salience 50))
  (usuario (requiere_reserva si))
  (restaurante (id ?r) (reserva ?rv))
  (test (neq ?rv si))
=>
  (assert (descartar (rest ?r) (razon "no requiere reserva")))
)

(defrule filtro-requiere-reserva-no
  (declare (salience 50))
  (usuario (requiere_reserva no))
  (restaurante (id ?r) (reserva ?rv))
  (test (eq ?rv si))
=>
  (assert (descartar (rest ?r) (razon "requiere reserva")))
)

; ---------- CONTEXTO (prioridad media) ----------
(defrule contexto-lluvia-aumenta-cercania
  (declare (salience 10))
  (contexto (clima lluvia))
  ?u <- (usuario (wd ?wd))
=>
  (bind ?nuevo (+ ?wd 0.10))
  (modify ?u (wd (min 1.0 ?nuevo)))
)

; ---------- PUNTUACIÓN (con guardas anti-loop) ----------
(defrule puntuar-afinidad
  (declare (salience 0))
  (usuario (cocinas_favoritas $?fav) (wg ?wg))
  (restaurante (id ?r) (cocinas $?c))
  (not (descartar (rest ?r)))
  (not (puntaje (rest ?r) (criterio afinidad))) ; Reañadida
  ?ac <- (acum (rest ?r) (U ?U) (justifs $?J))
=>
  (bind ?i 0)
  (progn$ (?x $?fav) (if (member$ ?x ?c) then (bind ?i (+ ?i 1))))
  (bind ?uN (- (+ (length$ ?fav) (length$ ?c)) ?i))
  (bind ?s (if (= ?uN 0) then 0.0 else (/ ?i ?uN)))
  (bind ?inc (* ?wg ?s))
  (modify ?ac (U (+ ?U ?inc)) (justifs (create$ $?J (str-cat "afinidad=" ?s))))
  (assert (puntaje (rest ?r) (criterio afinidad) (valor ?s) (just "coincide con gustos")))
)

(defrule puntuar-precio
  (declare (salience 0))
  (usuario (presupuesto ?p) (wp ?wp))
  (restaurante (id ?r) (precio_pp ?pr))
  (not (descartar (rest ?r)))
  (not (puntaje (rest ?r) (criterio precio))) ; Reañadida
  (not (puntaje (rest ?r) (criterio penalizacion_presupuesto))) ; No puntuar precio si ya hay penalización
  ?ac <- (acum (rest ?r) (U ?U) (justifs $?J))
=>
  ; Solo puntúa positivamente si está dentro del presupuesto
  (bind ?s (if (<= ?pr ?p) then (normalizar-inversa ?pr ?p) else 0.0))
  (bind ?inc (* ?wp ?s))
  (modify ?ac (U (+ ?U ?inc)) (justifs (create$ $?J (str-cat "precio=" ?s))))
  (assert (puntaje (rest ?r) (criterio precio) (valor ?s) (just "dentro del presupuesto")))
)

(defrule puntuar-cercania
  (declare (salience 0))
  (usuario (tiempo_max ?tmax) (wd ?wd))
  (restaurante (id ?r) (tiempo_min ?t))
  (not (descartar (rest ?r)))
  (not (puntaje (rest ?r) (criterio cercania))) ; Reañadida
  ?ac <- (acum (rest ?r) (U ?U) (justifs $?J))
=>
  (bind ?s (if (<= ?t ?tmax) then (normalizar-inversa ?t ?tmax) else 0.0))
  (bind ?inc (* ?wd ?s))
  (modify ?ac (U (+ ?U ?inc)) (justifs (create$ $?J (str-cat "cercania=" ?s))))
  (assert (puntaje (rest ?r) (criterio cercania) (valor ?s) (just (str-cat ?t " min"))))
)

(defrule puntuar-calidad
  (declare (salience 0))
  (usuario (wq ?wq))
  (restaurante (id ?r) (rating ?ra) (n_resenas ?n))
  (not (descartar (rest ?r)))
  (not (puntaje (rest ?r) (criterio calidad))) ; Reañadida
  ?ac <- (acum (rest ?r) (U ?U) (justifs $?J))
=>
  (bind ?s (if (and (>= ?ra 3.5) (>= ?n 10)) then (agregar-calidad ?ra ?n) else 0.0))
  (bind ?inc (* ?wq ?s))
  (modify ?ac (U (+ ?U ?inc)) (justifs (create$ $?J (str-cat "calidad=" ?s))))
  (assert (puntaje (rest ?r) (criterio calidad) (valor ?s) (just (str-cat ?ra "★ con " ?n " reseñas"))))
)

(defrule puntuar-disponibilidad
  (declare (salience 0))
  (usuario (wa ?wa))
  (contexto (franja cena))
  (restaurante (id ?r) (reserva ?rv))
  (not (descartar (rest ?r)))
  (not (puntaje (rest ?r) (criterio disponibilidad))) ; Reañadida
  ?ac <- (acum (rest ?r) (U ?U) (justifs $?J))
=>
  (bind ?s (if (eq ?rv si) then 1.0 else 0.3))
  (bind ?inc (* ?wa ?s))
  (modify ?ac (U (+ ?U ?inc)) (justifs (create$ $?J (str-cat "disp=" ?s))))
  (assert (puntaje (rest ?r) (criterio disponibilidad) (valor ?s) (just "turnos/reserva")))
)

; ---------- PENALIZACIONES (en lugar de descartar) ----------
(defrule penalizar-presupuesto-excedido
  (declare (salience 0))
  (usuario (presupuesto ?p) (wp ?wp))
  (restaurante (id ?r) (precio_pp ?pr))
  (test (> ?pr ?p))
  (not (descartar (rest ?r)))
  (not (puntaje (rest ?r) (criterio penalizacion_presupuesto)))
  ?ac <- (acum (rest ?r) (U ?U) (justifs $?J))
=>
  ; Penalización proporcional: cuanto más supera, más penaliza (máximo -0.3 del peso wp)
  (bind ?exceso (/ (- ?pr ?p) ?p)) ; exceso como fracción del presupuesto (ej: 0.5 = 50% más caro)
  (bind ?penalizacion (min 0.3 (* ?exceso 0.5))) ; penalización máxima del 30% del peso wp
  (bind ?inc (* ?wp (- 0 ?penalizacion))) ; valor negativo para penalizar
  (modify ?ac (U (+ ?U ?inc)) (justifs (create$ $?J (str-cat "penalizacion_presupuesto=" (format nil "%.2f" ?penalizacion)))))
  (assert (puntaje (rest ?r) (criterio penalizacion_presupuesto) (valor ?penalizacion) (just "supera presupuesto")))
)

(defrule penalizar-sin-estacionamiento
  (declare (salience 0))
  (usuario (movilidad ?mov))
  (test (or (eq ?mov auto) (eq ?mov moto)))
  (restaurante (id ?r) (estacionamiento_propio ?ep))
  (test (neq ?ep si))
  (not (descartar (rest ?r)))
  (not (puntaje (rest ?r) (criterio penalizacion_estacionamiento)))
  ?ac <- (acum (rest ?r) (U ?U) (justifs $?J))
=>
  ; Penalización fija: -0.15 del índice U total (aproximadamente 15% de penalización)
  (bind ?penalizacion 0.15)
  (bind ?inc (- 0 ?penalizacion)) ; valor negativo para penalizar
  (modify ?ac (U (+ ?U ?inc)) (justifs (create$ $?J "penalizacion_estacionamiento=-0.15")))
  (assert (puntaje (rest ?r) (criterio penalizacion_estacionamiento) (valor ?penalizacion) (just "sin estacionamiento")))
)

; ---------- RANKING Y REPORTE ----------
(defrule marcar-listo
  (declare (salience 10))
  (restaurante (id ?r))
  (not (descartar (rest ?r)))
  (acum (rest ?r))
  (not (listo (rest ?r)))
=>
  (assert (listo (rest ?r)))
)

(defrule reporte-final
  (declare (salience 5))
  ?a <- (acum (rest ?r) (U ?U) (justifs $?J))
  (restaurante (id ?r) (nombre ?n))
  (listo (rest ?r))
=>
  (printout t crlf "*** " ?r " - " ?n
                " => U=" (format nil "%.3f" ?U)
                "  [" (implode$ $?J) "]" crlf)
)
