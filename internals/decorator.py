"""
MIT License

Copyright (c) 2020-present noaione

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Optional

from sanic.response import text

if TYPE_CHECKING:
    from sanic import Request

    from .vth import SanicVTHell


__all__ = ("secure_access", "check_auth_header")


def check_auth_header(request: Request):
    app: SanicVTHell = request.app
    secure_pass = app.config.WEBSERVER_PASSWORD
    auth_header: Optional[str] = request.headers.get("Authorization") or request.headers.get("authorization")
    x_auth_token = request.headers.get("X-Auth-Token") or request.headers.get("x-auth-token")
    x_password = request.headers.get("X-Password") or request.headers.get("x-password")

    if auth_header is not None:
        if not auth_header.startswith("Password"):
            return False
        actual_password = auth_header.replace("Password ", "")
        if actual_password == secure_pass:
            return True

    x_auth_value = x_auth_token or x_password
    if x_auth_value is not None:
        if x_auth_value == secure_pass:
            return True

    return False


def secure_access(wrapped):
    def decorator(f):
        @wraps(f)
        async def decorated_routes(request: Request, *args, **kwargs):
            is_auth = check_auth_header(request)
            if is_auth:
                return await f(request, *args, **kwargs)
            else:
                return text("Unauthorized", 401)

        return decorated_routes

    return decorator(wrapped)
