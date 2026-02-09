#include <stddef.h>

enum {
    PIECE_PAWN = 0,
    PIECE_KNIGHT = 1,
    PIECE_BISHOP = 2,
    PIECE_ROOK = 3,
    PIECE_QUEEN = 4,
    PIECE_KING = 5
};

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

static int is_backward_pawn(
    int pawn_color,
    int pawn_col,
    int pawn_row,
    const int* piece_types,
    const int* piece_colors,
    const int* piece_cols,
    const int* piece_rows,
    int piece_count
) {
    int direction = pawn_color == 0 ? 1 : -1;
    int forward_row = pawn_row + direction;
    if (forward_row < 0 || forward_row > 7) {
        return 0;
    }

    for (int delta = -1; delta <= 1; delta += 2) {
        int adjacent_col = pawn_col + delta;
        if (adjacent_col < 0 || adjacent_col > 7) {
            continue;
        }

        for (int i = 0; i < piece_count; i++) {
            if (piece_types[i] != PIECE_PAWN || piece_colors[i] != pawn_color || piece_cols[i] != adjacent_col) {
                continue;
            }
            if (pawn_color == 0 && piece_rows[i] >= pawn_row) {
                return 0;
            }
            if (pawn_color == 1 && piece_rows[i] <= pawn_row) {
                return 0;
            }
        }
    }

    int opponent_color = pawn_color == 0 ? 1 : 0;
    for (int i = 0; i < piece_count; i++) {
        if (piece_types[i] != PIECE_PAWN || piece_colors[i] != opponent_color) {
            continue;
        }

        int attack_row = piece_rows[i] + (opponent_color == 0 ? 1 : -1);
        if (attack_row != forward_row) {
            continue;
        }
        if (piece_cols[i] - 1 == pawn_col || piece_cols[i] + 1 == pawn_col) {
            return 1;
        }
    }

    return 0;
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
    if (piece_count < 0 || out_material == NULL || out_heuristic == NULL || piece_values == NULL) {
        return 0;
    }

    *out_material = 0.0;
    *out_heuristic = 0.0;
    for (int i = 0; i < piece_count; i++) {
        int piece_type = piece_types[i];
        int piece_color = piece_colors[i];
        int piece_col = piece_cols[i];
        int piece_row = piece_rows[i];

        if (piece_type < PIECE_PAWN || piece_type > PIECE_KING) {
            return 0;
        }

        double material_score = piece_values[piece_type];
        double piece_score = material_score;

        if (piece_type == PIECE_PAWN) {
            if (has_pawn_rank_values && pawn_rank_values != NULL) {
                int pawn_rank = piece_color == 0 ? piece_row + 1 : 8 - piece_row;
                double rank_score = pawn_rank_values[pawn_rank];
                if (rank_score > piece_score) {
                    piece_score = rank_score;
                }
            }
            if (
                has_backward_pawn_value
                && is_backward_pawn(piece_color, piece_col, piece_row, piece_types, piece_colors, piece_cols, piece_rows, piece_count)
                && backward_pawn_value < piece_score
            ) {
                piece_score = backward_pawn_value;
            }
        }

        piece_score *= square_weight_for_piece(piece_type, piece_col, piece_row, position_multipliers, has_position_multipliers);
        double heuristic_score = piece_score - material_score;

        if (piece_color == perspective_color) {
            *out_material += material_score;
            *out_heuristic += heuristic_score;
        } else {
            *out_material -= material_score;
            *out_heuristic -= heuristic_score;
        }
    }

    return 1;
}
