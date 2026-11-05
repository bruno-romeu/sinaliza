"""Rate limiting de `POST /auth/login`.

Por que existe
--------------
`docs/deferred-work.md` (Story 1.1): o login é a única rota anônima do
sistema e protege a única conta semeada, sem lockout nem backoff — portanto
aberta a adivinhação ilimitada de senha. Além disso o bcrypt (custo 12) faz
de cada tentativa algo caro: sem limite, o próprio login é um amplificador
de carga contra a VM de demonstração.

Por que *só* o login
--------------------
Todas as demais rotas exigem JWT, e o projeto é um TCC com uma conta, dados
sintéticos e uma VM — um limite global não fecha nenhuma exposição real e
arriscaria derrubar a própria demonstração (vários avaliadores atrás do
mesmo NAT compartilhariam uma cota). `AGENTS.md` ("Segurança futura") pede
explicitamente para não implementar security theater.

Por que implementação própria
-----------------------------
Um contador de janela deslizante para uma rota são ~80 linhas. Uma
biblioteca (slowapi/limits) traria dependências novas para o `uv.lock` sem
resolver nada que não esteja aqui, contra a regra do `AGENTS.md` de não
"adicionar tecnologia sem necessidade".

Algoritmo: janela deslizante por log de timestamps
--------------------------------------------------
Guarda os instantes das tentativas recentes por chave. Comparado com janela
fixa, não tem o degrau de fronteira (2x o limite na virada de janela);
comparado com token bucket, não permite rajada inicial — justamente o que
um ataque de adivinhação faz. O volume aqui (uma conta, um operador humano)
torna o custo de memória do log irrelevante.

DEPENDÊNCIA ARQUITETURAL — `--workers 1`
----------------------------------------
O estado é um dicionário em memória do processo. Isso só é correto porque
`backend/Dockerfile` serve com `uvicorn --workers 1` (AD-3: o singleton do
artefato de ML em memória não é seguro entre processos). **Se algum dia o
número de workers aumentar, este limitador passa a contar por processo e o
limite efetivo vira `limite x nº de workers`** — e, pior, silenciosamente.
Nesse momento o contador precisa migrar para um store compartilhado (Redis
ou uma tabela no Postgres que já existe); ver `_SlidingWindowCounter`.

Como o estado reinicia
----------------------
O store vive no processo e começa vazio a cada start da aplicação (ver
`app.main`, que o limpa no lifespan). Em produção isso significa que um
restart zera as janelas — aceitável para o limite ser um freio contra
força bruta, não um lockout persistente. Na suíte de testes, cada
`with TestClient(app)` dispara o mesmo lifespan, então os testes existentes
não acumulam tentativas uns dos outros.
"""

from __future__ import annotations

import math
from collections import OrderedDict, deque
from dataclasses import dataclass
from time import monotonic

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import Settings

#: Única rota protegida (ver docstring do módulo).
LOGIN_PATH = "/auth/login"
LOGIN_METHOD = "POST"

#: Código do envelope de erro `{"error": {"code", "message"}}` —
#: mesmo formato de `app.presentation.errors`. A mensagem é deliberadamente
#: genérica: não menciona e-mail, conta nem existência de usuário.
RATE_LIMITED_CODE = "rate_limited"
RATE_LIMITED_MESSAGE = "Muitas tentativas de login. Aguarde alguns instantes e tente novamente."

#: Teto de chaves distintas rastreadas, para que o dicionário em memória não
#: cresça sem limite. Evicção LRU: na prática só a demonstração escreve aqui.
MAX_TRACKED_KEYS = 1024


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    #: Segundos até a janela liberar a próxima vaga (>= 1).
    reset_seconds: int


class _SlidingWindowCounter:
    """Contador de janela deslizante em memória.

    NÃO É SEGURO ENTRE PROCESSOS. Ver "DEPENDÊNCIA ARQUITETURAL" na
    docstring do módulo antes de aumentar `uvicorn --workers`.
    """

    def __init__(self, max_events: int, window_seconds: int, max_keys: int = MAX_TRACKED_KEYS):
        self._max_events = max_events
        self._window_seconds = window_seconds
        self._max_keys = max_keys
        self._events: OrderedDict[str, deque[float]] = OrderedDict()

    def hit(self, key: str, now: float) -> RateLimitDecision:
        bucket = self._events.get(key)
        if bucket is None:
            bucket = deque()
            self._events[key] = bucket
        self._events.move_to_end(key)

        cutoff = now - self._window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        allowed = len(bucket) < self._max_events
        if allowed:
            bucket.append(now)

        # Quando a vaga mais antiga sai da janela.
        #
        # O `min` com a janela e um invariante, nao um band-aid: o tempo ate
        # a vaga mais antiga sair da janela nunca pode ser maior que a
        # propria janela. Sem ele, `RateLimit-Reset` pode anunciar um valor
        # que o proprio limitador nao honra.
        #
        # Ele foi acrescentado depois de o CI observar
        # `RateLimit-Reset: 121` numa janela de 120s
        # (test_allowed_responses_carry_the_ratelimit_headers), de forma
        # intermitente. A causa raiz NAO foi identificada: o arquivo passa
        # isolado e falha so com a suite inteira; `monotonic()` descarta a
        # hipotese de erro de ponto flutuante (foi medida e refutada, 0 em
        # 2000 instantes), e cada `make_client` monta app e contador
        # proprios, o que descarta estado compartilhado.
        #
        # O clamp e correto independentemente da causa, mas nao a explica --
        # se o sintoma voltar em outro cabecalho, procure antes de supor que
        # esta linha resolveu.
        reset_seconds = (
            min(self._window_seconds, max(1, math.ceil(bucket[0] + self._window_seconds - now)))
            if bucket
            else self._window_seconds
        )

        while len(self._events) > self._max_keys:
            self._events.popitem(last=False)

        return RateLimitDecision(
            allowed=allowed,
            limit=self._max_events,
            remaining=max(0, self._max_events - len(bucket)),
            reset_seconds=reset_seconds,
        )

    def reset(self) -> None:
        self._events.clear()


def client_key(request: Request, trusted_proxy_hops: int) -> str:
    """Identifica o cliente para fins de contagem.

    O backend não publica porta (`docker-compose.yml`): todo request chega
    pelo Nginx, que faz `proxy_set_header X-Forwarded-For
    $proxy_add_x_forwarded_for` — ou seja, *acrescenta* o IP do peer real ao
    final da lista. Logo, com um proxy confiável à frente, a entrada
    **mais à direita** é a única que o cliente não consegue forjar: um
    `X-Forwarded-For: 1.2.3.4` forjado vira `1.2.3.4, <ip real>`. Confiar na
    entrada mais à esquerda (o idioma ingênuo) daria a qualquer um a
    capacidade de escolher a própria chave e zerar o limite a cada request.

    `trusted_proxy_hops` diz quantos proxies confiáveis existem à frente;
    pulamos essa quantidade a partir da direita. Com `0`, o cabeçalho é
    ignorado por completo (backend exposto diretamente). Sem o cabeçalho
    (dev local, `uvicorn` direto), cai no peer da conexão.
    """
    if trusted_proxy_hops > 0:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            hops = [hop.strip() for hop in forwarded_for.split(",") if hop.strip()]
            if hops:
                index = max(0, len(hops) - trusted_proxy_hops)
                return hops[index]

    client = request.client
    return client.host if client else "unknown"


def _rate_limit_headers(decision: RateLimitDecision) -> dict[str, str]:
    """Cabeçalhos `RateLimit-*` no formato de campos separados do draft-07
    do IETF (`draft-ietf-httpapi-ratelimit-headers`), que é o que clientes e
    proxies realmente entendem hoje — o formato de campo único (`RateLimit:
    limit=..., remaining=...`) dos drafts mais recentes ainda não tem
    adoção."""
    return {
        "RateLimit-Limit": str(decision.limit),
        "RateLimit-Remaining": str(decision.remaining),
        "RateLimit-Reset": str(decision.reset_seconds),
    }


class LoginRateLimitMiddleware(BaseHTTPMiddleware):
    """Conta **antes** de despachar o request.

    Duas consequências deliberadas:

    1. A contagem não olha para a resposta, logo não pode se comportar de
       forma diferente para e-mail conhecido e desconhecido. A chave é
       apenas o cliente — nunca o e-mail enviado. Um limite por e-mail
       responderia de formas distintas para conta existente e inexistente,
       criando exatamente o oráculo de enumeração que o 401 genérico de
       `invalid_credentials` existe para evitar.
    2. Um request bloqueado nem chega ao bcrypt, então o limite também
       protege a CPU da VM.
    """

    def __init__(self, app, counter: _SlidingWindowCounter, trusted_proxy_hops: int) -> None:
        super().__init__(app)
        self._counter = counter
        self._trusted_proxy_hops = trusted_proxy_hops

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method != LOGIN_METHOD or request.url.path != LOGIN_PATH:
            return await call_next(request)

        decision = self._counter.hit(client_key(request, self._trusted_proxy_hops), monotonic())
        headers = _rate_limit_headers(decision)

        if not decision.allowed:
            headers["Retry-After"] = str(decision.reset_seconds)
            # Mesmo envelope de `app.presentation.errors._app_error_handler`.
            # Não é levantado como `AppError` porque exception handlers rodam
            # abaixo da camada de middleware e não veriam a exceção.
            return JSONResponse(
                status_code=429,
                content={"error": {"code": RATE_LIMITED_CODE, "message": RATE_LIMITED_MESSAGE}},
                headers=headers,
            )

        response = await call_next(request)
        response.headers.update(headers)
        return response


def install_login_rate_limit(app: FastAPI, settings: Settings) -> None:
    """Instala o limitador e expõe o contador em `app.state` para que o
    lifespan possa zerá-lo no start do processo."""
    counter = _SlidingWindowCounter(
        max_events=settings.rate_limit_login_max_attempts,
        window_seconds=settings.rate_limit_login_window_seconds,
    )
    app.state.login_rate_limit_counter = counter

    if not settings.rate_limit_enabled:
        return

    app.add_middleware(
        LoginRateLimitMiddleware,
        counter=counter,
        trusted_proxy_hops=settings.rate_limit_trusted_proxy_hops,
    )
