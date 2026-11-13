"""Exceções do simulador.

Cada regra que pode ser violada tem uma exceção com nome próprio. Assim a
interface sabe exatamente o que aconteceu e mostra a mensagem certa.
"""


class ErroUrna(Exception):
    """Base de todos os erros do simulador."""


class UrnaDesconectada(ErroUrna):
    """O terminal do mesário não está conectado à urna."""


class UrnaBloqueada(ErroUrna):
    """Tecla pressionada na urna sem eleitor liberado pelo mesário."""


class UrnaOcupada(ErroUrna):
    """Já existe um eleitor votando."""


class VotacaoNaoIniciada(ErroUrna):
    """A votação ainda não foi aberta (zerésima não emitida)."""


class VotacaoEncerrada(ErroUrna):
    """A votação já foi encerrada."""


class EleitorNaoEncontrado(ErroUrna, LookupError):
    """O título não pertence a esta seção."""


class EleitorJaVotou(ErroUrna):
    """O eleitor já votou nesta eleição."""


class BiometriaPendente(ErroUrna):
    """O eleitor tem biometria e a digital ainda não foi conferida."""


class SenhaIncorreta(ErroUrna):
    """Senha do presidente da mesa inválida."""


class OperacaoInvalida(ErroUrna):
    """Operação fora de ordem (ex.: abrir uma urna já aberta)."""
