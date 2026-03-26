from __future__ import annotations

from core.presets.validator import ValidationReport


class EngineLauncher:
    def __init__(
        self,
        paths,
        repository,
        selection,
        compiler,
        validator,
        registry,
        status_service,
        adapters,
    ):
        self._paths = paths
        self._repository = repository
        self._selection = selection
        self._compiler = compiler
        self._validator = validator
        self._registry = registry
        self._status_service = status_service
        self._adapters = dict(adapters)

    def start(self, engine: str):
        adapter = self._adapter(engine)
        preset = self._selection.ensure_selected_preset(engine)
        if preset is None:
            raise ValueError(f"No preset selected for {engine}")

        compiled = self._compiler.compile(adapter, preset)
        if not compiled.ok:
            self._registry.write_last_validation(engine, ValidationReport(success=False, steps=[]))
            raise ValueError(f"Preset compilation failed for {engine}")

        report = self._validator.validate(adapter, compiled)
        self._registry.write_last_validation(engine, report)
        if not report.success:
            raise ValueError(f"Preset validation failed for {engine}")

        session = adapter.start(compiled, self._paths.engine_paths(engine).ensure_directories())
        self._registry.write_session(engine, session)
        return session

    def stop(self, engine: str) -> None:
        session = self._registry.read_session(engine)
        if session is None:
            return
        adapter = self._adapter(engine)
        adapter.stop(session, self._paths.engine_paths(engine).ensure_directories())
        self._registry.clear_session(engine)

    def restart(self, engine: str):
        session = self._registry.read_session(engine)
        if session is not None:
            self.stop(engine)
        return self.start(engine)

    def status(self, engine: str):
        return self._status_service.get_status(engine)

    def _adapter(self, engine: str):
        engine_key = str(engine or "").strip().lower()
        adapter = self._adapters.get(engine_key)
        if adapter is None:
            raise ValueError(f"Adapter is not registered for {engine_key}")
        return adapter
