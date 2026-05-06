from __future__ import annotations

from bisect import bisect_left, bisect_right  # Quickly find key positions in a sorted list
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# Information for one B+tree node
@dataclass
class BPlusNode:
    is_leaf: bool  # Whether this node is a leaf
    keys: List[int] = field(default_factory=list)  # Keys stored in this node
    children: List["BPlusNode"] = field(default_factory=list)  # Child pointers for internal nodes
    rids: List[int] = field(default_factory=list)  # Values(RIDs) stored only in leaf nodes
    next_leaf: Optional["BPlusNode"] = None  # Next leaf pointer for fast range queries


class BPlusTree:
    def __init__(self, order: int) -> None:
        # Error handling
        if order < 3:
            raise ValueError("order must be >= 3")
        self.order = order  # Current order, maximum number of child pointers
        self.max_keys = order - 1  # Maximum number of keys
        self.min_internal_keys = (order + 1) // 2 - 1  # Minimum number of keys in an internal node
        self.min_leaf_keys = order // 2  # Minimum number of keys in a leaf node
        self.root = BPlusNode(is_leaf=True)  # Start with an empty leaf node
        self.split_count = 0  # split counter
        self.merge_count = 0  # merge counter
        self.redistribution_count = 0  # redistribution counter

    # search
    def search(self, key: int) -> Optional[int]:
        leaf = self._leaf_for_key(key)  # Find the leaf that may contain the key
        i = bisect_left(leaf.keys, key)  # Find the key position inside the leaf
        # If a matching key exists, return the corresponding RID
        if i < len(leaf.keys) and leaf.keys[i] == key:
            return leaf.rids[i]
        return None

    # insert
    def insert(self, key: int, rid: int) -> None:
        maybe = self._insert_inner(self.root, key, rid)  # Result of recursive insertion
        # If split information comes up from the root, create a new root
        if maybe is not None:
            sep, right = maybe
            self.root = BPlusNode(is_leaf=False, keys=[sep], children=[self.root, right])

    # Delete
    def delete(self, key: int) -> bool:
        # Case: key to delete does not exist
        if self.search(key) is None:
            return False
        # Case: key to delete exists
        self._delete_recursive(self.root, key)
        # If the root is empty and not a leaf, promote its only child as the new root
        if not self.root.is_leaf and not self.root.keys:
            self.root = self.root.children[0]
        return True

    # range query
    def range_query(self, low: int, high: int) -> List[int]:
        out: List[int] = []
        leaf = self._leaf_for_low(low)  # Start from the first leaf where low may belong
        while leaf is not None:
            for k, rid in zip(leaf.keys, leaf.rids):
                if k > high:
                    return out
                if k >= low:
                    out.append(rid)
            leaf = leaf.next_leaf  # Move directly to the next leaf
        return out

    # Used key slots / total key slots
    def utilization(self) -> float:
        slot = 0
        used = 0
        stack = [self.root]
        while stack:
            cur = stack.pop()
            slot += self.max_keys
            used += len(cur.keys)
            stack.extend(cur.children)
        return used / slot if slot else 0.0  # Avoid division by zero

    # Final height
    def height(self) -> int:
        node = self.root
        h = 0
        while node.children:
            node = node.children[0]
            h += 1
        return h

    # Total number of nodes
    def node_count(self) -> int:
        stack = [self.root]
        count = 0
        while stack:
            node = stack.pop()
            count += 1
            stack.extend(node.children)
        return count

    # Compute the minimum number of keys depending on node type
    def _min_keys(self, node: BPlusNode) -> int:
        return self.min_leaf_keys if node.is_leaf else self.min_internal_keys

    # Find the leaf that may contain the key
    def _leaf_for_key(self, key: int) -> BPlusNode:
        node = self.root
        while not node.is_leaf:
            idx = bisect_right(node.keys, key)  # If the key is equal, go to the right child
            node = node.children[idx]
        return node

    # Find the first leaf that can contain a key greater than or equal to low
    def _leaf_for_low(self, low: int) -> BPlusNode:
        node = self.root
        while not node.is_leaf:
            idx = bisect_left(node.keys, low)
            node = node.children[idx]
        return node

    # Find the first key in the leftmost leaf of a subtree
    def _leaf_first_key(self, node: BPlusNode) -> int:
        while not node.is_leaf:
            node = node.children[0]
        return node.keys[0]

    # Recursive insertion: return (separator, right_node) if split occurs
    def _insert_inner(
        self,
        node: BPlusNode,
        key: int,
        rid: int,
    ) -> Optional[Tuple[int, BPlusNode]]:
        # 1) Case: leaf node
        if node.is_leaf:
            idx = bisect_left(node.keys, key)
            # If the same key already exists, update the RID
            if idx < len(node.keys) and node.keys[idx] == key:
                node.rids[idx] = rid
                return None
            # Otherwise, insert at the sorted position
            node.keys.insert(idx, key)
            node.rids.insert(idx, rid)
            if len(node.keys) <= self.max_keys:
                return None
            return self._split_leaf(node)

        # 2) Case: internal node
        child_index = bisect_right(node.keys, key)
        maybe = self._insert_inner(node.children[child_index], key, rid)
        # If the child did not split, only refresh separators
        if maybe is None:
            self._refresh_all_seps(node)
            return None

        # If split information comes up from the child, insert it into this node
        separator, right = maybe
        node.keys.insert(child_index, separator)
        node.children.insert(child_index + 1, right)
        if len(node.keys) <= self.max_keys:
            self._refresh_all_seps(node)
            return None
        return self._split_internal(node)

    # Leaf split handling
    def _split_leaf(self, leaf: BPlusNode) -> Tuple[int, BPlusNode]:
        left_count = (self.order + 1) // 2  # Number of keys to keep in the left leaf
        right = BPlusNode(is_leaf=True)
        right.keys = leaf.keys[left_count:]
        right.rids = leaf.rids[left_count:]
        leaf.keys = leaf.keys[:left_count]
        leaf.rids = leaf.rids[:left_count]
        # Connect leaf nodes with the next_leaf pointer
        right.next_leaf = leaf.next_leaf
        leaf.next_leaf = right
        self.split_count += 1
        return right.keys[0], right  # The first key of the right leaf becomes the separator

    # Internal node split handling
    def _split_internal(self, node: BPlusNode) -> Tuple[int, BPlusNode]:
        left_child_count = (len(node.children) + 1) // 2  # Number of children to keep on the left
        right = BPlusNode(is_leaf=False)
        right.children = node.children[left_child_count:]
        node.children = node.children[:left_child_count]
        # B+tree internal keys are separators based on children, so recompute them
        self._refresh_all_seps(node)
        self._refresh_all_seps(right)
        sep = self._leaf_first_key(right.children[0])
        self.split_count += 1
        return sep, right

    # Recursive deletion: return whether underflow occurred
    def _delete_recursive(self, node: BPlusNode, key: int) -> bool:
        # If this is a leaf node, delete directly
        if node.is_leaf:
            idx = bisect_left(node.keys, key)
            if idx < len(node.keys) and node.keys[idx] == key:
                node.keys.pop(idx)
                node.rids.pop(idx)
            return node is not self.root and len(node.keys) < self._min_keys(node)

        # If this is an internal node, go down to the child and delete
        child_idx = bisect_right(node.keys, key)
        under = self._delete_recursive(node.children[child_idx], key)
        # If underflow occurs in the child, rebalance
        if under:
            self._rebalance_child(node, child_idx)
        self._refresh_all_seps(node)
        return node is not self.root and len(node.keys) < self._min_keys(node)

    # Recompute all internal node separators based on children
    def _refresh_all_seps(self, node: BPlusNode) -> None:
        if not node.is_leaf:
            node.keys = [self._leaf_first_key(child) for child in node.children[1:]]

    # Recover child underflow
    def _rebalance_child(self, parent: BPlusNode, idx: int) -> None:
        child = parent.children[idx]
        left = parent.children[idx - 1] if idx > 0 else None
        right = parent.children[idx + 1] if idx + 1 < len(parent.children) else None
        min_keys = self._min_keys(child)

        # 1) Borrow from the left sibling if possible
        if left is not None and len(left.keys) > self._min_keys(left):
            if child.is_leaf:
                child.keys.insert(0, left.keys.pop())
                child.rids.insert(0, left.rids.pop())
            else:
                child.children.insert(0, left.children.pop())
                self._refresh_all_seps(left)
                self._refresh_all_seps(child)
            self.redistribution_count += 1
            self._refresh_all_seps(parent)
            return

        # 2) Borrow from the right sibling if possible
        if right is not None and len(right.keys) > self._min_keys(right):
            if child.is_leaf:
                child.keys.append(right.keys.pop(0))
                child.rids.append(right.rids.pop(0))
            else:
                child.children.append(right.children.pop(0))
                self._refresh_all_seps(child)
                self._refresh_all_seps(right)
            self.redistribution_count += 1
            self._refresh_all_seps(parent)
            return

        # 3) If borrowing is impossible and merge is possible, merge
        if left is not None and len(left.keys) + len(child.keys) <= self.max_keys:
            self._merge_nodes(parent, idx - 1)
        elif right is not None and len(child.keys) + len(right.keys) <= self.max_keys:
            self._merge_nodes(parent, idx)
        elif len(child.keys) < min_keys:
            raise RuntimeError("B+tree rebalancing failed to restore minimum occupancy")

    # Merge parent.children[left_idx] and the right child into one node
    def _merge_nodes(self, parent: BPlusNode, left_idx: int) -> None:
        left = parent.children[left_idx]
        right = parent.children.pop(left_idx + 1)
        parent.keys.pop(left_idx)
        # If this is a leaf node, append keys/values and next_leaf
        if left.is_leaf:
            left.keys.extend(right.keys)
            left.rids.extend(right.rids)
            left.next_leaf = right.next_leaf
        # If this is an internal node, append child pointers and recompute separators
        else:
            left.children.extend(right.children)
            self._refresh_all_seps(left)
        self.merge_count += 1
