from unittest.mock import MagicMock

GUILD_ID, USER_ID, ROLE_ID = 1, 2, 3


def make_http_error(cls, status):
    response = MagicMock(status=status, reason="error")
    return cls(response, "boom")
