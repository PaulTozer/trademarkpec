# Trademark PEC – Trademark Classification Tool

A web app and API that analyses business websites (or uploaded documents) and returns relevant **Nice Classification** trademark classes with specification terms and confidence scores.

Built with Flask, Azure AI Foundry (GPT-5.2-chat), and deployable as an **Azure Container App** that can be registered as an **agent tool in Azure AI Foundry**.

---

## Quick Start (Local)

```bash
# 1. Clone and install
git clone https://github.com/PaulTozer/trademarkpec.git
cd trademarkpec
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env with your Azure AI Foundry credentials

# 3. Run
python app.py
# Open http://localhost:5000
```

## Environment Variables

| Variable | Description |
|---|---|
| `AZURE_AI_ENDPOINT` | Azure AI Foundry project endpoint |
| `AZURE_AI_API_KEY` | API key for the endpoint |
| `AZURE_AI_MODEL` | Model deployment name (default: `gpt-5.2-chat`) |

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Web UI |
| `GET` | `/health` | Health check (returns `{"status":"healthy"}`) |
| `GET` | `/openapi.json` | OpenAPI 3.0 spec for agent integration |
| `POST` | `/analyse` | Web UI endpoint (JSON or multipart form) |
| `POST` | `/classify` | **Agent endpoint** – JSON only, structured response |

### POST /classify (Agent API)

**Request:**
```json
{
  "url": "https://example.com"
}
```
or:
```json
{
  "business_description": "We sell custom printed t-shirts and mugs..."
}
```

**Response:**
```json
{
  "source": "https://example.com",
  "classifications": [
    {
      "class_number": 25,
      "class_name": "Clothing",
      "confidence": 90,
      "specifications": ["T-shirts", "printed garments", "casual wear"],
      "raw": "Class 25 – Clothing (90%), T-shirts; printed garments; casual wear"
    }
  ],
  "raw": "Class 25 – Clothing (90%), T-shirts; printed garments; casual wear\n..."
}
```

---

## Deploy to Azure Container Apps

### Prerequisites
- Azure CLI installed and logged in (`az login`)
- `AZURE_AI_ENDPOINT` and `AZURE_AI_API_KEY` set in your environment

### Deploy (PowerShell)
```powershell
$env:AZURE_AI_ENDPOINT = "https://your-endpoint.services.ai.azure.com/api/projects/yourProject"
$env:AZURE_AI_API_KEY  = "your-key"
.\deploy.ps1
```

### Deploy (Bash)
```bash
export AZURE_AI_ENDPOINT="https://your-endpoint.services.ai.azure.com/api/projects/yourProject"
export AZURE_AI_API_KEY="your-key"
chmod +x deploy.sh
./deploy.sh
```

The script will:
1. Create a resource group, ACR, and Container Apps environment
2. Build the Docker image in ACR
3. Deploy the container app with your secrets
4. Print the app URL, OpenAPI spec URL, and agent API URL

---

## Register as an Azure AI Foundry Agent Tool

Once deployed, you can register this container app as a tool in Azure AI Foundry:

1. Go to your **Azure AI Foundry** project
2. Navigate to **Tools** → **Add a tool** → **OpenAPI**
3. Enter the OpenAPI spec URL: `https://<your-app>.azurecontainerapps.io/openapi.json`
4. Foundry will discover the `classifyTrademarks` operation
5. Your agent can now call this tool to classify business URLs into trademark classes

---

## Docker (Local)

```bash
docker build -t trademarkpec .
docker run -p 8080:8080 \
  -e AZURE_AI_ENDPOINT="..." \
  -e AZURE_AI_API_KEY="..." \
  -e AZURE_AI_MODEL="gpt-5.2-chat" \
  trademarkpec
```

Open http://localhost:8080
