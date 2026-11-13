"""Pincel: o QPainter do Qt com métodos extras para desenhar a urna."""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QColor, QFont, QFontMetricsF, QLinearGradient, QPainter, QPainterPath, QPen,
)


class Pincel(QPainter):
    """Herda de QPainter e acrescenta texto formatado e retratos ilustrados.

    Uso: dentro de paintEvent, p = Pincel(self); p.escrever(...); p.foto(...)
    """

    FAMILIAS = ["Liberation Sans", "Arial", "Helvetica", "DejaVu Sans", "Sans Serif"]
    FAMILIAS_MONO = ["DejaVu Sans Mono", "Liberation Mono", "Courier New", "Monospace"]
    ESQUERDA = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    CENTRO = Qt.AlignmentFlag.AlignCenter

    TONS_PELE = ["#f1c7a5", "#e0ac83", "#c68a62", "#a86b45", "#8a5534", "#f5d3b8"]
    TONS_CABELO = ["#2a1b12", "#4a2f1d", "#6b4325", "#1b1b1b", "#8c6a43", "#5a5a5a"]

    def __init__(self, dispositivo):
        super().__init__(dispositivo)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    # ------------------------------------------------------------ fontes
    @classmethod
    def fonte(cls, px, negrito=False, mono=False):
        """Fonte com tamanho em pixels (escala junto com o desenho da urna)."""
        f = QFont()
        f.setFamilies(cls.FAMILIAS_MONO if mono else cls.FAMILIAS)
        f.setPixelSize(max(1, int(px)))
        f.setBold(negrito)
        return f

    @classmethod
    def largura(cls, conteudo, px, negrito=False):
        return QFontMetricsF(cls.fonte(px, negrito)).horizontalAdvance(conteudo)

    # ------------------------------------------------------------ texto
    def escrever(self, rect, conteudo, px, negrito=False, cor="#111111", alinhar=None):
        self.setFont(self.fonte(px, negrito))
        self.setPen(QColor(cor))
        self.drawText(rect, alinhar if alinhar is not None else self.ESQUERDA, conteudo)

    def escrever_partes(self, x, y, partes, px, cor="#111111"):
        """Escreve vários trechos lado a lado; cada parte é (texto, negrito)."""
        for conteudo, negrito in partes:
            larg = self.largura(conteudo, px, negrito)
            self.escrever(QRectF(x, y, larg + 2, px * 1.4), conteudo, px, negrito, cor)
            x += larg

    # ------------------------------------------------------------ retrato
    def foto(self, rect, nome, cor_partido):
        """Desenha um retrato ilustrado (silhueta) no lugar da foto do candidato.

        A cor da pele e do cabelo varia de acordo com o nome; a roupa usa a cor do
        partido. Assim cada candidato tem uma "foto" própria sem precisar de imagens.
        """
        semente = sum(ord(c) * (i + 1) for i, c in enumerate(nome))
        pele = QColor(self.TONS_PELE[semente % len(self.TONS_PELE)])
        cabelo = QColor(self.TONS_CABELO[(semente // 7) % len(self.TONS_CABELO)])

        self.save()
        moldura = QPainterPath()
        moldura.addRoundedRect(rect, 4, 4)
        self.setClipPath(moldura)

        fundo = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        fundo.setColorAt(0, QColor("#dfe6ee"))
        fundo.setColorAt(1, QColor("#b9c4cf"))
        self.fillRect(rect, fundo)

        x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
        cx = x + w / 2
        self.setPen(Qt.PenStyle.NoPen)
        self.setBrush(QColor(cor_partido))                                   # roupa
        self.drawEllipse(QRectF(x + w * 0.08, y + h * 0.70, w * 0.84, h * 0.62))
        self.setBrush(pele.darker(108))                                      # pescoço
        self.drawRect(QRectF(cx - w * 0.09, y + h * 0.52, w * 0.18, h * 0.22))
        self.setBrush(cabelo)                                                # cabelo
        self.drawEllipse(QRectF(cx - w * 0.235, y + h * 0.14, w * 0.47, h * 0.42))
        self.setBrush(pele)                                                  # rosto
        self.drawEllipse(QRectF(cx - w * 0.20, y + h * 0.20, w * 0.40, h * 0.40))
        self.setBrush(QColor("#f4f4f4"))                                     # gola
        gola = QPainterPath()
        gola.moveTo(cx - w * 0.12, y + h * 0.72)
        gola.lineTo(cx, y + h * 0.84)
        gola.lineTo(cx + w * 0.12, y + h * 0.72)
        gola.closeSubpath()
        self.drawPath(gola)
        self.restore()

        self.setPen(QPen(QColor("#555555"), 1.2))
        self.setBrush(Qt.BrushStyle.NoBrush)
        self.drawRoundedRect(rect, 4, 4)
