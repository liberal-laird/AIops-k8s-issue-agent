# Kubernetes AI智能诊断Agent (LangGraph + LLM)

这是一个基于大模型(LLM)驱动的Kubernetes集群智能诊断AI Agent，使用LangGraph框架构建状态机工作流，能够理解自然语言输入并自动执行针对性的故障排查。通过集成多种大模型提供商（Anthropic、OpenAI、Qwen等），提供智能化的诊断分析和解决方案建议。

## LangGraph架构设计

### 📊 状态机工作流
- **集群概览检查**: 获取节点、Pod、命名空间的整体状态
- **节点状态分析**: 检查节点就绪状态、内存压力、磁盘压力等
- **Pod状态分析**: 检查Pod运行状态、容器就绪状态、重启次数等  
- **Service状态分析**: 检查Service配置和外部IP分配
- **智能诊断报告**: 集成大模型生成专业诊断报告

### 🤖 大模型集成
- **智能分析**: 使用LLM分析Kubernetes事件、日志和配置
- **多提供商支持**: 支持Anthropic、OpenAI、Qwen等多种大模型
- **规则回退**: 当大模型不可用时自动切换到规则引擎
- **专业报告**: 生成包含问题发现、解决方案和预防措施的完整报告

## 安装使用

```bash
# 安装依赖
pip install -e .

# 复制配置文件
cp .env.example .env

# 配置参数说明
# 1. Kubernetes配置: KUBECONFIG (默认: ~/.kube/config)
# 2. 大模型配置: LLM_PROVIDER、LLM_API_URL、LLM_API_KEY 等参数
# 3. 诊断配置: MAX_DIAGNOSTIC_STEPS、ENABLE_LOG_ANALYSIS 等参数
# 支持的提供商：anthropic, openai, google, azure, deepseek, minimax, qwen

# 使用示例
python main.py "节点worker-01内存压力大，怎么排查？"
python main.py "pod my-app-7d8f9c8b7-xyz频繁重启"
python main.py "检查default命名空间中所有Pod的状态"
```

## 功能特性

- **LangGraph状态机**: 基于LangGraph构建的可靠诊断工作流
- **大模型智能分析**: 集成LLM进行深度诊断分析，支持多种模型提供商
- **AI Agent架构**: 自主决策的Kubernetes诊断AI Agent
- **自然语言理解**: 支持中文和英文输入
- **全面诊断**: 覆盖节点、Pod、网络、存储等多个维度
- **详细报告**: 生成包含问题发现和解决方案的完整报告
- **灵活扩展**: 模块化设计，易于添加新的诊断工具和规则

## 示例截图

![Kubernetes AI智能诊断Agent示例](./docs/example.png)

## 配置说明

### Kubernetes配置
- `KUBECONFIG`: kubeconfig文件路径 (默认: ~/.kube/config)

### 大模型集成

本AI Agent支持多种大模型提供商，通过统一的配置接口进行集成：

### 支持的模型提供商
- **Anthropic**: Claude系列模型
- **OpenAI**: GPT系列模型  
- **Google**: Gemini系列模型
- **Azure**: Azure OpenAI服务
- **DeepSeek**: DeepSeek-Coder系列
- **MiniMax**: abab系列模型
- **Qwen**: 通义千问系列模型

### 配置参数
- `LLM_PROVIDER`: 模型提供商 (默认: anthropic)
- `LLM_API_URL`: API端点URL (可选，会根据提供商自动设置)
- `LLM_API_KEY`: API密钥
- `LLM_PROTOCOL`: 通信协议 (rest 或 grpc，默认: rest)
- `LLM_API_FORMAT`: API格式 (anthropic 或 openai)
- `LLM_MODEL`: 具体模型名称
- `LLM_TEMPERATURE`: 生成温度 (默认: 0.7)
- `LLM_MAX_TOKENS`: 最大输出token数 (默认: 4096)
- `LLM_TIMEOUT`: API请求超时秒数 (默认: 60)

### 诊断配置
- `MAX_DIAGNOSTIC_STEPS`: 最大诊断步骤数 (默认: 10)
- `ENABLE_LOG_ANALYSIS`: 启用日志分析 (默认: true)
- `ENABLE_EVENT_ANALYSIS`: 启用事件分析 (默认: true)

### 智能分析功能
- **事件分析**: 自动分析Kubernetes事件并提供根本原因
- **日志分析**: 解析Pod日志识别错误模式
- **综合报告**: 生成包含问题发现、解决方案和预防措施的专业报告
- **规则回退**: 当大模型不可用时，自动切换到规则引擎确保基本功能

## 权限要求

确保当前用户有以下Kubernetes权限：
- `nodes` 资源的 `get`, `list` 权限
- `pods` 资源的 `get`, `list` 权限（所有命名空间）
- `events` 资源的 `list` 权限（所有命名空间）
- `namespaces` 资源的 `list` 权限

## 故障排除

如果遇到连接问题，请确保：
1. `kubectl` 配置正确且能正常访问集群
2. 当前用户有足够的RBAC权限  
3. 集群API服务器可访问