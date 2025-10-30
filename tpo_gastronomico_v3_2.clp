
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
)

(deftemplate contexto
  (slot clima (default templado))
  (slot dia (default viernes))
  (slot franja (default cena))
  (slot grupo (default pareja))
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

(defrule filtro-presupuesto
  (declare (salience 50))
  (usuario (presupuesto ?p))
  (restaurante (id ?r) (precio_pp ?pr))
  (test (> ?pr ?p))
=>
  (assert (descartar (rest ?r) (razon "supera el presupuesto")))
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
  ?ac <- (acum (rest ?r) (U ?U) (justifs $?J))
=>
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
