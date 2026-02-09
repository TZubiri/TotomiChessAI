import re
from datetime import datetime
import os
import copy
import random


DEFAULT_SAVEFILE = "chess_save.pgn"
PIECE_TYPE_BY_CLASS = {
    "Pawn": "pawn",
    "Knight": "knight",
    "Bishop": "bishop",
    "Rook": "rook",
    "Queen": "queen",
    "King": "king",
}

AI_PERSONALITIES = [
    {
        "id": "basic",
        "name": "Classic",
        "piece_values": {
            "pawn": 1.0,
            "knight": 3.0,
            "bishop": 3.0,
            "rook": 5.0,
            "queen": 9.0,
            "king": 0.0,
        },
    },
    {
        "id": "lasker",
        "name": "Lasker",
        "piece_values": {
            "pawn": 1.0,
            "knight": 3.0,
            "bishop": 3.5,
            "rook": 5.0,
            "queen": 10.0,
            "king": 0.0,
        },
    },
    {
        "id": "kaufman",
        "name": "Kaufman",
        "piece_values": {
            "pawn": 1.0,
            "knight": 3.25,
            "bishop": 3.25,
            "rook": 5.0,
            "queen": 9.75,
            "king": 0.0,
        },
    },
]

AI_DIFFICULTIES = [
    {"plies": 1, "name": "Scout"},
    {"plies": 2, "name": "Thinker"},
    {"plies": 3, "name": "Oracle"},
]

SPECIAL_AI_PROFILES = [
    {
        "id": "d2_pawnwise",
        "name": "Thinker Pawnwise",
        "plies": 2,
        "personality_name": "Pawnwise",
        "piece_values": {
            "pawn": 1.0,
            "knight": 3.0,
            "bishop": 3.0,
            "rook": 5.0,
            "queen": 9.0,
            "king": 0.0,
        },
        "pawn_rank_values": {
            5: 1.1,
            6: 1.3,
            7: 1.5,
            8: 8.0,
        },
        "backward_pawn_value": 0.8,
        "position_multipliers": {
            "center": 1.3,
            "center_cross": 1.2,
            "center_diagonal": 1.15,
            "corner": 0.8,
            "corner_rook": 0.9,
            "corner_touch": 0.85,
            "corner_touch_rook": 0.95,
        },
    },
    {
        "id": "d2_pawnwise_control",
        "name": "Thinker Pawnwise Control",
        "plies": 2,
        "personality_name": "Pawnwise Control",
        "piece_values": {
            "pawn": 1.0,
            "knight": 3.0,
            "bishop": 3.0,
            "rook": 5.0,
            "queen": 9.0,
            "king": 0.0,
        },
        "pawn_rank_values": {
            5: 1.1,
            6: 1.3,
            7: 1.5,
            8: 8.0,
        },
        "backward_pawn_value": 0.8,
        "position_multipliers": {
            "center": 1.3,
            "center_cross": 1.2,
            "center_diagonal": 1.15,
            "corner": 0.8,
            "corner_rook": 0.9,
            "corner_touch": 0.85,
            "corner_touch_rook": 0.95,
        },
        "control_weight": 0.12,
        "opposite_bishop_draw_factor": 0.5,
    }
]

RANDOM_AI_PROFILE = {
    "id": "d0_random",
    "name": "Drifter Random",
    "plies": 0,
    "personality_name": "Random",
    "piece_values": AI_PERSONALITIES[0]["piece_values"],
}


def square_to_position(square):
    if len(square) != 2:
        raise ValueError(f"Invalid square: {square}")
    file_char, rank_char = square[0], square[1]
    if file_char not in "abcdefgh" or rank_char not in "12345678":
        raise ValueError(f"Invalid square: {square}")
    return ord(file_char) - ord("a"), int(rank_char) - 1


def position_to_square(position):
    col, row = position
    if not (0 <= col < 8 and 0 <= row < 8):
        raise ValueError(f"Invalid position: {position}")
    return f"{chr(ord('a') + col)}{row + 1}"


def parse_coordinate_move(move_text):
    text = move_text.strip()
    if not text:
        raise ValueError("Move cannot be empty")

    normalized = text.lower()
    match = re.match(r"^(?P<from>[a-h][1-8])(?P<to>[a-h][1-8])(?P<promotion>=?[qrbn])?$", normalized)
    if not match:
        raise ValueError("Invalid move format. Use source and destination, for example: e2e4")

    groups = match.groupdict()
    promotion = groups["promotion"]
    promotion_piece = promotion.replace("=", "") if promotion else None
    return {
        "from_square": groups["from"],
        "to_square": groups["to"],
        "promotion_piece": promotion_piece,
        "normalized": f"{groups['from']}{groups['to']}{promotion_piece or ''}",
    }


def parse_algebraic_move(move_text):
    text = move_text.strip()
    if not text:
        raise ValueError("Move cannot be empty")

    normalized = re.sub(r"[+#?!]+$", "", text)
    castle_token = normalized.replace("0", "O").replace("o", "O")
    if castle_token in {"O-O", "O-O-O"}:
        side = "kingside" if castle_token == "O-O" else "queenside"
        return {
            "kind": "castle",
            "side": side,
            "normalized": castle_token,
        }

    match = re.match(
        r"^(?P<piece>[KQRBNkqrbn])?(?P<from_file>[a-h])?(?P<from_rank>[1-8])?(?P<capture>x)?(?P<to>[a-h][1-8])(?P<promotion>=?[QRBNqrbn])?$",
        normalized,
    )
    if not match:
        raise ValueError("Invalid algebraic move format")

    groups = match.groupdict()
    piece_letter = (groups["piece"] or "").upper()
    piece_type = {
        "": "pawn",
        "N": "knight",
        "B": "bishop",
        "R": "rook",
        "Q": "queen",
        "K": "king",
    }[piece_letter]

    if piece_letter and (groups["from_file"] or groups["from_rank"]):
        raise ValueError("Piece disambiguation is not supported; use source-destination notation")

    promotion = groups["promotion"]
    promotion_piece = promotion.replace("=", "").lower() if promotion else None
    if promotion_piece is not None and piece_type != "pawn":
        raise ValueError("Only pawns can promote")

    return {
        "kind": "piece_move",
        "piece_type": piece_type,
        "from_file": groups["from_file"],
        "from_rank": int(groups["from_rank"]) if groups["from_rank"] else None,
        "is_capture": bool(groups["capture"]),
        "to_square": groups["to"],
        "promotion_piece": promotion_piece,
        "normalized": (
            f"{piece_letter}{groups['from_file'] or ''}{groups['from_rank'] or ''}"
            f"{'x' if groups['capture'] else ''}{groups['to']}"
            f"{f'={promotion_piece.upper()}' if promotion_piece else ''}"
        ),
    }


def _piece_letter_for_algebraic(piece):
    if isinstance(piece, Knight):
        return "N"
    if isinstance(piece, Bishop):
        return "B"
    if isinstance(piece, Rook):
        return "R"
    if isinstance(piece, Queen):
        return "Q"
    if isinstance(piece, King):
        return "K"
    return ""


def _resolve_coordinate_move_details(board, color, move_text):
    parsed_move = parse_coordinate_move(move_text)
    from_position = square_to_position(parsed_move["from_square"])
    to_position = square_to_position(parsed_move["to_square"])

    piece = board.get_piece_at(from_position)
    if piece is None:
        raise ValueError(f"No piece at {parsed_move['from_square']}")
    if piece.color != color:
        raise ValueError(f"Piece at {parsed_move['from_square']} belongs to {piece.color}")

    promotion_choice = _resolve_promotion_choice(piece, to_position, parsed_move["promotion_piece"])
    if not board.is_legal_move(color, from_position, to_position, promotion_piece=promotion_choice):
        raise ValueError("Illegal move for that piece")

    return from_position, to_position, promotion_choice, parsed_move["normalized"]


def _resolve_algebraic_move_details(board, color, move_text):
    parsed_move = parse_algebraic_move(move_text)

    if parsed_move["kind"] == "castle":
        home_row = 0 if color == "white" else 7
        from_position = (4, home_row)
        to_position = (6, home_row) if parsed_move["side"] == "kingside" else (2, home_row)

        piece = board.get_piece_at(from_position)
        if not isinstance(piece, King) or piece.color != color:
            raise ValueError("Castling is not legal in this position")
        if not board.is_legal_move(color, from_position, to_position):
            raise ValueError("Castling is not legal in this position")
        return from_position, to_position, None, parsed_move["normalized"]

    to_position = square_to_position(parsed_move["to_square"])
    candidate_pieces = []
    for piece in board.pieces:
        if piece.color != color:
            continue
        if not _piece_matches_type(piece, parsed_move["piece_type"]):
            continue
        if parsed_move["from_file"] is not None and piece.position[0] != ord(parsed_move["from_file"]) - ord("a"):
            continue
        if parsed_move["from_rank"] is not None and piece.position[1] != int(parsed_move["from_rank"]) - 1:
            continue
        if board.is_legal_move(color, piece.position, to_position):
            candidate_pieces.append(piece)

    if not candidate_pieces:
        raise ValueError("No legal piece can make that algebraic move")
    if len(candidate_pieces) > 1:
        raise ValueError("Ambiguous algebraic move; use source-destination notation")

    piece = candidate_pieces[0]
    target_piece = board.get_piece_at(to_position)
    is_capture = (target_piece is not None and target_piece.color != color) or _is_en_passant_capture_move(board, piece, to_position)
    if parsed_move["is_capture"] and not is_capture:
        raise ValueError("Move marks capture, but no capture is available")
    if not parsed_move["is_capture"] and is_capture:
        raise ValueError("Captures must include 'x' in algebraic notation")

    promotion_choice = _resolve_promotion_choice(piece, to_position, parsed_move["promotion_piece"])
    if not board.is_legal_move(color, piece.position, to_position, promotion_piece=promotion_choice):
        raise ValueError("No legal piece can make that algebraic move")

    return piece.position, to_position, promotion_choice, parsed_move["normalized"]


def move_text_to_algebraic(board, color, move_text):
    try:
        from_position, to_position, promotion_choice, _ = _resolve_coordinate_move_details(board, color, move_text)
    except ValueError as coordinate_error:
        if "Invalid move format" not in str(coordinate_error):
            raise
        from_position, to_position, promotion_choice, _ = _resolve_algebraic_move_details(board, color, move_text)

    piece = board.get_piece_at(from_position)
    if piece is None or piece.color != color:
        raise ValueError("Cannot render algebraic notation for missing piece")

    from_col, from_row = from_position
    to_col, to_row = to_position

    if isinstance(piece, King) and abs(to_col - from_col) == 2:
        return "O-O" if to_col > from_col else "O-O-O"

    target_piece = board.get_piece_at(to_position)
    is_capture = (target_piece is not None and target_piece.color != color) or _is_en_passant_capture_move(board, piece, to_position)
    destination = position_to_square(to_position)

    if isinstance(piece, Pawn):
        prefix = f"{chr(ord('a') + from_col)}x" if is_capture else ""
        promotion_suffix = ""
        if to_row in (0, 7):
            promotion_suffix = f"={(promotion_choice or 'q').upper()}"
        return f"{prefix}{destination}{promotion_suffix}"

    piece_letter = _piece_letter_for_algebraic(piece)
    capture_marker = "x" if is_capture else ""
    return f"{piece_letter}{capture_marker}{destination}"


def get_ai_profiles():
    profiles = [RANDOM_AI_PROFILE]
    for difficulty in AI_DIFFICULTIES:
        for personality in AI_PERSONALITIES:
            profiles.append(
                {
                    "id": f"d{difficulty['plies']}_{personality['id']}",
                    "name": f"{difficulty['name']} {personality['name']}",
                    "plies": difficulty["plies"],
                    "personality_name": personality["name"],
                    "piece_values": personality["piece_values"],
                }
            )
    profiles.extend(SPECIAL_AI_PROFILES)
    return profiles


def _status_to_pgn_result(status):
    if status.get("winner") == "white":
        return "1-0"
    if status.get("winner") == "black":
        return "0-1"
    if status.get("state") == "draw":
        return "1/2-1/2"
    return "*"


def _started_at_to_pgn_date(started_at):
    try:
        parsed = datetime.fromisoformat(started_at)
        return parsed.strftime("%Y.%m.%d")
    except ValueError:
        return "????.??.??"


def _build_pgn_header_lines(started_at, result="*"):
    return [
        "[Event \"OpenCode Chess CLI\"]",
        "[Site \"Local\"]",
        f"[Date \"{_started_at_to_pgn_date(started_at)}\"]",
        "[Round \"-\"]",
        "[White \"White\"]",
        "[Black \"Black\"]",
        f"[Result \"{result}\"]",
        "[Variant \"We Eat Kings\"]",
    ]


def _move_to_pgn_fragment(move_number, color, move_text):
    if color == "white":
        return f"{(move_number + 1) // 2}. {move_text} "
    if move_number % 2 == 1:
        return f"{(move_number + 1) // 2}... {move_text} "
    return f"{move_text} "


def start_savefile(savefile_path):
    has_existing_content = os.path.exists(savefile_path) and os.path.getsize(savefile_path) > 0
    with open(savefile_path, "a", encoding="utf-8") as savefile:
        if has_existing_content:
            savefile.write("\n")
        started_at = datetime.now().isoformat(timespec="seconds")
        for header_line in _build_pgn_header_lines(started_at, result="*"):
            savefile.write(f"{header_line}\n")
        savefile.write("\n")


def record_move(savefile_path, move_number, color, move_text):
    with open(savefile_path, "a", encoding="utf-8") as savefile:
        savefile.write(_move_to_pgn_fragment(move_number, color, move_text))


def finalize_savefile(savefile_path, status):
    result = _status_to_pgn_result(status)

    with open(savefile_path, "r", encoding="utf-8") as savefile:
        content = savefile.read()

    last_result_tag_index = content.rfind("[Result \"*\"]")
    if last_result_tag_index >= 0:
        content = (
            content[:last_result_tag_index]
            + f"[Result \"{result}\"]"
            + content[last_result_tag_index + len("[Result \"*\"]"):]
        )
        with open(savefile_path, "w", encoding="utf-8") as savefile:
            savefile.write(content)

    with open(savefile_path, "a", encoding="utf-8") as savefile:
        savefile.write(f"{result}\n\n")


def _parse_legacy_savefile_games(save_text):
    games = []
    current_game = None

    for raw_line in save_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        header_match = re.match(r"^=== Game started (?P<started_at>.+) ===$", line)
        if header_match:
            if current_game is not None:
                games.append(current_game)
            current_game = {
                "started_at": header_match.group("started_at"),
                "moves": [],
            }
            continue

        move_match = re.match(r"^(?P<move_number>\d+)\.\s+(?P<color>white|black)\s+(?P<move_text>\S+)$", line)
        if move_match and current_game is not None:
            current_game["moves"].append(
                {
                    "move_number": int(move_match.group("move_number")),
                    "color": move_match.group("color"),
                    "move_text": move_match.group("move_text"),
                }
            )

    if current_game is not None:
        games.append(current_game)

    return games


def convert_legacy_save_text_to_pgn(save_text):
    games = _parse_legacy_savefile_games(save_text)
    if not games:
        raise ValueError("No legacy save games found")

    pgn_chunks = []
    for game in games:
        header_lines = _build_pgn_header_lines(game["started_at"], result="*")
        board = Board()
        move_fragments = []
        for move in game["moves"]:
            color = move["color"]
            move_text = move["move_text"]
            algebraic_move = move_text_to_algebraic(board, color, move_text)
            apply_user_move(board, color, move_text)
            move_fragments.append(_move_to_pgn_fragment(move["move_number"], color, algebraic_move))

        movetext = "".join(move_fragments).strip()
        if movetext:
            movetext = f"{movetext} *"
        else:
            movetext = "*"

        pgn_chunks.append("\n".join(header_lines) + "\n\n" + movetext)

    return "\n\n".join(pgn_chunks) + "\n"


def convert_legacy_savefile_to_pgn(input_path, output_path=None):
    with open(input_path, "r", encoding="utf-8") as input_file:
        save_text = input_file.read()

    pgn_text = convert_legacy_save_text_to_pgn(save_text)
    resolved_output_path = output_path
    if resolved_output_path is None:
        root, _ = os.path.splitext(input_path)
        resolved_output_path = f"{root}.pgn"

    with open(resolved_output_path, "w", encoding="utf-8") as output_file:
        output_file.write(pgn_text)

    return resolved_output_path


class Piece:
    def __init__(self, color, position):
        self.color = color
        self.position = position
        self.moved = False

    def get_legal_moves(self, board):
        raise NotImplementedError("Subclasses must implement get_legal_moves")

    def is_valid_position(self, position):
        col, row = position
        return 0 <= col < 8 and 0 <= row < 8

    def can_occupy(self, board, position):
        target_piece = board.get_piece_at(position)
        return target_piece is None or target_piece.color != self.color

    def is_path_obstructed(self, board, to_position):
        from_col, from_row = self.position
        to_col, to_row = to_position

        col_delta = to_col - from_col
        row_delta = to_row - from_row

        step_col = 0 if col_delta == 0 else col_delta // abs(col_delta)
        step_row = 0 if row_delta == 0 else row_delta // abs(row_delta)

        if step_col == 0 and step_row == 0:
            return False

        current_col = from_col + step_col
        current_row = from_row + step_row

        while (current_col, current_row) != (to_col, to_row):
            if board.get_piece_at((current_col, current_row)) is not None:
                return True
            current_col += step_col
            current_row += step_row

        return False

    def __repr__(self):
        return f"{self.__class__.__name__}({self.color}, {self.position})"

class Knight(Piece):
    def __init__(self, color, position):
        super().__init__(color, position)
        self.symbol = 'N' if color == 'white' else 'n'
    
    def get_legal_moves(self, board):
        col, row = self.position
        moves = []
        
        # All possible knight move offsets
        knight_moves = [
            (2, 1), (2, -1), (-2, 1), (-2, -1),
            (1, 2), (1, -2), (-1, 2), (-1, -2)
        ]
        
        for col_offset, row_offset in knight_moves:
            new_col = col + col_offset
            new_row = row + row_offset

            if self.is_valid_position((new_col, new_row)) and self.can_occupy(board, (new_col, new_row)):
                moves.append((new_col, new_row))
        
        return moves

class Board:
    def __init__(self):
        self.board = [[None for _ in range(8)] for _ in range(8)]
        self.pieces = []
        self.en_passant_target = None
        self.en_passant_capture_position = None
        self.halfmove_clock = 0
        self.position_counts = {}
        self.setup_starting_position()
    
    def setup_starting_position(self):
        # Clear board
        self.board = [[None for _ in range(8)] for _ in range(8)]
        self.pieces = []
        self.en_passant_target = None
        self.en_passant_capture_position = None
        self.halfmove_clock = 0
        self.position_counts = {}
        
        # White pieces
        self.add_piece('white', 'rook', (0, 0))
        self.add_piece('white', 'knight', (1, 0))
        self.add_piece('white', 'bishop', (2, 0))
        self.add_piece('white', 'queen', (3, 0))
        self.add_piece('white', 'king', (4, 0))
        self.add_piece('white', 'bishop', (5, 0))
        self.add_piece('white', 'knight', (6, 0))
        self.add_piece('white', 'rook', (7, 0))
        
        for col in range(8):
            self.add_piece('white', 'pawn', (col, 1))
        
        # Black pieces
        self.add_piece('black', 'rook', (0, 7))
        self.add_piece('black', 'knight', (1, 7))
        self.add_piece('black', 'bishop', (2, 7))
        self.add_piece('black', 'queen', (3, 7))
        self.add_piece('black', 'king', (4, 7))
        self.add_piece('black', 'bishop', (5, 7))
        self.add_piece('black', 'knight', (6, 7))
        self.add_piece('black', 'rook', (7, 7))
        
        for col in range(8):
            self.add_piece('black', 'pawn', (col, 6))

        self.record_position('white')
    
    def add_piece(self, color, piece_type, position):
        piece_classes = {
            'pawn': Pawn,
            'knight': Knight,
            'bishop': Bishop,
            'rook': Rook,
            'queen': Queen,
            'king': King
        }
        
        piece_class = piece_classes.get(piece_type)
        if piece_class:
            piece = piece_class(color, position)
            self.pieces.append(piece)
            self.board[position[1]][position[0]] = piece

    def create_promoted_piece(self, color, position, promotion_piece):
        piece_classes = {
            'q': Queen,
            'r': Rook,
            'b': Bishop,
            'n': Knight,
        }
        piece_class = piece_classes.get((promotion_piece or 'q').lower())
        if piece_class is None:
            raise ValueError(f"Invalid promotion piece: {promotion_piece}")

        promoted_piece = piece_class(color, position)
        promoted_piece.moved = True
        return promoted_piece
    
    def get_piece_at(self, position):
        col, row = position
        if 0 <= col < 8 and 0 <= row < 8:
            return self.board[row][col]
        return None

    def is_valid_position(self, position):
        col, row = position
        return 0 <= col < 8 and 0 <= row < 8

    def get_opponent_color(self, color):
        return 'black' if color == 'white' else 'white'

    def clone(self):
        return copy.deepcopy(self)

    def get_castling_rights(self):
        rights = []

        white_king = self.get_piece_at((4, 0))
        if isinstance(white_king, King) and white_king.color == 'white' and not white_king.moved:
            white_kingside_rook = self.get_piece_at((7, 0))
            white_queenside_rook = self.get_piece_at((0, 0))
            if isinstance(white_kingside_rook, Rook) and white_kingside_rook.color == 'white' and not white_kingside_rook.moved:
                rights.append('K')
            if isinstance(white_queenside_rook, Rook) and white_queenside_rook.color == 'white' and not white_queenside_rook.moved:
                rights.append('Q')

        black_king = self.get_piece_at((4, 7))
        if isinstance(black_king, King) and black_king.color == 'black' and not black_king.moved:
            black_kingside_rook = self.get_piece_at((7, 7))
            black_queenside_rook = self.get_piece_at((0, 7))
            if isinstance(black_kingside_rook, Rook) and black_kingside_rook.color == 'black' and not black_kingside_rook.moved:
                rights.append('k')
            if isinstance(black_queenside_rook, Rook) and black_queenside_rook.color == 'black' and not black_queenside_rook.moved:
                rights.append('q')

        return ''.join(rights) if rights else '-'

    def get_en_passant_square_for_signature(self, active_color):
        if self.en_passant_target is None:
            return '-'

        target_col, target_row = self.en_passant_target
        direction = 1 if active_color == 'white' else -1
        source_row = target_row - direction

        for source_col in (target_col - 1, target_col + 1):
            source_position = (source_col, source_row)
            if not self.is_valid_position(source_position):
                continue
            piece = self.get_piece_at(source_position)
            if isinstance(piece, Pawn) and piece.color == active_color:
                if self.en_passant_target in piece.get_legal_moves(self):
                    return position_to_square(self.en_passant_target)

        return '-'

    def get_position_signature(self, active_color):
        pieces_state = tuple(
            sorted((piece.symbol, piece.position[0], piece.position[1]) for piece in self.pieces)
        )
        return (
            pieces_state,
            active_color,
            self.get_castling_rights(),
            self.get_en_passant_square_for_signature(active_color),
        )

    def record_position(self, active_color):
        signature = self.get_position_signature(active_color)
        self.position_counts[signature] = self.position_counts.get(signature, 0) + 1

    def is_threefold_repetition(self, active_color):
        signature = self.get_position_signature(active_color)
        return self.position_counts.get(signature, 0) >= 3

    def is_fifty_move_draw(self):
        return self.halfmove_clock >= 100

    def find_king_position(self, color):
        for piece in self.pieces:
            if isinstance(piece, King) and piece.color == color:
                return piece.position
        return None

    def is_in_check(self, color):
        king_position = self.find_king_position(color)
        if king_position is None:
            return False
        return self.is_square_attacked(king_position, self.get_opponent_color(color))

    def is_legal_move(self, color, from_pos, to_pos, promotion_piece=None):
        piece = self.get_piece_at(from_pos)
        if piece is None or piece.color != color:
            return False
        if to_pos not in piece.get_legal_moves(self):
            return False
        _ = promotion_piece
        return True

    def has_legal_move(self, color):
        for piece in self.pieces:
            if piece.color != color:
                continue
            from_pos = piece.position
            for to_pos in piece.get_legal_moves(self):
                if self.is_legal_move(color, from_pos, to_pos):
                    return True
        return False

    def get_legal_moves_for_color(self, color):
        legal_moves = []
        for piece in self.pieces:
            if piece.color != color:
                continue
            from_pos = piece.position
            for to_pos in piece.get_legal_moves(self):
                if self.is_legal_move(color, from_pos, to_pos):
                    legal_moves.append((from_pos, to_pos))
        return legal_moves

    def _sliding_piece_attacks_square(self, piece, target_position, directions):
        for col_step, row_step in directions:
            current_col = piece.position[0] + col_step
            current_row = piece.position[1] + row_step
            while self.is_valid_position((current_col, current_row)):
                if (current_col, current_row) == target_position:
                    return True
                if self.get_piece_at((current_col, current_row)) is not None:
                    break
                current_col += col_step
                current_row += row_step
        return False

    def piece_attacks_square(self, piece, target_position):
        piece_col, piece_row = piece.position
        target_col, target_row = target_position

        if isinstance(piece, Pawn):
            direction = 1 if piece.color == 'white' else -1
            return (target_col, target_row) in {
                (piece_col - 1, piece_row + direction),
                (piece_col + 1, piece_row + direction),
            }

        if isinstance(piece, Knight):
            return (abs(piece_col - target_col), abs(piece_row - target_row)) in {
                (1, 2),
                (2, 1),
            }

        if isinstance(piece, Bishop):
            return self._sliding_piece_attacks_square(
                piece,
                target_position,
                [(-1, -1), (-1, 1), (1, -1), (1, 1)],
            )

        if isinstance(piece, Rook):
            return self._sliding_piece_attacks_square(
                piece,
                target_position,
                [(-1, 0), (1, 0), (0, -1), (0, 1)],
            )

        if isinstance(piece, Queen):
            return self._sliding_piece_attacks_square(
                piece,
                target_position,
                [
                    (-1, -1),
                    (-1, 1),
                    (1, -1),
                    (1, 1),
                    (-1, 0),
                    (1, 0),
                    (0, -1),
                    (0, 1),
                ],
            )

        if isinstance(piece, King):
            return max(abs(piece_col - target_col), abs(piece_row - target_row)) == 1

        return False

    def is_square_attacked(self, position, by_color):
        for piece in self.pieces:
            if piece.color == by_color and self.piece_attacks_square(piece, position):
                return True
        return False

    def get_castling_moves(self, king):
        if king.moved:
            return []

        home_row = 0 if king.color == 'white' else 7
        if king.position != (4, home_row):
            return []

        castle_rules = [
            {
                'rook_position': (7, home_row),
                'required_empty': [(5, home_row), (6, home_row)],
                'king_destination': (6, home_row),
            },
            {
                'rook_position': (0, home_row),
                'required_empty': [(1, home_row), (2, home_row), (3, home_row)],
                'king_destination': (2, home_row),
            },
        ]

        available_moves = []
        for rule in castle_rules:
            rook = self.get_piece_at(rule['rook_position'])
            if not isinstance(rook, Rook) or rook.color != king.color or rook.moved:
                continue
            if any(self.get_piece_at(position) is not None for position in rule['required_empty']):
                continue
            available_moves.append(rule['king_destination'])

        return available_moves
    
    def remove_piece_at(self, position):
        col, row = position
        piece = self.board[row][col]
        if piece:
            if piece in self.pieces:
                self.pieces.remove(piece)
            self.board[row][col] = None
    
    def move_piece(self, from_pos, to_pos, update_tracking=True, promotion_piece=None):
        piece = self.get_piece_at(from_pos)
        if not piece:
            return False

        from_col, from_row = from_pos
        to_col, to_row = to_pos
        target_piece = self.get_piece_at(to_pos)

        is_en_passant_capture = (
            isinstance(piece, Pawn)
            and target_piece is None
            and from_col != to_col
            and self.en_passant_target == to_pos
            and self.en_passant_capture_position is not None
        )

        is_capture = target_piece is not None or is_en_passant_capture

        if is_en_passant_capture:
            self.remove_piece_at(self.en_passant_capture_position)
        elif target_piece is not None:
            self.remove_piece_at(to_pos)

        self.board[from_pos[1]][from_pos[0]] = None
        self.board[to_pos[1]][to_pos[0]] = piece
        piece.position = to_pos

        is_pawn_move = isinstance(piece, Pawn)
        is_promotion_rank = is_pawn_move and (to_row == 7 or to_row == 0)
        if is_promotion_rank:
            if piece in self.pieces:
                self.pieces.remove(piece)
            promoted_piece = self.create_promoted_piece(piece.color, to_pos, promotion_piece)
            self.pieces.append(promoted_piece)
            self.board[to_pos[1]][to_pos[0]] = promoted_piece
            piece = promoted_piece

        is_castling_move = isinstance(piece, King) and abs(to_col - from_col) == 2
        if is_castling_move:
            if to_col > from_col:
                rook_from = (7, from_row)
                rook_to = (5, from_row)
            else:
                rook_from = (0, from_row)
                rook_to = (3, from_row)
            rook = self.get_piece_at(rook_from)
            if isinstance(rook, Rook):
                self.board[rook_from[1]][rook_from[0]] = None
                self.board[rook_to[1]][rook_to[0]] = rook
                rook.position = rook_to
                rook.moved = True

        piece.moved = True

        self.en_passant_target = None
        self.en_passant_capture_position = None
        if isinstance(piece, Pawn) and abs(to_row - from_row) == 2:
            self.en_passant_target = (from_col, (from_row + to_row) // 2)
            self.en_passant_capture_position = (to_col, to_row)

        if update_tracking:
            if is_pawn_move or is_capture:
                self.halfmove_clock = 0
            else:
                self.halfmove_clock += 1

            next_color = self.get_opponent_color(piece.color)
            self.record_position(next_color)

        return True
    
    def __str__(self):
        board_str = "  a b c d e f g h\n"
        for row_idx in range(7, -1, -1):
            row = self.board[row_idx]
            board_str += f"{row_idx + 1} "
            for piece in row:
                if piece:
                    board_str += f"{piece.symbol} "
                else:
                    board_str += ". "
            board_str += f"{row_idx + 1}\n"
        board_str += "  a b c d e f g h"
        return board_str


def apply_coordinate_move(board, color, move_text):
    from_position, to_position, promotion_choice, normalized_move = _resolve_coordinate_move_details(board, color, move_text)
    board.move_piece(from_position, to_position, promotion_piece=promotion_choice)
    return board.get_piece_at(to_position), to_position, normalized_move


def _piece_matches_type(piece, piece_type):
    return piece.__class__.__name__.lower() == piece_type


def _is_en_passant_capture_move(board, piece, to_position):
    if not isinstance(piece, Pawn):
        return False
    from_col, _ = piece.position
    to_col, _ = to_position
    return (
        board.en_passant_target == to_position
        and board.get_piece_at(to_position) is None
        and from_col != to_col
    )


def _resolve_promotion_choice(piece, to_position, promotion_piece):
    to_row = to_position[1]
    reaches_promotion_rank = isinstance(piece, Pawn) and to_row in (0, 7)
    if reaches_promotion_rank:
        return (promotion_piece or "q").lower()
    if promotion_piece is not None:
        raise ValueError("Promotion piece is only valid for pawn promotion moves")
    return None


def apply_algebraic_move(board, color, move_text):
    from_position, to_position, promotion_choice, normalized_move = _resolve_algebraic_move_details(board, color, move_text)
    board.move_piece(from_position, to_position, promotion_piece=promotion_choice)
    return board.get_piece_at(to_position), to_position, normalized_move


def apply_user_move(board, color, move_text):
    try:
        parse_coordinate_move(move_text)
        return apply_coordinate_move(board, color, move_text)
    except ValueError as coordinate_error:
        if "Invalid move format" not in str(coordinate_error):
            raise

    return apply_algebraic_move(board, color, move_text)


def has_legal_move(board, color):
    return board.has_legal_move(color)


def get_game_status(board, active_color):
    white_king = board.find_king_position("white")
    black_king = board.find_king_position("black")
    if white_king is None and black_king is None:
        return {"state": "draw", "reason": "both_kings_captured", "winner": None}
    if white_king is None:
        return {"state": "king_capture", "reason": "king_captured", "winner": "black"}
    if black_king is None:
        return {"state": "king_capture", "reason": "king_captured", "winner": "white"}

    if board.is_threefold_repetition(active_color):
        return {"state": "draw", "reason": "threefold_repetition", "winner": None}

    if board.is_fifty_move_draw():
        return {"state": "draw", "reason": "fifty_move_rule", "winner": None}

    if not board.has_legal_move(active_color):
        return {"state": "draw", "reason": "stalemate", "winner": None}

    return {"state": "in_progress", "reason": None, "winner": None}


def _pawn_rank_for_value(pawn):
    _, row = pawn.position
    if pawn.color == "white":
        return row + 1
    return 8 - row


def _is_backward_pawn(board, pawn):
    if not isinstance(pawn, Pawn):
        return False

    col, row = pawn.position
    direction = 1 if pawn.color == "white" else -1
    forward_square = (col, row + direction)
    if not board.is_valid_position(forward_square):
        return False

    has_adjacent_support = False
    for adjacent_col in (col - 1, col + 1):
        if not (0 <= adjacent_col < 8):
            continue
        for scan_row in range(8):
            adjacent_piece = board.get_piece_at((adjacent_col, scan_row))
            if not isinstance(adjacent_piece, Pawn) or adjacent_piece.color != pawn.color:
                continue
            if pawn.color == "white" and scan_row >= row:
                has_adjacent_support = True
            if pawn.color == "black" and scan_row <= row:
                has_adjacent_support = True
            if has_adjacent_support:
                break
        if has_adjacent_support:
            break

    if has_adjacent_support:
        return False

    opponent_color = board.get_opponent_color(pawn.color)
    for piece in board.pieces:
        if isinstance(piece, Pawn) and piece.color == opponent_color and board.piece_attacks_square(piece, forward_square):
            return True

    return False


def _square_weight_for_piece(piece, square, position_multipliers):
    if not position_multipliers:
        return 1.0

    col, row = square
    center_squares = {(3, 3), (4, 3), (3, 4), (4, 4)}
    center_cross_squares = {(2, 3), (2, 4), (3, 2), (4, 2), (5, 3), (5, 4), (3, 5), (4, 5)}
    center_diagonal_squares = {(2, 2), (5, 2), (2, 5), (5, 5)}
    corner_squares = {(0, 0), (7, 0), (0, 7), (7, 7)}
    corner_touch_squares = {(1, 0), (0, 1), (6, 0), (7, 1), (0, 6), (1, 7), (6, 7), (7, 6)}

    if (col, row) in corner_squares:
        if isinstance(piece, Rook):
            return position_multipliers.get("corner_rook", position_multipliers.get("corner", 1.0))
        return position_multipliers.get("corner", 1.0)

    if (col, row) in corner_touch_squares:
        if isinstance(piece, Rook):
            return position_multipliers.get("corner_touch_rook", position_multipliers.get("corner_touch", 1.0))
        return position_multipliers.get("corner_touch", 1.0)

    if (col, row) in center_squares:
        return position_multipliers.get("center", 1.0)

    if (col, row) in center_cross_squares:
        return position_multipliers.get("center_cross", 1.0)

    if (col, row) in center_diagonal_squares:
        return position_multipliers.get("center_diagonal", 1.0)

    return 1.0


def _position_multiplier(piece, position_multipliers):
    return _square_weight_for_piece(piece, piece.position, position_multipliers)


def _control_score(board, perspective_color, position_multipliers):
    total = 0.0
    for piece in board.pieces:
        controlled = 0.0
        for square in piece.get_legal_moves(board):
            controlled += _square_weight_for_piece(piece, square, position_multipliers)
        if piece.color == perspective_color:
            total += controlled
        else:
            total -= controlled
    return total


def _has_opposite_color_bishops(board):
    white_bishops = [piece for piece in board.pieces if isinstance(piece, Bishop) and piece.color == "white"]
    black_bishops = [piece for piece in board.pieces if isinstance(piece, Bishop) and piece.color == "black"]
    if len(white_bishops) != 1 or len(black_bishops) != 1:
        return False

    white_square_color = (white_bishops[0].position[0] + white_bishops[0].position[1]) % 2
    black_square_color = (black_bishops[0].position[0] + black_bishops[0].position[1]) % 2
    return white_square_color != black_square_color


def _evaluate_piece_scores(
    piece,
    board,
    piece_values,
    pawn_rank_values=None,
    backward_pawn_value=None,
    position_multipliers=None,
):
    piece_type = PIECE_TYPE_BY_CLASS[piece.__class__.__name__]
    material_score = piece_values[piece_type]
    piece_score = material_score

    if isinstance(piece, Pawn):
        if pawn_rank_values:
            pawn_rank = _pawn_rank_for_value(piece)
            piece_score = max(piece_score, pawn_rank_values.get(pawn_rank, piece_score))
        if backward_pawn_value is not None and _is_backward_pawn(board, piece):
            piece_score = min(piece_score, backward_pawn_value)

    piece_score *= _position_multiplier(piece, position_multipliers)
    heuristic_score = piece_score - material_score
    return material_score, heuristic_score

def evaluate_position_scores(
    board,
    perspective_color,
    piece_values,
    pawn_rank_values=None,
    backward_pawn_value=None,
    position_multipliers=None,
    control_weight=0.0,
    opposite_bishop_draw_factor=None,
):
    material_score = 0.0
    heuristic_score = 0.0
    for piece in board.pieces:
        piece_material, piece_heuristic = _evaluate_piece_scores(
            piece,
            board,
            piece_values,
            pawn_rank_values=pawn_rank_values,
            backward_pawn_value=backward_pawn_value,
            position_multipliers=position_multipliers,
        )
        if piece.color == perspective_color:
            material_score += piece_material
            heuristic_score += piece_heuristic
        else:
            material_score -= piece_material
            heuristic_score -= piece_heuristic

    if control_weight:
        heuristic_score += control_weight * _control_score(
            board,
            perspective_color,
            position_multipliers,
        )

    if opposite_bishop_draw_factor is not None and _has_opposite_color_bishops(board):
        heuristic_score *= opposite_bishop_draw_factor

    return material_score, heuristic_score


def evaluate_material(
    board,
    perspective_color,
    piece_values,
    pawn_rank_values=None,
    backward_pawn_value=None,
    position_multipliers=None,
    control_weight=0.0,
    opposite_bishop_draw_factor=None,
):
    material_score, heuristic_score = evaluate_position_scores(
        board,
        perspective_color,
        piece_values,
        pawn_rank_values=pawn_rank_values,
        backward_pawn_value=backward_pawn_value,
        position_multipliers=position_multipliers,
        control_weight=control_weight,
        opposite_bishop_draw_factor=opposite_bishop_draw_factor,
    )
    return material_score + heuristic_score


def minimax_score(
    board,
    active_color,
    perspective_color,
    remaining_plies,
    piece_values,
    pawn_rank_values=None,
    backward_pawn_value=None,
    position_multipliers=None,
    control_weight=0.0,
    opposite_bishop_draw_factor=None,
):
    status = get_game_status(board, active_color)
    if status["winner"] is not None:
        return (100000.0, 0.0) if status["winner"] == perspective_color else (-100000.0, 0.0)
    if status["state"] == "draw":
        return 0.0, 0.0
    if remaining_plies <= 0:
        return evaluate_position_scores(
            board,
            perspective_color,
            piece_values,
            pawn_rank_values=pawn_rank_values,
            backward_pawn_value=backward_pawn_value,
            position_multipliers=position_multipliers,
            control_weight=control_weight,
            opposite_bishop_draw_factor=opposite_bishop_draw_factor,
        )

    legal_moves = board.get_legal_moves_for_color(active_color)
    next_color = board.get_opponent_color(active_color)

    if active_color == perspective_color:
        best_score = (float("-inf"), float("-inf"))
        for from_pos, to_pos in legal_moves:
            simulation = board.clone()
            simulation.move_piece(from_pos, to_pos)
            score = minimax_score(
                simulation,
                next_color,
                perspective_color,
                remaining_plies - 1,
                piece_values,
                pawn_rank_values=pawn_rank_values,
                backward_pawn_value=backward_pawn_value,
                position_multipliers=position_multipliers,
                control_weight=control_weight,
                opposite_bishop_draw_factor=opposite_bishop_draw_factor,
            )
            if score > best_score:
                best_score = score
        return best_score

    best_score = (float("inf"), float("inf"))
    for from_pos, to_pos in legal_moves:
        simulation = board.clone()
        simulation.move_piece(from_pos, to_pos)
        score = minimax_score(
            simulation,
            next_color,
            perspective_color,
            remaining_plies - 1,
            piece_values,
            pawn_rank_values=pawn_rank_values,
            backward_pawn_value=backward_pawn_value,
            position_multipliers=position_multipliers,
            control_weight=control_weight,
            opposite_bishop_draw_factor=opposite_bishop_draw_factor,
        )
        if score < best_score:
            best_score = score
    return best_score


def choose_random_legal_move(board, color, rng=None):
    legal_moves = board.get_legal_moves_for_color(color)
    if not legal_moves:
        return None

    random_source = rng if rng is not None else random
    return random_source.choice(legal_moves)


def choose_minimax_legal_move(
    board,
    color,
    plies,
    piece_values,
    rng=None,
    pawn_rank_values=None,
    backward_pawn_value=None,
    position_multipliers=None,
    control_weight=0.0,
    opposite_bishop_draw_factor=None,
):
    legal_moves = board.get_legal_moves_for_color(color)
    if not legal_moves:
        return None

    if plies <= 0:
        return choose_random_legal_move(board, color, rng=rng)

    next_color = board.get_opponent_color(color)
    best_score = (float("-inf"), float("-inf"))
    best_moves = []
    for from_pos, to_pos in legal_moves:
        simulation = board.clone()
        simulation.move_piece(from_pos, to_pos)
        score = minimax_score(
            simulation,
            next_color,
            color,
            plies - 1,
            piece_values,
            pawn_rank_values=pawn_rank_values,
            backward_pawn_value=backward_pawn_value,
            position_multipliers=position_multipliers,
            control_weight=control_weight,
            opposite_bishop_draw_factor=opposite_bishop_draw_factor,
        )
        if score > best_score:
            best_score = score
            best_moves = [(from_pos, to_pos)]
        elif score == best_score:
            best_moves.append((from_pos, to_pos))

    random_source = rng if rng is not None else random
    return random_source.choice(best_moves)


def choose_ai_move(board, color, ai_profile, rng=None):
    if ai_profile["plies"] <= 0:
        return choose_random_legal_move(board, color, rng=rng)
    return choose_minimax_legal_move(
        board,
        color,
        ai_profile["plies"],
        ai_profile["piece_values"],
        rng=rng,
        pawn_rank_values=ai_profile.get("pawn_rank_values"),
        backward_pawn_value=ai_profile.get("backward_pawn_value"),
        position_multipliers=ai_profile.get("position_multipliers"),
        control_weight=ai_profile.get("control_weight", 0.0),
        opposite_bishop_draw_factor=ai_profile.get("opposite_bishop_draw_factor"),
    )


def apply_ai_move(board, color, ai_profile, rng=None):
    chosen_move = choose_ai_move(board, color, ai_profile, rng=rng)
    if chosen_move is None:
        raise ValueError(f"No legal moves available for {color}")

    from_pos, to_pos = chosen_move
    board.move_piece(from_pos, to_pos)
    piece = board.get_piece_at(to_pos)
    move_text = f"{position_to_square(from_pos)}{position_to_square(to_pos)}"
    return piece, from_pos, to_pos, move_text


def apply_random_ai_move(board, color, rng=None):
    return apply_ai_move(board, color, RANDOM_AI_PROFILE, rng=rng)


def choose_menu_option(options, prompt_text, default_index=0, allow_quit=False):
    for index, option in enumerate(options, start=1):
        print(f"{index}. {option}")
    raw_value = input(prompt_text).strip()
    if allow_quit and raw_value.lower() in {"q", "quit", "exit"}:
        return None
    if not raw_value:
        return default_index
    if raw_value.isdigit():
        selected = int(raw_value) - 1
        if 0 <= selected < len(options):
            return selected
    if allow_quit:
        print("Invalid choice, using default (or type q to quit).")
    else:
        print("Invalid choice, using default.")
    return default_index


def choose_ai_profile(profiles, prompt_text, default_index=0):
    profile_options = [
        f"{profile['name']} ({profile['plies']} plies, {profile['personality_name']})"
        for profile in profiles
    ]
    profile_index = choose_menu_option(profile_options, prompt_text, default_index=default_index)
    return profiles[profile_index]


def configure_game_menu(rng=None):
    random_source = rng if rng is not None else random

    print("=== Chess Menu ===")
    mode_index = choose_menu_option(
        ["Self play", "Play versus AI", "AI versus AI", "Quit"],
        "Select mode [1] (or q): ",
        default_index=0,
        allow_quit=True,
    )
    if mode_index is None or mode_index == 3:
        return {"mode": "quit"}

    if mode_index == 0:
        return {"mode": "self_play", "ai_profile": None, "ai_color": None}

    profiles = get_ai_profiles()
    if mode_index == 1:
        selected_profile = choose_ai_profile(profiles, "Select AI [1]: ", default_index=0)

        color_input = input("Choose your color ([R]andom/[W]hite/[B]lack, default random): ").strip().lower()
        if color_input == "w":
            human_color = "white"
        elif color_input == "b":
            human_color = "black"
        else:
            human_color = random_source.choice(["white", "black"])

        ai_color = "black" if human_color == "white" else "white"
        print(f"You are {human_color}. AI is {selected_profile['name']} ({ai_color}).")
        return {
            "mode": "vs_ai",
            "ai_profile": selected_profile,
            "ai_color": ai_color,
        }

    white_profile = choose_ai_profile(profiles, "Select white AI [1]: ", default_index=0)
    black_profile = choose_ai_profile(profiles, "Select black AI [1]: ", default_index=0)
    print(f"AI match: {white_profile['name']} (white) vs {black_profile['name']} (black)")
    return {
        "mode": "ai_vs_ai",
        "white_ai_profile": white_profile,
        "black_ai_profile": black_profile,
    }


def _match_result_message(status):
    if status["winner"] is not None:
        return f"King captured. {status['winner'].capitalize()} wins."
    if status["state"] == "draw":
        return f"Draw by {status['reason'].replace('_', ' ')}."
    return "Match ended."

def play_match(game_setup, savefile_path=DEFAULT_SAVEFILE, ai_vs_ai_show_board=True):
    board = Board()
    current_turn = "white"
    move_number = 1
    start_savefile(savefile_path)

    fast_mode = game_setup["mode"] == "ai_vs_ai"
    if not fast_mode:
        print("Play chess with coordinate or algebraic notation (e2e4, e7e8q, e4, Nf3, O-O, e8=Q).")
        print("Type 'ai' to let a random AI move for the current side.")
        print("Type 'quit' to exit to menu.")
        print(f"Saving moves to {savefile_path}")

    while True:
        if not fast_mode:
            print()
            print(board)
        status = get_game_status(board, current_turn)
        if status["winner"] is not None or status["state"] == "draw":
            if fast_mode:
                print(_match_result_message(status))
            else:
                print(_match_result_message(status))
            finalize_savefile(savefile_path, status)
            return status

        if game_setup["mode"] == "ai_vs_ai":
            ai_profile = game_setup[f"{current_turn}_ai_profile"]
            board_before_move = board.clone()
            piece, _, to_position, normalized_move = apply_ai_move(board, current_turn, ai_profile)
            algebraic_move = move_text_to_algebraic(board_before_move, current_turn, normalized_move)
            record_move(savefile_path, move_number, current_turn, algebraic_move)
            if ai_vs_ai_show_board:
                print(f"{move_number}. {current_turn} {normalized_move} ({piece.__class__.__name__} -> {position_to_square(to_position)})")
                print(board)
                print()
            move_number += 1
            current_turn = board.get_opponent_color(current_turn)
            continue

        if game_setup["mode"] == "vs_ai" and current_turn == game_setup["ai_color"]:
            board_before_move = board.clone()
            piece, _, to_position, normalized_move = apply_ai_move(board, current_turn, game_setup["ai_profile"])
            algebraic_move = move_text_to_algebraic(board_before_move, current_turn, normalized_move)
            record_move(savefile_path, move_number, current_turn, algebraic_move)
            move_number += 1
            print(f"AI moved {piece.__class__.__name__} to {position_to_square(to_position)}")
            current_turn = board.get_opponent_color(current_turn)
            continue

        move_text = input(f"{current_turn}> ").strip()
        if move_text.lower() in {"quit", "exit"}:
            print("Returning to menu")
            status = {"state": "aborted", "reason": "quit", "winner": None}
            finalize_savefile(savefile_path, status)
            return status

        if move_text.lower() == "ai":
            try:
                board_before_move = board.clone()
                piece, _, to_position, normalized_move = apply_random_ai_move(board, current_turn)
                algebraic_move = move_text_to_algebraic(board_before_move, current_turn, normalized_move)
                record_move(savefile_path, move_number, current_turn, algebraic_move)
                move_number += 1
                print(f"AI moved {piece.__class__.__name__} to {position_to_square(to_position)}")
                current_turn = board.get_opponent_color(current_turn)
            except ValueError as error:
                print(f"Illegal move: {error}")
            continue

        try:
            board_before_move = board.clone()
            piece, to_position, normalized_move = apply_user_move(board, current_turn, move_text)
            algebraic_move = move_text_to_algebraic(board_before_move, current_turn, normalized_move)
            record_move(savefile_path, move_number, current_turn, algebraic_move)
            move_number += 1
            print(f"Moved {piece.__class__.__name__} to {position_to_square(to_position)}")
            current_turn = board.get_opponent_color(current_turn)
        except ValueError as error:
            print(f"Illegal move: {error}")


def play_cli(savefile_path=DEFAULT_SAVEFILE):
    while True:
        game_setup = configure_game_menu()
        if game_setup["mode"] == "quit":
            print("Goodbye")
            return

        play_match(game_setup, savefile_path=savefile_path)
        print("Returning to main menu.")

class Pawn(Piece):
    def __init__(self, color, position):
        super().__init__(color, position)
        self.symbol = 'P' if color == 'white' else 'p'
    
    def get_legal_moves(self, board):
        col, row = self.position
        moves = []
        
        direction = 1 if self.color == 'white' else -1
        
        # One step forward
        new_row = row + direction
        if 0 <= new_row < 8 and board.get_piece_at((col, new_row)) is None:
            moves.append((col, new_row))
        
        # Two steps forward from starting position
        if (self.color == 'white' and row == 1) or (self.color == 'black' and row == 6):
            two_steps = row + 2 * direction
            if 0 <= two_steps < 8 and board.get_piece_at((col, row + direction)) is None and board.get_piece_at((col, two_steps)) is None:
                moves.append((col, two_steps))

        # Captures
        for col_offset in (-1, 1):
            capture_col = col + col_offset
            capture_row = row + direction
            if self.is_valid_position((capture_col, capture_row)):
                target_piece = board.get_piece_at((capture_col, capture_row))
                if target_piece is not None and target_piece.color != self.color:
                    moves.append((capture_col, capture_row))
                elif board.en_passant_target == (capture_col, capture_row):
                    capture_position = board.en_passant_capture_position
                    captured_piece = board.get_piece_at(capture_position) if capture_position else None
                    if (
                        isinstance(captured_piece, Pawn)
                        and captured_piece.color != self.color
                        and capture_position == (capture_col, row)
                    ):
                        moves.append((capture_col, capture_row))
        
        return moves

class Bishop(Piece):
    def __init__(self, color, position):
        super().__init__(color, position)
        self.symbol = 'B' if color == 'white' else 'b'
    
    def get_legal_moves(self, board):
        col, row = self.position
        moves = []
        
        # Diagonal directions
        directions = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
        
        for dcol, drow in directions:
            new_col, new_row = col + dcol, row + drow
            while self.is_valid_position((new_col, new_row)):
                if self.is_path_obstructed(board, (new_col, new_row)):
                    break
                if self.can_occupy(board, (new_col, new_row)):
                    moves.append((new_col, new_row))
                if board.get_piece_at((new_col, new_row)) is not None:
                    break
                new_col += dcol
                new_row += drow
        
        return moves

class Rook(Piece):
    def __init__(self, color, position):
        super().__init__(color, position)
        self.symbol = 'R' if color == 'white' else 'r'
    
    def get_legal_moves(self, board):
        col, row = self.position
        moves = []
        
        # Straight directions
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        
        for dcol, drow in directions:
            new_col, new_row = col + dcol, row + drow
            while self.is_valid_position((new_col, new_row)):
                if self.is_path_obstructed(board, (new_col, new_row)):
                    break
                if self.can_occupy(board, (new_col, new_row)):
                    moves.append((new_col, new_row))
                if board.get_piece_at((new_col, new_row)) is not None:
                    break
                new_col += dcol
                new_row += drow
        
        return moves

class Queen(Piece):
    def __init__(self, color, position):
        super().__init__(color, position)
        self.symbol = 'Q' if color == 'white' else 'q'
    
    def get_legal_moves(self, board):
        col, row = self.position
        moves = []
        
        # All directions (rook + bishop)
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1),
                      (-1, -1), (-1, 1), (1, -1), (1, 1)]
        
        for dcol, drow in directions:
            new_col, new_row = col + dcol, row + drow
            while self.is_valid_position((new_col, new_row)):
                if self.is_path_obstructed(board, (new_col, new_row)):
                    break
                if self.can_occupy(board, (new_col, new_row)):
                    moves.append((new_col, new_row))
                if board.get_piece_at((new_col, new_row)) is not None:
                    break
                new_col += dcol
                new_row += drow
        
        return moves

class King(Piece):
    def __init__(self, color, position):
        super().__init__(color, position)
        self.symbol = 'K' if color == 'white' else 'k'
    
    def get_legal_moves(self, board):
        col, row = self.position
        moves = []
        
        # All adjacent squares
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1),
                      (-1, -1), (-1, 1), (1, -1), (1, 1)]
        
        for dcol, drow in directions:
            new_col, new_row = col + dcol, row + drow
            if (
                self.is_valid_position((new_col, new_row))
                and self.can_occupy(board, (new_col, new_row))
            ):
                moves.append((new_col, new_row))

        moves.extend(board.get_castling_moves(self))

        return moves

if __name__ == "__main__":
    play_cli()
