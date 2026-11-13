"""Partido político."""


class Partido:
    """Partido com número de 2 dígitos, sigla, nome e uma cor (usada na tela)."""

    def __init__(self, numero, sigla, nome, cor="#777777"):
        numero = str(numero)
        if len(numero) != 2 or not numero.isdigit():
            raise ValueError(f"Número de partido inválido: {numero!r} (use 2 dígitos).")
        if not sigla or not nome:
            raise ValueError("Sigla e nome do partido são obrigatórios.")
        self.__numero = numero
        self.__sigla = sigla.upper()
        self.__nome = nome
        self.__cor = cor

    @property
    def numero(self):
        return self.__numero

    @property
    def sigla(self):
        return self.__sigla

    @property
    def nome(self):
        return self.__nome

    @property
    def cor(self):
        return self.__cor

    def __str__(self):
        return f"{self.numero} - {self.sigla}"
