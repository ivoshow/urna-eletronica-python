"""
SIMULADOR DE URNA ELETRÔNICA — Projeto Integrador

Abre duas janelas, como numa seção eleitoral de verdade:
  * Terminal do Mesário: identifica o eleitor (título + biometria ou documento) e libera a urna
  * Urna Eletrônica: o eleitor vota em cada cargo; no final aparece FIM

Sem o cabo conectado e sem a liberação do mesário, a urna não aceita votos.
No encerramento é emitido o Boletim de Urna (salvo em boletins/ como .txt e .pdf).
A urna grava seu estado em memoria/ e se recupera de uma queda de energia.

Como rodar (dentro desta pasta):
    python main.py           # com sons
    python main.py --mudo    # sem sons
    python main.py --nova    # apaga a memória e começa uma votação nova
    python main.py --eleicao dados/eleicao_2turno.json   # outra eleição (ex.: 2º turno)
"""

import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from interface.exportar import ExportadorDocumento
from interface.janela_terminal import JanelaTerminal
from interface.janela_urna import JanelaUrna
from interface.sons import Sons
from modelo.carregador import CarregadorEleicao
from modelo.memoria import MemoriaUrna
from modelo.terminal import TerminalMesario
from modelo.urna import Urna


class Aplicacao:
    """Monta o simulador: cria o modelo, as duas janelas e liga uma à outra."""

    PASTA = Path(__file__).resolve().parent
    SEGUNDOS_SEM_ENERGIA = 3

    def __init__(self, argumentos):
        self.__qt = QApplication(argumentos)
        self.__qt.setStyle("Fusion")
        self.__qt.setApplicationName("Simulador de Urna Eletrônica")

        self.__arquivo_eleicao = self.__escolher_eleicao(argumentos)
        self.__sons = Sons(ativo="--mudo" not in argumentos)
        self.__exportador = ExportadorDocumento(self.PASTA / "boletins")
        self.__janelas_desligadas = []   # janelas da "vida anterior" da urna (ficam ocultas)

        eleicao = CarregadorEleicao(self.__arquivo_eleicao).carregar()
        secao = eleicao.secao
        # um arquivo de memória por seção E por turno: 1º e 2º turno nunca se misturam
        self.__memoria = MemoriaUrna(self.PASTA / "memoria" /
                                     f"urna_Z{secao.zona}_S{secao.numero}_T{eleicao.turno}.json")
        self.__preparar_memoria(argumentos)
        self.__montar()

    # ------------------------------------------------------------ montagem
    def __escolher_eleicao(self, argumentos):
        """--eleicao <arquivo> escolhe outro JSON (ex.: 2º turno); o padrão é dados/eleicao.json."""
        if "--eleicao" in argumentos:
            indice = argumentos.index("--eleicao")
            if indice + 1 >= len(argumentos):
                raise SystemExit("Uso: python main.py --eleicao dados/eleicao_2turno.json")
            caminho = Path(argumentos[indice + 1])
            return caminho if caminho.is_absolute() else Path.cwd() / caminho
        return self.PASTA / "dados" / "eleicao.json"

    def __preparar_memoria(self, argumentos):
        """Se já existe uma votação gravada, pergunta se continua ou começa outra."""
        if "--nova" in argumentos:
            self.__memoria.apagar()
            return
        if not self.__memoria.existe():
            return
        caixa = QMessageBox(QMessageBox.Icon.Question, "Memória da urna",
                            "A memória da urna tem uma votação gravada.\n\n"
                            "Deseja continuar essa votação ou começar uma nova (apagando a memória)?")
        continuar = caixa.addButton("Continuar votação gravada", QMessageBox.ButtonRole.AcceptRole)
        caixa.addButton("Nova votação", QMessageBox.ButtonRole.DestructiveRole)
        caixa.exec()
        if caixa.clickedButton() is not continuar:
            self.__memoria.apagar()

    def __montar(self):
        """Cria modelo e janelas. A Urna lê a memória: se houver dados, ela se recupera."""
        eleicao = CarregadorEleicao(self.__arquivo_eleicao).carregar()
        try:
            self.urna = Urna(eleicao, self.__memoria)
        except (ValueError, KeyError) as erro:
            QMessageBox.warning(None, "Memória da urna",
                                f"A memória gravada não pôde ser lida e foi descartada.\n\n{erro}")
            self.__memoria.apagar()
            eleicao = CarregadorEleicao(self.__arquivo_eleicao).carregar()
            self.urna = Urna(eleicao, self.__memoria)
        self.terminal = TerminalMesario(eleicao)
        if self.urna.conectada:             # o cabo continua fisicamente ligado
            self.terminal.conectar(self.urna)

        self.janela_urna = JanelaUrna(self.urna, self.__sons)
        self.janela_terminal = JanelaTerminal(self.terminal, self.urna, self.__sons, self.__exportador)
        self.janela_terminal.ao_simular_queda = self.__simular_queda

        # Toda mudança na urna (conexão, liberação, voto, fim) redesenha as duas janelas.
        self.urna.adicionar_ouvinte(self.janela_urna.atualizar)
        self.urna.adicionar_ouvinte(self.janela_terminal.atualizar)

    # ------------------------------------------------------------ queda de energia
    def __simular_queda(self):
        """Apaga as duas janelas; depois de alguns segundos a energia volta."""
        self.janela_urna.desligar()
        self.janela_terminal.desligar()
        QTimer.singleShot(self.SEGUNDOS_SEM_ENERGIA * 1000, self.__religar)

    def __religar(self):
        """Joga fora todos os objetos e recria tudo a partir do JSON + memória da urna."""
        geometria_urna = self.janela_urna.geometry()
        geometria_terminal = self.janela_terminal.geometry()
        antigas = (self.janela_urna, self.janela_terminal)

        self.__montar()

        for janela in antigas:
            janela.hide()
            self.__janelas_desligadas.append(janela)
        self.janela_urna.setGeometry(geometria_urna)
        self.janela_terminal.setGeometry(geometria_terminal)
        self.janela_terminal.show()
        self.janela_urna.show()
        self.janela_urna.avisar_religamento()
        self.janela_terminal.avisar_religamento()

    # ------------------------------------------------------------ execução
    def executar(self):
        self.__posicionar()
        self.janela_terminal.show()
        self.janela_urna.show()
        if self.urna.recuperada:
            self.janela_urna.avisar_religamento()
            self.janela_terminal.avisar_religamento()
        return self.__qt.exec()

    def __posicionar(self):
        """Coloca o terminal à esquerda e a urna à direita, cabendo na tela."""
        tela = self.__qt.primaryScreen().availableGeometry()
        larg_terminal = min(1000, int(tela.width() * 0.45))
        altura = min(780, tela.height() - 40)
        self.janela_terminal.setGeometry(tela.x() + 10, tela.y() + 30, larg_terminal, altura)
        larg_urna = max(720, tela.width() - larg_terminal - 30)
        alt_urna = min(altura, int(larg_urna * 0.62))
        self.janela_urna.setGeometry(tela.x() + larg_terminal + 20, tela.y() + 30,
                                     larg_urna, alt_urna)


if __name__ == "__main__":
    sys.exit(Aplicacao(sys.argv).executar())
