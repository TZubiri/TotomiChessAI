#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define MAX_PIECES 64
#define MAX_MOVES 256

enum {
    PIECE_PAWN = 0,
    PIECE_KNIGHT = 1,
    PIECE_BISHOP = 2,
    PIECE_ROOK = 3,
    PIECE_QUEEN = 4,
    PIECE_KING = 5,
};

typedef struct {
    int piece_count;
    int piece_type[MAX_PIECES];
    int piece_color[MAX_PIECES];
    int piece_col[MAX_PIECES];
    int piece_row[MAX_PIECES];
    int piece_moved[MAX_PIECES];
    int alive[MAX_PIECES];
    int board[8][8];
    int en_passant_target_col;
    int en_passant_target_row;
    int en_passant_capture_col;
    int en_passant_capture_row;
    int halfmove_clock;
} SearchState;

typedef struct {
    int from_col;
    int from_row;
    int to_col;
    int to_row;
    int promotion_type;
} Move;

typedef struct {
    Move entries[MAX_MOVES];
    int count;
} MoveList;

typedef struct {
    double material;
    double heuristic;
} Score;

typedef struct {
    const double* piece_values;
    const double* pawn_rank_values;
    int has_pawn_rank_values;
    double backward_pawn_value;
    int has_backward_pawn_value;
    const double* position_multipliers;
    int has_position_multipliers;
    double control_weight;
    double opposite_bishop_draw_factor;
    int has_opposite_bishop_draw_factor;
} EvalParams;

typedef struct {
    uint64_t key;
    int remaining_plies;
    int active_color;
    double material;
    double heuristic;
    uint8_t valid;
} CacheEntry;

typedef struct {
    size_t capacity;
    CacheEntry* entries;
} SearchCache;

static int is_inside(int col, int row) {
    return col >= 0 && col < 8 && row >= 0 && row < 8;
}

static int opponent_color(int color) {
    return color == 0 ? 1 : 0;
}

static int is_corner_square(int col, int row) {
    return (col == 0 || col == 7) && (row == 0 || row == 7);
}

static int is_corner_touch_square(int col, int row) {
    return ((col == 1 || col == 6) && (row == 0 || row == 7)) || ((row == 1 || row == 6) && (col == 0 || col == 7));
}

static int is_center_square(int col, int row) {
    return (col == 3 || col == 4) && (row == 3 || row == 4);
}

static int is_center_cross_square(int col, int row) {
    return (col == 2 && (row == 3 || row == 4))
        || (col == 3 && (row == 2 || row == 5))
        || (col == 4 && (row == 2 || row == 5))
        || (col == 5 && (row == 3 || row == 4));
}

static int is_center_diagonal_square(int col, int row) {
    return (col == 2 || col == 5) && (row == 2 || row == 5);
}

static double square_weight_for_piece(int piece_type, int col, int row, const double* position_multipliers, int has_position_multipliers) {
    if (!has_position_multipliers) {
        return 1.0;
    }

    if (is_corner_square(col, row)) {
        return piece_type == PIECE_ROOK ? position_multipliers[4] : position_multipliers[3];
    }
    if (is_corner_touch_square(col, row)) {
        return piece_type == PIECE_ROOK ? position_multipliers[6] : position_multipliers[5];
    }
    if (is_center_square(col, row)) {
        return position_multipliers[0];
    }
    if (is_center_cross_square(col, row)) {
        return position_multipliers[1];
    }
    if (is_center_diagonal_square(col, row)) {
        return position_multipliers[2];
    }
    return 1.0;
}

static int compare_score(Score a, Score b) {
    if (a.material < b.material) {
        return -1;
    }
    if (a.material > b.material) {
        return 1;
    }
    if (a.heuristic < b.heuristic) {
        return -1;
    }
    if (a.heuristic > b.heuristic) {
        return 1;
    }
    return 0;
}

static Score score_for_winner(int winner, int perspective_color) {
    Score score;
    score.material = winner == perspective_color ? 100000.0 : -100000.0;
    score.heuristic = 0.0;
    return score;
}

static Score draw_score(void) {
    Score score;
    score.material = 0.0;
    score.heuristic = 0.0;
    return score;
}

static void clear_board(SearchState* state) {
    for (int row = 0; row < 8; row++) {
        for (int col = 0; col < 8; col++) {
            state->board[row][col] = -1;
        }
    }
}

static int init_state(
    SearchState* state,
    const int* piece_types,
    const int* piece_colors,
    const int* piece_cols,
    const int* piece_rows,
    const int* piece_moved,
    int piece_count,
    int en_passant_target_col,
    int en_passant_target_row,
    int en_passant_capture_col,
    int en_passant_capture_row,
    int halfmove_clock
) {
    if (piece_count < 0 || piece_count > MAX_PIECES) {
        return 0;
    }

    state->piece_count = piece_count;
    clear_board(state);

    for (int i = 0; i < piece_count; i++) {
        int piece_type = piece_types[i];
        int piece_color = piece_colors[i];
        int col = piece_cols[i];
        int row = piece_rows[i];

        if (!is_inside(col, row)) {
            return 0;
        }
        if (piece_type < PIECE_PAWN || piece_type > PIECE_KING) {
            return 0;
        }
        if (piece_color != 0 && piece_color != 1) {
            return 0;
        }
        if (state->board[row][col] != -1) {
            return 0;
        }

        state->piece_type[i] = piece_type;
        state->piece_color[i] = piece_color;
        state->piece_col[i] = col;
        state->piece_row[i] = row;
        state->piece_moved[i] = piece_moved != NULL ? piece_moved[i] : 0;
        state->alive[i] = 1;
        state->board[row][col] = i;
    }

    state->en_passant_target_col = en_passant_target_col;
    state->en_passant_target_row = en_passant_target_row;
    state->en_passant_capture_col = en_passant_capture_col;
    state->en_passant_capture_row = en_passant_capture_row;
    state->halfmove_clock = halfmove_clock;
    return 1;
}

static int append_move(MoveList* list, int from_col, int from_row, int to_col, int to_row, int promotion_type) {
    if (list->count >= MAX_MOVES) {
        return 0;
    }

    Move move;
    move.from_col = from_col;
    move.from_row = from_row;
    move.to_col = to_col;
    move.to_row = to_row;
    move.promotion_type = promotion_type;
    list->entries[list->count] = move;
    list->count += 1;
    return 1;
}

static void generate_moves_for_piece(const SearchState* state, int piece_index, MoveList* list) {
    if (!state->alive[piece_index]) {
        return;
    }

    int piece_type = state->piece_type[piece_index];
    int piece_color = state->piece_color[piece_index];
    int col = state->piece_col[piece_index];
    int row = state->piece_row[piece_index];

    if (piece_type == PIECE_PAWN) {
        int direction = piece_color == 0 ? 1 : -1;
        int one_forward = row + direction;
        if (is_inside(col, one_forward) && state->board[one_forward][col] == -1) {
            int promotion = (one_forward == 0 || one_forward == 7) ? PIECE_QUEEN : -1;
            append_move(list, col, row, col, one_forward, promotion);

            int two_forward = row + (2 * direction);
            if (!state->piece_moved[piece_index] && is_inside(col, two_forward) && state->board[two_forward][col] == -1) {
                append_move(list, col, row, col, two_forward, -1);
            }
        }

        for (int delta_col = -1; delta_col <= 1; delta_col += 2) {
            int capture_col = col + delta_col;
            int capture_row = row + direction;
            if (!is_inside(capture_col, capture_row)) {
                continue;
            }

            int target_index = state->board[capture_row][capture_col];
            if (target_index != -1 && state->alive[target_index] && state->piece_color[target_index] != piece_color) {
                int promotion = (capture_row == 0 || capture_row == 7) ? PIECE_QUEEN : -1;
                append_move(list, col, row, capture_col, capture_row, promotion);
                continue;
            }

            if (
                state->en_passant_target_col == capture_col
                && state->en_passant_target_row == capture_row
                && state->board[capture_row][capture_col] == -1
                && is_inside(state->en_passant_capture_col, state->en_passant_capture_row)
            ) {
                int capture_index = state->board[state->en_passant_capture_row][state->en_passant_capture_col];
                if (
                    capture_index != -1
                    && state->alive[capture_index]
                    && state->piece_type[capture_index] == PIECE_PAWN
                    && state->piece_color[capture_index] != piece_color
                    && state->en_passant_capture_col == capture_col
                    && state->en_passant_capture_row == row
                ) {
                    append_move(list, col, row, capture_col, capture_row, -1);
                }
            }
        }
        return;
    }

    if (piece_type == PIECE_KNIGHT) {
        static const int offsets[8][2] = {
            {-2, -1}, {-2, 1}, {-1, -2}, {-1, 2},
            {1, -2}, {1, 2}, {2, -1}, {2, 1},
        };
        for (int i = 0; i < 8; i++) {
            int to_col = col + offsets[i][0];
            int to_row = row + offsets[i][1];
            if (!is_inside(to_col, to_row)) {
                continue;
            }
            int target_index = state->board[to_row][to_col];
            if (target_index == -1 || state->piece_color[target_index] != piece_color) {
                append_move(list, col, row, to_col, to_row, -1);
            }
        }
        return;
    }

    if (piece_type == PIECE_BISHOP || piece_type == PIECE_ROOK || piece_type == PIECE_QUEEN) {
        static const int bishop_dirs[4][2] = {{-1, -1}, {-1, 1}, {1, -1}, {1, 1}};
        static const int rook_dirs[4][2] = {{-1, 0}, {1, 0}, {0, -1}, {0, 1}};

        if (piece_type == PIECE_BISHOP || piece_type == PIECE_QUEEN) {
            for (int i = 0; i < 4; i++) {
                int to_col = col + bishop_dirs[i][0];
                int to_row = row + bishop_dirs[i][1];
                while (is_inside(to_col, to_row)) {
                    int target_index = state->board[to_row][to_col];
                    if (target_index == -1) {
                        append_move(list, col, row, to_col, to_row, -1);
                    } else {
                        if (state->piece_color[target_index] != piece_color) {
                            append_move(list, col, row, to_col, to_row, -1);
                        }
                        break;
                    }
                    to_col += bishop_dirs[i][0];
                    to_row += bishop_dirs[i][1];
                }
            }
        }

        if (piece_type == PIECE_ROOK || piece_type == PIECE_QUEEN) {
            for (int i = 0; i < 4; i++) {
                int to_col = col + rook_dirs[i][0];
                int to_row = row + rook_dirs[i][1];
                while (is_inside(to_col, to_row)) {
                    int target_index = state->board[to_row][to_col];
                    if (target_index == -1) {
                        append_move(list, col, row, to_col, to_row, -1);
                    } else {
                        if (state->piece_color[target_index] != piece_color) {
                            append_move(list, col, row, to_col, to_row, -1);
                        }
                        break;
                    }
                    to_col += rook_dirs[i][0];
                    to_row += rook_dirs[i][1];
                }
            }
        }
        return;
    }

    if (piece_type == PIECE_KING) {
        for (int d_col = -1; d_col <= 1; d_col++) {
            for (int d_row = -1; d_row <= 1; d_row++) {
                if (d_col == 0 && d_row == 0) {
                    continue;
                }
                int to_col = col + d_col;
                int to_row = row + d_row;
                if (!is_inside(to_col, to_row)) {
                    continue;
                }
                int target_index = state->board[to_row][to_col];
                if (target_index == -1 || state->piece_color[target_index] != piece_color) {
                    append_move(list, col, row, to_col, to_row, -1);
                }
            }
        }

        if (!state->piece_moved[piece_index]) {
            int home_row = piece_color == 0 ? 0 : 7;
            if (col == 4 && row == home_row) {
                int kingside_rook = state->board[home_row][7];
                if (
                    kingside_rook != -1
                    && state->alive[kingside_rook]
                    && state->piece_type[kingside_rook] == PIECE_ROOK
                    && state->piece_color[kingside_rook] == piece_color
                    && !state->piece_moved[kingside_rook]
                    && state->board[home_row][5] == -1
                    && state->board[home_row][6] == -1
                ) {
                    append_move(list, 4, home_row, 6, home_row, -1);
                }

                int queenside_rook = state->board[home_row][0];
                if (
                    queenside_rook != -1
                    && state->alive[queenside_rook]
                    && state->piece_type[queenside_rook] == PIECE_ROOK
                    && state->piece_color[queenside_rook] == piece_color
                    && !state->piece_moved[queenside_rook]
                    && state->board[home_row][1] == -1
                    && state->board[home_row][2] == -1
                    && state->board[home_row][3] == -1
                ) {
                    append_move(list, 4, home_row, 2, home_row, -1);
                }
            }
        }
    }
}

static void generate_legal_moves_for_color(const SearchState* state, int color, MoveList* list) {
    list->count = 0;
    for (int i = 0; i < state->piece_count; i++) {
        if (!state->alive[i] || state->piece_color[i] != color) {
            continue;
        }
        generate_moves_for_piece(state, i, list);
    }
}

static int apply_move(SearchState* state, const Move* move) {
    if (!is_inside(move->from_col, move->from_row) || !is_inside(move->to_col, move->to_row)) {
        return 0;
    }

    int piece_index = state->board[move->from_row][move->from_col];
    if (piece_index == -1 || !state->alive[piece_index]) {
        return 0;
    }

    int piece_type = state->piece_type[piece_index];
    int piece_color = state->piece_color[piece_index];
    int target_index = state->board[move->to_row][move->to_col];
    int is_capture = target_index != -1;
    int is_pawn_move = piece_type == PIECE_PAWN;

    int is_en_passant_capture = (
        is_pawn_move
        && target_index == -1
        && move->from_col != move->to_col
        && state->en_passant_target_col == move->to_col
        && state->en_passant_target_row == move->to_row
        && is_inside(state->en_passant_capture_col, state->en_passant_capture_row)
    );

    if (is_en_passant_capture) {
        int capture_index = state->board[state->en_passant_capture_row][state->en_passant_capture_col];
        if (
            capture_index == -1
            || !state->alive[capture_index]
            || state->piece_type[capture_index] != PIECE_PAWN
            || state->piece_color[capture_index] == piece_color
        ) {
            return 0;
        }
        state->alive[capture_index] = 0;
        state->board[state->en_passant_capture_row][state->en_passant_capture_col] = -1;
        is_capture = 1;
    } else if (target_index != -1) {
        if (!state->alive[target_index] || state->piece_color[target_index] == piece_color) {
            return 0;
        }
        state->alive[target_index] = 0;
        state->board[move->to_row][move->to_col] = -1;
    }

    state->board[move->from_row][move->from_col] = -1;
    state->board[move->to_row][move->to_col] = piece_index;
    state->piece_col[piece_index] = move->to_col;
    state->piece_row[piece_index] = move->to_row;

    if (is_pawn_move && (move->to_row == 0 || move->to_row == 7)) {
        state->piece_type[piece_index] = move->promotion_type >= PIECE_PAWN ? move->promotion_type : PIECE_QUEEN;
    }

    if (piece_type == PIECE_KING && (move->to_col - move->from_col == 2 || move->to_col - move->from_col == -2)) {
        int home_row = move->from_row;
        if (move->to_col > move->from_col) {
            int rook_index = state->board[home_row][7];
            if (rook_index != -1 && state->alive[rook_index] && state->piece_type[rook_index] == PIECE_ROOK) {
                state->board[home_row][7] = -1;
                state->board[home_row][5] = rook_index;
                state->piece_col[rook_index] = 5;
                state->piece_row[rook_index] = home_row;
                state->piece_moved[rook_index] = 1;
            }
        } else {
            int rook_index = state->board[home_row][0];
            if (rook_index != -1 && state->alive[rook_index] && state->piece_type[rook_index] == PIECE_ROOK) {
                state->board[home_row][0] = -1;
                state->board[home_row][3] = rook_index;
                state->piece_col[rook_index] = 3;
                state->piece_row[rook_index] = home_row;
                state->piece_moved[rook_index] = 1;
            }
        }
    }

    state->piece_moved[piece_index] = 1;

    state->en_passant_target_col = -1;
    state->en_passant_target_row = -1;
    state->en_passant_capture_col = -1;
    state->en_passant_capture_row = -1;
    if (piece_type == PIECE_PAWN && (move->to_row - move->from_row == 2 || move->to_row - move->from_row == -2)) {
        state->en_passant_target_col = move->from_col;
        state->en_passant_target_row = (move->from_row + move->to_row) / 2;
        state->en_passant_capture_col = move->to_col;
        state->en_passant_capture_row = move->to_row;
    }

    if (is_pawn_move || is_capture) {
        state->halfmove_clock = 0;
    } else {
        state->halfmove_clock += 1;
    }

    return 1;
}

static int is_backward_pawn_state(const SearchState* state, int pawn_index) {
    if (!state->alive[pawn_index] || state->piece_type[pawn_index] != PIECE_PAWN) {
        return 0;
    }

    int pawn_color = state->piece_color[pawn_index];
    int pawn_col = state->piece_col[pawn_index];
    int pawn_row = state->piece_row[pawn_index];
    int direction = pawn_color == 0 ? 1 : -1;
    int forward_row = pawn_row + direction;
    if (!is_inside(pawn_col, forward_row)) {
        return 0;
    }

    for (int delta = -1; delta <= 1; delta += 2) {
        int adjacent_col = pawn_col + delta;
        if (adjacent_col < 0 || adjacent_col > 7) {
            continue;
        }

        for (int i = 0; i < state->piece_count; i++) {
            if (!state->alive[i]) {
                continue;
            }
            if (
                state->piece_type[i] != PIECE_PAWN
                || state->piece_color[i] != pawn_color
                || state->piece_col[i] != adjacent_col
            ) {
                continue;
            }

            if (pawn_color == 0 && state->piece_row[i] >= pawn_row) {
                return 0;
            }
            if (pawn_color == 1 && state->piece_row[i] <= pawn_row) {
                return 0;
            }
        }
    }

    int opposing_color = opponent_color(pawn_color);
    for (int i = 0; i < state->piece_count; i++) {
        if (!state->alive[i]) {
            continue;
        }
        if (state->piece_type[i] != PIECE_PAWN || state->piece_color[i] != opposing_color) {
            continue;
        }

        int attack_row = state->piece_row[i] + (opposing_color == 0 ? 1 : -1);
        if (attack_row != forward_row) {
            continue;
        }
        if (state->piece_col[i] - 1 == pawn_col || state->piece_col[i] + 1 == pawn_col) {
            return 1;
        }
    }

    return 0;
}

static int has_opposite_color_bishops_state(const SearchState* state) {
    int white_bishop_index = -1;
    int black_bishop_index = -1;
    int white_count = 0;
    int black_count = 0;

    for (int i = 0; i < state->piece_count; i++) {
        if (!state->alive[i] || state->piece_type[i] != PIECE_BISHOP) {
            continue;
        }
        if (state->piece_color[i] == 0) {
            white_count += 1;
            white_bishop_index = i;
        } else {
            black_count += 1;
            black_bishop_index = i;
        }
    }

    if (white_count != 1 || black_count != 1) {
        return 0;
    }

    int white_square_color = (state->piece_col[white_bishop_index] + state->piece_row[white_bishop_index]) % 2;
    int black_square_color = (state->piece_col[black_bishop_index] + state->piece_row[black_bishop_index]) % 2;
    return white_square_color != black_square_color;
}

static double control_score(const SearchState* state, int perspective_color, const EvalParams* params) {
    double total = 0.0;
    for (int i = 0; i < state->piece_count; i++) {
        if (!state->alive[i]) {
            continue;
        }

        MoveList moves;
        moves.count = 0;
        generate_moves_for_piece(state, i, &moves);

        double controlled = 0.0;
        int piece_type = state->piece_type[i];
        for (int j = 0; j < moves.count; j++) {
            controlled += square_weight_for_piece(
                piece_type,
                moves.entries[j].to_col,
                moves.entries[j].to_row,
                params->position_multipliers,
                params->has_position_multipliers
            );
        }

        if (state->piece_color[i] == perspective_color) {
            total += controlled;
        } else {
            total -= controlled;
        }
    }
    return total;
}

static Score evaluate_state(const SearchState* state, int perspective_color, const EvalParams* params) {
    Score score;
    score.material = 0.0;
    score.heuristic = 0.0;

    for (int i = 0; i < state->piece_count; i++) {
        if (!state->alive[i]) {
            continue;
        }

        int piece_type = state->piece_type[i];
        int piece_color = state->piece_color[i];
        int piece_col = state->piece_col[i];
        int piece_row = state->piece_row[i];

        double material_score = params->piece_values[piece_type];
        double piece_score = material_score;

        if (piece_type == PIECE_PAWN) {
            if (params->has_pawn_rank_values && params->pawn_rank_values != NULL) {
                int pawn_rank = piece_color == 0 ? piece_row + 1 : 8 - piece_row;
                double rank_score = params->pawn_rank_values[pawn_rank];
                if (rank_score > piece_score) {
                    piece_score = rank_score;
                }
            }
            if (params->has_backward_pawn_value && is_backward_pawn_state(state, i) && params->backward_pawn_value < piece_score) {
                piece_score = params->backward_pawn_value;
            }
        }

        piece_score *= square_weight_for_piece(
            piece_type,
            piece_col,
            piece_row,
            params->position_multipliers,
            params->has_position_multipliers
        );
        double heuristic_score = piece_score - material_score;

        if (piece_color == perspective_color) {
            score.material += material_score;
            score.heuristic += heuristic_score;
        } else {
            score.material -= material_score;
            score.heuristic -= heuristic_score;
        }
    }

    if (params->control_weight != 0.0) {
        score.heuristic += params->control_weight * control_score(state, perspective_color, params);
    }

    if (params->has_opposite_bishop_draw_factor && has_opposite_color_bishops_state(state)) {
        score.heuristic *= params->opposite_bishop_draw_factor;
    }

    return score;
}

static uint64_t hash_mix(uint64_t hash, uint64_t value) {
    hash ^= value + 0x9e3779b97f4a7c15ULL + (hash << 6) + (hash >> 2);
    return hash;
}

static uint64_t hash_state(const SearchState* state, int active_color, int remaining_plies) {
    uint64_t hash = 1469598103934665603ULL;
    for (int row = 0; row < 8; row++) {
        for (int col = 0; col < 8; col++) {
            int piece_index = state->board[row][col];
            if (piece_index == -1 || !state->alive[piece_index]) {
                hash = hash_mix(hash, 0ULL);
                continue;
            }
            uint64_t piece_bits = (uint64_t)state->piece_type[piece_index]
                | ((uint64_t)state->piece_color[piece_index] << 3)
                | ((uint64_t)(state->piece_moved[piece_index] ? 1 : 0) << 4)
                | ((uint64_t)col << 8)
                | ((uint64_t)row << 16);
            hash = hash_mix(hash, piece_bits + 1ULL);
        }
    }

    uint64_t en_passant_bits = (uint64_t)(state->en_passant_target_col + 1)
        | ((uint64_t)(state->en_passant_target_row + 1) << 4)
        | ((uint64_t)(state->en_passant_capture_col + 1) << 8)
        | ((uint64_t)(state->en_passant_capture_row + 1) << 12);
    hash = hash_mix(hash, en_passant_bits);
    hash = hash_mix(hash, (uint64_t)state->halfmove_clock);
    hash = hash_mix(hash, (uint64_t)active_color);
    hash = hash_mix(hash, (uint64_t)remaining_plies);
    return hash;
}

static int cache_lookup(
    const SearchCache* cache,
    uint64_t key,
    int active_color,
    int remaining_plies,
    Score* out_score
) {
    if (cache == NULL || cache->entries == NULL || cache->capacity == 0) {
        return 0;
    }

    size_t index = (size_t)(key & (uint64_t)(cache->capacity - 1));
    const CacheEntry* entry = &cache->entries[index];
    if (
        !entry->valid
        || entry->key != key
        || entry->active_color != active_color
        || entry->remaining_plies != remaining_plies
    ) {
        return 0;
    }

    out_score->material = entry->material;
    out_score->heuristic = entry->heuristic;
    return 1;
}

static void cache_store(
    SearchCache* cache,
    uint64_t key,
    int active_color,
    int remaining_plies,
    Score score
) {
    if (cache == NULL || cache->entries == NULL || cache->capacity == 0) {
        return;
    }

    size_t index = (size_t)(key & (uint64_t)(cache->capacity - 1));
    CacheEntry* entry = &cache->entries[index];
    entry->valid = 1;
    entry->key = key;
    entry->active_color = active_color;
    entry->remaining_plies = remaining_plies;
    entry->material = score.material;
    entry->heuristic = score.heuristic;
}

void* create_search_cache_c(size_t max_bytes) {
    if (max_bytes < sizeof(CacheEntry) * 2) {
        return NULL;
    }

    SearchCache* cache = (SearchCache*)malloc(sizeof(SearchCache));
    if (cache == NULL) {
        return NULL;
    }

    size_t capacity = max_bytes / sizeof(CacheEntry);
    size_t pow2_capacity = 1;
    while (pow2_capacity <= capacity / 2) {
        pow2_capacity <<= 1;
    }

    while (pow2_capacity >= 2) {
        CacheEntry* entries = (CacheEntry*)calloc(pow2_capacity, sizeof(CacheEntry));
        if (entries != NULL) {
            cache->capacity = pow2_capacity;
            cache->entries = entries;
            return (void*)cache;
        }
        pow2_capacity >>= 1;
    }

    free(cache);
    return NULL;
}

void destroy_search_cache_c(void* cache_ptr) {
    if (cache_ptr == NULL) {
        return;
    }
    SearchCache* cache = (SearchCache*)cache_ptr;
    free(cache->entries);
    cache->entries = NULL;
    cache->capacity = 0;
    free(cache);
}

enum {
    STATUS_IN_PROGRESS = 0,
    STATUS_DRAW = 1,
    STATUS_WIN = 2,
};

static int get_game_status_state(const SearchState* state, int active_color, int* winner) {
    int white_king_found = 0;
    int black_king_found = 0;
    for (int i = 0; i < state->piece_count; i++) {
        if (!state->alive[i] || state->piece_type[i] != PIECE_KING) {
            continue;
        }
        if (state->piece_color[i] == 0) {
            white_king_found = 1;
        } else {
            black_king_found = 1;
        }
    }

    if (!white_king_found && !black_king_found) {
        *winner = -1;
        return STATUS_DRAW;
    }
    if (!white_king_found) {
        *winner = 1;
        return STATUS_WIN;
    }
    if (!black_king_found) {
        *winner = 0;
        return STATUS_WIN;
    }

    if (state->halfmove_clock >= 100) {
        *winner = -1;
        return STATUS_DRAW;
    }

    MoveList legal_moves;
    generate_legal_moves_for_color(state, active_color, &legal_moves);
    if (legal_moves.count == 0) {
        *winner = -1;
        return STATUS_DRAW;
    }

    *winner = -1;
    return STATUS_IN_PROGRESS;
}

static Score minimax_score_state(
    const SearchState* state,
    int active_color,
    int perspective_color,
    int remaining_plies,
    const EvalParams* params,
    SearchCache* cache
) {
    uint64_t key = hash_state(state, active_color, remaining_plies);
    Score cached_score;
    if (cache_lookup(cache, key, active_color, remaining_plies, &cached_score)) {
        return cached_score;
    }

    int winner = -1;
    int state_status = get_game_status_state(state, active_color, &winner);
    if (state_status == STATUS_WIN) {
        Score score = score_for_winner(winner, perspective_color);
        cache_store(cache, key, active_color, remaining_plies, score);
        return score;
    }
    if (state_status == STATUS_DRAW) {
        Score score = draw_score();
        cache_store(cache, key, active_color, remaining_plies, score);
        return score;
    }
    if (remaining_plies <= 0) {
        Score score = evaluate_state(state, perspective_color, params);
        cache_store(cache, key, active_color, remaining_plies, score);
        return score;
    }

    MoveList legal_moves;
    generate_legal_moves_for_color(state, active_color, &legal_moves);
    if (legal_moves.count == 0) {
        Score score = draw_score();
        cache_store(cache, key, active_color, remaining_plies, score);
        return score;
    }

    int next_color = opponent_color(active_color);
    if (active_color == perspective_color) {
        Score best;
        best.material = -1e300;
        best.heuristic = -1e300;
        for (int i = 0; i < legal_moves.count; i++) {
            SearchState child = *state;
            if (!apply_move(&child, &legal_moves.entries[i])) {
                continue;
            }
            Score current = minimax_score_state(&child, next_color, perspective_color, remaining_plies - 1, params, cache);
            if (compare_score(current, best) > 0) {
                best = current;
            }
        }
        cache_store(cache, key, active_color, remaining_plies, best);
        return best;
    }

    Score best;
    best.material = 1e300;
    best.heuristic = 1e300;
    for (int i = 0; i < legal_moves.count; i++) {
        SearchState child = *state;
        if (!apply_move(&child, &legal_moves.entries[i])) {
            continue;
        }
        Score current = minimax_score_state(&child, next_color, perspective_color, remaining_plies - 1, params, cache);
        if (compare_score(current, best) < 0) {
            best = current;
        }
    }
    cache_store(cache, key, active_color, remaining_plies, best);
    return best;
}

int evaluate_piece_components_c(
    const int* piece_types,
    const int* piece_colors,
    const int* piece_cols,
    const int* piece_rows,
    int piece_count,
    int perspective_color,
    const double* piece_values,
    const double* pawn_rank_values,
    int has_pawn_rank_values,
    double backward_pawn_value,
    int has_backward_pawn_value,
    const double* position_multipliers,
    int has_position_multipliers,
    double* out_material,
    double* out_heuristic
) {
    if (
        piece_types == NULL
        || piece_colors == NULL
        || piece_cols == NULL
        || piece_rows == NULL
        || piece_values == NULL
        || out_material == NULL
        || out_heuristic == NULL
    ) {
        return 0;
    }

    SearchState state;
    if (!init_state(
        &state,
        piece_types,
        piece_colors,
        piece_cols,
        piece_rows,
        NULL,
        piece_count,
        -1,
        -1,
        -1,
        -1,
        0
    )) {
        return 0;
    }

    EvalParams params;
    params.piece_values = piece_values;
    params.pawn_rank_values = pawn_rank_values;
    params.has_pawn_rank_values = has_pawn_rank_values;
    params.backward_pawn_value = backward_pawn_value;
    params.has_backward_pawn_value = has_backward_pawn_value;
    params.position_multipliers = position_multipliers;
    params.has_position_multipliers = has_position_multipliers;
    params.control_weight = 0.0;
    params.opposite_bishop_draw_factor = 1.0;
    params.has_opposite_bishop_draw_factor = 0;

    Score score = evaluate_state(&state, perspective_color, &params);
    *out_material = score.material;
    *out_heuristic = score.heuristic;
    return 1;
}

int choose_best_move_c(
    const int* piece_types,
    const int* piece_colors,
    const int* piece_cols,
    const int* piece_rows,
    const int* piece_moved,
    int piece_count,
    int active_color,
    int plies,
    const double* piece_values,
    const double* pawn_rank_values,
    int has_pawn_rank_values,
    double backward_pawn_value,
    int has_backward_pawn_value,
    const double* position_multipliers,
    int has_position_multipliers,
    double control_weight,
    double opposite_bishop_draw_factor,
    int has_opposite_bishop_draw_factor,
    int en_passant_target_col,
    int en_passant_target_row,
    int en_passant_capture_col,
    int en_passant_capture_row,
    int halfmove_clock,
    int* out_from_col,
    int* out_from_row,
    int* out_to_col,
    int* out_to_row,
    void* cache_ptr
) {
    if (
        piece_types == NULL
        || piece_colors == NULL
        || piece_cols == NULL
        || piece_rows == NULL
        || piece_moved == NULL
        || piece_values == NULL
        || out_from_col == NULL
        || out_from_row == NULL
        || out_to_col == NULL
        || out_to_row == NULL
    ) {
        return 0;
    }

    if (active_color != 0 && active_color != 1) {
        return 0;
    }

    SearchCache* cache = (SearchCache*)cache_ptr;

    SearchState root;
    if (!init_state(
        &root,
        piece_types,
        piece_colors,
        piece_cols,
        piece_rows,
        piece_moved,
        piece_count,
        en_passant_target_col,
        en_passant_target_row,
        en_passant_capture_col,
        en_passant_capture_row,
        halfmove_clock
    )) {
        return 0;
    }

    MoveList legal_moves;
    generate_legal_moves_for_color(&root, active_color, &legal_moves);
    if (legal_moves.count == 0) {
        return 2;
    }

    EvalParams params;
    params.piece_values = piece_values;
    params.pawn_rank_values = pawn_rank_values;
    params.has_pawn_rank_values = has_pawn_rank_values;
    params.backward_pawn_value = backward_pawn_value;
    params.has_backward_pawn_value = has_backward_pawn_value;
    params.position_multipliers = position_multipliers;
    params.has_position_multipliers = has_position_multipliers;
    params.control_weight = control_weight;
    params.opposite_bishop_draw_factor = opposite_bishop_draw_factor;
    params.has_opposite_bishop_draw_factor = has_opposite_bishop_draw_factor;

    int next_color = opponent_color(active_color);
    Score best_score;
    best_score.material = -1e300;
    best_score.heuristic = -1e300;
    int best_index = 0;

    for (int i = 0; i < legal_moves.count; i++) {
        SearchState child = root;
        if (!apply_move(&child, &legal_moves.entries[i])) {
            continue;
        }
        Score score = minimax_score_state(&child, next_color, active_color, plies - 1, &params, cache);
        if (compare_score(score, best_score) > 0) {
            best_score = score;
            best_index = i;
        }
    }

    *out_from_col = legal_moves.entries[best_index].from_col;
    *out_from_row = legal_moves.entries[best_index].from_row;
    *out_to_col = legal_moves.entries[best_index].to_col;
    *out_to_row = legal_moves.entries[best_index].to_row;
    return 1;
}
