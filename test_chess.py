import tempfile

from chess import (
    Board,
    Pawn,
    Rook,
    apply_algebraic_move,
    parse_algebraic_move,
    record_move,
    start_savefile,
)


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


def _move_counts_by_position(board):
    return {piece.position: len(piece.get_legal_moves(board)) for piece in board.pieces}


def _assert_position_move_counts(case_name, board, expected_move_counts):
    actual_move_counts = _move_counts_by_position(board)
    assert set(actual_move_counts) == set(expected_move_counts), (
        f"{case_name}: expected positions {sorted(expected_move_counts)} "
        f"but got {sorted(actual_move_counts)}"
    )

    for position, expected_count in expected_move_counts.items():
        actual_count = actual_move_counts[position]
        assert actual_count == expected_count, (
            f"{case_name}: piece at {position} expected {expected_count} moves, "
            f"got {actual_count}"
        )


def _starting_position_expected_move_counts():
    expected = {}

    for col in range(8):
        expected[(col, 1)] = 2
        expected[(col, 6)] = 2

    for col in (1, 6):
        expected[(col, 0)] = 2
        expected[(col, 7)] = 2

    for col in (0, 2, 3, 4, 5, 7):
        expected[(col, 0)] = 0
        expected[(col, 7)] = 0

    return expected


POSITION_MOVE_COUNT_CASES = [
    {
        "name": "starting_position",
        "setup": Board,
        "expected_move_counts": _starting_position_expected_move_counts(),
    }
]


def test_position_move_counts():
    for case in POSITION_MOVE_COUNT_CASES:
        board = case["setup"]()
        _assert_position_move_counts(case["name"], board, case["expected_move_counts"])

def test_rook_path_obstruction_and_capture():
    board = _empty_board()
    rook = _place(board, Rook("white", (0, 0)))
    _place(board, Pawn("white", (0, 3)))
    _place(board, Pawn("black", (3, 0)))

    assert set(rook.get_legal_moves(board)) == {(0, 1), (0, 2), (1, 0), (2, 0), (3, 0)}


def test_pawn_forward_and_diagonal_captures():
    board = _empty_board()
    pawn = _place(board, Pawn("white", (4, 1)))
    _place(board, Pawn("black", (3, 2)))
    _place(board, Pawn("black", (5, 2)))

    assert set(pawn.get_legal_moves(board)) == {(4, 2), (4, 3), (3, 2), (5, 2)}


def test_parse_algebraic_move():
    assert parse_algebraic_move("e4") == {
        "piece_type": "pawn",
        "from_file": None,
        "from_rank": None,
        "is_capture": False,
        "to_square": "e4",
    }
    assert parse_algebraic_move("Nf3") == {
        "piece_type": "knight",
        "from_file": None,
        "from_rank": None,
        "is_capture": False,
        "to_square": "f3",
    }
    assert parse_algebraic_move("exd5") == {
        "piece_type": "pawn",
        "from_file": "e",
        "from_rank": None,
        "is_capture": True,
        "to_square": "d5",
    }


def test_apply_algebraic_move_from_starting_position():
    board = Board()

    piece, to_position = apply_algebraic_move(board, "white", "e4")
    assert piece.__class__.__name__ == "Pawn"
    assert to_position == (4, 3)
    assert board.get_piece_at((4, 1)) is None
    assert board.get_piece_at((4, 3)) == piece


def test_apply_algebraic_move_rejects_illegal_move():
    board = Board()

    try:
        apply_algebraic_move(board, "white", "e5")
        assert False, "Expected illegal move error"
    except ValueError as error:
        assert str(error) == "No legal piece can make that move"


def test_apply_algebraic_move_requires_capture_marker():
    board = _empty_board()
    _place(board, Pawn("white", (4, 3)))
    _place(board, Pawn("black", (3, 4)))

    try:
        apply_algebraic_move(board, "white", "d5")
        assert False, "Expected capture marker error"
    except ValueError as error:
        assert str(error) == "Capture must include 'x' in algebraic notation"

    piece, to_position = apply_algebraic_move(board, "white", "exd5")
    assert piece.__class__.__name__ == "Pawn"
    assert to_position == (3, 4)


def test_savefile_records_moves():
    with tempfile.TemporaryDirectory() as temp_dir:
        savefile_path = f"{temp_dir}/moves.log"
        start_savefile(savefile_path)
        record_move(savefile_path, 1, "white", "e4")
        record_move(savefile_path, 2, "black", "e5")

        with open(savefile_path, "r", encoding="utf-8") as savefile:
            lines = [line.rstrip("\n") for line in savefile]

    assert len(lines) == 3
    assert lines[0].startswith("=== Game started ")
    assert lines[0].endswith(" ===")
    assert lines[1] == "1. white e4"
    assert lines[2] == "2. black e5"


def run_all_tests():
    tests = [
        test_position_move_counts,
        test_rook_path_obstruction_and_capture,
        test_pawn_forward_and_diagonal_captures,
        test_parse_algebraic_move,
        test_apply_algebraic_move_from_starting_position,
        test_apply_algebraic_move_rejects_illegal_move,
        test_apply_algebraic_move_requires_capture_marker,
        test_savefile_records_moves,
    ]

    for test in tests:
        test()

    print(f"{len(tests)} tests passed")


if __name__ == "__main__":
    run_all_tests()
