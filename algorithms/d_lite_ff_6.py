import API
import sys
import heapq
from collections import defaultdict
from collections import deque
import random

# Constants for directions
NORTH, EAST, SOUTH, WEST = 0, 1, 2, 3
direction_map = {NORTH: 'n', EAST: 'e', SOUTH: 's', WEST: 'w'}
current_orientation = NORTH

# Mouse position
x, y = 0, 0

# Maze dimensions
maze_width, maze_height = 6, 6

# Wall data structures to track where walls are in the maze
horizontal_walls = [[0] * maze_width for _ in range(maze_height + 1)]
vertical_walls = [[0] * (maze_width + 1) for _ in range(maze_height)]

# Set to track which cells have been explored
explored_cells = set()

phase = 'initial'
steps = {}

SKIP = True

# The steps taken by robot
path = []

# Variables needed for Phase final
# Set walls on unexplored vertices
# API.setWall only sets visual wall. checkWall will still return False.
# So set walls here. If we dont have wall in mss, we check if we have wall from this variable.
walls = defaultdict(set)


def add_concreteWall(u, v):
    global walls
    walls[u].add(v)
    walls[v].add(u)

def check_concreteWall(u, v):
    global walls
    return v in walls[u]


# Function to log messages for debugging purposes
def log(string, skip = None):
    if skip == False or SKIP == False:
        sys.stderr.write("{}\n".format(string))
        sys.stderr.flush()

# Functions to control the mouse's movement and update its orientation

def turn_left():
    global current_orientation
    API.turnLeft()
    current_orientation = (current_orientation - 1) % 4
    log(f"Turned left. New orientation: {current_orientation}")

def turn_right():
    global current_orientation
    API.turnRight()
    current_orientation = (current_orientation + 1) % 4
    log(f"Turned right. New orientation: {current_orientation}")

def turn_around():
    global current_orientation
    API.turnLeft()
    API.turnLeft()
    current_orientation = (current_orientation + 2) % 4
    log(f"Turned around. New orientation: {current_orientation}")

# Function to move the mouse forward and update its position in the maze
def move_forward():
    global x, y, current_orientation
    log(f"Attempting to move forward. Current position: ({x}, {y}), orientation: {current_orientation}")
    API.moveForward()

    # Update the mouse's position based on its current orientation
    if current_orientation == NORTH:
        y += 1
    elif current_orientation == EAST:
        x += 1
    elif current_orientation == SOUTH:
        y -= 1
    elif current_orientation == WEST:
        x -= 1
    log("----------------------------------------------------------------")
    log(f"Moved forward to ({x}, {y}). Updated position: ({x}, {y})")
    log(f"New orientation: {current_orientation}")


class LexicographicPriority:
    def __init__(self, primary_key, secondary_key):
        self.primary_key = primary_key
        self.secondary_key = secondary_key
        self.v = (primary_key, secondary_key)

    def __lt__(self, other):
        if self.primary_key == other.primary_key:
            return self.secondary_key < other.secondary_key
        return self.primary_key < other.primary_key

    def __repr__(self):
        return f"(primary_key={self.primary_key}, secondary_key={self.secondary_key})"



class QueueNode:
    def __init__(self, priority, vertex):
        self.priority = priority
        self.vertex = vertex

    def __lt__(self, other):
        return self.priority < other.priority


# Class to represent the D* Lite algorithm
class DStarLite:
    def __init__(self, start, goals, graph):
        # Initialize the D* Lite algorithm with a start point, goal points, and a graph of the maze
        self.start = start
        self.goals = goals
        self.graph = graph
        self.k_m = 0  # Km is a heuristic adjustment factor
        self.g = {v: float('inf') for v in graph.get_all_nodes()}
        self.rhs = {v: float('inf') for v in graph.get_all_nodes()}
        self.flood_fill_values = flood_fill(graph, goals)  # Moved before initialize
        self.priority_queue = PriorityQueue()
        self.initialize(start, goals)

    # Initialize the D* Lite algorithm
    def initialize(self, start, goals):
        log("Initializing D* Lite")
        for goal in goals:
            # Set the rhs value of the goal nodes to 0 (known cost to reach goal is zero)
            self.rhs[goal] = 0
            # Add the goal nodes to the priority queue with their calculated key
            heuristic_value = self.heuristic(self.start, goal)
            key = LexicographicPriority(heuristic_value, 0)
            self.priority_queue.insert(goal, key)

        log("D* Lite initialization complete.")
        for goal in goals:
            log(f"g[{goal}] = {self.g[goal]}")
            log(f"rhs[{goal}] = {self.rhs[goal]}")
            log(f"Added {goal} to the priority queue with key {self.calculate_key(goal)}")
            # Update the simulator with the rhs value at each goal location
            API.setText(goal[0], goal[1], str(int(self.rhs[goal])))
            log(f"Post-init check - rhs[{goal}] = {self.rhs[goal]}")

    # Calculate the priority key for a given vertex in the graph
    def calculate_key(self, vertex):
        g_rhs_min = min(self.g[vertex], self.rhs[vertex])
        heuristic_value = self.heuristic(self.start, vertex)
        key = LexicographicPriority(g_rhs_min + heuristic_value + self.k_m, g_rhs_min)
        
        log(f"Calculating key for {vertex}:")
        log(f"  g[{vertex}] = {self.g[vertex]}, rhs[{vertex}] = {self.rhs[vertex]}")
        log(f"  Heuristic from start to {vertex}: {heuristic_value}")
        log(f"  Key = (primary: {key.primary_key}, secondary: {key.secondary_key})")
        
        return key


    def heuristic(self, a, b):
        # Use the precomputed flood fill distance from 's_start' to 'vertex'
        return self.flood_fill_values.get(b, float('inf'))

    
    def update_vertex(self, vertex):
        if vertex not in self.goals:
            log(f"YEP 1")
            neighbors = self.graph.get_accessible_neighbors(vertex)
            new_rhs = float('inf')
            for neighbor in neighbors:
                log(f"Neighbour = {neighbor}")
                if self.graph.is_connected(vertex, neighbor):
                    cost = self.graph.cost(vertex, neighbor)
                    candidate_rhs = self.g[neighbor] + cost
                    if candidate_rhs < new_rhs:
                        new_rhs = candidate_rhs
                else:
                    log(f"NO")
            self.rhs[vertex] = new_rhs

        log(f"values = {self.g[vertex]} and {self.rhs[vertex]}")

        if vertex in self.priority_queue.vertex_set:
            log(f"YEP 2")
            self.priority_queue.remove(vertex)

        if self.g[vertex] != self.rhs[vertex]:
            log(f"YEP 3")
            key = self.calculate_key(vertex)
            self.priority_queue.insert(vertex, key)

        if self.rhs[vertex] == float('inf'):
            API.setText(vertex[0], vertex[1], "inf")
        else:
            API.setText(vertex[0], vertex[1], str(int(self.rhs[vertex])))

    def compute_shortest_path(self):
        log(f"Length of queue = {len(self.priority_queue.heap)}")
        while (self.priority_queue.peek_priority() < self.calculate_key(self.start)) or (self.rhs[self.start] != self.g[self.start]):
            kold = self.priority_queue.peek_priority()
            u = self.priority_queue.extract_min()
            if kold < self.calculate_key(u):
                self.priority_queue.insert(u, self.calculate_key(u))
            elif self.g[u] > self.rhs[u]:
                self.g[u] = self.rhs[u]
                for s in self.graph.get_parents(u):
                    self.update_vertex(s)
            else:
                self.g[u] = float('inf')
                self.update_vertex(u)
                for s in self.graph.get_parents(u):
                    self.update_vertex(s)

        show(self.g, self.rhs, self.flood_fill_values, self.priority_queue)

class MazeGraph:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.graph = {}
        self.initialize_graph()
        self.initialize_full_connections()

    # Initialize the graph structure
    def initialize_graph(self):
        for x in range(self.width):
            for y in range(self.height):
                self.graph[(x, y)] = []

    # Create full connections between neighboring cells
    def initialize_full_connections(self):
        for x in range(self.width):
            for y in range(self.height):
                if y < self.height - 1:
                    self.add_edge((x, y), (x, y + 1))  # Connect to north
                if y > 0:
                    self.add_edge((x, y), (x, y - 1))  # Connect to south
                if x < self.width - 1:
                    self.add_edge((x, y), (x + 1, y))  # Connect to east
                if x > 0:
                    self.add_edge((x, y), (x - 1, y))  # Connect to west

    # Add an edge between two cells
    def add_edge(self, u, v):
        not_exists = v not in self.graph[u]
        if not_exists:        
            self.graph[u].append(v)
            self.graph[v].append(u)
        return not_exists

    # Remove an edge between two cells
    def remove_edge(self, u, v):
        exists = v in self.graph[u]
        if exists:
            self.graph[u] = [i for i in self.graph[u] if i != v]
            self.graph[v] = [i for i in self.graph[v] if i != u]
        return exists
    
    def get_accessible_neighbors(self, node):
        # Returns only neighbors that are connected via an open path (no wall)
        return self.graph[node]

    def get_parents(self, node):
        parents = []
        for u in self.graph.keys():
            if node in self.graph[u]:
                parents.append(u)
        return parents

    def get_all_neighbors(self, node):
        # Returns all neighbors in all four directions, regardless of current walls
        x, y = node
        potential_neighbors = []
        if y < self.height - 1:
            potential_neighbors.append((x, y + 1))  # NORTH
        if y > 0:
            potential_neighbors.append((x, y - 1))  # SOUTH
        if x < self.width - 1:
            potential_neighbors.append((x + 1, y))  # EAST
        if x > 0:
            potential_neighbors.append((x - 1, y))  # WEST
        return potential_neighbors

    # Check if two cells are connected
    def is_connected(self, u, v):
        return v in self.graph[u]

    # Get the cost of moving between two cells
    def cost(self, u, v):
        if not self.is_connected(u, v):
            return float('inf')
        return 1

    # Get all nodes in the graph
    def get_all_nodes(self):
        return list(self.graph.keys())


class PriorityQueue:
    def __init__(self):
        self.heap = []
        self.vertex_set = set()

    def peek(self):
        return self.heap[0].vertex

    def peek_priority(self):
        if len(self.heap) == 0:
            return LexicographicPriority(float('inf'), float('inf'))
        return self.heap[0].priority

    def extract_min(self):
        item = heapq.heappop(self.heap)
        self.vertex_set.remove(item.vertex)
        return item.vertex


    def insert(self, vertex, priority):
        if vertex in self.vertex_set:
            self.update(vertex, priority)
        else:
            heapq.heappush(self.heap, QueueNode(priority, vertex))
            self.vertex_set.add(vertex)

    def remove(self, vertex):
        if vertex in self.vertex_set:
            self.vertex_set.remove(vertex)
            for index, node in enumerate(self.heap):
                if node.vertex == vertex:
                    # Replace the node with the last element
                    self.heap[index] = self.heap[-1]
                    self.heap.pop()
                    # Restore the heap property
                    heapq.heapify(self.heap)
                    break

    def update(self, vertex, priority):
        if vertex in self.vertex_set:
            # Find the vertex in the heap
            for index, node in enumerate(self.heap):
                if node.vertex == vertex:
                    self.heap[index].priority = priority
                    # Restore the heap property
                    heapq.heapify(self.heap)
                    break
        else:
            self.insert(vertex, priority)

    def is_empty(self):
        return len(self.heap) == 0

    def log_queue_state(self):
        log("Current Priority Queue:")
        for node in sorted(self.heap, key=lambda x: (x.priority.primary_key, x.priority.secondary_key)):
            log(f"  Vertex: {node.vertex}, Priority: ({node.priority.primary_key}, {node.priority.secondary_key})")

def scan_and_update_walls(start, last, dstar_lite):
    x, y = start
    global explored_cells, final_vertices_updated
    explored_cells.add((x, y))
    directions = [0, 1, 3]  # NORTH, EAST, WEST
    # directions = [0, 1, 2, 3]  # NORTH, EAST, WEST
    log(f"Scanning walls at ({x}, {y}) with orientation {current_orientation}")
    
    wall_detected = False
    updated_vertices = set()

    graph_changed = False

    for direction in directions:
        nx, ny = None, None
        actual_direction = (current_orientation + direction) % 4
        
        if actual_direction == NORTH: 
            nx, ny = x, y + 1
        elif actual_direction == EAST: 
            nx, ny = x + 1, y
        elif actual_direction == SOUTH: 
            nx, ny = x, y - 1
        elif actual_direction == WEST: 
            nx, ny = x - 1, y

        has_wall = check_wall(direction)
        if not has_wall:
            has_wall = check_concreteWall((x, y), (nx, ny))
            graph_changed = True
        
        log(f"Checking wall in direction {direction}: {has_wall}, coords = {(nx, ny)}")

        if valid_position(nx, ny, maze_width, maze_height):
            if has_wall:
                wall_detected = True
                if dstar_lite.graph.remove_edge((x, y), (nx, ny)):
                    graph_changed = True
                log(f"Removing edge: {(x, y)} and {(nx, ny)} and {graph_changed}")
                updated_vertices.add((x, y))
            else:
                if dstar_lite.graph.add_edge((x, y), (nx, ny)):
                    graph_changed = True
                log(f"Added edge between ({x}, {y}) and ({nx, ny}) - no wall detected.")
                updated_vertices.add((x, y))

    log(f"Wall has been detected: {wall_detected}")

    if graph_changed:
            # Recompute the flood fill values from scratch
            dstar_lite.flood_fill_values = flood_fill(dstar_lite.graph, dstar_lite.goals)
            dstar_lite.k_m += dstar_lite.heuristic(last, start)
            dstar_lite.update_vertex(start)
            for u in dstar_lite.graph.get_all_neighbors(start):
                dstar_lite.update_vertex(u)
            dstar_lite.compute_shortest_path()
    
def phase_change_update_vertex(dstar_lite, vertex):
    # Recompute flood fill values
    dstar_lite.flood_fill_values = flood_fill(dstar_lite.graph, dstar_lite.goals)
    dstar_lite.update_vertex(vertex)
    for u in dstar_lite.graph.get_all_neighbors(vertex):
        dstar_lite.update_vertex(u)
    dstar_lite.compute_shortest_path()



# Function to check if there is a wall in a specified direction
def check_wall(direction):
    log(f"Checking wall. Current orientation: {current_orientation}, direction: {direction}")
    if direction == 0:  # Front
        return API.wallFront()
    elif direction == 1:  # Right
        return API.wallRight()
    # elif direction == 2:
    #     return API.wallBack()
    elif direction == 3:  # Left
        return API.wallLeft()

# Function to validate if a given coordinate is within the maze bounds
def valid_position(x, y, width, height):
    return 0 <= x < width and 0 <= y < height

# Move to next position in the simulator
def mms_move_to(prev_position, next_position):

    x, y = prev_position
    next_x, next_y = next_position
    if next_x == x and next_y == y + 1:
        target_orientation = NORTH
    elif next_x == x + 1 and next_y == y:
        target_orientation = EAST
    elif next_x == x and next_y == y - 1:
        target_orientation = SOUTH
    elif next_x == x - 1 and next_y == y:
        target_orientation = WEST
    else:
        log(f"Unexpected move: from ({x}, {y}) to ({next_x}, {next_y}), which is not adjacent.")
        return x, y  # Abort move if something is wrong

    # Adjust the mouse's orientation to face the target direction
    while current_orientation != target_orientation:
        if (target_orientation - current_orientation) % 4 == 1:
            turn_right()
        elif (target_orientation - current_orientation) % 4 == 3:
            turn_left()
        elif (target_orientation - current_orientation) % 4 == 2:
            turn_around()

    # Move forward after turning
    move_forward()

def find_next_position(s_start, graph, g, dstar_lite):
    neighbors = graph.get_accessible_neighbors((x, y))
    log(f"Evaluating neighbors for move from ({x}, {y}): {neighbors}")

    lowest_g = float('inf')
    next_x, next_y = x, y

    # Find the neighbor with the lowest g value
    for nx, ny in neighbors:
        log(f"Neighbor ({nx}, {ny}) has g value {g[(nx, ny)]}")
        if g[(nx, ny)] < lowest_g:
            lowest_g = g[(nx, ny)]
            next_x, next_y = nx, ny

    
    return (next_x, next_y)



def set_virtual_walls_around_unexplored(graph, maze_width, maze_height, explored_cells):
    for x in range(maze_width):
        for y in range(maze_height):
            if (x, y) not in explored_cells:
                # North wall
                if valid_position(x, y + 1, maze_width, maze_height) and (x, y + 1) in explored_cells:
                    graph.remove_edge((x, y), (x, y + 1))
                    API.setWall(x, y, 'n')
                    add_concreteWall((x, y), (x, y + 1))                
                    log(f"Set north wall at ({x}, {y})")
                # East wall
                if valid_position(x + 1, y, maze_width, maze_height) and (x + 1, y) in explored_cells:
                    graph.remove_edge((x, y), (x + 1, y))
                    API.setWall(x, y, 'e')
                    add_concreteWall((x, y), (x + 1, y))
                    log(f"Set east wall at ({x}, {y})")
                # South wall
                if valid_position(x, y - 1, maze_width, maze_height) and (x, y - 1) in explored_cells:
                    graph.remove_edge((x, y), (x, y - 1))
                    API.setWall(x, y, 's')
                    add_concreteWall((x, y), (x, y - 1))
                    log(f"Set south wall at ({x}, {y})")
                # West wall
                if valid_position(x - 1, y, maze_width, maze_height) and (x - 1, y) in explored_cells:
                    graph.remove_edge((x, y), (x - 1, y))
                    API.setWall(x, y, 'w')
                    add_concreteWall((x, y), (x - 1, y))
                    log(f"Set west wall at ({x}, {y})")

    
def show(g, rhs, flood_fill_values, priority_queue=None):
    max_x = max([coord[0] for coord in g.keys()])
    max_y = max([coord[1] for coord in g.keys()])
    
    for y in range(max_y, -1, -1):
        for x in range(max_x + 1):
            flood_fill_value = flood_fill_values.get((x, y), float('inf'))
            flood_fill_str = "i" if flood_fill_value == float('inf') else str(int(flood_fill_value))
            cell_text = f"ff{flood_fill_str}"
            API.setText(x, y, cell_text)


def tick(start, last, graph, dstar_lite):
    prev = start
    start = find_next_position(start, graph, dstar_lite.g, dstar_lite)
    dstar_lite.start = start
    mms_move_to(prev, start)

    # current simulator mouse position
    global x, y
    x, y = start

    last = scan_and_update_walls(start, last, dstar_lite)

    # Display the flood fill values in the simulator
    show(dstar_lite.g, dstar_lite.rhs, dstar_lite.flood_fill_values, dstar_lite.priority_queue)

    return start, last, graph, dstar_lite


def flood_fill_from_start(graph, start):
    distance_map = {node: float('inf') for node in graph.get_all_nodes()}
    queue = deque()
    distance_map[start] = 0
    queue.append(start)

    while queue:
        current = queue.popleft()
        current_distance = distance_map[current]
        for neighbor in graph.get_accessible_neighbors(current):
            if distance_map[neighbor] > current_distance + 1:
                distance_map[neighbor] = current_distance + 1
                queue.append(neighbor)
    return distance_map


def run_d_lite_ff_6():
    try:
        global x, y, current_orientation, phase, steps

        width, height = 6, 6
        start = (0, 0)
        origin = (0, 0)
        x, y = start
        
        # Select a Random goal
        # goal = (random.randrange(0, width - 1), random.randrange(0, height - 1))
        # goals = [goal]
        goals = [(2, 2), (3, 2), (2, 3), (3, 3)]   # Multiple goal cells

        log(f"goals = {goals}", False)

        # Initialize the MazeGraph
        graph = MazeGraph(width, height)

        # Initialize the D* Lite algorithm
        dstar_lite = DStarLite(start, goals, graph)

        # Compute the initial shortest path
        log("Running D* Lite to calculate the initial shortest path.")
        log(f"queue = {dstar_lite.priority_queue.heap}")
        dstar_lite.compute_shortest_path()
        log(f"queue = {dstar_lite.priority_queue.heap}")


        log(f"=====Initial conditions======")
        for key in dstar_lite.graph.graph.keys():
            log(f"key = {key} and value = {dstar_lite.graph.graph[key]}")
        log(f"\n")
        log(f"{dstar_lite.graph.graph}")
        log(f"{dstar_lite.g}")
        log(f"{dstar_lite.rhs}")

        # Initially there are no walls, so before making a first move 
        # we need to check for walls. 
        last = start
        last = scan_and_update_walls(start, last, dstar_lite)

        steps[phase] = 0

        while True:
            log(f"----> Phase: {phase}. Mouse at ({x}, {y}), current orientation: {current_orientation}.")

            # Set color based on the phase
            if phase == "initial":
                API.setColor(x, y, 'y')  # Yellow for the first run
            elif phase == "return":
                API.setColor(x, y, 'b')  # Blue for the return run
            elif phase == "final":
                API.setColor(x, y, 'g')  # Green for the final run

            if phase == 'initial' and start in goals:
                log("Mouse has reached the goal. Switching to return phase.", False)
                phase = 'return'
                steps[phase] = 0

                # Set new goal as the start position
                new_goals = [origin]
                dstar_lite.goals = new_goals
                dstar_lite.initialize(dstar_lite.start, new_goals)
                phase_change_update_vertex(dstar_lite, start)
                continue  # Proceed to the next iteration with updated goals

            if phase == 'return' and start == origin: # original start position
                log("Mouse has returned to the start. Preparing for the final run.", False)
                
                # Set virtual walls around all unexplored cells
                set_virtual_walls_around_unexplored(graph, maze_width, maze_height, explored_cells)

                # Switch to final phase
                phase = 'final'
                steps[phase] = 0

                # Re-initialize the algorithm for the final run
                dstar_lite.goals = goals
                dstar_lite.initialize(dstar_lite.start, goals)
                phase_change_update_vertex(dstar_lite, start)

                continue

            if phase == 'final' and dstar_lite.start in goals:
                log("Mouse has completed the final run.")
                break  # Exit the loop as the task is complete

            start, last, graph, dstar_lite = tick(start, last, graph, dstar_lite)
            steps[phase] += 1

        log("Mouse has completed its run.")
        log(f"\n", False)
        for i in steps.keys():
            log(f"Number of steps in {i} is {steps[i]}", False)


    except Exception as e:
        log(f"Error during D* Lite execution: {e}")
        raise  # Re-raise the exception for further investigation


# Entry point of the program
if __name__ == "__main__":
    try:
        log("Starting D* Lite algorithm...")
        run_d_lite_ff_6()
        log("Finished running D* Lite algorithm.")
    except Exception as e:
        log(f"Error in main execution: {e}")