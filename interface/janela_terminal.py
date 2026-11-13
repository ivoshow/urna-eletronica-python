"""Janela do terminal do mesário.

À esquerda, o aparelho (display, teclado e leitor biométrico) usado para
identificar o eleitor e liberar a urna. À direita, o painel do presidente da
mesa (cabo, abertura, encerramento, boletim), o caderno de votação e o log.
"""

from enum import Enum, auto

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QFrame, QGridLayout, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QListWidget, QMainWindow, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from modelo.erros import (
    EleitorJaVotou, EleitorNaoEncontrado, ErroUrna, SenhaIncorreta, UrnaDesconectada,
    UrnaOcupada, VotacaoEncerrada, VotacaoNaoIniciada,
)
from modelo.pessoas import Eleitor
from modelo.urna import EstadoUrna

from .creditos import Creditos
from .desenho import Pincel
from .dialogo_documento import DialogoDocumento


class Modo(Enum):
    TITULO = auto()             # digitando o título
    CONFIRMAR_ELEITOR = auto()  # mostra o nome, aguarda CONFIRMA
    BIOMETRIA = auto()          # aguardando o dedo no leitor
    LENDO = auto()              # lendo a digital
    VOTANDO = auto()            # urna liberada, eleitor votando
    MENSAGEM = auto()           # aviso temporário no display
    SENHA = auto()              # presidente digitando a senha (abrir ou encerrar)


class Led(QWidget):
    """Luz indicadora com um rótulo."""

    def __init__(self, rotulo, cor="#35d04a"):
        super().__init__()
        self._rotulo, self._cor, self._ligado = rotulo, QColor(cor), False
        self.setFixedHeight(22)

    def sizeHint(self):
        return QSize(len(self._rotulo) * 7 + 26, 22)

    def definir(self, ligado):
        if ligado != self._ligado:
            self._ligado = ligado
            self.update()

    def paintEvent(self, _evento):
        p = Pincel(self)
        centro = QPointF(9, self.height() / 2)
        if self._ligado:
            brilho = QColor(self._cor)
            brilho.setAlpha(80)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(brilho)
            p.drawEllipse(centro, 9, 9)
        p.setPen(QPen(QColor("#111"), 1))
        p.setBrush(self._cor if self._ligado else QColor("#4d544d"))
        p.drawEllipse(centro, 5.5, 5.5)
        p.escrever(QRectF(20, 0, self.width() - 20, self.height()), self._rotulo, 11, True, "#d5d9dd")


class LeitorBiometrico(QWidget):
    """Leitor de digital simulado: clique nele para "encostar o dedo"."""

    tocado = Signal()

    def __init__(self):
        super().__init__()
        self.setFixedSize(150, 118)
        self._estado = "inativo"     # inativo | aguardando | lendo | ok
        self._fase = 0
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._animar)

    def definir_estado(self, estado):
        self._estado = estado
        self._fase = 0
        ativo = estado in ("aguardando", "lendo")
        self._timer.start() if ativo else self._timer.stop()
        self.setCursor(Qt.CursorShape.PointingHandCursor if estado == "aguardando"
                       else Qt.CursorShape.ArrowCursor)
        self.update()

    def _animar(self):
        self._fase = (self._fase + 1) % 50
        self.update()

    def mousePressEvent(self, _evento):
        if self._estado == "aguardando":
            self.tocado.emit()

    def paintEvent(self, _evento):
        p = Pincel(self)
        corpo = QRectF(2, 2, self.width() - 4, self.height() - 4)
        p.setPen(QPen(QColor("#0b0d0f"), 2))
        p.setBrush(QColor("#1a1d21"))
        p.drawRoundedRect(corpo, 14, 14)

        cores = {"inativo": "#3c4852", "aguardando": "#4fc3f7", "lendo": "#4fc3f7", "ok": "#5fd16b"}
        cor = QColor(cores[self._estado])
        if self._estado == "aguardando":  # pulsa para chamar atenção
            cor.setAlpha(110 + int(145 * abs(25 - self._fase) / 25))

        sensor = QRectF(corpo.center().x() - 30, 12, 60, 74)
        p.setPen(QPen(QColor("#0b0d0f"), 2))
        p.setBrush(QColor("#0f1417"))
        p.drawRoundedRect(sensor, 26, 26)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(cor, 1.6))
        for i in range(6):  # sulcos da digital
            r = sensor.adjusted(8 + i * 4, 8 + i * 5, -8 - i * 4, -8 - i * 5)
            p.drawArc(r, 20 * 16, 320 * 16)
        if self._estado == "lendo":
            y = sensor.top() + 6 + (sensor.height() - 12) * (self._fase / 49)
            p.setPen(QPen(QColor("#b3ecff"), 2.4))
            p.drawLine(QPointF(sensor.left() + 6, y), QPointF(sensor.right() - 6, y))
        rotulos = {"inativo": "LEITOR BIOMÉTRICO", "aguardando": "TOQUE AQUI",
                   "lendo": "LENDO...", "ok": "DIGITAL CONFERIDA"}
        p.escrever(QRectF(0, 90, self.width(), 20), rotulos[self._estado], 10, True,
              "#c9d2d9" if self._estado == "inativo" else cor.name(), Pincel.CENTRO)


class JanelaTerminal(QMainWindow):
    """Terminal do mesário + painel do presidente da mesa."""

    COLUNAS_DISPLAY = 24
    TAMANHO_MAX_SENHA = 8

    ESTILO = """
#corpoTerminal {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3b4047, stop:1 #22262b);
    border: 1px solid #111417; border-radius: 22px;
}
#tituloTerminal { color: #e9e9e9; font-size: 15px; font-weight: bold; letter-spacing: 3px; }
#subtituloTerminal { color: #8d949c; font-size: 11px; }
#display {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #c8dba6, stop:1 #a7c085);
    color: #18240f; border: 7px solid #101214; border-radius: 10px; padding: 8px 12px;
    font-family: "DejaVu Sans Mono", "Liberation Mono", monospace;
    font-size: 19px; font-weight: bold;
}
#dica { color: #9aa1a8; font-size: 11px; }
QPushButton[tipo="digito"] {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4d4d4d, stop:1 #191919);
    color: white; font-size: 22px; font-weight: bold;
    border: 1px solid #050505; border-radius: 9px; min-height: 46px; min-width: 66px;
}
QPushButton[tipo="digito"]:pressed { background: #0d0d0d; padding-top: 4px; }
QPushButton[tipo="corrige"] {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f7964a, stop:1 #d9641a);
    color: #111; font-size: 13px; font-weight: bold;
    border: 1px solid #5a2a08; border-radius: 9px; min-height: 46px;
}
QPushButton[tipo="confirma"] {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #5fcf6b, stop:1 #2e9a3b);
    color: #111; font-size: 13px; font-weight: bold;
    border: 1px solid #124d19; border-radius: 9px; min-height: 46px;
}
QPushButton[tipo="corrige"]:pressed, QPushButton[tipo="confirma"]:pressed { padding-top: 4px; }
QPushButton[tipo="painel"] { padding: 7px 10px; font-weight: bold; }
"""

    def __init__(self, terminal, urna, sons, exportador):
        super().__init__()
        self.terminal = terminal
        self.urna = urna
        self.sons = sons
        self.exportador = exportador
        s = urna.eleicao.secao
        self.setWindowTitle(f"Terminal do Mesário — Zona {s.zona} / Seção {s.numero} — "
                            f"{urna.eleicao.turno}º turno")
        self.setStyleSheet(self.ESTILO)

        self._modo = Modo.TITULO
        self._titulo = ""
        self._senha = ""
        self._acao_senha = "encerrar"   # "abrir" ou "encerrar"
        self._eleitor = None
        self._linhas_msg = []
        self._msg_id = 0
        self.ao_simular_queda = None   # função chamada pelo botão "Simular queda de energia"

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)
        layout.addWidget(self._montar_aparelho())
        layout.addWidget(self._montar_painel(), 1)
        self.setCentralWidget(central)
        Creditos.instalar_rodape(self)
        self.atualizar()

    # ================================================================ montagem
    def _montar_aparelho(self):
        corpo = QFrame()
        corpo.setObjectName("corpoTerminal")
        corpo.setFixedWidth(400)
        lay = QVBoxLayout(corpo)
        lay.setContentsMargins(26, 20, 26, 20)
        lay.setSpacing(12)

        titulo = QLabel("TERMINAL DO MESÁRIO")
        titulo.setObjectName("tituloTerminal")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub = QLabel("Identificação do eleitor e liberação da urna")
        sub.setObjectName("subtituloTerminal")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(titulo)
        lay.addWidget(sub)

        leds = QHBoxLayout()
        self.led_cabo = Led("URNA CONECTADA")
        self.led_aberta = Led("VOTAÇÃO ABERTA")
        self.led_votando = Led("VOTANDO", "#ffb300")
        for led in (self.led_cabo, self.led_aberta, self.led_votando):
            leds.addWidget(led)
        lay.addLayout(leds)

        self.display = QLabel()
        self.display.setObjectName("display")
        self.display.setTextFormat(Qt.TextFormat.PlainText)
        self.display.setFixedHeight(132)
        lay.addWidget(self.display)

        grade = QGridLayout()
        grade.setSpacing(10)
        for i, d in enumerate("123456789"):
            grade.addWidget(self._botao(d, "digito"), i // 3, i % 3)
        grade.addWidget(self._botao("CORRIGE", "corrige"), 3, 0)
        grade.addWidget(self._botao("0", "digito"), 3, 1)
        grade.addWidget(self._botao("CONFIRMA", "confirma"), 3, 2)
        lay.addLayout(grade)

        self.leitor = LeitorBiometrico()
        self.leitor.tocado.connect(self._ler_digital)
        linha_leitor = QHBoxLayout()
        linha_leitor.addStretch()
        linha_leitor.addWidget(self.leitor)
        linha_leitor.addStretch()
        lay.addLayout(linha_leitor)

        dica = QLabel("Digite o título (ou clique no caderno) e aperte CONFIRMA.\n"
                      "Teclado do computador: 0-9, Enter, Backspace.")
        dica.setObjectName("dica")
        dica.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(dica)
        lay.addStretch()
        return corpo

    def _botao(self, rotulo, tipo):
        b = QPushButton(rotulo)
        b.setProperty("tipo", tipo)
        b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(lambda: self._tecla(rotulo))
        return b

    def _montar_painel(self):
        painel = QWidget()
        lay = QVBoxLayout(painel)
        lay.setContentsMargins(0, 0, 0, 0)

        # ----- presidente da mesa
        grupo = QGroupBox("Presidente da mesa")
        g = QVBoxLayout(grupo)
        linha = QHBoxLayout()
        self.lbl_cabo = QLabel()
        self.btn_cabo = QPushButton()
        self.btn_cabo.setProperty("tipo", "painel")
        self.btn_cabo.clicked.connect(self._alternar_cabo)
        linha.addWidget(self.lbl_cabo, 1)
        linha.addWidget(self.btn_cabo)
        g.addLayout(linha)

        botoes = QHBoxLayout()
        self.btn_abrir = QPushButton("Abrir votação\n(emitir zerésima)")
        self.btn_encerrar = QPushButton("Encerrar votação\n(emitir BU)")
        self.btn_bu = QPushButton("Ver documentos\nemitidos")
        for b, acao in ((self.btn_abrir, self._abrir), (self.btn_encerrar, self._encerrar),
                        (self.btn_bu, self._ver_documentos)):
            b.setProperty("tipo", "painel")
            b.clicked.connect(acao)
            botoes.addWidget(b)
        g.addLayout(botoes)
        botoes2 = QHBoxLayout()
        self.btn_interromper = QPushButton("Interromper votação\ndo eleitor (desistência)")
        self.btn_queda = QPushButton("⚡ Simular queda\nde energia")
        for b, acao in ((self.btn_interromper, self._interromper), (self.btn_queda, self._simular_queda)):
            b.setProperty("tipo", "painel")
            b.clicked.connect(acao)
            botoes2.addWidget(b)
        g.addLayout(botoes2)
        self.lbl_stats = QLabel()
        g.addWidget(self.lbl_stats)
        lay.addWidget(grupo)

        # ----- caderno de votação
        grupo = QGroupBox("Caderno de votação da seção")
        g = QVBoxLayout(grupo)
        self.tabela = QTableWidget(0, 4)
        self.tabela.setHorizontalHeaderLabels(["Título", "Eleitor", "Biometria", "Situação"])
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabela.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tabela.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        cab = self.tabela.horizontalHeader()
        cab.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        cab.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabela.cellClicked.connect(self._usar_caderno)
        g.addWidget(self.tabela)
        dica = QLabel("Clique em um eleitor para preencher o título no terminal.")
        dica.setStyleSheet("color: gray; font-size: 11px;")
        g.addWidget(dica)
        lay.addWidget(grupo, 3)

        # ----- log
        grupo = QGroupBox("Registro de eventos da urna (log)")
        g = QVBoxLayout(grupo)
        self.lista_log = QListWidget()
        self.lista_log.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        g.addWidget(self.lista_log)
        lay.addWidget(grupo, 2)
        return painel

    # ================================================================ teclado
    def keyPressEvent(self, evento):
        k, letra = evento.key(), evento.text()
        if len(letra) == 1 and letra.isdigit():
            self._tecla(letra)
        elif k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._tecla("CONFIRMA")
        elif k == Qt.Key.Key_Backspace and self._modo is Modo.TITULO:
            self._titulo = self._titulo[:-1]
            self._atualizar_display()
        elif k == Qt.Key.Key_Backspace and self._modo is Modo.SENHA:
            self._senha = self._senha[:-1]
            self._atualizar_display()
        elif k in (Qt.Key.Key_Escape, Qt.Key.Key_Delete):
            self._tecla("CORRIGE")
        else:
            super().keyPressEvent(evento)

    def _tecla(self, nome):
        estado = self.urna.estado
        if self._modo is Modo.MENSAGEM:
            if nome == "CORRIGE":
                self._voltar_titulo()
            return
        if self._modo is Modo.SENHA:
            self._tecla_senha(nome)
            self._atualizar_display()
            return
        if estado is EstadoUrna.PREPARADA:
            self._mensagem(["VOTAÇÃO NÃO INICIADA", "", "O PRESIDENTE DA MESA", "DEVE ABRIR A VOTAÇÃO"])
            return
        if estado is EstadoUrna.ENCERRADA:
            self._mensagem(["VOTAÇÃO ENCERRADA", "", "NENHUM ELEITOR PODE", "MAIS SER LIBERADO"])
            return

        if self._modo is Modo.TITULO:
            if nome.isdigit():
                if len(self._titulo) < Eleitor.DIGITOS_TITULO:
                    self._titulo += nome
                    self.sons.tocar("tecla")
            elif nome == "CORRIGE":
                self._titulo = ""
                self.sons.tocar("tecla")
            elif nome == "CONFIRMA":
                self._consultar()
        elif self._modo is Modo.CONFIRMAR_ELEITOR:
            if nome == "CONFIRMA":
                self._prosseguir()
            elif nome == "CORRIGE":
                self._voltar_titulo()
        elif self._modo is Modo.BIOMETRIA and nome == "CORRIGE":
            self.leitor.definir_estado("inativo")
            self._voltar_titulo()
        elif self._modo is Modo.VOTANDO:
            self.sons.tocar("erro")
        self._atualizar_display()

    # ================================================================ fluxo do eleitor
    def _consultar(self):
        if len(self._titulo) != Eleitor.DIGITOS_TITULO:
            self._mensagem(["TÍTULO INCOMPLETO", "", f"DIGITE OS {Eleitor.DIGITOS_TITULO} DÍGITOS",
                            "DO TÍTULO DE ELEITOR"])
            return
        try:
            eleitor = self.terminal.consultar(self._titulo)
            self.terminal.verificar_urna_pronta()
        except EleitorNaoEncontrado:
            self._mensagem(["ELEITOR NÃO ENCONTRADO", "", "TÍTULO NÃO PERTENCE", "A ESTA SEÇÃO"])
        except EleitorJaVotou as erro:
            self._titulo = ""        # não há o que corrigir: limpa para o próximo eleitor
            self._mensagem(["ELEITOR JÁ VOTOU", "", self._cortar(str(erro).replace(" já votou.", "")),
                            "VOTO NÃO PERMITIDO"])
        except UrnaDesconectada:
            self._mensagem(["URNA NÃO CONECTADA", "", "CONECTE O CABO ENTRE", "TERMINAL E URNA"])
        except UrnaOcupada:
            self._mensagem(["URNA OCUPADA", "", "AGUARDE O ELEITOR", "TERMINAR DE VOTAR"])
        except (VotacaoNaoIniciada, VotacaoEncerrada) as erro:
            self._mensagem(["URNA INDISPONÍVEL", "", self._cortar(str(erro)), ""])
        else:
            self._eleitor = eleitor
            self._modo = Modo.CONFIRMAR_ELEITOR
            self.sons.tocar("tecla")

    def _prosseguir(self):
        """Com biometria: vai para o leitor. Sem biometria: o mesário já conferiu o documento."""
        if self._eleitor.possui_biometria:
            self._modo = Modo.BIOMETRIA
            self.leitor.definir_estado("aguardando")
            self.sons.tocar("tecla")
        else:
            self._liberar(digital_conferida=False)

    def _ler_digital(self):
        if self._modo is not Modo.BIOMETRIA:
            return
        self._modo = Modo.LENDO
        self.leitor.definir_estado("lendo")
        self._atualizar_display()
        QTimer.singleShot(1300, lambda: self._liberar(digital_conferida=True))

    def _liberar(self, digital_conferida):
        if self._modo not in (Modo.CONFIRMAR_ELEITOR, Modo.LENDO):
            return
        try:
            self.terminal.liberar(self._eleitor, digital_conferida)
        except ErroUrna as erro:
            self.leitor.definir_estado("inativo")
            motivo = "URNA NÃO CONECTADA" if isinstance(erro, UrnaDesconectada) else "NÃO LIBERADO"
            self._mensagem([motivo, "", *self._quebrar(str(erro))[:2]])
            return
        if digital_conferida:
            self.leitor.definir_estado("ok")
            QTimer.singleShot(1200, lambda: self.leitor.definir_estado("inativo"))
        self._modo = Modo.VOTANDO
        self._titulo = ""
        self.sons.tocar("liberado")
        self.atualizar()

    def _voltar_titulo(self):
        self._modo = Modo.TITULO
        self._eleitor = None
        self._atualizar_display()

    def _usar_caderno(self, linha, _coluna):
        if self._modo is not Modo.TITULO:
            return
        item = self.tabela.item(linha, 0)
        if item:
            self._titulo = item.data(Qt.ItemDataRole.UserRole)
            self._atualizar_display()

    # ================================================================ display
    def _cortar(self, s):
        return s.upper()[:self.COLUNAS_DISPLAY]

    def _quebrar(self, s):
        palavras, linhas, atual = s.upper().split(), [], ""
        for p in palavras:
            if len(atual) + len(p) + 1 > self.COLUNAS_DISPLAY:
                linhas.append(atual)
                atual = p
            else:
                atual = f"{atual} {p}".strip()
        return linhas + [atual] if atual else linhas

    def _mensagem(self, linhas, ms=2800, som="erro"):
        self._modo = Modo.MENSAGEM
        self._linhas_msg = linhas
        self._msg_id += 1
        ident = self._msg_id
        if som:
            self.sons.tocar(som)
        QTimer.singleShot(ms, lambda: self._fim_mensagem(ident))
        self._atualizar_display()

    def _fim_mensagem(self, ident):
        if ident != self._msg_id or self._modo is not Modo.MENSAGEM:
            return
        if self.urna.estado is EstadoUrna.VOTANDO and self._eleitor is not None:
            self._modo = Modo.VOTANDO     # aviso durante a votação: volta a "ELEITOR VOTANDO"
            self._atualizar_display()
        else:
            self._voltar_titulo()

    def _titulo_mascarado(self):
        t = self._titulo.ljust(Eleitor.DIGITOS_TITULO, "_")
        return f"{t[0:4]} {t[4:8]} {t[8:12]}"

    def _atualizar_display(self):
        u = self.urna
        s = u.eleicao.secao
        if self._modo is Modo.MENSAGEM:
            linhas = self._linhas_msg
        elif self._modo is Modo.SENHA:
            mascara = "*" * len(self._senha) if self._senha else "_"
            acao = {"abrir": "ABRIR VOTAÇÃO", "encerrar": "ENCERRAR VOTAÇÃO",
                    "interromper": "INTERROMPER VOTAÇÃO"}[self._acao_senha]
            linhas = [acao, "SENHA DO PRESIDENTE:", "  " + mascara, "CONFIRMA=OK CORRIGE=SAIR"]
        elif u.estado is EstadoUrna.PREPARADA:
            linhas = ["VOTAÇÃO NÃO INICIADA", "", "AGUARDANDO ABERTURA", "PELO PRESIDENTE"]
        elif u.estado is EstadoUrna.ENCERRADA:
            linhas = ["VOTAÇÃO ENCERRADA", "",
                      f"COMPARECIMENTO {u.eleicao.comparecimento}/{u.eleicao.aptos}", "BU EMITIDO"]
        elif self._modo is Modo.TITULO:
            topo = f"ZONA {s.zona}  SEÇÃO {s.numero}" if self.terminal.conectado else "!! URNA DESCONECTADA !!"
            linhas = [topo, "TÍTULO DO ELEITOR:", "  " + self._titulo_mascarado(),
                      "CONFIRMA = CONSULTAR"]
        elif self._modo is Modo.CONFIRMAR_ELEITOR:
            e = self._eleitor
            if e.possui_biometria:
                linhas = ["ELEITOR:", self._cortar(e.nome), f"TIT {e.titulo_formatado}",
                          "CONFIRMA=BIOMETRIA"]
            else:
                linhas = ["SEM BIOMETRIA:", self._cortar(e.nome), "CONFIRA DOC. COM FOTO",
                          "CONFIRMA=LIBERAR"]
        elif self._modo is Modo.BIOMETRIA:
            linhas = ["POSICIONE O DEDO NO", "LEITOR BIOMÉTRICO", self._cortar(self._eleitor.nome),
                      "CORRIGE = CANCELAR"]
        elif self._modo is Modo.LENDO:
            linhas = ["LENDO DIGITAL...", "", "NÃO RETIRE O DEDO", ""]
        else:  # VOTANDO
            linhas = ["URNA LIBERADA", self._cortar(self._eleitor.nome if self._eleitor else ""),
                      "ELEITOR VOTANDO...", ""]
        linhas = (list(linhas) + [""] * 4)[:4]
        self.display.setText("\n".join(l[:self.COLUNAS_DISPLAY] for l in linhas))

    # ================================================================ presidente da mesa
    def _alternar_cabo(self):
        if self.terminal.conectado:
            self.terminal.desconectar()
        else:
            self.terminal.conectar(self.urna)
            self.sons.tocar("liberado")

    # ---------------------------------------------------------------- senha do presidente
    def _abrir(self):
        """Pede no visor a senha do presidente para abrir a votação (emite a zerésima)."""
        if self.urna.estado is not EstadoUrna.PREPARADA:
            return
        if not self.terminal.conectado:
            self._mensagem(["URNA NÃO CONECTADA", "", "CONECTE O CABO ANTES", "DE ABRIR A VOTAÇÃO"])
            return
        self._pedir_senha("abrir")

    def _encerrar(self):
        """Pede no visor a senha do presidente para encerrar a votação (emite o BU)."""
        if self.urna.estado is not EstadoUrna.AGUARDANDO_ELEITOR:
            return
        self._pedir_senha("encerrar")

    def _interromper(self):
        """Eleitor desistiu ou abandonou a cabine: o presidente finaliza a votação dele."""
        if self.urna.estado is not EstadoUrna.VOTANDO:
            return
        self._pedir_senha("interromper")

    def _pedir_senha(self, acao):
        """Coloca o terminal no modo SENHA para "abrir", "encerrar" ou "interromper"."""
        if acao != "interromper":                # na interrupção o eleitor continua na urna
            self.leitor.definir_estado("inativo")   # cancela um atendimento no meio
            self._eleitor = None
        self._msg_id += 1                        # descarta aviso pendente no display
        self._senha = ""
        self._acao_senha = acao
        self._modo = Modo.SENHA
        self.sons.tocar("tecla")
        self.activateWindow()
        self.setFocus()                          # para aceitar também o teclado do computador
        self._atualizar_display()

    def _tecla_senha(self, nome):
        if nome.isdigit():
            if len(self._senha) < self.TAMANHO_MAX_SENHA:
                self._senha += nome
                self.sons.tocar("tecla")
        elif nome == "CORRIGE":                  # sai sem fazer nada
            self._senha = ""
            self.sons.tocar("tecla")
            if self._acao_senha == "interromper":
                self._modo = Modo.VOTANDO
                self._atualizar_display()
            else:
                self._voltar_titulo()
        elif nome == "CONFIRMA":
            self._confirmar_senha()

    def _confirmar_senha(self):
        if self._acao_senha == "interromper":
            self._confirmar_interrupcao()
            return
        senha, self._senha = self._senha, ""    # não guarda a senha depois de usar
        abrir = self._acao_senha == "abrir"
        try:
            if abrir:
                documento = self.terminal.abrir_votacao(senha)
            else:
                documento = self.terminal.encerrar_votacao(senha)
        except SenhaIncorreta:
            if abrir:
                self._mensagem(["SENHA INCORRETA", "", "ABERTURA", "NÃO AUTORIZADA"])
            else:
                self._mensagem(["SENHA INCORRETA", "", "ENCERRAMENTO", "NÃO AUTORIZADO"])
            return
        except ErroUrna as erro:
            self._mensagem(["NÃO FOI POSSÍVEL", "ABRIR" if abrir else "ENCERRAR",
                            *self._quebrar(str(erro))[:2]])
            return
        self.sons.tocar("liberado")
        self._voltar_titulo()
        self._exibir(documento)

    def _confirmar_interrupcao(self):
        senha, self._senha = self._senha, ""
        nome = self._cortar(self._eleitor.nome if self._eleitor else "")
        try:
            resultado = self.terminal.interromper_votacao(senha)
        except SenhaIncorreta:
            self._mensagem(["SENHA INCORRETA", "", "INTERRUPÇÃO", "NÃO AUTORIZADA"])
            return
        except ErroUrna as erro:
            self._mensagem(["NÃO FOI POSSÍVEL", "INTERROMPER", *self._quebrar(str(erro))[:2]])
            return
        self._eleitor = None
        if resultado.eleitor_votou:
            self._mensagem(["VOTAÇÃO INTERROMPIDA", nome, f"{resultado.anulados} VOTO(S) NULO(S)",
                            "CONSTA COMO VOTOU"], ms=4500, som="liberado")
        else:
            self._mensagem(["VOTAÇÃO SUSPENSA", nome, "NENHUM VOTO CONFIRMADO",
                            "PODE VOTAR DEPOIS"], ms=4500, som="liberado")
        self.atualizar()

    # ---------------------------------------------------------------- queda de energia
    def _simular_queda(self):
        if self.ao_simular_queda is not None:
            self.ao_simular_queda()

    def desligar(self):
        """Sem energia: display apagado e terminal sem resposta."""
        self._msg_id += 1
        self.leitor.definir_estado("inativo")
        for led in (self.led_cabo, self.led_aberta, self.led_votando):
            led.definir(False)
        self.display.setText("")
        self.display.setStyleSheet("background: #1b1f19; color: #1b1f19;")
        self.centralWidget().setEnabled(False)

    def avisar_religamento(self):
        """Depois que a energia volta: resumo do que foi recuperado da memória."""
        el = self.urna.eleicao
        linhas = ["ENERGIA RESTABELECIDA", "DADOS RECUPERADOS",
                  f"COMPARECIMENTO {el.comparecimento}/{el.aptos}", ""]
        pendente = self.urna.pendencia_na_queda
        if pendente is not None:
            linhas[3] = "VOTO PENDENTE CONCLUÍDO" if pendente.eleitor_votou else "VOTO PENDENTE SUSPENSO"
        self._mensagem(linhas, ms=5000, som="liberado")

    def _ver_documentos(self):
        for documento in (self.urna.zeresima, self.urna.boletim):
            if documento is not None:
                self._exibir(documento, salvar=False)

    def _exibir(self, documento, salvar=True):
        caminhos = self.exportador.caminhos(documento)
        if salvar:
            try:
                caminhos = self.exportador.salvar(documento)
            except OSError as erro:
                QMessageBox.warning(self, "Erro ao salvar", f"Não foi possível salvar: {erro}")
        DialogoDocumento(documento, caminhos, self).exec()

    # ================================================================ atualização
    def atualizar(self, evento=None):
        u = self.urna
        if evento == "fim_eleitor" and self._modo is Modo.VOTANDO:
            nome = self._eleitor.nome if self._eleitor else ""
            self._eleitor = None
            self._mensagem(["VOTO CONCLUÍDO", self._cortar(nome), "", "PRÓXIMO ELEITOR"],
                           ms=3200, som="liberado")
        elif evento == "estado" and u.estado is EstadoUrna.ENCERRADA:
            self._msg_id += 1          # descarta aviso pendente no display
            self._voltar_titulo()

        conectado = self.terminal.conectado
        aberta = u.estado in (EstadoUrna.AGUARDANDO_ELEITOR, EstadoUrna.VOTANDO)
        self.led_cabo.definir(conectado)
        self.led_aberta.definir(aberta)
        self.led_votando.definir(u.estado is EstadoUrna.VOTANDO)

        if conectado:
            self.lbl_cabo.setText("<b style='color:#2e9a3b'>●</b> Cabo conectado à urna")
            self.btn_cabo.setText("Desconectar cabo")
        else:
            self.lbl_cabo.setText("<b style='color:#c62828'>●</b> Urna desconectada")
            self.btn_cabo.setText("Conectar cabo")
        self.btn_abrir.setEnabled(u.estado is EstadoUrna.PREPARADA)
        self.btn_encerrar.setEnabled(u.estado is EstadoUrna.AGUARDANDO_ELEITOR)
        self.btn_bu.setEnabled(u.zeresima is not None)
        self.btn_interromper.setEnabled(u.estado is EstadoUrna.VOTANDO)

        el = u.eleicao
        self.lbl_stats.setText(
            f"Eleitores aptos: <b>{el.aptos}</b> &nbsp;&nbsp; Compareceram: <b>{el.comparecimento}</b>"
            f" &nbsp;&nbsp; Faltam: <b>{el.aptos - el.comparecimento}</b>")
        self._atualizar_caderno()
        self._atualizar_log()
        self._atualizar_display()

    def _atualizar_caderno(self):
        eleitores = self.urna.eleicao.eleitores
        self.tabela.setRowCount(len(eleitores))
        votando = self._eleitor if self._modo is Modo.VOTANDO else None
        for linha, e in enumerate(eleitores):
            if e.votou:
                situacao, cor = "✔ Votou", QColor("#2e9a3b")
            elif e is votando:
                situacao, cor = "Votando…", QColor("#d98c00")
            else:
                situacao, cor = "Aguardando", None
            itens = [e.titulo_formatado, e.nome, "Sim" if e.possui_biometria else "Não", situacao]
            for coluna, valor in enumerate(itens):
                item = QTableWidgetItem(valor)
                if coluna == 0:
                    item.setData(Qt.ItemDataRole.UserRole, e.titulo)
                if coluna == 3 and cor is not None:
                    item.setForeground(cor)
                self.tabela.setItem(linha, coluna, item)

    def _atualizar_log(self):
        log = self.urna.log
        if self.lista_log.count() == len(log):
            return
        self.lista_log.clear()
        for momento, mensagem in log:
            self.lista_log.addItem(f"{momento:%H:%M:%S}   {mensagem}")
        self.lista_log.scrollToBottom()

    def closeEvent(self, evento):
        evento.accept()
        QApplication.quit()
