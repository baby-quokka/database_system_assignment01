from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path
from typing import Dict, List

from b_tree import BTree
from bstar_tree import BStarTree
from bplus_tree import BPlusTree
from loader import StudentRecord, load_student_records


# Build three tree types with the same records and order
def build_trees(records: List[StudentRecord], order: int):
    # Create three empty index structures
    trees = {
        "B-tree": BTree(order),
        "B*-tree": BStarTree(order),
        "B+tree": BPlusTree(order),
    }
    # Insert every record into each tree using Student ID as the key and array index as the RID
    for tree in trees.values():
        for rid, rec in enumerate(records):
            tree.insert(rec.student_id, rid)
    return trees


# Run range queries with different Student ID range widths
def run_range_size_experiment(
    records: List[StudentRecord],
    order: int,
    widths: List[int],
    repeats: int,
) -> List[Dict[str, str]]:
    # Sort keys to choose the middle Student ID as the center of all range queries
    keys = sorted(rec.student_id for rec in records)
    center = keys[len(keys) // 2]
    # Build the trees only once, then reuse them for every range width
    trees = build_trees(records, order)
    rows: List[Dict[str, str]] = []  # Result rows to write into the output CSV

    # Repeat the experiment for each requested Student ID range width
    for width in widths:
        # Create a symmetric range around the center Student ID
        low = center - width // 2
        high = center + width // 2
        # Used to check whether all tree types return the same number of results
        expected_count: int | None = None

        for tree_name, tree in trees.items():
            times: List[float] = []  # Store repeated execution times
            result_count = 0
            # Execute the same range query several times and average the elapsed time
            for _ in range(repeats):
                t0 = time.perf_counter()
                rids = tree.range_query(low, high)
                times.append(time.perf_counter() - t0)
                result_count = len(rids)

            # Correctness check: all trees should return the same number of RIDs for the same range
            if expected_count is None:
                expected_count = result_count
            elif result_count != expected_count:
                raise RuntimeError(
                    f"inconsistent range result count for width={width}: "
                    f"expected {expected_count}, got {result_count} from {tree_name}"
                )

            # Save one CSV row for this tree type and range width
            rows.append(
                {
                    "tree_type": tree_name,
                    "order": str(order),
                    "range_width": str(width),
                    "low": str(low),
                    "high": str(high),
                    "result_count": str(result_count),
                    "selectivity_percent": f"{result_count / len(records) * 100:.6f}",
                    "avg_elapsed_ms": f"{sum(times) / len(times) * 1000:.6f}",
                    "repeats": str(repeats),
                }
            )

    return rows


# Write the experiment rows to a CSV file
def write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    # Configure command line arguments
    parser = argparse.ArgumentParser(description="Range selectivity experiment")
    parser.add_argument("--csv", type=str, default=str(Path("data") / "student.csv"))
    parser.add_argument("--order", type=int, default=10)
    parser.add_argument(
        "--widths",
        nargs="+",
        type=int,
        default=[100, 1000, 10000, 100000, 500000, 1000000],
    )
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument(
        "--output",
        type=str,
        default=str(Path("results") / "range_size_experiment.csv"),
    )
    args = parser.parse_args()

    # Error handling
    if args.repeats < 1:
        raise ValueError("repeats must be >= 1")
    if any(width < 1 for width in args.widths):
        raise ValueError("all range widths must be positive")

    # Load records from the input CSV file
    records = load_student_records(args.csv)
    # Run the additional range-size experiment
    rows = run_range_size_experiment(
        records=records,
        order=args.order,
        widths=args.widths,
        repeats=args.repeats,
    )
    # Save the result CSV file
    write_csv(Path(args.output), rows)
    print(f"range size experiment saved: {args.output}")


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(1)
