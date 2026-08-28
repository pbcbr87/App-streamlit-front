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

def renderizar_formulario_dividendo(registro: Optional[Dict[str, Any]],
                                    on_salvar: Callable[[Dict[str, Any], bool], bool],
                                    on_sucesso: Optional[Callable[[], None]] = None,
                                    dado_global: Optional[Dict[str, Any]] = False,
                                    key_estado_dinamico: str = "form_dividendo",
                                    ) -> Dict[str, Any]:
    registro = dict(registro or {})
    editando = registro.get("id") is not None    

    chave_estado_ativo = f"estado_ativo_{key_estado_dinamico}"
    if chave_estado_ativo not in st.session_state:
        st.session_state[chave_estado_ativo] = {
            "ativo_original": registro.get("fk_ativo") or "Selecionar Ativo",
            "dados_ativo_original": registro.get("dados_ativo_original"),
        }
    estado_ativo = st.session_state[chave_estado_ativo]

    with st.container(border=True):
        g1, g2, g3, g4, g5 = st.columns(5)
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

        dados_ativo = estado_ativo.get("dados_ativo_original") or {}
        moeda = dados_ativo.get("moeda") or registro.get("moeda") or "BRL"

        if not dado_global:
            moeda = registro.get("moeda") or "BRL"
            sufixo = "brl" if moeda == "BRL" else "usd"
            valor_col = f"valor_bruto_{sufixo}"
            val_liq_col = f"valor_liq_{sufixo}"
            imposto_col = f"imposto_{sufixo}"
        else:
            valor_col = "valor_bruto"
            val_liq_col = "valor_liq"
            imposto_col = "imposto"
            
        tipo_atual = registro.get("tipo") if registro.get("tipo") in TIPOS_DIVIDENDO else TIPOS_DIVIDENDO[0]
        tipo = g2.selectbox("⚡ Tipo", TIPOS_DIVIDENDO, index=TIPOS_DIVIDENDO.index(tipo_atual), key=f"tipo_{key_estado_dinamico}")
      
        val_bruto_default = "0,00" if not registro.get(valor_col) else f"{registro.get(valor_col)}".replace(".", ",")
        val_liq_default = "0,00" if not registro.get(val_liq_col) else f"{registro.get(val_liq_col)}".replace(".", ",")
        val_imposto_default = "0,00" if not registro.get(imposto_col) else f"{registro.get(imposto_col)}".replace(".", ",")

        def atualizar_liquido():
            bruto_val = st.session_state.get(f"bruto_{key_estado_dinamico}_return", 0.00)
            imposto_val = st.session_state.get(f"imposto_{key_estado_dinamico}_return", 0.00)
            liquido_val = max(0.0, bruto_val - imposto_val)

            st.session_state[f"liquido_{key_estado_dinamico}"] = formatar_numero_para_br_str(liquido_val)
            st.session_state[f"liquido_{key_estado_dinamico}_return"] = liquido_val
        def atualizar_imposto():
            liquido_val = st.session_state.get(f"liquido_{key_estado_dinamico}_return", 0.00)
            bruto_val = st.session_state.get(f"bruto_{key_estado_dinamico}_return", 0.00)
            imposto_val = bruto_val - liquido_val

            st.session_state[f"imposto_{key_estado_dinamico}"] = formatar_numero_para_br_str(imposto_val)
            st.session_state[f"imposto_{key_estado_dinamico}_return"] = imposto_val

        with g3:
            bruto = st_number_input_custom( f"💰 Valor Bruto {moeda}",
                                            value=val_bruto_default,  
                                            key=f"bruto_{key_estado_dinamico}", 
                                            on_change=atualizar_liquido
                                            )

        with g4:
            imposto = st_number_input_custom( f"🏛️ Imposto {moeda}",
                                                value=val_imposto_default,
                                                key=f"imposto_{key_estado_dinamico}",
                                                on_change=atualizar_liquido
                                            )
        with g5:
            liquido = st_number_input_custom( f"💵 Valor Líquido {moeda}",
                                                value=val_liq_default,
                                                key=f"liquido_{key_estado_dinamico}",
                                                on_change=atualizar_imposto
                                            )

        d1, d2, d3, d4 = st.columns(4)
        datas = {}
        for container, campo, rotulo in ( (d1, "data_aprov", "Data Aprovação"), 
                                          (d2, "data_com", "Data Com"),
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
        "valor_liq": liquido,
        "ano_calendario_ir": int(ano),
        **datas,
    }
    if editando:
        payload["id"] = registro["id"]

    datas_obrigatorias_preenchidas = bool(datas["data_aprov"] and datas["data_com"])
    valido = bool(ativo) and bruto is not None and liquido is not None and datas_obrigatorias_preenchidas
    if not valido:
        st.warning("⚠️ Informe ativo, valores válidos e as três datas para continuar.")
    
    #  BLOCO DE PREVIEW DINÂMICO DOS DIVIDENDOS
    if valido:
        # 1. Tratamento seguro das datas retornando objeto date puro da função + strftime
        d_aprov = formatar_data_segura(datas["data_aprov"]) if datas["data_aprov"] else None
        d_com = formatar_data_segura(datas["data_com"]) if datas["data_com"] else None
        d_pag = formatar_data_segura(datas["data_pag"]) if datas["data_pag"] else None

        f_data_aprov = d_aprov.strftime("%d/%m/%Y") if d_aprov else "-"
        f_data_com = d_com.strftime("%d/%m/%Y") if d_com else "-"
        f_data_pag = d_pag.strftime("%d/%m/%Y") if d_pag else "-"

        # 2. Formatação Numérica com o utilitário do projeto
        str_bruto = f"{moeda} {formatar_numero_para_br_str(bruto or 0.0)}"
        str_imposto = f"{moeda} {formatar_numero_para_br_str(imposto or 0.0)}"
        str_liquido = f"{moeda} {formatar_numero_para_br_str(liquido or 0.0)}"

        # 3. Renderização do Container Estilizado
        with st.container(border=True):
            st.markdown("#### 🔍 Resumo do Provento")
            
            # Cabeçalho com badge de Tipo + Ativo
            st.markdown(f"##### 💸 {tipo} | {ativo}")
            st.caption(f"Ano Calendário IR: {ano} | Moeda: {moeda}")

            # GRID COMPACTO EM HTML/CSS (2 Linhas x 3 Colunas)
            html_preview = f"""
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-top: 5px; margin-bottom: 5px;">
                <div style="background-color: rgba(128, 128, 128, 0.08); padding: 8px; border-radius: 6px;">
                    <small style="color: gray; display: block; margin-bottom: 2px;">📅 Data Com</small>
                    <strong style="font-size: 1.05rem;">{f_data_com}</strong>
                </div>
                <div style="background-color: rgba(128, 128, 128, 0.08); padding: 8px; border-radius: 6px;">
                    <small style="color: gray; display: block; margin-bottom: 2px;">📋 Data Aprovação</small>
                    <strong style="font-size: 1.05rem;">{f_data_aprov}</strong>
                </div>
                <div style="background-color: rgba(128, 128, 128, 0.08); padding: 8px; border-radius: 6px;">
                    <small style="color: gray; display: block; margin-bottom: 2px;">💳 Data Pagamento</small>
                    <strong style="font-size: 1.05rem;">{f_data_pag}</strong>
                </div>
                <div style="background-color: rgba(128, 128, 128, 0.08); padding: 8px; border-radius: 6px;">
                    <small style="color: gray; display: block; margin-bottom: 2px;">💰 Valor Bruto</small>
                    <strong style="font-size: 1.05rem;">{str_bruto}</strong>
                </div>
                <div style="background-color: rgba(128, 128, 128, 0.08); padding: 8px; border-radius: 6px;">
                    <small style="color: gray; display: block; margin-bottom: 2px;">🏛️ Imposto Retido</small>
                    <strong style="font-size: 1.05rem; color: #e74c3c;">{str_imposto}</strong>
                </div>
                <div style="background-color: rgba(128, 128, 128, 0.12); padding: 8px; border-radius: 6px; border-left: 3px solid #2ecc71;">
                    <small style="color: gray; display: block; margin-bottom: 2px;">💵 Valor Líquido</small>
                    <strong style="font-size: 1.05rem; color: #2ecc71;">{str_liquido}</strong>
                </div>
            </div>
            """
            st.markdown(html_preview, unsafe_allow_html=True)
        with st.container(horizontal=True):
            btn = st.empty()
            concordou = st.checkbox("Os dados estão corretos", key=f"chk_agree_{key_estado_dinamico}")

            btn_label = "💾 Salvar Alterações" if editando else "🚀 Inserir Dividendo"

            if btn.button(btn_label, type="primary", disabled=not (valido and concordou), key=f"salvar_{key_estado_dinamico}"):
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
