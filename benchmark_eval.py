import argparse
import random
import time

from chess import (
    _evaluate_position_scores_c_base,
    _evaluate_position_scores_python_base,
    c_evaluator_available,
    get_ai_profiles,
    get_game_status,
    Board,
)


def parse_args():
    parser = argparse.ArgumentParser(description="Benchmark Python vs C AI evaluation")
    parser.add_argument("--positions", type=int, default=2500, help="Number of sampled positions")
    parser.add_argument("--iterations", type=int, default=6, help="Benchmark loops per evaluator")
    parser.add_argument("--max-plies", type=int, default=18, help="Max random plies when generating each position")
    parser.add_argument("--seed", type=int, default=7, help="RNG seed")
    parser.add_argument("--profile-id", default="d2_pawnwise_control", help="AI profile id for eval settings")
    return parser.parse_args()


def _sample_positions(count, max_plies, rng):
    positions = []
    for _ in range(count):
        board = Board()
        current_turn = "white"
        plies = rng.randint(0, max_plies)

        for _ in range(plies):
            if get_game_status(board, current_turn)["state"] != "in_progress":
                break
            legal_moves = board.get_legal_moves_for_color(current_turn)
            if not legal_moves:
                break
            from_pos, to_pos = rng.choice(legal_moves)
            board.move_piece(from_pos, to_pos)
            current_turn = board.get_opponent_color(current_turn)

        positions.append(board)
    return positions


def _evaluate_python(positions, perspective_color, profile):
    total = 0.0
    for board in positions:
        material_score, heuristic_score = _evaluate_position_scores_python_base(
            board,
            perspective_color,
            profile["piece_values"],
            pawn_rank_values=profile.get("pawn_rank_values"),
            backward_pawn_value=profile.get("backward_pawn_value"),
            position_multipliers=profile.get("position_multipliers"),
        )
        total += material_score + heuristic_score
    return total


def _evaluate_c(positions, perspective_color, profile):
    total = 0.0
    for board in positions:
        scores = _evaluate_position_scores_c_base(
            board,
            perspective_color,
            profile["piece_values"],
            pawn_rank_values=profile.get("pawn_rank_values"),
            backward_pawn_value=profile.get("backward_pawn_value"),
            position_multipliers=profile.get("position_multipliers"),
        )
        if scores is None:
            raise RuntimeError("C evaluator unavailable during benchmark")
        total += scores[0] + scores[1]
    return total


def _benchmark(label, func, positions, perspective_color, profile, iterations):
    start = time.perf_counter()
    checksum = 0.0
    for _ in range(iterations):
        checksum += func(positions, perspective_color, profile)
    elapsed = time.perf_counter() - start
    calls = len(positions) * iterations
    per_call_us = (elapsed / calls) * 1_000_000.0
    print(f"{label:>8}: {elapsed:.4f}s total, {per_call_us:.2f} us/eval, checksum={checksum:.4f}")
    return elapsed, checksum


def main():
    args = parse_args()
    rng = random.Random(args.seed)
    profiles = get_ai_profiles()
    profile = next((entry for entry in profiles if entry["id"] == args.profile_id), None)
    if profile is None:
        raise ValueError(f"Unknown profile id: {args.profile_id}")

    perspective_color = "white"
    positions = _sample_positions(args.positions, args.max_plies, rng)
    print(
        f"Generated {len(positions)} positions, iterations={args.iterations}, "
        f"profile={profile['id']}, seed={args.seed}"
    )

    python_elapsed, python_checksum = _benchmark(
        "python",
        _evaluate_python,
        positions,
        perspective_color,
        profile,
        args.iterations,
    )

    if not c_evaluator_available():
        print("C evaluator unavailable (gcc/build/load failed), skipping C benchmark")
        return

    c_elapsed, c_checksum = _benchmark(
        "c",
        _evaluate_c,
        positions,
        perspective_color,
        profile,
        args.iterations,
    )

    delta = abs(c_checksum - python_checksum)
    speedup = python_elapsed / c_elapsed if c_elapsed > 0 else float("inf")
    print(f"checksum delta: {delta:.10f}")
    print(f"speedup: {speedup:.2f}x")


if __name__ == "__main__":
    main()
