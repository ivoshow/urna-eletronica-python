"""Impressora da urna: emite a Zerésima e o Boletim de Urna (BU).

Os documentos saem em formato de bobina de impressora térmica (40 colunas) e
terminam com um código de verificação SHA-256 calculado sobre o conteúdo.
"""

import hashlib
import textwrap
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Documento:
    """Documento impresso pela urna."""

    tipo: str               # "ZERÉSIMA" ou "BOLETIM DE URNA"
    linhas: tuple
    codigo: str
    zona: str
    secao: str
    emitido_em: datetime = field(default_factory=datetime.now)

    LINHAS_CODIGO = 5       # as últimas linhas trazem o próprio código

    @property
    def texto(self):
        return "\n".join(self.linhas)

    @property
    def nome_arquivo(self):
        prefixo = "BU" if self.tipo == "BOLETIM DE URNA" else "ZERESIMA"
        return f"{prefixo}_Z{self.zona}_S{self.secao}_{self.emitido_em:%Y%m%d_%H%M%S}"

    def para_dict(self):
        return {"tipo": self.tipo, "linhas": list(self.linhas), "codigo": self.codigo,
                "zona": self.zona, "secao": self.secao, "emitido_em": self.emitido_em.isoformat()}

    @classmethod
    def de_dict(cls, dados):
        return cls(dados["tipo"], tuple(dados["linhas"]), dados["codigo"], dados["zona"],
                   dados["secao"], datetime.fromisoformat(dados["emitido_em"]))

    def verificar(self):
        """Recalcula o SHA-256 e diz se o documento não foi alterado."""
        conteudo = self.linhas[: len(self.linhas) - self.LINHAS_CODIGO]
        return ImpressoraUrna.calcular_codigo(conteudo) == self.codigo


class ImpressoraUrna:
    """Monta a zerésima e o boletim de urna a partir dos dados de uma urna."""

    LARGURA = 40
    DUPLO = "=" * LARGURA
    TRACO = "-" * LARGURA

    # ------------------------------------------------------------ documentos
    def emitir_zeresima(self, urna):
        """Prova, antes da abertura, que todos os candidatos estão com zero votos."""
        agora = datetime.now()
        linhas = self.__cabecalho(urna, "ZERÉSIMA")
        linhas += [
            "",
            *textwrap.wrap(
                "Este documento comprova que a urna não contém nenhum voto "
                "registrado antes do início da votação.", self.LARGURA),
        ]
        linhas += self.__resultados(urna)
        return self.__assinar("ZERÉSIMA", linhas, urna, agora)

    def emitir_boletim(self, urna):
        """Resultado da seção, emitido no encerramento da votação."""
        agora = datetime.now()
        eleicao = urna.eleicao
        linhas = self.__cabecalho(urna, "BOLETIM DE URNA")
        linhas += [
            self.__valor("Comparecimento", eleicao.comparecimento),
            self.__valor("Eleitores faltosos", eleicao.aptos - eleicao.comparecimento),
            "",
            self.__valor("Abertura", f"{urna.abertura:%d/%m/%Y %H:%M:%S}"),
            self.__valor("Encerramento", f"{urna.encerramento:%d/%m/%Y %H:%M:%S}"),
        ]
        linhas += self.__resultados(urna)
        return self.__assinar("BOLETIM DE URNA", linhas, urna, agora)

    @staticmethod
    def calcular_codigo(linhas):
        return hashlib.sha256("\n".join(linhas).encode("utf-8")).hexdigest().upper()

    # ------------------------------------------------------------ formatação
    def __valor(self, rotulo, valor, recuo=0):
        """Monta 'Rótulo ........ valor' ocupando exatamente LARGURA colunas."""
        valor = str(valor)
        espaco = self.LARGURA - recuo - len(valor) - 1
        rotulo = rotulo[: espaco - 2]
        return " " * recuo + (rotulo + " ").ljust(espaco, ".") + " " + valor

    def __centro(self, texto):
        return texto.center(self.LARGURA).rstrip()

    def __cabecalho(self, urna, titulo):
        eleicao = urna.eleicao
        s = eleicao.secao
        return [
            self.DUPLO,
            self.__centro(titulo),
            self.__centro("*** SIMULAÇÃO - SEM VALOR OFICIAL ***"),
            self.DUPLO,
            *[self.__centro(t) for t in textwrap.wrap(eleicao.descricao, self.LARGURA)],
            self.__centro(f"{eleicao.turno}º turno - {eleicao.data}"),
            "",
            self.__valor("UF", s.uf),
            self.__valor("Município", s.municipio.upper()),
            self.__valor("Zona eleitoral", s.zona),
            self.__valor("Seção eleitoral", s.numero),
            *textwrap.wrap(f"Local: {s.local}", self.LARGURA),
            self.__valor("Código da urna", urna.codigo),
            "",
            self.__valor("Eleitores aptos", eleicao.aptos),
        ]

    def __resultados(self, urna):
        linhas = []
        for cargo in urna.eleicao.cargos:
            linhas += [self.DUPLO, self.__centro(cargo.nome.upper())]
            if cargo.votos_por_eleitor > 1:
                linhas.append(self.__centro(f"({cargo.votos_por_eleitor} votos por eleitor)"))
            linhas.append(self.TRACO)
            if cargo.proporcional:
                linhas += self.__por_partido(cargo)
            else:
                # Majoritários: do mais votado para o menos votado.
                for c in sorted(cargo.candidatos, key=lambda c: (-c.votos, c.numero)):
                    linhas.append(self.__valor(f"{c.numero} {c.nome.upper()} ({c.partido.sigla})",
                                               c.votos))
            linhas += self.__totais(cargo)
        return linhas

    def __por_partido(self, cargo):
        linhas = []
        for partido in cargo.partidos_participantes():
            linhas.append(f"{partido.numero} - {partido.sigla}")
            for c in cargo.candidatos_do_partido(partido.numero):
                linhas.append(self.__valor(f"{c.numero} {c.nome.upper()}", c.votos, 1))
            linhas.append(self.__valor("Legenda", cargo.votos_legenda(partido.numero), 1))
            linhas.append(self.__valor("Total do partido", cargo.votos_partido(partido.numero), 1))
            linhas.append("")
        return linhas

    def __totais(self, cargo):
        linhas = [self.TRACO, self.__valor("Votos nominais", cargo.nominais)]
        if cargo.proporcional:
            linhas.append(self.__valor("Votos de legenda", cargo.legenda_total))
        linhas += [
            self.__valor("Votos em branco", cargo.brancos),
            self.__valor("Votos nulos", cargo.nulos),
            self.__valor("Total apurado", cargo.total),
        ]
        return linhas

    def __assinar(self, tipo, linhas, urna, emitido_em):
        """Fecha o documento com o código SHA-256 calculado sobre todo o conteúdo."""
        linhas = list(linhas) + [self.DUPLO, f"Emitido em {emitido_em:%d/%m/%Y %H:%M:%S}"]
        codigo = self.calcular_codigo(linhas)
        blocos = [codigo[i:i + 4] for i in range(0, len(codigo), 4)]
        linhas += [
            "",
            "Código de verificação (SHA-256):",
            " ".join(blocos[:8]),
            " ".join(blocos[8:]),
            self.DUPLO,
        ]
        s = urna.eleicao.secao
        return Documento(tipo, tuple(linhas), codigo, s.zona, s.numero, emitido_em)
