import streamlit as st
import random
import math
from typing import List, Tuple, Optional

# --- CONSTANTES E CONFIGURAÇÕES ---
JOGADOR_HUMANO = "❌"
JOGADOR_IA = "⭕"
VAZIO = " "

st.set_page_config(page_title="Jogo da Velha IA", page_icon="🕹️", layout="centered")

# --- CSS CUSTOMIZADO (Visual Premium) ---
st.markdown(
    """
    <style>
    /* Estilização dos botões para parecerem um tabuleiro de verdade */
    div[data-testid="column"] button {
        height: 110px !important;
        font-size: 50px !important;
        border-radius: 10px !important;
        transition: transform 0.1s ease-in-out;
    }
    div[data-testid="column"] button:hover {
        transform: scale(1.02);
    }
    div[data-testid="column"] button p {
        font-size: 3.5rem !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)


# --- LÓGICA DO JOGO ---
def verificar_vitoria(tabuleiro: List[List[str]], jogador: str) -> bool:
    # Checa linhas e colunas
    for i in range(3):
        if all(tabuleiro[i][j] == jogador for j in range(3)) or all(
            tabuleiro[j][i] == jogador for j in range(3)
        ):
            return True
    # Checa diagonais
    if (tabuleiro[0][0] == tabuleiro[1][1] == tabuleiro[2][2] == jogador) or (
        tabuleiro[0][2] == tabuleiro[1][1] == tabuleiro[2][0] == jogador
    ):
        return True
    return False


def tabuleiro_cheio(tabuleiro: List[List[str]]) -> bool:
    return all(celula != VAZIO for linha in tabuleiro for celula in linha)


def obter_posicoes_livres(tabuleiro: List[List[str]]) -> List[Tuple[int, int]]:
    return [(r, c) for r in range(3) for c in range(3) if tabuleiro[r][c] == VAZIO]


# --- INTELIGÊNCIA ARTIFICIAL (MINIMAX) ---
def minimax(
    tabuleiro: List[List[str]],
    profundidade: int,
    alpha: float,
    beta: float,
    maximizando: bool,
) -> float:
    if verificar_vitoria(tabuleiro, JOGADOR_IA):
        return 10 - profundidade  # IA prefere vencer rápido
    if verificar_vitoria(tabuleiro, JOGADOR_HUMANO):
        return profundidade - 10  # IA prefere perder devagar
    if tabuleiro_cheio(tabuleiro):
        return 0

    if maximizando:
        melhor_pontuacao = -math.inf
        for r, c in obter_posicoes_livres(tabuleiro):
            tabuleiro[r][c] = JOGADOR_IA
            pontuacao = minimax(tabuleiro, profundidade + 1, alpha, beta, False)
            tabuleiro[r][c] = VAZIO
            melhor_pontuacao = max(pontuacao, melhor_pontuacao)
            alpha = max(alpha, pontuacao)
            if beta <= alpha:
                break  # Poda
        return melhor_pontuacao
    else:
        melhor_pontuacao = math.inf
        for r, c in obter_posicoes_livres(tabuleiro):
            tabuleiro[r][c] = JOGADOR_HUMANO
            pontuacao = minimax(tabuleiro, profundidade + 1, alpha, beta, True)
            tabuleiro[r][c] = VAZIO
            melhor_pontuacao = min(pontuacao, melhor_pontuacao)
            beta = min(beta, pontuacao)
            if beta <= alpha:
                break  # Poda
        return melhor_pontuacao


def jogada_ia(
    tabuleiro: List[List[str]], dificuldade: str
) -> Optional[Tuple[int, int]]:
    posicoes_livres = obter_posicoes_livres(tabuleiro)
    if not posicoes_livres:
        return None

    # Se for a primeira jogada da IA no modo impossível, escolhe o meio ou canto para economizar processamento
    if len(posicoes_livres) == 9 and dificuldade == "Impossível":
        return random.choice([(1, 1), (0, 0), (0, 2), (2, 0), (2, 2)])

    if dificuldade == "Fácil":
        return random.choice(posicoes_livres)

    # Modo Impossível (Minimax)
    melhor_pontuacao = -math.inf
    melhor_jogada = None
    for r, c in posicoes_livres:
        tabuleiro[r][c] = JOGADOR_IA
        pontuacao = minimax(tabuleiro, 0, -math.inf, math.inf, False)
        tabuleiro[r][c] = VAZIO

        if pontuacao > melhor_pontuacao:
            melhor_pontuacao = pontuacao
            melhor_jogada = (r, c)

    return melhor_jogada


# --- GERENCIAMENTO DE ESTADO (SESSION STATE) ---
def inicializar_estado():
    if "tabuleiro" not in st.session_state:
        st.session_state.tabuleiro = [[VAZIO for _ in range(3)] for _ in range(3)]
    if "game_over" not in st.session_state:
        st.session_state.game_over = False
    if "mensagem" not in st.session_state:
        st.session_state.mensagem = ""
    if "placar" not in st.session_state:
        st.session_state.placar = {"Humano": 0, "IA": 0, "Empate": 0}


def reiniciar_jogo(ia_comeca: bool = False, dificuldade: str = "Impossível"):
    st.session_state.tabuleiro = [[VAZIO for _ in range(3)] for _ in range(3)]
    st.session_state.game_over = False
    st.session_state.mensagem = ""

    # Se a IA for configurada para começar, ela faz a primeira jogada imediatamente
    if ia_comeca:
        r, c = jogada_ia(st.session_state.tabuleiro, dificuldade)
        st.session_state.tabuleiro[r][c] = JOGADOR_IA


inicializar_estado()


# --- AÇÃO DE CLIQUE NO TABULEIRO ---
def processar_turno(r: int, c: int, dificuldade: str):
    if st.session_state.tabuleiro[r][c] != VAZIO or st.session_state.game_over:
        return

    # 1. Jogada do Humano
    st.session_state.tabuleiro[r][c] = JOGADOR_HUMANO

    if verificar_vitoria(st.session_state.tabuleiro, JOGADOR_HUMANO):
        st.session_state.mensagem = "🎉 INCRÍVEL! Você venceu a IA!"
        st.session_state.placar["Humano"] += 1
        st.session_state.game_over = True
        return

    if tabuleiro_cheio(st.session_state.tabuleiro):
        st.session_state.mensagem = "🤝 Deu Velha! O jogo empatou."
        st.session_state.placar["Empate"] += 1
        st.session_state.game_over = True
        return

    # 2. Jogada da IA
    ia_movimento = jogada_ia(st.session_state.tabuleiro, dificuldade)
    if ia_movimento:
        ia_r, ia_c = ia_movimento
        st.session_state.tabuleiro[ia_r][ia_c] = JOGADOR_IA

        if verificar_vitoria(st.session_state.tabuleiro, JOGADOR_IA):
            st.session_state.mensagem = "🤖 Fim de jogo. A Máquina venceu!"
            st.session_state.placar["IA"] += 1
            st.session_state.game_over = True
            return


# --- INTERFACE VISUAL (STREAMLIT) ---
st.title("🕹️ Jogo da Velha vs IA")
st.markdown("Mostre que a humanidade ainda tem salvação!")

# Menu Lateral (Configurações e Placar)
with st.sidebar:
    st.header("⚙️ Configurações")
    dificuldade = st.radio("Inteligência da IA:", ("Fácil", "Impossível"), index=1)
    quem_comeca = st.radio(
        "Quem começa jogando?", ("Você (❌)", "Máquina (⭕)"), index=0
    )

    # Botão para aplicar quem começa e reiniciar
    ia_first = quem_comeca == "Máquina (⭕)"
    st.button(
        "🔄 Aplicar e Reiniciar",
        on_click=reiniciar_jogo,
        args=(ia_first, dificuldade),
        use_container_width=True,
    )

    st.divider()
    st.header("🏆 Placar Global")
    col1, col2 = st.columns(2)
    col1.metric("Você (❌)", st.session_state.placar["Humano"])
    col2.metric("IA (⭕)", st.session_state.placar["IA"])
    st.metric("Empates", st.session_state.placar["Empate"])

# Centralizando o tabuleiro usando colunas (Layout 1 - 2 - 1)
espaco_esq, area_tabuleiro, espaco_dir = st.columns([1, 2, 1])

with area_tabuleiro:
    for r in range(3):
        cols = st.columns(3)
        for c in range(3):
            conteudo = st.session_state.tabuleiro[r][c]
            label = (
                conteudo if conteudo != VAZIO else "⠀"
            )  # Caractere invisível para manter tamanho

            with cols[c]:
                st.button(
                    label,
                    key=f"btn_{r}_{c}",
                    on_click=processar_turno,
                    args=(r, c, dificuldade),
                    disabled=st.session_state.game_over or conteudo != VAZIO,
                    use_container_width=True,
                )

# Área de Mensagens e Reinício
st.write("")
if st.session_state.game_over:
    if "🎉" in st.session_state.mensagem:
        st.success(st.session_state.mensagem, icon="🏆")
    elif "🤖" in st.session_state.mensagem:
        st.error(st.session_state.mensagem, icon="💀")
    else:
        st.info(st.session_state.mensagem, icon="🤝")

    # Botão de jogar novamente chamando a função de reiniciar preservando quem começa
    st.button(
        "🎮 Jogar Novamente",
        on_click=reiniciar_jogo,
        args=(ia_first, dificuldade),
        type="primary",
        use_container_width=True,
    )
