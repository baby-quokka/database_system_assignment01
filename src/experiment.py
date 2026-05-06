from __future__ import annotations

import argparse
import csv
import random
import time
from pathlib import Path
from typing import Dict, Iterable, List

from b_tree import BTree
from bstar_tree import BStarTree
from bplus_tree import BPlusTree
from loader import StudentRecord, load_student_records


# Measure insertion time for all records
def workload_insertion(tree, records: List[StudentRecord]) -> float:
    t0 = time.perf_counter()
    for rid, rec in enumerate(records):
        tree.insert(rec.student_id, rid)
    return time.perf_counter() - t0


# Measure point search time
def workload_point_search(tree, keys: Iterable[int]) -> float:
    t0 = time.perf_counter()
    for key in keys:
        tree.search(key)
    return time.perf_counter() - t0


# Measure range query time and return result RIDs
def workload_range_query(tree, low: int, high: int) -> tuple[float, List[int]]:
    t0 = time.perf_counter()
    rids = tree.range_query(low, high)
    elapsed = time.perf_counter() - t0
    return elapsed, rids


# Measure random deletion time
def workload_deletion(tree, keys_to_delete: Iterable[int]) -> float:
    t0 = time.perf_counter()
    for key in keys_to_delete:
        tree.delete(key)
    return time.perf_counter() - t0


# Compute the total number of keys in the tree
def total_key_count(tree) -> int:
    root = getattr(tree, "root", None)
    # If there is no root, return 0
    if root is None:
        return 0
    count = 0
    stack = [root]
    while stack:
        node = stack.pop()
        count += len(node.keys)  # Add the number of keys in the current node
        stack.extend(node.children)
    return count


# Compute the number of actual record payloads
def total_record_count(tree) -> int:
    root = getattr(tree, "root", None)
    # If there is no root, return 0
    if root is None:
        return 0
    count = 0
    stack = [root]
    while stack:
        node = stack.pop()
        # In a B+tree, only leaf-node rids are actual record payloads
        if hasattr(node, "rids"):
            if getattr(node, "is_leaf", False):
                count += len(node.rids)
        else:
            count += len(node.keys)  # B-tree/B*-tree have one value per key
        stack.extend(node.children)
    return count


# Collect common experiment metrics
def collect_metrics(tree) -> Dict[str, float]:
    stat_source = getattr(tree, "stats", tree)  # B-tree family stores counters in stats
    split_count = getattr(stat_source, "split_count", 0)
    merge_count = getattr(stat_source, "merge_count", 0)
    redistribution_count = getattr(stat_source, "redistribution_count", 0)
    return {
        "height": tree.height() if hasattr(tree, "height") else 0,
        "node_count": tree.node_count() if hasattr(tree, "node_count") else 0,
        "key_count": total_key_count(tree),
        "record_count": total_record_count(tree),
        "utilization": tree.utilization(),
        "split_count": split_count,
        "merge_count": merge_count,
        "redistribution_count": redistribution_count,
    }


# Add one workload result row
def add_workload_row(
    rows: List[Dict[str, float | int | str]],
    tree_name: str,
    order: int,
    workload: str,
    query_count: int,
    elapsed: float,
    metrics: Dict[str, float],
) -> None:
    mean = (elapsed / query_count) if query_count else elapsed  # Compute mean time
    rows.append(
        {
            "tree_type": tree_name,
            "order": order,
            "workload": workload,
            "query_count": query_count,
            "elapsed_seconds": elapsed,
            "mean_seconds": mean,
            "height": int(metrics["height"]),
            "node_count": int(metrics["node_count"]),
            "key_count": int(metrics["key_count"]),
            "record_count": int(metrics["record_count"]),
            "split_count": int(metrics["split_count"]),
            "merge_count": int(metrics["merge_count"]),
            "redistribution_count": int(metrics["redistribution_count"]),
            "utilization": metrics["utilization"],
        }
    )


# Run experiments for three trees with one order
def run_one_order(
    records: List[StudentRecord],
    order: int,
    n_search: int,
    n_delete: int,
    range_low: int,
    range_high: int,
) -> tuple[List[Dict[str, float | int | str]], List[Dict[str, str]]]:
    keys = [r.student_id for r in records]  # Full student_id list
    search_keys = random.sample(keys, k=min(n_search, len(keys)))  # Key samples for search
    delete_keys = random.sample(keys, k=min(n_delete, len(keys)))  # Key samples for delete

    # Create three tree types with the same order
    trees = {
        "B-tree": BTree(order),
        "B*-tree": BStarTree(order),
        "B+tree": BPlusTree(order),
    }

    workload_rows: List[Dict[str, float | int | str]] = []
    range_rows: List[Dict[str, str]] = []

    for name, tree in trees.items():
        print(f"\n[{name}] order={order}")

        # 1) Full insertion experiment
        t_insert = workload_insertion(tree, records)
        m_insert = collect_metrics(tree)
        add_workload_row(workload_rows, name, order, "insert_all", len(records), t_insert, m_insert)
        print(f" insertion_time: {t_insert:.6f}s")
        print(f" utilization: {m_insert['utilization']:.4f}")
        print(f" split_count: {int(m_insert['split_count'])}")

        # 2) Point search experiment
        t_search = workload_point_search(tree, search_keys)
        m_search = collect_metrics(tree)
        add_workload_row(workload_rows, name, order, "point_search", len(search_keys), t_search, m_search)
        print(f" point_search_time: {t_search:.6f}s")

        # 3) Range query experiment
        t_range, range_rids = workload_range_query(tree, range_low, range_high)
        m_range = collect_metrics(tree)
        add_workload_row(workload_rows, name, order, "range_query", 1, t_range, m_range)
        print(f" range_query_time: {t_range:.6f}s")

        # Filter only Male records from the range result and compute averages
        male_records = [records[rid] for rid in range_rids if records[rid].gender == "Male"]
        male_count = len(male_records)
        avg_male_gpa = (sum(r.gpa for r in male_records) / male_count) if male_count else 0.0
        avg_male_height = (sum(r.height for r in male_records) / male_count) if male_count else 0.0
        range_rows.append(
            {
                "tree_type": name,
                "order": str(order),
                "low": str(range_low),
                "high": str(range_high),
                "male_count": str(male_count),
                "avg_male_gpa": f"{avg_male_gpa:.6f}",
                "avg_male_height": f"{avg_male_height:.6f}",
                "elapsed_seconds": f"{t_range:.9f}",
            }
        )

        # 4) Random deletion experiment
        t_delete = workload_deletion(tree, delete_keys)
        m_delete = collect_metrics(tree)
        add_workload_row(workload_rows, name, order, "delete_random", len(delete_keys), t_delete, m_delete)
        print(f" deletion_time: {t_delete:.6f}s")

    return workload_rows, range_rows


# Common CSV writer
def write_csv(path: Path, rows: List[Dict[str, float | int | str]]) -> None:
    # If rows are empty, do not create a file
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


# CSV writer for range analysis
def write_range_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "tree_type",
        "order",
        "low",
        "high",
        "male_count",
        "avg_male_gpa",
        "avg_male_height",
        "elapsed_seconds",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    # Configure command line arguments
    parser = argparse.ArgumentParser(description="CSE321 Project #1 experiment runner")
    parser.add_argument("--csv", type=str, default=str(Path("data") / "student.csv"))
    parser.add_argument("--orders", nargs="+", type=int, default=[3, 5, 10])
    parser.add_argument("--n-search", type=int, default=10000)
    parser.add_argument("--n-delete", type=int, default=2000)
    parser.add_argument("--range-low", type=int, default=202000000)
    parser.add_argument("--range-high", type=int, default=202100000)
    parser.add_argument("--seed", type=int, default=321)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--output", type=str, default="results")
    args = parser.parse_args()

    records = load_student_records(args.csv)
    # If limit is given, use only the first records
    if args.limit > 0:
        records = records[: args.limit]
    print(f"loaded_records: {len(records)}")
    random.seed(args.seed)

    all_workload_rows: List[Dict[str, float | int | str]] = []
    all_range_rows: List[Dict[str, str]] = []
    # Repeat the same experiment for each order
    for order in args.orders:
        rows, range_rows = run_one_order(
            records=records,
            order=order,
            n_search=args.n_search,
            n_delete=args.n_delete,
            range_low=args.range_low,
            range_high=args.range_high,
        )
        all_workload_rows.extend(rows)
        all_range_rows.extend(range_rows)

    output_dir = Path(args.output)
    workload_path = output_dir / "workload_results.csv"
    range_path = output_dir / "range_analysis.csv"
    # Save result CSV files
    write_csv(workload_path, all_workload_rows)
    write_range_csv(range_path, all_range_rows)
    print(f"\nresults saved: {workload_path}")
    print(f"range analysis saved: {range_path}")


if __name__ == "__main__":
    main()


"""
Test: python src\experiment.py --csv data\student.csv --orders 3 5 10 --n-search 10000 --n-delete 2000 --range-low 202000000 --range-high 202100000 --seed 321 --output results
"""
