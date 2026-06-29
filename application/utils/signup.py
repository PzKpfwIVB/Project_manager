import json
from urllib.parse import urlencode

from fastapi import Form


class LoginSignupMessage:
    """
    Custom message to show when redirecting to either the login or to the
    signup page.
    """

    def __init__(self, is_error: bool, content: str) -> None:
        self.is_error = is_error
        self.content = content

    @property
    def serialized(self) -> str:
        return json.dumps(
            {'is_error': self.is_error, 'content': self.content}
        )

    @classmethod
    def deserialize(cls, data: str | None):
        deserialized_data = {'is_error': False, 'content': ''}
        if data is not None:
            deserialized_data = json.loads(data)

        return cls(
            is_error=deserialized_data['is_error'],
            content=deserialized_data['content']
        )

    @property
    def urlencoded(self) -> str:
        return urlencode({'message_data': self.serialized})


class SignupForm:
    def __init__(
            self,
            username: str = Form(...),
            password: str = Form(...),
            email: str = Form(default=''),
            full_name: str = Form(default='')
    ):
        self.username = username
        self.password = password
        self.email = email
        self.full_name = full_name
