import warnings

from pydantic.warnings import PydanticDeprecatedSince20

warnings.filterwarnings('ignore', category=PydanticDeprecatedSince20)
