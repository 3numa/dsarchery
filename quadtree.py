# quadtree.py
# The main data structure for this project.
# Divides 2D space into quadrants recursively so we only check
# collisions between objects that are actually close to each other.

MAX_OBJECTS = 2   # max objects per node before it splits — finer partitions
MAX_DEPTH   = 6   # hard cap to prevent infinite recursion


class Rect:
    """A simple axis-aligned bounding box."""
    def __init__(self, x, y, w, h):
        self.x = x   # top-left corner
        self.y = y
        self.w = w
        self.h = h

    def contains(self, px, py):
        """Is a point inside this rect?"""
        return self.x <= px < self.x + self.w and self.y <= py < self.y + self.h

    def intersects(self, other):
        """Do two rects overlap?"""
        return not (other.x > self.x + self.w or
                    other.x + other.w < self.x or
                    other.y > self.y + self.h  or
                    other.y + other.h < self.y)

    def __repr__(self):
        return f"Rect({self.x:.0f}, {self.y:.0f}, {self.w:.0f}, {self.h:.0f})"


class QuadTree:
    def __init__(self, boundary: Rect, depth: int = 0):
        self.boundary = boundary   # the Rect this node covers
        self.depth    = depth
        self.objects  = []         # objects stored at this node
        self.children = None       # None until this node splits (list of 4)

    def _subdivide(self):
        """Split into 4 equal quadrants: NW, NE, SW, SE."""
        x, y, w, h = self.boundary.x, self.boundary.y, self.boundary.w, self.boundary.h
        hw, hh = w / 2, h / 2
        d = self.depth + 1
        self.children = [
            QuadTree(Rect(x, y, hw, hh), d),  # NW
            QuadTree(Rect(x + hw, y, hw, hh), d),  # NE
            QuadTree(Rect(x, y + hh, hw, hh), d),  # SW
            QuadTree(Rect(x + hw, y + hh, hw, hh), d),  # SE
        ]

    def insert(self, obj) -> bool:
        """
        Insert an object into the tree.
        Object must have .x, .y, .w, .h attributes (screen-space bounding box).
        Returns True if inserted successfully.
        """
        obj_rect = Rect(obj.x, obj.y, obj.w, obj.h)
        if not self.boundary.intersects(obj_rect):
            return False

        # store here if there's room or we've hit max depth
        if len(self.objects) < MAX_OBJECTS or self.depth >= MAX_DEPTH:
            self.objects.append(obj)
            return True

        # otherwise subdivide (if not already) and push down
        if self.children is None:
            self._subdivide()

        for child in self.children:
            child.insert(obj)

        return True

    def query(self, query_rect: Rect, found: list = None) -> list:
        """
        Return all objects whose bounding boxes overlap with query_rect.
        This is what makes collision detection fast — we skip entire subtrees
        that don't intersect the query region.
        """
        if found is None:
            found = []

        if not self.boundary.intersects(query_rect):
            return found

        for obj in self.objects:
            if query_rect.intersects(Rect(obj.x, obj.y, obj.w, obj.h)):
                found.append(obj)

        if self.children:
            for child in self.children:
                child.query(query_rect, found)

        return found

    def clear(self):
        """Wipe the tree — called at the start of each frame."""
        self.objects  = []
        self.children = None

    def get_leaf_boundaries(self, result: list = None) -> list:
        """Collect all occupied leaf node rects (used by renderer to draw the grid overlay)."""
        if result is None:
            result = []

        if self.children is None:
            if self.objects:
                result.append(self.boundary)
        else:
            for child in self.children:
                child.get_leaf_boundaries(result)

        return result
