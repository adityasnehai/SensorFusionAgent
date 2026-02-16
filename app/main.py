import sys
import pandas as pd
from dotenv import load_dotenv
from rich import print
from app.agent.loop import HarmonizationLoop


def main():
    load_dotenv()

    if len(sys.argv) < 3:
        print("Usage: python -m app.main <dataset1.csv> <dataset2.csv>")
        return

    file1 = sys.argv[1]
    file2 = sys.argv[2]

    print("\n🚀 SensorFusionAgent — LLM Enhanced Fusion\n")

    df1 = pd.read_csv(file1)
    df2 = pd.read_csv(file2)

    loop = HarmonizationLoop(max_iterations=3)
    final_df = loop.run(df1, df2)

    print("\nFusion complete. Output saved in outputs/.")


if __name__ == "__main__":
    main()
