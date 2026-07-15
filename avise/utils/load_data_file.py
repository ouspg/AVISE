"""Data file loader."""

import csv
import json
import pickle
from pathlib import Path


def load_data_file(filepath: str) -> list:
    """Loads data from a file into a list.

    Supported formats:
        .txt        — one item per line
        .csv        — list of dicts (one per row)
        .tsv        — list of dicts (one per row, tab-separated)
        .json       — parsed JSON (wrapped in list if not already)
        .jsonl      — list of parsed JSON objects (one per line)
        .xml        — list of child elements under root
        .yaml/.yml  — parsed YAML (wrapped in list if not already)
        .xlsx/.xls  — list of dicts (one per row)
        .parquet    — list of row dicts
        .pkl        — unpickled object (wrapped in list if not already)

    Args:
        filepath: Path to the file.

    Returns:
        A list containing the loaded data.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file extension is unsupported.
    """
    path = Path(filepath)

    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {filepath}")

    ext = path.suffix.lower()

    # .txt — one item per line
    if ext == ".txt":
        with open(path, "r", encoding="utf-8") as f:
            return [line.rstrip("\n") for line in f]

    # .csv — list of row dicts
    elif ext == ".csv":
        with open(path, "r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    # .tsv — list of row dicts (tab-separated)
    elif ext == ".tsv":
        with open(path, "r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f, delimiter="\t"))

    # .json — parsed JSON, normalised to a list
    elif ext == ".json":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else [data]

    # .jsonl — one JSON object per line
    elif ext == ".jsonl":
        with open(path, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    # .xml — list of child elements under root
    elif ext == ".xml":
        from xml.etree import ElementTree as ET

        tree = ET.parse(path)
        return list(tree.getroot())

    # .yaml / .yml
    elif ext in (".yaml", ".yml"):
        import yaml

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, list) else [data]

    # .xlsx / .xls — list of row dicts
    elif ext in (".xlsx", ".xls"):
        import openpyxl

        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        headers = rows[0]
        return [dict(zip(headers, row)) for row in rows[1:]]

    # .parquet — list of row dicts
    elif ext == ".parquet":
        import pandas as pd

        return pd.read_parquet(path).to_dict(orient="records")

    # .pkl — unpickled object, normalised to a list
    elif ext == ".pkl" or ext == "":  # handle both .pkl and extensionless
        with open(path, "rb") as f:
            data = pickle.load(f, encoding="bytes")

        # CIFAR-style bulk dict → per-sample list
        if isinstance(data, dict) and b"data" in data and b"fine_labels" in data:
            pixel_arrays = data[b"data"]  # (N, 3072) uint8
            labels = data[b"fine_labels"]  # list of N ints
            return [
                {
                    "image": pixel_arrays[i]  # raw 3072-element flat array for now
                    .reshape(3, 32, 32)  # CHW
                    .transpose(1, 2, 0),  # → HWC (32, 32, 3) uint8
                    "label": int(labels[i]),
                }
                for i in range(len(labels))
            ]

        return data if isinstance(data, list) else [data]

    else:
        raise ValueError(f"Unsupported file type for data: '{ext}'")
