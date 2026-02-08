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
            
            if board.is_valid_position((new_col, new_row)):
                moves.append((new_col, new_row))
        
        return moves

class Board:
    def __init__(self):
        self.board = [[None for _ in range(8)] for _ in range(8)]
        self.pieces = []
        self.setup_starting_position()
    
    def setup_starting_position(self):
        # Clear board
        self.board = [[None for _ in range(8)] for _ in range(8)]
        self.pieces = []
        
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
    
    def remove_piece_at(self, position):
        col, row = position
        piece = self.board[row][col]
        if piece:
            self.pieces.remove(piece)
            self.board[row][col] = None
    
    def move_piece(self, from_pos, to_pos):
        piece = self.get_piece_at(from_pos)
        if piece:
            self.remove_piece_at(from_pos)
            self.board[to_pos[1]][to_pos[0]] = piece
            piece.position = to_pos
            piece.moved = True
    
    def __str__(self):
        board_str = "  a b c d e f g h\n"
        for row_idx, row in enumerate(self.board):
            board_str += f"{8 - row_idx} "
            for piece in row:
                if piece:
                    board_str += f"{piece.symbol} "
                else:
                    board_str += ". "
            board_str += f"{8 - row_idx}\n"
        board_str += "  a b c d e f g h"
        return board_str

class Pawn(Piece):
    def __init__(self, color, position):
        super().__init__(color, position)
        self.symbol = 'P' if color == 'white' else 'p'
    
    def get_legal_moves(self, board):
        col, row = self.position
        moves = []
        
        direction = -1 if self.color == 'white' else 1
        
        # One step forward
        new_row = row + direction
        if 0 <= new_row < 8:
            moves.append((col, new_row))
        
        # Two steps forward from starting position
        if (self.color == 'white' and row == 1) or (self.color == 'black' and row == 6):
            two_steps = row + 2 * direction
            if 0 <= two_steps < 8:
                moves.append((col, two_steps))
        
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
                moves.append((new_col, new_row))
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
                moves.append((new_col, new_row))
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
                moves.append((new_col, new_row))
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
            if self.is_valid_position((new_col, new_row)):
                moves.append((new_col, new_row))
        
        return moves

# Test the implementation
if __name__ == "__main__":
    board = Board()
    print("Starting Position:")
    print(board)
    
    # Test knight moves from starting position
    white_knight = board.get_piece_at((1, 0))
    if white_knight:
        print(f"\nWhite knight at {white_knight.position} can move to:")
        print(white_knight.get_legal_moves(board))
    
    black_knight = board.get_piece_at((1, 7))
    if black_knight:
        print(f"Black knight at {black_knight.position} can move to:")
        print(black_knight.get_legal_moves(board))