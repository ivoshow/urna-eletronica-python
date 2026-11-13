"""Janela que mostra a zerésima ou o boletim de urna como uma bobina impressa."""

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFontMetricsF
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout,
)

from modelo.boletim import ImpressoraUrna

from .desenho import Pincel


class DialogoDocumento(QDialog):
    """Mostra o documento, confere o código de verificação e abre o PDF salvo."""

    def __init__(self, documento, caminhos, pai=None):
        super().__init__(pai)
        self.setWindowTitle(f"{documento.tipo.title()} — Seção {documento.secao}")
        self._caminhos = caminhos

        lay = QVBoxLayout(self)
        titulo = QLabel(f"<b>{documento.tipo}</b> impresso pela urna")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(titulo)

        papel = QPlainTextEdit(documento.texto)
        papel.setReadOnly(True)
        papel.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        f = Pincel.fonte(13, mono=True)
        papel.setFont(f)
        largura = QFontMetricsF(f).horizontalAdvance("M" * ImpressoraUrna.LARGURA) + 46
        papel.setFixedWidth(int(largura))
        papel.setStyleSheet(
            "QPlainTextEdit { background: #fffdf5; color: #1d1d1d; border: 1px solid #d6cfba;"
            " padding: 10px; }")
        linha_papel = QHBoxLayout()
        linha_papel.addStretch()
        linha_papel.addWidget(papel)
        linha_papel.addStretch()
        lay.addLayout(linha_papel, 1)

        integro = "✔ código de verificação confere" if documento.verificar() else "✘ documento alterado"
        info = QLabel(integro)
        info.setStyleSheet("color: #2e7d32;")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(info)
        if caminhos:
            salvo = QLabel(f"Arquivos: {caminhos[1].name} e {caminhos[0].name}\n"
                           f"Pasta: {caminhos[1].parent}")
            salvo.setStyleSheet("color: gray; font-size: 11px;")
            salvo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            salvo.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            salvo.setWordWrap(True)
            salvo.setMaximumWidth(int(largura) + 40)
            lay.addWidget(salvo)

        botoes = QHBoxLayout()
        abrir_pdf = QPushButton("Abrir PDF")
        abrir_pasta = QPushButton("Abrir pasta")
        fechar = QPushButton("Fechar")
        abrir_pdf.clicked.connect(lambda: self._abrir(self._caminhos[1]))
        abrir_pasta.clicked.connect(lambda: self._abrir(self._caminhos[1].parent))
        fechar.clicked.connect(self.accept)
        existe = bool(caminhos) and caminhos[1].exists()
        abrir_pdf.setEnabled(existe)
        abrir_pasta.setEnabled(existe)
        for b in (abrir_pdf, abrir_pasta):
            botoes.addWidget(b)
        botoes.addStretch()
        botoes.addWidget(fechar)
        lay.addLayout(botoes)
        self.resize(int(largura) + 60, 720)

    @staticmethod
    def _abrir(caminho):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(caminho)))
