import re
from datetime import datetime
import os


DEFAULT_SAVEFILE = "chess_save.txt"


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
        self.setup_starting_position()
    
    def setup_starting_position(self):
        # Clear board
        self.board = [[None for _ in range(8)] for _ in range(8)]
        self.pieces = []
        self.en_passant_target = None
        self.en_passant_capture_position = None
        
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
    
    def move_piece(self, from_pos, to_pos):
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
    if to_position not in piece.get_legal_moves(board):
        raise ValueError("Illegal move for that piece")

    board.move_piece(from_position, to_position)
    return piece, to_position, parsed_move["normalized"]


def has_legal_move(board, color):
    for piece in board.pieces:
        if piece.color == color and piece.get_legal_moves(board):
            return True
    return False


def play_cli(savefile_path=DEFAULT_SAVEFILE):
    board = Board()
    current_turn = "white"
    move_number = 1
    start_savefile(savefile_path)

    print("Play chess with source and destination notation (example: e2e4).")
    print("Type 'quit' to exit.")
    print(f"Saving moves to {savefile_path}")

    while True:
        print()
        print(board)
        if not has_legal_move(board, current_turn):
            print(f"{current_turn.capitalize()} has no legal moves. Game over.")
            return

        move_text = input(f"{current_turn}> ").strip()
        if move_text.lower() in {"quit", "exit"}:
            print("Goodbye")
            return

        try:
            piece, to_position, normalized_move = apply_coordinate_move(board, current_turn, move_text)
            record_move(savefile_path, move_number, current_turn, normalized_move)
            move_number += 1
            print(f"Moved {piece.__class__.__name__} to {position_to_square(to_position)}")
            current_turn = "black" if current_turn == "white" else "white"
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
