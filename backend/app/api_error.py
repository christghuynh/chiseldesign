"""ApiError, kept in a module that imports nothing from the app.

It lives here (and is re-exported from `app.api.errors`) because `app.api` imports every route and the routes
import `app.auth.verify`; if `verify` had to import `app.api` for this class, importing `verify` first would
loop back into itself.
"""


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message
