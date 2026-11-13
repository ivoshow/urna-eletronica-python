"""Cargo em disputa e a interpretação do número digitado na urna."""

from dataclasses import dataclass
from enum import Enum


class TipoVoto(Enum):
    NOMINAL = "nominal"   # voto em um candidato
    LEGENDA = "legenda"   # voto só no partido (cargos proporcionais)
    BRANCO = "branco"
    NULO = "nulo"


@dataclass(frozen=True)
class Previa:
    """O que a urna mostra para o número digitado até agora.

    tipo fica None enquanto o número ainda não forma um voto.
    pode_confirmar diz se a tecla CONFIRMA está aceitando o voto.
    """

    tipo: TipoVoto | None = None
    numero: str = ""
    candidato: object = None
    partido: object = None
    pode_confirmar: bool = False
    aviso: str = ""


class Cargo:
    """Um cargo da eleição (ex.: Governador) com seus candidatos e a contagem.

    proporcional=True (deputados) permite voto de legenda.
    votos_por_eleitor=2 é usado quando há duas vagas (ex.: Senado em 2026).
    """

    def __init__(self, codigo, nome, digitos, partidos, proporcional=False, votos_por_eleitor=1):
        if digitos < 2:
            raise ValueError("O cargo precisa de pelo menos 2 dígitos.")
        self.__codigo = codigo
        self.__nome = nome
        self.__digitos = digitos
        self.__partidos = partidos          # número -> Partido (compartilhado pela eleição)
        self.__proporcional = proporcional
        self.__votos_por_eleitor = votos_por_eleitor
        self.__candidatos = {}              # número -> Candidato
        self.__legenda = {}                 # número do partido -> votos
        self.__brancos = 0
        self.__nulos = 0

    # ------------------------------------------------------------ dados
    @property
    def codigo(self):
        return self.__codigo

    @property
    def nome(self):
        return self.__nome

    @property
    def digitos(self):
        return self.__digitos

    @property
    def proporcional(self):
        return self.__proporcional

    @property
    def votos_por_eleitor(self):
        return self.__votos_por_eleitor

    @property
    def candidatos(self):
        return sorted(self.__candidatos.values(), key=lambda c: c.numero)

    def adicionar_candidato(self, candidato):
        if len(candidato.numero) != self.__digitos:
            raise ValueError(
                f"{self.__nome} usa {self.__digitos} dígitos; {candidato.numero} não serve."
            )
        if candidato.numero in self.__candidatos:
            raise ValueError(f"Já existe candidato {candidato.numero} para {self.__nome}.")
        self.__candidatos[candidato.numero] = candidato

    def buscar(self, numero):
        return self.__candidatos.get(numero)

    def candidatos_do_partido(self, numero_partido):
        return [c for c in self.candidatos if c.partido.numero == numero_partido]

    def partidos_participantes(self):
        numeros = {c.partido.numero for c in self.__candidatos.values()} | set(self.__legenda)
        return [self.__partidos[n] for n in sorted(numeros)]

    # ------------------------------------------------------------ interpretação
    def interpretar(self, numero):
        """Devolve a Previa do número digitado (completo ou não)."""
        if not numero:
            return Previa()
        partido = self.__partidos.get(numero[:2]) if len(numero) >= 2 else None

        if len(numero) < self.__digitos:
            if self.__proporcional and partido:
                # Com só os 2 dígitos do partido, CONFIRMA vira voto de legenda.
                if len(numero) == 2:
                    return Previa(TipoVoto.LEGENDA, numero, None, partido, True)
                return Previa(None, numero, None, partido, False)
            return Previa(None, numero)

        candidato = self.__candidatos.get(numero)
        if candidato:
            return Previa(TipoVoto.NOMINAL, numero, candidato, candidato.partido, True)
        if self.__proporcional and partido:
            return Previa(TipoVoto.LEGENDA, numero, None, partido, True, "CANDIDATO INEXISTENTE")
        return Previa(TipoVoto.NULO, numero, None, None, True, "NÚMERO ERRADO")

    @staticmethod
    def previa_branco():
        return Previa(TipoVoto.BRANCO, "", None, None, True)

    # ------------------------------------------------------------ apuração
    def registrar(self, previa):
        """Soma um voto já confirmado. Não guarda QUEM votou: só a contagem."""
        if previa.tipo is TipoVoto.NOMINAL:
            previa.candidato.receber_voto()
        elif previa.tipo is TipoVoto.LEGENDA:
            numero = previa.partido.numero
            self.__legenda[numero] = self.__legenda.get(numero, 0) + 1
        elif previa.tipo is TipoVoto.BRANCO:
            self.__brancos += 1
        elif previa.tipo is TipoVoto.NULO:
            self.__nulos += 1
        else:
            raise ValueError("Prévia sem tipo não pode ser registrada.")

    def votos_legenda(self, numero_partido):
        return self.__legenda.get(numero_partido, 0)

    def votos_partido(self, numero_partido):
        nominais = sum(c.votos for c in self.candidatos_do_partido(numero_partido))
        return nominais + self.votos_legenda(numero_partido)

    @property
    def nominais(self):
        return sum(c.votos for c in self.__candidatos.values())

    @property
    def legenda_total(self):
        return sum(self.__legenda.values())

    @property
    def brancos(self):
        return self.__brancos

    @property
    def nulos(self):
        return self.__nulos

    @property
    def validos(self):
        return self.nominais + self.legenda_total

    @property
    def total(self):
        return self.validos + self.__brancos + self.__nulos
