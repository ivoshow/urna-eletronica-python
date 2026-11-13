"""A urna eletrônica: estados, votação de cada eleitor e registro de eventos."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .boletim import Documento, ImpressoraUrna
from .cargo import Cargo, Previa, TipoVoto
from .erros import (
    EleitorJaVotou,
    OperacaoInvalida,
    SenhaIncorreta,
    UrnaBloqueada,
    UrnaDesconectada,
    UrnaOcupada,
    VotacaoEncerrada,
    VotacaoNaoIniciada,
)


class EstadoUrna(Enum):
    PREPARADA = "preparada"                 # ligada, esperando a abertura
    AGUARDANDO_ELEITOR = "aguardando"       # aberta, teclado bloqueado
    VOTANDO = "votando"                     # eleitor liberado pelo mesário
    ENCERRADA = "encerrada"                 # boletim de urna emitido


@dataclass(frozen=True)
class ResultadoInterrupcao:
    """O que aconteceu quando o presidente interrompeu a votação de um eleitor."""

    eleitor_votou: bool    # True se havia pelo menos 1 voto confirmado
    confirmados: int       # votos já confirmados (continuam valendo)
    anulados: int          # votos que faltavam e foram computados como nulos


class SessaoVotacao:
    """A votação de UM eleitor: percorre os cargos na ordem da eleição.

    Guarda só o que está sendo digitado. Cada voto confirmado vai direto para
    a contagem do cargo, sem nenhuma ligação com o eleitor.
    """

    def __init__(self, cargos, inicio=0):
        # Um cargo com 2 vagas (Senado) vira duas etapas.
        self.__etapas = [(c, i + 1) for c in cargos for i in range(c.votos_por_eleitor)]
        self.__indice = inicio      # > 0 só na recuperação após queda de energia
        self.__numero = ""
        self.__branco = False
        self.__ja_escolhidos = {}  # código do cargo -> números já confirmados nesta sessão

    @property
    def finalizada(self):
        return self.__indice >= len(self.__etapas)

    @property
    def cargo_atual(self):
        return None if self.finalizada else self.__etapas[self.__indice][0]

    @property
    def ordem_voto(self):
        """1 ou 2 quando o cargo tem duas vagas (1º voto, 2º voto)."""
        return None if self.finalizada else self.__etapas[self.__indice][1]

    @property
    def etapa(self):
        return self.__indice + 1

    @property
    def votos_confirmados(self):
        return self.__indice

    def anular_restantes(self):
        """Computa como NULO cada voto que faltava (eleitor desistiu). Devolve quantos."""
        anulados = 0
        while not self.finalizada:
            self.cargo_atual.registrar(Previa(TipoVoto.NULO))
            self.__indice += 1
            anulados += 1
        self.__numero = ""
        self.__branco = False
        return anulados

    @property
    def total_etapas(self):
        return len(self.__etapas)

    @property
    def numero(self):
        return self.__numero

    @property
    def em_branco(self):
        return self.__branco

    @property
    def previa(self):
        cargo = self.cargo_atual
        if cargo is None:
            return None
        if self.__branco:
            return Cargo.previa_branco()
        previa = cargo.interpretar(self.__numero)
        repetidos = self.__ja_escolhidos.get(cargo.codigo, ())
        if previa.tipo is TipoVoto.NOMINAL and previa.numero in repetidos:
            # Não se pode votar duas vezes no mesmo candidato ao Senado.
            return type(previa)(None, previa.numero, previa.candidato, previa.partido,
                                False, "CANDIDATO JÁ VOTADO")
        return previa

    def digitar(self, digito):
        cargo = self.cargo_atual
        if cargo is None or self.__branco or len(self.__numero) >= cargo.digitos:
            return False
        if len(digito) != 1 or not digito.isdigit():
            return False
        self.__numero += digito
        return True

    def votar_branco(self):
        """BRANCO só funciona com o campo vazio, como na urna real."""
        if self.finalizada or self.__numero or self.__branco:
            return False
        self.__branco = True
        return True

    def corrigir(self):
        if self.finalizada:
            return False
        self.__numero = ""
        self.__branco = False
        return True

    def confirmar(self):
        """Registra o voto do cargo atual e avança. Devolve a Previa ou None."""
        previa = self.previa
        if previa is None or not previa.pode_confirmar:
            return None
        cargo = self.cargo_atual
        cargo.registrar(previa)
        if previa.tipo is TipoVoto.NOMINAL:
            self.__ja_escolhidos.setdefault(cargo.codigo, set()).add(previa.numero)
        self.__indice += 1
        self.__numero = ""
        self.__branco = False
        return previa


class Urna:
    """Urna eletrônica de uma seção.

    Só aceita votos quando o terminal do mesário está conectado e liberou um
    eleitor. A interface é avisada de cada mudança pelos "ouvintes".
    """

    VERSAO_MEMORIA = 2   # 2: a memória passou a registrar o turno

    def __init__(self, eleicao, memoria=None):
        self.__eleicao = eleicao
        self.__memoria = memoria            # MemoriaUrna ou None (testes rodam sem disco)
        self.__recuperada = False
        self.__pendencia_na_queda = None    # ResultadoInterrupcao, se havia eleitor votando
        self.__impressora = ImpressoraUrna()
        self.__estado = EstadoUrna.PREPARADA
        self.__conectada = False
        self.__sessao = None
        self.__eleitor_votando = None   # só para marcar o comparecimento no final
        self.__abertura = None
        self.__encerramento = None
        self.__zeresima = None
        self.__boletim = None
        self.__log = []
        self.__ouvintes = []
        if memoria is not None and memoria.existe():
            self.__restaurar(memoria.ler())
        else:
            self._registrar("Urna ligada")

    # ------------------------------------------------------------ consulta
    @property
    def eleicao(self):
        return self.__eleicao

    @property
    def codigo(self):
        return self.__eleicao.secao.codigo_urna

    @property
    def estado(self):
        return self.__estado

    @property
    def conectada(self):
        return self.__conectada

    @property
    def sessao(self):
        return self.__sessao

    @property
    def abertura(self):
        return self.__abertura

    @property
    def encerramento(self):
        return self.__encerramento

    @property
    def zeresima(self):
        return self.__zeresima

    @property
    def boletim(self):
        return self.__boletim

    @property
    def log(self):
        return tuple(self.__log)

    @property
    def recuperada(self):
        """True se esta urna foi religada recuperando dados da memória."""
        return self.__recuperada

    @property
    def pendencia_na_queda(self):
        """ResultadoInterrupcao do eleitor que votava na hora da queda (ou None)."""
        return self.__pendencia_na_queda

    # ------------------------------------------------------------ eventos
    def adicionar_ouvinte(self, funcao):
        self.__ouvintes.append(funcao)

    def _notificar(self, evento):
        if evento != "tecla":          # o que está só digitado não é gravado (nem na urna real)
            self.__salvar()
        for funcao in self.__ouvintes:
            funcao(evento)

    def _registrar(self, mensagem):
        self.__log.append((datetime.now(), mensagem))
        self.__salvar()

    # ------------------------------------------------------------ memória
    def __salvar(self):
        if self.__memoria is not None:
            self.__memoria.gravar(self.__fotografia())

    def __fotografia(self):
        """Tudo o que a urna precisa para ser religada. Sem ligação eleitor → voto."""
        contagem = {}
        for cargo in self.__eleicao.cargos:
            contagem[cargo.codigo] = {
                "candidatos": {c.numero: c.votos for c in cargo.candidatos if c.votos},
                "legenda": {p.numero: cargo.votos_legenda(p.numero)
                            for p in cargo.partidos_participantes() if cargo.votos_legenda(p.numero)},
                "brancos": cargo.brancos,
                "nulos": cargo.nulos,
            }
        em_votacao = None
        if self.__estado is EstadoUrna.VOTANDO and self.__sessao is not None:
            em_votacao = {"titulo": self.__eleitor_votando.titulo,
                          "confirmados": self.__sessao.votos_confirmados}
        data = lambda d: d.isoformat() if d else None
        return {
            "versao": self.VERSAO_MEMORIA,
            "codigo_urna": self.codigo,
            "turno": self.__eleicao.turno,
            "estado": self.__estado.value,
            "conectada": self.__conectada,
            "abertura": data(self.__abertura),
            "encerramento": data(self.__encerramento),
            "zeresima": self.__zeresima.para_dict() if self.__zeresima else None,
            "boletim": self.__boletim.para_dict() if self.__boletim else None,
            "votaram": [e.titulo for e in self.__eleicao.eleitores if e.votou],
            "contagem": contagem,
            "em_votacao": em_votacao,
            "log": [[m.isoformat(), texto] for m, texto in self.__log],
        }

    def __restaurar(self, dados):
        """Religa a urna com os dados da memória (após queda de energia)."""
        if dados.get("versao") != self.VERSAO_MEMORIA or dados.get("codigo_urna") != self.codigo:
            raise ValueError("A memória gravada não pertence a esta urna.")
        if dados.get("turno") != self.__eleicao.turno:     # 1º e 2º turno nunca se misturam
            raise ValueError(f"A memória gravada é do {dados.get('turno')}º turno, "
                             f"mas esta eleição é do {self.__eleicao.turno}º turno.")
        eleicao = self.__eleicao
        partidos = eleicao.partidos
        # contadores: "reproduz" os votos pelos métodos públicos (encapsulamento preservado)
        for cargo in eleicao.cargos:
            dados_cargo = dados["contagem"].get(cargo.codigo, {})
            for numero, votos in dados_cargo.get("candidatos", {}).items():
                candidato = cargo.buscar(numero)
                if candidato is None:
                    raise ValueError(f"Candidato {numero} da memória não existe em {cargo.nome}.")
                for _ in range(votos):
                    candidato.receber_voto()
            for numero, votos in dados_cargo.get("legenda", {}).items():
                for _ in range(votos):
                    cargo.registrar(Previa(TipoVoto.LEGENDA, partido=partidos[numero]))
            for _ in range(dados_cargo.get("brancos", 0)):
                cargo.registrar(Cargo.previa_branco())
            for _ in range(dados_cargo.get("nulos", 0)):
                cargo.registrar(Previa(TipoVoto.NULO))
        # caderno: quem já votou continua marcado
        for titulo in dados["votaram"]:
            eleicao.buscar_eleitor(titulo).registrar_comparecimento()

        quando = lambda s: datetime.fromisoformat(s) if s else None
        self.__estado = EstadoUrna(dados["estado"])
        self.__conectada = dados["conectada"]
        self.__abertura = quando(dados["abertura"])
        self.__encerramento = quando(dados["encerramento"])
        self.__zeresima = Documento.de_dict(dados["zeresima"]) if dados["zeresima"] else None
        self.__boletim = Documento.de_dict(dados["boletim"]) if dados["boletim"] else None
        self.__log = [(datetime.fromisoformat(m), texto) for m, texto in dados["log"]]
        self.__recuperada = True
        self._registrar("Energia restabelecida: dados recuperados da memória")

        # eleitor que votava na hora da queda: mesma regra da interrupção pelo presidente
        pendente = dados.get("em_votacao")
        if self.__estado is EstadoUrna.VOTANDO and pendente:
            eleitor = eleicao.buscar_eleitor(pendente["titulo"])
            confirmados = pendente["confirmados"]
            if confirmados == 0:
                self.__pendencia_na_queda = ResultadoInterrupcao(False, 0, 0)
                self._registrar("Votação pendente suspensa na queda (nenhum voto confirmado)")
            else:
                anulados = SessaoVotacao(eleicao.cargos, inicio=confirmados).anular_restantes()
                eleitor.registrar_comparecimento()
                self.__pendencia_na_queda = ResultadoInterrupcao(True, confirmados, anulados)
                self._registrar(f"Votação pendente concluída na queda: {anulados} voto(s) nulo(s)")
            self.__estado = EstadoUrna.AGUARDANDO_ELEITOR
            self.__salvar()

    # ------------------------------------------------------------ conexão
    def conectar(self):
        if not self.__conectada:
            self.__conectada = True
            self._registrar("Terminal do mesário conectado")
            self._notificar("conexao")

    def desconectar(self):
        if self.__conectada:
            self.__conectada = False
            self._registrar("Terminal do mesário desconectado")
            self._notificar("conexao")

    # ------------------------------------------------------------ abertura / encerramento
    def abrir(self, senha):
        """Confere a senha, emite a zerésima (prova de que não há votos) e abre a votação."""
        if not self.__eleicao.presidente.autenticar(senha):
            self._registrar("Tentativa de abertura com senha incorreta")
            raise SenhaIncorreta("Senha do presidente da mesa incorreta.")
        if self.__estado is not EstadoUrna.PREPARADA:
            raise OperacaoInvalida("A votação já foi aberta.")
        self.__zeresima = self.__impressora.emitir_zeresima(self)
        self.__estado = EstadoUrna.AGUARDANDO_ELEITOR
        self.__abertura = datetime.now()
        self._registrar("Zerésima emitida")
        self._registrar("Votação aberta")
        self._notificar("estado")
        return self.__zeresima

    def encerrar(self, senha):
        if not self.__eleicao.presidente.autenticar(senha):
            self._registrar("Tentativa de encerramento com senha incorreta")
            raise SenhaIncorreta("Senha do presidente da mesa incorreta.")
        if self.__estado is EstadoUrna.VOTANDO:
            raise UrnaOcupada("Há um eleitor votando. Aguarde ele terminar.")
        if self.__estado is not EstadoUrna.AGUARDANDO_ELEITOR:
            raise OperacaoInvalida("A votação não está aberta.")
        self.__estado = EstadoUrna.ENCERRADA
        self.__encerramento = datetime.now()
        self._registrar("Votação encerrada")
        self.__boletim = self.__impressora.emitir_boletim(self)
        self._registrar("Boletim de urna emitido")
        self._notificar("estado")
        return self.__boletim

    # ------------------------------------------------------------ liberação
    def verificar_disponivel(self):
        """Lança a exceção adequada se a urna não puder receber um eleitor agora."""
        if not self.__conectada:
            raise UrnaDesconectada("A urna não está conectada ao terminal do mesário.")
        if self.__estado is EstadoUrna.PREPARADA:
            raise VotacaoNaoIniciada("A votação ainda não foi aberta.")
        if self.__estado is EstadoUrna.ENCERRADA:
            raise VotacaoEncerrada("A votação já foi encerrada.")
        if self.__estado is EstadoUrna.VOTANDO:
            raise UrnaOcupada("Há um eleitor votando.")

    def habilitar(self, eleitor):
        self.verificar_disponivel()
        if eleitor.votou:
            raise EleitorJaVotou(f"{eleitor.nome} já votou.")
        self.__sessao = SessaoVotacao(self.__eleicao.cargos)
        self.__eleitor_votando = eleitor
        self.__estado = EstadoUrna.VOTANDO
        self._registrar("Eleitor habilitado")  # o log não identifica o eleitor
        self._notificar("liberada")

    # ------------------------------------------------------------ teclas
    def _sessao_ativa(self):
        if self.__estado is not EstadoUrna.VOTANDO:
            raise UrnaBloqueada("Aguarde a liberação pelo mesário.")
        return self.__sessao

    def digitar(self, digito):
        ok = self._sessao_ativa().digitar(digito)
        self._notificar("tecla")
        return ok

    def votar_branco(self):
        ok = self._sessao_ativa().votar_branco()
        self._notificar("tecla")
        return ok

    def corrigir(self):
        ok = self._sessao_ativa().corrigir()
        self._notificar("tecla")
        return ok

    def confirmar(self):
        """Confirma o voto do cargo atual. Devolve a Previa registrada ou None."""
        sessao = self._sessao_ativa()
        cargo = sessao.cargo_atual
        previa = sessao.confirmar()
        if previa is None:
            return None
        self._registrar(f"Voto computado: {cargo.nome}")
        if sessao.finalizada:
            self._finalizar_eleitor()
        else:
            self._notificar("voto")
        return previa

    def interromper(self, senha):
        """Finaliza a votação de um eleitor que desistiu ou abandonou a cabine.

        * Nenhum voto confirmado: a votação é SUSPENSA. O eleitor não consta como
          votante e pode ser liberado de novo depois.
        * Pelo menos um voto confirmado: os votos confirmados valem, os cargos que
          faltavam são computados como NULOS e o eleitor consta como votante.
        """
        if not self.__eleicao.presidente.autenticar(senha):
            self._registrar("Tentativa de interrupção com senha incorreta")
            raise SenhaIncorreta("Senha do presidente da mesa incorreta.")
        if self.__estado is not EstadoUrna.VOTANDO:
            raise OperacaoInvalida("Não há eleitor votando.")

        sessao = self.__sessao
        confirmados = sessao.votos_confirmados
        if confirmados == 0:
            resultado = ResultadoInterrupcao(False, 0, 0)
            self._registrar("Votação do eleitor suspensa (nenhum voto confirmado)")
        else:
            anulados = sessao.anular_restantes()
            self.__eleitor_votando.registrar_comparecimento()
            resultado = ResultadoInterrupcao(True, confirmados, anulados)
            self._registrar(f"Votação do eleitor interrompida: {anulados} voto(s) computado(s) como nulo")
        self.__eleitor_votando = None
        self.__sessao = None
        self.__estado = EstadoUrna.AGUARDANDO_ELEITOR
        self._notificar("interrompida")
        return resultado

    def _finalizar_eleitor(self):
        self.__eleitor_votando.registrar_comparecimento()
        self.__eleitor_votando = None
        self.__sessao = None
        self.__estado = EstadoUrna.AGUARDANDO_ELEITOR
        self._registrar("Eleitor concluiu a votação")
        self._notificar("fim_eleitor")
