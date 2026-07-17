"""Модуль middleware для проверки владельца бота."""

from .owner_check import OwnerCheckMiddleware

__all__ = ["OwnerCheckMiddleware"]
