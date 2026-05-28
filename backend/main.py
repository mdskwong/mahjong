from __future__ import annotations
import json
import os
import sys
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rules import patterns
from rules.models import Dragon, Hand, Meld, MeldType, Suit, Tile, Wind, GameState, Player


def _parse_tile(d: dict) -> Tile:
    suit_map = {
        "bamboo": Suit.BAMBOO, "b": Suit.BAMBOO,
        "characters": Suit.CHARACTERS, "c": Suit.CHARACTERS, "man": Suit.CHARACTERS, "m": Suit.CHARACTERS,
        "dots": Suit.DOTS, "d": Suit.DOTS, "pin": Suit.DOTS, "p": Suit.DOTS,
        "wind": Suit.WIND, "w": Suit.WIND,
        "dragon": Suit.DRAGON, "dr": Suit.DRAGON,
    }
    suit = suit_map.get(d["suit"].lower())
    if suit is None:
        raise ValueError(f"Unknown suit: {d['suit']}")
    return Tile(suit=suit, value=int(d["value"]))


def _parse_meld(m: dict) -> Meld:
    return Meld(
        tiles=[_parse_tile(t) for t in m["tiles"]],
        meld_type=MeldType(m["meld_type"]),
        concealed=m.get("concealed", True),
    )


def _parse_wind(w: str) -> Wind:
    return Wind(w.lower())


SCORE_HAND_PATH = "/score"

PATTERNS_DATA = {
    "patterns": [
        {"fan": 1, "name": "Ping Hu (Peace Hand)", "name_zh": "平糊", "desc": "All chows, pair is not a value pair"},
        {"fan": 1, "name": "Self-Pick", "name_zh": "自摸", "desc": "Win by drawing the winning tile yourself"},
        {"fan": 1, "name": "Fully Concealed Hand", "name_zh": "門前清", "desc": "No melds revealed, won on discard"},
        {"fan": 1, "name": "Dragon Pong", "name_zh": "番牌 (箭牌)", "desc": "Pong/kong of any dragon tile"},
        {"fan": 1, "name": "Value Wind Pong", "name_zh": "番牌 (風牌)", "desc": "Pong/kong of seat wind or prevalent wind"},
        {"fan": 2, "name": "Double Dragon Pong", "name_zh": "雙箭牌", "desc": "Two pongs of dragons"},
        {"fan": 2, "name": "Double Value Wind Pong", "name_zh": "雙風牌", "desc": "Both seat and prevalent wind pongs"},
        {"fan": 3, "name": "Triple Value Wind Pong", "name_zh": "三風牌", "desc": "Three value wind pongs"},
        {"fan": 3, "name": "Mixed One Suit (Half Flush)", "name_zh": "混一色", "desc": "All tiles in one suit + honors"},
        {"fan": 3, "name": "All Pongs", "name_zh": "對對糊", "desc": "All melds are pongs/kongs"},
        {"fan": 5, "name": "Little Three Dragons", "name_zh": "小三元", "desc": "Two dragon pongs + dragon pair"},
        {"fan": 7, "name": "Pure One Suit (Full Flush)", "name_zh": "清一色", "desc": "All tiles in one suit, no honors"},
        {"fan": 8, "name": "Big Three Dragons", "name_zh": "大三元", "desc": "Three pongs of dragons"},
        {"fan": 8, "name": "Four Small Winds", "name_zh": "小四喜", "desc": "Three wind pongs + wind pair"},
        {"fan": 10, "name": "Thirteen Orphans", "name_zh": "十三幺", "desc": "One of each terminal/honor plus one duplicate"},
        {"fan": 10, "name": "Big Four Winds", "name_zh": "大四喜", "desc": "Four pongs of winds"},
        {"fan": 10, "name": "All Honors", "name_zh": "字一色", "desc": "All tiles are winds or dragons"},
        {"fan": 10, "name": "Pure Terminals", "name_zh": "清么九", "desc": "All tiles are 1 or 9 of suits"},
        {"fan": 10, "name": "Nine Gates", "name_zh": "九子連環", "desc": "1112345678999 in one suit fully concealed + 1 extra"},
        {"fan": 10, "name": "Eighteen Arhats", "name_zh": "十八羅漢", "desc": "Four kongs"},
    ]
}

game_state = GameState(
    players=[
        Player(name="Player 1", seat_wind=Wind.EAST),
        Player(name="Player 2", seat_wind=Wind.SOUTH),
        Player(name="Player 3", seat_wind=Wind.WEST),
        Player(name="Player 4", seat_wind=Wind.NORTH),
    ]
)


def handle_score(body: dict) -> dict:
    try:
        concealed = [_parse_tile(t) for t in body["concealed_tiles"]]
        melds_raw = body.get("melds", [])
        melds = [_parse_meld(m) for m in melds_raw]
        discarder = body.get("discarder_wind")
        base_point = int(body.get("base_point", 1))
        limit_hand_points = int(body.get("limit_hand_points", 10000))
        hand = Hand(
            concealed_tiles=concealed,
            melds=melds,
            is_self_drawn=body.get("is_self_drawn", False),
            seat_wind=_parse_wind(body.get("seat_wind", "east")),
            prevalent_wind=_parse_wind(body.get("prevalent_wind", "east")),
            discarder_wind=_parse_wind(discarder) if discarder else None
        )
        return patterns.apply_round_scores(game_state, hand, base_point, limit_hand_points)
    except Exception as e:
        return {"error": str(e), "total_fan": 0, "fans": [], "total_payable": 0}


FRONTEND_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "index.html")


class Handler(BaseHTTPRequestHandler):
    def handle(self):
        try:
            super().handle()
        except (ConnectionResetError, BrokenPipeError):
            pass

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str, status: int = 200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "" or path == "/" or path == "/ui" or path == "/ui/index.html":
            try:
                with open(FRONTEND_PATH, "r", encoding="utf-8") as f:
                    html = f.read()
                self._send_html(html)
            except FileNotFoundError:
                self._send_html("<h1>Frontend not found</h1>", 404)
        elif path == "/patterns":
            self._send_json(PATTERNS_DATA)
        elif path == "/state":
            state_data = {
                "prevalent_wind": game_state.prevalent_wind.value,
                "players": [
                    {
                        "name": p.name,
                        "seat_wind": p.seat_wind.value,
                        "score": p.score
                    } for p in game_state.players
                ]
            }
            self._send_json(state_data)
        elif path == "/score":
            self._send_json({"message": "Send a POST request to /score with a JSON body"})
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/score":
            content_length = int(self.headers.get("Content-Length", 0))
            body_data = self.rfile.read(content_length)
            body = json.loads(body_data.decode("utf-8"))
            result = handle_score(body)
            self._send_json(result)
        elif path == "/players":
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                body_data = self.rfile.read(content_length)
                body = json.loads(body_data.decode("utf-8"))
                for p in game_state.players:
                    if p.seat_wind.value in body:
                        p.name = body[p.seat_wind.value]
                self._send_json({"message": "Players updated successfully"})
            else:
                self._send_json({"error": "Empty request body"}, 400)
        elif path == "/rotate-winds":
            wind_transition = {
                Wind.EAST: Wind.NORTH,
                Wind.SOUTH: Wind.EAST,
                Wind.WEST: Wind.SOUTH,
                Wind.NORTH: Wind.WEST
            }
            for p in game_state.players:
                p.seat_wind = wind_transition[p.seat_wind]
            self._send_json({"message": "Winds rotated successfully"})
        elif path == "/reset-scores":
            for p in game_state.players:
                p.score = 0
            self._send_json({"message": "Scores reset successfully"})
        else:
            self._send_json({"error": "Not found"}, 404)


def main():
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Server running on http://{host}:{port}")
    print(f"API: http://localhost:{port}/score (POST)")
    print(f"UI:  http://localhost:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.server_close()


if __name__ == "__main__":
    main()