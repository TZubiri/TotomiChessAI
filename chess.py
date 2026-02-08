import re
from datetime import datetime
import os
import copy
import random


DEFAULT_SAVEFILE = "chess_save.txt"
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
    match = re.match(r"^(?P<from>[a-h][1-8])(?P<to>[a-h][1-8])$", normalized)
    if not match:
        raise ValueError("Invalid move format. Use source and destination, for example: e2e4")

    groups = match.groupdict()
    return {
        "from_square": groups["from"],
        "to_square": groups["to"],
        "normalized": f"{groups['from']}{groups['to']}",
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
        r"^(?P<piece>[KQRBNkqrbn])?(?P<from_file>[a-h])?(?P<from_rank>[1-8])?(?P<capture>x)?(?P<to>[a-h][1-8])$",
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

    return {
        "kind": "piece_move",
        "piece_type": piece_type,
        "from_file": groups["from_file"],
        "from_rank": int(groups["from_rank"]) if groups["from_rank"] else None,
        "is_capture": bool(groups["capture"]),
        "to_square": groups["to"],
        "normalized": (
            f"{piece_letter}{groups['from_file'] or ''}{groups['from_rank'] or ''}"
            f"{'x' if groups['capture'] else ''}{groups['to']}"
        ),
    }


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
    return profiles


def start_savefile(savefile_path):
    has_existing_content = os.path.exists(savefile_path) and os.path.getsize(savefile_path) > 0
    with open(savefile_path, "a", encoding="utf-8") as savefile:
        if has_existing_content:
            savefile.write("\n")
        started_at = datetime.now().isoformat(timespec="seconds")
        savefile.write(f"=== Game started {started_at} ===\n")


def record_move(savefile_path, move_number, color, move_text):
    with open(savefile_path, "a", encoding="utf-8") as savefile:
        savefile.write(f"{move_number}. {color} {move_text}\n")


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

    def is_legal_move(self, color, from_pos, to_pos):
        piece = self.get_piece_at(from_pos)
        if piece is None or piece.color != color:
            return False
        if to_pos not in piece.get_legal_moves(self):
            return False

        simulation = self.clone()
        simulation.move_piece(from_pos, to_pos, update_tracking=False)
        return not simulation.is_in_check(color)

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

        opponent_color = self.get_opponent_color(king.color)
        if self.is_square_attacked((4, home_row), opponent_color):
            return []

        castle_rules = [
            {
                'rook_position': (7, home_row),
                'required_empty': [(5, home_row), (6, home_row)],
                'safe_for_king': [(5, home_row), (6, home_row)],
                'king_destination': (6, home_row),
            },
            {
                'rook_position': (0, home_row),
                'required_empty': [(1, home_row), (2, home_row), (3, home_row)],
                'safe_for_king': [(3, home_row), (2, home_row)],
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
            if any(self.is_square_attacked(position, opponent_color) for position in rule['safe_for_king']):
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
    
    def move_piece(self, from_pos, to_pos, update_tracking=True):
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
            if isinstance(piece, Pawn) or is_capture:
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
    parsed_move = parse_coordinate_move(move_text)
    from_position = square_to_position(parsed_move["from_square"])
    to_position = square_to_position(parsed_move["to_square"])

    piece = board.get_piece_at(from_position)
    if piece is None:
        raise ValueError(f"No piece at {parsed_move['from_square']}")
    if piece.color != color:
        raise ValueError(f"Piece at {parsed_move['from_square']} belongs to {piece.color}")
    if not board.is_legal_move(color, from_position, to_position):
        raise ValueError("Illegal move for that piece")

    board.move_piece(from_position, to_position)
    return piece, to_position, parsed_move["normalized"]


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


def apply_algebraic_move(board, color, move_text):
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

        board.move_piece(from_position, to_position)
        return piece, to_position, parsed_move["normalized"]

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

    board.move_piece(piece.position, to_position)
    return piece, to_position, parsed_move["normalized"]


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
    if board.is_threefold_repetition(active_color):
        return {"state": "draw", "reason": "threefold_repetition", "winner": None}

    if board.is_fifty_move_draw():
        return {"state": "draw", "reason": "fifty_move_rule", "winner": None}

    if not board.has_legal_move(active_color):
        if board.is_in_check(active_color):
            return {
                "state": "checkmate",
                "reason": "checkmate",
                "winner": board.get_opponent_color(active_color),
            }
        return {"state": "draw", "reason": "stalemate", "winner": None}

    return {"state": "in_progress", "reason": None, "winner": None}


def evaluate_material(board, perspective_color, piece_values):
    score = 0.0
    for piece in board.pieces:
        piece_type = PIECE_TYPE_BY_CLASS[piece.__class__.__name__]
        piece_score = piece_values[piece_type]
        if piece.color == perspective_color:
            score += piece_score
        else:
            score -= piece_score
    return score


def minimax_score(board, active_color, perspective_color, remaining_plies, piece_values):
    status = get_game_status(board, active_color)
    if status["state"] == "checkmate":
        return 100000.0 if status["winner"] == perspective_color else -100000.0
    if status["state"] == "draw":
        return 0.0
    if remaining_plies <= 0:
        return evaluate_material(board, perspective_color, piece_values)

    legal_moves = board.get_legal_moves_for_color(active_color)
    next_color = board.get_opponent_color(active_color)

    if active_color == perspective_color:
        best_score = float("-inf")
        for from_pos, to_pos in legal_moves:
            simulation = board.clone()
            simulation.move_piece(from_pos, to_pos)
            score = minimax_score(simulation, next_color, perspective_color, remaining_plies - 1, piece_values)
            if score > best_score:
                best_score = score
        return best_score

    best_score = float("inf")
    for from_pos, to_pos in legal_moves:
        simulation = board.clone()
        simulation.move_piece(from_pos, to_pos)
        score = minimax_score(simulation, next_color, perspective_color, remaining_plies - 1, piece_values)
        if score < best_score:
            best_score = score
    return best_score


def choose_random_legal_move(board, color, rng=None):
    legal_moves = board.get_legal_moves_for_color(color)
    if not legal_moves:
        return None

    random_source = rng if rng is not None else random
    return random_source.choice(legal_moves)


def choose_minimax_legal_move(board, color, plies, piece_values, rng=None):
    legal_moves = board.get_legal_moves_for_color(color)
    if not legal_moves:
        return None

    if plies <= 0:
        return choose_random_legal_move(board, color, rng=rng)

    next_color = board.get_opponent_color(color)
    best_score = float("-inf")
    best_moves = []
    for from_pos, to_pos in legal_moves:
        simulation = board.clone()
        simulation.move_piece(from_pos, to_pos)
        score = minimax_score(simulation, next_color, color, plies - 1, piece_values)
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
    )


def apply_ai_move(board, color, ai_profile, rng=None):
    chosen_move = choose_ai_move(board, color, ai_profile, rng=rng)
    if chosen_move is None:
        raise ValueError(f"No legal moves available for {color}")

    from_pos, to_pos = chosen_move
    piece = board.get_piece_at(from_pos)
    board.move_piece(from_pos, to_pos)
    move_text = f"{position_to_square(from_pos)}{position_to_square(to_pos)}"
    return piece, from_pos, to_pos, move_text


def apply_random_ai_move(board, color, rng=None):
    return apply_ai_move(board, color, RANDOM_AI_PROFILE, rng=rng)


def choose_menu_option(options, prompt_text, default_index=0):
    for index, option in enumerate(options, start=1):
        print(f"{index}. {option}")
    raw_value = input(prompt_text).strip()
    if not raw_value:
        return default_index
    if raw_value.isdigit():
        selected = int(raw_value) - 1
        if 0 <= selected < len(options):
            return selected
    print("Invalid choice, using default.")
    return default_index


def configure_game_menu(rng=None):
    random_source = rng if rng is not None else random

    print("=== Chess Menu ===")
    mode_index = choose_menu_option(
        ["Self play", "Play versus AI"],
        "Select mode [1]: ",
        default_index=0,
    )
    if mode_index == 0:
        return {"mode": "self_play", "ai_profile": None, "ai_color": None}

    profiles = get_ai_profiles()
    profile_options = [
        f"{profile['name']} ({profile['plies']} plies, {profile['personality_name']})"
        for profile in profiles
    ]
    profile_index = choose_menu_option(profile_options, "Select AI [1]: ", default_index=0)
    selected_profile = profiles[profile_index]

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


def play_cli(savefile_path=DEFAULT_SAVEFILE):
    board = Board()
    current_turn = "white"
    move_number = 1
    game_setup = configure_game_menu()
    start_savefile(savefile_path)

    print("Play chess with coordinate or algebraic notation (e2e4, e4, Nf3, O-O).")
    print("Type 'ai' to let a random AI move for the current side.")
    print("Type 'quit' to exit.")
    print(f"Saving moves to {savefile_path}")

    while True:
        print()
        print(board)
        status = get_game_status(board, current_turn)
        if status["state"] == "checkmate":
            print(f"Checkmate. {status['winner'].capitalize()} wins.")
            return
        if status["state"] == "draw":
            print(f"Draw by {status['reason'].replace('_', ' ')}.")
            return

        if game_setup["mode"] == "vs_ai" and current_turn == game_setup["ai_color"]:
            piece, _, to_position, normalized_move = apply_ai_move(board, current_turn, game_setup["ai_profile"])
            record_move(savefile_path, move_number, current_turn, normalized_move)
            move_number += 1
            print(f"AI moved {piece.__class__.__name__} to {position_to_square(to_position)}")
            current_turn = board.get_opponent_color(current_turn)
            continue

        move_text = input(f"{current_turn}> ").strip()
        if move_text.lower() in {"quit", "exit"}:
            print("Goodbye")
            return

        if move_text.lower() == "ai":
            try:
                piece, _, to_position, normalized_move = apply_random_ai_move(board, current_turn)
                record_move(savefile_path, move_number, current_turn, normalized_move)
                move_number += 1
                print(f"AI moved {piece.__class__.__name__} to {position_to_square(to_position)}")
                current_turn = board.get_opponent_color(current_turn)
            except ValueError as error:
                print(f"Illegal move: {error}")
            continue

        try:
            piece, to_position, normalized_move = apply_user_move(board, current_turn, move_text)
            record_move(savefile_path, move_number, current_turn, normalized_move)
            move_number += 1
            print(f"Moved {piece.__class__.__name__} to {position_to_square(to_position)}")
            current_turn = board.get_opponent_color(current_turn)
        except ValueError as error:
            print(f"Illegal move: {error}")

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
                and not board.is_square_attacked((new_col, new_row), board.get_opponent_color(self.color))
            ):
                moves.append((new_col, new_row))

        moves.extend(board.get_castling_moves(self))

        return moves

if __name__ == "__main__":
    play_cli()
