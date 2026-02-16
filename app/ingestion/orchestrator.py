import uuid
from app.ingestion.loader import extract_if_zip, collect_data_files
from app.ingestion.parser import detect_structure_type, load_file
from app.ingestion.canonicalizer import build_canonical_df


class DatasetIngestor:

    def ingest(self, path):

        dataset_id = str(uuid.uuid4())

        path = extract_if_zip(path)

        file_list = collect_data_files(path)

        if not file_list:
            raise ValueError("No data files found in dataset")

        structure = detect_structure_type(file_list)

        canonical_df = build_canonical_df(
            file_list,
            load_file,
            dataset_id,
            structure
        )

        return canonical_df, structure
