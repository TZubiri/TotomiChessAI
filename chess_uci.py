#!/usr/bin/env python3
import os
import sys

from chess import (
    DEFAULT_SAVEFILE,
    Board,
    King,
    Pawn,
    SavefileRecorder,
    apply_coordinate_move,
    choose_ai_move,
    create_c_search_cache,
    destroy_c_search_cache,
    evaluate_material,
    get_ai_profiles,
    get_game_status,
    position_to_square,
    set_savefile_recorder,
    square_to_position,
)


ENGINE_NAME = "OpenCode Chess UCI"
ENGINE_AUTHOR = "OpenCode"


def _opponent(color):
    return "black" if color == "white" else "white"


def _reset_board(board):
    board.board = [[None for _ in range(8)] for _ in range(8)]
    board.pieces = []
    board.en_passant_target = None
    board.en_passant_capture_position = None
    board.halfmove_clock = 0
    board.position_counts = {}


def _set_castling_flags_from_fen(board, castling):
    for piece in board.pieces:
        piece.moved = True

    if castling == "-":
        return

    white_king = board.get_piece_at((4, 0))
    black_king = board.get_piece_at((4, 7))

    if any(flag in castling for flag in ("K", "Q")):
        if not isinstance(white_king, King) or white_king.color != "white":
            raise ValueError("Invalid FEN castling rights: missing white king on e1")
        white_king.moved = False

    if any(flag in castling for flag in ("k", "q")):
        if not isinstance(black_king, King) or black_king.color != "black":
            raise ValueError("Invalid FEN castling rights: missing black king on e8")
        black_king.moved = False

    if "K" in castling:
        rook = board.get_piece_at((7, 0))
        if rook is None or rook.__class__.__name__ != "Rook" or rook.color != "white":
            raise ValueError("Invalid FEN castling rights: missing white rook on h1")
        rook.moved = False
    if "Q" in castling:
        rook = board.get_piece_at((0, 0))
        if rook is None or rook.__class__.__name__ != "Rook" or rook.color != "white":
            raise ValueError("Invalid FEN castling rights: missing white rook on a1")
        rook.moved = False
    if "k" in castling:
        rook = board.get_piece_at((7, 7))
        if rook is None or rook.__class__.__name__ != "Rook" or rook.color != "black":
            raise ValueError("Invalid FEN castling rights: missing black rook on h8")
        rook.moved = False
    if "q" in castling:
        rook = board.get_piece_at((0, 7))
        if rook is None or rook.__class__.__name__ != "Rook" or rook.color != "black":
            raise ValueError("Invalid FEN castling rights: missing black rook on a8")
        rook.moved = False


def board_from_fen(fen_text):
    fields = fen_text.strip().split()
    if len(fields) < 4:
        raise ValueError("FEN must include at least piece placement, turn, castling, and en-passant")

    piece_placement = fields[0]
    active_color = fields[1]
    castling = fields[2]
    en_passant = fields[3]
    halfmove_clock = int(fields[4]) if len(fields) > 4 else 0

    if active_color not in ("w", "b"):
        raise ValueError(f"Invalid FEN active color: {active_color}")

    board = Board()
    _reset_board(board)

    ranks = piece_placement.split("/")
    if len(ranks) != 8:
        raise ValueError("FEN piece placement must contain 8 ranks")

    piece_type_map = {
        "p": "pawn",
        "n": "knight",
        "b": "bishop",
        "r": "rook",
        "q": "queen",
        "k": "king",
    }

    for rank_index, rank_text in enumerate(ranks):
        row = 7 - rank_index
        col = 0
        for char in rank_text:
            if char.isdigit():
                col += int(char)
                continue
            piece_type = piece_type_map.get(char.lower())
            if piece_type is None:
                raise ValueError(f"Invalid FEN piece token: {char}")
            if col >= 8:
                raise ValueError("FEN rank overflow")
            color = "white" if char.isupper() else "black"
            board.add_piece(color, piece_type, (col, row))
            col += 1
        if col != 8:
            raise ValueError("FEN rank does not sum to 8 squares")

    _set_castling_flags_from_fen(board, castling)

    board.en_passant_target = None
    board.en_passant_capture_position = None
    if en_passant != "-":
        ep_target = square_to_position(en_passant)
        board.en_passant_target = ep_target
        capture_row = ep_target[1] - 1 if active_color == "w" else ep_target[1] + 1
        capture_position = (ep_target[0], capture_row)
        captured_piece = board.get_piece_at(capture_position)
        if isinstance(captured_piece, Pawn) and captured_piece.color == ("black" if active_color == "w" else "white"):
            board.en_passant_capture_position = capture_position

    board.halfmove_clock = max(0, halfmove_clock)
    side_to_move = "white" if active_color == "w" else "black"
    board.record_position(side_to_move)
    return board, side_to_move


def _extract_position_move_tokens(position_tokens):
    if not position_tokens:
        raise ValueError("position command is missing arguments")

    if position_tokens[0] == "startpos":
        if len(position_tokens) > 1:
            if position_tokens[1] != "moves":
                raise ValueError("Expected 'moves' after 'startpos'")
            return position_tokens[2:]
        return []

    if position_tokens[0] == "fen":
        if len(position_tokens) < 5:
            raise ValueError("position fen command is incomplete")
        try:
            moves_index = position_tokens.index("moves")
            return position_tokens[moves_index + 1 :]
        except ValueError:
            return []

    raise ValueError(f"Unsupported position source: {position_tokens[0]}")


def parse_uci_position(position_tokens, savefile_recorder=None, record_from_move_index=0):
    if not position_tokens:
        raise ValueError("position command is missing arguments")

    move_tokens = _extract_position_move_tokens(position_tokens)
    if position_tokens[0] == "startpos":
        board = Board()
        active_color = "white"
    elif position_tokens[0] == "fen":
        try:
            moves_index = position_tokens.index("moves")
            fen_tokens = position_tokens[1:moves_index]
        except ValueError:
            fen_tokens = position_tokens[1:]
        board, active_color = board_from_fen(" ".join(fen_tokens))
    else:
        raise ValueError(f"Unsupported position source: {position_tokens[0]}")

    if savefile_recorder is not None:
        set_savefile_recorder(board, savefile_recorder)

    for move_index, move_text in enumerate(move_tokens):
        should_record = move_index >= record_from_move_index
        apply_coordinate_move(board, active_color, move_text, record=should_record)
        active_color = _opponent(active_color)

    return board, active_color


def move_to_uci(board, move):
    from_pos, to_pos = move
    move_text = f"{position_to_square(from_pos)}{position_to_square(to_pos)}"
    piece = board.get_piece_at(from_pos)
    if isinstance(piece, Pawn) and to_pos[1] in (0, 7):
        return f"{move_text}q"
    return move_text


def _is_standard_legal_move(board, color, move):
    from_pos, to_pos = move
    piece = board.get_piece_at(from_pos)
    if piece is None or piece.color != color:
        return False

    if isinstance(piece, King) and abs(to_pos[0] - from_pos[0]) == 2:
        if board.is_in_check(color):
            return False
        step = 1 if to_pos[0] > from_pos[0] else -1
        middle_pos = (from_pos[0] + step, from_pos[1])
        middle = board.clone()
        if not middle.move_piece(from_pos, middle_pos, update_tracking=False):
            return False
        if middle.is_in_check(color):
            return False

    simulation = board.clone()
    if not simulation.move_piece(from_pos, to_pos, update_tracking=False):
        return False
    if simulation.find_king_position(color) is None:
        return False
    return not simulation.is_in_check(color)


def _choose_fallback_standard_move(board, color, profile):
    legal_moves = [
        move
        for move in board.get_legal_moves_for_color(color)
        if _is_standard_legal_move(board, color, move)
    ]
    if not legal_moves:
        return None

    best_move = None
    best_score = float("-inf")
    for move in legal_moves:
        simulation = board.clone()
        simulation.move_piece(move[0], move[1])
        score = evaluate_material(
            simulation,
            color,
            profile["piece_values"],
            pawn_rank_values=profile.get("pawn_rank_values"),
            backward_pawn_value=profile.get("backward_pawn_value"),
            position_multipliers=profile.get("position_multipliers"),
            control_weight=profile.get("control_weight", 0.0),
            opposite_bishop_draw_factor=profile.get("opposite_bishop_draw_factor"),
        )
        if score > best_score:
            best_score = score
            best_move = move
    return best_move


def _score_move_in_centipawns(board, color, move, profile):
    simulation = board.clone()
    simulation.move_piece(move[0], move[1])
    score = evaluate_material(
        simulation,
        color,
        profile["piece_values"],
        pawn_rank_values=profile.get("pawn_rank_values"),
        backward_pawn_value=profile.get("backward_pawn_value"),
        position_multipliers=profile.get("position_multipliers"),
        control_weight=profile.get("control_weight", 0.0),
        opposite_bishop_draw_factor=profile.get("opposite_bishop_draw_factor"),
    )
    return int(round(score * 100.0))

import sys
class UCIEngine:
    def __init__(self):
        profiles = get_ai_profiles()
        self.profile_by_id = {profile["id"]: profile for profile in profiles}
        self.profile_ids = [profile["id"] for profile in profiles if profile["plies"] > 0]

	
        default_profile_id = os.environ.get("CHESS_UCI_PROFILE", sys.argv[1])
        if default_profile_id not in self.profile_by_id:
            raise Exception("404 AI Not found")

        self.profile_id = default_profile_id
        self.cache_mb = int(os.environ.get("CHESS_UCI_CACHE_MB", "512"))
        self.search_cache_handle = None
        self.board = Board()
        self.active_color = "white"
        self.savefile_recorder = SavefileRecorder(os.environ.get("CHESS_UCI_SAVEFILE", DEFAULT_SAVEFILE))
        self.position_move_tokens = []
        set_savefile_recorder(self.board, self.savefile_recorder)

    def _send(self, line):
        sys.stdout.write(f"{line}\n")
        sys.stdout.flush()

    def _reset_cache(self):
        if self.search_cache_handle is not None:
            destroy_c_search_cache(self.search_cache_handle)
            self.search_cache_handle = None
        cache_bytes = self.cache_mb * 1024 * 1024
        self.search_cache_handle = create_c_search_cache(cache_bytes)

    def _ensure_cache(self):
        if self.search_cache_handle is None:
            self._reset_cache()

    def _status_for_recording_end(self, fallback_reason):
        status = get_game_status(self.board, self.active_color)
        if status["state"] == "in_progress":
            return {"state": "aborted", "reason": fallback_reason, "winner": None}
        return status

    def _finalize_current_recording(self, fallback_reason):
        if not self.savefile_recorder.has_moves():
            return
        self.savefile_recorder.finalize(self._status_for_recording_end(fallback_reason))

    def _start_new_recording(self):
        self.savefile_recorder.prepare_new_game()
        self.position_move_tokens = []
        set_savefile_recorder(self.board, self.savefile_recorder)

    def _handle_uci(self):
        self._send(f"id name {ENGINE_NAME}")
        self._send(f"id author {ENGINE_AUTHOR}")
        self._send(
            "option name Profile type combo default "
            f"{self.profile_id} "
            + " ".join(f"var {profile_id}" for profile_id in self.profile_ids)
        )
        self._send(
            f"option name CacheMB type spin default {self.cache_mb} min 16 max 4096"
        )
        self._send("uciok")

    def _handle_setoption(self, line):
        payload = line[len("setoption") :].strip()
        if not payload.startswith("name "):
            return

        payload = payload[5:]
        if " value " in payload:
            name, value = payload.split(" value ", 1)
        else:
            name, value = payload, ""
        name = name.strip().lower()
        value = value.strip()

        if name == "profile":
            if value in self.profile_by_id:
                self.profile_id = value
            else:
                self._send(f"info string Unknown profile '{value}'")
            return

        if name == "cachemb":
            try:
                parsed = int(value)
            except ValueError:
                self._send(f"info string Invalid CacheMB value '{value}'")
                return
            self.cache_mb = max(16, min(4096, parsed))
            self._reset_cache()

    def _handle_go(self, line):
        self._ensure_cache()
        profile = dict(self.profile_by_id[self.profile_id])
        profile["search_cache_handle"] = self.search_cache_handle

        go_tokens = line.split()
        search_depth = profile["plies"]
        for index, token in enumerate(go_tokens):
            if token == "depth" and index + 1 < len(go_tokens):
                try:
                    search_depth = max(1, int(go_tokens[index + 1]))
                except ValueError:
                    pass
                break

        profile["plies"] = search_depth

        chosen_move = choose_ai_move(self.board, self.active_color, profile)
        if chosen_move is not None and _is_standard_legal_move(self.board, self.active_color, chosen_move):
            bestmove_uci = move_to_uci(self.board, chosen_move)
            cp = _score_move_in_centipawns(self.board, self.active_color, chosen_move, profile)
            self._send(f"info depth {search_depth} score cp {cp} pv {bestmove_uci}")
            self._send(f"bestmove {move_to_uci(self.board, chosen_move)}")
            return

        fallback_move = _choose_fallback_standard_move(self.board, self.active_color, profile)
        if fallback_move is None:
            self._send("bestmove 0000")
            return

        self._send("info string Primary move failed strict legality check; using fallback")
        fallback_uci = move_to_uci(self.board, fallback_move)
        cp = _score_move_in_centipawns(self.board, self.active_color, fallback_move, profile)
        self._send(f"info depth {search_depth} score cp {cp} pv {fallback_uci}")
        self._send(f"bestmove {move_to_uci(self.board, fallback_move)}")

    def run(self):
        try:
            self._reset_cache()
            while True:
                raw_line = sys.stdin.readline()
                if not raw_line:
                    break
                line = raw_line.strip()
                if not line:
                    continue

                if line == "uci":
                    self._handle_uci()
                    continue
                if line == "isready":
                    self._ensure_cache()
                    self._send("readyok")
                    continue
                if line == "ucinewgame":
                    self._finalize_current_recording("ucinewgame")
                    self.board = Board()
                    self.active_color = "white"
                    self._start_new_recording()
                    self._reset_cache()
                    continue
                if line.startswith("position "):
                    try:
                        position_tokens = line.split()[1:]
                        move_tokens = _extract_position_move_tokens(position_tokens)
                        if self.savefile_recorder.finalized:
                            self._start_new_recording()

                        if move_tokens[: len(self.position_move_tokens)] == self.position_move_tokens:
                            record_from_move_index = len(self.position_move_tokens)
                        else:
                            self._finalize_current_recording("position_reset")
                            self._start_new_recording()
                            record_from_move_index = 0

                        self.board, self.active_color = parse_uci_position(
                            position_tokens,
                            savefile_recorder=self.savefile_recorder,
                            record_from_move_index=record_from_move_index,
                        )
                        self.position_move_tokens = move_tokens

                        terminal_status = get_game_status(self.board, self.active_color)
                        if terminal_status["state"] != "in_progress":
                            self.savefile_recorder.finalize(terminal_status)
                    except ValueError as error:
                        self._send(f"info string position parse error: {error}")
                    continue
                if line.startswith("setoption "):
                    self._handle_setoption(line)
                    continue
                if line.startswith("go"):
                    self._handle_go(line)
                    continue
                if line in ("stop", "ponderhit"):
                    continue
                if line in ("quit", "exit"):
                    break
        finally:
            self._finalize_current_recording("quit")
            if self.search_cache_handle is not None:
                destroy_c_search_cache(self.search_cache_handle)


if __name__ == "__main__":
    engine = UCIEngine()
    engine.run()
