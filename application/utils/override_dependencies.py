from types import TracebackType
from typing import Type

from fastapi import FastAPI


class OverrideDependencies:
    def __init__(self, app: FastAPI, overrides: dict) -> None:
        """
        A context manager that takes a FastAPI application and temporarily
        overrides some dependencies.

        :param app: FastAPI application whose dependencies are to be overridden.
        :param overrides: Mapping, override {this: with this}.
        """

        self._app = app
        self._overrides = overrides

    def __enter__(self) -> FastAPI:

        for to_override, override_with in self._overrides.items():
            # noinspection PyUnresolvedReferences
            self._app.dependency_overrides[to_override] = override_with

        return self._app

    def __exit__(self, exc_type: Type[BaseException] | None,
                 exc_value: BaseException | None,
                 traceback: TracebackType | None) -> None:

        # noinspection PyUnresolvedReferences
        self._app.dependency_overrides.clear()
