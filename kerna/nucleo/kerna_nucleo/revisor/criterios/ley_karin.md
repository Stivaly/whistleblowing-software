# Criterios: Ley 21.643 (Ley Karin) y Código del Trabajo (acoso, violencia y protocolos)

Borrador de demostración. Fuente: texto del corpus (Código del Trabajo, arts. 2, 154, 154 bis, 154 ter, 211-A a 211-E;
Ley 21.643, art. 6 y transitorios) y conocimiento jurídico general chileno.

## Ámbito subjetivo y de régimen
- El Código del Trabajo rige las relaciones entre empleadores y trabajadores del sector privado y de empresas del
  Estado. Para funcionarios con estatuto propio (Fuerzas Armadas, Carabineros, personal de la Administración del
  Estado y municipal) rige su estatuto; el Código solo opera si ese estatuto remite a él (conocimiento general, art. 1
  del Código del Trabajo, fuera del corpus).
  - Si los hechos muestran que denunciante y denunciado son funcionarios regidos por estatuto propio y no hay
    remisión al Código: veto regimen_excluye_norma. Si hay duda sobre el régimen: condiciona con ambito_regimen.
  - La Ley 21.643 también modificó estatutos administrativos; esos artículos no están en el corpus: alerta
    fuera_de_corpus:administrativo.
  - Acoso en educación superior (Ley 21.369) y convivencia escolar tienen leyes propias: posible_otra_via.
- Art. 2, inc. 2, letra c): la violencia por terceros ajenos (clientes, proveedores, usuarios) con ocasión de la
  prestación de servicios también está cubierta; el sujeto activo no tiene que ser trabajador.
- Es presupuesto una relación laboral o la prestación de servicios con ocasión del trabajo. Sin ella (conflicto entre
  vecinos, entre clientes): condiciona con ambito_regimen o veta regimen_excluye_norma si los hechos lo muestran.

## Definiciones (art. 2, inc. 2)
- Acoso sexual (letra a): requerimientos sexuales indebidos, no consentidos, que amenacen o perjudiquen la situación
  laboral u oportunidades en el empleo.
- Acoso laboral (letra b): agresión u hostigamiento del empleador o de uno o más trabajadores contra otro u otros,
  "ya sea que se manifieste una sola vez o de manera reiterada", con resultado de menoscabo, maltrato o humillación o
  amenaza o perjuicio de la situación laboral. Un solo acto puede bastar: no vetes por falta de reiteración.
- Discriminación: distinciones, exclusiones o preferencias por motivos enumerados (sexo, edad, sindicación, etc.) que
  alteren la igualdad de oportunidades. No es lo mismo que acoso: si los hechos son solo de trato desigual sin
  hostigamiento, el artículo de acoso condiciona con naturaleza_conducta.

## Procedimiento (arts. 211-A a 211-E, 154 y 154 bis)
- 211-A: el empleador debe adoptar medidas para prevenir, investigar y sancionar, y poner a disposición un protocolo.
  154 y 154 bis: el protocolo y el procedimiento de investigación figuran en el reglamento interno o se informan al
  contratar. Aplican cuando la pregunta es qué debe tener o hacer la empresa.
- 211-B bis: la denuncia se presenta a la empresa o a la Inspección del Trabajo; medidas de resguardo inmediatas.
- 211-C: investigación interna o remisión a la Inspección en tres días; investigación concluida en treinta días,
  por escrito, reservada y oyendo a ambas partes.
- 211-D: puesta en conocimiento de conclusiones. 211-E: medidas o sanciones en quince días; causales del art. 160 N° 1,
  letras b) y f) del Código del Trabajo.
- Estos artículos operan cuando hay una denuncia de acoso, acoso sexual o violencia en el trabajo. Si los hechos son
  de otro tipo, condiciona con procedimiento_aplicable o veta naturaleza_distinta.

## Naturaleza de la conducta (otra vía)
- Despido por necesidades de la empresa (art. 161) o por otra causal sin hechos de acoso: veta naturaleza_distinta
  para los artículos de acoso; alerta fuera_de_corpus:laboral.
- Reclamo de remuneraciones, jornada o prestaciones sin hostigamiento: naturaleza_distinta.
- Conflicto colectivo o sindical (negociación, huelga, fuero): no es acoso individual; condiciona con
  naturaleza_conducta y alerta posible_otra_via, salvo que haya hostigamiento hacia una persona.
- Vulneración de derechos fundamentales con despido (tutela laboral, arts. 485 y siguientes, fuera del corpus):
  alerta fuera_de_corpus:laboral y posible_otra_via; el procedimiento 211-A a 211-E puede coexistir.

## Vigencia
- Ley 21.643, art. primero transitorio: rige desde el primer día del sexto mes siguiente a su publicación (1 de agosto
  de 2024). Art. segundo transitorio: los procesos o investigaciones iniciados antes se rigen por las normas vigentes a
  la fecha de la denuncia.
- Hechos anteriores a esa fecha pueden denunciarse hoy; no vetes por la fecha de los hechos. Veta
  hechos_anteriores_a_vigencia solo si la denuncia indica que el proceso se inició antes del 1 de agosto de 2024. Si no
  hay fecha: condiciona con vigencia solo cuando los hechos mencionen un tiempo lejano.

## Otras normas del corpus de esta familia
- Ley 21.643, art. 6: obligación de reporte de organismos administradores a la Superintendencia de Seguridad Social
  y deber del empleador de proporcionar información. No regula la conducta entre personas: condiciona con
  naturaleza_conducta salvo que los hechos traten de ese reporte.
- Art. 154 ter: reserva de datos privados del trabajador por el empleador. Aplica si los hechos tratan de filtración
  o uso de información privada del trabajador en una relación laboral; sin relación laboral condiciona con
  ambito_regimen. Puede complementarse con la normativa de datos personales.

## Verificación contra el corpus (2026-11-12)
- Ley 21.643, art. primero transitorio: rige "el primer día del sexto mes subsiguiente a su publicación"; el corpus
  no trae la fecha de publicación del Diario Oficial (la versión indica 2024-01-15), así que el 1 de agosto de 2024 es
  conocimiento general no verificado contra el corpus. Por eso el veto por vigencia exige que la denuncia diga que el
  proceso se inició antes de esa fecha.
- Los fragmentos del Código del Trabajo traen `vigencia_desde` 2026-07-23: es la fecha de la versión consolidada, no la
  vigencia de los artículos de la Ley Karin; no debe usarse para vetar.
- Art. 2 inc. 2 letra b): confirmado "ya sea que se manifieste una sola vez o de manera reiterada".
