from datetime import date
from typing import Any, Callable, Dict, Optional

import streamlit as st

from Pages.utils.components import (
    componente_buscador_ativo,
    st_number_input_custom,
)
from Pages.utils.ferramentas import (
    formatar_data_segura,
    formatar_numero_para_br_str,
)
from Pages.utils.form_edit import renderizar_erro_api
from Pages.utils.request_api import ApiRequestError

TIPOS_DIVIDENDO = [
    "DIVIDENDO", "JCP", "REND. TRIBUTADO", "RENDIMENTO",
    "RENDIMENTO EXT", "AMORTIZAÇÃO", "AGENCY PROC. FEE",
]

def renderizar_formulario_dividendo( registro: Optional[Dict[str, Any]],
                                    moeda: str,
                                    on_salvar: Callable[[Dict[str, Any], bool], bool],
                                    on_sucesso: Optional[Callable[[], None]] = None,
                                    key_estado_dinamico: str = "form_dividendo",
                                    ) -> Dict[str, Any]:
    registro = dict(registro or {})
    editando = registro.get("id") is not None
    sufixo = "brl" if moeda == "BRL" else "usd"
    valor_col = f"valor_bruto_{sufixo}"
    imposto_col = f"imposto_{sufixo}"

    chave_estado_ativo = f"estado_ativo_{key_estado_dinamico}"
    if chave_estado_ativo not in st.session_state:
        st.session_state[chave_estado_ativo] = {
            "ativo_original": registro.get("fk_ativo") or "Selecionar Ativo",
        }
    estado_ativo = st.session_state[chave_estado_ativo]

    with st.container(border=True):
        g1, g2, g3, g4 = st.columns(4)
        with g1:
            componente_buscador_ativo(
                estado_ativo,
                "ativo_original",
                sufixo_key=f"div_{key_estado_dinamico}",
                titulo="🏷️ Ativo Categoria:",
            )
        ativo = estado_ativo.get("ativo_original")
        if ativo == "Selecionar Ativo":
            ativo = ""
        tipo_atual = registro.get("tipo") if registro.get("tipo") in TIPOS_DIVIDENDO else TIPOS_DIVIDENDO[0]
        tipo = g2.selectbox("⚡ Tipo", TIPOS_DIVIDENDO, index=TIPOS_DIVIDENDO.index(tipo_atual), key=f"tipo_{key_estado_dinamico}")
      
        val_bruto_default = "0,00" if not registro.get(valor_col) else f"{registro.get(valor_col)}".replace(".", ",")
        val_imposto_default = "0,00" if not registro.get(imposto_col) else f"{registro.get(imposto_col)}".replace(".", ",")
        with g3:
            bruto = st_number_input_custom( f"💰 Valor Bruto ({moeda})", value=val_bruto_default,  key=f"bruto_{key_estado_dinamico}",)
        with g4:
            imposto = st_number_input_custom( f"🏛️ Imposto ({moeda})",
                                                value=val_imposto_default,
                                                key=f"imposto_{key_estado_dinamico}",
                                            )

        d1, d2, d3, d4 = st.columns(4)
        datas = {}
        for container, campo, rotulo in ( (d1, "data_aprov", "Data Aprovação"), (d2, "data_com", "Data Com"),
                                        (d3, "data_pag", "Data Pagamento"), ):
            valor_original = registro.get(campo)
            valor_data = formatar_data_segura(valor_original) if valor_original else None
            if f"{campo}_{key_estado_dinamico}" not in st.session_state:
                st.session_state[f"{campo}_{key_estado_dinamico}"] = valor_data
            data = container.date_input(rotulo, min_value=date(2000, 1, 1), value=None, format="DD/MM/YYYY", key=f"{campo}_{key_estado_dinamico}")
            
            datas[campo] = data.isoformat() if data else None

        ano = d4.number_input( "📅 Ano Calendário IR", min_value=2000, max_value=2100,
                                value=int(registro.get("ano_calendario_ir") or date.today().year),
                                step=1, key=f"ano_{key_estado_dinamico}",
                            )
    payload = {
        "fk_ativo": ativo,
        "tipo": tipo,
        "valor_bruto": bruto,
        "valor_liq": bruto - imposto,
        "ano_calendario_ir": int(ano),
        **datas,
    }
    if editando:
        payload["id"] = registro["id"]

    datas_obrigatorias_preenchidas = bool(datas["data_aprov"] and datas["data_com"])
    valido = bool(ativo) and bruto is not None and imposto is not None and datas_obrigatorias_preenchidas
    if not valido:
        st.warning("⚠️ Informe ativo, valores válidos e as três datas para continuar.")

    bruto_resumo = formatar_numero_para_br_str(bruto or 0)
    st.caption(f"Resumo: {ativo or '-'} | {tipo} | {moeda} {bruto_resumo}")
    if st.button("💾 Salvar Alterações" if editando else "🚀 Inserir Dividendo", type="primary", disabled=not valido, key=f"salvar_{key_estado_dinamico}"):
        try:
            if on_salvar(payload, editando):
                st.toast("✅ Dividendo salvo com sucesso!", icon="🎉")
                if on_sucesso:
                    on_sucesso()
        except ApiRequestError as erro:
            st.error(erro.message)
        except Exception as erro:
            st.error(str(erro))

    return payload
