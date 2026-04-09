"""Carga dinámica de instrucciones de agente desde api/agents/."""

from pathlib import Path

_AGENTS_DIR = Path(__file__).resolve().parent.parent / "agents"

_FASE_AGENTE: dict[str, str] = {
    "extraccion": "coordinator",
    "explicacion": "coordinator",
}


def load_agent(name: str) -> str:
    """Lee y retorna el contenido de api/agents/{name}.md.

    Raises:
        FileNotFoundError si el archivo no existe.
    """
    path = _AGENTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Agente no encontrado: {path}")
    return path.read_text(encoding="utf-8")


def get_system_prompt(fase: str) -> str:
    """Retorna el prompt de sistema para la fase dada.

    Fases con IA: 'extraccion' (FASE 0) y 'explicacion' (FASE 8).
    Para fases sin IA lanza ValueError.
    """
    agente = _FASE_AGENTE.get(fase)
    if agente is None:
        raise ValueError(f"No hay agente definido para la fase: {fase!r}")
    return load_agent(agente)
