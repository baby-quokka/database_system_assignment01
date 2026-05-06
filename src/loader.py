from __future__ import annotations  # Use newer type-hint syntax with compatibility

from dataclasses import dataclass  # Create a simple data container class
import csv
from pathlib import Path  # Handle file/folder paths
from typing import List  # List type annotation


# Data class for one student record
@dataclass(frozen=True)  # Read-only object
class StudentRecord:
    student_id: int
    name: str
    gender: str
    gpa: float
    height: float
    weight: float
    

# Load a CSV file and return a list of StudentRecord objects
def load_student_records(csv_path: str | Path) -> List[StudentRecord]:
    path = Path(csv_path)  # Normalize to a Path object
    # Error handling
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")
    
    records: List[StudentRecord] = []  # Empty list for the result (":" is a type hint)
    # Open the CSV file in read mode (with closes the file automatically after the block)
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)  # Read each CSV row as a dictionary, e.g. {"Student ID": "...", "Name": "...", ...}
        # Error handling
        if reader.fieldnames is None:
            raise ValueError("CSV header is missing")
        
        # Iterate over each CSV row -> convert one row into a StudentRecord and append it
        for row in reader:
            records.append(
                StudentRecord(
                    student_id=int(row["Student ID"].strip()),  # strip(): remove whitespace
                    name=row["Name"].strip(),
                    gender=row["Gender"].strip(),
                    gpa=float(row["GPA"].strip()),
                    height=float(row["Height"].strip()),
                    weight=float(row["Weight"].strip()),
                )
            )
        return records
    
    
"""
Test: python -c "from src.loader import load_student_records; r=load_student_records('data/student.csv'); print(len(r)); print(r[0]); print(r[-1])"

100000
StudentRecord(student_id=202038411, name='Pamela Kwak', gender='Female', gpa=3.36, height=160.3, weight=55.2)
StudentRecord(student_id=202217117, name='Eric Woo', gender='Male', gpa=3.1, height=175.1, weight=57.3)
"""

