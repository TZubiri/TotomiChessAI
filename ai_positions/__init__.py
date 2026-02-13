import importlib
from functools import lru_cache


POSITION_TABLE_ORDER = (
    "pawn",
    "knight",
    "bishop_white",
    "bishop_black",
    "rook",
    "queen",
    "king",
)
PHASE_ORDER = ("opening", "endgame")
BITMAP_SQUARE_COUNT = 64
BITMAP_ROW_COUNT = 8
BITMAP_ROW_WIDTH = 8
BITMAP_BASE53_ALPHABET = "abcdefghijklmnopqrstuvwxyz-ABCDEFGHIJKLMNOPQRSTUVWXYZ"
BITMAP_BASE53_LOOKUP = {char: index for index, char in enumerate(BITMAP_BASE53_ALPHABET)}


def _parse_ascii_base53_rows(bitmap_rows, module_name, phase_name, piece_type):
    if isinstance(bitmap_rows, str):
        rows = [line.strip() for line in bitmap_rows.splitlines() if line.strip()]
    else:
        rows = list(bitmap_rows)

    if len(rows) != BITMAP_ROW_COUNT:
        raise ValueError(
            f"Bitmap for '{piece_type}' in {module_name} ({phase_name}) must have {BITMAP_ROW_COUNT} rows"
        )

    values = []
    for row_index, row_text in enumerate(rows):
        if not isinstance(row_text, str):
            raise ValueError(
                f"Bitmap row {row_index} for '{piece_type}' in {module_name} ({phase_name}) must be a string"
            )

        compact_row = row_text.strip()
        if len(compact_row) != BITMAP_ROW_WIDTH:
            raise ValueError(
                f"Bitmap row {row_index} for '{piece_type}' in {module_name} ({phase_name}) must be 8 characters"
            )

        for char_index, cell_char in enumerate(compact_row):
            if cell_char not in BITMAP_BASE53_LOOKUP:
                raise ValueError(
                    f"Invalid bitmap character '{cell_char}' at row {row_index}, col {char_index} "
                    f"for '{piece_type}' in {module_name} ({phase_name})"
                )
            values.append(BITMAP_BASE53_LOOKUP[cell_char])

    return bytes(values)


def _normalize_bitmap_payload(bitmap_payload, module_name, phase_name, piece_type):
    if isinstance(bitmap_payload, (bytes, bytearray)):
        bitmap = bytes(bitmap_payload)
        if len(bitmap) != BITMAP_SQUARE_COUNT:
            raise ValueError(
                f"Bitmap for '{piece_type}' in {module_name} ({phase_name}) must have {BITMAP_SQUARE_COUNT} entries"
            )
        if any(cell_value >= len(BITMAP_BASE53_ALPHABET) for cell_value in bitmap):
            raise ValueError(
                f"Bitmap for '{piece_type}' in {module_name} ({phase_name}) contains values outside base53 range"
            )
        return bitmap

    if isinstance(bitmap_payload, str) or isinstance(bitmap_payload, (list, tuple)):
        return _parse_ascii_base53_rows(bitmap_payload, module_name, phase_name, piece_type)

    raise ValueError(
        f"Bitmap for '{piece_type}' in {module_name} ({phase_name}) must be bytes or 8 rows of base53 characters"
    )


def _normalize_piece_bitmap_mapping(bitmap_mapping, module_name, phase_name):
    if not isinstance(bitmap_mapping, dict):
        raise ValueError(f"Invalid bitmap mapping for phase '{phase_name}' in {module_name}")

    bishop_fallback = bitmap_mapping.get("bishop")

    normalized = []
    for piece_type in POSITION_TABLE_ORDER:
        bitmap_payload = bitmap_mapping.get(piece_type)
        if bitmap_payload is None and piece_type in {"bishop_white", "bishop_black"}:
            bitmap_payload = bishop_fallback
        if bitmap_payload is None:
            raise ValueError(f"Missing '{piece_type}' bitmap for phase '{phase_name}' in {module_name}")
        bitmap = _normalize_bitmap_payload(bitmap_payload, module_name, phase_name, piece_type)
        normalized.append((piece_type, bitmap))
    return tuple(normalized)


@lru_cache(maxsize=None)
def _load_profile_position_bitmaps_cached(profile_id):
    module = importlib.import_module(f"ai_positions.{profile_id}")
    module_name = f"ai_positions.{profile_id}"
    position_bitmaps = getattr(module, "POSITION_BITMAPS", None)
    if not isinstance(position_bitmaps, dict):
        raise ValueError(f"Invalid POSITION_BITMAPS in {module_name}")

    has_explicit_phases = all(phase_name in position_bitmaps for phase_name in PHASE_ORDER)
    if has_explicit_phases:
        return tuple(
            (phase_name, _normalize_piece_bitmap_mapping(position_bitmaps[phase_name], module_name, phase_name))
            for phase_name in PHASE_ORDER
        )

    normalized_single_phase = _normalize_piece_bitmap_mapping(position_bitmaps, module_name, "opening")
    return (
        ("opening", normalized_single_phase),
        ("endgame", normalized_single_phase),
    )


def load_profile_position_bitmaps(profile_id):
    phase_tables = {}
    for phase_name, phase_entries in _load_profile_position_bitmaps_cached(profile_id):
        phase_tables[phase_name] = dict(phase_entries)
    return phase_tables
