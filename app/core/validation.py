from app.core.hqscore_v3 import compute_hqscore_v3


def validate_and_compare(original_df, modified_df):

    original_score = compute_hqscore_v3(original_df)
    modified_score = compute_hqscore_v3(modified_df)

    improvement = modified_score - original_score

    return {
        "original_score": round(float(original_score), 4),
        "modified_score": round(float(modified_score), 4),
        "improvement": round(float(improvement), 4),
        "accepted": improvement >= 0
    }
