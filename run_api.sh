#!/bin/bash
source senenv/bin/activate
uvicorn app.api:app --reload --host 0.0.0.0 --port 8000
