"""Pessoas envolvidas na votação: eleitor e mesário (herdam de Pessoa)."""

from .erros import EleitorJaVotou


class Pessoa:
    """Classe base com o dado comum a todas as pessoas: o nome."""

    def __init__(self, nome):
        nome = (nome or "").strip()
        if not nome:
            raise ValueError("O nome é obrigatório.")
        self.__nome = nome

    @property
    def nome(self):
        return self.__nome


class Eleitor(Pessoa):
    """Eleitor da seção. Sabe apenas SE votou, nunca EM QUEM (voto sigiloso)."""

    DIGITOS_TITULO = 12

    def __init__(self, titulo, nome, possui_biometria=True):
        super().__init__(nome)
        titulo = str(titulo)
        if len(titulo) != self.DIGITOS_TITULO or not titulo.isdigit():
            raise ValueError(f"Título inválido: {titulo!r} (use {self.DIGITOS_TITULO} dígitos).")
        self.__titulo = titulo
        self.__biometria = bool(possui_biometria)
        self.__votou = False

    @property
    def titulo(self):
        return self.__titulo

    @property
    def titulo_formatado(self):
        t = self.__titulo
        return f"{t[0:4]} {t[4:8]} {t[8:12]}"

    @property
    def possui_biometria(self):
        return self.__biometria

    @property
    def votou(self):
        return self.__votou

    def registrar_comparecimento(self):
        if self.__votou:
            raise EleitorJaVotou(f"{self.nome} já votou.")
        self.__votou = True


class Mesario(Pessoa):
    """Presidente da mesa: tem a senha para abrir e encerrar a votação."""

    def __init__(self, nome, senha):
        super().__init__(nome)
        self.__senha = str(senha)

    def autenticar(self, senha):
        return str(senha) == self.__senha
