import os
import io
import json
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

app = Flask(__name__, static_folder="static")
CORS(app)

# ---------------------------------------------------------------------------
# Azure AI Foundry client
# ---------------------------------------------------------------------------
AZURE_AI_ENDPOINT = os.getenv("AZURE_AI_ENDPOINT", "")
AZURE_AI_MODEL = os.getenv("AZURE_AI_MODEL", "gpt-4o")
AZURE_AI_API_KEY = os.getenv("AZURE_AI_API_KEY", "")

TRADEMARK_CLASSES_URL = "https://tmclass.tmdn.org/ec2/"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_ai_client() -> OpenAI:
    """Return an OpenAI client pointed at the Azure AI Foundry inference endpoint."""
    if not AZURE_AI_ENDPOINT:
        raise RuntimeError("AZURE_AI_ENDPOINT is not configured. Set it in your .env file.")

    # Use the /openai/deployments path on the base host (not the project path)
    # Extract the base host from the endpoint URL
    from urllib.parse import urlparse
    parsed = urlparse(AZURE_AI_ENDPOINT)
    base_url = f"{parsed.scheme}://{parsed.netloc}/openai/deployments/{AZURE_AI_MODEL}"

    return OpenAI(
        base_url=base_url,
        api_key=AZURE_AI_API_KEY,
        default_query={"api-version": "2024-10-21"},
    )


def extract_text_from_file(file_storage) -> str:
    """Extract text from an uploaded file (PDF, DOCX, or plain text)."""
    filename = file_storage.filename.lower()
    file_bytes = file_storage.read()

    if filename.endswith(".pdf"):
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(pages)
    elif filename.endswith((".docx",)):
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        text = "\n".join(p.text for p in doc.paragraphs)
    elif filename.endswith((".txt", ".md", ".csv")):
        text = file_bytes.decode("utf-8", errors="replace")
    else:
        raise ValueError(f"Unsupported file type: {filename}. Please upload a PDF, DOCX, or TXT file.")

    return text[:12000]


def scrape_url(url: str) -> str:
    """Fetch a URL and return its visible text content."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove scripts, styles, nav, footer for cleaner text
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    # Truncate to a reasonable size for the LLM context window
    return text[:12000]


def scrape_trademark_classes() -> str:
    """Fetch the trademark classes page and return its content."""
    return scrape_url(TRADEMARK_CLASSES_URL)


def analyse_with_foundry(business_text: str, trademark_text: str) -> str:
    """Send both texts to Azure AI Foundry and get trademark classification."""
    client = _get_ai_client()

    system_prompt = """You are an expert trademark classification assistant.

You will receive two pieces of information:
1. BUSINESS CONTENT – text scraped from a business website or document describing their services/products.
2. TRADEMARK CLASSES REFERENCE – text from a trademark classes reference page listing all Nice Classification trademark classes and their associated terms/specifications.

Your task:
- Analyse the business content to understand what goods and services the business provides.
- Match those goods and services to the most relevant trademark classes from the reference.
- For each relevant class, list the specific specification terms from that class that relate to the business.

Return your answer STRICTLY in this format (one class per line):

Class [Number] – [Class Name] ([Confidence]%), [specification term 1]; [specification term 2]; [specification term 3]

Rules:
- Only include classes that are genuinely relevant to the business.
- Include the official class name/title after the number (e.g. "Class 9 – Scientific Apparatus").
- Include a confidence percentage (0-100) in parentheses after the class name indicating how confident you are that this class applies to the business.
- The specification terms MUST come from the trademark classes reference text.
- Separate specification terms with semicolons.
- Order classes by confidence score (highest first).
- Do not include any other text, headings, or explanations – just the class lines.
"""

    user_prompt = f"""=== BUSINESS CONTENT ===
{business_text}

=== TRADEMARK CLASSES REFERENCE ===
{trademark_text}
"""

    response = client.chat.completions.create(
        model=AZURE_AI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_completion_tokens=4000,
    )

    return response.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/health")
def health():
    """Health check endpoint for Azure Container Apps."""
    return jsonify({"status": "healthy"}), 200


# ---------------------------------------------------------------------------
# OpenAPI spec for Azure AI Foundry agent tool
# ---------------------------------------------------------------------------

OPENAPI_SPEC = {
    "openapi": "3.0.0",
    "info": {
        "title": "Trademark Classification API",
        "description": "Analyses a business website or description and returns relevant Nice Classification trademark classes with specification terms and confidence scores.",
        "version": "1.0.0",
    },
    "servers": [{"url": "/"}],
    "paths": {
        "/classify": {
            "post": {
                "operationId": "classifyTrademarks",
                "summary": "Classify a business URL into trademark classes",
                "description": "Given a business website URL, scrapes the site to understand its services, then matches them against Nice Classification trademark classes. Returns relevant classes with specification terms and confidence scores.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "url": {
                                        "type": "string",
                                        "description": "The URL of the business website to analyse for trademark classification.",
                                    },
                                    "business_description": {
                                        "type": "string",
                                        "description": "A text description of the business services/products. Use this if a URL is not available.",
                                    },
                                },
                            },
                        },
                    },
                },
                "responses": {
                    "200": {
                        "description": "Successful classification",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "source": {
                                            "type": "string",
                                            "description": "The URL or source that was analysed.",
                                        },
                                        "classifications": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "class_number": {"type": "integer"},
                                                    "class_name": {"type": "string"},
                                                    "confidence": {"type": "integer"},
                                                    "specifications": {
                                                        "type": "array",
                                                        "items": {"type": "string"},
                                                    },
                                                    "raw": {"type": "string"},
                                                },
                                            },
                                        },
                                        "raw": {
                                            "type": "string",
                                            "description": "The full raw classification text.",
                                        },
                                    },
                                },
                            },
                        },
                    },
                    "400": {
                        "description": "Bad request – missing URL or business description",
                    },
                    "500": {
                        "description": "Server error during analysis",
                    },
                },
            },
        },
    },
}


@app.route("/.well-known/openapi.json")
def openapi_spec():
    """Serve the OpenAPI spec for Azure AI Foundry agent discovery."""
    return jsonify(OPENAPI_SPEC)


@app.route("/openapi.json")
def openapi_spec_alt():
    """Alternate path for the OpenAPI spec."""
    return jsonify(OPENAPI_SPEC)


# ---------------------------------------------------------------------------
# Agent-compatible /classify endpoint (JSON only, structured response)
# ---------------------------------------------------------------------------

def _parse_classification_line(line: str) -> dict:
    """Parse a single classification line into structured data."""
    import re
    # Match: Class 9 – Scientific Apparatus (85%), spec1; spec2
    match = re.match(
        r"^Class\s+(\d+)\s*[\u2013\-]\s*(.+?)\s*\((\d+)%\)\s*,?\s*(.*)",
        line, re.IGNORECASE,
    )
    if match:
        return {
            "class_number": int(match.group(1)),
            "class_name": match.group(2).strip(),
            "confidence": int(match.group(3)),
            "specifications": [s.strip() for s in match.group(4).split(";") if s.strip()],
            "raw": line,
        }
    # Fallback: Class N, specs
    match2 = re.match(r"^Class\s+(\d+),?\s*(.*)", line, re.IGNORECASE)
    if match2:
        return {
            "class_number": int(match2.group(1)),
            "class_name": "",
            "confidence": 0,
            "specifications": [s.strip() for s in match2.group(2).split(";") if s.strip()],
            "raw": line,
        }
    return {"class_number": 0, "class_name": "", "confidence": 0, "specifications": [], "raw": line}


@app.route("/classify", methods=["POST"])
def classify():
    """Agent-compatible endpoint: accepts JSON with url or business_description."""
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    description = (data.get("business_description") or "").strip()

    if not url and not description:
        return jsonify({"error": "Please provide a 'url' or 'business_description'."}), 400

    # Get business text from URL or direct description
    if url:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            business_text = scrape_url(url)
            source_label = url
        except Exception as e:
            return jsonify({"error": f"Could not fetch the provided URL: {e}"}), 400
    else:
        business_text = description[:12000]
        source_label = "business_description"

    try:
        trademark_text = scrape_trademark_classes()
    except Exception as e:
        return jsonify({"error": f"Could not fetch trademark classes page: {e}"}), 500

    try:
        result = analyse_with_foundry(business_text, trademark_text)
    except Exception as e:
        return jsonify({"error": f"AI analysis failed: {e}"}), 500

    # Parse into structured data
    lines = [line.strip() for line in result.split("\n") if line.strip()]
    classifications = [_parse_classification_line(line) for line in lines]

    return jsonify({
        "source": source_label,
        "classifications": classifications,
        "raw": result,
    })


@app.route("/analyse", methods=["POST"])
def analyse():
    """Accept a URL or uploaded file, compare against trademark classes, return results."""
    # Check if this is a file upload (multipart) or JSON (URL)
    if request.content_type and "multipart/form-data" in request.content_type:
        # File upload path
        uploaded_file = request.files.get("file")
        url = request.form.get("url", "").strip()

        if uploaded_file and uploaded_file.filename:
            try:
                business_text = extract_text_from_file(uploaded_file)
                source_label = uploaded_file.filename
            except Exception as e:
                return jsonify({"error": f"Could not read the uploaded file: {e}"}), 400
        elif url:
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            try:
                business_text = scrape_url(url)
                source_label = url
            except Exception as e:
                return jsonify({"error": f"Could not fetch the provided URL: {e}"}), 400
        else:
            return jsonify({"error": "Please provide a URL or upload a document."}), 400
    else:
        # JSON path (original)
        data = request.get_json(silent=True) or {}
        url = (data.get("url") or "").strip()

        if not url:
            return jsonify({"error": "Please provide a URL or upload a document."}), 400

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        try:
            business_text = scrape_url(url)
            source_label = url
        except Exception as e:
            return jsonify({"error": f"Could not fetch the provided URL: {e}"}), 400

    try:
        trademark_text = scrape_trademark_classes()
    except Exception as e:
        return jsonify({"error": f"Could not fetch trademark classes page: {e}"}), 500

    try:
        result = analyse_with_foundry(business_text, trademark_text)
    except Exception as e:
        return jsonify({"error": f"AI analysis failed: {e}"}), 500

    # Parse the result into structured data
    lines = [line.strip() for line in result.split("\n") if line.strip()]
    classifications = [_parse_classification_line(line) for line in lines]

    return jsonify({
        "source": source_label,
        "classifications": classifications,
        "raw": result,
    })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, port=5000)
