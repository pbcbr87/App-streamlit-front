from datetime import date, datetime
from decimal import Decimal
import streamlit as st
from typing import Any, Optional
import math
import pandas as pd


def tratar_dados_carteira_raw(dados_raw: list) -> list:
    """
    Processa e enriquece a lista de dicionários vinda da API
    usando apenas estruturas nativas do Python.
    """
    if not dados_raw:
        return []

    dados_tratados = []
    for item in dados_raw:
        reg = dict(item)

        # Trata campos de texto
        reg["categoria"] = str(reg.get("categoria", "Sem Categorias")).upper().strip()
        reg["setor"] = str(reg.get("setor", "Sem Setor")).upper().strip()

        reg['grupo'] = str(reg.get("grupo", reg["categoria"])).upper().strip()
        reg['subgrupo'] = str(reg.get("subgrupo", reg["setor"])).upper().strip()

        reg["codigo_ativo"] = str(reg.get("codigo_ativo", "sem ticket")).upper().strip()

        # Leitura segura dos numéricos
        custo_brl = float(reg.get("custo_brl", 0.0) or 0.0)
        custo_usd = float(reg.get("custo_usd", 0.0) or 0.0)
        v_mkt_brl = float(reg.get("valor_mercado_brl", 0.0) or 0.0)
        v_mkt_usd = float(reg.get("valor_mercado_usd", 0.0) or 0.0)
        v_plan_brl = float(reg.get("valor_plan_brl", 0.0) or 0.0)
        v_plan_usd = float(reg.get("valor_plan_usd", 0.0) or 0.0)
        lucro_brl = float(reg.get("lucro_brl", 0.0) or 0.0)
        lucro_usd = float(reg.get("lucro_usd", 0.0) or 0.0)
        lucro_div_brl = float(reg.get("lucro_div_brl", 0.0) or 0.0)
        lucro_div_usd = float(reg.get("lucro_div_usd", 0.0) or 0.0)

        # Cálculos de Percentuais e Aportes Nativos
        reg["lucro_p_brl"] = (lucro_brl / custo_brl) if custo_brl > 0 else 0.0
        reg["lucro_p_usd"] = (lucro_usd / custo_usd) if custo_usd > 0 else 0.0
        reg["lucro_div_p_brl"] = (lucro_div_brl / custo_brl) if custo_brl > 0 else 0.0
        reg["lucro_div_p_usd"] = (lucro_div_usd / custo_usd) if custo_usd > 0 else 0.0

        reg["aporte_brl"] = v_plan_brl - v_mkt_brl
        reg["aporte_usd"] = v_plan_usd - v_mkt_usd
        reg["aporte_p_brl"] = ( (v_plan_brl - v_mkt_brl) / v_mkt_brl) if v_mkt_brl > 0 else 0.0
        reg["aporte_p_usd"] = ( (v_plan_usd - v_mkt_usd) / v_mkt_usd) if v_mkt_usd > 0 else 0.0

        dados_tratados.append(reg)

    return dados_tratados

def sanitizar_numero(valor: Any, fallback: Optional[float] = None) -> Optional[float]:
    """
    Sanitiza qualquer entrada (str, int, float, Decimal) e a converte com segurança para float.
    Útil para limpar retornos do banco de dados/JSON ou dados de inputs de formulários.
    
    Exemplos:
        sanitizar_numero("1.500,50") -> 1500.5
        sanitizar_numero("0,260000") -> 0.26
        sanitizar_numero(Decimal('10.5')) -> 10.5
        sanitizar_numero("qtd") -> None (ou o fallback definido)
    """
    if valor is None:
        return fallback

    # Se já for um tipo numérico direto, converte direto para float
    if isinstance(valor, (int, float, Decimal)):
        return float(valor)

    if isinstance(valor, str):
        # Remove espaços nas pontas e ignora marcadores textuais genéricos do motor
        valor_limpo = valor.strip()
        if valor_limpo.lower() in ("", "none", "null", "qtd", "qtd_temp"):
            return fallback

        try:
            # Identifica o padrão de formatação (BR vs Internacional)
            # Se tiver vírgula e o ponto vier antes da vírgula (ex: 1.500,00) ou se apenas tiver vírgula (ex: 0,26)
            if "," in valor_limpo:
                if "." in valor_limpo and valor_limpo.find(".") < valor_limpo.find(","):
                    # Padrão BR com separador de milhar: 1.500,50 -> 1500.50
                    valor_limpo = valor_limpo.replace(".", "").replace(",", ".")
                else:
                    # Apenas decimal com vírgula: 0,26 -> 0.26
                    valor_limpo = valor_limpo.replace(",", ".")
            else:
                # Padrão internacional com separador de milhar: 1,500.50 -> 1500.50
                if "," in valor_limpo:
                    valor_limpo = valor_limpo.replace(",", "")

            return float(valor_limpo)
        except (ValueError, TypeError):
            return fallback

    return fallback

def dividir_id_ativo(id_ativo: str) -> tuple[str, str]:
    """Função dedicada exclusivamente a fazer o split do ID do ativo."""
    if not id_ativo or id_ativo == "Selecionar Ativo":
        return None, None
    if "_" in id_ativo:
        partes = id_ativo.split("_", 1)
        return partes[0].strip(), partes[1].strip()
    return id_ativo.strip(), ""

def formatar_ativo_visual(id_ativo: str) -> str:
    """Formatador visual reaproveitável."""
    if not id_ativo or id_ativo == "Selecionar Ativo":
        return id_ativo
    if "_" in id_ativo:
        ativo, categoria = id_ativo.split("_", 1)
        return f"{ativo} ({categoria})"
    return id_ativo

def limpar_nans_dict(lista_dicts: list[dict]) -> list[dict]:
    """
    Converte NaNs/NaTs para None e formata objetos de Data (Timestamp/datetime) 
    para strings no padrão ISO (YYYY-MM-DD) aceito pelo JSON.
    """
    lista_limpa = []
    for d in lista_dicts:
        item_limpo = {}
        for k, v in d.items():
            # 1. Trata valores ausentes (NaN, NaT, None, inf)
            if pd.isna(v) or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
                item_limpo[k] = None
            # 2. Trata Timestamps do Pandas ou datetimes do Python
            elif isinstance(v, (pd.Timestamp, datetime, date)):
                # Converte '2020-07-02 00:00:00' para '2020-07-02'
                item_limpo[k] = v.strftime("%Y-%m-%d")
            # 3. Mantém outros valores válidos
            else:
                item_limpo[k] = v

        lista_limpa.append(item_limpo)
    return lista_limpa

def converter_para_float(texto):
    if texto is None or texto == "":
        return 0.0
    if isinstance(texto, (int, float)):
        return float(texto)
    try:
        limpo = str(texto).strip().replace(".", "").replace(",", ".")
        return float(limpo)
    except ValueError:
        return None

def formatar_numero_para_br_str(val):
    if val is None or val == "":
        return ""
    # Se for string, primeiro tenta converter pra float pra reformatar limpo
    if isinstance(val, str):
        val_limpo = val.strip().replace(".", "").replace(",", ".")
        try:
            val = float(val_limpo)
        except ValueError:
            return val  # Mantém o texto para disparar a validação de erro

    if isinstance(val, (int, float)):
        return f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return str(val)

def formatar_data_segura(valor):
    """Garante que o valor retornado seja SEMPRE um objeto date puro."""
    if isinstance(valor, datetime):
        return valor.date()  # 👈 Extrai apenas a data do datetime
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        try:
            return datetime.fromisoformat(valor.split('T')[0]).date()
        except:
            return date.today()
    return date.today()