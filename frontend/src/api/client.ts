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

export type AcademicPeriod =
  paths['/academic-periods']['get']['responses'][200]['content']['application/json'][number]
export type GradeCreateRequest =
  paths['/grades']['post']['requestBody']['content']['application/json']
export type Grade = paths['/grades']['post']['responses'][201]['content']['application/json']

export type AssignmentCreateRequest =
  paths['/assignments']['post']['requestBody']['content']['application/json']
export type Assignment =
  paths['/assignments']['post']['responses'][201]['content']['application/json']
export type AssignmentSubmissionCreateRequest =
  paths['/assignment-submissions']['post']['requestBody']['content']['application/json']
export type AssignmentSubmission =
  paths['/assignment-submissions']['post']['responses'][201]['content']['application/json']

export type PedagogicalObservationCreateRequest =
  paths['/pedagogical-observations']['post']['requestBody']['content']['application/json']
export type PedagogicalObservation =
  paths['/pedagogical-observations']['post']['responses'][201]['content']['application/json']

export type Home = paths['/home']['get']['responses'][200]['content']['application/json']
export type RecentChange = Home['recent_changes'][number]
export type StudentSearchResults =
  paths['/home/search']['get']['responses'][200]['content']['application/json']
export type StudentSearchResult = StudentSearchResults['results'][number]

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

/**
 * Invoked whenever the backend rejects a bearer token as stale/invalid
 * (spec-1-1 I/O Matrix, "Stale/invalid bearer token": *frontend clears
 * session, redirects to /login*).
 *
 * This module is plain TypeScript — it cannot call `useAuth()` or
 * `useNavigate()`. So instead of reaching into React from here, `AuthProvider`
 * registers its own `logout` below; clearing the session flips
 * `isAuthenticated` to false and the existing `ProtectedRoute` performs the
 * redirect. One redirect mechanism, not two.
 */
type UnauthorizedHandler = () => void

let unauthorizedHandler: UnauthorizedHandler | null = null

export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  unauthorizedHandler = handler
}

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
      // Gated on `invalid_token` specifically, not on the 401 status: a failed
      // login also answers 401, with code `invalid_credentials`, and that must
      // not clear a session or bounce the user mid-login.
      if (response.status === 401 && errorBody.error.code === 'invalid_token') {
        unauthorizedHandler?.()
      }
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

export async function listAcademicPeriods(token: string): Promise<AcademicPeriod[]> {
  return request<AcademicPeriod[]>({
    method: 'GET',
    path: '/academic-periods',
    token,
    fallbackMessage: 'Não foi possível carregar os períodos letivos agora.',
  })
}

export async function registerGrade(token: string, payload: GradeCreateRequest): Promise<Grade> {
  return request<Grade>({
    method: 'POST',
    path: '/grades',
    body: payload,
    token,
    fallbackMessage: 'Não foi possível salvar a nota agora.',
  })
}

export async function registerAssignment(
  token: string,
  payload: AssignmentCreateRequest,
): Promise<Assignment> {
  return request<Assignment>({
    method: 'POST',
    path: '/assignments',
    body: payload,
    token,
    fallbackMessage: 'Não foi possível cadastrar a atividade agora.',
  })
}

export async function listAssignmentsByClassroom(
  token: string,
  classroomId: string,
): Promise<Assignment[]> {
  return request<Assignment[]>({
    method: 'GET',
    path: `/classrooms/${classroomId}/assignments`,
    token,
    fallbackMessage: 'Não foi possível carregar as atividades agora.',
  })
}

export async function registerAssignmentSubmission(
  token: string,
  payload: AssignmentSubmissionCreateRequest,
): Promise<AssignmentSubmission> {
  return request<AssignmentSubmission>({
    method: 'POST',
    path: '/assignment-submissions',
    body: payload,
    token,
    fallbackMessage: 'Não foi possível salvar o registro agora.',
  })
}

export async function getHome(token: string): Promise<Home> {
  return request<Home>({
    method: 'GET',
    path: '/home',
    token,
    fallbackMessage: 'Não foi possível carregar os dados agora.',
  })
}

export async function searchStudents(token: string, query: string): Promise<StudentSearchResults> {
  return request<StudentSearchResults>({
    method: 'GET',
    path: `/home/search?q=${encodeURIComponent(query)}`,
    token,
    fallbackMessage: 'Não foi possível buscar estudantes agora.',
  })
}

export async function registerPedagogicalObservation(
  token: string,
  payload: PedagogicalObservationCreateRequest,
): Promise<PedagogicalObservation> {
  return request<PedagogicalObservation>({
    method: 'POST',
    path: '/pedagogical-observations',
    body: payload,
    token,
    fallbackMessage: 'Não foi possível salvar a observação agora.',
  })
}
