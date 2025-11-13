"""
Copyright (c) 2021-25 MIT 6.102/6.031 course staff, all rights reserved.
Redistribution of original or derived work requires permission of course staff.

HTTP web game server for Memory Scramble.

PS4 instructions: you are advised *not* to modify this file.

Command-line usage:
    python server.py PORT FILENAME
where:
  - PORT is an integer that specifies the server's listening port number,
  - FILENAME is the path to a valid board file, which will be loaded as
    the starting game board.

For example, to start a web server on port 8080 using the board in `boards/perfect.txt`:
    python server.py 8080 boards/perfect.txt
"""

import sys
import asyncio
from flask import Flask, send_from_directory
from flask_cors import CORS
from board import Board
from commands import look, flip, map_cards, watch


class WebServer:
    """HTTP web game server."""
    
    def __init__(self, board: Board, port: int):
        """
        Make a new web game server using board that listens for connections on port.
        
        :param board: shared game board
        :param port: server port number
        """
        self.board = board
        self.port = port
        self.app = Flask(__name__, static_folder='../public', static_url_path='')
        
        # Enable CORS to allow requests from web pages hosted anywhere
        CORS(self.app)
        
        # Route: GET /look/<player_id>
        @self.app.route('/look/<player_id>')
        def route_look(player_id):
            """
            GET /look/<player_id>
            player_id must be a nonempty string of alphanumeric or underscore characters
            
            Response is the board state from player_id's perspective.
            """
            board_state = asyncio.run(look(self.board, player_id))
            return board_state, 200, {'Content-Type': 'text/plain'}
        
        # Route: GET /flip/<player_id>/<row>,<column>
        @self.app.route('/flip/<player_id>/<location>')
        def route_flip(player_id, location):
            """
            GET /flip/<player_id>/<row>,<column>
            player_id must be a nonempty string of alphanumeric or underscore characters;
            row and column must be integers, 0 <= row,column < height,width of board (respectively)
            
            Response is the state of the board after the flip from the perspective of player_id.
            """
            try:
                parts = location.split(',')
                row = int(parts[0])
                column = int(parts[1])
                
                board_state = asyncio.run(flip(self.board, player_id, row, column))
                return board_state, 200, {'Content-Type': 'text/plain'}
            except ValueError as e:
                return f"cannot flip this card: {e}", 409, {'Content-Type': 'text/plain'}
            except Exception as e:
                return f"error: {e}", 400, {'Content-Type': 'text/plain'}
        
        # Route: GET /replace/<player_id>/<from_card>/<to_card>
        @self.app.route('/replace/<player_id>/<from_card>/<to_card>')
        def route_replace(player_id, from_card, to_card):
            """
            GET /replace/<player_id>/<from_card>/<to_card>
            player_id must be a nonempty string of alphanumeric or underscore characters;
            from_card and to_card must be nonempty strings.
            
            Replaces all occurrences of from_card with to_card (as card labels) on the board.
            
            Response is the state of the board after the replacement from the perspective of player_id.
            """
            async def transform(card: str) -> str:
                return to_card if card == from_card else card
            
            board_state = asyncio.run(map_cards(self.board, player_id, transform))
            return board_state, 200, {'Content-Type': 'text/plain'}
        
        # Route: GET /watch/<player_id>
        @self.app.route('/watch/<player_id>')
        def route_watch(player_id):
            """
            GET /watch/<player_id>
            player_id must be a nonempty string of alphanumeric or underscore characters
            
            Waits until the next time the board changes (defined as any cards turning face up or face down, 
            being removed from the board, or changing from one string to a different string).
            
            Response is the new state of the board from the perspective of player_id.
            """
            board_state = asyncio.run(watch(self.board, player_id))
            return board_state, 200, {'Content-Type': 'text/plain'}
        
        # Route: GET /
        @self.app.route('/')
        def route_index():
            """
            GET /
            
            Response is the game UI as an HTML page.
            """
            return send_from_directory('../public', 'index.html')
    
    def start(self):
        """Start this server."""
        print(f"server now listening at http://localhost:{self.port}")
        self.app.run(host='0.0.0.0', port=self.port, debug=False, threaded=True)
    
    def stop(self):
        """Stop this server. Once stopped, this server cannot be restarted."""
        print('server stopped')


async def main():
    """
    Start a game server using the given arguments.
    
    :raises: Exception if an error occurs parsing a file or starting a server
    """
    if len(sys.argv) < 3:
        print("Usage: python server.py PORT FILENAME")
        sys.exit(1)
    
    try:
        port = int(sys.argv[1])
        if port < 0:
            raise ValueError("PORT must be non-negative")
    except ValueError:
        print("Error: PORT must be a non-negative integer")
        sys.exit(1)
    
    filename = sys.argv[2]
    
    try:
        board = await Board.parse_from_file(filename)
        server = WebServer(board, port)
        server.start()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
