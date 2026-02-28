from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import json, os, sys, traceback
from io import StringIO

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

class CodeRequest(BaseModel):
    code: str

def execute_python_code(code: str) -> dict:
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        exec(code, {})
        output = sys.stdout.getvalue()
        return {"success": True, "output": output}
    except Exception:
        output = traceback.format_exc()
        return {"success": False, "output": output}
    finally:
        sys.stdout = old_stdout

def analyze_error_with_ai(code: str, tb: str) -> List[int]:
    from openai import OpenAI
    client = OpenAI(
        api_key=os.environ["GROQ_API_KEY"],
        base_url="https://api.groq.com/openai/v1"
    )
    prompt = f"""Analyze this Python code and its error traceback.
Return ONLY a JSON object with the line numbers where the error occurred.
Format: {{"error_lines": [3]}}

CODE:
{code}

TRACEBACK:
{tb}"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You are a Python error analyzer. Return only JSON with error_lines array."},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"}
    )
    result = json.loads(response.choices[0].message.content)
    return result.get("error_lines", [])

@app.post("/code-interpreter")
async def code_interpreter(request: CodeRequest):
    if not request.code.strip():
        raise HTTPException(status_code=422, detail="Code cannot be empty")

    execution = execute_python_code(request.code)

    if execution["success"]:
        return {"error": [], "result": execution["output"]}
    else:
        error_lines = analyze_error_with_ai(request.code, execution["output"])
        return {"error": error_lines, "result": execution["output"]}
