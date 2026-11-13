"""Janela da urna eletrônica: tela à esquerda e teclado à direita.

Tudo é desenhado com o Pincel (um QPainter) em um "papel" de 1200 x 720 unidades, que é
escalado para o tamanho da janela. Assim a urna fica proporcional em qualquer
resolução e os cliques são convertidos de volta para essas coordenadas.
"""

import time
from datetime import datetime

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPen
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget

from modelo.cargo import TipoVoto
from modelo.erros import UrnaBloqueada
from modelo.urna import EstadoUrna

from .creditos import Creditos
from .desenho import Pincel

class TelaUrna(QWidget):
    """Desenha a urna e transforma cliques/teclas em chamadas ao modelo."""

    LARGURA, ALTURA = 1200, 720
    TELA = QRectF(56, 70, 700, 520)
    PAINEL = QRectF(812, 40, 360, 640)
    FIM_SEGUNDOS = 4.0
    BLOQUEIO_SEGUNDOS = 2.5

    # cores (topo do gradiente, base, texto) de cada tipo de tecla
    CORES_TECLAS = {
        "digito": ("#4a4a4a", "#141414", "#ffffff"),
        "BRANCO": ("#ffffff", "#d6d6d6", "#111111"),
        "CORRIGE": ("#f7964a", "#d9641a", "#111111"),
        "CONFIRMA": ("#5fcf6b", "#2e9a3b", "#111111"),
    }

    def __init__(self, urna, sons):
        super().__init__()
        self.urna = urna
        self.sons = sons
        self.setMinimumSize(720, 432)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self._teclas = self._montar_teclas()
        self._pressionada = None
        self._piscar = True
        self._aviso_ate = 0.0
        self._aviso = ("", "", "#b0261e")   # título, subtítulo, cor da faixa
        self._fim_ate = 0.0
        self._sem_energia = False

        self._relogio = QTimer(self)
        self._relogio.setInterval(450)
        self._relogio.timeout.connect(self._tique)
        self._relogio.start()

    def _montar_teclas(self):
        """Posição de cada tecla no painel (mesmo arranjo da urna real)."""
        teclas = {}
        larg, alt, folga = 92, 64, 16
        x0 = self.PAINEL.x() + (self.PAINEL.width() - (3 * larg + 2 * folga)) / 2
        y0 = 170
        for i, digito in enumerate("123456789"):
            lin, col = divmod(i, 3)
            teclas[digito] = QRectF(x0 + col * (larg + folga), y0 + lin * (alt + folga), larg, alt)
        teclas["0"] = QRectF(x0 + larg + folga, y0 + 3 * (alt + folga), larg, alt)
        yb = y0 + 4 * (alt + folga) + 14
        teclas["BRANCO"] = QRectF(824, yb, 100, 66)
        teclas["CORRIGE"] = QRectF(932, yb, 100, 66)
        teclas["CONFIRMA"] = QRectF(1040, yb - 10, 118, 86)
        return teclas

    # ------------------------------------------------------------ tempo
    def _tique(self):
        self._piscar = not self._piscar
        self.update()

    # ------------------------------------------------------------ coordenadas
    def _escala(self):
        e = min(self.width() / self.LARGURA, self.height() / self.ALTURA)
        return e, (self.width() - self.LARGURA * e) / 2, (self.height() - self.ALTURA * e) / 2

    def _tecla_em(self, pos):
        e, dx, dy = self._escala()
        ponto = QPointF((pos.x() - dx) / e, (pos.y() - dy) / e)
        for nome, rect in self._teclas.items():
            if rect.contains(ponto):
                return nome
        return None

    # ------------------------------------------------------------ mouse e teclado
    def mousePressEvent(self, evento):
        self._pressionada = self._tecla_em(evento.position())
        self.update()

    def mouseReleaseEvent(self, evento):
        nome = self._pressionada
        self._pressionada = None
        if nome and nome == self._tecla_em(evento.position()):
            self.acionar(nome)
        self.update()

    def mouseMoveEvent(self, evento):
        sobre = self._tecla_em(evento.position())
        forma = Qt.CursorShape.PointingHandCursor if sobre else Qt.CursorShape.ArrowCursor
        self.setCursor(forma)

    def keyPressEvent(self, evento):
        k, letra = evento.key(), evento.text()
        if len(letra) == 1 and letra.isdigit():
            nome = letra
        elif k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            nome = "CONFIRMA"
        elif k in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete, Qt.Key.Key_Escape):
            nome = "CORRIGE"
        elif k == Qt.Key.Key_Space or letra.lower() == "b":
            nome = "BRANCO"
        else:
            super().keyPressEvent(evento)
            return
        self._pressionada = nome
        QTimer.singleShot(120, self._soltar)
        self.acionar(nome)

    def _soltar(self):
        self._pressionada = None
        self.update()

    def mostrar_aviso(self, titulo, subtitulo, cor, segundos):
        """Mostra uma faixa colorida sobre a tela por alguns segundos."""
        self._aviso = (titulo, subtitulo, cor)
        self._aviso_ate = time.monotonic() + segundos
        self.update()

    def desligar(self):
        """Queda de energia: tela apagada, LEDs desligados e teclado sem resposta."""
        self._sem_energia = True
        self._relogio.stop()
        self.update()

    def acionar(self, nome):
        """Repassa a tecla para a urna e escolhe o som de resposta."""
        if self._sem_energia:
            return
        try:
            if nome.isdigit():
                aceita = self.urna.digitar(nome)
            elif nome == "BRANCO":
                aceita = self.urna.votar_branco()
            elif nome == "CORRIGE":
                aceita = self.urna.corrigir()
            else:
                aceita = self.urna.confirmar() is not None
        except UrnaBloqueada:
            self.sons.tocar("erro")
            self.mostrar_aviso("URNA BLOQUEADA", "Aguarde a liberação pelo mesário", "#b0261e",
                               self.BLOQUEIO_SEGUNDOS)
            return

        if nome == "CONFIRMA" and aceita:
            if self.urna.estado is EstadoUrna.VOTANDO:
                self.sons.tocar("confirma")
            else:  # foi o último cargo: tela FIM
                self.sons.tocar("fim")
                self._fim_ate = time.monotonic() + self.FIM_SEGUNDOS
        elif aceita:
            self.sons.tocar("tecla")
        self.update()

    # ------------------------------------------------------------ desenho
    def paintEvent(self, _evento):
        p = Pincel(self)
        p.fillRect(self.rect(), QColor("#2f353b"))
        e, dx, dy = self._escala()
        p.translate(dx, dy)
        p.scale(e, e)
        self._desenhar_corpo(p)
        self._desenhar_tela(p)
        self._desenhar_teclas(p)
        self._desenhar_leds(p)
        p.end()

    def _desenhar_corpo(self, p):
        corpo = QRectF(8, 8, self.LARGURA - 16, self.ALTURA - 16)
        grad = QLinearGradient(corpo.topLeft(), corpo.bottomLeft())
        grad.setColorAt(0, QColor("#ebe8e1"))
        grad.setColorAt(1, QColor("#c3beb3"))
        p.setPen(QPen(QColor("#8f8a7f"), 2))
        p.setBrush(grad)
        p.drawRoundedRect(corpo, 30, 30)

        # moldura da tela
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#2a2c2e"))
        p.drawRoundedRect(self.TELA.adjusted(-20, -20, 20, 20), 16, 16)

        # painel do teclado
        grad = QLinearGradient(self.PAINEL.topLeft(), self.PAINEL.bottomLeft())
        grad.setColorAt(0, QColor("#2b2b2b"))
        grad.setColorAt(1, QColor("#161616"))
        p.setBrush(grad)
        p.setPen(QPen(QColor("#0c0c0c"), 2))
        p.drawRoundedRect(self.PAINEL, 18, 18)
        p.escrever(QRectF(self.PAINEL.x(), 62, self.PAINEL.width(), 30), "URNA ELETRÔNICA", 24, True,
              "#f2f2f2", Pincel.CENTRO)
        p.escrever(QRectF(self.PAINEL.x(), 94, self.PAINEL.width(), 20), "SIMULADOR  •  USO EDUCACIONAL",
              12, False, "#9a9a9a", Pincel.CENTRO)
        p.setPen(QPen(QColor("#3d3d3d"), 1.5))
        p.drawLine(QPointF(self.PAINEL.x() + 40, 132), QPointF(self.PAINEL.right() - 40, 132))
        p.escrever(QRectF(self.PAINEL.x(), 622, self.PAINEL.width(), 18),
              "Teclado do computador: 0-9, Enter, Backspace, B", 12, False, "#7c7c7c", Pincel.CENTRO)

    def _desenhar_teclas(self, p):
        for nome, rect in self._teclas.items():
            apertada = nome == self._pressionada
            topo, base, cor_texto = self.CORES_TECLAS.get(nome, self.CORES_TECLAS["digito"])
            r = rect.translated(0, 3) if apertada else rect
            p.setPen(Qt.PenStyle.NoPen)
            if not apertada:
                p.setBrush(QColor(0, 0, 0, 120))
                p.drawRoundedRect(rect.translated(0, 5), 10, 10)
            grad = QLinearGradient(r.topLeft(), r.bottomLeft())
            grad.setColorAt(0, QColor(topo).darker(115) if apertada else QColor(topo))
            grad.setColorAt(1, QColor(base))
            p.setBrush(grad)
            p.setPen(QPen(QColor("#050505"), 1.2))
            p.drawRoundedRect(r, 10, 10)
            tamanho = 36 if nome.isdigit() else (19 if nome == "CONFIRMA" else 17)
            p.escrever(r, nome, tamanho, True, cor_texto, Pincel.CENTRO)
            if nome == "5":  # marcação em relevo para deficientes visuais
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor("#9a9a9a"))
                p.drawEllipse(QPointF(r.center().x(), r.top() + 10), 3, 3)

    def _desenhar_leds(self, p):
        u = self.urna
        leds = [
            ("TERMINAL CONECTADO", u.conectada, "#35d04a"),
            ("VOTAÇÃO ABERTA", u.estado in (EstadoUrna.AGUARDANDO_ELEITOR, EstadoUrna.VOTANDO),
             "#35d04a"),
            ("ELEITOR LIBERADO", u.estado is EstadoUrna.VOTANDO, "#ffb300"),
        ]
        if self._sem_energia:
            leds = [(rotulo, False, cor) for rotulo, _, cor in leds]
        x = 70
        for rotulo, ligado, cor in leds:
            centro = QPointF(x, 652)
            if ligado:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(QColor(cor).red(), QColor(cor).green(), QColor(cor).blue(), 70))
                p.drawEllipse(centro, 15, 15)
            p.setPen(QPen(QColor("#555"), 1.2))
            p.setBrush(QColor(cor) if ligado else QColor("#6d736d"))
            p.drawEllipse(centro, 8, 8)
            p.escrever(QRectF(x + 16, 640, 220, 24), rotulo, 14, True, "#4a4740")
            x += 240

    # ------------------------------------------------------------ telas
    def _desenhar_tela(self, p):
        u = self.urna
        agora = time.monotonic()
        p.save()
        p.setClipRect(self.TELA)
        if self._sem_energia:
            p.fillRect(self.TELA, QColor("#050606"))
            p.escrever(self.TELA, "SEM ENERGIA", 30, True, "#2a2d2f", Pincel.CENTRO)
            p.restore()
            return
        if u.estado is EstadoUrna.VOTANDO:
            p.fillRect(self.TELA, QColor("#f7f7f2"))
            self._tela_votacao(p)
        elif u.estado is EstadoUrna.AGUARDANDO_ELEITOR:
            p.fillRect(self.TELA, QColor("#f7f7f2"))
            if agora < self._fim_ate:
                self._tela_fim(p)
            else:
                self._tela_espera(p)
        elif u.estado is EstadoUrna.PREPARADA:
            if u.conectada:
                p.fillRect(self.TELA, QColor("#f7f7f2"))
                self._tela_mensagem(p, "URNA PREPARADA",
                                    ["Aguardando a abertura da votação",
                                     "pelo presidente da mesa"])
            else:
                p.fillRect(self.TELA, QColor("#1c2120"))
                self._tela_mensagem(p, "AGUARDANDO CONEXÃO",
                                    ["Conecte o cabo do terminal do mesário"],
                                    cor="#9fb3aa")
        else:
            p.fillRect(self.TELA, QColor("#f7f7f2"))
            fim = u.encerramento
            self._tela_mensagem(p, "VOTAÇÃO ENCERRADA", [
                f"Encerrada às {fim:%H:%M:%S}" if fim else "",
                f"Comparecimento: {u.eleicao.comparecimento} de {u.eleicao.aptos} eleitores",
                "Boletim de urna emitido",
            ])
        if agora < self._aviso_ate:
            self._faixa_aviso(p)
        p.restore()

    def _rodape_secao(self, p, cor="#555555"):
        s = self.urna.eleicao.secao
        r = self.TELA
        p.escrever(QRectF(r.left(), r.bottom() - 62, r.width(), 22),
              f"Zona {s.zona}  •  Seção {s.numero}  •  {s.municipio}/{s.uf}  •  "
              f"{self.urna.eleicao.turno}º turno", 16, False, cor, Pincel.CENTRO)
        p.escrever(QRectF(r.left(), r.bottom() - 36, r.width(), 22),
              datetime.now().strftime("%d/%m/%Y   %H:%M:%S"), 16, False, cor, Pincel.CENTRO)

    def _tela_mensagem(self, p, titulo, linhas, cor="#1b1b1b"):
        r = self.TELA
        p.escrever(QRectF(r.left(), r.top() + 150, r.width(), 60), titulo, 42, True, cor, Pincel.CENTRO)
        y = r.top() + 225
        for linha in linhas:
            p.escrever(QRectF(r.left(), y, r.width(), 30), linha, 22, False, cor, Pincel.CENTRO)
            y += 34
        self._rodape_secao(p, cor)

    def _tela_espera(self, p):
        r = self.TELA
        # emblema: cédula com um "visto"
        icone = QRectF(r.center().x() - 42, r.top() + 70, 84, 84)
        p.setPen(QPen(QColor("#1b1b1b"), 5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(icone, 12, 12)
        p.drawPolyline([QPointF(icone.left() + 20, icone.center().y() + 2),
                        QPointF(icone.left() + 37, icone.bottom() - 22),
                        QPointF(icone.right() - 18, icone.top() + 22)])
        p.escrever(QRectF(r.left(), r.top() + 175, r.width(), 60), "URNA ELETRÔNICA", 44, True,
              "#1b1b1b", Pincel.CENTRO)
        p.escrever(QRectF(r.left(), r.top() + 245, r.width(), 30),
              "Aguardando liberação do eleitor", 24, False, "#1b1b1b", Pincel.CENTRO)
        p.escrever(QRectF(r.left(), r.top() + 280, r.width(), 30),
              "pelo terminal do mesário", 24, False, "#1b1b1b", Pincel.CENTRO)
        if not self.urna.conectada:
            aviso = QRectF(r.right() - 350, r.top() + 14, 336, 32)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#d9822b"))
            p.drawRoundedRect(aviso, 6, 6)
            p.escrever(aviso, "TERMINAL DO MESÁRIO DESCONECTADO", 14, True, "#ffffff", Pincel.CENTRO)
        self._rodape_secao(p)

    def _tela_fim(self, p):
        p.escrever(self.TELA, "FIM", 210, True, "#1b1b1b", Pincel.CENTRO)

    def _faixa_aviso(self, p):
        titulo, subtitulo, cor = self._aviso
        r = self.TELA
        faixa = QRectF(r.left(), r.center().y() - 64, r.width(), 128)
        fundo = QColor(cor)
        fundo.setAlpha(240)
        p.fillRect(faixa, fundo)
        p.escrever(QRectF(faixa.left(), faixa.top() + 18, faixa.width(), 50), titulo,
                   36, True, "#ffffff", Pincel.CENTRO)
        p.escrever(QRectF(faixa.left(), faixa.top() + 72, faixa.width(), 34),
                   subtitulo, 22, False, "#ffffff", Pincel.CENTRO)

    def _linha_info(self, p, x, y, rotulo, valor):
        p.escrever(QRectF(x, y, 300, 30), rotulo, 20)
        x_valor = x + Pincel.largura(rotulo, 20) + 12
        p.escrever(QRectF(x_valor, y, self.TELA.width() - 260 - (x_valor - x), 30), valor, 22, True)

    def _tela_votacao(self, p):
        r = self.TELA
        sessao = self.urna.sessao
        cargo = sessao.cargo_atual
        previa = sessao.previa
        esq, topo = r.left() + 24, r.top()
        larg_texto = r.width() - 230

        p.escrever(QRectF(esq, topo + 18, 300, 24), "SEU VOTO PARA", 17)
        p.escrever(QRectF(esq, topo + 50, larg_texto, 46), cargo.nome, 36, True, alinhar=Pincel.CENTRO)
        if cargo.votos_por_eleitor > 1:
            p.escrever(QRectF(esq, topo + 94, larg_texto, 24), f"{sessao.ordem_voto}º voto", 18,
                  alinhar=Pincel.CENTRO)

        if sessao.em_branco:
            p.escrever(QRectF(r.left(), topo + 170, r.width(), 90), "VOTO EM BRANCO", 50, True,
                  alinhar=Pincel.CENTRO)
        else:
            self._caixas_numero(p, esq, topo + 136, cargo.digitos, sessao.numero)
            self._detalhes(p, previa, cargo, esq, topo + 216, larg_texto)

        if previa.pode_confirmar:
            y = r.bottom() - 112
            p.setPen(QPen(QColor("#222222"), 1.4))
            p.drawLine(QPointF(r.left() + 14, y), QPointF(r.right() - 14, y))
            p.escrever(QRectF(esq, y + 8, 300, 26), "Aperte a tecla:", 18)
            p.escrever_partes(esq + 36, y + 38, [("CONFIRMA", True), (" para CONFIRMAR este voto", False)], 18)
            p.escrever_partes(esq + 36, y + 66, [("CORRIGE", True), (" para REINICIAR este voto", False)], 18)

    def _caixas_numero(self, p, x, y, digitos, numero):
        p.escrever(QRectF(x, y, 110, 58), "Número:", 20)
        for i in range(digitos):
            caixa = QRectF(x + 106 + i * 50, y, 44, 58)
            cursor = i == len(numero) and self._piscar
            p.setPen(QPen(QColor("#222222"), 1.6))
            p.setBrush(QColor("#c9c9c9") if cursor else QColor("#ffffff"))
            p.drawRect(caixa)
            if i < len(numero):
                p.escrever(caixa, numero[i], 40, True, alinhar=Pincel.CENTRO)

    def _detalhes(self, p, previa, cargo, x, y, larg):
        """Nome, partido, vices, fotos e avisos (nulo, legenda...)."""
        candidato = previa.candidato
        if candidato is not None:
            self._linha_info(p, x, y, "Nome:", candidato.nome)
            self._linha_info(p, x, y + 36, "Partido:", candidato.partido.sigla)
            for i, vice in enumerate(candidato.vices):
                self._linha_info(p, x, y + 72 + i * 36, f"{vice.titulo}:", vice.nome)
            self._fotos(p, candidato, cargo)
        elif previa.partido is not None:
            self._linha_info(p, x, y, "Partido:", f"{previa.partido.sigla} - {previa.partido.nome}")

        if previa.aviso == "CANDIDATO JÁ VOTADO":
            p.escrever(QRectF(x, y + 150, larg, 32), "CANDIDATO JÁ ESCOLHIDO NO 1º VOTO", 22, True,
                  "#b3261e", Pincel.CENTRO)
            p.escrever(QRectF(x, y + 184, larg, 28), "Aperte CORRIGE e escolha outro", 18,
                  alinhar=Pincel.CENTRO)
        elif previa.tipo is TipoVoto.NULO:
            p.escrever(QRectF(x, y + 4, larg, 36), "NÚMERO ERRADO", 26, True, alinhar=Pincel.CENTRO)
            if self._piscar:
                p.escrever(QRectF(x, y + 56, larg, 80), "VOTO NULO", 54, True, alinhar=Pincel.CENTRO)
        elif previa.tipo is TipoVoto.LEGENDA and candidato is None:
            if previa.aviso:
                p.escrever(QRectF(x, y + 50, larg, 32), previa.aviso, 22, True, alinhar=Pincel.CENTRO)
            p.escrever(QRectF(x, y + 86, larg, 60), "VOTO DE LEGENDA", 40, True, alinhar=Pincel.CENTRO)

    def _fotos(self, p, candidato, cargo):
        r = self.TELA
        foto = QRectF(r.right() - 194, r.top() + 22, 164, 200)
        p.foto(foto, candidato.nome, candidato.partido.cor)
        p.escrever(QRectF(foto.left() - 10, foto.bottom() + 2, foto.width() + 20, 22), cargo.nome,
              14, alinhar=Pincel.CENTRO)
        if len(candidato.vices) == 1:  # vice-governador / vice-presidente aparece com foto
            vice = candidato.vices[0]
            fv = QRectF(r.right() - 167, r.top() + 250, 110, 134)
            p.foto(fv, vice.nome, candidato.partido.cor)
            p.escrever(QRectF(fv.left() - 30, fv.bottom() + 2, fv.width() + 60, 20), vice.titulo,
                  13, alinhar=Pincel.CENTRO)


class JanelaUrna(QMainWindow):
    def __init__(self, urna, sons):
        super().__init__()
        s = urna.eleicao.secao
        self.setWindowTitle(f"Urna Eletrônica — Zona {s.zona} / Seção {s.numero} — "
                            f"{urna.eleicao.turno}º turno")
        self.tela = TelaUrna(urna, sons)
        self.setCentralWidget(self.tela)
        Creditos.instalar_rodape(self, escuro=True)

    def atualizar(self, evento=None):
        if evento == "interrompida":
            self.tela.mostrar_aviso("VOTAÇÃO INTERROMPIDA", "pelo presidente da mesa", "#9a5b00", 3.5)
        self.tela.update()

    def desligar(self):
        self.tela.desligar()

    def avisar_religamento(self):
        self.tela.mostrar_aviso("ENERGIA RESTABELECIDA", "Dados recuperados da memória da urna",
                                "#1f6f43", 4.0)

    def closeEvent(self, evento):
        evento.accept()
        QApplication.quit()
