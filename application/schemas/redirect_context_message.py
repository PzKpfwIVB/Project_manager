from urllib.parse import urlencode

from pydantic import BaseModel


class RedirectContextMessage(BaseModel):
    """
    Custom message to pass as context and show it on a redirected page.
    """

    is_error: bool | None = None
    content: str | None = None

    @property
    def urlencoded(self) -> str:
        """
        Encodes the object to a query parameter: `message={encoded object}`.
        """

        return urlencode(self.model_dump(mode='json'))
