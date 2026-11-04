"""Practice-only configuration and credentials.

THE HOST IS A CONSTANT. No parameter, environment variable or config key can
change it, and a config file that tries (any host/url/environment key, or any
value naming the live host family) is refused rather than ignored. There is no
live constant anywhere in this package, so there is nothing to switch to.

CREDENTIALS live outside the repository in a file only the operator can read
(no group or other permission bits). The token is wrapped so that repr(),
str() and formatting never show it; only the transport reads it, to build the
Authorization header.
"""
import json
import os
import re
import stat

from .errors import ConfigRefused

PRACTICE_HOST = "api-fxpractice.oanda.com"
PRACTICE_BASE_URL = "https://" + PRACTICE_HOST
MODE = "BROKER_PRACTICE"

#: The live host family, spelled so that no source file contains it whole.
_LIVE_MARKER = "fx" + "trade"

DEFAULT_CREDENTIALS_PATH = os.path.join(os.path.expanduser("~"), ".mogo",
                                        "oanda_practice.json")
_REQUIRED_KEYS = ("accountId", "token")
_FORBIDDEN_KEYS = ("host", "url", "baseUrl", "environment", "env", "live")
_ACCOUNT_ID_RE = re.compile(r"^[0-9]{3}-[0-9]{3}-[0-9]{5,12}-[0-9]{3}$")


class Secret(object):
    """A credential that refuses to be displayed."""

    __slots__ = ("_value",)

    def __init__(self, value):
        self._value = value

    def reveal(self):
        return self._value

    def __repr__(self):
        return "Secret(<redacted>)"

    __str__ = __repr__

    def __format__(self, spec):
        return repr(self)

    def __reduce__(self):
        raise TypeError("a Secret cannot be pickled")


class PracticeConfig(object):
    __slots__ = ("account_id", "token")

    def __init__(self, account_id, token):
        if not isinstance(token, Secret):
            raise ConfigRefused("token must be a Secret")
        if not isinstance(account_id, str) or not _ACCOUNT_ID_RE.match(account_id):
            raise ConfigRefused("accountId is not an OANDA account id")
        self.account_id = account_id
        self.token = token

    @property
    def base_url(self):
        return PRACTICE_BASE_URL

    def __repr__(self):
        return "PracticeConfig(account_id=%r, token=<redacted>)" % (self.account_id,)


def load_config(path=DEFAULT_CREDENTIALS_PATH):
    """Read the credentials file, refusing anything that could widen its reach."""
    try:
        info = os.stat(path)
    except OSError:
        raise ConfigRefused("credentials file not found")
    if not stat.S_ISREG(info.st_mode):
        raise ConfigRefused("credentials path is not a regular file")
    if info.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise ConfigRefused("credentials file is readable by group or others; chmod 600 it")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        raise ConfigRefused("credentials file is not readable JSON")
    return config_from_mapping(data)


def config_from_mapping(data):
    if not isinstance(data, dict):
        raise ConfigRefused("credentials must be a JSON object")
    for key in data:
        if key in _FORBIDDEN_KEYS:
            raise ConfigRefused("credentials may not set %r: the host is fixed to practice" % key)
    missing = [k for k in _REQUIRED_KEYS if not isinstance(data.get(k), str) or not data.get(k)]
    if missing:
        raise ConfigRefused("credentials missing %s" % ", ".join(missing))
    for key, value in data.items():
        if key != "token" and _LIVE_MARKER in json.dumps(value).lower():
            raise ConfigRefused("credentials reference the live host family")
    return PracticeConfig(data["accountId"], Secret(data["token"]))
