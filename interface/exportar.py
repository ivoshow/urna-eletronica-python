"""Salva a zerésima e o boletim de urna em .txt e em .pdf (formato de bobina)."""

from PySide6.QtCore import QMarginsF, QPointF, QSizeF
from PySide6.QtGui import QFont, QPageLayout, QPageSize, QPainter, QPdfWriter

from .desenho import Pincel


class ExportadorDocumento:
    """Grava os documentos da urna em uma pasta, como texto e como PDF."""

    LARGURA_PAPEL_MM = 80      # bobina térmica de 80 mm, como a impressora da urna
    ENTRELINHA_MM = 3.6
    MARGEM_MM = 6

    def __init__(self, pasta):
        self.__pasta = pasta

    @property
    def pasta(self):
        return self.__pasta

    def caminhos(self, documento):
        """Onde o documento é (ou seria) salvo: (caminho_txt, caminho_pdf)."""
        base = self.__pasta / documento.nome_arquivo
        return base.with_suffix(".txt"), base.with_suffix(".pdf")

    def salvar(self, documento):
        """Grava o documento e devolve (caminho_txt, caminho_pdf)."""
        self.__pasta.mkdir(parents=True, exist_ok=True)
        txt, pdf = self.caminhos(documento)
        txt.write_text(documento.texto + "\n", encoding="utf-8")
        self.__gerar_pdf(documento, pdf)
        return txt, pdf

    def __gerar_pdf(self, documento, caminho):
        linhas = documento.linhas
        altura_mm = 2 * self.MARGEM_MM + len(linhas) * self.ENTRELINHA_MM
        pdf = QPdfWriter(str(caminho))
        pdf.setResolution(300)
        pdf.setTitle(f"{documento.tipo} - Seção {documento.secao}")
        pdf.setCreator("Simulador de Urna Eletrônica")
        pdf.setPageSize(QPageSize(QSizeF(self.LARGURA_PAPEL_MM, altura_mm),
                                  QPageSize.Unit.Millimeter, "Bobina"))
        pdf.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter)

        p = QPainter(pdf)
        f = QFont()
        f.setFamilies(Pincel.FAMILIAS_MONO)
        f.setPointSizeF(7.4)
        p.setFont(f)
        px_mm = pdf.resolution() / 25.4
        y = (self.MARGEM_MM + self.ENTRELINHA_MM * 0.8) * px_mm
        for linha in linhas:
            p.drawText(QPointF(self.MARGEM_MM * px_mm, y), linha)
            y += self.ENTRELINHA_MM * px_mm
        p.end()
