def get_bishop_moves(board, row, col):
    """
    Returns all legal moves for a bishop at position (row, col) on the given board.
    
    Args:
        board: 2D list representing the chessboard (8x8)
        row: Current row of the bishop (0-7)
        col: Current column of the bishop (0-7)
    
    Returns:
        List of tuples representing legal moves (target_row, target_col)
    """
    def is_in_check(board, king_row, king_col):
        """Check if king at (king_row, king_col) is in check."""
        # Check for opponent pawns
        opponent_pawn_row = king_row - 1 if board[king_row][king_col].isupper() else king_row + 1
        if 0 <= opponent_pawn_row < 8:
            if (king_col - 1 >= 0 and board[opponent_pawn_row][king_col - 1] == 'p') or \
               (king_col + 1 < 8 and board[opponent_pawn_row][king_col + 1] == 'p'):
                return True
        
        # Check for opponent knights
        knight_moves = [(2, 1), (2, -1), (-2, 1), (-2, -1), 
                       (1, 2), (1, -2), (-1, 2), (-1, -2)]
        for dr, dc in knight_moves:
            r, c = king_row + dr, king_col + dc
            if 0 <= r < 8 and 0 <= c < 8:
                if board[r][c] == 'n' or board[r][c] == 'N':
                    return True
        
        # Check for opponent king (adjacent squares)
        king_adj_moves = [(1, 0), (-1, 0), (0, 1), (0, -1), 
                         (1, 1), (1, -1), (-1, 1), (-1, -1)]
        for dr, dc in king_adj_moves:
            r, c = king_row + dr, king_col + dc
            if 0 <= r < 8 and 0 <= c < 8:
                if board[r][c].lower() == 'k':
                    return True
        
        # Check for opponent bishops and queens (diagonals)
        directions = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
        for dr, dc in directions:
            r, c = king_row + dr, king_col + dc
            while 0 <= r < 8 and 0 <= c < 8:
                if board[r][c] != '':
                    if (board[r][c] == 'b' or board[r][c] == 'q') and board[r][c].islower():
                        return True
                    elif (board[r][c] == 'B' or board[r][c] == 'Q') and board[r][c].isupper():
                        return True
                    break
                r += dr
                c += dc
        
        # Check for opponent rooks and queens (ranks/files)
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        for dr, dc in directions:
            r, c = king_row + dr, king_col + dc
            while 0 <= r < 8 and 0 <= c < 8:
                if board[r][c] != '':
                    if (board[r][c] == 'r' or board[r][c] == 'q') and board[r][c].islower():
                        return True
                    elif (board[r][c] == 'R' or board[r][c] == 'Q') and board[r][c].isupper():
                        return True
                    break
                r += dr
                c += dc
        
        return False
    
    def find_king(board, is_white):
        """Find the king of the given color."""
        king_symbol = 'K' if is_white else 'k'
        for r in range(8):
            for c in range(8):
                if board[r][c] == king_symbol:
                    return (r, c)
        return None
    
    moves = []
    directions = [(-1, -1), (-1, 1), (1, -1), (1, 1)]  # 4 diagonal directions
    
    # Find the king of the same color as the bishop
    is_white = board[row][col].isupper()
    king_pos = find_king(board, is_white)
    
    if king_pos is None:
        return []  # No king found, return no moves
    
    for dr, dc in directions:
        r, c = row + dr, col + dc
        
        while 0 <= r < 8 and 0 <= c < 8:
            # Empty square - can move here
            if board[r][c] == '':
                # Temporarily move bishop to test for check
                board[row][col] = ''
                board[r][c] = 'B' if is_white else 'b'
                
                if not is_in_check(board, king_pos[0], king_pos[1]):
                    moves.append((r, c))
                
                # Undo the move
                board[r][c] = ''
                board[row][col] = 'B' if is_white else 'b'
            
            # Square with opponent piece - can move here and stop
            elif board[r][c].islower() if is_white else board[r][c].isupper():
                # Temporarily move bishop to test for check
                board[row][col] = ''
                board[r][c] = 'B' if is_white else 'b'
                
                if not is_in_check(board, king_pos[0], king_pos[1]):
                    moves.append((r, c))
                
                # Undo the move
                board[r][c] = ''
                board[row][col] = 'B' if is_white else 'b'
                break
            
            # Square with own piece - cannot move here, stop
            else:
                break
            
            r += dr
            c += dc
    
    return moves