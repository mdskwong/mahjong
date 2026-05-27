from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional


class Suit(Enum):
    BAMBOO = "bamboo"
    CHARACTERS = "characters"
    DOTS = "dots"
    WIND = "wind"
    DRAGON = "dragon"


class Wind(Enum):
    EAST = "east"
    SOUTH = "south"
    WEST = "west"
    NORTH = "north"


class Dragon(Enum):
    RED = "red"
    GREEN = "green"
    WHITE = "white"


class MeldType(Enum):
    CHOW = "chow"
    PONG = "pong"
    KONG = "kong"
    PAIR = "pair"


@dataclass(frozen=True)
class Tile:
    suit: Suit
    value: int

    def __hash__(self):
        return hash((self.suit.value, self.value))

    def is_honor(self) -> bool:
        return self.suit in (Suit.WIND, Suit.DRAGON)

    def is_terminal(self) -> bool:
        return self.suit in (Suit.BAMBOO, Suit.CHARACTERS, Suit.DOTS) and self.value in (1, 9)

    def is_simple(self) -> bool:
        return self.suit in (Suit.BAMBOO, Suit.CHARACTERS, Suit.DOTS) and 2 <= self.value <= 8

    def is_dragon(self) -> bool:
        return self.suit == Suit.DRAGON

    def is_wind(self) -> bool:
        return self.suit == Suit.WIND

    def to_dict(self):
        return {"suit": self.suit.value, "value": self.value}

    def display(self) -> str:
        symbols = {
            Suit.BAMBOO: "🀑🀒🀓🀔🀕🀖🀗🀘",
            Suit.CHARACTERS: "🀇🀈🀉🀊🀋🀌🀍🀎🀏",
            Suit.DOTS: "🀙🀚🀛🀜🀝🀞🀟🀠🀡",
        }
        if self.suit in symbols:
            return symbols[self.suit][self.value - 1]
        if self.suit == Suit.WIND:
            return ["🀀", "🀁", "🀂", "🀃"][self.value - 1]
        if self.suit == Suit.DRAGON:
            return {1: "🀄", 2: "🀅", 3: "🀆"}.get(self.value, "?")
        return f"{self.suit.value}:{self.value}"


@dataclass
class Meld:
    tiles: List[Tile]
    meld_type: MeldType
    concealed: bool = True

    def is_three_dragons(self) -> bool:
        if self.meld_type not in (MeldType.PONG, MeldType.KONG):
            return False
        return all(t.is_dragon() for t in self.tiles)

    def is_value_pair(self, seat_wind: Wind, prevalent_wind: Wind) -> bool:
        if self.meld_type != MeldType.PAIR:
            return False
        return self._is_value_tile(seat_wind, prevalent_wind)

    def _is_value_tile(self, seat_wind: Wind, prevalent_wind: Wind) -> bool:
        t = self.tiles[0]
        if t.is_dragon():
            return True
        if t.is_wind():
            wind_val = t.value
            seat_val = {"east": 1, "south": 2, "west": 3, "north": 4}[seat_wind.value]
            prevalent_val = {"east": 1, "south": 2, "west": 3, "north": 4}[prevalent_wind.value]
            return wind_val in (seat_val, prevalent_val)
        return False

    def to_dict(self):
        return {"tiles": [t.to_dict() for t in self.tiles], "meld_type": self.meld_type.value, "concealed": self.concealed}


@dataclass
class Hand:
    concealed_tiles: List[Tile]
    melds: List[Meld] = field(default_factory=list)
    winning_tile: Optional[Tile] = None
    is_self_drawn: bool = False
    seat_wind: Wind = Wind.EAST
    prevalent_wind: Wind = Wind.EAST
    discarder_wind: Optional[Wind] = None

    def all_tiles(self) -> List[Tile]:
        result = list(self.concealed_tiles)
        for meld in self.melds:
            result.extend(meld.tiles)
        return result


@dataclass
class FanResult:
    name: str
    fan: int
    name_zh: str = ""

    def to_dict(self):
        return {"name": self.name, "name_zh": self.name_zh, "fan": self.fan}


@dataclass
class Player:
    name: str
    seat_wind: Wind
    score: int = 0


@dataclass
class GameState:
    players: List[Player]
    prevalent_wind: Wind = Wind.EAST