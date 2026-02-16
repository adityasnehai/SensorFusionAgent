import pandas as pd
import os


def detect_structure_type(file_list):

    folder_names = []

    for f in file_list:
        parts = f.split(os.sep)
        if len(parts) > 2:
            folder_names.append(parts[-2])

    unique_folders = set(folder_names)

    if len(file_list) == 1:
        return "single_file"

    if len(unique_folders) > 1:
        return "participant_folder"

    return "multi_file_flat"


def load_file(path):

    if path.endswith(".csv"):
        return pd.read_csv(path)

    if path.endswith(".txt"):
        return pd.read_csv(path)

    if path.endswith(".parquet"):
        return pd.read_parquet(path)

    raise ValueError(f"Unsupported file type: {path}")
