import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# Kubernetes配置
KUBECONFIG_PATH = os.getenv("KUBECONFIG", "~/.kube/config")
DEBUG_MODE = os.getenv("DEBUG", "false").lower() == "true"
TIMEOUT_SECONDS = int(os.getenv("TIMEOUT_SECONDS", "30"))

# 大模型配置
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")

# 通用大模型配置 (基于URL + API Key + 协议 + API格式)
LLM_API_URL = os.getenv("LLM_API_URL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_PROTOCOL = os.getenv("LLM_PROTOCOL", "rest")  # 支持: rest, grpc
LLM_API_FORMAT = os.getenv("LLM_API_FORMAT", "anthropic")  # 支持: anthropic, openai

# 模型参数
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "60"))
LLM_MODEL = os.getenv("LLM_MODEL", "")  # 自定义模型名称

# 诊断配置
MAX_DIAGNOSTIC_STEPS = int(os.getenv("MAX_DIAGNOSTIC_STEPS", "10"))
ENABLE_LOG_ANALYSIS = os.getenv("ENABLE_LOG_ANALYSIS", "true").lower() == "true"
ENABLE_EVENT_ANALYSIS = os.getenv("ENABLE_EVENT_ANALYSIS", "true").lower() == "true"

# 根据提供商设置默认模型和端点
if LLM_PROVIDER == "anthropic":
    if not LLM_MODEL:
        LLM_MODEL = "claude-3-5-sonnet-20241022"
    LLM_BASE_URL = "https://api.anthropic.com/v1"
    LLM_API_FORMAT = "anthropic"
elif LLM_PROVIDER == "openai":
    if not LLM_MODEL:
        LLM_MODEL = "gpt-4-turbo"
    LLM_BASE_URL = "https://api.openai.com/v1"
    LLM_API_FORMAT = "openai"
elif LLM_PROVIDER == "google":
    if not LLM_MODEL:
        LLM_MODEL = "gemini-1.5-pro"
    LLM_BASE_URL = "https://generativelanguage.googleapis.com/v1"
    LLM_API_FORMAT = "openai"  # Google Vertex AI兼容OpenAI格式
elif LLM_PROVIDER == "azure":
    if not LLM_MODEL:
        LLM_MODEL = "gpt-4"
    LLM_BASE_URL = LLM_API_URL or "https://your-azure-openai-endpoint.openai.azure.com"
    LLM_API_FORMAT = "openai"
elif LLM_PROVIDER == "deepseek":
    if not LLM_MODEL:
        LLM_MODEL = "deepseek-coder"
    LLM_BASE_URL = "https://api.deepseek.com/v1"
    LLM_API_FORMAT = "openai"
elif LLM_PROVIDER == "minimax":
    if not LLM_MODEL:
        LLM_MODEL = "abab6-chat"
    LLM_BASE_URL = "https://api.minimax.chat/v1"
    LLM_API_FORMAT = "openai"
elif LLM_PROVIDER == "qwen":
    if not LLM_MODEL:
        LLM_MODEL = "qwen-max"
    LLM_BASE_URL = "https://dashscope.aliyuncs.com/api/v1"
    LLM_API_FORMAT = "openai"
else:
    if not LLM_MODEL:
        LLM_MODEL = "claude-3-5-sonnet-20241022"
    LLM_BASE_URL = "https://api.anthropic.com/v1"
    LLM_API_FORMAT = "anthropic"