# 🤖 LLM Provider Configuration

NL2SQL supports multiple LLM providers, giving you flexibility to choose based on cost, performance, and availability.

## 🎯 Quick Start

Set your provider in `.env`:

```bash
LLM_PROVIDER=openai  # or: gemini | openrouter | anthropic | azure_openai
```

## 📋 Supported Providers

### 1. OpenAI (Default)

**Best for:** Production, highest quality  
**Cost:** $$$ (Pay per token)  
**Free tier:** $5 credit for new accounts

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_MODEL=gpt-4o-mini  # or: gpt-4o, gpt-4-turbo
```

**Get API Key:** https://platform.openai.com/api-keys

**Recommended Models:**

- `gpt-4o-mini` - Fast, cheap, good quality (default)
- `gpt-4o` - Best quality, more expensive
- `gpt-4-turbo` - Good balance

---

### 2. Google Gemini ⭐ FREE TIER

**Best for:** Development, cost-conscious users  
**Cost:** FREE up to 15 requests/min, 1500 requests/day  
**Free tier:** ✅ Generous free quota

```bash
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-gemini-api-key-here
GEMINI_MODEL=gemini-1.5-flash  # or: gemini-1.5-pro, gemini-2.0-flash-exp
```

**Get API Key:** https://aistudio.google.com/apikey

**Recommended Models:**

- `gemini-1.5-flash` - Fast, FREE, good for most tasks (default)
- `gemini-1.5-pro` - Better quality, FREE tier available
- `gemini-2.0-flash-exp` - Experimental, latest features

**Why Gemini?**

- ✅ Completely FREE for development
- ✅ No credit card required
- ✅ Generous rate limits (1500 req/day)
- ✅ Good quality for SQL generation

---

### 3. OpenRouter

**Best for:** Access to many models, including open-source  
**Cost:** $ - $$$ (Varies by model)  
**Free tier:** Some free models available

```bash
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-your-openrouter-key-here
OPENROUTER_MODEL=openai/gpt-4o-mini  # or: anthropic/claude-3.5-sonnet
OPENROUTER_APP_NAME=NL2SQL  # Optional: for analytics
OPENROUTER_APP_URL=http://localhost:8000  # Optional: for analytics
```

**Get API Key:** https://openrouter.ai/keys

**Popular Models:**

- `openai/gpt-4o-mini` - OpenAI models via OpenRouter
- `anthropic/claude-3.5-sonnet` - Claude models
- `google/gemini-pro-1.5` - Gemini models
- `meta-llama/llama-3.1-70b-instruct` - Open-source, cheaper
- `mistralai/mistral-7b-instruct` - Very cheap

**Why OpenRouter?**

- ✅ Access to 100+ models from one API
- ✅ Some free models available
- ✅ Pay-as-you-go, no subscriptions
- ✅ Automatic fallback if model is down

---

### 4. Anthropic Claude

**Best for:** Complex reasoning, long context  
**Cost:** $$ - $$$ (Competitive with OpenAI)  
**Free tier:** $5 credit for new accounts

```bash
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022  # or: claude-3-5-haiku
```

**Get API Key:** https://console.anthropic.com/

**Recommended Models:**

- `claude-3-5-sonnet-20241022` - Best quality (default)
- `claude-3-5-haiku-20241022` - Fastest, cheapest
- `claude-3-opus-20240229` - Most capable, expensive

**Why Claude?**

- ✅ Excellent at following instructions
- ✅ Very good at SQL generation
- ✅ 200K token context window
- ⚠️ Requires anthropic package: `pip install anthropic`

---

### 5. Azure OpenAI

**Best for:** Enterprise, compliance requirements  
**Cost:** $$$ (Enterprise pricing)  
**Free tier:** None (requires Azure subscription)

```bash
LLM_PROVIDER=azure_openai
AZURE_OPENAI_API_KEY=your-azure-key-here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=your-deployment-name
AZURE_OPENAI_API_VERSION=2024-02-15-preview
```

**Setup:** Azure Portal → Create OpenAI resource → Deploy model

**Why Azure OpenAI?**

- ✅ Enterprise SLA and support
- ✅ Data residency options
- ✅ RBAC and network isolation
- ⚠️ Requires Azure subscription

---

## 💰 Cost Comparison

| Provider           | Free Tier       | Cost/1K Input Tokens | Cost/1K Output Tokens | Typical Query Cost |
| ------------------ | --------------- | -------------------- | --------------------- | ------------------ |
| **Gemini Flash**   | ✅ 1500 req/day | FREE (paid: $0.075)  | FREE (paid: $0.30)    | FREE               |
| OpenRouter (Llama) | ✅ Some models  | $0.00 - $0.10        | $0.00 - $0.10         | $0.001 - $0.01     |
| OpenAI GPT-4o-mini | $5 credit       | $0.15                | $0.60                 | $0.01 - $0.05      |
| Claude 3.5 Haiku   | $5 credit       | $0.80                | $4.00                 | $0.05 - $0.15      |
| OpenAI GPT-4o      | $5 credit       | $2.50                | $10.00                | $0.15 - $0.50      |

**Typical NL2SQL Query:** ~200 input tokens (schema + question) + ~100 output tokens (SQL)

---

## ⚙️ Advanced Configuration

### Custom Model Parameters

```bash
# Temperature (0.0 = deterministic, 1.0 = creative)
LLM_TEMPERATURE=0.1  # Lower is better for SQL

# Request timeout (seconds)
LLM_TIMEOUT=30

# Max retries on failure
LLM_MAX_RETRIES=3
```

### Programmatic Configuration

```python
from src.core.llm_provider import LLMConfig, LLMProvider
from src.core.converter import NL2SQLConverter

# Method 1: Use environment variables (recommended)
converter = NL2SQLConverter(
    connection_string="mysql+pymysql://root:admin@localhost:3306/ecommerce",
    # LLM config auto-detected from env vars
)

# Method 2: Explicit configuration
llm_config = LLMConfig(
    provider=LLMProvider.GEMINI,
    api_key="your-gemini-key",
    model="gemini-1.5-flash",
    temperature=0.1
)

converter = NL2SQLConverter(
    connection_string="mysql+pymysql://root:admin@localhost:3306/ecommerce",
    llm_config=llm_config
)
```

---

## 🎓 Recommendations

### For Development

**Use Gemini** - Free, no credit card, good quality

```bash
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-key-here
```

### For Production (High Quality)

**Use OpenAI GPT-4o-mini** - Best quality/cost ratio

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=your-key-here
OPENAI_MODEL=gpt-4o-mini
```

### For Cost-Conscious Production

**Use OpenRouter + Llama** - Open-source models, very cheap

```bash
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your-key-here
OPENROUTER_MODEL=meta-llama/llama-3.1-70b-instruct
```

### For Enterprise

**Use Azure OpenAI** - SLA, compliance, support

```bash
LLM_PROVIDER=azure_openai
AZURE_OPENAI_API_KEY=your-key-here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
```

---

## 🔧 Installation

### Base Installation

```bash
pip install -r requirements.txt
```

### Optional Providers

**For Anthropic Claude:**

```bash
pip install anthropic>=0.18.0
```

**For Google Gemini (alternative SDK):**

```bash
pip install google-generativeai>=0.3.0
```

**For Azure OpenAI:**

```bash
pip install azure-identity>=1.15.0
```

> **Note:** OpenRouter and Gemini (OpenAI-compatible mode) work with base `openai` package, no extra deps needed.

---

## 🐛 Troubleshooting

### "LLM provider not configured"

- Check `LLM_PROVIDER` is set in `.env`
- Check API key env var matches provider (e.g., `GEMINI_API_KEY` for Gemini)

### "Rate limit exceeded"

- **Gemini:** Wait 1 minute (15 req/min limit on free tier)
- **OpenAI:** Upgrade to paid account or wait
- **OpenRouter:** Check account balance

### "Model not found"

- Check model name spelling
- Some models require special access (e.g., GPT-4 requires separate API approval)

### "Connection timeout"

- Increase `LLM_TIMEOUT=60` in `.env`
- Check internet connection
- Some providers have regional restrictions

---

## 📚 API Key Resources

| Provider     | Get API Key                          | Docs                                                  |
| ------------ | ------------------------------------ | ----------------------------------------------------- |
| OpenAI       | https://platform.openai.com/api-keys | https://platform.openai.com/docs                      |
| Gemini       | https://aistudio.google.com/apikey   | https://ai.google.dev/docs                            |
| OpenRouter   | https://openrouter.ai/keys           | https://openrouter.ai/docs                            |
| Anthropic    | https://console.anthropic.com/       | https://docs.anthropic.com                            |
| Azure OpenAI | https://portal.azure.com             | https://learn.microsoft.com/azure/ai-services/openai/ |

---

## 🚀 Quick Test

Test your provider configuration:

```python
from src.core.llm_provider import create_llm_config_from_env, get_llm_client

# Load config from .env
config = create_llm_config_from_env()
print(f"Provider: {config.provider}")
print(f"Model: {config.model}")

# Test client
client = get_llm_client(config)
print("✅ LLM client initialized successfully!")
```

Or via API:

```bash
# Start server
python -m uvicorn src.api.main:app --reload

# Test query
curl -X POST http://localhost:8000/api/nl2sql \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How many users do we have?",
    "execute": true
  }'
```

---

## 💡 Tips

1. **Start with Gemini** - Free, no commitment, good for learning
2. **Use temperature=0.1** - SQL needs deterministic outputs
3. **Enable few-shot examples** - Improves accuracy significantly
4. **Monitor costs** - Set up billing alerts in provider console
5. **Use OpenRouter** - Easy switching between models without changing code
6. **Cache schemas** - Reduces token usage (done automatically by NL2SQL)

---

Need help? Check the main [README.md](../README.md) or open an issue!
