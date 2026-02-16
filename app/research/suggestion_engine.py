from app.research.fingerprint import generate_fingerprint
from app.research.openalex_client import search_openalex
from app.research.advisor import extract_research_patterns


def generate_suggestions(df):
    fingerprint = generate_fingerprint(df)
    query = "smartphone " + " ".join(fingerprint["modalities"]) + " dataset sampling rate fusion"

    papers = search_openalex(query, per_page=20)
    papers.sort(key=lambda paper: int(paper.get("citation_count") or 0), reverse=True)
    papers = papers[:5]

    patterns = extract_research_patterns(fingerprint, papers)

    return {
        "fingerprint": fingerprint,
        "papers": papers,
        "suggestions": patterns,
    }
