"""
Simulation of a Memory Scramble game with multiple players.
This is useful for testing the board with concurrent operations.
"""

import asyncio
import sys
import os
import random
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from board import Board


class PlayerStats:
    """Track statistics for a player."""
    
    def __init__(self, player_id: str):
        self.player_id = player_id
        self.successful_flips = 0
        self.failed_flips = 0
        self.matches_found = 0
        self.start_time: float = 0
        self.end_time: float = 0
    
    @property
    def total_moves(self) -> int:
        """Total number of move attempts (pairs of flips)."""
        return (self.successful_flips + self.failed_flips) // 2
    
    @property
    def duration(self) -> float:
        """Time taken by this player in seconds."""
        return self.end_time - self.start_time if self.end_time > 0 else 0


async def player(board: Board, player_id: str, size: int, tries: int, max_delay_ms: float, min_delay_ms: float, stats: PlayerStats):
    """
    Simulate a player making random moves.
    
    :param board: the game board
    :param player_id: ID of this player
    :param size: board dimension (assumes square board)
    :param tries: number of flip attempts to make
    :param max_delay_ms: maximum delay between moves in milliseconds
    :param min_delay_ms: minimum delay between moves in milliseconds
    :param stats: statistics tracker for this player
    """
    print(f"Player {player_id} starting...")
    stats.start_time = time.time()
    
    for attempt in range(tries):
        try:
            # Random delay between min and max (no shuffling, pure random)
            delay = min_delay_ms + random.random() * (max_delay_ms - min_delay_ms)
            await asyncio.sleep(delay / 1000)  # Convert ms to seconds
            
            # Try to flip a first card at random position
            row1 = random.randint(0, size - 1)
            col1 = random.randint(0, size - 1)
            print(f"{player_id}: Flipping first card at ({row1}, {col1})")
            result1 = await board.flip(player_id, row1, col1)
            stats.successful_flips += 1
            
            # Extract card label from result
            lines = result1.strip().split('\n')
            card1_line = lines[1 + row1 * size + col1].split()
            card1_label = card1_line[1] if len(card1_line) > 1 else None
            
            # Random delay between min and max (no shuffling, pure random)
            delay = min_delay_ms + random.random() * (max_delay_ms - min_delay_ms)
            await asyncio.sleep(delay / 1000)  # Convert ms to seconds
            
            # Try to flip a second card at random position
            row2 = random.randint(0, size - 1)
            col2 = random.randint(0, size - 1)
            print(f"{player_id}: Flipping second card at ({row2}, {col2})")
            result2 = await board.flip(player_id, row2, col2)
            stats.successful_flips += 1
            
            # Extract card label from result
            lines = result2.strip().split('\n')
            card2_line = lines[1 + row2 * size + col2].split()
            card2_label = card2_line[1] if len(card2_line) > 1 else None
            
            # Check if it was a match (both cards should be removed now)
            if card1_label and card2_label and card1_label == card2_label:
                # Verify cards were removed
                final_lines = result2.strip().split('\n')
                card1_status = final_lines[1 + row1 * size + col1]
                if card1_status == "none":
                    stats.matches_found += 1
                    print(f"{player_id}: MATCH! Found pair of {card1_label}")
            
        except Exception as e:
            print(f"{player_id}: Flip failed - {e}")
            stats.failed_flips += 1
    
    stats.end_time = time.time()
    print(f"Player {player_id} finished.")


async def main():
    """Run a simulation of the Memory Scramble game."""
    filename = 'boards/ab.txt'
    size = 5
    num_players = 4  # Requirements: 4 players
    tries = 100  # Requirements: 100 moves each
    max_delay_ms = 2  # Requirements: timeouts between 0.1ms and 2ms
    min_delay_ms = 0.1
    
    print("=" * 60)
    print("MEMORY SCRAMBLE SIMULATION")
    print("=" * 60)
    print(f"\nLoading board from {filename}...")
    board = await Board.parse_from_file(filename)
    print(f"Board loaded: {board}")
    
    print(f"\nStarting simulation with {num_players} players...")
    print(f"Each player will make {tries} move attempts")
    print(f"Random delays between {min_delay_ms}ms and {max_delay_ms}ms")
    print()
    
    # Track statistics for each player
    player_stats = {}
    
    # Create player tasks
    player_tasks = []
    simulation_start = time.time()
    
    for i in range(num_players):
        player_id = f"player{i}"
        stats = PlayerStats(player_id)
        player_stats[player_id] = stats
        task = asyncio.create_task(player(board, player_id, size, tries, max_delay_ms, min_delay_ms, stats))
        player_tasks.append(task)
    
    # Wait for all players to finish
    await asyncio.gather(*player_tasks)
    
    simulation_end = time.time()
    total_duration = simulation_end - simulation_start
    
    print("\n" + "=" * 60)
    print("SIMULATION COMPLETE!")
    print("=" * 60)
    
    # Show final board state
    final_state = await board.look("observer")
    print("\nFinal board state:")
    print(final_state)
    
    # Print statistics
    print("\n" + "=" * 60)
    print("PLAYER STATISTICS")
    print("=" * 60)
    
    for player_id in sorted(player_stats.keys()):
        stats = player_stats[player_id]
        print(f"\n{stats.player_id}:")
        print(f"  Total moves attempted: {stats.total_moves}")
        print(f"  Successful flips: {stats.successful_flips}")
        print(f"  Failed flips: {stats.failed_flips}")
        print(f"  Matches found: {stats.matches_found}")
        print(f"  Time taken: {stats.duration:.2f} seconds")
        if stats.successful_flips > 0:
            print(f"  Success rate: {(stats.successful_flips / (stats.successful_flips + stats.failed_flips) * 100):.1f}%")
    
    print("\n" + "=" * 60)
    print("OVERALL STATISTICS")
    print("=" * 60)
    print(f"Total simulation time: {total_duration:.2f} seconds")
    print(f"Total moves by all players: {sum(s.total_moves for s in player_stats.values())}")
    print(f"Total matches found: {sum(s.matches_found for s in player_stats.values())}")
    print(f"Total successful flips: {sum(s.successful_flips for s in player_stats.values())}")
    print(f"Total failed flips: {sum(s.failed_flips for s in player_stats.values())}")
    print("=" * 60)


if __name__ == '__main__':
    asyncio.run(main())
