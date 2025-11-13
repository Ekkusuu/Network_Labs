"""
Copyright (c) 2021-25 MIT 6.102/6.031 course staff, all rights reserved.
Redistribution of original or derived work requires permission of course staff.

Board ADT for Memory Scramble game.
"""

import asyncio
import aiofiles
from typing import Optional, Dict, Set, List, Callable, Awaitable
from enum import Enum


class CardState(Enum):
    """State of a card on the board."""
    FACE_DOWN = "down"
    FACE_UP = "up"


class Card:
    """
    Represents a card on the board.
    Immutable.
    
    Abstraction function:
        AF(label) = a card with the given label text
    Representation invariant:
        - label is a non-empty string with no whitespace or newlines
    Safety from rep exposure:
        - label is a string (immutable in Python)
    """
    
    def __init__(self, label: str):
        """
        Create a new card.
        
        :param label: the text on this card
        """
        self.label = label
        self._check_rep()
    
    def _check_rep(self) -> None:
        """Check the representation invariant."""
        assert self.label, "Card label must be non-empty"
        assert ' ' not in self.label and '\n' not in self.label and '\r' not in self.label, \
            "Card label must not contain whitespace or newlines"
    
    def __eq__(self, other) -> bool:
        """Two cards are equal if they have the same label."""
        if not isinstance(other, Card):
            return False
        return self.label == other.label
    
    def __hash__(self) -> int:
        return hash(self.label)
    
    def __str__(self) -> str:
        return self.label


class PlayerState:
    """
    Represents a player's state in the game.
    Mutable.
    
    Abstraction function:
        AF(first_card, second_card, previous_cards) = 
            a player who currently controls first_card and second_card,
            and previously controlled previous_cards (for turning face down)
    Representation invariant:
        - first_card and second_card are positions on the board or None
        - previous_cards contains at most 2 positions
    Safety from rep exposure:
        - All fields are primitive types or None
        - Defensive copies not needed for tuples
    """
    
    def __init__(self):
        """Create a new player with no controlled cards."""
        self.first_card: Optional[tuple[int, int]] = None
        self.second_card: Optional[tuple[int, int]] = None
        self.previous_cards: List[tuple[int, int]] = []
        self._check_rep()
    
    def _check_rep(self) -> None:
        """Check the representation invariant."""
        assert len(self.previous_cards) <= 2, "Cannot have more than 2 previous cards"
    
    def has_first_card(self) -> bool:
        """Return True if player controls a first card."""
        return self.first_card is not None
    
    def has_second_card(self) -> bool:
        """Return True if player controls a second card."""
        return self.second_card is not None


class Board:
    """
    Represents a Memory Scramble game board.
    Mutable and concurrency safe.
    
    Abstraction function:
        AF(rows, cols, cards, card_states, players, waiters, change_listeners, lock) =
            a rows x cols game board where:
            - cards[r][c] is the card at position (r,c), or None if empty
            - card_states[r][c] is FACE_UP or FACE_DOWN for the card at (r,c)
            - players[player_id] tracks each player's controlled cards
            - waiters[(r,c)] is a list of futures waiting for the card at (r,c)
            - change_listeners is a list of futures waiting for any board change
            - lock protects all mutable state for thread safety
    
    Representation invariant:
        - rows > 0, cols > 0
        - len(cards) == rows, len(cards[r]) == cols for all r
        - len(card_states) == rows, len(card_states[r]) == cols for all r
        - if cards[r][c] is not None, then card_states[r][c] is defined
        - all player_ids are non-empty alphanumeric/underscore strings
        - a card can be controlled by at most one player
    
    Safety from rep exposure:
        - All fields are private
        - cards are Card objects (immutable)
        - All public methods use asyncio.Lock for synchronization
        - Never return mutable internal state directly
    """
    
    def __init__(self, rows: int, cols: int, card_labels: List[str]):
        """
        Create a new board with the given dimensions and cards.
        
        :param rows: number of rows
        :param cols: number of columns  
        :param card_labels: list of card labels in row-major order
        """
        assert rows > 0 and cols > 0, "Board must have positive dimensions"
        assert len(card_labels) == rows * cols, "Must provide exactly rows*cols cards"
        
        self._rows = rows
        self._cols = cols
        self._lock = asyncio.Lock()
        
        # Initialize the board grid
        self._cards: List[List[Optional[Card]]] = []
        self._card_states: List[List[Optional[CardState]]] = []
        
        idx = 0
        for r in range(rows):
            card_row = []
            state_row = []
            for c in range(cols):
                card_row.append(Card(card_labels[idx]))
                state_row.append(CardState.FACE_DOWN)
                idx += 1
            self._cards.append(card_row)
            self._card_states.append(state_row)
        
        # Player state tracking
        self._players: Dict[str, PlayerState] = {}
        
        # Waiting mechanisms for concurrency
        # waiters[position] = list of Futures waiting to control that card
        self._waiters: Dict[tuple[int, int], List[asyncio.Future]] = {}
        
        # Listeners waiting for any change to the board
        self._change_listeners: List[asyncio.Future] = []
        
        # Track board version for change detection
        self._version = 0
        
        self._check_rep()
    
    def _check_rep(self) -> None:
        """Check the representation invariant."""
        assert self._rows > 0 and self._cols > 0, "Board must have positive dimensions"
        assert len(self._cards) == self._rows, "Cards grid height mismatch"
        assert len(self._card_states) == self._rows, "States grid height mismatch"
        
        for r in range(self._rows):
            assert len(self._cards[r]) == self._cols, f"Cards grid width mismatch at row {r}"
            assert len(self._card_states[r]) == self._cols, f"States grid width mismatch at row {r}"
            for c in range(self._cols):
                if self._cards[r][c] is not None:
                    assert self._card_states[r][c] is not None, \
                        f"Card at ({r},{c}) must have a state"
    
    @staticmethod
    async def parse_from_file(filename: str) -> 'Board':
        """
        Make a new board by parsing a file.
        
        PS4 instructions: the specification of this method may not be changed.
        
        :param filename: path to game board file
        :return: a new board with the size and cards from the file
        :raises: Error if the file cannot be read or is not a valid game board
        """
        try:
            async with aiofiles.open(filename, 'r', encoding='utf-8') as f:
                content = await f.read()
            
            lines = content.strip().split('\n')
            if not lines:
                raise ValueError("Empty board file")
            
            # Parse dimensions
            dims = lines[0].split('x')
            if len(dims) != 2:
                raise ValueError("First line must be ROWSxCOLS")
            
            rows = int(dims[0])
            cols = int(dims[1])
            
            # Parse cards
            card_lines = lines[1:]
            if len(card_lines) != rows * cols:
                raise ValueError(f"Expected {rows * cols} cards, got {len(card_lines)}")
            
            card_labels = []
            for line in card_lines:
                label = line.strip()
                if not label:
                    raise ValueError("Card label cannot be empty")
                if ' ' in label or '\n' in label or '\r' in label:
                    raise ValueError("Card label cannot contain whitespace or newlines")
                card_labels.append(label)
            
            return Board(rows, cols, card_labels)
        
        except FileNotFoundError:
            raise FileNotFoundError(f"Board file not found: {filename}")
        except Exception as e:
            raise ValueError(f"Invalid board file: {e}")
    
    async def look(self, player_id: str) -> str:
        """
        Look at the current state of the board from a player's perspective.
        
        :param player_id: ID of the player looking at the board
        :return: board state string in the format specified in ps4 handout
        """
        async with self._lock:
            self._ensure_player(player_id)
            return self._get_board_state(player_id)
    
    async def flip(self, player_id: str, row: int, column: int) -> str:
        """
        Flip a card on the board according to the game rules.
        
        :param player_id: ID of the player making the flip
        :param row: row number of the card (0-indexed from top)
        :param column: column number of the card (0-indexed from left)
        :return: board state after the flip
        :raises: ValueError if the flip fails according to game rules
        """
        # Validate position
        if not (0 <= row < self._rows and 0 <= column < self._cols):
            raise ValueError(f"Invalid position: ({row}, {column})")
        
        async with self._lock:
            self._ensure_player(player_id)
            player = self._players[player_id]
            pos = (row, column)
            
            # Clean up previous move's cards
            await self._cleanup_previous_move(player_id)
            
            # Determine if this is a first card or second card flip
            if not player.has_first_card():
                # Flipping first card
                return await self._flip_first_card(player_id, pos)
            else:
                # Flipping second card
                return await self._flip_second_card(player_id, pos)
    
    async def _flip_first_card(self, player_id: str, pos: tuple[int, int]) -> str:
        """
        Handle flipping a first card.
        
        :param player_id: ID of the player
        :param pos: position of the card
        :return: board state after the flip
        :raises: ValueError if operation fails
        """
        row, col = pos
        card = self._cards[row][col]
        player = self._players[player_id]
        
        # Rule 1-A: No card there
        if card is None:
            raise ValueError("No card at this position")
        
        # Check if another player controls this card
        controller = self._get_controller(pos)
        
        if controller is not None and controller != player_id:
            # Rule 1-D: Wait until we can control it
            await self._wait_for_card(pos)
            # After waiting, try again
            return await self._flip_first_card(player_id, pos)
        
        # Rule 1-B: Card is face down - turn it face up
        # Rule 1-C: Card is face up but not controlled - take control
        self._card_states[row][col] = CardState.FACE_UP
        player.first_card = pos
        self._notify_change()
        
        return self._get_board_state(player_id)
    
    async def _flip_second_card(self, player_id: str, pos: tuple[int, int]) -> str:
        """
        Handle flipping a second card.
        
        :param player_id: ID of the player
        :param pos: position of the card
        :return: board state after the flip
        :raises: ValueError if operation fails
        """
        row, col = pos
        card = self._cards[row][col]
        player = self._players[player_id]
        
        # Rule 2-A: No card there
        if card is None:
            # Relinquish control of first card
            first_card_pos = player.first_card
            player.previous_cards.append(first_card_pos)
            player.first_card = None
            # Wake up anyone waiting for the relinquished card
            if first_card_pos:
                self._wake_waiters(first_card_pos)
            self._notify_change()
            raise ValueError("No card at this position")
        
        # Rule 2-B: Card is controlled by someone (including self)
        controller = self._get_controller(pos)
        if controller is not None:
            # Relinquish control of first card
            first_card_pos = player.first_card
            player.previous_cards.append(first_card_pos)
            player.first_card = None
            # Wake up anyone waiting for the relinquished card
            if first_card_pos:
                self._wake_waiters(first_card_pos)
            self._notify_change()
            raise ValueError("Card is already controlled")
        
        # Rule 2-C: Turn face up if face down
        self._card_states[row][col] = CardState.FACE_UP
        
        # Check if cards match
        first_pos = player.first_card
        first_card = self._cards[first_pos[0]][first_pos[1]]
        second_card = card
        
        if first_card == second_card:
            # Rule 2-D: Match! Player keeps control of both
            player.second_card = pos
        else:
            # Rule 2-E: No match - relinquish control of both
            first_pos = player.first_card
            player.previous_cards = [first_pos, pos]
            player.first_card = None
            player.second_card = None
            # Wake up anyone waiting for these cards (now uncontrolled but face-up)
            self._wake_waiters(first_pos)
            self._wake_waiters(pos)
        
        self._notify_change()
        return self._get_board_state(player_id)
    
    async def _cleanup_previous_move(self, player_id: str) -> None:
        """
        Clean up cards from the player's previous move according to rules 3-A and 3-B.
        
        :param player_id: ID of the player
        """
        player = self._players[player_id]
        
        # Rule 3-A: Remove matched cards
        if player.has_second_card():
            # Player had a matching pair - remove them
            first_pos = player.first_card
            second_pos = player.second_card
            
            self._cards[first_pos[0]][first_pos[1]] = None
            self._card_states[first_pos[0]][first_pos[1]] = None
            self._cards[second_pos[0]][second_pos[1]] = None
            self._card_states[second_pos[0]][second_pos[1]] = None
            
            player.first_card = None
            player.second_card = None
            
            # Wake up anyone waiting for these cards
            self._wake_waiters(first_pos)
            self._wake_waiters(second_pos)
            self._notify_change()
        
        # Rule 3-B: Turn face down non-matching cards
        for pos in player.previous_cards:
            row, col = pos
            if self._cards[row][col] is not None:  # Card still exists
                state = self._card_states[row][col]
                controller = self._get_controller(pos)
                
                # Only turn face down if face up and not controlled
                if state == CardState.FACE_UP and controller is None:
                    self._card_states[row][col] = CardState.FACE_DOWN
                    self._notify_change()
        
        player.previous_cards = []
    
    def _get_controller(self, pos: tuple[int, int]) -> Optional[str]:
        """
        Get the player ID that controls the card at the given position.
        
        :param pos: position of the card
        :return: player ID or None if no one controls it
        """
        for player_id, player_state in self._players.items():
            if player_state.first_card == pos or player_state.second_card == pos:
                return player_id
        return None
    
    async def _wait_for_card(self, pos: tuple[int, int]) -> None:
        """
        Wait until the card at the given position is available.
        
        :param pos: position of the card to wait for
        """
        # Create a future that will be resolved when the card is available
        future = asyncio.Future()
        
        if pos not in self._waiters:
            self._waiters[pos] = []
        self._waiters[pos].append(future)
        
        # Release lock while waiting
        self._lock.release()
        try:
            await future
        finally:
            await self._lock.acquire()
    
    def _wake_waiters(self, pos: tuple[int, int]) -> None:
        """
        Wake up one waiter for the card at the given position.
        
        :param pos: position of the card
        """
        if pos in self._waiters and self._waiters[pos]:
            future = self._waiters[pos].pop(0)
            if not future.done():
                future.set_result(None)
    
    def _ensure_player(self, player_id: str) -> None:
        """
        Ensure a player exists in the game.
        
        :param player_id: ID of the player
        """
        if player_id not in self._players:
            self._players[player_id] = PlayerState()
    
    def _get_board_state(self, player_id: str) -> str:
        """
        Get the board state from a player's perspective.
        
        :param player_id: ID of the player
        :return: board state string
        """
        lines = [f"{self._rows}x{self._cols}"]
        
        for r in range(self._rows):
            for c in range(self._cols):
                card = self._cards[r][c]
                state = self._card_states[r][c]
                
                if card is None:
                    lines.append("none")
                elif state == CardState.FACE_DOWN:
                    lines.append("down")
                else:  # FACE_UP
                    controller = self._get_controller((r, c))
                    if controller == player_id:
                        lines.append(f"my {card.label}")
                    else:
                        lines.append(f"up {card.label}")
        
        return '\n'.join(lines)
    
    async def map(self, player_id: str, f: Callable[[str], Awaitable[str]]) -> str:
        """
        Apply a transformation function to every card on the board.
        
        :param player_id: ID of the player applying the map
        :param f: async function that transforms card labels
        :return: board state after the transformation
        """
        async with self._lock:
            self._ensure_player(player_id)
            
            # Collect unique cards and their transformations
            # This maintains pairwise consistency
            transformations: Dict[str, str] = {}
            
            for r in range(self._rows):
                for c in range(self._cols):
                    card = self._cards[r][c]
                    if card is not None and card.label not in transformations:
                        # Release lock while calling f
                        self._lock.release()
                        try:
                            new_label = await f(card.label)
                            transformations[card.label] = new_label
                        finally:
                            await self._lock.acquire()
            
            # Apply transformations atomically (while holding lock)
            changed = False
            for r in range(self._rows):
                for c in range(self._cols):
                    card = self._cards[r][c]
                    if card is not None:
                        new_label = transformations[card.label]
                        if new_label != card.label:
                            self._cards[r][c] = Card(new_label)
                            changed = True
            
            if changed:
                self._notify_change()
            
            return self._get_board_state(player_id)
    
    async def watch(self, player_id: str) -> str:
        """
        Wait for the board to change, then return the new state.
        
        :param player_id: ID of the player watching
        :return: board state after a change occurs
        """
        # Create a future to wait for change
        future = asyncio.Future()
        
        async with self._lock:
            self._ensure_player(player_id)
            # Register as a listener for the next change
            self._change_listeners.append(future)
        
        # Wait for change outside the lock
        await future
        
        # Get the updated board state
        async with self._lock:
            return self._get_board_state(player_id)
    
    def _notify_change(self) -> None:
        """Notify all watchers that the board has changed."""
        self._version += 1
        
        # Wake up all listeners
        for future in self._change_listeners:
            if not future.done():
                future.set_result(None)
        self._change_listeners.clear()
    
    def __str__(self) -> str:
        """Return a string representation of the board."""
        return f"Board({self._rows}x{self._cols}, {sum(1 for r in range(self._rows) for c in range(self._cols) if self._cards[r][c] is not None)} cards)"
