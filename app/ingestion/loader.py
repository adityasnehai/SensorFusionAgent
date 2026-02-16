import os
import zipfile
import shutil


def extract_if_zip(path, extract_root="data/extracted"):

    if path.endswith(".zip"):

        os.makedirs(extract_root, exist_ok=True)
        extract_path = os.path.join(
            extract_root,
            os.path.basename(path).replace(".zip", "")
        )

        if os.path.exists(extract_path):
            shutil.rmtree(extract_path)

        with zipfile.ZipFile(path, "r") as zip_ref:
            zip_ref.extractall(extract_path)

        return extract_path

    return path


def collect_data_files(path):

    data_files = []

    if os.path.isfile(path):
        return [path]

    for root, dirs, files in os.walk(path):
        for file in files:
            if file.lower().endswith((".csv", ".txt", ".parquet")):
                data_files.append(os.path.join(root, file))

    return data_files
