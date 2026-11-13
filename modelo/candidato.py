"""Candidato e seus vices/suplentes."""


class Vice:
    """Vice ou suplente que aparece junto do candidato na tela da urna."""

    def __init__(self, titulo, nome):
        self.titulo = titulo  # ex.: "Vice-Governador", "1º Suplente"
        self.nome = nome


class Candidato:
    """Candidato a um cargo. O número sempre começa com o número do partido."""

    def __init__(self, numero, nome, partido, vices=()):
        numero = str(numero)
        if not numero.isdigit():
            raise ValueError(f"Número de candidato inválido: {numero!r}.")
        if not numero.startswith(partido.numero):
            raise ValueError(
                f"O número {numero} deve começar com o número do partido ({partido.numero})."
            )
        if not nome:
            raise ValueError("O nome do candidato é obrigatório.")
        self.__numero = numero
        self.__nome = nome
        self.__partido = partido
        self.__vices = tuple(vices)
        self.__votos = 0  # privado: só muda por receber_voto()

    @property
    def numero(self):
        return self.__numero

    @property
    def nome(self):
        return self.__nome

    @property
    def partido(self):
        return self.__partido

    @property
    def vices(self):
        return self.__vices

    @property
    def votos(self):
        return self.__votos

    def receber_voto(self):
        self.__votos += 1

    def __str__(self):
        return f"{self.numero} {self.nome} ({self.partido.sigla})"
