import tempfile
import random
from pathlib import Path

from chess import (
    Board,
    Bishop,
    King,
    Knight,
    Pawn,
    Queen,
    Rook,
    apply_algebraic_move,
    apply_ai_move,
    apply_coordinate_move,
    apply_random_ai_move,
    apply_user_move,
    choose_ai_move,
    choose_random_legal_move,
    evaluate_material,
    get_ai_profiles,
    get_game_status,
    parse_algebraic_move,
    parse_coordinate_move,
    position_to_square,
    record_move,
    start_savefile,
)
from run_tournament import build_fixtures, run_tournament


def _empty_board():
    board = Board()
    board.board = [[None for _ in range(8)] for _ in range(8)]
    board.pieces = []
    board.en_passant_target = None
    board.en_passant_capture_position = None
    board.halfmove_clock = 0
    board.position_counts = {}
    return board


def _place(board, piece):
    col, row = piece.position
    board.board[row][col] = piece
    board.pieces.append(piece)
    return piece


def _replay_moves(moves):
    board = Board()
    current_turn = "white"
    for move in moves:
        apply_coordinate_move(board, current_turn, move)
        current_turn = "black" if current_turn == "white" else "white"
    return board, current_turn


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


def test_parse_coordinate_move():
    assert parse_coordinate_move("e2e4") == {
        "from_square": "e2",
        "to_square": "e4",
        "promotion_piece": None,
        "normalized": "e2e4",
    }
    assert parse_coordinate_move("E7E5") == {
        "from_square": "e7",
        "to_square": "e5",
        "promotion_piece": None,
        "normalized": "e7e5",
    }
    assert parse_coordinate_move("e7e8q") == {
        "from_square": "e7",
        "to_square": "e8",
        "promotion_piece": "q",
        "normalized": "e7e8q",
    }


def test_parse_algebraic_move():
    assert parse_algebraic_move("e4") == {
        "kind": "piece_move",
        "piece_type": "pawn",
        "from_file": None,
        "from_rank": None,
        "is_capture": False,
        "to_square": "e4",
        "promotion_piece": None,
        "normalized": "e4",
    }
    assert parse_algebraic_move("Nf3") == {
        "kind": "piece_move",
        "piece_type": "knight",
        "from_file": None,
        "from_rank": None,
        "is_capture": False,
        "to_square": "f3",
        "promotion_piece": None,
        "normalized": "Nf3",
    }
    assert parse_algebraic_move("O-O") == {
        "kind": "castle",
        "side": "kingside",
        "normalized": "O-O",
    }
    assert parse_algebraic_move("e8=Q") == {
        "kind": "piece_move",
        "piece_type": "pawn",
        "from_file": None,
        "from_rank": None,
        "is_capture": False,
        "to_square": "e8",
        "promotion_piece": "q",
        "normalized": "e8=Q",
    }


def test_apply_coordinate_move_from_starting_position():
    board = Board()

    piece, to_position, normalized_move = apply_coordinate_move(board, "white", "e2e4")
    assert piece.__class__.__name__ == "Pawn"
    assert to_position == (4, 3)
    assert normalized_move == "e2e4"
    assert board.get_piece_at((4, 1)) is None
    assert board.get_piece_at((4, 3)) == piece


def test_apply_algebraic_move_from_starting_position():
    board = Board()

    piece, to_position, normalized_move = apply_algebraic_move(board, "white", "e4")
    assert piece.__class__.__name__ == "Pawn"
    assert to_position == (4, 3)
    assert normalized_move == "e4"


def test_apply_user_move_supports_both_notations():
    board = Board()

    piece, to_position, normalized_move = apply_user_move(board, "white", "e2e4")
    assert piece.__class__.__name__ == "Pawn"
    assert to_position == (4, 3)
    assert normalized_move == "e2e4"

    piece, to_position, normalized_move = apply_user_move(board, "black", "e5")
    assert piece.__class__.__name__ == "Pawn"
    assert to_position == (4, 4)
    assert normalized_move == "e5"


def test_apply_coordinate_move_promotes_pawn():
    board = _empty_board()
    _place(board, Pawn("white", (4, 6)))

    piece, to_position, normalized_move = apply_coordinate_move(board, "white", "e7e8q")
    assert isinstance(piece, Queen)
    assert to_position == (4, 7)
    assert normalized_move == "e7e8q"
    assert isinstance(board.get_piece_at((4, 7)), Queen)


def test_apply_algebraic_move_promotes_pawn():
    board = _empty_board()
    _place(board, Pawn("white", (4, 6)))

    piece, to_position, normalized_move = apply_algebraic_move(board, "white", "e8=N")
    assert isinstance(piece, Knight)
    assert to_position == (4, 7)
    assert normalized_move == "e8=N"
    assert isinstance(board.get_piece_at((4, 7)), Knight)


def test_apply_coordinate_move_rejects_illegal_move():
    board = Board()

    try:
        apply_coordinate_move(board, "white", "e2e5")
        assert False, "Expected illegal move error"
    except ValueError as error:
        assert str(error) == "Illegal move for that piece"


def test_apply_coordinate_move_rejects_wrong_turn_piece():
    board = Board()

    try:
        apply_coordinate_move(board, "white", "e7e5")
        assert False, "Expected wrong-color error"
    except ValueError as error:
        assert str(error) == "Piece at e7 belongs to black"


def test_apply_coordinate_move_allows_capture():
    board = _empty_board()
    _place(board, Pawn("white", (4, 3)))
    _place(board, Pawn("black", (3, 4)))

    piece, to_position, normalized_move = apply_coordinate_move(board, "white", "e4d5")
    assert piece.__class__.__name__ == "Pawn"
    assert to_position == (3, 4)
    assert normalized_move == "e4d5"


def test_last_game_scenario_attempted_moves():
    opening_moves = ["e2e4", "e7e5", "d2d4", "f7f5"]

    board, current_turn = _replay_moves(opening_moves)
    assert current_turn == "white"
    piece, to_position, normalized_move = apply_coordinate_move(board, "white", "d4d5")
    assert piece.__class__.__name__ == "Pawn"
    assert to_position == (3, 4)
    assert normalized_move == "d4d5"

    board, current_turn = _replay_moves(opening_moves)
    assert current_turn == "white"
    try:
        apply_coordinate_move(board, "white", "e4xf5")
        assert False, "Expected coordinate-format error"
    except ValueError as error:
        assert str(error) == "Invalid move format. Use source and destination, for example: e2e4"

    piece, to_position, normalized_move = apply_coordinate_move(board, "white", "e4f5")
    assert piece.__class__.__name__ == "Pawn"
    assert to_position == (5, 4)
    assert normalized_move == "e4f5"


def test_en_passant_capture_is_available_immediately():
    board, current_turn = _replay_moves(["e2e4", "a7a6", "e4e5", "f7f5"])
    assert current_turn == "white"

    piece, to_position, normalized_move = apply_coordinate_move(board, "white", "e5f6")
    assert piece.__class__.__name__ == "Pawn"
    assert to_position == (5, 5)
    assert normalized_move == "e5f6"
    assert board.get_piece_at((5, 5)) == piece
    assert board.get_piece_at((5, 4)) is None


def test_en_passant_expires_after_one_turn():
    board, current_turn = _replay_moves(["e2e4", "a7a6", "e4e5", "f7f5", "a2a3", "a6a5"])
    assert current_turn == "white"

    try:
        apply_coordinate_move(board, "white", "e5f6")
        assert False, "Expected en passant window to expire"
    except ValueError as error:
        assert str(error) == "Illegal move for that piece"


def test_castling_kingside_and_queenside():
    kingside_board = _empty_board()
    _place(kingside_board, King("white", (4, 0)))
    _place(kingside_board, Rook("white", (7, 0)))

    piece, to_position, normalized_move = apply_coordinate_move(kingside_board, "white", "e1g1")
    assert piece.__class__.__name__ == "King"
    assert to_position == (6, 0)
    assert normalized_move == "e1g1"
    rook = kingside_board.get_piece_at((5, 0))
    assert rook is not None and rook.__class__.__name__ == "Rook"

    queenside_board = _empty_board()
    _place(queenside_board, King("white", (4, 0)))
    _place(queenside_board, Rook("white", (0, 0)))

    piece, to_position, normalized_move = apply_coordinate_move(queenside_board, "white", "e1c1")
    assert piece.__class__.__name__ == "King"
    assert to_position == (2, 0)
    assert normalized_move == "e1c1"
    rook = queenside_board.get_piece_at((3, 0))
    assert rook is not None and rook.__class__.__name__ == "Rook"


def test_castling_allowed_even_when_path_square_is_attacked():
    board = _empty_board()
    _place(board, King("white", (4, 0)))
    _place(board, Rook("white", (7, 0)))
    _place(board, Rook("black", (5, 7)))

    piece, to_position, normalized_move = apply_coordinate_move(board, "white", "e1g1")
    assert piece.__class__.__name__ == "King"
    assert to_position == (6, 0)
    assert normalized_move == "e1g1"


def test_threefold_repetition_draw_status():
    board, current_turn = _replay_moves(
        [
            "g1f3",
            "g8f6",
            "f3g1",
            "f6g8",
            "g1f3",
            "g8f6",
            "f3g1",
            "f6g8",
        ]
    )
    assert current_turn == "white"

    status = get_game_status(board, current_turn)
    assert status == {"state": "draw", "reason": "threefold_repetition", "winner": None}


def test_fifty_move_rule_draw_status():
    board = Board()
    board.halfmove_clock = 100

    status = get_game_status(board, "white")
    assert status == {"state": "draw", "reason": "fifty_move_rule", "winner": None}


def test_king_capture_ends_game():
    board = _empty_board()
    _place(board, King("white", (0, 0)))
    _place(board, Queen("white", (3, 3)))
    _place(board, King("black", (4, 4)))

    apply_coordinate_move(board, "white", "d4e5")
    status = get_game_status(board, "black")
    assert status == {"state": "king_capture", "reason": "king_captured", "winner": "white"}


def test_choose_random_legal_move_returns_legal_move():
    board = Board()
    legal_moves = set(board.get_legal_moves_for_color("white"))

    move = choose_random_legal_move(board, "white", rng=random.Random(7))
    assert move is not None
    assert move in legal_moves


def test_apply_random_ai_move_executes_selected_legal_move():
    board = Board()
    legal_moves = set(board.get_legal_moves_for_color("white"))

    piece, from_pos, to_pos, move_text = apply_random_ai_move(board, "white", rng=random.Random(11))

    assert (from_pos, to_pos) in legal_moves
    assert board.get_piece_at(from_pos) is None
    assert board.get_piece_at(to_pos) == piece
    assert move_text == f"{position_to_square(from_pos)}{position_to_square(to_pos)}"


def test_apply_random_ai_move_fails_without_legal_moves():
    board = _empty_board()
    _place(board, King("black", (7, 7)))

    assert choose_random_legal_move(board, "white", rng=random.Random(1)) is None
    try:
        apply_random_ai_move(board, "white", rng=random.Random(1))
        assert False, "Expected no-legal-moves error"
    except ValueError as error:
        assert str(error) == "No legal moves available for white"


def test_ai_profiles_and_minimax_selection():
    profiles = get_ai_profiles()
    assert len(profiles) == 12
    assert sum(1 for profile in profiles if profile["plies"] == 0) == 1
    assert any(profile["plies"] == 3 for profile in profiles)
    assert any(profile["id"] == "d2_pawnwise" for profile in profiles)
    assert any(profile["id"] == "d2_pawnwise_control" for profile in profiles)

    board = Board()
    oracle_profile = next(profile for profile in profiles if profile["plies"] == 3 and profile["personality_name"] == "Classic")
    move = choose_ai_move(board, "white", oracle_profile, rng=random.Random(3))
    assert move is not None

    piece, from_pos, to_pos, move_text = apply_ai_move(board, "white", oracle_profile, rng=random.Random(3))
    assert board.get_piece_at(from_pos) is None
    assert board.get_piece_at(to_pos) == piece
    assert move_text == f"{position_to_square(from_pos)}{position_to_square(to_pos)}"


def test_pawnwise_profile_heuristics_affect_evaluation():
    board = _empty_board()
    _place(board, Pawn("white", (4, 4)))
    _place(board, Pawn("black", (3, 6)))

    profiles = get_ai_profiles()
    pawnwise = next(profile for profile in profiles if profile["id"] == "d2_pawnwise")
    classic = next(profile for profile in profiles if profile["id"] == "d2_basic")

    classic_score = evaluate_material(board, "white", classic["piece_values"])
    pawnwise_score = evaluate_material(
        board,
        "white",
        pawnwise["piece_values"],
        pawn_rank_values=pawnwise.get("pawn_rank_values"),
        backward_pawn_value=pawnwise.get("backward_pawn_value"),
        position_multipliers=pawnwise.get("position_multipliers"),
    )

    assert pawnwise_score != classic_score


def test_pawnwise_control_profile_drawish_opposite_bishops():
    board = _empty_board()
    _place(board, Bishop("white", (2, 0)))
    _place(board, Bishop("black", (2, 7)))
    _place(board, Pawn("white", (4, 4)))

    profiles = get_ai_profiles()
    profile = next(profile for profile in profiles if profile["id"] == "d2_pawnwise_control")

    baseline = evaluate_material(
        board,
        "white",
        profile["piece_values"],
        pawn_rank_values=profile.get("pawn_rank_values"),
        backward_pawn_value=profile.get("backward_pawn_value"),
        position_multipliers=profile.get("position_multipliers"),
        control_weight=profile.get("control_weight", 0.0),
        opposite_bishop_draw_factor=None,
    )
    drawish = evaluate_material(
        board,
        "white",
        profile["piece_values"],
        pawn_rank_values=profile.get("pawn_rank_values"),
        backward_pawn_value=profile.get("backward_pawn_value"),
        position_multipliers=profile.get("position_multipliers"),
        control_weight=profile.get("control_weight", 0.0),
        opposite_bishop_draw_factor=profile.get("opposite_bishop_draw_factor"),
    )

    assert baseline > 0
    assert abs(drawish - (baseline * 0.5)) < 1e-9


def test_tournament_fixture_counts():
    profiles = get_ai_profiles()
    assert len(build_fixtures(profiles, "ordered")) == 132
    assert len(build_fixtures(profiles, "single")) == 66


def test_tournament_writes_results_and_scoreboard():
    with tempfile.TemporaryDirectory() as temp_dir:
        manifest, rows = run_tournament(
            output_dir=temp_dir,
            pairing_mode="ordered",
            seed=7,
            max_halfmoves=8,
            max_matches=1,
            report_progress=False,
        )

        output_root = Path(temp_dir)
        assert manifest["match_count"] == 1
        assert len(rows) == 12
        assert (output_root / "scoreboard.csv").exists()
        assert (output_root / "scoreboard.json").exists()
        assert (output_root / "manifest.json").exists()
        assert len(list((output_root / "matches").iterdir())) == 1


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
        test_parse_coordinate_move,
        test_parse_algebraic_move,
        test_apply_coordinate_move_from_starting_position,
        test_apply_algebraic_move_from_starting_position,
        test_apply_user_move_supports_both_notations,
        test_apply_coordinate_move_promotes_pawn,
        test_apply_algebraic_move_promotes_pawn,
        test_apply_coordinate_move_rejects_illegal_move,
        test_apply_coordinate_move_rejects_wrong_turn_piece,
        test_apply_coordinate_move_allows_capture,
        test_last_game_scenario_attempted_moves,
        test_en_passant_capture_is_available_immediately,
        test_en_passant_expires_after_one_turn,
        test_castling_kingside_and_queenside,
        test_castling_allowed_even_when_path_square_is_attacked,
        test_threefold_repetition_draw_status,
        test_fifty_move_rule_draw_status,
        test_king_capture_ends_game,
        test_choose_random_legal_move_returns_legal_move,
        test_apply_random_ai_move_executes_selected_legal_move,
        test_apply_random_ai_move_fails_without_legal_moves,
        test_ai_profiles_and_minimax_selection,
        test_pawnwise_profile_heuristics_affect_evaluation,
        test_pawnwise_control_profile_drawish_opposite_bishops,
        test_tournament_fixture_counts,
        test_tournament_writes_results_and_scoreboard,
        test_savefile_records_moves,
    ]

    for test in tests:
        test()

    print(f"{len(tests)} tests passed")


if __name__ == "__main__":
    run_all_tests()
