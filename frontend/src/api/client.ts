import type { paths } from './schema'

// Types generated from the backend's OpenAPI schema — never hand-transcribed
// (Consistency Conventions). Regenerate with `npm run generate:api-types`.
export type LoginRequest = paths['/auth/login']['post']['requestBody']['content']['application/json']
export type LoginResponse =
  paths['/auth/login']['post']['responses'][200]['content']['application/json']

export type Classroom =
  paths['/classrooms']['get']['responses'][200]['content']['application/json'][number]
export type Student =
  paths['/classrooms/{classroom_id}/students']['get']['responses'][200]['content']['application/json'][number]
export type AttendanceCreateRequest =
  paths['/attendance']['post']['requestBody']['content']['application/json']
export type AttendanceRecord =
  paths['/attendance']['post']['responses'][201]['content']['application/json']

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

interface RequestOptions {
  method: 'GET' | 'POST'
  path: string
  body?: unknown
  token?: string
  fallbackMessage: string
}

async function request<T>({ method, path, body, token, fallbackMessage }: RequestOptions): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers: {
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    })
  } catch (caught) {
    if (caught instanceof DOMException && caught.name === 'TimeoutError') {
      throw new ApiError(0, 'request_timeout', 'O servidor demorou para responder. Tente novamente.')
    }
    throw new ApiError(0, 'network_error', 'Não foi possível conectar ao servidor.')
  }

  if (!response.ok) {
    const errorBody: unknown = await response.json().catch(() => null)
    if (isErrorEnvelope(errorBody)) {
      throw new ApiError(response.status, errorBody.error.code, errorBody.error.message)
    }
    throw new ApiError(response.status, 'unknown_error', fallbackMessage)
  }

  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

export async function login(payload: LoginRequest): Promise<LoginResponse> {
  return request<LoginResponse>({
    method: 'POST',
    path: '/auth/login',
    body: payload,
    fallbackMessage: 'Não foi possível fazer login agora.',
  })
}

export async function listClassrooms(token: string): Promise<Classroom[]> {
  return request<Classroom[]>({
    method: 'GET',
    path: '/classrooms',
    token,
    fallbackMessage: 'Não foi possível carregar as turmas agora.',
  })
}

export async function listEnrolledStudents(token: string, classroomId: string): Promise<Student[]> {
  return request<Student[]>({
    method: 'GET',
    path: `/classrooms/${classroomId}/students`,
    token,
    fallbackMessage: 'Não foi possível carregar os estudantes agora.',
  })
}

export async function registerAttendance(
  token: string,
  payload: AttendanceCreateRequest,
): Promise<AttendanceRecord> {
  return request<AttendanceRecord>({
    method: 'POST',
    path: '/attendance',
    body: payload,
    token,
    fallbackMessage: 'Não foi possível salvar o registro agora.',
  })
}
