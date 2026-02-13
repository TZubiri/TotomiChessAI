import tempfile
import random
import subprocess
from pathlib import Path
import builtins

from chess import (
    _opening_phase_ratio,
    _evaluate_position_scores_c_base,
    _evaluate_position_scores_python_base,
    Board,
    Bishop,
    King,
    Knight,
    Pawn,
    Queen,
    Rook,
    SavefileRecorder,
    apply_algebraic_move,
    apply_ai_move,
    apply_coordinate_move,
    apply_random_ai_move,
    apply_user_move,
    choose_ai_move,
    choose_minimax_legal_move,
    choose_random_legal_move,
    c_evaluator_available,
    c_search_available,
    create_c_search_cache,
    destroy_c_search_cache,
    convert_legacy_save_text_to_pgn,
    configure_game_menu,
    evaluate_material,
    evaluate_position_scores,
    finalize_savefile,
    get_ai_profiles,
    get_game_status,
    move_text_to_algebraic,
    play_match,
    parse_algebraic_move,
    parse_coordinate_move,
    position_to_square,
    record_move,
    set_savefile_recorder,
    start_savefile,
)
from chess_uci import move_to_uci, parse_uci_position
from run_tournament import build_fixtures, rank_rows_with_tiebreakers, run_tournament
from ai_positions import BITMAP_BASE53_LOOKUP
from ai_positions._shared import PAWNWISE_PAWN_BITMAP_ROWS


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


def _with_mocked_input(responses, func, *args, **kwargs):
    original_input = builtins.input
    pending = iter(responses)

    def fake_input(_prompt=""):
        return next(pending)

    builtins.input = fake_input
    try:
        return func(*args, **kwargs)
    finally:
        builtins.input = original_input


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
    assert sum(1 for profile in profiles if profile["plies"] == 0) == 1
    assert any(profile["plies"] == 3 for profile in profiles)
    assert any(profile["plies"] == 4 for profile in profiles)
    assert any(profile["plies"] == 5 for profile in profiles)
    assert any(profile["id"] == "d2_pawnwise" for profile in profiles)
    assert any(profile["id"] == "d1_pawnwise_forcing" for profile in profiles)
    assert any(profile["id"] == "d2_pawnwise_forcing" for profile in profiles)
    assert any(profile["id"] == "d2_pawnwise_control" for profile in profiles)
    assert any(profile["id"] == "d3_pawnwise" for profile in profiles)
    assert any(profile["id"] == "d3_pawnwise_forcing" for profile in profiles)
    assert any(profile["id"] == "d4_pawnwise" for profile in profiles)

    d1_forcing = next(profile for profile in profiles if profile["id"] == "d1_pawnwise_forcing")
    d2_forcing = next(profile for profile in profiles if profile["id"] == "d2_pawnwise_forcing")
    d3_forcing = next(profile for profile in profiles if profile["id"] == "d3_pawnwise_forcing")
    assert d1_forcing["plies"] == 1
    assert d2_forcing["plies"] == 2
    assert d3_forcing["plies"] == 3
    assert d1_forcing.get("captures_extend_plies") is True
    assert d2_forcing.get("captures_extend_plies") is True
    assert d3_forcing.get("captures_extend_plies") is True
    assert d1_forcing.get("captures_extend_limit") == 2
    assert d2_forcing.get("captures_extend_limit") == 2
    assert d3_forcing.get("captures_extend_limit") == 2

    board = Board()
    oracle_profile = next(profile for profile in profiles if profile["plies"] == 3 and profile["personality_name"] == "Classic")
    move = choose_ai_move(board, "white", oracle_profile, rng=random.Random(3))
    assert move is not None

    piece, from_pos, to_pos, move_text = apply_ai_move(board, "white", oracle_profile, rng=random.Random(3))
    assert board.get_piece_at(from_pos) is None
    assert board.get_piece_at(to_pos) == piece
    assert move_text == f"{position_to_square(from_pos)}{position_to_square(to_pos)}"


def test_configure_game_menu_ai_vs_ai_mode():
    setup = _with_mocked_input(["3", "1", "2"], configure_game_menu, random.Random(0))
    assert setup["mode"] == "ai_vs_ai"
    white_profile = setup["white_ai_profile"]
    black_profile = setup["black_ai_profile"]
    assert isinstance(white_profile, dict)
    assert isinstance(black_profile, dict)
    assert white_profile.get("id") == "d0_random"
    assert black_profile.get("id") != ""


def test_configure_game_menu_quit_option():
    setup = _with_mocked_input(["q"], configure_game_menu, random.Random(0))
    assert setup == {"mode": "quit"}


def test_play_match_ai_vs_ai_returns_terminal_status():
    profiles = get_ai_profiles()
    setup = {
        "mode": "ai_vs_ai",
        "white_ai_profile": profiles[0],
        "black_ai_profile": profiles[0],
    }

    with tempfile.TemporaryDirectory() as temp_dir:
        status = play_match(setup, savefile_path=f"{temp_dir}/match.log", ai_vs_ai_show_board=False)

    assert status["state"] in {"king_capture", "draw"}


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


def test_profile_position_bitmaps_load_per_piece_table():
    profiles = get_ai_profiles()
    expected_piece_tables = ("pawn", "knight", "bishop_white", "bishop_black", "rook", "queen", "king")
    for profile in profiles:
        position_multipliers = profile.get("position_multipliers")
        assert position_multipliers is not None
        for phase_name in ("opening", "endgame"):
            assert phase_name in position_multipliers
            for piece_type in expected_piece_tables:
                assert piece_type in position_multipliers[phase_name]
                assert len(position_multipliers[phase_name][piece_type]) == 64

    basic = next(profile for profile in profiles if profile["id"] == "d2_basic")
    pawnwise = next(profile for profile in profiles if profile["id"] == "d2_pawnwise")

    assert len(set(basic["position_multipliers"]["opening"]["queen"])) == 1
    assert basic["position_multipliers"]["opening"]["queen"][0] == 1.0
    assert basic["position_multipliers"]["opening"]["queen"] == basic["position_multipliers"]["endgame"]["queen"]

    pawnwise_queen = pawnwise["position_multipliers"]["opening"]["queen"]
    pawnwise_rook = pawnwise["position_multipliers"]["opening"]["rook"]
    pawnwise_bishop_white = pawnwise["position_multipliers"]["opening"]["bishop_white"]
    pawnwise_bishop_black = pawnwise["position_multipliers"]["opening"]["bishop_black"]
    assert pawnwise_queen[(3 * 8) + 3] > pawnwise_queen[0]
    assert pawnwise_rook[0] > pawnwise_queen[0]
    assert pawnwise_bishop_white != pawnwise_bishop_black


def test_position_weight_transition_uses_material_phase():
    piece_values = {
        "pawn": 1.0,
        "knight": 3.0,
        "bishop": 3.0,
        "rook": 5.0,
        "queen": 9.0,
        "king": 0.0,
    }

    opening_pawn_weights = [1.0] * 64
    opening_pawn_weights[0] = 2.0
    endgame_pawn_weights = [1.0] * 64
    endgame_pawn_weights[0] = 4.0
    neutral_weights = tuple([1.0] * 64)

    position_multipliers = {
        "opening": {
            "pawn": tuple(opening_pawn_weights),
            "knight": neutral_weights,
            "bishop_white": neutral_weights,
            "bishop_black": neutral_weights,
            "rook": neutral_weights,
            "queen": neutral_weights,
            "king": neutral_weights,
        },
        "endgame": {
            "pawn": tuple(endgame_pawn_weights),
            "knight": neutral_weights,
            "bishop_white": neutral_weights,
            "bishop_black": neutral_weights,
            "rook": neutral_weights,
            "queen": neutral_weights,
            "king": neutral_weights,
        },
    }

    full_board = Board()
    assert _opening_phase_ratio(full_board, piece_values) == 1.0

    endgame_board = _empty_board()
    _place(endgame_board, Pawn("white", (0, 0)))
    endgame_material, endgame_heuristic = evaluate_position_scores(
        endgame_board,
        "white",
        piece_values,
        position_multipliers=position_multipliers,
    )
    assert endgame_material == 1.0
    assert _opening_phase_ratio(endgame_board, piece_values) == 0.0
    assert abs(endgame_heuristic - 3.0) < 1e-9

    mixed_board = _empty_board()
    _place(mixed_board, Pawn("white", (0, 0)))
    _place(mixed_board, Queen("white", (7, 7)))
    mixed_phase = _opening_phase_ratio(mixed_board, piece_values)
    mixed_material, mixed_heuristic = evaluate_position_scores(
        mixed_board,
        "white",
        piece_values,
        position_multipliers=position_multipliers,
    )

    expected_phase = (10.0 - 1.0) / (78.0 - 1.0)
    expected_pawn_weight = (expected_phase * 2.0) + ((1.0 - expected_phase) * 4.0)
    expected_pawn_heuristic = expected_pawn_weight - 1.0

    assert mixed_material == 10.0
    assert abs(mixed_phase - expected_phase) < 1e-9
    assert abs(mixed_heuristic - expected_pawn_heuristic) < 1e-9


def test_kings_bishop_pawn_bitmap_values_prefer_start_square_for_both_sides():
    profiles = get_ai_profiles()
    pawnwise_profiles = [
        profile
        for profile in profiles
        if "pawnwise" in profile["id"] and profile.get("position_multipliers")
    ]
    assert pawnwise_profiles

    def expected_multiplier(color, square):
        col, row = square
        mapped_col = 7 - col
        mapped_row = row if color == "white" else 7 - row
        bitmap_char = PAWNWISE_PAWN_BITMAP_ROWS[mapped_row][mapped_col]
        return BITMAP_BASE53_LOOKUP[bitmap_char] / 26.0

    white_squares = {
        "start": (5, 1),
        "one_step": (5, 2),
        "two_step": (5, 3),
    }
    black_squares = {
        "start": (5, 6),
        "one_step": (5, 5),
        "two_step": (5, 4),
    }

    for profile in pawnwise_profiles:
        position_tables = profile["position_multipliers"]

        for color, squares in (("white", white_squares), ("black", black_squares)):
            actual_multipliers = {}

            for label, square in squares.items():
                col, row = square
                mapped_col = 7 - col
                mapped_row = row if color == "white" else 7 - row
                square_index = (mapped_row * 8) + mapped_col

                actual_multiplier = position_tables["opening"]["pawn"][square_index]
                expected = expected_multiplier(color, square)
                actual_multipliers[label] = actual_multiplier

                assert abs(actual_multiplier - expected) < 1e-9, (
                    f"{profile['id']} {color} {label}: expected {expected}, got {actual_multiplier}"
                )

                board = _empty_board()
                _place(board, Pawn(color, square))
                material_score, heuristic_score = evaluate_position_scores(
                    board,
                    color,
                    profile["piece_values"],
                    pawn_rank_values=profile.get("pawn_rank_values"),
                    backward_pawn_value=profile.get("backward_pawn_value"),
                    position_multipliers=position_tables,
                    control_weight=0.0,
                    opposite_bishop_draw_factor=None,
                )
                expected_heuristic = expected - profile["piece_values"]["pawn"]
                assert abs(material_score - profile["piece_values"]["pawn"]) < 1e-9
                assert abs(heuristic_score - expected_heuristic) < 1e-9, (
                    f"{profile['id']} {color} {label}: expected heuristic {expected_heuristic}, got {heuristic_score}"
                )

            assert actual_multipliers["start"] > actual_multipliers["one_step"], (
                f"{profile['id']} {color}: expected start > one-step, got {actual_multipliers}"
            )
            assert actual_multipliers["start"] > actual_multipliers["two_step"], (
                f"{profile['id']} {color}: expected start > two-step, got {actual_multipliers}"
            )


def test_castling_rights_add_secondary_score_and_rook_movement_loses_it():
    piece_values = {
        "pawn": 1.0,
        "knight": 3.0,
        "bishop": 3.0,
        "rook": 5.0,
        "queen": 9.0,
        "king": 0.0,
    }

    board = _empty_board()
    _place(board, King("white", (4, 0)))
    white_h_rook = _place(board, Rook("white", (7, 0)))
    white_a_rook = _place(board, Rook("white", (0, 0)))
    _place(board, King("black", (4, 7)))

    material_score, heuristic_score = evaluate_position_scores(board, "white", piece_values)
    assert abs(material_score - 10.0) < 1e-9
    assert abs(heuristic_score - 5.0) < 1e-9

    white_h_rook.moved = True
    _, heuristic_without_kingside = evaluate_position_scores(board, "white", piece_values)
    assert abs(heuristic_without_kingside - 2.0) < 1e-9

    white_a_rook.moved = True
    _, heuristic_without_castling = evaluate_position_scores(board, "white", piece_values)
    assert abs(heuristic_without_castling - 0.0) < 1e-9

    black_board = _empty_board()
    _place(black_board, King("white", (4, 0)))
    _place(black_board, King("black", (4, 7)))
    black_h_rook = _place(black_board, Rook("black", (7, 7)))
    black_a_rook = _place(black_board, Rook("black", (0, 7)))

    _, black_heuristic = evaluate_position_scores(black_board, "black", piece_values)
    assert abs(black_heuristic - 5.0) < 1e-9

    black_h_rook.moved = True
    _, black_no_kingside = evaluate_position_scores(black_board, "black", piece_values)
    assert abs(black_no_kingside - 2.0) < 1e-9

    black_a_rook.moved = True
    _, black_none = evaluate_position_scores(black_board, "black", piece_values)
    assert abs(black_none - 0.0) < 1e-9


def test_pawnwise_control_profile_drawish_opposite_bishops():
    board = _empty_board()
    _place(board, Bishop("white", (2, 0)))
    _place(board, Bishop("black", (2, 7)))
    _place(board, Pawn("white", (4, 4)))

    profiles = get_ai_profiles()
    profile = next(profile for profile in profiles if profile["id"] == "d2_pawnwise_control")

    baseline_material, baseline_heuristic = evaluate_position_scores(
        board,
        "white",
        profile["piece_values"],
        pawn_rank_values=profile.get("pawn_rank_values"),
        backward_pawn_value=profile.get("backward_pawn_value"),
        position_multipliers=profile.get("position_multipliers"),
        control_weight=profile.get("control_weight", 0.0),
        opposite_bishop_draw_factor=None,
    )
    drawish_material, drawish_heuristic = evaluate_position_scores(
        board,
        "white",
        profile["piece_values"],
        pawn_rank_values=profile.get("pawn_rank_values"),
        backward_pawn_value=profile.get("backward_pawn_value"),
        position_multipliers=profile.get("position_multipliers"),
        control_weight=profile.get("control_weight", 0.0),
        opposite_bishop_draw_factor=profile.get("opposite_bishop_draw_factor"),
    )

    assert drawish_material == baseline_material
    assert baseline_heuristic != 0
    assert abs(drawish_heuristic - (baseline_heuristic * profile["opposite_bishop_draw_factor"])) < 1e-9


def test_position_heuristics_are_tie_breakers_for_major_pieces():
    center_board = _empty_board()
    corner_board = _empty_board()
    _place(center_board, Queen("white", (3, 3)))
    _place(corner_board, Queen("white", (0, 0)))

    profiles = get_ai_profiles()
    pawnwise = next(profile for profile in profiles if profile["id"] == "d2_pawnwise")

    center_material, center_heuristic = evaluate_position_scores(
        center_board,
        "white",
        pawnwise["piece_values"],
        pawn_rank_values=pawnwise.get("pawn_rank_values"),
        backward_pawn_value=pawnwise.get("backward_pawn_value"),
        position_multipliers=pawnwise.get("position_multipliers"),
    )
    corner_material, corner_heuristic = evaluate_position_scores(
        corner_board,
        "white",
        pawnwise["piece_values"],
        pawn_rank_values=pawnwise.get("pawn_rank_values"),
        backward_pawn_value=pawnwise.get("backward_pawn_value"),
        position_multipliers=pawnwise.get("position_multipliers"),
    )

    assert center_material == corner_material
    assert center_heuristic > corner_heuristic

    center_total = evaluate_material(
        center_board,
        "white",
        pawnwise["piece_values"],
        pawn_rank_values=pawnwise.get("pawn_rank_values"),
        backward_pawn_value=pawnwise.get("backward_pawn_value"),
        position_multipliers=pawnwise.get("position_multipliers"),
    )
    assert abs(center_total - (center_material + center_heuristic)) < 1e-9


def test_minimax_prefers_material_over_heuristic():
    board = _empty_board()
    _place(board, King("white", (7, 0)))
    _place(board, King("black", (6, 7)))
    _place(board, Queen("white", (3, 3)))
    _place(board, Pawn("black", (0, 0)))

    move = choose_minimax_legal_move(
        board,
        "white",
        1,
        {
            "pawn": 1.0,
            "knight": 3.0,
            "bishop": 3.0,
            "rook": 5.0,
            "queen": 9.0,
            "king": 0.0,
        },
        rng=random.Random(0),
        position_multipliers={
            "center": 25.0,
            "center_cross": 25.0,
            "center_diagonal": 10.0,
            "corner": 0.01,
            "corner_rook": 0.01,
            "corner_touch": 0.5,
            "corner_touch_rook": 0.5,
        },
    )

    assert move == ((3, 3), (0, 0))


def test_forcing_capture_extension_does_not_consume_ply():
    if not c_search_available():
        return

    board = _empty_board()
    _place(board, King("white", (0, 0)))
    _place(board, Queen("white", (3, 0)))
    _place(board, King("black", (7, 7)))
    _place(board, Rook("black", (3, 7)))
    _place(board, Bishop("black", (6, 4)))

    piece_values = {
        "pawn": 1.0,
        "knight": 3.0,
        "bishop": 3.0,
        "rook": 5.0,
        "queen": 9.0,
        "king": 0.0,
    }

    no_extension_move = choose_minimax_legal_move(
        board.clone(),
        "white",
        1,
        piece_values,
        captures_extend_plies=False,
    )
    forcing_move = choose_minimax_legal_move(
        board.clone(),
        "white",
        1,
        piece_values,
        captures_extend_plies=True,
    )

    assert no_extension_move == ((3, 0), (3, 7))
    assert forcing_move is not None
    assert forcing_move != ((3, 0), (3, 7))


def test_forcing_profiles_make_legal_moves_on_first_three_halfmoves():
    if not c_search_available():
        return

    profiles_by_id = {profile["id"]: profile for profile in get_ai_profiles()}
    forcing_profile_ids = ("d1_pawnwise_forcing", "d2_pawnwise_forcing", "d3_pawnwise_forcing")

    for profile_id in forcing_profile_ids:
        board = Board()
        active_color = "white"
        cache_handle = create_c_search_cache()
        try:
            for _ in range(3):
                legal_moves_before = set(board.get_legal_moves_for_color(active_color))
                assert legal_moves_before, f"{profile_id} had no legal moves"

                piece, from_pos, to_pos, _ = apply_ai_move(
                    board,
                    active_color,
                    profiles_by_id[profile_id],
                    search_cache_handle=cache_handle,
                )
                assert piece is not None
                assert (from_pos, to_pos) in legal_moves_before
                active_color = board.get_opponent_color(active_color)
        finally:
            destroy_c_search_cache(cache_handle)


def test_forcing_profiles_complete_first_three_halfmoves_without_hanging():
    if not c_search_available():
        return

    probe_script = """
from chess import Board, apply_ai_move, create_c_search_cache, destroy_c_search_cache, get_ai_profiles

profiles_by_id = {profile["id"]: profile for profile in get_ai_profiles()}
forcing_profile_ids = ("d1_pawnwise_forcing", "d2_pawnwise_forcing", "d3_pawnwise_forcing")

for profile_id in forcing_profile_ids:
    board = Board()
    active_color = "white"
    cache_handle = create_c_search_cache()
    try:
        for _ in range(3):
            piece, _from_pos, _to_pos, _move_text = apply_ai_move(
                board,
                active_color,
                profiles_by_id[profile_id],
                search_cache_handle=cache_handle,
            )
            if piece is None:
                raise RuntimeError(f"{profile_id} failed to produce a move")
            active_color = board.get_opponent_color(active_color)
    finally:
        destroy_c_search_cache(cache_handle)

print("ok")
"""

    completed = subprocess.run(
        ["python3", "-c", probe_script],
        text=True,
        capture_output=True,
        timeout=30,
        check=True,
    )
    assert completed.stdout.strip() == "ok"


def test_pawnwise_control_profile_no_selective_second_ply_pruning():
    profiles = get_ai_profiles()
    profile = next(profile for profile in profiles if profile["id"] == "d2_pawnwise_control")
    assert "selective_second_ply_ratio" not in profile


def test_tournament_fixture_counts():
    profiles = get_ai_profiles()
    profile_count = len(profiles)
    assert len(build_fixtures(profiles, "ordered")) == profile_count * (profile_count - 1)
    assert len(build_fixtures(profiles, "single")) == profile_count * (profile_count - 1) // 2


def test_tournament_tiebreaker_prefers_head_to_head_for_champion_tie():
    scoreboard = {
        "a": {
            "id": "a",
            "name": "A",
            "games": 4,
            "wins": 2,
            "draws": 0,
            "losses": 2,
            "raw_points": 2.0,
            "points": 2.0,
        },
        "b": {
            "id": "b",
            "name": "B",
            "games": 4,
            "wins": 2,
            "draws": 0,
            "losses": 2,
            "raw_points": 2.0,
            "points": 2.0,
        },
        "c": {
            "id": "c",
            "name": "C",
            "games": 4,
            "wins": 1,
            "draws": 0,
            "losses": 3,
            "raw_points": 1.0,
            "points": 1.0,
        },
    }
    head_to_head = {
        "a": {"b": 1.5, "c": 0.5},
        "b": {"a": 0.5, "c": 1.5},
        "c": {"a": 1.5, "b": 0.5},
    }

    ranked = rank_rows_with_tiebreakers(scoreboard, head_to_head)

    assert ranked[0]["id"] == "a"
    assert ranked[0]["h2h_tiebreak"] == 1.5
    assert ranked[1]["id"] == "b"


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
        assert len(rows) == manifest["player_count"]
        assert (output_root / "scoreboard.csv").exists()
        assert (output_root / "scoreboard.json").exists()
        assert (output_root / "manifest.json").exists()
        assert len(list((output_root / "matches").iterdir())) == 1


def test_savefile_records_moves():
    with tempfile.TemporaryDirectory() as temp_dir:
        savefile_path = f"{temp_dir}/moves.pgn"
        start_savefile(savefile_path)
        record_move(savefile_path, 1, "white", "e4")
        record_move(savefile_path, 2, "black", "e5")
        finalize_savefile(savefile_path, {"state": "draw", "reason": "stalemate", "winner": None})

        with open(savefile_path, "r", encoding="utf-8") as savefile:
            lines = [line.rstrip("\n") for line in savefile]

    assert lines[0] == "[Event \"OpenCode Chess CLI\"]"
    assert lines[1] == "[Site \"Local\"]"
    assert lines[2].startswith("[Date \"")
    assert lines[2].endswith("\"]")
    assert lines[6] == "[Result \"1/2-1/2\"]"
    assert lines[7] == "[Variant \"We Eat Kings\"]"
    assert lines[8] == ""
    assert lines[9] == "1. e4 e5 1/2-1/2"


def test_apply_user_move_records_with_attached_savefile_recorder():
    with tempfile.TemporaryDirectory() as temp_dir:
        savefile_path = f"{temp_dir}/moves.pgn"
        board = Board()
        savefile_recorder = SavefileRecorder(savefile_path)
        savefile_recorder.start_new_game()
        set_savefile_recorder(board, savefile_recorder)

        apply_user_move(board, "white", "e4")
        apply_user_move(board, "black", "e5")
        savefile_recorder.finalize({"state": "draw", "reason": "stalemate", "winner": None})

        with open(savefile_path, "r", encoding="utf-8") as savefile:
            lines = [line.rstrip("\n") for line in savefile]

    assert lines[9] == "1. e4 e5 1/2-1/2"


def test_parse_uci_position_record_from_move_index_skips_existing_moves():
    with tempfile.TemporaryDirectory() as temp_dir:
        savefile_path = f"{temp_dir}/moves.pgn"
        savefile_recorder = SavefileRecorder(savefile_path)
        savefile_recorder.start_new_game()

        parse_uci_position(["startpos", "moves", "e2e4", "e7e5"], savefile_recorder=savefile_recorder)
        parse_uci_position(
            ["startpos", "moves", "e2e4", "e7e5", "g1f3"],
            savefile_recorder=savefile_recorder,
            record_from_move_index=2,
        )
        savefile_recorder.finalize({"state": "draw", "reason": "stalemate", "winner": None})

        with open(savefile_path, "r", encoding="utf-8") as savefile:
            lines = [line.rstrip("\n") for line in savefile]

    assert lines[9] == "1. e4 e5 2. Nf3 1/2-1/2"


def test_convert_legacy_save_text_to_pgn():
    legacy_text = "\n".join(
        [
            "=== Game started 2026-02-08T10:11:12 ===",
            "1. white e2e4",
            "2. black e7e5",
            "3. white g1f3",
            "",
            "=== Game started 2026-02-08T11:22:33 ===",
            "1. white d2d4",
            "2. black d7d5",
        ]
    )

    converted = convert_legacy_save_text_to_pgn(legacy_text)

    assert "[Date \"2026.02.08\"]" in converted
    assert "1. e4 e5 2. Nf3 *" in converted
    assert "1. d4 d5 *" in converted
    assert converted.count("[Event \"OpenCode Chess CLI\"]") == 2


def test_move_text_to_algebraic_converts_coordinate_notation():
    board = Board()
    assert move_text_to_algebraic(board, "white", "e2e4") == "e4"
    apply_coordinate_move(board, "white", "e2e4")
    assert move_text_to_algebraic(board, "black", "g8f6") == "Nf6"


def test_move_text_to_algebraic_disambiguates_knight_by_file():
    board = _empty_board()
    _place(board, Knight("white", (2, 2)))
    _place(board, Knight("white", (4, 2)))

    assert move_text_to_algebraic(board, "white", "c3d5") == "Ncd5"
    assert move_text_to_algebraic(board, "white", "e3d5") == "Ned5"


def test_move_text_to_algebraic_disambiguates_rook_by_rank():
    board = _empty_board()
    _place(board, Rook("white", (0, 0)))
    _place(board, Rook("white", (0, 6)))

    assert move_text_to_algebraic(board, "white", "a1a4") == "R1a4"
    assert move_text_to_algebraic(board, "white", "a7a4") == "R7a4"


def test_move_text_to_algebraic_disambiguates_queen_by_file_and_rank():
    board = _empty_board()
    _place(board, Queen("white", (0, 0)))
    _place(board, Queen("white", (0, 4)))
    _place(board, Queen("white", (4, 0)))

    assert move_text_to_algebraic(board, "white", "a1e5") == "Qa1e5"


def test_move_text_to_algebraic_uses_pawn_file_on_capture():
    board = _empty_board()
    _place(board, Pawn("white", (4, 3)))
    _place(board, Pawn("black", (5, 4)))

    assert move_text_to_algebraic(board, "white", "e4f5") == "exf5"


def test_c_piece_evaluation_matches_python_when_available():
    if not c_evaluator_available():
        return

    board, _ = _replay_moves(["e2e4", "d7d5", "e4d5", "g8f6", "d2d4", "f6d5"])
    profiles = get_ai_profiles()
    profile = next(profile for profile in profiles if profile["id"] == "d2_pawnwise_control")

    python_scores = _evaluate_position_scores_python_base(
        board,
        "white",
        profile["piece_values"],
        pawn_rank_values=profile.get("pawn_rank_values"),
        backward_pawn_value=profile.get("backward_pawn_value"),
        position_multipliers=profile.get("position_multipliers"),
    )
    c_scores = _evaluate_position_scores_c_base(
        board,
        "white",
        profile["piece_values"],
        pawn_rank_values=profile.get("pawn_rank_values"),
        backward_pawn_value=profile.get("backward_pawn_value"),
        position_multipliers=profile.get("position_multipliers"),
    )

    assert c_scores is not None
    assert abs(c_scores[0] - python_scores[0]) < 1e-9
    assert abs(c_scores[1] - python_scores[1]) < 1e-9


def test_c_search_returns_legal_move_when_available():
    if not c_search_available():
        return

    board = Board()
    profiles = get_ai_profiles()
    oracle_profile = next(profile for profile in profiles if profile["id"] == "d3_basic")

    move = choose_ai_move(board, "white", oracle_profile, rng=random.Random(5))
    assert move in board.get_legal_moves_for_color("white")


def test_pawnwise_fen_prefers_kg1_or_g2_for_shallow_depths():
    if not c_search_available():
        return

    fen_tokens = [
        "fen",
        "3r4/p4r2/3b1p2/2pk2pp/P1p1R3/B1Pp1P1N/3P2PP/5K2",
        "w",
        "-",
        "-",
        "8",
        "30",
    ]
    profiles = get_ai_profiles()
    profile = next(profile for profile in profiles if profile["id"] == "d4_pawnwise")

    for plies in range(1, 5):
        board, active_color = parse_uci_position(fen_tokens)
        move = choose_minimax_legal_move(
            board,
            active_color,
            plies,
            profile["piece_values"],
            pawn_rank_values=profile.get("pawn_rank_values"),
            backward_pawn_value=profile.get("backward_pawn_value"),
            position_multipliers=profile.get("position_multipliers"),
            control_weight=profile.get("control_weight", 0.0),
            opposite_bishop_draw_factor=profile.get("opposite_bishop_draw_factor"),
        )
        assert move is not None

        is_kg1 = move == ((5, 0), (6, 0))
        is_g2_move = move[0] == (6, 1)
        assert is_kg1 or is_g2_move, (
            f"Expected Kg1 or a move from g2 at {plies} plies, got "
            f"{position_to_square(move[0])}{position_to_square(move[1])}"
        )


def test_intermezzo_fen_prefers_qh5_for_ai_three_ply_and_above():
    if not c_search_available():
        return

    fen_tokens = [
        "fen",
        "r1bqkbnr/1pp1p2p/p1n5/3p1pp1/4P3/2NB1Q2/PPPP1PPP/1RB1K1NR",
        "w",
        "Kk",
        "-",
        "0",
        "10",
    ]
    board, active_color = parse_uci_position(fen_tokens)
    assert active_color == "white"

    expected_move = "f3h5"
    profiles = [profile for profile in get_ai_profiles() if profile.get("plies", 0) >= 3]
    assert profiles

    mismatches = []
    for profile in profiles:
        move = choose_ai_move(board.clone(), active_color, profile, rng=random.Random(0))
        move_square_text = "0000" if move is None else f"{position_to_square(move[0])}{position_to_square(move[1])}"
        if move_square_text != expected_move:
            mismatches.append(f"{profile['id']}({profile['plies']}):{move_square_text}")

    assert not mismatches, (
        f"Expected {expected_move} for all AI profiles >=3 plies, mismatches: {', '.join(mismatches)}"
    )


def test_c_search_cache_handle_reused_across_turns():
    if not c_search_available():
        return

    board = Board()
    profiles = get_ai_profiles()
    profile = next(profile for profile in profiles if profile["id"] == "d3_basic")
    cache_handle = create_c_search_cache()
    assert cache_handle is not None

    try:
        piece_one, from_one, to_one, _ = apply_ai_move(
            board,
            "white",
            profile,
            rng=random.Random(1),
            search_cache_handle=cache_handle,
        )
        assert piece_one is not None
        assert from_one is not None
        assert to_one is not None

        move_two = choose_minimax_legal_move(
            board,
            "black",
            profile["plies"],
            profile["piece_values"],
            rng=random.Random(2),
            search_cache_handle=cache_handle,
        )
        assert move_two is not None
        assert move_two in board.get_legal_moves_for_color("black")
    finally:
        destroy_c_search_cache(cache_handle)


def test_parse_uci_position_startpos_with_moves_tracks_turn():
    board, active_color = parse_uci_position(["startpos", "moves", "e2e4", "e7e5", "g1f3"])

    assert active_color == "black"
    piece_e4 = board.get_piece_at((4, 3))
    piece_e5 = board.get_piece_at((4, 4))
    piece_f3 = board.get_piece_at((5, 2))
    assert isinstance(piece_e4, Pawn) and piece_e4.color == "white"
    assert isinstance(piece_e5, Pawn) and piece_e5.color == "black"
    assert isinstance(piece_f3, Knight) and piece_f3.color == "white"


def test_uci_go_reports_score_info_line():
    if not c_search_available():
        return

    command = ["python3", "chess_uci.py", "d2_basic"]
    uci_input = "uci\nisready\nsetoption name InfoMode value verbose\nposition startpos\ngo depth 1\nquit\n"
    completed = subprocess.run(
        command,
        input=uci_input,
        text=True,
        capture_output=True,
        check=True,
    )
    output_lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]

    assert any(line.startswith("info depth 1 score cp ") for line in output_lines)
    assert any(
        line.startswith("info string eval main_pawns ")
        and " main_cp " in line
        and " tiebreak_pawns " in line
        for line in output_lines
    )
    assert any(line.startswith("bestmove ") for line in output_lines)


def test_uci_eval_reports_score_without_bestmove():
    command = ["python3", "chess_uci.py", "d4_pawnwise"]
    uci_input = (
        "uci\n"
        "isready\n"
        "position fen 3r4/p4r2/3b1p2/2pk2pp/P1p1R3/B1Pp1P1N/3P2PP/5K2 w - - 8 30\n"
        "eval\n"
        "quit\n"
    )
    completed = subprocess.run(
        command,
        input=uci_input,
        text=True,
        capture_output=True,
        check=True,
    )
    output_lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]

    assert any(line.startswith("info depth 0 score cp ") for line in output_lines)
    assert any(
        line.startswith("info string eval main_pawns ")
        and " main_cp " in line
        and " tiebreak_pawns " in line
        for line in output_lines
    )
    cp_line = next(line for line in output_lines if line.startswith("info depth 0 score cp "))
    cp_value = int(cp_line.split()[5])
    eval_line = next(line for line in output_lines if line.startswith("info string eval main_pawns "))
    tokens = eval_line.split()
    main_pawns = float(tokens[4])
    tiebreak_pawns = float(tokens[8])
    assert cp_value // 100 == int(round(abs(main_pawns) * 10.0))
    assert cp_value % 100 == min(99, int(abs(tiebreak_pawns)))
    assert not any(line.startswith("bestmove ") for line in output_lines)


def test_uci_go_reports_multipv_lines_when_enabled():
    if not c_search_available():
        return

    command = ["python3", "chess_uci.py", "d2_basic"]
    uci_input = (
        "uci\n"
        "isready\n"
        "setoption name InfoMode value verbose\n"
        "setoption name MultiPV value 3\n"
        "position startpos\n"
        "go depth 1\n"
        "quit\n"
    )
    completed = subprocess.run(
        command,
        input=uci_input,
        text=True,
        capture_output=True,
        check=True,
    )
    output_lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]

    multipv_lines = [
        line
        for line in output_lines
        if line.startswith("info depth 1 ") and " multipv " in line and " pv " in line
    ]
    assert len(multipv_lines) >= 3
    assert any(" multipv 1 " in line and " pv " in line for line in multipv_lines)
    assert any(" multipv 2 " in line and " pv " in line for line in multipv_lines)
    assert any(" multipv 3 " in line and " pv " in line for line in multipv_lines)
    assert any(line.startswith("bestmove ") for line in output_lines)


def test_uci_go_depth_two_with_multipv_three_emits_depth_updates():
    if not c_search_available():
        return

    command = ["python3", "chess_uci.py", "d2_basic"]
    uci_input = (
        "uci\n"
        "isready\n"
        "setoption name InfoMode value verbose\n"
        "setoption name MultiPV value 3\n"
        "position startpos\n"
        "go depth 2\n"
        "quit\n"
    )
    completed = subprocess.run(
        command,
        input=uci_input,
        text=True,
        capture_output=True,
        check=True,
    )
    output_lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    depth_one = [line for line in output_lines if line.startswith("info depth 1 ") and " multipv " in line and " pv " in line]
    depth_two = [line for line in output_lines if line.startswith("info depth 2 ") and " multipv " in line and " pv " in line]
    info_string_two = [line for line in output_lines if line.startswith("info string depth 2 multipv ")]

    assert len(depth_one) == 3
    assert len(depth_two) == 3
    assert len(info_string_two) == 3
    assert any(line.startswith("bestmove ") for line in output_lines)


def test_uci_terminal_lines_outputs_full_width_tree():
    command = ["python3", "chess_uci.py", "d2_basic"]
    uci_input = "uci\nisready\nposition startpos\nterminal_lines depth 2 width 3\nquit\n"
    completed = subprocess.run(
        command,
        input=uci_input,
        text=True,
        capture_output=True,
        check=True,
    )
    output_lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]

    terminal_rows = [line for line in output_lines if line.startswith("info depth 2 multipv ") and " pv " in line]
    assert len(terminal_rows) == 9
    assert any(line == "info string terminal_lines 9" for line in output_lines)


def test_uci_go_terse_mode_omits_verbose_info_lines():
    if not c_search_available():
        return

    command = ["python3", "chess_uci.py", "d2_basic"]
    uci_input = (
        "uci\n"
        "isready\n"
        "setoption name InfoMode value terse\n"
        "position startpos\n"
        "go depth 2\n"
        "quit\n"
    )
    completed = subprocess.run(
        command,
        input=uci_input,
        text=True,
        capture_output=True,
        check=True,
    )
    output_lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]

    assert any(line.startswith("bestmove ") for line in output_lines)
    assert not any(line.startswith("info depth ") for line in output_lines)
    assert not any(line.startswith("info string eval ") for line in output_lines)


def test_uci_proxy_logs_bidirectional_traffic():
    log_path = Path(".tmp_uci_proxy_test.log")
    command = [
        "python3",
        "uci_proxy.py",
        "--log",
        str(log_path),
        "--",
        "python3",
        "-u",
        "-c",
        (
            "import sys\n"
            "for raw in sys.stdin:\n"
            "    text = raw.strip()\n"
            "    print(text.upper(), flush=True)\n"
            "    if text == 'quit':\n"
            "        break\n"
        ),
    ]

    try:
        completed = subprocess.run(
            command,
            input="uci\nquit\n",
            text=True,
            capture_output=True,
            check=True,
        )
        assert "UCI" in completed.stdout
        assert "QUIT" in completed.stdout

        log_text = log_path.read_text(encoding="utf-8")
        assert ">> uci" in log_text
        assert ">> quit" in log_text
        assert "<< UCI" in log_text
        assert "<< QUIT" in log_text
    finally:
        if log_path.exists():
            log_path.unlink()


def test_move_to_uci_adds_queen_promotion_suffix():
    board = _empty_board()
    _place(board, Pawn("white", (4, 6)))

    assert move_to_uci(board, ((4, 6), (4, 7))) == "e7e8q"


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
        test_configure_game_menu_ai_vs_ai_mode,
        test_configure_game_menu_quit_option,
        test_play_match_ai_vs_ai_returns_terminal_status,
        test_pawnwise_profile_heuristics_affect_evaluation,
        test_profile_position_bitmaps_load_per_piece_table,
        test_position_weight_transition_uses_material_phase,
        test_kings_bishop_pawn_bitmap_values_prefer_start_square_for_both_sides,
        test_castling_rights_add_secondary_score_and_rook_movement_loses_it,
        test_pawnwise_control_profile_drawish_opposite_bishops,
        test_position_heuristics_are_tie_breakers_for_major_pieces,
        test_minimax_prefers_material_over_heuristic,
        test_forcing_capture_extension_does_not_consume_ply,
        test_forcing_profiles_make_legal_moves_on_first_three_halfmoves,
        test_forcing_profiles_complete_first_three_halfmoves_without_hanging,
        test_pawnwise_control_profile_no_selective_second_ply_pruning,
        test_tournament_fixture_counts,
        test_tournament_tiebreaker_prefers_head_to_head_for_champion_tie,
        test_tournament_writes_results_and_scoreboard,
        test_savefile_records_moves,
        test_apply_user_move_records_with_attached_savefile_recorder,
        test_parse_uci_position_record_from_move_index_skips_existing_moves,
        test_convert_legacy_save_text_to_pgn,
        test_move_text_to_algebraic_converts_coordinate_notation,
        test_move_text_to_algebraic_disambiguates_knight_by_file,
        test_move_text_to_algebraic_disambiguates_rook_by_rank,
        test_move_text_to_algebraic_disambiguates_queen_by_file_and_rank,
        test_move_text_to_algebraic_uses_pawn_file_on_capture,
        test_c_piece_evaluation_matches_python_when_available,
        test_c_search_returns_legal_move_when_available,
        test_pawnwise_fen_prefers_kg1_or_g2_for_shallow_depths,
        test_intermezzo_fen_prefers_qh5_for_ai_three_ply_and_above,
        test_c_search_cache_handle_reused_across_turns,
        test_parse_uci_position_startpos_with_moves_tracks_turn,
        test_uci_go_reports_score_info_line,
        test_uci_eval_reports_score_without_bestmove,
        test_uci_go_reports_multipv_lines_when_enabled,
        test_uci_go_depth_two_with_multipv_three_emits_depth_updates,
        test_uci_terminal_lines_outputs_full_width_tree,
        test_uci_go_terse_mode_omits_verbose_info_lines,
        test_uci_proxy_logs_bidirectional_traffic,
        test_move_to_uci_adds_queen_promotion_suffix,
    ]

    for test in tests:
        test()

    print(f"{len(tests)} tests passed")


if __name__ == "__main__":
    run_all_tests()
