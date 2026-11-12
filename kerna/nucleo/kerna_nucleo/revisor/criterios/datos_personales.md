# Criterios: Ley 19.628 reformada por la Ley 21.719 (datos personales)

Borrador de demostración. Fuente: texto del corpus (Ley 19.628 arts. 1 a 30 y siguientes; Ley 21.719, transitorios) y
conocimiento jurídico general chileno.

## Ámbito (arts. 1 y 1 bis)
- Protege datos de personas naturales. Los datos de personas jurídicas no están en el ámbito: naturaleza_distinta si
  solo se trata de información de una empresa.
- Excluye el tratamiento en ejercicio de las libertades de opinar e informar (con la salvedad de los medios que tratan
  datos con otra finalidad) y el que hacen personas naturales en sus actividades personales. Un conflicto entre
  particulares sin tratamiento por un responsable: veta naturaleza_distinta o condiciona con posicion_afectado.
- Art. 1 bis: aplica si el responsable o mandatario están establecidos en Chile, o si ofrecen bienes o servicios a
  titulares en Chile o monitorean su comportamiento. Hechos íntegramente en el extranjero sin responsable ni titular
  en Chile: veta hechos_fuera_de_chile; si hay conexión parcial: condiciona con territorialidad.

## Posición del afectado
- Los derechos y la mayoría de las infracciones se miden desde el titular. Si no hay un titular afectado y quien
  consulta es la empresa que quiere saber cómo tratar datos: condiciona con posicion_afectado.
- Arts. 20 a 26 regulan el tratamiento por órganos públicos. Si el responsable es una empresa privada: condiciona con
  ambito_regimen; si es un órgano público, los arts. 12 a 16 (privados) condicionan igualmente.

## Contenido de los artículos
- Definiciones (art. 2): dato personal, dato sensible (origen racial o étnico, afiliación política, sindical o
  gremial, situación socioeconómica, convicciones, salud, datos biométricos, vida sexual, orientación e identidad de
  género), consentimiento, responsable, titular, tratamiento.
- Principios (art. 3): licitud, finalidad, proporcionalidad, calidad, responsabilidad, seguridad, transparencia,
  confidencialidad.
- Derechos del titular (arts. 4 a 9: acceso, rectificación, supresión, oposición, portabilidad, bloqueo) y su
  procedimiento (arts. 10 y 11): aplican si el titular los ejerció o se le negaron; sin ello, condiciona con
  procedimiento_aplicable.
- Licitud: consentimiento (art. 12), otras fuentes de licitud (art. 13: obligación legal, contrato, interés legítimo,
  defensa de derechos) y datos sensibles (art. 16: consentimiento expreso y excepciones). Si hay tratamiento y los
  hechos no aclaran la base de licitud: condiciona con hechos_insuficientes.
- Deberes del responsable: arts. 14 y 14 ter (información y transparencia), 14 bis (secreto), 14 quáter (diseño),
  14 quinquies (seguridad), 14 sexies (reporte de vulneraciones a la Agencia), 15 y 15 bis (cesión y encargados),
  15 ter (evaluación de impacto). Cubren filtraciones, accesos indebidos y fallas de seguridad.
- Transferencia internacional: arts. 27 a 29. Agencia, fiscalización, infracciones y sanciones: artículos desde el 30.
  Si los hechos no pasan de un reclamo individual, estos artículos de sanción condicionan con procedimiento_aplicable.

## Ponderación de derechos
- Transparencia o acceso a información pública (Ley 20.285, fuera del corpus) frente a datos personales, y libertad de
  expresión frente a honra o vida privada: no hay respuesta binaria. Condiciona con requiere_ponderacion y agrega las
  alertas requiere_ponderacion y fuera_de_corpus:administrativo. No vetes por ponderación.

## Vigencia
- Ley 21.719, art. primero transitorio: las modificaciones a la Ley 19.628 rigen desde el primer día del mes
  vigésimo cuarto posterior a su publicación (1 de diciembre de 2026). El corpus contiene el texto reformado; antes
  de esa fecha rige el texto anterior, que no está en el corpus.
- Por eso no vetes por vigencia en esta familia: condiciona con vigencia y agrega hechos_insuficientes si no hay
  fecha. Veta hechos_anteriores_a_vigencia solo si la denuncia fija una fecha anterior a esa vigencia y los hechos no
  continúan en el tiempo (por ejemplo, un tratamiento que sigue ocurriendo se rige por el texto vigente).

## Relación con el empleo
- Datos privados del trabajador en poder del empleador: también el art. 154 ter del Código del Trabajo (reserva).
  Cámaras, correos y revisión de dispositivos laborales: condiciona con requiere_ponderacion y alerta
  fuera_de_corpus:laboral.

## Verificación contra el corpus (2026-11-12)
- Ley 21.719, art. primero transitorio: las modificaciones a la Ley 19.628 rigen "el día primero del mes vigésimo
  cuarto posterior a la publicación". La ley se publicó el 2024-12-13 (versión del corpus), de modo que el mes 24
  posterior es diciembre de 2026: 2026-12-01. Coincide con `vigencia_desde` de los 87 fragmentos de la Ley 19.628 del
  corpus. Conclusión confirmada: no se veta por vigencia en esta familia; condiciona con vigencia.
- Las normas de la 19.628 que ya rigen hoy no están en el corpus (solo el texto reformado).
