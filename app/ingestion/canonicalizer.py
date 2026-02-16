import pandas as pd
import os


# -------------------------------------------
# TIMESTAMP NORMALIZATION
# -------------------------------------------

def normalize_timestamp(df):

    for col in df.columns:
        if "time" in col.lower():
            try:
                df[col] = pd.to_datetime(df[col], format="mixed", errors="coerce")
                df = df.dropna(subset=[col])
                df = df.rename(columns={col: "timestamp"})
                return df
            except Exception:
                continue

    raise ValueError("No valid timestamp column found")


# -------------------------------------------
# PARTICIPANT ID EXTRACTION
# -------------------------------------------

def extract_participant_id(path):

    parts = path.split(os.sep)

    if len(parts) > 2:
        return parts[-2]

    return "single"


# -------------------------------------------
# MODALITY DETECTION
# -------------------------------------------

def detect_axis(col_name):

    col = col_name.lower()

    if any(k in col for k in ["acc", "linear", "linacc"]):
        if "x" in col:
            return "acc_x"
        if "y" in col:
            return "acc_y"
        if "z" in col:
            return "acc_z"

    if any(k in col for k in ["gyro", "rotation", "angular"]):
        if "x" in col or "alpha" in col:
            return "gyro_x"
        if "y" in col or "beta" in col:
            return "gyro_y"
        if "z" in col or "gamma" in col:
            return "gyro_z"

    return None


def apply_column_mapping(df):

    rename_map = {}

    for col in df.columns:

        if col == "timestamp":
            continue

        canonical = detect_axis(col)

        if canonical:
            rename_map[col] = canonical

    df = df.rename(columns=rename_map)

    return df


# -------------------------------------------
# CANONICAL DF BUILDER
# -------------------------------------------

def build_canonical_df(file_list, load_file_fn, dataset_id, structure_type):

    all_rows = []

    if structure_type == "participant_folder":

        participant_groups = {}

        for file_path in file_list:
            participant_id = extract_participant_id(file_path)

            if participant_id not in participant_groups:
                participant_groups[participant_id] = []

            participant_groups[participant_id].append(file_path)

        for participant_id, files in participant_groups.items():

            participant_dfs = []

            for file_path in files:
                df = load_file_fn(file_path)

                df = normalize_timestamp(df)

                df = apply_column_mapping(df)

                df["source_file"] = os.path.basename(file_path)

                participant_dfs.append(df)

            combined_participant = pd.concat(participant_dfs, ignore_index=True)

            combined_participant["participant_id"] = participant_id
            combined_participant["dataset_id"] = dataset_id

            all_rows.append(combined_participant)

    else:
        dfs = []

        for file_path in file_list:
            df = load_file_fn(file_path)

            df = normalize_timestamp(df)

            df = apply_column_mapping(df)

            df["source_file"] = os.path.basename(file_path)

            dfs.append(df)

        combined = pd.concat(dfs, ignore_index=True)

        combined["participant_id"] = "single"
        combined["dataset_id"] = dataset_id

        all_rows.append(combined)

    final_df = pd.concat(all_rows, ignore_index=True)

    final_df = final_df.sort_values("timestamp")

    return final_df
