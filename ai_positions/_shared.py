NEUTRAL_BITMAP_ROWS = (
    "--------",
    "--------",
    "--------",
    "--------",
    "--------",
    "--------",
    "--------",
    "--------",
)

PAWNWISE_PAWN_BITMAP_ROWS = (
    "--------",
    "-DCww-B-",
    "A-xCC--A",
    "--xFFE--",
    "--EEEE--",
    "LLLLLLLL",
    "ZZZZZZZZ",
    "--------",
)

PAWNWISE_ROOK_BITMAP_ROWS = (
    "xz-BB-zx",
    "z------z",
    "--DHHD--",
    "--EEEE--",
    "--EEEE--",
    "--DEED--",
    "JLLLLLLJ",
    "DKKKKKKD",
)

PAWNWISE_KNIGHT_BITMAP_ROWS = (
    "tv-xx-vt",
    "v---C--v",
    "xDKEED-x",
    "-CFLLFC-",
    "-BFLLFB-",
    "--BDDB--",
    "v------v",
    "tv----vt",
)

PAWNWISE_BISHOP_WHITE_BITMAP_ROWS = (
    "vw----wv",
    "wA----Aw",
    "--DDDD--",
    "--EFFE--",
    "--EFFE--",
    "--DDDD--",
    "wA----Aw",
    "vw----wv",
)

PAWNWISE_BISHOP_BLACK_BITMAP_ROWS = (
    "wv----vw",
    "w----AAw",
    "--DDDD--",
    "--EFFE--",
    "--EFFE--",
    "--DDDD--",
    "wAA----w",
    "wv----vw",
)

PAWNWISE_QUEEN_BITMAP_ROWS = (
    "uw----wu",
    "DDDDDDDD",
    "AAACCAAA",
    "t--BB--t",
    "t------t",
    "--------",
    "CCCCCCCC",
    "AAAAAAAA",
)

PAWNWISE_KING_BITMAP_ROWS = (
    "CGxA-CEB",
    "wvvvvvvw",
    "xwwwwwwx",
    "A------A",
    "A------A",
    "BAAAAAAB",
    "CBBBBBBC",
    "--------",
)


def neutral_piece_bitmaps():
    return {
        "pawn": NEUTRAL_BITMAP_ROWS,
        "knight": NEUTRAL_BITMAP_ROWS,
        "bishop_white": NEUTRAL_BITMAP_ROWS,
        "bishop_black": NEUTRAL_BITMAP_ROWS,
        "rook": NEUTRAL_BITMAP_ROWS,
        "queen": NEUTRAL_BITMAP_ROWS,
        "king": NEUTRAL_BITMAP_ROWS,
    }


def pawnwise_piece_bitmaps():
    return {
        "pawn": PAWNWISE_PAWN_BITMAP_ROWS,
        "knight": PAWNWISE_KNIGHT_BITMAP_ROWS,
        "bishop_white": PAWNWISE_BISHOP_WHITE_BITMAP_ROWS,
        "bishop_black": PAWNWISE_BISHOP_BLACK_BITMAP_ROWS,
        "rook": PAWNWISE_ROOK_BITMAP_ROWS,
        "queen": PAWNWISE_QUEEN_BITMAP_ROWS,
        "king": PAWNWISE_KING_BITMAP_ROWS,
    }


def neutral_phase_bitmaps():
    opening = neutral_piece_bitmaps()
    endgame = neutral_piece_bitmaps()
    return {
        "opening": opening,
        "endgame": endgame,
    }


def pawnwise_phase_bitmaps():
    opening = pawnwise_piece_bitmaps()
    endgame = pawnwise_piece_bitmaps()
    return {
        "opening": opening,
        "endgame": endgame,
    }
