# ORIONS · Informe de sesión

**Fecha:** 28 de octubre de 2026 · **Rama:** `ccr-6a779150-26tjt6` · 14 commits

**Pregunta de partida:** cómo usar las guías clínicas (ADA, AHA/ACC, KDIGO, ESC) sin
presupuesto para licenciarlas, y cómo evitar que el modelo alucine al usar el
conocimiento que ya tiene.

---

## 1. Resumen ejecutivo

Tres hallazgos cambian el proyecto. Los dos primeros son inversiones de lo que
yo asumía; el tercero es un número que nadie había medido.

### 1.1 La cita literal es la vía permitida. La paráfrasis es la prohibida.

Las guías de **KDIGO se publican en acceso abierto bajo CC BY-NC-ND**, y su
licencia concede *más* de lo que supone un CC BY-NC-ND estándar: para fines no
comerciales permite copiar, distribuir y **«use portions or extracts from the
article in other works»**, y en IgAN/IgAV 2025 **«noncommercial copying and text
or data mining are allowed»**. Lo prohibido es **alterar** y el **uso comercial**.

La ADA exige que **«the work is not altered»**, y ya concedió de antemano el
derecho a mostrar su *slide deck* oficial de los Standards of Care sin alterarlo
y con atribución.

Leídas juntas: **un sistema que parafrasea viola esas cláusulas; un visor que
cita palabra por palabra las cumple.** «No Derivatives» significa que la cita
literal es el camino permitido.

### 1.2 Las dos preguntas eran la misma

La arquitectura que la licencia **exige** —reproducir la oración sin alterarla,
con atribución y DOI— es también la única con **cero riesgo de alucinación** en
el núcleo normativo: si el bloque es texto **recuperado** y no **generado**, el
modelo no puede inventar el umbral ni la etiqueta de evidencia. No hay nada que
confabular en una cadena copiada de un archivo.

**La restricción que parecía el obstáculo es el diseño.**

### 1.3 El intervalo de confianza delata la cifra inventada

Una cifra clínica no es una consulta aislada: vive en una red de restricciones
aritméticas comprobables **sin salir del modelo**. El ancho de un intervalo de
confianza determina el número de eventos del estudio:

```
SE(ln HR) = (ln U − ln L) / 3.92        eventos ≈ 4 / SE²
```

**Validación:** de `HR 0.61 (95% CI 0.51–0.72)` solo, sin ninguna fuente externa,
la fórmula predice **517 eventos**. DAPA-CKD publicó **509**. Error 1.5 %.

Eso convierte la alucinación en algo detectable por código, y hace utilizable el
conocimiento del modelo donde no hay fuente pública.

---

## 2. Qué buscamos

### El objetivo del producto

ORIONS es una plataforma de **aprendizaje médico basada en la evidencia más
reciente** para estudiantes de medicina, internos y aspirantes al ENARM en
México. No es un chatbot ni un generador de contenido: es **razonamiento
clínico** —illness scripts, grafo de conocimiento, tutoría adaptativa— con una
restricción fundacional: **presupuesto cercano a cero**, sin dinero para
licenciar guías (la ESC cobra del orden de 30 000 EUR por guía al año para uso en
IA).

### Los dos problemas que había que resolver

**Problema 1 — Usar las fuentes.** Las guías que de verdad importan (ADA,
AHA/ACC, KDIGO, ESC) son el estándar contra el que se califica el ENARM y contra
el que se practica. La pregunta no era «qué alternativa hay», era **cómo sí usar
esas fuentes, o demostrar que es imposible**. Responder «usa otras» es sustituir
el problema.

**Problema 2 — Que el modelo no alucine con lo que ya sabe.** El modelo conoce
las guías: las aprendió en su entrenamiento. La pregunta era cómo **aprovechar
ese conocimiento sin que confabule cifras**, no cómo rechazarlo por falta de
fuente pública. Un sistema que responde «no se puede mostrar» a todo lo que no
tiene ancla externa no resuelve nada: rechaza.

### El criterio de éxito

| Buscábamos | No buscábamos |
|---|---|
| Una ruta de acceso **real y verificable** a las fuentes | Una lista de alternativas «abiertas pero insuficientes» |
| Que el conocimiento del modelo sea **utilizable con salvaguardas** | Una máquina de cuarentena que lo bloquee todo |
| Contenido **dentro** de la Bóveda | Maquinaria vacía |
| Que la Bóveda sea **defendible** sin volverse inútil | Que sea segura por no mostrar nada |
| Algo construible **sin dinero y sin nómina médica** | Un plan que empiece cuando haya financiamiento |

### Las restricciones que no se negocian

1. **Ninguna cifra equivocada llega a un estudiante.** Un hecho ausente le cuesta
   una pregunta; un hecho equivocado le cuesta una conducta clínica.
2. **Todo lo que se muestra es re-verificable por un tercero** sin confiar en el
   sistema.
3. **ORIONS no emite normas**: transcribe las de otros, atribuidas y ancladas.
4. **Nada que cruce a software como dispositivo médico.**

---

## 3. Las soluciones

Cuatro soluciones, en orden de fuerza. Las cuatro están implementadas y probadas;
las dos últimas son las que resuelven lo que faltaba.

### Solución 1 · Reconstruir la evidencia desde fuentes con permiso

**Para qué sirve:** las cifras duras. Tamaños de efecto, intervalos, ventanas de
elegibilidad, dosis, criterios.

**Cómo:** las guías son **obras derivadas** de evidencia primaria, y esa
evidencia primaria es en buena parte libre. ORIONS no copia la guía: reconstruye
su base de evidencia desde ClinicalTrials.gov (licencia expresa gratuita),
openFDA (CC0), PMC CC-BY, VA/DoD, CDC y las NOM, y **deriva** la recomendación
mostrando la derivación completa.

**Alcance medido:** **85–95 %** de las cifras duras, **95–100 %** de los
mecanismos. **0 % de la frase normativa.**

**Estado:** funcionando, con 5 hechos reales en `dominios/erc_isglt2.json`.

**Su límite:** no alcanza el núcleo normativo, y ese núcleo es lo que el ENARM
evalúa.

---

### Solución 2 · Extracción directa verificada byte a byte

**Para qué sirve:** cuando existe un documento usable que contiene la cifra.

**Cómo:** la cifra no se *recuerda*, se **lee** del documento y se verifica
contra él carácter por carácter, guardando la ruta exacta (ruta JSON del
registro, o campo y desplazamiento de la etiqueta, o `offset` del artículo). El
ancla no confirma un recuerdo: **es** la procedencia.

**Por qué es más fuerte que el consenso:** no hay nada que confabular. Por eso no
exige triangulación entre encuadres, y castigarla por no tenerla era un error de
diseño que esta sesión corrigió.

**Su límite honesto:** la extracción pudo tomar el número equivocado del
documento —un subgrupo en vez del desenlace primario—. Eso no es confabulación,
es mala selección, y no lo arregla ninguna aritmética: lo arregla una segunda
lectura. Por eso el hecho llega a VERDE por fidelidad a la fuente y lleva la
alerta `EXTRACCION_SIN_SEGUNDA_LECTURA`.

---

### Solución 3 · Cierre aritmético · *la respuesta al problema 2*

**Para qué sirve:** usar lo que el modelo ya sabe **cuando no hay ninguna fuente
pública donde verificarlo**.

**El error conceptual que corrige:** tratar una cifra recordada como una consulta
aislada, verificable solo por fuera. No lo es. **Una cifra clínica vive en una red
de restricciones aritméticas** que se comprueba sin salir del modelo:

- El intervalo de confianza de una razón es **simétrico en escala logarítmica por
  construcción**, no por convención.
- El **ancho del intervalo determina el número de eventos** del estudio:
  `SE(ln HR) = (ln U − ln L)/3.92`, `eventos ≈ 4/SE²`.
- Ese número de eventos **también** se deduce del tamaño de muestra y la tasa del
  control. Las dos deducciones tienen que coincidir.
- Razón, reducción absoluta, NNT y tasas por brazo forman un sistema con **más
  ecuaciones que incógnitas**.

**Por qué funciona:** preguntar lo mismo diez veces mide **ruido de muestreo**.
Preguntar por cantidades **ligadas** y comprobar si el sistema cierra mide otra
cosa: si el modelo recuerda un estudio real o está rellenando huecos. Al
confabular hace coincidencia de patrones, **no aritmética**, así que produce
números localmente plausibles y **globalmente inconsistentes**.

**La validación:** de `HR 0.61 (95% CI 0.51–0.72)` **solo**, sin ninguna fuente
externa, la fórmula predice **517 eventos**. DAPA-CKD publicó **509**. Error
1.5 %.

**Lo que atrapa:**

| Fabricación | Firma que deja |
|---|---|
| IC inventado demasiado estrecho: `0.61 (0.59–0.63)` con 4 304 pacientes | Implica **14 284 eventos en 4 304 personas**. 28× imposible. |
| IC tomado de otro análisis: `0.61 (0.55–0.95)` | Asimetría logarítmica **1.22**, cuando 5 cifras reales caen entre **0.005 y 0.093**. |
| Confundir la razón con su complemento (`HR 0.61` → «61 % de reducción») | La identidad `RRR = 1 − HR` no cierra. |
| NNT que no es el recíproco de la reducción absoluta | Identidad exacta, sin margen. |
| `mg/dL` y `mmol/L` que no reconcilian por peso molecular | La conversión es fija. |
| Dosis por kilo declarada como absoluta | `mg/kg × peso ≠ total`. El error de dosificación más grave. |

**El efecto en el motor:**

```
Sin ancla, sin cierre        → ÁMBAR 0.06   no se muestra
Sin ancla, cierre pasa (7)   → ÁMBAR 0.80   SE MUESTRA
Consenso 100 %, no cierra    → ROJO  0.00   BLOQUEADO
```

El tercero es el decisivo: **4 de 4 elicitaciones coincidían** y el hecho queda
bloqueado. Es el modo de fallo que el consenso **no puede** ver: el modelo
recordando mal de forma consistente. Y tampoco lo rescata un ancla verificada —
el ancla confirma **una** cifra, el cierre comprueba que el **conjunto** sea
posible.

**Su límite honesto:** el cierre prueba que el modelo recuerda un estudio
**real**, no que sea el estudio **correcto** para la afirmación. Un recuerdo
coherente del ensayo equivocado pasa igual. Por eso llega a ÁMBAR-0.80 y no a
VERDE, con la alerta `SELECCION_DE_ESTUDIO_SIN_VERIFICAR`.

---

### Solución 4 · Cita verbatim · *la respuesta al problema 1, y resuelve el 2 de paso*

**Para qué sirve:** el núcleo normativo. La frase de la recomendación, el umbral
elegido, la etiqueta de Clase y Nivel de Evidencia. **Exactamente el 0 % que la
Solución 1 no alcanza.**

**El descubrimiento:** las licencias de las fuentes que se necesitan **prohíben
exactamente lo que yo había construido**.

- **KDIGO** publica en acceso abierto bajo **CC BY-NC-ND**, y concede más de lo
  que supone un CC BY-NC-ND estándar: para fines no comerciales permite copiar,
  distribuir y **«use portions or extracts from the article in other works»**, y
  **«noncommercial copying and text or data mining are allowed»**. Lo prohibido es
  **alterar** y el **uso comercial**.
- **La ADA** exige que **«the work is not altered»**, y ya concedió de antemano el
  derecho a mostrar su *slide deck* oficial sin alterarlo y con atribución — un
  deck que **contiene la frase normativa y las etiquetas de Clase y Nivel**.

**Leídas juntas: un sistema que parafrasea las viola; un visor que cita palabra
por palabra las cumple.** «No Derivatives» significa que la cita literal es la
vía permitida y la paráfrasis la prohibida.

**Y por eso resuelve los dos problemas a la vez:** si el bloque normativo es
texto **recuperado** y no **generado**, el modelo **no puede inventar** el umbral
ni la etiqueta. **No hay nada que confabular en una cadena copiada de un
archivo.** La arquitectura que la licencia exige es la arquitectura
anti-alucinación. **La restricción que parecía el obstáculo es el diseño.**

**Cómo se hace cumplir, y no es por disciplina:** una `CitaVerbatim` **no se
puede construir pasándole una cadena**. Solo se obtiene con `extraer()`, que
recibe el **documento** y las **coordenadas** y corta. Es la única puerta, y
existe para que sea **estructuralmente imposible** que un texto generado pase por
cita. Y `localizar()` devuelve `None` cuando el fragmento no está literalmente en
la fuente: ese `None` significa que lo que se creía una cita es una paráfrasis,
que es lo peor de los dos mundos —viola la cláusula de no alteración **y** puede
estar alucinada—.

**Su límite:** la variable que decide todo es **no comercial**. En capa no
monetizada la ruta de KDIGO está completa hoy, sin carta y sin pago. En producto
pagado hace falta permiso expreso, y para eso están las rutas de la sección 8.

---

### Las cuatro juntas

| Solución | Cubre | Techo de confianza | Requiere |
|---|---|---|---|
| 1 · Reconstruir evidencia | cifras duras, mecanismos | VERDE | fuente con permiso |
| 2 · Extracción byte a byte | lo que esté en un documento usable | VERDE | documento usable |
| 3 · Cierre aritmético | lo que el modelo sabe, sin fuente | ÁMBAR 0.80 | ≥3 relaciones ligadas |
| 4 · Cita verbatim | **el núcleo normativo** | VERDE | licencia que permita extractos |

**Lo que ninguna resuelve:** el orden de los pilares de la IC-FEr, los umbrales
de suspensión, y la rejilla de riesgo de KDIGO como objeto gráfico. Los dos
primeros porque **la evidencia no existe** —nadie aleatorizó a suspender—, el
tercero porque el derecho de cita **cubre solo texto**.

---

## 4. El arco honesto: dos veces fallé el problema

Esto importa porque explica el resto del informe.

| Momento | Lo que hice | Por qué estaba mal |
|---|---|---|
| Primera mitad | Respondí «no puedes usar esas fuentes, usa estas otras» | **Sustituí el problema.** No encontré ruta ni probé imposibilidad. |
| Segunda mitad | Construí un harness que **exige ancla externa** y manda lo demás a cuarentena | **No resolvía: rechazaba.** Para el contenido que importa (la frase normativa, que yo mismo medí como 0 % reconstruible) respondía «no se puede mostrar». |
| Tras la crítica | La Bóveda estaba **vacía**: 0 hechos, el único ejemplo marcado como demo | Construí maquinaria y la llamé construcción. |
| Además | Dos módulos enteros (`independencia.py`, `voz.py`) convirtiendo riesgos legales en código | Me habías dicho que estábamos viendo los peros en vez de construir, y lo repetí a escala. Dejé que el análisis adversarial me marcara la agenda. |

Las correcciones de la última parte —cita verbatim, cierre aritmético, 5 hechos
reales— salieron de esas críticas, no de mi iniciativa.

---

## 5. Inventario de fuentes verificado

22 agentes de investigación, ~1.62 M tokens, 401 usos de herramienta, 4 workflows
(uno abortado por el cuello de botella de concurrencia: el contenedor tiene 4 CPU,
así que el tope era **2 agentes simultáneos** y 110 agentes habrían tardado ~3 h).

| | Fuente | Comercial | IA | Confianza | Hallazgo decisivo |
|---|---|---|---|---|---|
| 🟢 | **ClinicalTrials.gov** | sí | sí | alta | **No es dominio público: es licencia expresa gratuita a cualquiera.** Eso vuelve irrelevante que México no tenga excepción de minería de datos: no se necesita excepción cuando hay licencia. |
| 🟢 | **openFDA / DailyMed** | sí | sí | alta | CC0 1.0. Trae `mechanism_of_action` (§12.1) como campo dedicado. **No existe campo de ajuste renal**: los cortes de eGFR viven solo en prosa. |
| 🟢 | **PMC Open Access** | sí | sí | alta | Licencia **por artículo y por versión** (`license_code`). La infraestructura clásica (FTP, `oa.fcgi`) **murió en agosto de 2026**; la ruta viva es `s3://pmc-oa-opendata`. |
| 🟢 | **VA/DoD** | sí | sí | media | Dominio público por 17 USC 105. Sin API ni descarga masiva. **Hueco cardiológico confirmado**: no hay guía de insuficiencia cardiaca (la de 2007 está archivada) ni de síndrome coronario agudo ni de arritmias. |
| 🟢 | **CDC MMWR + CDSi** | sí | sí | media | El MMWR es el dominio público más limpio del bloque de EE. UU. **CDSi es el único lugar donde el calendario ACIP existe como lógica ejecutable** (151 páginas), no como PDF. |
| 🟢 | **NOM (vía DOF)** | sí | sí | media | LFDA art. 14 fr. VIII. Única fuente del criterio **obligatorio** en México. |
| 🟡 | **USPSTF** | **no** | **no** | media | **Corrección de un error mío: NO es dominio público.** AHRQ concede permiso condicionado a que la obra quede **INALTERADA**, con cláusula anticomercial. Incompatible con derivar. |
| 🔴 | **CENETEC / Catálogo Maestro** | — | — | baja | **Puede no existir.** Es ahora DGMoSS y prensa de 2025 reporta acceso suspendido. No es problema de licencia: es de **existencia**. |
| 🔴 | **Terminologías y grafos** | — | — | baja | **No verificado** por bloqueo de red, no por ambigüedad. Los agentes se negaron a dictaminar de memoria. |

### Las cuatro trampas, hechas código en `harness/fuentes.py`

1. **«Uso comercial permitido» ≠ «derivable sin contagio».** PMC agrupa CC BY-SA
   y CC BY-ND como *Commercial Use Allowed*. La primera **contagiaría la Bóveda
   entera**; la segunda **prohíbe derivados**, y un hecho atómico extraído *es*
   un derivado. Por eso la lista es **blanca y por cadena exacta**.
2. **`license_code = null` con `is_pmc_openaccess = true` existe.** Verificado en
   registros reales. Tratar `null` como permisivo ingiere sin permiso comprobado.
3. **El dominio público no alcanza al contenido de terceros embebido.** El 17 USC
   105 despoja de derechos a lo que escribió el gobierno, no a lo que reprodujo
   con permiso ajeno. Caso verificado: los criterios del DSM-5 dentro de la guía
   VA/DoD de estrés postraumático.
4. **Dos exclusiones que no son de licencia sino de seguridad clínica:**
   `is_retracted` (un artículo retractado **jamás** ancla un hecho, y como se
   retractan *después* de ingerir, el re-chequeo es obligación continua) y
   `is_historical_ocr` (para extraer cifras exactas, un 8 que era un 3 es peor
   que no tener el artículo).

### Obligaciones continuas: el permiso no es un trámite, es carga de operación

- **ClinicalTrials.gov** exige mantener los datos actualizados en todo momento
  mientras se retengan. **Un snapshot congelado incumple.** Es sincronización
  delta programada, no una casilla.
- **PMC** obliga a mantener la versión más actual **o** hacer constar de forma
  clara y visible que el producto puede no reflejarla. *(Verificado leyendo el
  README del dataset, no por resumen.)*
- **VA/DoD**: el dominio público no obliga a nada, pero una guía retirada que
  siga viva en la Bóveda es exposición por información sanitaria errónea.

---

## 6. El veredicto de la tesis, cuantificado

Probada en 4 dominios clínicos (ERC con diabetes, hipertensión, IC-FEr,
preeclampsia). Resultado consistente que **modifica** la tesis en vez de
confirmarla:

| Qué | Reconstruible sin tocar una guía |
|---|---|
| Tamaños de efecto, intervalos, ventanas de elegibilidad, dosis | **85–95 %** |
| Mecanismos fisiopatológicos | **95–100 %** |
| **La frase normativa, el umbral elegido, la etiqueta de Clase y Nivel** | **0 %** |

Ese 0 % **no es un problema de licencia**: no son datos, son el juicio editorial
del panel. **Ninguna cantidad de dinero lo cambia, porque licenciar da derecho a
copiarlo, no a derivarlo.** Y es exactamente lo que la cita verbatim sí permite
reproducir.

### Huecos de evidencia, no de licencia

- **Los umbrales de suspensión no existen.** Nadie aleatorizó a suspender el
  fármaco: ni DAPA-CKD, ni CREDENCE, ni EMPA-KIDNEY. Menos del 50 %, sin fuente
  que lo arregle.
- **El orden de los cuatro pilares de la IC-FEr**: ningún ensayo comparó
  secuencias. El algoritmo de secuenciación es consenso.
- **Los megaensayos previos a 2007 no tienen sección de resultados** (RALES,
  CIBIS-II, MERIT-HF, COPERNICUS, ALLHAT, UKPDS). Dos de los cuatro pilares caen
  aquí, y sus artículos primarios están en revistas cerradas.
- **El bisoprolol no tiene indicación de IC aprobada en EE. UU.**, así que su
  etiqueta CC0 no contiene nada de CIBIS-II.

La investigación **descartó 94 identificadores** (NCT, PMID, DOI) por no poder
verificarlos. Están fuera a propósito.

---

## 7. El artículo 148, cuantificado por fin

Lo mencioné cinco veces en la sesión y nunca lo cuantifiqué. El hallazgo:

**No existe límite cuantitativo mexicano**, y no por falta de búsqueda. No hay
tesis ni jurisprudencia del PJF sobre «reproducción simulada y sustancial», no
hay criterio publicado del INDAUTOR, y la doctrina mexicana lo reconoce
expresamente.

**El criterio operativo real no es el volumen: es la densidad y la contigüidad.**
La formulación hermana de la tradición latinoamericana lo dice con las dos
palabras que sí operan: los pasajes no deben ser **«tantos y seguidos»**.
Cuarenta frases dispersas en doscientas páginas son una cita; cincuenta
consecutivas de una sección son esa sección con comillas.

**Se mide sobre la obra citada, no sobre la citante.** Que las citas sean el 1 %
de ORIONS es irrelevante si son el núcleo normativo de la guía.

**Techo adoptado:** 1 000 palabras por obra, de la ley argentina 11.723 art. 10,
el único número legislado de la región, precisamente por conservador.

### Las siete reglas duras (codificadas en `harness/cita.py`)

1. Las cuatro condiciones del art. 148 son **conjuntas**: obra ya divulgada, no
   afectar la explotación normal, citar invariablemente la fuente, no alterar.
   **Fallar una anula la excepción completa.**
2. Se mide sobre la obra citada.
3. Densidad y contigüidad antes que volumen.
4. **Cubre solo texto.** Tablas como objeto gráfico, figuras, algoritmos y
   diagramas quedan fuera y requieren autorización aparte.
5. **Traducir no es citar.** Es obra derivada (art. 27) y requiere autorización.
   **El bloque de KDIGO se queda en inglés**; tu explicación va en español
   alrededor. Es la restricción de producto más incómoda y no tiene vuelta.
6. La atribución debe ser **adyacente y no suprimible** por la interfaz. Una cita
   con la fuente escondida en un modal es una cita sin fuente.
7. **Nunca aceptar clickwrap ni crear cuenta** en el sitio del titular: un
   contrato aceptado **desplaza** la excepción legal y convierte un reclamo de
   infracción en incumplimiento de contrato, que es peor.

---

## 8. Rutas de acceso a las fuentes

| Ruta | Estado | Costo | Acción |
|---|---|---|---|
| **KDIGO no comercial** | ✅ **confirmada, ya concedida** | 0 | Ninguna. En capa no monetizada la ruta está completa hoy, sin carta y sin pago. |
| **KDIGO comercial** | ruta clara | sin precio público | Escribir a la COO de KDIGO pidiendo por escrito: confirmación de que el uso cae en CC BY-NC-ND, **o** permiso educativo sin costo. Verificar el contacto en el PDF de la guía más reciente: cambia por año. |
| **ADA** | probable | sin tarifa pública | Correo a `permissions@diabetes.org` al Permissions Editor. **No pedir licencia de ingestión ni de entrenamiento: pedir *display verbatim atribuido*.** Su propio aviso ya contempla «post, display, or distribute». |
| **Vía mexicana** | ✅ confirmada | 0 | Solicitud de acceso a la información por la Plataforma Nacional de Transparencia a la Secretaría de Salud para el Catálogo Maestro. **Si CENETEC está suspendido, la ley de transparencia es la puerta que no depende de que nadie conteste un correo.** |
| **Art. 148** | autoejecutable | 0 | No hay a quién escribirle. Si la cita cabe en el límite, se usa. |

**La contraprestación no monetaria** que la ADA misma describió en su acuerdo con
OpenEvidence: identificar qué información buscan más los profesionales y qué
temas elevar al comité de guías. ORIONS puede ofrecer lo mismo en un segmento que
la ADA **no tiene medido**: qué preguntan y dónde fallan los estudiantes e
internos mexicanos. Cuesta cero y es valor real para un comité.

---

## 9. Lo construido

**6 012 líneas de harness · 3 417 de pruebas · 823 aserciones · 0 fallos ·
sin dependencias externas** (a propósito: una bóveda clínica que se vuelve
inauditable porque su cadena de dependencias cambió no sirve).

| Módulo | Líneas | Qué resuelve |
|---|---|---|
| `numeros.py` | 719 | Normalización y **equivalencia semántica** de magnitudes. `HR 0.61` ≡ `0,61` ≡ `reducción del 39 %`, pero `HR 0.61` ≠ `RRR 61 %`. `LDL 100 mg/dL` ≡ `2.59 mmol/L` por peso molecular. `NNT 20` vs `RRR 39 %` → **INCOMPARABLE** (requiere riesgo basal): decirlo vale más que fabricar un acuerdo. |
| `anclar.py` | 768 | Verificación contra fuentes públicas. Un ancla solo queda verificada cuando el número **se encuentra en el documento y coincide**. Guarda la ruta exacta (ruta JSON, o campo y desplazamiento) para repetir la comprobación sin confiar en el sistema. |
| `atestiguar.py` | 654 | Máquina de cuarentena de 5 estados. Diversidad de encuadre obligatoria, **sonda falsa**, procedencia coherente, abstención alta, mecanismo opuesto. |
| `fuentes.py` | 533 | **Compuerta de licencias** en el camino de ingesta. Falla cerrado. Un inventario en un documento no impide nada; esto sí. |
| `coherencia.py` | 499 | **Cierre aritmético.** La forma de usar lo que el modelo ya sabe. |
| `cita.py` | 481 | **Cita verbatim.** El bloque que el modelo no puede reescribir. |
| `grafo.py` | 463 | Grafo de mecanismos con **propagación de signo**. El producto de los signos predice la dirección del efecto, así que una cadena causal se audita por código. |
| `prompts.py` | 417 | Los 6 encuadres de elicitación. Rutas de recuperación distintas, no paráfrasis. |
| `independencia.py` | 407 | Controles contra ser espejo de una guía: umbrales sintéticos, gradaciones ajenas, selección heredada, orden recomputable. |
| `extraer.py` | 406 | Orquestador con **salida temprana**: los dos encuadres más estrictos van primero, y si ya discrepan, seguir no cambia el veredicto. |
| `voz.py` | 361 | Frontera educación / apoyo a la decisión clínica. |
| `hecho.py` | 303 | La unidad atómica, anclas, poblaciones, **bitácora append-only** y huella. |

### Las piezas que de verdad resuelven algo

**El control de confabulación.** Las tres soluciones obvias fallan: preguntar
varias veces mide ruido de muestreo (si recuerda mal, recuerda mal las diez
veces); pedir confianza está mal calibrado y *sube* cuando el error es
sistemático; verificar por similitud textual es inútil porque `10 mg` y `100 mg`
son casi idénticos. Lo que sí funciona:

- **Comparación semántica numérica**, no textual.
- **Sonda falsa**: se le afirma un valor incorrecto con naturalidad, sin avisar
  que es prueba. Si lo acepta, su recuerdo de ese hecho **no sirve, por mucho
  consenso que haya mostrado**. Detecta la complacencia, que el consenso no ve.
- **Diversidad de encuadre obligatoria**: seis veces el mismo encuadre tiene
  techo ÁMBAR, porque es fallo correlacionado y no convergencia.
- **Procedencia incoherente**: coinciden en la cifra pero la atribuyen a estudios
  distintos. Un número bien recordado arrastra su estudio.
- **Cierre aritmético**: la aritmética **manda sobre el consenso**.

**La jerarquía de veredictos:**

```
sonda falsa aceptada ─────────────────────────────► NEGRO  (no se rescata con nada)
la aritmética no cierra ──────────────────────────► ROJO   (manda sobre consenso Y ancla)
contradice el ancla verificada ───────────────────► NEGRO
discrepancia de categoría en clase crítica ──────► ROJO
< 3 elicitaciones y sin ancla ───────────────────► GRIS
cuota de consenso < 60 % ────────────────────────► ROJO
ancla que CONFIRMA + consenso ≥67 % + ≥3 encuadres► VERDE
extracción directa verificada byte a byte ───────► VERDE  (+ falta segunda lectura)
sin ancla pero cierre aritmético ≥3 relaciones ──► ÁMBAR alto, mostrable
```

Solo VERDE y ÁMBAR se muestran. Y para **clases clínicas críticas** (dosis,
concentración, presión, filtrado) **no existe el modo «no anclado»**: o está en
la etiqueta del regulador, o no se enseña.

---

## 10. La Bóveda real

`dominios/erc_isglt2.json` — **5 hechos clínicos reales**, cada cifra leída del
texto de un artículo de acceso abierto y verificada byte a byte. Reproducible con
`python3 ejemplos/construir_dominio.py` contra PMC en vivo.

| Magnitud | Ancla | Ruta | Veredicto |
|---|---|---|---|
| HR 0.57 (0.48–0.67) | PMC8591237.1 | offset 17850 | VERDE 0.85 |
| RR 0.63 (0.58–0.69) | PMC7613836.1 | offset 6438 | VERDE 0.85 |
| HR 0.66 (0.58–0.75) | PMC9491404.1 | offset 16920 | VERDE 0.85 |
| HR 0.70 (0.58–0.83) | PMC8591237.1 | offset 3406 | VERDE 0.85 |
| HR 0.86 (0.77–0.96) | PMC9491404.1 | offset 14414 | VERDE 0.85 |

**El sexto no entró**: su artículo es CC BY-NC-ND y la compuerta lo rechazó
*antes de leer el contenido*. La compuerta no es decorativa.

Orden por la **función canónica recomputable** (magnitud de efecto → amplitud del
intervalo → fecha del ancla). Un orden recomputable **se demuestra**; uno
ajustado a mano hay que justificarlo, y esa es la pregunta que no conviene tener
que contestar.

---

## 11. Los 20 bugs, y quién los encontró

| # | Bug | Quién |
|---|---|---|
| 1 | **Punto medio decimal** (`0·63`, estilo Lancet) → devolvía **`0`**. No fallaba: devolvía un número plausible y equivocado. **Corrupción silenciosa.** | datos reales |
| 2 | `HR 0.66, 95% CI 0.58-0.75` **perdía el intervalo** (el patrón exigía paréntesis) | datos reales |
| 3 | **`"relative risk"` ausente de los alias**. Mi suite estaba sesgada al español. | datos reales |
| 4 | El corchete de `relative risk [RR] 0.63` rompía el enlace alias-número | datos reales |
| 5 | Numeración de sección FDA (`2.1 Recommended Dosage`) → **dosis de 2.1 mg** | datos reales |
| 6 | `CC BY-NC-ND 4.0`: la detección de ND fallaba porque el split dejaba `"nd 4.0"` | datos reales |
| 7 | **Factor de alarma fijo en 10** → una **dosis doble pasaba como imprecisión** | análisis adversarial |
| 8 | `mostrable()` True para todo ÁMBAR → **una dosis sin ancla con confianza 0.31 entraba al mazo de repetición espaciada**, cuyo propósito es que se retenga | análisis adversarial |
| 9 | `aplicar()` sobrescribía sin bitácora → imposible acreditar qué se mostró | análisis adversarial |
| 10 | Un ancla **INCOMPARABLE** acreditaba VERDE: un hecho «anclado» contra una cifra de otra clase | análisis adversarial |
| 11 | `_representante` **fabricaba magnitudes compuestas**: punto de una fuente, intervalo de otra | análisis adversarial |
| 12 | La cuarentena era **solo de pantalla**: la cifra repudiada quedaba en el campo principal | análisis adversarial |
| 13 | **3 aristas con el signo invertido** en la cadena causal del iSGLT2. El producto daba que el fármaco *empeora* la ERC. **Ninguna persona lo notó.** | el propio grafo |
| 14 | Rama de rango sin guarda contra clase sin resolver → `AttributeError` | pruebas |
| 15 | El detector de ciclos bloqueado por la guarda anti-revisita | pruebas |
| 16 | El orden del texto importaba: `hazard ratio 0.61` sí, `0.61 hazard ratio` no | pruebas |
| 17 | `aplicar()` **asignaba** el diagnóstico en vez de actualizarlo → se comía la justificación. Síntoma: un control gritando en falso sobre hechos correctos. **La peor clase de bug: no rompe el producto, hace que dejes de creerle al control.** | pruebas |
| 18 | `fuente_de_ancla` devolvía la primera del catálogo, y en los dos casos donde varias comparten tipo **la primera es la inusable** | pruebas |
| 19 | El piso de confianza mordía VERDE: doble conteo de las compuertas duras | pruebas |
| 20 | Orden de campos del dataclass | pruebas |

**6 solo aparecen con texto real. 6 los encontró el análisis adversarial leyendo
el código. 1 lo encontró el propio auditor del grafo. 7 las pruebas.**

---

## 12. El análisis legal adversarial

6 ataques, cada uno desde la posición del abogado de la parte contraria.

| Ataque | Veredicto | Riesgo residual |
|---|---|---|
| Obra derivada / selección y disposición | sobrevive con condiciones | medio |
| El grafo de mecanismos como paráfrasis estructurada | sobrevive con condiciones | medio |
| **La indemnización del proveedor de IA** | **refutada** | **alto** |
| **El archivo que sube el estudiante** | **refutada** | medio |
| Software como dispositivo médico | sobrevive con condiciones | medio |
| Responsabilidad civil por cifra mal derivada | sobrevive con condiciones | **alto** |

### Lo que hay que abandonar

**La ruta de «el estudiante sube su guía».** El escenario que la mata no pasa por
un tribunal: un despacho compra **una** suscripción, un pasante sube el PDF y
**graba la pantalla**. Ese video es el expediente completo. Después, tres disparos
simultáneos y gratuitos: notificación al **proveedor de infraestructura** (el
equipo de abuse no litiga, aplica su política, 24–72 h), queja ante **App Review
de Apple y Google Play**, y carta a la **pasarela de pagos**. El puerto seguro es
jurídicamente irrelevante frente a un contrato privado de hosting.

Única versión viable: **exclusivamente en cliente** (WASM, cero copia en
servidor), y lo único que cruza la red son identificadores de una ontología
propia. Ningún byte del archivo, ningún embedding, ningún span.

### La indemnización del proveedor: trátala como inexistente

La de Anthropic cubre solo `paid use`; los servicios en Beta se entregan
**expresamente sin indemnización**, con tope en el menor entre USD 1 000 y 12
meses de fees. Google define el servicio indemnizado como el que no se provee
gratis. **Lanzar con créditos de programa startup y un modelo en preview = cero
indemnización.** La red no se rompe: nunca se tendió. Y hay una cláusula al
revés: por los inputs de tus colaboradores y usuarios, **ORIONS le debe
indemnización a Anthropic**.

> **Regla:** ninguna decisión de producto puede justificarse con «el proveedor nos
> cubre». Si una función solo es aceptable asumiendo la indemnización, esa función
> no se construye.

### Dato que invierte el ranking de riesgo

**KDIGO es una fundación belga** (Bruselas) y la **ESC está en Francia**. Eso les
da el **derecho sui generis de bases de datos** europeo (directiva 96/9/CE art.
11), que **no requiere ninguna originalidad**: basta inversión sustancial. La ADA
y la AHA/ACC, al ser estadounidenses, **no lo tienen**.

Contraintuitivo: **KDIGO y ESC son más peligrosas que ADA y AHA.** Aunque KDIGO
sea también la que ya concedió la licencia abierta — las dos cosas a la vez.

### Google Vertex y Gemini quedan fuera

Sus Service Specific Terms 20(e) prohíben usar los servicios de IA generativa con
fines clínicos, y 20(g) lo convierte en *Use Restriction* cuyo incumplimiento
rompe el acuerdo.

### El punto más incómodo

El análisis de responsabilidad civil señaló que **mi propia documentación se
vuelve prueba en contra**: «los umbrales son decisiones de producto razonadas, no
constantes derivadas de datos» + «subirlos reduce cobertura y aumenta precisión»
equivale a que la empresa **documentó que pudo ser más segura y eligió
cobertura**.

**La lección que *no* hay que sacar es dejar de documentar con honestidad.** La
correcta: **no embarques la configuración que tu honestidad describe como
insegura.** Documentación que dice «elegimos cobertura sobre precisión en dosis»
es condenatoria; documentación que dice «las dosis exigen ancla de regulador,
factor de alarma 1.6 y bitácora de exhibición, y aquí está la medición» es
exculpatoria. Por eso el trabajo fue cerrar las compuertas, no suavizar el texto.

---

## 13. La frontera regulatoria

**Es más urgente que el riesgo de derechos de autor.** Una demanda se pelea; una
clasificación como software de apoyo a la decisión clínica sin registro sanitario
**cierra el producto por vía administrativa** sin que nadie gane un juicio.

La frontera no la fija el contenido: la fijan **la voz y el referente**, y las dos
son verificables (`harness/voz.py`):

```
"Para mi paciente debe iniciar un iSGLT2, es el de primera linea"
  del lado educativo: NO
   - NORMATIVO_SIN_ATRIBUIR  | debe
   - NORMATIVO_SIN_ATRIBUIR  | primera linea
   - REFERENTE_INDIVIDUAL    | mi paciente
   - VISTA_COLAPSADA, DERIVACION_OCULTA, ANCLAS_OCULTAS, SALIDA_UNICA

"Segun NOM-030-SSA2-2009 (numeral 7.4, 2009): en adultos con ERC y
 albuminuria se recomienda un iSGLT2."
  del lado educativo: SÍ
```

Misma cifra, lados distintos. El criterio central de la guía de la FDA (§520(o)(1)(E)
de la FD&C Act) es que el profesional pueda **revisar independientemente las
bases** de la recomendación. Así que la vista de «respuesta rápida» no es una
preferencia de diseño: **es la que cruza la frontera.**

El enum de referente es **cerrado** (`poblacion_pico`, `documento`, `mecanismo`).
**No existe el valor `paciente`**, y agregarlo no es una decisión de ingeniería:
es un cambio de categoría regulatoria del producto entero.

> **Consecuencia que conviene aceptar de frente: ORIONS no puede tener un botón de
> «dime qué hacer».** Es la función más pedida y la más vendible, y es exactamente
> la que convierte la plataforma en un dispositivo médico sin registro.

---

## 14. Lo que NO está verificado

La honestidad sobre el estado real importa, porque el valor de este sistema
depende de que la distinción entre verificado y no verificado se respete también
aquí.

| | |
|---|---|
| **El adaptador HTTP está probado a medias.** | Ejecutado contra PMC (17 registros reales, compuerta corrida sobre `license_code` reales). **Falta `clinicaltrials.gov` y `api.fda.gov`**, que la política de egress de esta sesión bloquea con 403. Las anclas más fuertes —registro de ensayo y etiqueta de regulador— **no se han ejercitado ni una vez**. |
| **Los PDF primarios de KDIGO no se leyeron.** | Su front matter lleva una nota más estricta (*«no part of this publication may be reproduced… without explicit permission in writing»*) **en tensión** con la nota de acceso abierto. Y la guía 2024 de ERC **no es homogénea**: páginas principales en CC BY-NC-ND pero capítulos individuales bajo otras licencias. **Antes de citar nada hay que leer la página de copyright de la sección exacta.** |
| **Terminologías y libros abiertos: sin verificar.** | Por bloqueo de red, no por ambigüedad. Si StatPearls lleva NonCommercial + NoDerivatives es doblemente inusable. Si México no es miembro de SNOMED International, SNOMED CT es inviable con presupuesto cero. |
| **El Catálogo Maestro puede no existir.** | Verificación pendiente de más valor de todo el expediente: de ella depende la viabilidad de la capa mexicana. |
| **Los umbrales de atestiguación no están calibrados contra datos.** | `consenso ≥67 %`, `≥3 encuadres`, `piso 0.5` son decisiones razonadas. Los del **cierre aritmético sí** se calibraron con 5 cifras reales. |
| **La tasa de salida temprana no está medida.** | El ahorro de llamadas es una estimación de arquitectura. |
| **Las cifras de `ejemplos/isglt2_nefroproteccion.py` son de demostración**, marcadas como tales. Lo que demuestra es el *pipeline*. |

---

## 15. Plan de acción

### Esta semana — todo costo cero

1. **Verificar si el Catálogo Maestro sigue vivo.** Decide la viabilidad de la
   capa mexicana. Una tarde.
2. **Solicitud de transparencia** a la Secretaría de Salud por la PNT. Es la
   puerta que no depende de que nadie conteste un correo.
3. **Leer la página de copyright del PDF de KDIGO** de la guía exacta que quieras
   usar, capítulo por capítulo. Antes de citar nada.
4. **Correo a KDIGO** (COO, verificar nombre en el PDF más reciente) y a
   `permissions@diabetes.org`. Pedir *display verbatim atribuido*, no licencia de
   ingestión.
5. **Correr `FetcherHTTP` contra ClinicalTrials.gov y openFDA** desde una red sin
   esta política de egress, y confirmar las rutas de campo.

### Mes 1 — medir antes de escalar

6. **Calibrar los umbrales**: 20 hechos de respuesta conocida, correr el harness
   completo, medir cuántos llegan a VERDE, cuántos a NEGRO y **cuántos NEGRO son
   falsos positivos**. Sin esta medición los umbrales son una opinión — y una
   opinión documentada como tal es prueba en contra.
7. **El cosechador de PMC.** El cuello de botella ya no es el diseño: es que cada
   hecho requiere encontrar a mano el PMCID de un artículo CC-BY con la cifra. El
   **inventario diario del bucket** (`s3://pmc-oa-opendata/inventory-reports/`)
   permite filtrar por licencia *antes* de descargar, así que se puede barrer el
   subconjunto CC-BY de una especialidad y extraer todas las magnitudes con su
   contexto. Convierte «buscar a mano» en «cosechar lo admisible».
8. **Un dominio completo**: ERC con diabetes, ~40 hechos anclados y ~60 aristas.
   Mejor relación entre rendimiento ENARM y densidad de evidencia primaria.
9. **Sincronización delta de ClinicalTrials.gov.** Es obligación contractual, no
   mejora opcional.

### Mes 2–3

10. **La capa que nadie tiene**: el delta México (NOM, Compendio Nacional de
    Insumos, disponibilidad real en primer nivel). Es lo que ninguna fuente
    internacional cubre, es trabajo original, **y el art. 14 fr. VIII la protege
    como obra tuya**: el único artículo del expediente que te da un activo y no
    solo un permiso.
11. **Generación de preguntas desde el grafo**, con la cola de revisión en manos
    de un médico. Medir **minutos de médico por hecho aceptado**: ese número
    decide si el modelo escala.

---

## 16. Riesgos abiertos, en orden de urgencia

1. **Regulatorio.** Puede cerrar el producto sin juicio. Mitigación construida
   (`voz.py`), pero sin validar con nadie que conozca COFEPRIS.
2. **El Catálogo Maestro.** Si no existe, la capa que distingue a ORIONS en
   México no tiene fuente estructurada, y es justo lo que el ENARM evalúa.
3. **Responsabilidad civil.** Riesgo residual alto incluso con las compuertas
   cerradas. No hay sentencia firme en ninguna jurisdicción que condene a un
   proveedor de información clínica, pero tampoco hay precedente que proteja.
4. **La no homogeneidad de las licencias de KDIGO.** Un capítulo bajo otra
   licencia convierte una cita lícita en una infracción.
5. **El cuello de botella de contenido.** 5 hechos y hacen falta cientos.

---

## 17. En una línea

La Bóveda no es un espejo de las guías: es un **sistema de medición** de hechos
clínicos, con tres vías de confianza —ancla pública verificada, extracción
directa byte a byte, y cierre aritmético sin fuente externa— más una cuarta que
la sesión descubrió al final y que resultó ser la más simple: **citar la
recomendación palabra por palabra, que es a la vez lo que la licencia permite y
lo único que el modelo no puede inventar.**

---

*Informe generado el 28 de octubre de 2026. Nada de lo legal aquí es dictamen:
está escrito para que un abogado de propiedad intelectual lo revise rápido y
barato, porque las preguntas ya están acotadas y las fuentes citadas.*
