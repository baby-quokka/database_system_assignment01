# CSE321 Assignment #1

# Environment
- Python 3.10 or later
- No external libraries required

# Order Definition
- `order d`: maximum number of child pointers in a node
- Maximum number of keys: `d - 1`
- Minimum number of keys in a non-root B-tree/B*-tree node: `ceil(d / 2) - 1`
- Minimum number of keys in a B+tree internal node: `ceil(d / 2) - 1`
- Minimum number of keys in a B+tree leaf node: `floor(d / 2)`

# Project Structure
- `src/loader.py`: reads the CSV file and converts rows into a list of `StudentRecord` objects
- `src/b_tree.py`: basic B-tree implementation
- `src/bstar_tree.py`: B*-tree implementation using redistribution and 2-to-3 split
- `src/bplus_tree.py`: B+tree implementation with linked leaf nodes
- `src/experiment.py`: runs experiments and writes result CSV files
- `src/range_size_experiment.py`: runs the additional range-width experiment

# Run Experiments
```bash
python src\experiment.py --csv data\student.csv --orders 3 5 10 --n-search 10000 --n-delete 2000 --range-low 202000000 --range-high 202100000 --seed 321 --output results
```

# Additional Range Size Experiment
```bash
python src\range_size_experiment.py --csv data\student.csv --order 10 --widths 100 1000 10000 100000 500000 1000000 --repeats 7 --output results\range_size_experiment.csv
```

# Output Files
- `results/workload_results.csv`: stores execution time, height, node count, split/merge/redistribution count, and utilization for each workload
- `results/range_analysis.csv`: stores the number of male students, average GPA, and average height in the selected Student ID range
- `results/range_size_experiment.csv`: stores range-query time for different Student ID range widths and selectivity values

# Implementation Notes
- `Student ID` is used as the key.
- The RID is the array index of each record loaded from the CSV file.
- The B+tree stores actual RIDs only in leaf nodes.
- B*-tree insertion follows B*-tree-specific policies, including sibling redistribution and 2-to-3 split. For deletion, the implementation applies the same underflow handling and rebalancing strategy as the basic B-tree implementation.
