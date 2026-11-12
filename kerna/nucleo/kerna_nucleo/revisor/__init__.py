"""Revisor jurídico (KERNA_REVISOR): tercer agente, entre la validación de citas y el registro por artículo."""
from .agente import (ALERTAS, CAUSALES, CONDICIONES, Revisor, ResultadoRevisor, cargar_criterios, esquema_revision,
                     familia_de, familias_en_juego)

__all__ = ["ALERTAS", "CAUSALES", "CONDICIONES", "Revisor", "ResultadoRevisor", "cargar_criterios", "esquema_revision",
           "familia_de", "familias_en_juego"]
