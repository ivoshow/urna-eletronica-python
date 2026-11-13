"""Dados da eleição e da seção eleitoral."""

from dataclasses import dataclass

from .erros import EleitorNaoEncontrado


@dataclass(frozen=True)
class Secao:
    uf: str
    municipio: str
    zona: str
    numero: str
    local: str
    codigo_urna: str


class Eleicao:
    """Agrupa partidos, cargos (na ordem de votação), eleitores e a mesa."""

    def __init__(self, descricao, turno, data, secao, partidos, cargos, eleitores, presidente):
        self.__descricao = descricao
        self.__turno = turno
        self.__data = data
        self.__secao = secao
        self.__partidos = dict(partidos)
        self.__cargos = tuple(cargos)
        self.__presidente = presidente
        self.__eleitores = {}
        for eleitor in eleitores:
            if eleitor.titulo in self.__eleitores:
                raise ValueError(f"Título repetido: {eleitor.titulo}")
            self.__eleitores[eleitor.titulo] = eleitor
        if not self.__cargos:
            raise ValueError("A eleição precisa de pelo menos um cargo.")

    @property
    def descricao(self):
        return self.__descricao

    @property
    def turno(self):
        return self.__turno

    @property
    def data(self):
        return self.__data

    @property
    def secao(self):
        return self.__secao

    @property
    def partidos(self):
        return dict(self.__partidos)

    @property
    def cargos(self):
        return self.__cargos

    @property
    def presidente(self):
        return self.__presidente

    @property
    def eleitores(self):
        return sorted(self.__eleitores.values(), key=lambda e: e.nome)

    @property
    def aptos(self):
        return len(self.__eleitores)

    @property
    def comparecimento(self):
        return sum(1 for e in self.__eleitores.values() if e.votou)

    def buscar_eleitor(self, titulo):
        eleitor = self.__eleitores.get(titulo)
        if eleitor is None:
            raise EleitorNaoEncontrado("Eleitor não pertence a esta seção.")
        return eleitor
