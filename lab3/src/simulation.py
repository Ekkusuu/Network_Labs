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
        self.flip_attempts = 0  # Total flip attempts (should be exactly 100)
        self.successful_flips = 0
        self.failed_flips = 0
        self.matches_found = 0
        self.start_time: float = 0
        self.end_time: float = 0
    
    @property
    def duration(self) -> float:
        """Time taken by this player in seconds."""
        return self.end_time - self.start_time if self.end_time > 0 else 0


async def player(board: Board, player_id: str, size: int, flip_attempts: int, max_delay_ms: float, min_delay_ms: float, stats: PlayerStats):
    """
    Simulate a player making random moves.
    
    :param board: the game board
    :param player_id: ID of this player
    :param size: board dimension (assumes square board)
    :param flip_attempts: number of flip attempts to make (exactly this many)
    :param max_delay_ms: maximum delay between moves in milliseconds
    :param min_delay_ms: minimum delay between moves in milliseconds
    :param stats: statistics tracker for this player
    """
    print(f"Player {player_id} starting...")
    stats.start_time = time.time()
    
    for i in range(flip_attempts):
        try:
            # Random delay between min and max (no shuffling, pure random)
            delay = min_delay_ms + random.random() * (max_delay_ms - min_delay_ms)
            await asyncio.sleep(delay / 1000)  # Convert ms to seconds
            
            # Try to flip a card at random position
            row = random.randint(0, size - 1)
            col = random.randint(0, size - 1)
            print(f"{player_id}: Attempt {i+1}/{flip_attempts}: Flipping card at ({row}, {col})")
            
            stats.flip_attempts += 1
            await board.flip(player_id, row, col)
            stats.successful_flips += 1
            
        except Exception as e:
            print(f"{player_id}: Flip failed - {e}")
            stats.failed_flips += 1
    
    stats.end_time = time.time()
    print(f"Player {player_id} finished {stats.flip_attempts} flip attempts.")


async def main():
    """Run a simulation of the Memory Scramble game."""
    filename = 'boards/ab.txt'
    size = 5
    num_players = 4  # Requirements: 4 players
    flip_attempts = 100  # Requirements: 100 flip attempts each (not move pairs)
    max_delay_ms = 2  # Requirements: timeouts between 0.1ms and 2ms
    min_delay_ms = 0.1
    
    print("=" * 60)
    print("MEMORY SCRAMBLE SIMULATION")
    print("=" * 60)
    print(f"\nLoading board from {filename}...")
    board = await Board.parse_from_file(filename)
    print(f"Board loaded: {board}")
    
    print(f"\nStarting simulation with {num_players} players...")
    print(f"Each player will make {flip_attempts} flip attempts")
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
        task = asyncio.create_task(player(board, player_id, size, flip_attempts, max_delay_ms, min_delay_ms, stats))
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
        print(f"  Total flip attempts: {stats.flip_attempts}")
        print(f"  Successful flips: {stats.successful_flips}")
        print(f"  Failed flips: {stats.failed_flips}")
        print(f"  Time taken: {stats.duration:.2f} seconds")
        if stats.flip_attempts > 0:
            print(f"  Success rate: {(stats.successful_flips / stats.flip_attempts * 100):.1f}%")
    
    print("\n" + "=" * 60)
    print("OVERALL STATISTICS")
    print("=" * 60)
    print(f"Total simulation time: {total_duration:.2f} seconds")
    print(f"Total flip attempts by all players: {sum(s.flip_attempts for s in player_stats.values())}")
    print(f"Total successful flips: {sum(s.successful_flips for s in player_stats.values())}")
    print(f"Total failed flips: {sum(s.failed_flips for s in player_stats.values())}")
    print("=" * 60)


if __name__ == '__main__':
    asyncio.run(main())
