"""Exceptions raised by the engine. They live here (not in engine.py) so the template registry can
raise them without importing the engine. `app.engine` re-exports both, and that is the public name."""


class TemplateError(Exception):
    """The template is unknown or cannot be built."""


class ParamValidationError(Exception):
    """A parameter is missing, has the wrong type, or is outside its bounds."""
