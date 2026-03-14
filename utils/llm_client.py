import os
import json
import requests
from typing import Dict, Any, Optional
from config.config import (
    LLM_API_URL, LLM_API_KEY, LLM_PROTOCOL, LLM_API_FORMAT,
    LLM_MODEL, LLM_BASE_URL, LLM_TEMPERATURE, LLM_MAX_TOKENS, LLM_TIMEOUT
)
import logging

logger = logging.getLogger(__name__)

class LLMClient:
    """大模型客户端 - 支持Anthropic和OpenAI格式"""
    
    def __init__(self):
        self.api_url = LLM_API_URL or LLM_BASE_URL
        self.api_key = LLM_API_KEY
        self.api_format = LLM_API_FORMAT
        self.model = LLM_MODEL
        self.temperature = LLM_TEMPERATURE
        self.max_tokens = LLM_MAX_TOKENS
        self.timeout = LLM_TIMEOUT
        
        if not self.api_key:
            logger.warning("未配置LLM_API_KEY，大模型功能将被禁用")
            self.enabled = False
        else:
            self.enabled = True
    
    def analyze_k8s_events(self, events: list, pod_name: str = None) -> str:
        """使用大模型分析Kubernetes事件"""
        if not self.enabled:
            return "大模型功能未启用"
        
        try:
            # 构建事件文本
            events_text = "\n".join([
                f"类型: {event.get('type', 'Unknown')}, "
                f"原因: {event.get('reason', 'Unknown')}, "
                f"消息: {event.get('message', 'Unknown')}, "
                f"计数: {event.get('count', 1)}"
                for event in events[:10]  # 限制事件数量
            ])
            
            prompt = f"""你是一个Kubernetes专家，请分析以下Pod事件并提供详细的故障诊断和解决方案。

Pod名称: {pod_name or 'Unknown'}

事件列表:
{events_text}

请提供:
1. 问题的根本原因分析
2. 具体的排查步骤
3. 解决方案建议
4. 预防措施

请用中文回答，格式清晰，提供可执行的命令。"""
            
            response = self._call_llm(prompt)
            return response
            
        except Exception as e:
            logger.error(f"大模型分析失败: {e}")
            # 返回规则引擎分析结果作为回退
            return self._fallback_event_analysis(events, pod_name)
    
    def _fallback_event_analysis(self, events: list, pod_name: str = None) -> str:
        """规则引擎回退分析"""
        analysis = []
        for event in events:
            reason = event.get('reason', '')
            message = event.get('message', '')
            
            if 'ImagePullBackOff' in reason or 'Failed' in reason:
                analysis.append("检测到镜像拉取失败")
                analysis.append(f"建议: 检查镜像 {message} 是否可访问")
                analysis.append("建议: 确认私有仓库的imagePullSecrets配置")
            
            elif 'OutOfmemory' in message or 'OOMKilled' in message:
                analysis.append("检测到内存不足(OOM)错误")
                analysis.append("建议: 增加Pod内存限制或优化应用内存使用")
            
            elif 'CrashLoopBackOff' in reason:
                analysis.append("检测到Pod频繁崩溃重启")
                analysis.append("建议: 查看Pod日志以确定应用崩溃原因")
        
        if analysis:
            return "\n".join(analysis)
        else:
            return f"事件分析完成，未发现明显错误模式。Pod: {pod_name}"
    
    def analyze_k8s_logs(self, logs: str, pod_name: str = None) -> str:
        """使用大模型分析Kubernetes日志"""
        if not self.enabled:
            return "大模型功能未启用"
        
        try:
            # 截断日志以避免超长输入
            truncated_logs = logs[-2000:] if len(logs) > 2000 else logs
            
            prompt = f"""你是一个Kubernetes和应用运维专家，请分析以下Pod日志并提供故障诊断。

Pod名称: {pod_name or 'Unknown'}

日志内容:
{truncated_logs}

请提供:
1. 错误模式识别
2. 可能的根本原因
3. 具体的排查命令
4. 解决方案建议

请用中文回答，格式清晰，提供可执行的kubectl命令。"""
            
            response = self._call_llm(prompt)
            return response
            
        except Exception as e:
            logger.error(f"大模型日志分析失败: {e}")
            return f"大模型日志分析失败: {str(e)}"
    
    def generate_diagnostic_report(self, findings: dict) -> str:
        """使用大模型生成综合诊断报告"""
        if not self.enabled:
            return "大模型功能未启用"
        
        try:
            findings_text = json.dumps(findings, ensure_ascii=False, indent=2)
            
            prompt = f"""你是一个Kubernetes集群诊断专家，请基于以下发现生成专业的诊断报告。

发现详情:
{findings_text}

请提供:
1. 整体健康状态评估
2. 按优先级排序的问题列表
3. 针对每个问题的详细解决方案
4. 集群优化建议
5. 监控和告警配置建议

请用中文回答，格式专业，提供具体的kubectl命令和配置示例。"""
            
            response = self._call_llm(prompt)
            return response
            
        except Exception as e:
            logger.error(f"大模型报告生成失败: {e}")
            return f"大模型报告生成失败: {str(e)}"
    
    def _call_llm(self, prompt: str) -> str:
        """调用大模型API"""
        if self.api_format == "anthropic":
            return self._call_anthropic_api(prompt)
        elif self.api_format == "openai":
            return self._call_openai_api(prompt)
        else:
            raise ValueError(f"不支持的API格式: {self.api_format}")
    
    def _call_anthropic_api(self, prompt: str) -> str:
        """调用Anthropic API"""
        url = f"{self.api_url}/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        data = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=self.timeout)
        response.raise_for_status()
        result = response.json()
        return result["content"][0]["text"]
    
    def _call_openai_api(self, prompt: str) -> str:
        """调用OpenAI兼容API"""
        # 检查是否是Qwen DashScope API 或 coding.dashscope URL
        if "dashscope.aliyuncs.com" in self.api_url:
            if "coding.dashscope.aliyuncs.com" in self.api_url:
                # 使用标准OpenAI格式调用coding.dashscope
                url = f"{self.api_url}/chat/completions"
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                data = {
                    "model": self.model,
                    "max_tokens": self.max_tokens,
                    "temperature": self.temperature,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ]
                }
                
                response = requests.post(url, headers=headers, json=data, timeout=self.timeout)
                response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                # 使用Qwen原生API格式
                return self._call_qwen_api(prompt)
        
        # 标准OpenAI兼容API
        url = f"{self.api_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=self.timeout)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
    
    def _call_qwen_api(self, prompt: str) -> str:
        """调用Qwen DashScope API"""
        url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "input": {
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            },
            "parameters": {
                "max_tokens": self.max_tokens,
                "temperature": self.temperature
            }
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=self.timeout)
        response.raise_for_status()
        result = response.json()
        return result["output"]["text"]