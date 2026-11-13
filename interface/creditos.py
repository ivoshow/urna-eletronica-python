"""Créditos do projeto, exibidos no rodapé das janelas."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy


class Creditos:
    """Guarda num só lugar quem desenvolveu o projeto e em qual curso."""

    ALUNO = "Ivonielson F."
    PROFESSOR = "Prof. Esp. Ibukun Didier"
    MODULO = "Programação em Python"
    INSTITUICAO = "ITEAM"
    ANO = 2026

    @classmethod
    def texto(cls):
        return (f"Desenvolvido por {cls.ALUNO} com os conceitos aprendidos nas aulas do "
                f"{cls.PROFESSOR} • {cls.MODULO} — {cls.INSTITUICAO} {cls.ANO}")

    @classmethod
    def instalar_rodape(cls, janela, escuro=False):
        """Coloca a mensagem de créditos na barra de status (rodapé) de uma QMainWindow."""
        rotulo = QLabel(cls.texto())
        rotulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # uma linha só; se a janela ficar estreita, o texto é cortado (e aparece inteiro no tooltip)
        rotulo.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        rotulo.setToolTip(cls.texto())
        barra = janela.statusBar()
        barra.setSizeGripEnabled(False)
        barra.addWidget(rotulo, 1)
        if escuro:
            barra.setStyleSheet("QStatusBar { background: #23282d; border-top: 1px solid #15181b; }"
                                "QLabel { color: #aeb5bc; font-size: 11px; padding: 3px; }")
        else:
            barra.setStyleSheet("QStatusBar { border-top: 1px solid palette(mid); }"
                                "QLabel { color: palette(placeholder-text); font-size: 11px; padding: 3px; }")
        return rotulo
