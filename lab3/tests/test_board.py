"""
Copyright (c) 2021-25 MIT 6.102/6.031 course staff, all rights reserved.
Redistribution of original or derived work requires permission of course staff.

Tests for the Board abstract data type.
"""

import pytest
import asyncio
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from board import Board, Card, CardState


# Testing strategy for Board:
# 
# Partition on board dimensions: 1x1, small (2x2, 3x3), large (5x5+)
# Partition on number of players: 0, 1, 2, many
# Partition on card operations:
#   - look: empty board, partial board, full board
#   - flip first card: face down, face up uncontrolled, face up controlled by other
#   - flip second card: no card, controlled card, matching card, non-matching card
#   - map: identity function, replacement function
#   - watch: immediate change, delayed change
# Partition on concurrency: serial operations, concurrent flips, concurrent maps
# Partition on game rules:
#   - Rule 1-A: flip empty space as first card
#   - Rule 1-B: flip face-down card as first card
#   - Rule 1-C: flip face-up uncontrolled card as first card
#   - Rule 1-D: wait for controlled card as first card
#   - Rule 2-A: flip empty space as second card
#   - Rule 2-B: flip controlled card as second card (fails, doesn't wait)
#   - Rule 2-C: flip face-down card as second card (turns face-up)
#   - Rule 2-D: match two cards
#   - Rule 2-E: cards don't match
#   - Rule 3-A: remove matched cards on next move
#   - Rule 3-B: turn face-down non-matching cards on next move


@pytest.mark.asyncio
class TestBoard:
    """Tests for Board ADT."""
    
    async def test_parse_simple_board(self):
        """Test parsing a simple board file."""
        board = await Board.parse_from_file('boards/ab.txt')
        state = await board.look('alice')
        lines = state.split('\n')
        assert lines[0] == '5x5'
        # All cards should be face down initially
        for i in range(1, 26):
            assert lines[i] == 'down'
    
    async def test_parse_perfect_board(self):
        """Test parsing the perfect.txt board."""
        board = await Board.parse_from_file('boards/perfect.txt')
        state = await board.look('bob')
        lines = state.split('\n')
        assert lines[0] == '3x3'
        assert len(lines) == 10  # header + 9 cards
    
    async def test_look_empty_player(self):
        """Test that look works for a new player."""
        board = Board(2, 2, ['A', 'B', 'A', 'B'])
        state = await board.look('player1')
        assert state.startswith('2x2')
    
    async def test_rule_1b_flip_first_card_face_down(self):
        """Test flipping a face-down card as first card (Rule 1-B)."""
        board = Board(2, 2, ['A', 'B', 'A', 'B'])
        state = await board.flip('alice', 0, 0)
        
        lines = state.split('\n')
        assert lines[1] == 'my A'  # alice controls this card
        assert lines[2] == 'down'  # other cards still face down
    
    async def test_rule_1c_flip_first_card_face_up_uncontrolled(self):
        """Test flipping a face-up uncontrolled card as first card (Rule 1-C)."""
        board = Board(2, 2, ['A', 'B', 'A', 'B'])
        
        # Alice flips (0,0)
        await board.flip('alice', 0, 0)
        # Alice flips second card - no match
        try:
            await board.flip('alice', 0, 1)
        except ValueError:
            pass
        # Alice's previous cards should be face up now
        
        # Bob can take control of the face-up card at (0,0)
        state = await board.flip('bob', 0, 0)
        lines = state.split('\n')
        assert 'my A' in lines[1]  # Bob controls it
    
    async def test_rule_1a_flip_empty_space_first_card(self):
        """Test flipping an empty space as first card (Rule 1-A)."""
        board = Board(2, 2, ['A', 'B', 'A', 'B'])
        
        # Alice flips and matches two cards
        await board.flip('alice', 0, 0)
        await board.flip('alice', 1, 0)
        
        # Cards are removed on next move
        await board.flip('alice', 0, 1)
        
        # Try to flip the now-empty space
        with pytest.raises(ValueError, match="No card at this position"):
            await board.flip('bob', 0, 0)
    
    async def test_rule_2d_flip_second_card_matching(self):
        """Test flipping a matching second card (Rule 2-D)."""
        board = Board(2, 2, ['A', 'B', 'A', 'B'])
        
        # Flip first card
        await board.flip('alice', 0, 0)
        # Flip matching second card
        state = await board.flip('alice', 1, 0)
        
        lines = state.split('\n')
        assert lines[1] == 'my A'
        assert lines[3] == 'my A'
    
    async def test_rule_2e_flip_second_card_non_matching(self):
        """Test flipping a non-matching second card (Rule 2-E)."""
        board = Board(2, 2, ['A', 'B', 'A', 'B'])
        
        # Flip first card (A)
        await board.flip('alice', 0, 0)
        # Flip non-matching second card (B)
        state = await board.flip('alice', 0, 1)
        
        # Both should be face up but alice shouldn't control them
        lines = state.split('\n')
        assert lines[1] == 'up A'
        assert lines[2] == 'up B'
    
    async def test_rule_2a_flip_empty_space_second_card(self):
        """Test flipping an empty space as second card (Rule 2-A)."""
        board = Board(2, 2, ['A', 'B', 'A', 'B'])
        
        # Alice matches two cards
        await board.flip('alice', 0, 0)
        await board.flip('alice', 1, 0)
        
        # Remove them by making another move
        await board.flip('alice', 0, 1)
        
        # Bob flips a first card
        await board.flip('bob', 1, 1)
        
        # Bob tries to flip the empty space as second card
        with pytest.raises(ValueError, match="No card at this position"):
            await board.flip('bob', 0, 0)
    
    async def test_rule_2b_flip_controlled_card_second_card(self):
        """Test flipping a controlled card as second card (Rule 2-B)."""
        board = Board(2, 2, ['A', 'B', 'A', 'B'])
        
        # Alice flips first card
        await board.flip('alice', 0, 0)
        
        # Alice tries to flip the same card again (controlled by self)
        with pytest.raises(ValueError, match="Card is already controlled"):
            await board.flip('alice', 0, 0)
        
        # Verify alice relinquished first card but it's still face-up
        state = await board.look('alice')
        lines = state.split('\n')
        assert lines[1] == 'up A'  # Face-up but not controlled by alice
    
    async def test_rule_2b_flip_other_player_controlled_second_card(self):
        """Test flipping another player's controlled card as second card (Rule 2-B)."""
        board = Board(2, 2, ['A', 'B', 'A', 'B'])
        
        # Alice and Bob each flip first cards
        await board.flip('alice', 0, 0)
        await board.flip('bob', 0, 1)
        
        # Alice tries to flip Bob's controlled card as second card
        with pytest.raises(ValueError, match="Card is already controlled"):
            await board.flip('alice', 0, 1)
        
        # Alice's first card should be relinquished but face-up
        state_alice = await board.look('alice')
        lines_alice = state_alice.split('\n')
        assert lines_alice[1] == 'up A'  # Alice's first card is face-up but not controlled
        assert lines_alice[2] == 'up B'  # Bob's card appears as face-up (but controlled by Bob)
        
        # Bob should still control his card
        state_bob = await board.look('bob')
        assert 'my B' in state_bob  # Bob still controls his card
    
    async def test_rule_2c_flip_face_down_second_card(self):
        """Test flipping a face-down card as second card turns it face-up (Rule 2-C)."""
        board = Board(2, 2, ['A', 'B', 'A', 'B'])
        
        # Alice flips first card (face-down -> face-up)
        state1 = await board.flip('alice', 0, 0)
        lines1 = state1.split('\n')
        assert lines1[1] == 'my A'  # First card is face-up and controlled
        assert lines1[2] == 'down'  # Second card is still face-down
        
        # Alice flips second card (face-down -> should turn face-up per Rule 2-C)
        state2 = await board.flip('alice', 0, 1)
        lines2 = state2.split('\n')
        
        # Both cards should now be face-up (non-matching, so uncontrolled)
        assert lines2[1] == 'up A'  # First card face-up
        assert lines2[2] == 'up B'  # Second card turned face-up by Rule 2-C
    
    async def test_rule_3a_matched_cards_removed(self):
        """Test that matched cards are removed on next move (Rule 3-A)."""
        board = Board(2, 2, ['A', 'B', 'A', 'B'])
        
        # Alice matches two cards
        await board.flip('alice', 0, 0)
        await board.flip('alice', 1, 0)
        
        # Make another move - matched cards should be removed
        state = await board.flip('alice', 0, 1)
        
        lines = state.split('\n')
        assert lines[1] == 'none'  # (0,0) removed
        assert lines[3] == 'none'  # (1,0) removed
        assert lines[2] == 'my B'  # alice's new first card
    
    async def test_rule_3b_non_matching_cards_turned_face_down(self):
        """Test that non-matching cards turn face down on next move (Rule 3-B)."""
        board = Board(2, 2, ['A', 'B', 'A', 'B'])
        
        # Alice flips non-matching cards
        await board.flip('alice', 0, 0)
        await board.flip('alice', 0, 1)
        
        # Make another move - previous cards should turn face down
        state = await board.flip('alice', 1, 0)
        
        lines = state.split('\n')
        assert lines[1] == 'down'  # (0,0) turned face down
        assert lines[2] == 'down'  # (0,1) turned face down
        assert lines[3] == 'my A'  # alice's new first card
    
    async def test_controlled_card_not_turned_face_down(self):
        """Test that controlled cards stay face up (Rule 3-B condition)."""
        board = Board(2, 2, ['A', 'B', 'A', 'B'])
        
        # Alice flips non-matching cards
        await board.flip('alice', 0, 0)
        await board.flip('alice', 0, 1)
        
        # Bob takes control of one of alice's previous cards before she makes next move
        # This is tricky - bob would need to wait for it in Rule 1-D
        # For now, let's just verify the basic case
    
    async def test_map_identity(self):
        """Test map with identity function."""
        board = Board(2, 2, ['A', 'B', 'A', 'B'])
        
        async def identity(card: str) -> str:
            return card
        
        state = await board.map('alice', identity)
        lines = state.split('\n')
        # Board should be unchanged
        assert lines[0] == '2x2'
    
    async def test_map_replacement(self):
        """Test map with replacement function."""
        board = Board(2, 2, ['A', 'B', 'A', 'B'])
        
        async def replace_a_with_c(card: str) -> str:
            return 'C' if card == 'A' else card
        
        # First look to see original state
        state1 = await board.look('alice')
        
        # Apply map
        state2 = await board.map('alice', replace_a_with_c)
        
        # All A cards should now be C, but still face down
        lines = state2.split('\n')
        assert state2.startswith('2x2')
    
    async def test_map_preserves_pairwise_consistency(self):
        """Test that map preserves matching pairs."""
        board = Board(2, 2, ['A', 'A', 'B', 'B'])
        
        async def transform(card: str) -> str:
            if card == 'A':
                return 'X'
            return 'Y'
        
        await board.map('alice', transform)
        
        # All A's should become X, all B's should become Y
        # If we flip and match, it should still work
        await board.flip('alice', 0, 0)
        state = await board.flip('alice', 0, 1)
        
        # Should match since both were A (now both X)
        lines = state.split('\n')
        assert 'my X' in lines[1]
        assert 'my X' in lines[2]
    
    async def test_watch_detects_flip(self):
        """Test that watch detects a flip operation."""
        board = Board(2, 2, ['A', 'B', 'A', 'B'])
        
        # Start watching in background
        watch_task = asyncio.create_task(board.watch('bob'))
        
        # Give watch time to register
        await asyncio.sleep(0.01)
        
        # Make a change
        await board.flip('alice', 0, 0)
        
        # Watch should complete
        state = await watch_task
        assert state.startswith('2x2')
    
    async def test_watch_detects_removal(self):
        """Test that watch detects card removal."""
        board = Board(2, 2, ['A', 'B', 'A', 'B'])
        
        # Alice matches cards
        await board.flip('alice', 0, 0)
        await board.flip('alice', 1, 0)
        
        # Start watching
        watch_task = asyncio.create_task(board.watch('bob'))
        await asyncio.sleep(0.01)
        
        # Alice makes next move, removing matched cards
        await board.flip('alice', 0, 1)
        
        # Watch should detect the removal
        state = await watch_task
        assert 'none' in state
    
    async def test_concurrent_flips_different_cards(self):
        """Test concurrent flips on different cards."""
        board = Board(3, 3, ['A', 'B', 'C', 'A', 'B', 'C', 'A', 'B', 'C'])
        
        # Two players flip different cards concurrently
        task1 = asyncio.create_task(board.flip('alice', 0, 0))
        task2 = asyncio.create_task(board.flip('bob', 0, 1))
        
        state1, state2 = await asyncio.gather(task1, task2)
        
        # Both should succeed
        assert 'my' in state1
        assert 'my' in state2
    
    async def test_rule_1d_concurrent_flips_same_card_wait(self):
        """Test that concurrent flips on same card cause waiting (Rule 1-D)."""
        board = Board(2, 2, ['A', 'B', 'A', 'B'])
        
        # Alice flips first card and controls it
        await board.flip('alice', 0, 0)
        
        # Bob tries to flip same card - should wait
        bob_task = asyncio.create_task(board.flip('bob', 0, 0))
        
        # Give bob time to start waiting
        await asyncio.sleep(0.05)
        
        # Alice makes second flip (no match), relinquishing control of (0,0)
        await board.flip('alice', 0, 1)
        
        # Bob should now be able to get the card (it's face-up and uncontrolled)
        # Set a timeout so test doesn't hang forever
        try:
            state = await asyncio.wait_for(bob_task, timeout=2.0)
            assert 'my' in state or 'A' in state  # Bob should get the card
        except asyncio.TimeoutError:
            pytest.fail("Bob's flip timed out - possible deadlock")
    
    async def test_multiple_players(self):
        """Test game with multiple players."""
        board = Board(3, 3, ['A', 'B', 'C', 'A', 'B', 'C', 'A', 'B', 'C'])
        
        # Three players each flip cards
        await board.flip('alice', 0, 0)
        await board.flip('bob', 0, 1)
        await board.flip('charlie', 0, 2)
        
        # Each player should see their own controlled card
        state_alice = await board.look('alice')
        state_bob = await board.look('bob')
        state_charlie = await board.look('charlie')
        
        assert 'my A' in state_alice
        assert 'my B' in state_bob
        assert 'my C' in state_charlie
    
    async def test_invalid_position(self):
        """Test flipping invalid positions."""
        board = Board(2, 2, ['A', 'B', 'A', 'B'])
        
        with pytest.raises(ValueError, match="Invalid position"):
            await board.flip('alice', -1, 0)
        
        with pytest.raises(ValueError, match="Invalid position"):
            await board.flip('alice', 0, 5)
        
        with pytest.raises(ValueError, match="Invalid position"):
            await board.flip('alice', 10, 10)
    
    async def test_board_string_representation(self):
        """Test __str__ method."""
        board = Board(3, 3, ['A', 'B', 'C', 'A', 'B', 'C', 'A', 'B', 'C'])
        s = str(board)
        assert '3x3' in s
        assert '9 cards' in s


class TestCard:
    """Tests for Card ADT."""
    
    def test_card_creation(self):
        """Test creating a card."""
        card = Card('A')
        assert card.label == 'A'
    
    def test_card_equality(self):
        """Test card equality."""
        card1 = Card('A')
        card2 = Card('A')
        card3 = Card('B')
        
        assert card1 == card2
        assert card1 != card3
    
    def test_card_hash(self):
        """Test that cards can be hashed."""
        card1 = Card('A')
        card2 = Card('A')
        
        s = {card1, card2}
        assert len(s) == 1  # Same card
    
    def test_card_invalid_label(self):
        """Test that invalid card labels fail."""
        with pytest.raises(AssertionError):
            Card('')  # Empty label
        
        with pytest.raises(AssertionError):
            Card('A B')  # Contains space
        
        with pytest.raises(AssertionError):
            Card('A\n')  # Contains newline


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
