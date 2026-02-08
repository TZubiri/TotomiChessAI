from chess import Board, Pawn, Rook


def _empty_board():
    board = Board()
    board.board = [[None for _ in range(8)] for _ in range(8)]
    board.pieces = []
    return board


def _place(board, piece):
    col, row = piece.position
    board.board[row][col] = piece
    board.pieces.append(piece)
    return piece


def _piece_at(board, position):
    piece = board.get_piece_at(position)
    assert piece is not None
    return piece


def test_starting_knight_moves():
    board = Board()

    assert set(_piece_at(board, (1, 0)).get_legal_moves(board)) == {(0, 2), (2, 2)}
    assert set(_piece_at(board, (6, 0)).get_legal_moves(board)) == {(5, 2), (7, 2)}
    assert set(_piece_at(board, (1, 7)).get_legal_moves(board)) == {(0, 5), (2, 5)}
    assert set(_piece_at(board, (6, 7)).get_legal_moves(board)) == {(5, 5), (7, 5)}


def test_starting_bishop_moves_blocked():
    board = Board()

    assert _piece_at(board, (2, 0)).get_legal_moves(board) == []
    assert _piece_at(board, (5, 0)).get_legal_moves(board) == []
    assert _piece_at(board, (2, 7)).get_legal_moves(board) == []
    assert _piece_at(board, (5, 7)).get_legal_moves(board) == []


def test_rook_path_obstruction_and_capture():
    board = _empty_board()
    rook = _place(board, Rook("white", (0, 0)))
    _place(board, Pawn("white", (0, 3)))
    _place(board, Pawn("black", (3, 0)))

    assert set(rook.get_legal_moves(board)) == {(0, 1), (0, 2), (1, 0), (2, 0), (3, 0)}


def test_pawn_forward_and_diagonal_captures():
    board = _empty_board()
    pawn = _place(board, Pawn("white", (4, 6)))
    _place(board, Pawn("black", (3, 5)))
    _place(board, Pawn("black", (5, 5)))

    assert set(pawn.get_legal_moves(board)) == {(4, 5), (3, 5), (5, 5)}


def run_all_tests():
    tests = [
        test_starting_knight_moves,
        test_starting_bishop_moves_blocked,
        test_rook_path_obstruction_and_capture,
        test_pawn_forward_and_diagonal_captures,
    ]

    for test in tests:
        test()

    print(f"{len(tests)} tests passed")


if __name__ == "__main__":
    run_all_tests()
