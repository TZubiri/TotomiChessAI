import argparse
import csv
import json
import random
from datetime import datetime
from pathlib import Path

from chess import Board, apply_ai_move, get_ai_profiles, get_game_status


def build_fixtures(players, mode):
    fixtures = []
    if mode == "ordered":
        for white_player in players:
            for black_player in players:
                if white_player["id"] != black_player["id"]:
                    fixtures.append((white_player, black_player))
        return fixtures

    for index in range(len(players)):
        for opponent_index in range(index + 1, len(players)):
            fixtures.append((players[index], players[opponent_index]))
    return fixtures


def play_ai_match(white_profile, black_profile, rng, max_halfmoves):
    board = Board()
    current_turn = "white"
    move_list = []
    ai_by_color = {"white": white_profile, "black": black_profile}

    while True:
        status = get_game_status(board, current_turn)
        if status["state"] != "in_progress":
            break

        if len(move_list) >= max_halfmoves:
            status = {"state": "draw", "reason": "move_limit", "winner": None}
            break

        piece, from_pos, to_pos, move_text = apply_ai_move(board, current_turn, ai_by_color[current_turn], rng=rng)
        move_list.append(
            {
                "ply": len(move_list) + 1,
                "color": current_turn,
                "piece": piece.__class__.__name__,
                "from": [from_pos[0], from_pos[1]],
                "to": [to_pos[0], to_pos[1]],
                "move": move_text,
            }
        )
        current_turn = board.get_opponent_color(current_turn)

    if status["winner"] == "white":
        white_points = 1.0
        black_points = 0.0
    elif status["winner"] == "black":
        white_points = 0.0
        black_points = 1.0
    else:
        white_points = 0.5
        black_points = 0.5

    return {
        "status": status,
        "moves": move_list,
        "white_points": white_points,
        "black_points": black_points,
        "final_board": str(board),
        "plies_played": len(move_list),
    }


def write_match_artifacts(output_root, match_index, white_profile, black_profile, result):
    match_slug = f"{match_index:03d}_{white_profile['id']}_vs_{black_profile['id']}"
    match_dir = output_root / "matches" / match_slug
    match_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "match": match_index,
        "white": white_profile,
        "black": black_profile,
        "result": {
            "status": result["status"],
            "plies_played": result["plies_played"],
            "white_points": result["white_points"],
            "black_points": result["black_points"],
        },
        "moves": result["moves"],
    }
    with open(match_dir / "result.json", "w", encoding="utf-8") as result_file:
        json.dump(metadata, result_file, indent=2)

    with open(match_dir / "moves.txt", "w", encoding="utf-8") as moves_file:
        for move in result["moves"]:
            moves_file.write(f"{move['ply']}. {move['color']} {move['move']}\n")

    with open(match_dir / "final_board.txt", "w", encoding="utf-8") as board_file:
        board_file.write(result["final_board"])
        board_file.write("\n")


def write_scoreboard(output_root, rows):
    with open(output_root / "scoreboard.csv", "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(
            [
                "rank",
                "id",
                "name",
                "games",
                "wins",
                "draws",
                "losses",
                "raw_points",
                "points",
            ]
        )
        for index, row in enumerate(rows, start=1):
            writer.writerow(
                [
                    index,
                    row["id"],
                    row["name"],
                    row["games"],
                    row["wins"],
                    row["draws"],
                    row["losses"],
                    f"{row['raw_points']:.2f}",
                    f"{row['points']:.2f}",
                ]
            )

    with open(output_root / "scoreboard.json", "w", encoding="utf-8") as json_file:
        json.dump(rows, json_file, indent=2)


def run_tournament(output_dir, pairing_mode, seed, max_halfmoves, max_matches=None):
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "matches").mkdir(parents=True, exist_ok=True)

    players = get_ai_profiles()
    fixtures = build_fixtures(players, pairing_mode)
    if max_matches is not None:
        fixtures = fixtures[:max_matches]

    scoreboard = {
        player["id"]: {
            "id": player["id"],
            "name": player["name"],
            "games": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "raw_points": 0.0,
            "points": 0.0,
        }
        for player in players
    }

    rng = random.Random(seed)
    for match_index, (white_profile, black_profile) in enumerate(fixtures, start=1):
        result = play_ai_match(white_profile, black_profile, rng, max_halfmoves)
        write_match_artifacts(output_root, match_index, white_profile, black_profile, result)

        white_row = scoreboard[white_profile["id"]]
        black_row = scoreboard[black_profile["id"]]

        white_row["games"] += 1
        black_row["games"] += 1
        white_row["raw_points"] += result["white_points"]
        black_row["raw_points"] += result["black_points"]

        if result["white_points"] == 1.0:
            white_row["wins"] += 1
            black_row["losses"] += 1
        elif result["black_points"] == 1.0:
            black_row["wins"] += 1
            white_row["losses"] += 1
        else:
            white_row["draws"] += 1
            black_row["draws"] += 1

    max_games = max((entry["games"] for entry in scoreboard.values()), default=0)
    score_scale = (len(players) - 1) / max_games if max_games else 0.0
    for row in scoreboard.values():
        row["points"] = row["raw_points"] * score_scale

    sorted_rows = sorted(
        scoreboard.values(),
        key=lambda row: (row["points"], row["raw_points"], row["wins"]),
        reverse=True,
    )
    write_scoreboard(output_root, sorted_rows)

    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "seed": seed,
        "pairing_mode": pairing_mode,
        "player_count": len(players),
        "match_count": len(fixtures),
        "max_halfmoves": max_halfmoves,
        "max_score": len(players) - 1,
        "notes": "points are normalized to max_score; raw_points retain standard scoring",
    }
    with open(output_root / "manifest.json", "w", encoding="utf-8") as manifest_file:
        json.dump(manifest, manifest_file, indent=2)

    return manifest, sorted_rows


def parse_args():
    parser = argparse.ArgumentParser(description="Run an AI chess round robin tournament")
    parser.add_argument(
        "--output-dir",
        default=f"tournament_results/{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        help="Directory where tournament outputs are written",
    )
    parser.add_argument(
        "--pairing-mode",
        choices=["ordered", "single"],
        default="ordered",
        help="ordered gives 90 matches for 10 AIs; single gives 45",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--max-halfmoves",
        type=int,
        default=300,
        help="Abort game as draw after this many plies",
    )
    parser.add_argument(
        "--max-matches",
        type=int,
        default=None,
        help="Optional cap for quick trial runs",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    manifest, rows = run_tournament(
        output_dir=args.output_dir,
        pairing_mode=args.pairing_mode,
        seed=args.seed,
        max_halfmoves=args.max_halfmoves,
        max_matches=args.max_matches,
    )

    print(f"Tournament complete: {manifest['match_count']} matches")
    print(f"Output directory: {args.output_dir}")
    if rows:
        print("Top 3:")
        for index, row in enumerate(rows[:3], start=1):
            print(
                f"{index}. {row['name']} - {row['points']:.2f}/{manifest['max_score']} "
                f"(raw {row['raw_points']:.2f})"
            )


if __name__ == "__main__":
    main()
