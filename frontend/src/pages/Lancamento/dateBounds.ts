/**
 * Os limites `min`/`max` dos campos de data das telas de lançamento.
 *
 * Espelham a faixa que o backend passou a exigir em
 * `backend/app/presentation/schemas/school_dates.py`: cinco anos para trás,
 * e para frente nada no caso de um fato que já aconteceu (presença, nota,
 * entrega) ou um ano no caso de um prazo de atividade. Sem eles o navegador
 * aceita qualquer ano digitado e o erro só aparece como 422 depois do envio.
 *
 * O backend ancora a faixa em `as_of()`; aqui a âncora é o "hoje" do
 * navegador. Os dois coincidem no deploy real, onde `SINALIZA_DEMO_AS_OF`
 * fica desligado (ver `docker-compose.yml`). O backend continua sendo a
 * autoridade: estes atributos evitam a digitação errada, não substituem a
 * validação.
 */

const PAST_YEARS = 5
const FUTURE_DAYS_FOR_DUE_DATE = 365

function isoDate(value: Date): string {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

/** O piso compartilhado pelos dois tipos de data. */
export function earliestDate(): string {
  const floor = new Date()
  floor.setFullYear(floor.getFullYear() - PAST_YEARS)
  return isoDate(floor)
}

/** O teto de uma data de fato ocorrido: hoje. */
export function latestFactDate(): string {
  return isoDate(new Date())
}

/** O teto de um prazo de atividade: um ano à frente. */
export function latestDueDate(): string {
  const ceiling = new Date()
  ceiling.setDate(ceiling.getDate() + FUTURE_DAYS_FOR_DUE_DATE)
  return isoDate(ceiling)
}
