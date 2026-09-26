import type { paths } from './schema'

// Types generated from the backend's OpenAPI schema — never hand-transcribed
// (Consistency Conventions). Regenerate with `npm run generate:api-types`.
export type LoginRequest = paths['/auth/login']['post']['requestBody']['content']['application/json']
export type LoginResponse =
  paths['/auth/login']['post']['responses'][200]['content']['application/json']

interface ErrorEnvelope {
  error: {
    code: string
    message: string
  }
}

export class ApiError extends Error {
  status: number
  code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

const API_BASE = '/api'
const REQUEST_TIMEOUT_MS = 10_000

function isErrorEnvelope(value: unknown): value is ErrorEnvelope {
  return (
    typeof value === 'object' &&
    value !== null &&
    'error' in value &&
    typeof (value as ErrorEnvelope).error?.message === 'string'
  )
}

export async function login(payload: LoginRequest): Promise<LoginResponse> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    })
  } catch (caught) {
    if (caught instanceof DOMException && caught.name === 'TimeoutError') {
      throw new ApiError(0, 'request_timeout', 'O servidor demorou para responder. Tente novamente.')
    }
    throw new ApiError(0, 'network_error', 'Não foi possível conectar ao servidor.')
  }

  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null)
    if (isErrorEnvelope(body)) {
      throw new ApiError(response.status, body.error.code, body.error.message)
    }
    throw new ApiError(response.status, 'unknown_error', 'Não foi possível fazer login agora.')
  }

  return (await response.json()) as LoginResponse
}
