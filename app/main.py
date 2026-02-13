import os
from dotenv import load_dotenv
from rich import print

def load_config():
    load_dotenv()

    config = {
        "env": os.getenv("ENV"),
        "log_level": os.getenv("LOG_LEVEL"),
        "output_dir": os.getenv("OUTPUT_DIR"),
        "data_dir": os.getenv("DATA_DIR"),
        "log_dir": os.getenv("LOG_DIR"),
        "llm_provider": os.getenv("LLM_PROVIDER"),
        "llm_model": os.getenv("LLM_MODEL"),
        "confidence_threshold": float(os.getenv("CONFIDENCE_THRESHOLD")),
        "max_iterations": int(os.getenv("MAX_ITERATIONS")),
    }

    return config


def main():
    config = load_config()

    print("\n[bold green]🚀 SensorFusionAgent v1.0 Initialized[/bold green]\n")

    print("Environment:", config["env"])
    print("LLM Model:", config["llm_model"])
    print("Confidence Threshold:", config["confidence_threshold"])
    print("Max Iterations:", config["max_iterations"])

    print("\nSystem Ready.\n")


if __name__ == "__main__":
    main()
