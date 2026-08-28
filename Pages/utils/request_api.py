from typing import Any, Dict, List, Literal, Optional, Union
import requests
import streamlit as st
from settings import API_URL


class ApiRequestError(Exception):
    def __init__(self, message: str, status_code: int | None = None, contexto: str = "na API", payload: dict | None = None):
        self.message = message
        self.status_code = status_code
        self.contexto = contexto
        self.payload = payload or {}
        super().__init__(message)

# ==============================================================================
# UTILITÁRIOS E HELPERS INTERNOS
# ==============================================================================
def _get_headers(extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Recupera o token da sessão e monta os cabeçalhos padrão da requisição."""
    token = st.session_state.get("token")
    if not token:
        raise Exception("🔑 Token expirado ou inválido. Faça o login novamente.")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)
    return headers


def _tratar_erro_resposta(response: requests.Response, contexto: str = "na API") -> None:
    try:
        payload = response.json()
    except Exception:
        payload = {}

    detalhe = payload.get("detail", payload) if isinstance(payload, dict) else payload

    def _formatar_detalhe_erro(item: Any) -> str:
        if not isinstance(item, dict):
            return str(item)

        loc = item.get("loc")
        msg = item.get("msg") or item.get("message") or "Erro de validação"
        tipo = item.get("type")

        loc_texto = " > ".join(str(part) for part in loc) if isinstance(loc, list) and loc else ""

        if msg.lower() == "field required" and loc_texto:
            return f"Campo obrigatório ausente em '{loc_texto}'."

        if loc_texto and tipo:
            return f"[{tipo}] {loc_texto}: {msg}"
        if loc_texto:
            return f"{loc_texto}: {msg}"
        if tipo:
            return f"[{tipo}] {msg}"
        return msg

    if isinstance(detalhe, list):
        mensagens = [_formatar_detalhe_erro(item) for item in detalhe]
        mensagem = "; ".join(m for m in mensagens if m)
    elif isinstance(detalhe, dict):
        mensagem = detalhe.get("message") or detalhe.get("detail") or str(detalhe)
    elif isinstance(detalhe, str):
        mensagem = detalhe
    else:
        mensagem = str(detalhe) if detalhe is not None else f"Erro HTTP {response.status_code}"

    mensagem_final = f"Erro {contexto} ({response.status_code}): {mensagem}"

    raise ApiRequestError(
        status_code=response.status_code,
        message=mensagem_final,
        contexto=contexto,
        payload=payload,
    )


def _ativar_monitoramento_backend( chaves_update: Optional[List[str]] = None, ) -> None:
    """
    Ativa a flag no session_state para iniciar o polling na sidebar
    e acumula as chaves de cache que devem ser expurgadas da UI após o cálculo.
    """
    st.session_state["motor_em_andamento"] = True

    if "lista_para_update" not in st.session_state:
        st.session_state["lista_para_update"] = []

    chaves_padrao = [
        "page_movimentacao.ultimo_carregar_tudo",
        "page_movimentacao.ultimo_ativo_carregado",
        "page_movimentacao.ordens_pendentes",
        "page_eventos.ultimo_carregar_tudo",
        "page_eventos.ultimo_ativo_carregado",
        "dados_carteira_cache"
    ]
    chaves_finais = chaves_update if chaves_update is not None else chaves_padrao

    for chave in chaves_finais:
        if chave not in st.session_state["lista_para_update"]:
            st.session_state["lista_para_update"].append(chave)


def _request( method: str, endpoint: str, params: Optional[Dict[str, Any]] = None, payload: Optional[Dict[str, Any]] = None, timeout: int = 15, ) -> requests.Response:
    """Wrapper central para disparo de requisições HTTP."""
    url = f"{API_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    headers = _get_headers()

    try:
        response = requests.request(
            method=method,
            url=url,
            params=params,
            json=payload,
            headers=headers,
            timeout=timeout,
        )
        return response
    except requests.exceptions.RequestException as e:
        raise ApiRequestError(
            message=f"Falha na comunicação com o backend em {API_URL}: {str(e)}",
            status_code=None,
            contexto="na comunicação com a API", )


# ==============================================================================
# AUTENTICAÇÃO
# ==============================================================================
def autenticar_usuario_api(username: str, password: str) -> dict:
    """Realiza o login via OAuth2/Form e retorna o payload com o access_token."""
    url = f"{API_URL.rstrip('/')}/auth/token"
    # Autenticação OAuth2 no FastAPI normalmente envia form-data em vez de JSON
    try:
        response = requests.post( url, data={"username": username, "password": password}, timeout=10)
    except requests.exceptions.RequestException as e:
        raise ApiRequestError(
            message=f"Falha na comunicação com o backend em {API_URL}: {str(e)}",
            status_code=None,
            contexto="na Autenticação",
        )

    if response.status_code == 200:
        return response.json()
    
    _tratar_erro_resposta(response, contexto="na Autenticação")


def obter_perfil_usuario_api() -> dict:
    """Obtém os dados do perfil do usuário logado (GET usuarios/)."""
    response = _request("GET", "usuarios/", timeout=10)

    if response.status_code == 200:
        return response.json()

    _tratar_erro_resposta(response, contexto="ao Obter Perfil")
    
# ==============================================================================
# MONITORAMENTO E STATUS (SIDEBAR)
# ==============================================================================
def checar_status_processamento_api(user_id: int) -> bool:
    """
    Consultado periodicamente pelo fragmento da sidebar (@st.fragment).
    Retorna True se o backend ainda estiver calculando posições contábeis.
    
    :raises ApiRequestError: Se a API retornar erro (3xx, 4xx, 5xx)
    :raises Exception: Se houver falha na comunicação com o backend
    """
    response = _request( "GET",  f"comandos_api/check_status_processamento/{user_id}", timeout=5)
    
    if response.status_code == 200:
        return response.json().get("calculando", False)
    elif response.status_code == 503:
        # 503 Service Unavailable - Backend ainda inicializando ou sobrecarregado
        raise ApiRequestError(
            message="Backend indisponível ou sobrecarregado. Tente novamente em alguns segundos.",
            status_code=response.status_code,
            contexto="ao verificar status do motor de cálculo",
        )
    
    # Qualquer outro erro (4xx, 5xx) será tratado por _tratar_erro_resposta
    _tratar_erro_resposta(response, contexto="ao verificar status do motor de cálculo")


# ==============================================================================
# REQUISIÇÕES DE MOVIMENTAÇÕES E ORDENS
# ==============================================================================
def executar_requisicao_edit_movimentacoes( mov_id: str, payload: dict ) -> bool:
    """Envia a requisição de edição de evento para o backend FastAPI."""
    response = _request("PUT", f"movimentacoes/editar/{mov_id}", payload=payload)

    if response.status_code == 200:
        _ativar_monitoramento_backend()
        return True

    _tratar_erro_resposta(response, contexto="ao Editar Movimentação")


def executar_requisicao_insert_ordens(payload: dict, modo_insert: Literal["TABELA", "MANUAL"] = "TABELA") -> bool:
    """Envia um pacote de ordens (manual ou via tabela) para a API.

    :param modo_insert: Origem dos dados ("TABELA" para importação via planilha, "MANUAL" para inserção manual).
    """
    response = _request("POST", "movimentacoes/insert_ordem", payload=payload, params={"modo_insert": modo_insert})

    if response.status_code in (200, 201):
        _ativar_monitoramento_backend()
        return True

    _tratar_erro_resposta(response, contexto="ao Inserir Ordens")
    

def executar_requisicao_insert_evento( payload: dict,  user_id: Optional[int] = None ) -> bool:
    """ Envia um novo evento personalizado (manual) para a API FastAPI.
    
    :param payload: Dicionário contendo os dados do evento (tipo, ativos, datas, instrucoes, modo_insert).
    :param user_id: ID opcional do usuário alvo (utilizado por administradores).
    :return: True em caso de sucesso na gravação.
    """
    # Suporte a envio de user_id via Query String para administradores
    params = {"user_id": user_id} if user_id is not None else None

    # Chamada HTTP POST para a rota de inserção de eventos
    response = _request( "POST",  "movimentacoes/insert_evento",  payload=payload,  params=params )

    # Status 200/201 indica gravação bem-sucedida e disparo do motor contábil em background
    if response.status_code in (200, 201):
        _ativar_monitoramento_backend()
        return True

    # Tratamento de erros centralizado caso o status não seja de sucesso
    _tratar_erro_resposta(response, contexto="ao Inserir Evento Personalizado")


def buscar_movimentacoes_api(ativo_id: Optional[str] = None) -> list:
    """Consome a rota GET de movimentações, filtrando opcionalmente por ativo_id."""
    params = {"ativo_id": ativo_id} if ativo_id else None
    response = _request("GET", "movimentacoes/listar", params=params)

    if response.status_code == 200:
        return response.json()
    elif response.status_code == 404:
        return []

    _tratar_erro_resposta(response, contexto="ao Listar Movimentações")


def listar_eventos_api(ativo_id: Optional[str] = None, apenas_aceitos: bool = False,
    user_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """ Consome a rota GET para listar eventos personalizados e corporativos.

    :param ativo_id: Ticker do ativo para filtragem no ativo base ou gerado (opcional).
    :param apenas_aceitos: Se True, filtra apenas os eventos ativos/aceitos (padrão: False).
    :param user_id: ID do usuário alvo (opcional - exclusivo para Administradores).
    :return: Lista de dicionários contendo a estrutura dos eventos.
    """
    #  Montagem dinâmica dos parâmetros de consulta da URL (Query Params)
    params: Dict[str, Any] = {
        "apenas_aceitos": str(apenas_aceitos).lower()
    }

    if ativo_id:
        params["ativo_id"] = ativo_id
    if user_id is not None:
        params["user_id"] = user_id

    # Disparo da requisição GET para o endpoint de listagem
    response = _request(
        method="GET",
        endpoint="movimentacoes/listar_eventos",
        params=params
    )

    if response.status_code == 200:
        return response.json()
    elif response.status_code == 404:
        return []

    # Tratamento padronizado de erro para HTTP 403, 500, etc.
    _tratar_erro_resposta(response, contexto="ao Listar Eventos")


def buscar_ordens_pendentes_api(user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Consome a rota GET de ordens pendentes, permitindo filtrar por user_id (exclusivo para Admins)."""
    params = {"user_id": user_id} if user_id else None
    
    response = _request("GET", "movimentacoes/listar_ordens_pendentes", params=params)

    if response.status_code == 200:
        return response.json()
    elif response.status_code == 404:
        return []

    _tratar_erro_resposta(response, contexto="ao Listar Ordens Pendentes")
    return []


def listar_ordens_input_api(user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Consome a rota GET de ordens pendentes, permitindo filtrar por user_id (exclusivo para Admins)."""
    params = {"user_id": user_id} if user_id else None
    
    response = _request("GET", "movimentacoes/listar_ordens_input", params=params)

    if response.status_code == 200:
        return response.json()
    elif response.status_code == 404:
        return []

    _tratar_erro_resposta(response, contexto="ao Listar Ordens Input")
    return []


def obter_detalhe_movimentacao_api(movimentacao_id: str) -> dict:
    """Consome a rota GET de detalhes agregados de uma movimentação."""
    response = _request("GET", f"movimentacoes/dados_origem/{movimentacao_id}")

    if response.status_code == 200:
        return response.json()
    elif response.status_code == 404:
        raise Exception("❌ Movimentação não encontrada no banco de dados.")
    elif response.status_code == 403:
        raise Exception(
            "🚫 Acesso negado: Você não tem permissão para visualizar este registro."
        )

    _tratar_erro_resposta(response, contexto="ao Obter Detalhes")


def executar_requisicao_deletar_movimentacoes_lote(ids_para_enviar: list, recalcular: bool) -> bool:
    """Dispara uma lista de UUIDs para exclusão em lote na API."""
    
    params = {"recalcular": str(recalcular).lower()}
    payload = {"ids": ids_para_enviar}

    response = _request(
        "DELETE",
        "movimentacoes/deletar_lote",
        params=params,
        payload=payload,
        timeout=15,
    )

    if response.status_code in (200, 204):
        _ativar_monitoramento_backend()
        return True

    _tratar_erro_resposta(response, contexto="na Exclusão em Lote")


def executar_requisicao_editar_evento( id_evento: str, payload: dict, user_id: Optional[int] = None ) -> bool:
    """ Envia a requisição de edição/clonagem de um evento para a API FastAPI.
    
    :param id_evento: UUID do evento a ser editado.
    :param payload: Dicionário contendo os dados alterados (tipo, ativos, datas, instrucoes).
    :param user_id: ID opcional do usuário alvo (Apenas para Administradores).
    :return: True em caso de sucesso na atualização.
    """
    #  Suporte a envio de user_id via Query String para administradores
    params = {"user_id": user_id} if user_id is not None else None

    # Chamada HTTP PUT para a rota de edição de evento
    response = _request(
        method="PUT",
        endpoint=f"movimentacoes/editar_evento/{id_evento}",
        payload=payload,
        params=params
    )

    # Aciona o monitoramento e limpa o cache em caso de sucesso
    if response.status_code == 200:
        _ativar_monitoramento_backend()
        return True

    _tratar_erro_resposta(response, contexto="ao Editar Evento Direto")


def executar_requisicao_alterar_status_evento(id_evento: str, aceito: bool, user_id: Optional[int] = None) -> bool:
    """Altera exclusivamente a flag 'aceito' (ativo/inativo) de um evento.
    
    :param id_evento: UUID do evento que terá o status alterado.
    :param aceito: True para reativar o evento ou False para inativar e desvincular movimentações.
    :param user_id: ID opcional do usuário alvo (Apenas para Administradores).
    :return: True em caso de sucesso na alteração do status.
    """
    # Montagem dos parâmetros de query contendo o booleano e user_id se aplicável
    params: Dict[str, Any] = {"aceito": str(aceito).lower()}
    if user_id is not None:
        params["user_id"] = user_id

    # Chamada HTTP PATCH para a rota dedicada de status
    response = _request(
        method="PATCH",
        endpoint=f"movimentacoes/eventos/{id_evento}/status",
        params=params
    )

    if response.status_code == 200:
        _ativar_monitoramento_backend()
        return True

    _tratar_erro_resposta(response, contexto="ao Alterar Status do Evento")


def executar_requisicao_deletar_eventos_lote(ids_eventos: List[str], recalcular: bool = False,
    user_id: Optional[int] = None ) -> bool:
    """🛠️ Envia uma lista de UUIDs para exclusão física ou inativação em lote de eventos.
    
    :param ids_eventos: Lista de UUIDs dos eventos a serem processados.
    :param recalcular: Se True, deleta fisicamente. Se False, apenas inativa (aceito=False).
    :param user_id: ID opcional do usuário alvo (Apenas para Administradores).
    :return: True em caso de sucesso no processamento em lote.
    """
    # Montagem de query params com flag de comportamento e user_id
    params: Dict[str, Any] = {"recalcular": str(recalcular).lower()}
    if user_id is not None:
        params["user_id"] = user_id

    # Payload no formato aceito pelo Pydantic Schema (DeleteEventosRequest)
    payload = {"ids": ids_eventos}

    # Chamada HTTP DELETE para a rota de exclusão em lote
    response = _request(
        method="DELETE",
        endpoint="movimentacoes/deletar_eventos_lote",
        params=params,
        payload=payload,
        timeout=15
    )

    if response.status_code in (200, 204):
        _ativar_monitoramento_backend()
        return True

    _tratar_erro_resposta(response, contexto="ao Deletar Lote de Eventos")


# ====================================================================
# REQUISICOES PARA DIVIDENDOS DO USUARIO
# ====================================================================
def listar_dividendos_usuario_api(
                                    ativo_id: Optional[str] = None,
                                    apenas_aceitos: bool = False,
                                    sem_data_corte: bool = False,
                                    user_id: Optional[int] = None,
                                ) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {}
    if ativo_id:
        params["ativo_id"] = ativo_id
    if apenas_aceitos:
        params["apenas_aceitos"] = str(apenas_aceitos).lower()
    if sem_data_corte:
        params["sem_data_corte"] = str(sem_data_corte).lower()
    if user_id is not None:
        params["user_id"] = user_id

    response = _request("GET", "dividendos_usuarios/pegar_dividendos", params=params or None)

    if response.status_code in (200, 204, 404):
        return response.json() if response.status_code == 200 else []

    _tratar_erro_resposta(response, contexto="ao Listar Dividendos")


def obter_dividendo_usuario_por_id_api(dividendo_id: int) -> Dict[str, Any]:
    """Consome a rota GET /dividendos_usuarios/{id} para buscar os detalhes de um provento específico.

    :param dividendo_id: ID do registro de dividendo no banco de dados.
    :return: Dicionário contendo os detalhes do dividendo.
    """
    # Requisição GET para o endpoint com parâmetro de rota
    response = _request("GET", f"dividendos_usuarios/id/{dividendo_id}")

    if response.status_code == 200:
        return response.json()
    elif response.status_code == 404:
        raise ApiRequestError(
            message=f"Dividendo com ID {dividendo_id} não foi encontrado.",
            status_code=404,
            contexto="ao Obter Dividendo Usuario por ID",
        )

    # Exceção padronizada para outros status HTTP
    _tratar_erro_resposta(response, contexto="ao Obter Dividendo Usuario por ID")


def obter_dividendos_usuario_agregados_api( periodo_opcao: str = "12M",
                                    agrupar_por: str = 'DATA_PAG',
                                    data_inicio: Optional[str] = None,
                                    data_fim: Optional[str] = None,
                                    apenas_aceitos: bool = True,
                                    user_id: Optional[int] = None,
                                ) -> List[dict]:
    """Obtém os proventos consolidados agrupados por Mês e por Ativo."""
    params: Dict[str, Any] = {
        "periodo_opcao": periodo_opcao,
        "apenas_aceitos": apenas_aceitos,
        "agrupar_por": agrupar_por,
    }
    if periodo_opcao == "CUSTOM":
        if data_inicio:
            params["data_inicio"] = data_inicio
        if data_fim:
            params["data_fim"] = data_fim

    if user_id is not None:
        params["user_id"] = user_id

    response = _request("GET", "dividendos_usuarios/obter_dividendos_agregados", params=params, timeout=20)

    if response.status_code == 200:
        return response.json()

    _tratar_erro_resposta(response, contexto="ao Obter Dividendos Agregados")


def inserir_dividendo_usuario_api( payload: Dict[str, Any], modo_insert: Literal["TABELA", "MANUAL"] = "TABELA",
                                    user_id: Optional[int] = None,
                                ) -> bool:
    """Envia um pacote de dividendos (manual ou via tabela) para a API.

    :param modo_insert: Origem dos dados ("TABELA" para importação via planilha, "MANUAL" para inserção manual).
    :param user_id: ID opcional do usuário alvo (Apenas para admins).
    """
    params: Dict[str, Any] = {"modo_insert": modo_insert}
    if user_id is not None:
        params["user_id"] = user_id

    response = _request("POST", "dividendos_usuarios/inserir_dividendos_tabela", payload=payload, params=params)

    if response.status_code in (200, 201):
        _ativar_monitoramento_backend()
        return True

    _tratar_erro_resposta(response, contexto="ao Inserir Dividendos")


def editar_dividendo_usuario_api(dividendo_id: Any, payload: Dict[str, Any], user_id: Optional[int] = None) -> bool:
    params = {"user_id": user_id} if user_id is not None else None
    response = _request("PUT", f"dividendos_usuarios/edit_dividendo/{dividendo_id}", params=params, payload=payload)

    if response.status_code == 200:
        return True

    _tratar_erro_resposta(response, contexto="ao Editar Dividendo")


def alterar_status_dividendo_usuario_api(ids: List[str], user_id: Optional[int] = None) -> bool:
    """Consome a rota PATCH /dividendos_usuarios/edit_aceito_lote para alternar o status 'aceito' em lote.

    :param ids: Lista de IDs dos dividendos a terem o status alterado.
    :param user_id: ID do usuário alvo (opcional para admin).
    :return: True em caso de alteração bem-sucedida.
    """
    if not ids:
        return False

    params = {"user_id": user_id} if user_id is not None else None
        
    #  Requisição PATCH enviando o payload JSON correto
    response = _request("PATCH", "dividendos_usuarios/edit_aceito_lote", payload={"ids": ids}, params=params)

    if response.status_code in (200, 204):
        # Ativa monitoramento para reprocessamento na UI após a alteração
        _ativar_monitoramento_backend()
        datail = response.json()
        st.session_state["toast_pendente"] = {"mensagem": f"✅ Status de aceito atualizado em {datail['total_afetados']} registros.", "icone": "🔄"}
        if datail.get('ids_nao_encontrados'):
            st.session_state['erro_pendente'] = {"mensagem": f"⚠️ IDs não encontrados: {', '.join(datail['ids_nao_encontrados'])}"}

        return True
    # Tratamento em caso de falha na alteração
    _tratar_erro_resposta(response, contexto="ao Alternar Aceite de Dividendos em Lote")
    return False


def excluir_dividendos_usuarios_em_lote_api(dividendo_id: Any, user_id: Optional[int] = None) -> bool:

    ids = [dividendo_id] if not isinstance(dividendo_id, (list, tuple, set)) else list(dividendo_id)
    params = {"user_id": user_id} if user_id is not None else None
    response = _request( "DELETE",
                        "dividendos_usuarios/delete_lote",
                        params=params,
                        payload={"ids": ids},
                    )

    if response.status_code in (200, 204):
        return True

    _tratar_erro_resposta(response, contexto="ao Excluir Dividendo")


# ==============================================================================
# REQUISIÇÕES DE DIVIDENDOS (MERCADO / GLOBAL)
# ==============================================================================

def listar_dividendos_global_api(
                                    ativo_id: Optional[str] = None,
                                    data_inicio: Optional[str] = None,
                                    data_fim: Optional[str] = None,
                                    limite: Optional[int] = None,
                                ) -> List[Dict[str, Any]]:
    """Consome a rota GET /dividendos/ para listar proventos globais cadastrados no sistema.

    Permite filtrar por ativo, intervalo de datas e limite de registros.

    :param ativo_id: Ticker do ativo (ex: 'PETR4', 'VALE3') (opcional).
    :param data_inicio: Data inicial de pagamento ou corte (AAAA-MM-DD) (opcional).
    :param data_fim: Data final de pagamento ou corte (AAAA-MM-DD) (opcional).
    :param limite: Quantidade máxima de registros a retornar (opcional).
    :return: Lista de dicionários contendo os dividendos globais.
    """
    params: Dict[str, Any] = {}
    
    if ativo_id:
        params["ativo_id"] = ativo_id.strip().upper()
    if data_inicio:
        params["data_inicio"] = data_inicio
    if data_fim:
        params["data_fim"] = data_fim
    if limite is not None:
        params["limite"] = limite

    # Chamada centralizada com tratamento de query params
    response = _request("GET", "dividendos/pegar_dividendos", params=params or None)

    if response.status_code == 200:
        return response.json()
    elif response.status_code in (204, 404):
        return []

    # Exceção padronizada em caso de erro
    _tratar_erro_resposta(response, contexto="ao Listar Dividendos Globais")


def obter_dividendo_global_por_id_api(dividendo_id: int) -> Dict[str, Any]:
    """Consome a rota GET /dividendos/{id} para buscar os detalhes de um provento específico.

    :param dividendo_id: ID do registro de dividendo no banco de dados.
    :return: Dicionário contendo os detalhes do dividendo.
    """
    # Requisição GET para o endpoint com parâmetro de rota
    response = _request("GET", f"dividendos/id/{dividendo_id}")

    if response.status_code == 200:
        return response.json()
    elif response.status_code == 404:
        raise ApiRequestError(
            message=f"Dividendo com ID {dividendo_id} não foi encontrado.",
            status_code=404,
            contexto="ao Obter Dividendo Global por ID",
        )

    # Exceção padronizada para outros status HTTP
    _tratar_erro_resposta(response, contexto="ao Obter Dividendo Global por ID")


def atualizar_dividendo_global_api(dividendo_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Consome a rota PUT /dividendos/edit_dividendo/{id} para atualizar os dados de um provento cadastrado.

    :param dividendo_id: ID do dividendo a ser editado.
    :param payload: Dicionário contendo os campos atualizados.
    :return: Dicionário contendo o dividendo atualizado.
    """
    # Chamada HTTP PUT para alteração do registro
    response = _request("PUT", f"dividendos/edit_dividendo/{dividendo_id}", payload=payload)

    if response.status_code == 200:
        # Expurga cache e avisa a UI sobre mudança
        _ativar_monitoramento_backend()
        return response.json()

    # Trata falhas de permissão ou erros de payload
    _tratar_erro_resposta(response, contexto="ao Atualizar Dividendo Global")


def auditar_dividendos_globais_em_lote_api(ids: List[int]) -> bool:
    """Consome a rota PATCH /dividendos/audit_dividendo_lote para alternar o status de auditoria em lote.

    :param ids: Lista com os IDs dos dividendos a serem auditados.
    :return: True em caso de auditoria com sucesso.
    """
    if not ids:
        return False

    # Requisição PATCH enviando o JSON no corpo da requisição
    response = _request("PATCH", "dividendos/audit_dividendo_lote", payload={"ids": ids})

    if response.status_code in (200, 204):
        # Ativa monitoramento para reprocessamento na UI após a alteração
        _ativar_monitoramento_backend()
        datail = response.json()
        st.session_state["toast_pendente"] = {"mensagem": f"✅ Status de auditoria atualizado em {datail['total_afetados']} registros.", "icone": "🔄"}
        if datail.get('ids_nao_encontrados'):
            st.session_state['erro_pendente'] = {"mensagem": f"⚠️ IDs não encontrados: {', '.join(datail['ids_nao_encontrados'])}"}
        return True

    # Tratamento em caso de falha na auditoria
    _tratar_erro_resposta(response, contexto="ao Auditar Dividendos Globais em Lote")
    return False


def alternar_conflito_dividendos_globais_em_lote_api(ids: List[int]) -> bool:
    """Consome a rota PATCH /dividendos/alternar_conflito_lote para alternar o status de conflito em lote.

    :param ids: Lista com os IDs dos dividendos a terem o status de conflito alternado.
    :return: True em caso de alteração bem-sucedida.
    """
    if not ids:
        return False

    # Requisição PATCH enviando o JSON no corpo da requisição
    response = _request("PATCH", "dividendos/alternar_conflito_lote", payload={"ids": ids})

    if response.status_code in (200, 204):
        # Ativa monitoramento para reprocessamento na UI após a alteração
        _ativar_monitoramento_backend()
        datail = response.json()
        st.session_state["toast_pendente"] = {"mensagem": f"✅ Status de conflito atualizado em {datail['total_afetados']} registros.", "icone": "🔄"}
        if datail.get('ids_nao_encontrados'):
            st.session_state['erro_pendente'] = {"mensagem": f"⚠️ IDs não encontrados: {', '.join(datail['ids_nao_encontrados'])}"}
        return True

    # Tratamento em caso de falha na alteração de conflito
    _tratar_erro_resposta(response, contexto="ao Alternar Conflito de Dividendos Globais em Lote")
    return False


def excluir_dividendos_globais_em_lote_api(ids: List[int]) -> bool:
    """Consome a rota DELETE /dividendos/delete_lote para excluir proventos em lote do cadastro geral.

    :param ids: Lista com os IDs dos dividendos a serem excluídos.
    :return: True em caso de remoção com sucesso.
    """
    if not ids:
        return False

    # Requisição DELETE com payload no corpo da mensagem
    response = _request("DELETE", "dividendos/delete_lote", payload={"ids": ids},)

    if response.status_code in (200, 204):
        # Ativa monitoramento para reprocessamento na UI após a deleção
        _ativar_monitoramento_backend()
        return True

    # Tratamento em caso de falha na remoção
    _tratar_erro_resposta(response, contexto="ao Excluir Dividendos Globais em Lote")
    return False


def inserir_pacote_dividendos_global_api(payload: Dict[str, Any], modo_insert: Literal["TABELA", "MANUAL"] = "TABELA",) -> Dict[str, Any]:
    """Consome a rota POST /dividendos/inserir_dividendos_tabela para inserção em lote de dividendos globais.

     Útil para rotinas de scraping ou carga de histórico.

    :param payload: Dicionário contendo a lista/pacote de dividendos.
    :return: Dicionário com o resumo da inserção (quantidade inserida, mensagens, etc.).
    """
    # Timeout estendido para inserção pesada em lote
    response = _request("POST", "dividendos/inserir_dividendos_tabela/", payload=payload, timeout=60, params={"modo_insert": modo_insert})

    if response.status_code in (200, 201):
        # Notifica a UI e limpa cache de carteira/eventos
        _ativar_monitoramento_backend()
        return response.json()

    # Tratamento de erros no lote
    _tratar_erro_resposta(response, contexto="ao Inserir Pacote de Dividendos")


# ====================================================================
# REQUISIÇÕES PARA EVENTOS CORPORATIVOS (API 'eventoscorporativos')
# ====================================================================
def executar_requisicao_simular_evento(payload: dict, user_id: Optional[int] = None) -> list:
    """Dispara os dados para a rota de simulação contábil."""
    params = {"user_id": user_id} if user_id is not None else None
    response = _request("POST", "eventoscorporativos/simular", params=params, payload=payload)

    if response.status_code == 200:
        return response.json()

    _tratar_erro_resposta(response, contexto="na Simulação")


def executar_requisicao_listar_eventos_corporativos(
    ativo_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Lista eventos corporativos registrados no backend.

    :param ativo_id: Filtra pelo ID do ativo base (opcional).
    :return: Lista de dicionários com os eventos.
    """
    params: Dict[str, Any] = {}
    if ativo_id:
        params["ativo_id"] = ativo_id

    response = _request("GET", "eventoscorporativos/", params=params or None)

    if response.status_code == 200:
        return response.json()
    elif response.status_code == 404:
        return []

    _tratar_erro_resposta(response, contexto="ao Listar Eventos Corporativos")


def executar_requisicao_pesquisar_eventos_corporativos(ativo: str) -> List[Dict[str, Any]]:
    """Pesquisa eventos corporativos pelo ativo base ou ativo gerado.

    A rota é restrita a administradores no backend, que valida o usuário atual.
    """
    termo = ativo.strip().upper() if ativo else ""
    if not termo:
        return []

    response = _request("GET", f"eventoscorporativos/pesquisa/{termo}")

    if response.status_code == 200:
        return response.json()
    elif response.status_code == 404:
        return []

    _tratar_erro_resposta(response, contexto="ao Pesquisar Eventos Corporativos")


def executar_requisicao_obter_evento_corporativo(evento_id: int) -> Dict[str, Any]:
    """Obtém os detalhes de um evento corporativo pelo ID."""
    response = _request("GET", f"eventoscorporativos/{evento_id}")

    if response.status_code == 200:
        return response.json()
    elif response.status_code == 404:
        raise Exception(f"Evento corporativo com ID {evento_id} não encontrado.")

    _tratar_erro_resposta(response, contexto="ao Obter Evento Corporativo")


def executar_requisicao_inserir_pacote_eventos_corporativos(payload: dict) -> Dict[str, Any]:
    """Envia um pacote de eventos corporativos para inserção em lote.

    :param payload: Dicionário conforme PacoteEventosCorporativosRequest.
    :return: Dicionário com mensagem e total inserido (conforme API).
    """
    # pacote pode demorar um pouco -> timeout maior
    response = _request("POST", "eventoscorporativos/inserir_pacote_eventos", payload=payload, timeout=60)

    if response.status_code in (200, 201):
        _ativar_monitoramento_backend()
        return response.json()

    _tratar_erro_resposta(response, contexto="ao Inserir Pacote de Eventos")


def executar_requisicao_criar_evento_corporativo(payload: dict) -> Dict[str, Any]:
    """Cria um novo evento corporativo.

    :param payload: Dicionário conforme EventoCorporativoBase.
    :return: Objeto do evento criado.
    """
    response = _request("POST", "eventoscorporativos/", payload=payload)

    if response.status_code in (200, 201):
        _ativar_monitoramento_backend()
        return response.json()

    _tratar_erro_resposta(response, contexto="ao Criar Evento Corporativo")


def executar_requisicao_atualizar_evento_corporativo(evento_id: int, payload: dict) -> Dict[str, Any]:
    """Atualiza um evento corporativo existente.

    :param evento_id: ID do evento a ser atualizado.
    :param payload: Dicionário com campos a atualizar (EventoCorporativoUpdate).
    :return: Evento atualizado.
    """
    response = _request("PUT", f"eventoscorporativos/{evento_id}", payload=payload)

    if response.status_code == 200:
        _ativar_monitoramento_backend()
        return response.json()

    _tratar_erro_resposta(response, contexto="ao Atualizar Evento Corporativo")


def executar_requisicao_excluir_eventos_corporativos_lote( eventos_ids: Union[int, List[int]],) -> Dict[str, Any]:
    """Exclui um lote de eventos corporativos pelo(s) seu(s) ID(s).

    :param eventos_ids: ID único (int) ou lista de IDs (List[int]) a serem excluídos.
    :return: Dicionário contendo a resposta do backend em caso de sucesso ou dicionário vazio em falha.
    """
    #  Tratamento de tipo para garantir que a entrada seja sempre uma lista de inteiros
    if isinstance(eventos_ids, int):
        ids_formatados: List[int] = [eventos_ids]
    else:
        ids_formatados = eventos_ids

    if not ids_formatados:
        return {}
    payload = {"ids": ids_formatados}

    response = _request("DELETE", "eventoscorporativos/lote", payload=payload)

    # Validação do status 200 OK retornado pela rota refatorada
    if response.status_code == 200:
        _ativar_monitoramento_backend()
        return response.json()  # Retorna os dados com 'eventos_deletados' e 'movimentacoes_desvinculadas'

    _tratar_erro_resposta(response, contexto="ao Excluir Evento(s) Corporativo(s) em Lote")
    return {}


# ==============================================================================
# REQUISIÇÕES DE EVENTOS PENDENTES (API 'eventos_pendentes')
# ==============================================================================

def listar_eventos_pendentes_api(ativo_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Consome a rota GET /eventos_pendentes/pegar_eventos para listar eventos pendentes.

    [RESTRITO: ADMIN]

    :param ativo_id: Ticker do ativo base para filtragem (opcional).
    :return: Lista de dicionários contendo os eventos pendentes.
    """
    params = {"ativo_id": ativo_id.strip().upper()} if ativo_id else None

    response = _request("GET", "eventos_pendentes/pegar_eventos", params=params)

    if response.status_code == 200:
        return response.json()
    elif response.status_code == 404:
        return []

    _tratar_erro_resposta(response, contexto="ao Listar Eventos Pendentes")


def obter_evento_pendente_por_id_api(evento_id: int) -> Dict[str, Any]:
    """Consome a rota GET /eventos_pendentes/pegar_evento/{id} para buscar detalhes de um evento pendente pelo ID.

    [RESTRITO: ADMIN]

    :param evento_id: ID do evento pendente.
    :return: Dicionário contendo os detalhes do evento pendente.
    """
    response = _request("GET", f"eventos_pendentes/pegar_evento/{evento_id}")

    if response.status_code == 200:
        return response.json()
    elif response.status_code == 404:
        raise ApiRequestError(
            message=f"Evento pendente com ID {evento_id} não foi encontrado.",
            status_code=404,
            contexto="ao Obter Evento Pendente por ID",
        )

    _tratar_erro_resposta(response, contexto="ao Obter Evento Pendente por ID")


def editar_evento_pendente_api(evento_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Consome a rota PUT /eventos_pendentes/evento/{id} para atualizar parcialmente ou totalmente um evento pendente.

    [RESTRITO: ADMIN]

    :param evento_id: ID do evento pendente.
    :param payload: Dicionário contendo os dados do evento (EventoPendenteUpdate).
    :return: Dicionário com a resposta da API (status, mensagem, campos modificados).
    """
    response = _request("PUT", f"eventos_pendentes/evento/{evento_id}", payload=payload)

    if response.status_code == 200:
        _ativar_monitoramento_backend()
        return response.json()

    _tratar_erro_resposta(response, contexto="ao Editar Evento Pendente")


def atualizar_status_evento_pendente_api(evento_id: int, status: str) -> Dict[str, Any]:
    """Consome a rota PATCH /eventos_pendentes/{id}/status para atualizar o status do evento pendente.

    [RESTRITO: ADMIN]

    :param evento_id: ID do evento pendente.
    :param status: Novo status (ex: 'PENDENTE', 'IMPLEMENTADO', 'EM ANDAMENTO').
    :return: Dicionário com a resposta da API (status, mensagem, novo_status).
    """
    payload = {"status": status}
    response = _request("PATCH", f"eventos_pendentes/{evento_id}/status", payload=payload)

    if response.status_code == 200:
        _ativar_monitoramento_backend()
        return response.json()

    _tratar_erro_resposta(response, contexto="ao Atualizar Status do Evento Pendente")


def deletar_eventos_pendentes_em_lote_api(ids: List[int]) -> Dict[str, Any]:
    """Consome a rota DELETE /eventos_pendentes/delete_lote para excluir múltiplos eventos pendentes por ID.

    [RESTRITO: ADMIN]

    :param ids: Lista contendo os IDs dos eventos a serem removidos.
    :return: Dicionário com o resultado do expurgo (total excluidos, ids excluidos e não encontrados).
    """
    if not ids:
        return {}

    payload = {"ids": ids}
    response = _request("DELETE", "eventos_pendentes/delete_lote", payload=payload)

    if response.status_code == 200:
        _ativar_monitoramento_backend()
        return response.json()

    _tratar_erro_resposta(response, contexto="ao Deletar Lote de Eventos Pendentes")

# ==============================================================================
# REQUISIÇÕES DE COMANDOS DA CARTEIRA E RECALCULO
# ==============================================================================
def executar_requisicao_zerar_carteira(user_id: int) -> bool:
    """Dispara a requisição POST para zerar totalmente a carteira do usuário."""
    response = _request(
        "DELETE", f"comandos_api/zerar_carteira/{user_id}", timeout=30
    )

    if response.status_code in (200, 204):
        _ativar_monitoramento_backend()
        return True

    _tratar_erro_resposta(response, contexto="ao Zerar Carteira")


def executar_requisicao_disparar_update(user_id: int) -> bool:
    """Dispara a atualização manual do recálculo da carteira no backend."""
    response = _request(
        "POST", f"comandos_api/disparar_update_carteira/{user_id}", timeout=15
    )

    if response.status_code == 200:
        _ativar_monitoramento_backend()
        return True

    _tratar_erro_resposta(response, contexto="ao Disparar Recálculo")


def buscar_carteira_api(user_id: Optional[int] = None) -> list:
    """Consome a rota GET de carteira consolidada."""
    params = {"user_id": user_id} if user_id is not None else None
    response = _request("GET", "carteira/pegar_carteira", params=params, timeout=15)

    if response.status_code == 200:
        return response.json()
    elif response.status_code in (204, 404):
        return []

    _tratar_erro_resposta(response, contexto="ao Buscar Carteira")

# ==============================================================================
# REQUISIÇÕES DE ATIVOS
# ==============================================================================
def pesquisar_ativos_api( termo_busca: str, limite: int = 5 ) -> List[Dict[str, Any]]:
    """
    Consome a rota GET de pesquisa de ativos por termo (ticker, nome, etc).
    Retorna a lista de dicionários dos ativos encontrados.
    
    :param termo_busca: Termo de busca (ticker, nome da empresa, etc)
    :param limite: Limite de resultados a retornar
    :return: Lista de dicionários com dados dos ativos encontrados
    :raises ApiRequestError: Se a API retornar erro (3xx, 4xx, 5xx)
    """
    if not termo_busca or not termo_busca.strip():
        return []

    params = {"limite": limite}
    # urlquote/encode no termo para evitar quebras caso venham caracteres especiais
    endpoint = f"ativos/pesquisar_dados_ativos/{termo_busca.strip()}"

    try:
        response = _request("GET", endpoint, params=params, timeout=5)
    except ApiRequestError as e:
        # Propaga erros de comunicação com contexto
        raise ApiRequestError(
            message=f"Falha ao buscar ativos: {e.message}",
            status_code=e.status_code,
            contexto="ao Pesquisar Ativos",
        )
    except Exception as e:
        # Captura qualquer outra exceção inesperada
        raise ApiRequestError(
            message=f"Erro inesperado na busca de ativos: {str(e)}",
            status_code=None,
            contexto="ao Pesquisar Ativos",
        )

    if response.status_code == 200:
        return response.json()
    elif response.status_code == 404:
        # 404 é esperado quando não há resultados
        return []

    _tratar_erro_resposta(response, contexto="ao Pesquisar Ativos")

# ==============================================================================
# REQUISIÇÕES DE APORTE E PLANEJAMENTO
# ==============================================================================

def executar_requisicao_aporte_etapa1(payload: dict, user_id: Optional[int] = None) -> dict:
    """
    Consome a rota POST /aporte/aporte_etapa1 para calcular a distribuição macro do aporte entre grupos.

    :param payload: Dicionário contendo a estrutura correspondente ao Etapa1AporteRequest.
    :param user_id: ID do usuário alvo (Opcional - Apenas para uso de Administradores).
    :return: Dicionário com a resposta da API (AporteMacroResponse).
    """
    params = {"user_id": user_id} if user_id is not None else None

    response = _request(
        method="POST",
        endpoint="aporte/aporte_etapa1",
        params=params,
        payload=payload,
        timeout=30
    )

    if response.status_code == 200:
        return response.json()

    _tratar_erro_resposta(response, contexto="no Cálculo Macro do Aporte (Etapa 1)")

def executar_requisicao_aporte_etapa2( payload: dict, user_id: Optional[int] = None ) -> dict:
    """
    Consome a rota POST /aporte/aporte_etapa2 para calcular a sugestão de aportes.
    
    :param payload: Dicionário contendo a estrutura correspondente ao Etapa2Request.
    :param user_id: ID do usuário alvo (Opcional - Apenas para uso de Administradores).
    :return: Dicionário com a resposta da API (Etapa2Response).
    """
    params = {"user_id": user_id} if user_id is not None else None
    
    response = _request(
        method="POST",
        endpoint="aporte/aporte_etapa2",
        params=params,
        payload=payload,
        timeout=30
    )

    if response.status_code == 200:
        return response.json()

    _tratar_erro_resposta(response, contexto="no Cálculo do Aporte (Etapa 2)")

def executar_requisicao_atualizar_planejamento_carteira( payload: List[Dict[str, Any]], user_id: Optional[int] = None ) -> dict:
    """Consome a rota POST /aporte/atualizar_planejamento_carteira para

    atualizar grupo, subgrupo, nota e peso dos ativos na carteira do usuário.

    :param payload: Lista de dicionários correspondente ao
    ItemAtualizarAtivoCarteira.
    :param user_id: ID do usuário alvo (Opcional - Apenas para uso de
    Administradores).
    :return: Dicionário contendo o status e a mensagem de confirmação da API.
    """
    params = {"user_id": user_id} if user_id is not None else None

    response = _request(
        method="PATCH",
        endpoint="aporte/atualizar_planejamento_carteira",
        params=params,
        payload=payload,
        timeout=30,
    )

    if response.status_code == 200:
        chaves_para_delete = [
                "page_movimentacao.ultimo_carregar_tudo",
                "page_movimentacao.ultimo_ativo_carregado",
                "page_movimentacao.ordens_pendentes",
                "dados_carteira_cache",
                "page_aportes",
                "planejamento_guiado",
                "page_aporte_rapido",
                "carregou_carteira"
            ]
        _ativar_monitoramento_backend(chaves_para_delete)
        return response.json()

    _tratar_erro_resposta( response, contexto="ao Atualizar Configurações de Ativos da Carteira" )

# ==============================================================================
# REQUISIÇÕES DE CONFIGURAÇÕES DE USUÁRIO
# ==============================================================================
def obter_configuracoes_usuario_api(user_id: Optional[int] = None) -> dict:
    """
    Consome a rota GET para obter a coluna JSON 'configuracoes' do usuário.
    
    :param user_id: ID do usuário alvo (Opcional - Apenas para Administradores).
    :return: Dicionário contendo as configurações cadastradas no banco de dados.
    :raises ApiRequestError: Se a API retornar erro (3xx, 4xx, 5xx)
    """
    params = {"user_id": user_id} if user_id is not None else None
    response = _request("GET", "usuarios/configuracoes", params=params, timeout=10)

    if response.status_code == 200:
        res_json = response.json()
        return res_json.get("configuracoes", {})

    _tratar_erro_resposta(response, contexto="ao Obter Configurações do Usuário")

def executar_requisicao_atualizar_configuracoes( payload: dict, user_id: Optional[int] = None ) -> dict:
    """
    Envia atualizações dinâmicas (JSON) para a coluna 'configuracoes' na tabela Usuarios.
    
    :param payload: Dicionário contendo as chaves a serem atualizadas no JSON.
    :param user_id: ID do usuário alvo (Opcional - Apenas para Administradores).
    :return: Dicionário contendo o resultado da resposta da API.
    :raises ApiRequestError: Se a API retornar erro (3xx, 4xx, 5xx)
    """
    params = {"user_id": user_id} if user_id is not None else None

    response = _request(
        method="PUT",
        endpoint="usuarios/configuracoes",
        params=params,
        payload=payload,
        timeout=10,
    )

    if response.status_code == 200:
        if 'configuracoes' in st.session_state:
            del st.session_state['configuracoes']
        return response.json()

    _tratar_erro_resposta(response, contexto="ao Salvar Configurações do Usuário")