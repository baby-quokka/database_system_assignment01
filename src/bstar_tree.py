from __future__ import annotations

from b_tree import BTree, BTreeNode


# B*-tree: try sibling redistribution before splitting
class BStarTree(BTree):
    # insert
    def insert(self, key: int, rid: int) -> None:
        self._insert_nonfull(self.root, key, rid)  # Use B*-tree-specific insertion logic
        # If the root overflows, split only the root with the basic split
        if len(self.root.keys) > self.max_keys:
            promoted_k, promoted_v, right = self._split_overflow_node(self.root)
            self.root = BTreeNode(
                is_leaf=False,
                keys=[promoted_k],
                values=[promoted_v],
                children=[self.root, right],
            )

    # Insert while preventing overflow before descending
    def _insert_nonfull(self, node: BTreeNode, key: int, rid: int) -> None:
        i = self._slot(key, node.keys)  # Compute where the key belongs in the current node

        # 1) Case: leaf node
        if node.is_leaf:
            # If the same key already exists, update the value
            if i < len(node.keys) and node.keys[i] == key:
                node.values[i] = rid
                return
            # Otherwise, insert at the sorted position
            node.keys.insert(i, key)
            node.values.insert(i, rid)
            return

        # 2) Case: internal node
        if i < len(node.keys) and node.keys[i] == key:
            node.values[i] = rid
            return

        # If the child to descend into is full, handle redistribution or 2-to-3 split before splitting
        if len(node.children[i].keys) >= self.max_keys:
            inserted = self._resolve_full_child(node, i, key, rid)
            # If the new key was already redistributed/split at the leaf level, insertion is done
            if inserted:
                return
            # Parent keys may have changed, so recompute the child index
            i = self._slot(key, node.keys)
            if i < len(node.keys) and node.keys[i] == key:
                node.values[i] = rid
                return

        # Descend to the child and continue insertion
        self._insert_nonfull(node.children[i], key, rid)
        # After recursion, recover again if the child still has overflow
        if len(node.children[i].keys) > self.max_keys:
            self._resolve_overflow_child(node, i)

    # Decide how to handle a full child
    def _resolve_full_child(self, parent: BTreeNode, index: int, key: int, rid: int) -> bool:
        # 1) If the right sibling has space, try redistribution first
        if index + 1 < len(parent.children) and len(parent.children[index + 1].keys) < self.max_keys:
            # If this is a leaf, redistribute together with the new key
            if parent.children[index].is_leaf:
                self._redistribute_pair_with_entry(parent, index, key, rid)
                return True
            if self._redistribute_pair(parent, index, key):
                return False
            # If there is no clear room for the incoming key, first perform balanced redistribution
            if self._redistribute_pair(parent, index, None):
                return False

        # 2) If the left sibling has space, try redistribution
        if index > 0 and len(parent.children[index - 1].keys) < self.max_keys:
            if parent.children[index].is_leaf:
                self._redistribute_pair_with_entry(parent, index - 1, key, rid)
                return True
            if self._redistribute_pair(parent, index - 1, key):
                return False
            if self._redistribute_pair(parent, index - 1, None):
                return False

        # 3) If neither sibling has space, perform a 2-to-3 split
        if index + 1 < len(parent.children):
            if parent.children[index].is_leaf:
                self._split_two_three_with_entry(parent, index, key, rid)
                return True
            self._split_two_three(parent, index)
            return False

        if index > 0:
            if parent.children[index].is_leaf:
                self._split_two_three_with_entry(parent, index - 1, key, rid)
                return True
            self._split_two_three(parent, index - 1)
            return False

        # Exceptionally, if there is no sibling, use the basic B-tree split
        promoted_k, promoted_v, right = self._split_overflow_node(parent.children[index])
        parent.keys.insert(index, promoted_k)
        parent.values.insert(index, promoted_v)
        parent.children.insert(index + 1, right)
        return False

    # Recover a child that has already overflowed
    def _resolve_overflow_child(self, parent: BTreeNode, index: int) -> None:
        # 1) If the right sibling has space, redistribute
        if index + 1 < len(parent.children) and len(parent.children[index + 1].keys) < self.max_keys:
            if self._redistribute_pair(parent, index, None):
                return

        # 2) If the left sibling has space, redistribute
        if index > 0 and len(parent.children[index - 1].keys) < self.max_keys:
            if self._redistribute_pair(parent, index - 1, None):
                return

        # 3) If neither works, perform a 2-to-3 split
        if index + 1 < len(parent.children):
            self._split_two_three(parent, index)
            return

        if index > 0:
            self._split_two_three(parent, index - 1)
            return

        # If there is no sibling, use the basic split
        promoted_k, promoted_v, right = self._split_overflow_node(parent.children[index])
        parent.keys.insert(index, promoted_k)
        parent.values.insert(index, promoted_v)
        parent.children.insert(index + 1, right)

    # Redistribute two siblings plus the parent separator key
    def _redistribute_pair(
        self,
        parent: BTreeNode,
        left_idx: int,
        incoming_key: int | None,
    ) -> bool:
        left = parent.children[left_idx]
        right = parent.children[left_idx + 1]
        # Gather left node, parent separator, and right node as one sorted sequence
        entries = (
            list(zip(left.keys, left.values))
            + [(parent.keys[left_idx], parent.values[left_idx])]
            + list(zip(right.keys, right.values))
        )
        # Internal nodes also need their child pointers moved with the key split
        children = left.children + right.children
        split_at = self._pick_redistribute_split(entries, incoming_key)
        # Fail if there is no valid split position
        if split_at is None:
            return False

        # Use the middle key as the parent separator key
        sep_k, sep_v = entries[split_at]
        # Keys before split_at go to the left node, keys after split_at go to the right node
        left_pairs = entries[:split_at]
        right_pairs = entries[split_at + 1 :]

        # Rewrite both siblings with the redistributed key/value pairs
        left.keys = [k for k, _ in left_pairs]
        left.values = [v for _, v in left_pairs]
        right.keys = [k for k, _ in right_pairs]
        right.values = [v for _, v in right_pairs]
        # Update the separator stored in the parent
        parent.keys[left_idx] = sep_k
        parent.values[left_idx] = sep_v

        # If this is an internal node, move child pointers according to the key split
        if not left.is_leaf:
            left.children = children[: split_at + 1]
            right.children = children[split_at + 1 :]

        self.stats.redistribution_count += 1
        return True

    # Redistribute two siblings at a leaf, including the new key
    def _redistribute_pair_with_entry(
        self,
        parent: BTreeNode,
        left_idx: int,
        key: int,
        rid: int,
    ) -> None:
        left = parent.children[left_idx]
        right = parent.children[left_idx + 1]
        # At a leaf, include the new key immediately instead of descending later
        entries = (
            list(zip(left.keys, left.values))
            + [(parent.keys[left_idx], parent.values[left_idx])]
            + list(zip(right.keys, right.values))
            + [(key, rid)]
        )
        entries.sort(key=lambda item: item[0])  # Sort again because the new key is included
        split_at = self._pick_redistribute_split(entries, None)
        if split_at is None:
            raise RuntimeError("B* redistribution could not find valid split")

        # Choose one separator for the parent and split the remaining entries into two leaves
        sep_k, sep_v = entries[split_at]
        left_pairs = entries[:split_at]
        right_pairs = entries[split_at + 1 :]

        # Store the redistributed entries back into the two leaf nodes
        left.keys = [k for k, _ in left_pairs]
        left.values = [v for _, v in left_pairs]
        right.keys = [k for k, _ in right_pairs]
        right.values = [v for _, v in right_pairs]
        # Replace the parent separator with the newly selected separator
        parent.keys[left_idx] = sep_k
        parent.values[left_idx] = sep_v
        self.stats.redistribution_count += 1

    # Choose the separator key position for redistribution
    def _pick_redistribute_split(
        self,
        entries: list[tuple[int, int]],
        incoming_key: int | None,
    ) -> int | None:
        candidates: list[tuple[int, int]] = []
        # Check all possible left/right counts
        for left_count in range(self.min_keys, self.max_keys + 1):
            right_count = len(entries) - left_count - 1
            # Both sides must satisfy B-tree occupancy constraints
            if not (self.min_keys <= right_count <= self.max_keys):
                continue
            # If there is an incoming key, keep only candidates where its target side has free space
            if incoming_key is not None:
                separator = entries[left_count][0]
                target_count = left_count if incoming_key < separator else right_count
                if target_count >= self.max_keys:
                    continue
            # Prefer candidates where the two siblings have similar sizes
            candidates.append((abs(left_count - right_count), left_count))

        # No valid redistribution exists, so the caller should try 2-to-3 split
        if not candidates:
            return None
        candidates.sort()
        return candidates[0][1]  # Choose the most balanced split

    # Split two nodes + one parent key into three nodes + two parent keys
    def _split_two_three(self, parent: BTreeNode, left_idx: int) -> None:
        left = parent.children[left_idx]
        right = parent.children[left_idx + 1]
        # Combine two full siblings and the parent separator into one ordered sequence
        entries = (
            list(zip(left.keys, left.values))
            + [(parent.keys[left_idx], parent.values[left_idx])]
            + list(zip(right.keys, right.values))
        )
        # Internal child pointers must be split into three groups as well
        children = left.children + right.children
        cut1, cut2 = self._pick_two_three_cuts(len(entries))

        # Promote two separators to the parent
        sep1_k, sep1_v = entries[cut1]
        sep2_k, sep2_v = entries[cut2]
        middle = BTreeNode(is_leaf=left.is_leaf)

        # Key groups for left/middle/right
        piece_left = entries[:cut1]
        piece_mid = entries[cut1 + 1 : cut2]
        piece_right = entries[cut2 + 1 :]

        # Rewrite the existing left/right nodes and create a new middle node
        left.keys = [k for k, _ in piece_left]
        left.values = [v for _, v in piece_left]
        middle.keys = [k for k, _ in piece_mid]
        middle.values = [v for _, v in piece_mid]
        right.keys = [k for k, _ in piece_right]
        right.values = [v for _, v in piece_right]

        # If this is an internal node, split children as well
        if not left.is_leaf:
            left.children = children[: cut1 + 1]
            middle.children = children[cut1 + 1 : cut2 + 1]
            right.children = children[cut2 + 1 :]

        # The parent gets two separators, so add one key/child
        parent.keys[left_idx] = sep1_k
        parent.values[left_idx] = sep1_v
        parent.keys.insert(left_idx + 1, sep2_k)
        parent.values.insert(left_idx + 1, sep2_v)
        parent.children.insert(left_idx + 1, middle)
        self.stats.split_count += 1

    # Perform a 2-to-3 split at a leaf, including the new key
    def _split_two_three_with_entry(
        self,
        parent: BTreeNode,
        left_idx: int,
        key: int,
        rid: int,
    ) -> None:
        left = parent.children[left_idx]
        right = parent.children[left_idx + 1]
        # Since this is a leaf-level split, include the incoming key/RID in the split set
        entries = (
            list(zip(left.keys, left.values))
            + [(parent.keys[left_idx], parent.values[left_idx])]
            + list(zip(right.keys, right.values))
            + [(key, rid)]
        )
        entries.sort(key=lambda item: item[0])  # Sort again because the new key is included
        cut1, cut2 = self._pick_two_three_cuts(len(entries))

        # Two entries become parent separators, and the rest become three leaf nodes
        sep1_k, sep1_v = entries[cut1]
        sep2_k, sep2_v = entries[cut2]
        middle = BTreeNode(is_leaf=True)

        # Divide the ordered entries around the two separators
        piece_left = entries[:cut1]
        piece_mid = entries[cut1 + 1 : cut2]
        piece_right = entries[cut2 + 1 :]

        # Store each group into left, middle, and right leaf nodes
        left.keys = [k for k, _ in piece_left]
        left.values = [v for _, v in piece_left]
        middle.keys = [k for k, _ in piece_mid]
        middle.values = [v for _, v in piece_mid]
        right.keys = [k for k, _ in piece_right]
        right.values = [v for _, v in piece_right]

        # Replace one parent separator and insert the second separator plus the middle child
        parent.keys[left_idx] = sep1_k
        parent.values[left_idx] = sep1_v
        parent.keys.insert(left_idx + 1, sep2_k)
        parent.values.insert(left_idx + 1, sep2_v)
        parent.children.insert(left_idx + 1, middle)
        self.stats.split_count += 1

    # Choose cut positions where each node satisfies key-count constraints in a 2-to-3 split
    def _pick_two_three_cuts(self, entry_count: int) -> tuple[int, int]:
        total_node_keys = entry_count - 2  # Number of keys for three nodes after excluding two separators
        candidates: list[tuple[int, int, int, int, int]] = []
        # Try every possible key count for the left and middle nodes
        for left_count in range(self.min_keys, self.max_keys + 1):
            for middle_count in range(self.min_keys, self.max_keys + 1):
                right_count = total_node_keys - left_count - middle_count
                # The right node must also satisfy occupancy constraints
                if not (self.min_keys <= right_count <= self.max_keys):
                    continue
                counts = [left_count, middle_count, right_count]
                # Prefer balanced splits, then prefer smaller maximum node occupancy
                candidates.append((max(counts) - min(counts), max(counts), left_count, middle_count, right_count))

        if not candidates:
            raise RuntimeError("B* 2-to-3 split could not find valid cuts")

        # cut1 is the first promoted separator, cut2 is the second promoted separator
        _, _, left_count, middle_count, _ = min(candidates)
        cut1 = left_count
        cut2 = left_count + 1 + middle_count
        return cut1, cut2

    # Deletion reuses the basic B-tree deletion logic
    def delete(self, key: int) -> bool:
        return super().delete(key)
