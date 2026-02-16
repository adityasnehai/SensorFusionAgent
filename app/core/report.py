import os
import json
from datetime import datetime


def generate_validation_report(
    df,
    final_score,
    sampling_rate,
    offset_ms,
    unit_corrected,
    output_dir="outputs"
):

    os.makedirs(output_dir, exist_ok=True)

    report_data = {
        "timestamp_generated": str(datetime.utcnow()),
        "final_hq_score": final_score,
        "chosen_sampling_rate_hz": sampling_rate,
        "estimated_time_offset_ms": offset_ms,
        "unit_auto_corrected": unit_corrected,
        "num_rows": len(df),
        "num_columns": len(df.columns),
        "columns": list(df.columns),
    }

    # Save JSON
    with open(os.path.join(output_dir, "validation_report.json"), "w") as f:
        json.dump(report_data, f, indent=2)

    # Save Markdown
    md_content = f"""
# SensorFusionAgent Validation Report

## Final HQScore
{final_score}

## Sampling Rate Selected
{sampling_rate} Hz

## Estimated Time Offset
{offset_ms} ms

## Unit Auto Correction Applied
{unit_corrected}

## Dataset Shape
Rows: {len(df)}
Columns: {len(df.columns)}

## Columns
{", ".join(df.columns)}

---
Generated at {report_data['timestamp_generated']}
"""

    with open(os.path.join(output_dir, "validation_report.md"), "w") as f:
        f.write(md_content)
