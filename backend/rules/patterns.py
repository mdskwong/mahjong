from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
from typing import Callable, Dict, List, Set, Tuple

from .models import FanResult, Hand, Meld, MeldType, Suit, Tile, Wind, Player, GameState


def _tile_counts(tiles: List[Tile]) -> Dict[Tuple[str, int], int]:
    c: Dict[Tuple[str, int], int] = {}
    for t in tiles:
        key = (t.suit.value, t.value)
        c[key] = c.get(key, 0) + 1
    return c


def _decompose(tiles: List[Tile]) -> List[List[Meld]]:
    if len(tiles) % 3 != 2:
        return []

    results: List[List[Meld]] = []
    counts = _tile_counts(tiles)

    def backtrack(current_melds: List[Meld], remaining_count: int):
        if remaining_count == 0:
            results.append(list(current_melds))
            return

        keys = sorted(k for k, v in counts.items() if v > 0)
        if not keys:
            return

        suit_str, value = keys[0]
        suit = Suit(suit_str)
        cnt = counts[(suit_str, value)]

        if cnt >= 2 and remaining_count == 2:
            counts[(suit_str, value)] -= 2
            if counts[(suit_str, value)] == 0:
                del counts[(suit_str, value)]
            current_melds.append(Meld(
                tiles=[Tile(suit, value), Tile(suit, value)],
                meld_type=MeldType.PAIR
            ))
            backtrack(current_melds, 0)
            current_melds.pop()
            counts[(suit_str, value)] = cnt

        elif remaining_count >= 3:
            if cnt >= 3:
                counts[(suit_str, value)] -= 3
                if counts[(suit_str, value)] == 0:
                    del counts[(suit_str, value)]
                current_melds.append(Meld(
                    tiles=[Tile(suit, value) for _ in range(3)],
                    meld_type=MeldType.PONG
                ))
                backtrack(current_melds, remaining_count - 3)
                current_melds.pop()
                counts[(suit_str, value)] = cnt

            if cnt >= 4:
                counts[(suit_str, value)] -= 4
                if counts[(suit_str, value)] == 0:
                    del counts[(suit_str, value)]
                current_melds.append(Meld(
                    tiles=[Tile(suit, value) for _ in range(4)],
                    meld_type=MeldType.KONG
                ))
                backtrack(current_melds, remaining_count - 4)
                current_melds.pop()
                counts[(suit_str, value)] = cnt

            if cnt >= 1 and suit in (Suit.BAMBOO, Suit.CHARACTERS, Suit.DOTS) and 1 <= value <= 7:
                v2 = (suit_str, value + 1)
                v3 = (suit_str, value + 2)
                if counts.get(v2, 0) >= 1 and counts.get(v3, 0) >= 1:
                    for v in [(suit_str, value), v2, v3]:
                        counts[v] -= 1
                        if counts[v] == 0:
                            del counts[v]
                    current_melds.append(Meld(
                        tiles=[Tile(suit, value), Tile(suit, value + 1), Tile(suit, value + 2)],
                        meld_type=MeldType.CHOW
                    ))
                    backtrack(current_melds, remaining_count - 3)
                    current_melds.pop()
                    for v, orig_val in [((suit_str, value), value), (v2, value + 1), (v3, value + 2)]:
                        counts[v] = counts.get(v, 0) + 1

            if cnt >= 1 and remaining_count > 2:
                counts[(suit_str, value)] -= 1
                if counts[(suit_str, value)] == 0:
                    del counts[(suit_str, value)]
                backtrack(current_melds, remaining_count - 1)
                counts[(suit_str, value)] = cnt

    backtrack([], len(tiles))
    return results


def _is_ping_hu(melds: List[Meld], seat_wind: Wind, prevalent_wind: Wind) -> bool:
    if len(melds) != 5:
        return False
    pair = None
    chow_count = 0
    for m in melds:
        if m.meld_type == MeldType.PAIR:
            pair = m
        elif m.meld_type == MeldType.CHOW:
            chow_count += 1
        else:
            return False
    return chow_count == 4 and pair is not None and not pair.is_value_pair(seat_wind, prevalent_wind)


def _all_pongs(melds: List[Meld]) -> bool:
    if len(melds) != 5:
        return False
    return all(m.meld_type in (MeldType.PONG, MeldType.KONG, MeldType.PAIR) for m in melds) and sum(1 for m in melds if m.meld_type == MeldType.PAIR) == 1


def _is_pure_one_suit(tiles: List[Tile]) -> bool:
    suits = {t.suit for t in tiles if not t.is_honor()}
    return len(suits) == 1


def _has_honors(tiles: List[Tile]) -> bool:
    return any(t.is_honor() for t in tiles)


def _is_small_three_dragons(melds: List[Meld]) -> bool:
    dragon_pongs = 0
    dragon_pair = False
    for m in melds:
        t = m.tiles[0]
        if t.is_dragon():
            if m.meld_type in (MeldType.PONG, MeldType.KONG):
                dragon_pongs += 1
            elif m.meld_type == MeldType.PAIR:
                dragon_pair = True
    return dragon_pongs == 2 and dragon_pair


def _is_big_three_dragons(melds: List[Meld]) -> bool:
    return sum(1 for m in melds if m.is_three_dragons()) == 3


def _is_small_four_winds(melds: List[Meld]) -> bool:
    wind_pongs = 0
    wind_pair = False
    for m in melds:
        t = m.tiles[0]
        if t.is_wind():
            if m.meld_type in (MeldType.PONG, MeldType.KONG):
                wind_pongs += 1
            elif m.meld_type == MeldType.PAIR and not wind_pair:
                wind_pair = True
    return wind_pongs == 3 and wind_pair


def _is_mixed_one_suit(tiles: List[Tile]) -> bool:
    suits = {t.suit for t in tiles if not t.is_honor()}
    return len(suits) == 1 and _has_honors(tiles)


def _is_thirteen_orphans(tiles: List[Tile]) -> bool:
    if len(tiles) != 14:
        return False
    required_tiles = {
        Tile(Suit.BAMBOO, 1), Tile(Suit.BAMBOO, 9),
        Tile(Suit.CHARACTERS, 1), Tile(Suit.CHARACTERS, 9),
        Tile(Suit.DOTS, 1), Tile(Suit.DOTS, 9),
        Tile(Suit.WIND, 1), Tile(Suit.WIND, 2), Tile(Suit.WIND, 3), Tile(Suit.WIND, 4),
        Tile(Suit.DRAGON, 1), Tile(Suit.DRAGON, 2), Tile(Suit.DRAGON, 3)
    }
    tile_set = set(tiles)
    return tile_set == required_tiles


def _is_nine_gates(concealed: List[Tile], melds: List[Meld]) -> bool:
    if melds:
        return False
    if len(concealed) != 14:
        return False
    suits = {t.suit for t in concealed}
    if len(suits) != 1:
        return False
    suit = list(suits)[0]
    if suit.value not in ("bamboo", "characters", "dots"):
        return False
    counts = Counter(t.value for t in concealed)
    for v in range(1, 10):
        required = 3 if v in (1, 9) else 1
        if counts[v] < required:
            return False
    return True


def _dragon_pong_count(melds: List[Meld]) -> int:
    return sum(1 for m in melds if m.is_three_dragons())


def _value_wind_pong_count(melds: List[Meld], seat_wind: Wind, prevalent_wind: Wind) -> int:
    count = 0
    for m in melds:
        if m.meld_type not in (MeldType.PONG, MeldType.KONG):
            continue
        t = m.tiles[0]
        if not t.is_wind():
            continue
        wind_val = t.value
        seat_val = {"east": 1, "south": 2, "west": 3, "north": 4}[seat_wind.value]
        prevalent_val = {"east": 1, "south": 2, "west": 3, "north": 4}[prevalent_wind.value]
        if wind_val == seat_val:
            count += 1
        if wind_val == prevalent_val:
            count += 1
    return count


def _is_all_honors(tiles: List[Tile]) -> bool:
    return all(t.is_honor() for t in tiles)

def _is_pure_terminals(tiles: List[Tile]) -> bool:
    return all(t.is_terminal() and not t.is_honor() for t in tiles)

def _is_eighteen_arhats(melds: List[Meld]) -> bool:
    return sum(1 for m in melds if m.meld_type == MeldType.KONG) == 4

def _is_big_four_winds(melds: List[Meld]) -> bool:
    wind_pongs = sum(1 for m in melds if m.tiles[0].is_wind() and m.meld_type in (MeldType.PONG, MeldType.KONG))
    return wind_pongs == 4

@dataclass
class PatternDefinition:
    name: str
    name_zh: str
    fan: int
    condition: Callable[[Hand, List[Meld], List[Tile]], bool]

PATTERN_REGISTRY: List[PatternDefinition] = [
    PatternDefinition(
        name="Ping Hu (Peace Hand)",
        name_zh="平糊",
        fan=1,
        condition=lambda h, m, t: _is_ping_hu(m, h.seat_wind, h.prevalent_wind)
    ),
    PatternDefinition(
        name="Self-Pick",
        name_zh="自摸",
        fan=1,
        condition=lambda h, m, t: h.is_self_drawn
    ),
    PatternDefinition(
        name="Fully Concealed Hand",
        name_zh="門前清",
        fan=1,
        condition=lambda h, m, t: all(x.concealed for x in m if x.meld_type != MeldType.PAIR) and not h.is_self_drawn
    ),
    PatternDefinition(
        name="Dragon Pong",
        name_zh="番牌 (箭牌)",
        fan=1,
        condition=lambda h, m, t: _dragon_pong_count(m) == 1 and not _is_small_three_dragons(m)
    ),
    PatternDefinition(
        name="Double Dragon Pong",
        name_zh="雙箭牌",
        fan=2,
        condition=lambda h, m, t: _dragon_pong_count(m) == 2 and not _is_small_three_dragons(m)
    ),
    PatternDefinition(
        name="Value Wind Pong",
        name_zh="番牌 (風牌)",
        fan=1,
        condition=lambda h, m, t: _value_wind_pong_count(m, h.seat_wind, h.prevalent_wind) == 1
    ),
    PatternDefinition(
        name="Double Value Wind Pong",
        name_zh="雙風牌",
        fan=2,
        condition=lambda h, m, t: _value_wind_pong_count(m, h.seat_wind, h.prevalent_wind) == 2
    ),
    PatternDefinition(
        name="Triple Value Wind Pong",
        name_zh="三風牌",
        fan=3,
        condition=lambda h, m, t: _value_wind_pong_count(m, h.seat_wind, h.prevalent_wind) == 3
    ),
    PatternDefinition(
        name="Mixed One Suit (Half Flush)",
        name_zh="混一色",
        fan=3,
        condition=lambda h, m, t: _is_mixed_one_suit(t)
    ),
    PatternDefinition(
        name="All Pongs",
        name_zh="對對糊",
        fan=3,
        condition=lambda h, m, t: _all_pongs(m)
    ),
    PatternDefinition(
        name="Little Three Dragons",
        name_zh="小三元",
        fan=5,
        condition=lambda h, m, t: _is_small_three_dragons(m)
    ),
    PatternDefinition(
        name="Pure One Suit (Full Flush)",
        name_zh="清一色",
        fan=7,
        condition=lambda h, m, t: _is_pure_one_suit(t) and not _has_honors(t)
    ),
    PatternDefinition(
        name="Big Three Dragons",
        name_zh="大三元",
        fan=8,
        condition=lambda h, m, t: _is_big_three_dragons(m)
    ),
    PatternDefinition(
        name="Four Small Winds",
        name_zh="小四喜",
        fan=8,
        condition=lambda h, m, t: _is_small_four_winds(m)
    ),
    PatternDefinition(
        name="Thirteen Orphans",
        name_zh="十三幺",
        fan=10,
        condition=lambda h, m, t: _is_thirteen_orphans(t)
    ),
    PatternDefinition(
        name="Big Four Winds",
        name_zh="大四喜",
        fan=10,
        condition=lambda h, m, t: _is_big_four_winds(m)
    ),
    PatternDefinition(
        name="All Honors",
        name_zh="字一色",
        fan=10,
        condition=lambda h, m, t: _is_all_honors(t)
    ),
    PatternDefinition(
        name="Pure Terminals",
        name_zh="清么九",
        fan=10,
        condition=lambda h, m, t: _is_pure_terminals(t)
    ),
    PatternDefinition(
        name="Nine Gates",
        name_zh="九子連環",
        fan=10,
        condition=lambda h, m, t: _is_nine_gates(h.concealed_tiles, h.melds)
    ),
    PatternDefinition(
        name="Eighteen Arhats",
        name_zh="十八羅漢",
        fan=10,
        condition=lambda h, m, t: _is_eighteen_arhats(m)
    ),
]


def detect_fans(hand: Hand, melds: List[Meld]) -> List[FanResult]:
    fans: List[FanResult] = []
    all_tiles = hand.concealed_tiles + [t for m in melds for t in m.tiles]

    for pattern in PATTERN_REGISTRY:
        if pattern.condition(hand, melds, all_tiles):
            fans.append(FanResult(name=pattern.name, name_zh=pattern.name_zh, fan=pattern.fan))

    return fans


def score_hand(hand: Hand) -> dict:
    counts = Counter(hand.all_tiles())
    for tile, count in counts.items():
        if count > 4:
            return {"error": f"Invalid hand: More than 4 tiles of {tile.suit.value} {tile.value}", "total_fan": 0, "fans": [], "total_payable": 0}

    if len(hand.concealed_tiles) % 3 != 2:
        return {"error": f"Invalid hand size: {len(hand.concealed_tiles)} tiles (must be 2 mod 3)", "total_fan": 0, "fans": [], "total_payable": 0}

    if len(hand.concealed_tiles) < 2:
        return {"error": "Too few tiles in hand", "total_fan": 0, "fans": [], "total_payable": 0}

    all_tiles = hand.all_tiles()
    is_thirteen = _is_thirteen_orphans(all_tiles)
    is_nine = _is_nine_gates(hand.concealed_tiles, hand.melds)

    decompositions = _decompose(hand.concealed_tiles)

    if is_thirteen or is_nine:
        if not decompositions:
            decompositions = [[]]
        else:
            decompositions.append([])

    if not decompositions:
        return {"error": "Not a winning hand - cannot form 4 melds + 1 pair", "total_fan": 0, "fans": [], "total_payable": 0}

    best_score = -1
    best_fans: List[FanResult] = []

    for melds in decompositions:
        all_melds = melds + hand.melds
        fans = detect_fans(hand, all_melds)
        total_fan = sum(f.fan for f in fans)

        if total_fan > best_score:
            best_score = total_fan
            best_fans = fans

    base = 1
    total = base << best_score if best_score < 10 else 0
    is_limit = best_score >= 10 or total >= 10000

    if is_limit:
        total = 10000
        best_score = max(best_score, 10)

    is_dealer = hand.seat_wind == Wind.EAST
    dealer_mult = 1
    if is_dealer:
        dealer_mult = 2

    total_payable = total * dealer_mult

    return {
        "total_fan": best_score,
        "fans": [f.to_dict() for f in best_fans],
        "base_score": base,
        "is_limit": is_limit,
        "dealer_multiplier": dealer_mult,
        "total_payable": total_payable,
        "winner": hand.seat_wind.value,
    }


def apply_round_scores(game_state: GameState, hand: Hand) -> dict:
    """
    Calculates the winning hand and distributes the points among the 4 players.
    """
    result = score_hand(hand)
    if "error" in result:
        return result

    total_payable = result["total_payable"]
    winner_wind = hand.seat_wind
    
    winner = next(p for p in game_state.players if p.seat_wind == winner_wind)

    if hand.is_self_drawn:
        # Self-drawn (Zimo): All 3 other players pay the winner
        for player in game_state.players:
            if player.seat_wind != winner_wind:
                player.score -= total_payable
                winner.score += total_payable
    else:
        # Discard (Ron): Only the discarder pays the winner
        if not hand.discarder_wind:
            return {"error": "discarder_wind must be provided if not self-drawn"}
            
        discarder = next(p for p in game_state.players if p.seat_wind == hand.discarder_wind)
        discarder.score -= total_payable
        winner.score += total_payable
        
    return result