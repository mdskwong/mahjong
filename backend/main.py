from __future__ import annotations
import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rules import patterns
from rules.models import Dragon, Hand, Meld, MeldType, Suit, Tile, Wind


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
        {"fan": 1, "name": "Ping Hu (Peace Hand)", "desc": "All melds are chows, pair is not a value pair"},
        {"fan": 1, "name": "Self-Pick", "desc": "Win by drawing the winning tile yourself"},
        {"fan": 1, "name": "Fully Concealed Hand", "desc": "No melds revealed, won on discard"},
        {"fan": 1, "name": "Dragon Pong", "desc": "Pong/kong of any dragon tile"},
        {"fan": 1, "name": "Value Wind Pong", "desc": "Pong/kong of seat wind or prevalent wind"},
        {"fan": 2, "name": "Mixed Triple Chow", "desc": "Same sequence in all 3 suits"},
        {"fan": 2, "name": "Mixed One Suit (Half Flush)", "desc": "All tiles in one suit + honors"},
        {"fan": 2, "name": "All Pongs", "desc": "All melds are pongs/kongs"},
        {"fan": 2, "name": "Double Dragon Pong", "desc": "Two pongs of dragons"},
        {"fan": 2, "name": "Double Value Wind Pong", "desc": "Both seat and prevalent wind pongs"},
        {"fan": 2, "name": "Outside Hand", "desc": "Every meld has a terminal or honor"},
        {"fan": 3, "name": "Pure Triple Chow", "desc": "Same sequence twice in same suit"},
        {"fan": 3, "name": "All Simples", "desc": "No terminals or honors (2-8 only)"},
        {"fan": 3, "name": "Three Concealed Pongs", "desc": "Three concealed pongs/kongs"},
        {"fan": 5, "name": "Little Three Dragons", "desc": "Two dragon pongs + dragon pair"},
        {"fan": 5, "name": "Three Kongs", "desc": "Three kongs in the hand"},
        {"fan": 5, "name": "All Terminals and Honors", "desc": "Every tile is terminal or honor"},
        {"fan": 7, "name": "Big Three Dragons", "desc": "Three pongs of dragons"},
        {"fan": 7, "name": "Four Small Winds", "desc": "Three wind pongs + wind pair"},
        {"fan": 7, "name": "Pure One Suit (Full Flush)", "desc": "All tiles in one suit, no honors"},
    ]
}


def handle_score(body: dict) -> dict:
    try:
        concealed = [_parse_tile(t) for t in body["concealed_tiles"]]
        melds_raw = body.get("melds", [])
        melds = [_parse_meld(m) for m in melds_raw]
        hand = Hand(
            concealed_tiles=concealed,
            melds=melds,
            is_self_drawn=body.get("is_self_drawn", False),
            seat_wind=_parse_wind(body.get("seat_wind", "east")),
            prevalent_wind=_parse_wind(body.get("prevalent_wind", "east")),
        )
        return patterns.score_hand(hand)
    except Exception as e:
        return {"error": str(e), "total_fan": 0, "fans": [], "total_payable": 0}


FRONTEND_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "index.html")


class Handler(BaseHTTPRequestHandler):
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
        else:
            self._send_json({"error": "Not found"}, 404)


def main():
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    server = HTTPServer((host, port), Handler)
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