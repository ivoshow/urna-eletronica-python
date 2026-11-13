"""Terminal do mesário: identifica o eleitor e libera a urna."""

from .erros import BiometriaPendente, EleitorJaVotou, UrnaDesconectada


class TerminalMesario:
    """Fica na mesa, ligado à urna por um cabo.

    Regras para liberar um eleitor:
      * o cabo precisa estar conectado à urna;
      * com biometria cadastrada: a digital precisa ser conferida no leitor;
      * sem biometria: o mesário confere o documento com foto e libera.
    """

    def __init__(self, eleicao):
        self.__eleicao = eleicao
        self.__urna = None

    @property
    def conectado(self):
        return self.__urna is not None and self.__urna.conectada

    def conectar(self, urna):
        self.__urna = urna
        urna.conectar()

    def desconectar(self):
        if self.__urna is not None:
            self.__urna.desconectar()

    def _urna(self):
        if not self.conectado:
            raise UrnaDesconectada("A urna não está conectada ao terminal do mesário.")
        return self.__urna

    def consultar(self, titulo):
        """Procura o eleitor no caderno da seção e confere se ainda pode votar."""
        eleitor = self.__eleicao.buscar_eleitor(titulo)
        if eleitor.votou:
            raise EleitorJaVotou(f"{eleitor.nome} já votou.")
        return eleitor

    def verificar_urna_pronta(self):
        self._urna().verificar_disponivel()

    def liberar(self, eleitor, digital_conferida=False):
        """Libera a urna. Quem tem biometria só é liberado com a digital conferida;
        quem não tem é liberado pelo mesário após conferir o documento com foto."""
        urna = self._urna()
        if eleitor.possui_biometria and not digital_conferida:
            raise BiometriaPendente("Confira a digital do eleitor no leitor biométrico.")
        urna.habilitar(eleitor)

    def abrir_votacao(self, senha):
        return self._urna().abrir(senha)

    def interromper_votacao(self, senha):
        """Presidente da mesa finaliza a votação de um eleitor que desistiu."""
        return self._urna().interromper(senha)

    def encerrar_votacao(self, senha):
        return self._urna().encerrar(senha)
