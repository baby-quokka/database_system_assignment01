from __future__ import annotations

from dataclasses import dataclass, field  # field: safely create list defaults
from typing import List, Optional  # Optional: this type or None


# Information for one B-tree node
@dataclass
class BTreeNode:
    is_leaf: bool = True  # Whether this node is a leaf
    keys: List[int] = field(default_factory=list)  # Keys stored in this node
    values: List[int] = field(default_factory=list)  # Value(RID) for each key
    children: List["BTreeNode"] = field(default_factory=list)  # Child pointers for internal nodes
    # "BTreeNode": forward reference syntax, used to refer to this class inside its own definition


# Structural cost counters
@dataclass
class TreeStats:
    split_count: int = 0
    merge_count: int = 0
    redistribution_count: int = 0
    


class BTree:
    def __init__(self, order: int) -> None:
        # Error handling
        if order < 3:
            raise ValueError("order must be >= 3")  # If order is 2 or lower, min_keys becomes 0 or less
        self.order = order  # Current order
        self.max_keys = order - 1  # Maximum number of keys
        self.min_keys = (order + 1) // 2 - 1  # Minimum number of keys
        self.root = BTreeNode(is_leaf=True)  # Start with an empty tree
        self.stats = TreeStats()  # Initialize counters
        
    # Compute the starting index for search/insert/delete
    # staticmethod: a function inside the class that does not use self (utility function)
    @staticmethod
    def _slot(key: int, keys: List[int]) -> int:
        i = 0
        while i < len(keys) and key > keys[i]:
            i += 1
        return i
    
    # search
    def search(self, key: int) -> Optional[int]:
        node = self.root
        while True:
            i = self._slot(key, node.keys)  # Use _slot to find the interval where the key belongs
            # If a matching key exists, return the corresponding value
            if i < len(node.keys) and node.keys[i] == key:
                return node.values[i]
            # If this is a leaf and no matching key exists, return None
            if node.is_leaf:
                return None
            # If this is an internal node, go down to the child and repeat
            node = node.children[i]
            
    # insert
    def insert(self, key: int, rid: int) -> None:
        # Check whether a key must be promoted to the parent
        promoted = self._insert_recursive(self.root, key, rid)
        # A promoted item was produced
        if promoted is not None:
            promoted_k, promoted_v, right = promoted  
            self.root = BTreeNode(
                is_leaf=False,
                keys=[promoted_k],
                values=[promoted_v],
                children=[self.root, right],  # Left child is the old root, right child is created by split
            )
        
        
    def _insert_recursive(self, node: BTreeNode, key: int, rid: int) -> Optional[tuple[int, int, BTreeNode]]:
        i = self._slot(key, node.keys)  # Compute where the key belongs in the current node
        
        # 1) Case: leaf node
        if node.is_leaf:
            # If a matching key exists, update the value
            if i < len(node.keys) and node.keys[i] == key:
                node.values[i] = rid
                return None
            # If no matching key exists, insert at i
            node.keys.insert(i, key)
            node.values.insert(i, rid)
            
            # If overflow occurs, split and return promotion information
            if len(node.keys) > self.max_keys:
                return self._split_overflow_node(node)
            
            return None
        
        # 2) Case: internal node
        # If the same key exists in the internal node, update the value
        if i < len(node.keys) and node.keys[i] == key:
            node.values[i] = rid
            return None
        # If no matching key exists, recursively go down to the child
        promoted = self._insert_recursive(node.children[i], key, rid)
        # If the child split and promotion information came up, insert it into this node
        if promoted is not None:
            promoted_k, promoted_v, right = promoted
            node.keys.insert(i, promoted_k)
            node.values.insert(i, promoted_v)  
            node.children.insert(i + 1, right)  # Add the right child created by split
        
        # If overflow occurs, split and return promotion information
        if len(node.keys) > self.max_keys:
            return self._split_overflow_node(node)
        
        return None
        
    # Split handling
    def _split_overflow_node(self, node: BTreeNode) -> tuple[int, int, BTreeNode]:
        mid = len(node.keys) // 2  # Select the middle index
        # Promote the middle key/value to the parent
        promoted_k = node.keys[mid]
        promoted_v = node.values[mid]
        
        # Create the new right node
        right = BTreeNode(is_leaf=node.is_leaf)
        right.keys = node.keys[mid + 1 :]
        right.values = node.values[mid + 1 :]
        # Left (existing) node
        node.keys = node.keys[:mid]
        node.values = node.values[:mid]
        
        # If this is not a leaf node, split the children as well
        if not node.is_leaf:
            right.children = node.children[mid + 1 :]
            node.children = node.children[: mid + 1]
            
        self.stats.split_count += 1  # Count one split
        return promoted_k, promoted_v, right
    
    # Use inorder traversal and return values whose keys are in the range
    def range_query(self, low: int, high: int) -> List[int]:
        found: List[int] = []
        
        # Recursive traversal function
        def visit(node: BTreeNode) -> None:
            # If this is a leaf node, directly check keys and append values in range
            if node.is_leaf:
                for k, v in zip(node.keys, node.values):
                    if low <= k <= high:
                        found.append(v)
                return
            
            # If this is an internal node, traverse in inorder
            for i, k in enumerate(node.keys):  # Create (index, key) pairs
                visit(node.children[i])
                if low <= k <= high:
                    found.append(node.values[i])
            visit(node.children[-1])  # Internal node has k+1 children for k keys, so visit the last child separately
            
        visit(self.root)
        return found
    
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
        def count(node: BTreeNode) -> int:
            return 1 + sum(count(child) for child in node.children)  # 1 means the current node
        
        return count(self.root)
    
    # Used key slots / total key slots
    def utilization(self) -> float:
        total_slots = 0
        used_slots = 0
        
        def walk(node: BTreeNode) -> None:
            nonlocal total_slots, used_slots  # nonlocal lets the inner function modify outer local variables
            total_slots += self.max_keys
            used_slots += len(node.keys)
            for child in node.children:
                walk(child)
                
        walk(self.root)
        return used_slots / total_slots if total_slots else 0.0  # Avoid division by zero

    # Delete
    def delete(self, key: int) -> bool:
        # Case: key to delete does not exist
        if self.search(key) is None:
            return False
        # Case: key to delete exists
        self._delete(self.root, key)
        # If the root is not a leaf and has no keys, promote its only child as the new root
        if not self.root.is_leaf and not self.root.keys:
            self.root = self.root.children[0]
        return True
    
    def _delete(self, node: BTreeNode, key: int) -> None:
        i = self._slot(key, node.keys)
        
        # Case: key exists in the current node
        if i < len(node.keys) and node.keys[i] == key:
            # If this is a leaf node, delete directly
            if node.is_leaf:
                node.keys.pop(i)
                node.values.pop(i)
            # If this is an internal node, handle separately
            else:
                self._delete_internal_key(node, i)
            return
        
        # Case: key does not exist in the current node
        # If this is a leaf node, stop
        if node.is_leaf:
            return
        
        # If this is an internal node, recursively go down to children[i]
        self._delete(node.children[i], key)
        # Check underflow after deletion in the child
        if len(node.children[i].keys) < self.min_keys:
            self._rebalance_child(node, i)  # Rebalance
    
    # Delete a key from an internal node
    def _delete_internal_key(self, node: BTreeNode, index: int) -> None:
        # Replace with the maximum of the left subtree (predecessor) or the minimum of the right subtree (successor)
        left = node.children[index]
        right = node.children[index + 1]

        # If the left child is not empty, use the predecessor
        if left.keys:
            pk, pv = self._take_max(left)
            node.keys[index] = pk
            node.values[index] = pv
            self._delete(left, pk)  # Delete the actual predecessor key
            # If underflow occurs after deletion, rebalance
            if len(left.keys) < self.min_keys:
                self._rebalance_child(node, index)
        # Otherwise, use the successor from the right child
        else:
            sk, sv = self._take_min(right)
            node.keys[index] = sk
            node.values[index] = sv
            self._delete(right, sk)  # Delete the actual successor key
            # If underflow occurs after deletion, rebalance
            if len(right.keys) < self.min_keys:
                self._rebalance_child(node, index + 1)

    def _take_min(self, node: BTreeNode) -> tuple[int, int]:
        # Keep going to the leftmost child to find the minimum key
        while not node.is_leaf:
            node = node.children[0]
        return node.keys[0], node.values[0]

    def _take_max(self, node: BTreeNode) -> tuple[int, int]:
        # Keep going to the rightmost child to find the maximum key
        while not node.is_leaf:
            node = node.children[-1]
        return node.keys[-1], node.values[-1]

    def _rebalance_child(self, parent: BTreeNode, index: int) -> None:
        # If the minimum key condition is already satisfied, no rebalancing is needed
        if len(parent.children[index].keys) >= self.min_keys:
            return
        # 1) Borrow from the left sibling if possible
        if index > 0 and len(parent.children[index - 1].keys) > self.min_keys:
            self._borrow_from_prev(parent, index)
        # 2) Borrow from the right sibling if possible
        elif index + 1 < len(parent.children) and len(parent.children[index + 1].keys) > self.min_keys:
            self._borrow_from_next(parent, index)
        # 3) If borrowing is impossible and merge is possible, merge
        elif index > 0 and self._can_merge(parent, index - 1):
            self._merge_children(parent, index - 1)
        elif index + 1 < len(parent.children) and self._can_merge(parent, index):
            self._merge_children(parent, index)
        # 4) If merge is also impossible, force redistribution
        else:
            self._redistribute_children(parent, max(0, index - 1))

    def _can_merge(self, parent: BTreeNode, left_index: int) -> bool:
        # Merge is possible if left + one parent key + right fits within max_keys
        left = parent.children[left_index]
        right = parent.children[left_index + 1]
        return len(left.keys) + 1 + len(right.keys) <= self.max_keys

    def _borrow_from_prev(self, parent: BTreeNode, index: int) -> None:
        # Borrow one key from the left sibling
        child = parent.children[index]
        sibling = parent.children[index - 1]
        # Move the parent separator key to the front of the child
        child.keys.insert(0, parent.keys[index - 1])
        child.values.insert(0, parent.values[index - 1])
        # If this is an internal node, move one child pointer too
        if not child.is_leaf:
            child.children.insert(0, sibling.children.pop())
        # Move the left sibling's last key to the parent and update the separator
        parent.keys[index - 1] = sibling.keys.pop()
        parent.values[index - 1] = sibling.values.pop()
        self.stats.redistribution_count += 1

    def _borrow_from_next(self, parent: BTreeNode, index: int) -> None:
        # Borrow one key from the right sibling
        child = parent.children[index]
        sibling = parent.children[index + 1]
        # Move the parent separator key to the back of the child
        child.keys.append(parent.keys[index])
        child.values.append(parent.values[index])
        # If this is an internal node, move one child pointer too
        if not child.is_leaf:
            child.children.append(sibling.children.pop(0))
        # Move the right sibling's first key to the parent and update the separator
        parent.keys[index] = sibling.keys.pop(0)
        parent.values[index] = sibling.values.pop(0)
        self.stats.redistribution_count += 1

    def _merge_children(self, parent: BTreeNode, index: int) -> None:
        # Merge left/right into one node with parent[index] between them
        left = parent.children[index]
        right = parent.children.pop(index + 1)
        left.keys.append(parent.keys.pop(index))
        left.values.append(parent.values.pop(index))
        left.keys.extend(right.keys)
        left.values.extend(right.values)
        # If this is an internal node, append child pointers too
        if not left.is_leaf:
            left.children.extend(right.children)
        self.stats.merge_count += 1

    def _redistribute_children(self, parent: BTreeNode, left_index: int) -> None:
        # If merge is impossible, evenly redistribute left/right plus the parent separator key
        left = parent.children[left_index]
        right = parent.children[left_index + 1]
        entries = (
            list(zip(left.keys, left.values))
            + [(parent.keys[left_index], parent.values[left_index])]
            + list(zip(right.keys, right.values))
        )
        # If this is an internal node, children must be rearranged too
        children = left.children + right.children
        split_at = len(entries) // 2

        # Use the middle entry as the parent separator key
        parent.keys[left_index], parent.values[left_index] = entries[split_at]
        left_pairs = entries[:split_at]
        right_pairs = entries[split_at + 1 :]

        left.keys = [k for k, _ in left_pairs]
        left.values = [v for _, v in left_pairs]
        right.keys = [k for k, _ in right_pairs]
        right.values = [v for _, v in right_pairs]

        # If this is an internal node, align child pointers with the key split
        if not left.is_leaf:
            left.children = children[: split_at + 1]
            right.children = children[split_at + 1 :]
        self.stats.redistribution_count += 1
