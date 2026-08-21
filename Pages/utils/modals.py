import streamlit as st
from typing import Optional
from Pages.utils.request_api import (executar_requisicao_deletar_movimentacoes_lote,
                                     executar_requisicao_zerar_carteira,
                                     executar_requisicao_deletar_eventos_lote)



@st.dialog("🚨 ATENÇÃO: Zerar Carteira")
def modal_confirmar_zerar_carteira():
    """Modal de dupla confirmação para a deleção total da carteira."""
    st.error(
        "Esta ação **apagará permanentemente** todas as suas movimentações, "
        "ordens de entrada, eventos e resumos fiscais da conta!"
    )
    st.write("Tem certeza absoluta de que deseja resetar todo o seu histórico?")
    
    st.divider()
    c_cancel, c_confirm = st.columns([1, 1])
    
    with c_cancel:
        if st.button("❌ Cancelar", width='stretch'):
            st.rerun()
            
    with c_confirm:
        if st.button("💣 Sim, Zerar Tudo", type="primary", width='stretch'):
            # Obtém o id do usuário logado na sessão
            user_id = st.session_state.id
            
            with st.spinner("Zerando base de dados..."):
                try:
                    sucesso = executar_requisicao_zerar_carteira(user_id)
                    if sucesso:
                        st.toast("🚨 Carteira zerada com sucesso! Reprocessando base...", icon="✅")
                        
                        # Invalida o cache da tela
                        state_loc = st.session_state.get('page_movimentacao', {})
                        state_loc['ultimo_ativo_carregado'] = None
                        state_loc['ultimo_carregar_tudo'] = False
                        st.rerun()

                except Exception as e:
                    st.toast(f"❌ Erro ao zerar carteira: {str(e)}", icon="❌")


@st.dialog("⚠️ Confirmar Exclusão de Eventos")
def modal_confirmar_delecao_eventos() -> None:
    """ Modal de confirmação dinâmico alinhado à rota /deletar_eventos_lote."""
    state_loc = st.session_state.get("page_eventos", {})
    ids_para_enviar = state_loc.get("ids_deletar_pendentes", [])
    tem_sistema: bool = state_loc.get("tem_eventos_sistema", False)
    
    recalcular = False

    # Exibe as opções de exclusão/inativação caso haja eventos de sistema
    if tem_sistema:
        st.write("Alguns eventos selecionados são **eventos de sistema** (gerados automaticamente).")
        
        # Checkbox alinhado ao parâmetro query 'recalcular' da API
        recalcular = st.checkbox( "Manter eventos ativos e recalcular automaticamente", 
                   value=True,
                   help="Se marcado, o motor sistema reprocessa os eventos. Se desmarcado, os eventos vinculados serão desativados (aceito = False)."
               )
        
        # Feedback visual imediato sobre o que vai acontecer
        if recalcular:
            st.info("ℹ️ Os eventos associados serão **mantidos e recalculados** pelo motor contábil.")
        else:
            st.warning("⚠️ Os eventos associados serão **desativados (marcados como não aceitos)**.")
    else:
        st.write(
            f"Tem certeza que deseja excluir permanentemente **{len(ids_para_enviar)}** evento(s) personalizado(s)?"
        )
    
    st.divider()
    c_cancel, c_confirm = st.columns([1, 1])
    
    with c_cancel:
        if st.button("❌ Cancelar", width="stretch"):
            state_loc["ids_deletar_pendentes"] = []
            state_loc["tem_eventos_sistema"] = False
            st.rerun()
            
    with c_confirm:
        if st.button("🗑️ Confirmar", type="primary", width="stretch"):
            with st.spinner("Processando solicitação..."):
                try:
                    # Executa a requisição enviando os IDs e a flag recalcular
                    sucesso = executar_requisicao_deletar_eventos_lote(
                        ids_eventos=ids_para_enviar, 
                        recalcular=recalcular
                    )
                    
                    if sucesso:
                        st.toast(
                            f"✅ Processamento de {len(ids_para_enviar)} evento(s) concluído com sucesso!", 
                            icon="✅"
                        )
                        # Invalida cache local da página para forçar recarregamento na listagem
                        state_loc["ultimo_ativo_carregado"] = None
                        state_loc["ultimo_carregar_tudo"] = False
                        
                        # Limpa a sessão do modal
                        state_loc["ids_deletar_pendentes"] = []
                        state_loc["tem_eventos_sistema"] = False
                        st.rerun()

                except Exception as e:
                    st.toast(f"❌ Erro ao processar exclusão: {str(e)}", icon="❌")


@st.dialog("⚠️ Confirmar Exclusão em Lote")
def modal_confirmar_delecao():
    """Modal de confirmação dinâmico com base na existência de eventos vinculados."""
    state_loc = st.session_state.get('page_movimentacao', {})
    ids_para_enviar = state_loc.get('ids_deletar_pendentes', [])
    tem_eventos = state_loc.get('deletar_tem_eventos', False)
    
    # Exibe o aviso e a pergunta SOMENTE se houver eventos associados
    if tem_eventos:
        st.write(
            "Existem **eventos corporativos associados** a estas movimentações."
        )
        
        # Checkbox para alternar entre recalcular ou desativar
        recalcular = st.checkbox(
            "Manter eventos ativos e recalcular automaticamente", 
            value=True,
            help="Se marcado, o motor sistema reprocessa os eventos. Se desmarcado, os eventos vinculados serão desativados (aceito = False)."
        )
        
        # Feedback visual imediato sobre o que vai acontecer
        if recalcular:
            st.info("ℹ️ Os eventos associados serão **mantidos e recalculados** pelo motor contábil.")
        else:
            st.warning("⚠️ Os eventos associados serão **desativados (marcados como não aceitos)**.")
            
    else:
        st.write(
            f"Tem certeza que deseja excluir **{len(ids_para_enviar)}** movimentação(ões) selecionada(s)?"
        )
        recalcular = False  # Não há eventos para recalcular
    
    st.divider()
    c_cancel, c_confirm = st.columns([1, 1])
    
    with c_cancel:
        if st.button("❌ Cancelar", width='stretch'):
            state_loc['ids_deletar_pendentes'] = []
            state_loc['deletar_tem_eventos'] = False
            st.rerun()
            
    with c_confirm:
        if st.button("🗑️ Confirmar Exclusão", type="primary", width='stretch'):
            with st.spinner("Excluindo..."):
                try:
                    sucesso = executar_requisicao_deletar_movimentacoes_lote(
                        ids_para_enviar, 
                        recalcular
                    )

                    if sucesso:
                        st.toast(
                            f"🗑️ {len(ids_para_enviar)} movimentação(ões) excluída(s) com sucesso!", 
                            icon="✅"
                        )
                        # Invalida o cache
                        state_loc['ultimo_ativo_carregado'] = None
                        state_loc['ultimo_carregar_tudo'] = False
                        
                        # Limpa a sessão
                        state_loc['ids_deletar_pendentes'] = []
                        state_loc['deletar_tem_eventos'] = False
                        st.rerun()

                except Exception as e:
                    st.toast(f"❌ Erro ao excluir: {str(e)}", icon="❌")
