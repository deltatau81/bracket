from enum import auto

from bracket.utils.types import EnumAutoStr


class UserAccountType(EnumAutoStr):
    REGULAR = auto()
    SCORER = auto()
    DEMO = auto()
