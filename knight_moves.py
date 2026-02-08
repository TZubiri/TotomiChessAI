def get_legal_knight_moves(position):
    """
    Returns all legal knight moves from the given position.
    
    Args:
        position (str): Chess position in algebraic notation (e.g., 'e4')
    
    Returns:
        list: List of legal positions the knight can move to
    """
    if len(position) != 2 or position[0] not in 'abcdefgh' or position[1] not in '12345678':
        return []
    
    col = ord(position[0]) - ord('a')  # 0-7
    row = int(position[1]) - 1        # 0-7
    
    # All possible knight move offsets
    knight_moves = [
        (2, 1), (2, -1), (-2, 1), (-2, -1),
        (1, 2), (1, -2), (-1, 2), (-1, -2)
    ]
    
    legal_moves = []
    
    for col_offset, row_offset in knight_moves:
        new_col = col + col_offset
        new_row = row + row_offset
        
        # Check if position is within board bounds
        if 0 <= new_col <= 7 and 0 <= new_row <= 7:
            new_position = chr(new_col + ord('a')) + str(new_row + 1)
            legal_moves.append(new_position)
    
    return legal_moves

# Example usage
if __name__ == "__main__":
    print(get_legal_knight_moves('e4'))  # ['f6', 'd6', 'g5', 'c5', 'g3', 'c3', 'f2', 'd2']