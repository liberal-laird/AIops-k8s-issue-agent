from typing import Dict, Any, List, Optional
from .models import DiagnosticState, ToolCallResult
from src.utils.tools import K8sToolExecutor
import logging

logger = logging.getLogger(__name__)

class ConditionRouter:
    """条件路由器 - 决定下一步执行哪个工具"""
    
    def __init__(self, tool_executor: K8sToolExecutor):
        self.tool_executor = tool_executor
    
    def determine_next_action(self, state: DiagnosticState) -> str:
        """确定下一步行动"""
        user_input = state.user_input
        
        # 如果指定了节点，优先检查节点
        if user_input.node_id:
            if not self._has_node_status(state):
                return "get_node_status"
            elif not self._has_node_description(state):
                return "describe_node"
            elif not self._has_pod_status_for_node(state):
                return "get_pod_status"
        
        # 如果指定了Pod，检查Pod
        if user_input.pod_id:
            if not self._has_pod_status(state):
                return "get_pod_status"
            elif not self._has_describe_pod(state):
                return "describe_pod"
            else:
                return "analyze_and_conclude"  # Pod相关信息收集完成，进行分析
        
        # 基于问题类型决定行动
        if user_input.issue_type == "memory":
            return self._handle_memory_issue(state)
        elif user_input.issue_type == "disk":
            return self._handle_disk_issue(state)
        elif user_input.issue_type == "restart":
            return self._handle_restart_issue(state)
        elif user_input.issue_type == "not_ready":
            return self._handle_not_ready_issue(state)
        
        # 默认全面检查 - 只执行必要的工具调用
        if not self._has_cluster_overview(state):
            return "get_cluster_overview"
        
        # 收集完基本信息后立即进行分析
        return "analyze_and_conclude"
    
    def _has_node_status(self, state: DiagnosticState) -> bool:
        return any(call.tool_name == "get_node_status" for call in state.tool_calls)
    
    def _has_node_description(self, state: DiagnosticState) -> bool:
        return any(call.tool_name == "describe_node" for call in state.tool_calls)
    
    def _has_pod_status(self, state: DiagnosticState) -> bool:
        return any(call.tool_name == "get_pod_status" for call in state.tool_calls)
    
    def _has_pod_status_for_node(self, state: DiagnosticState) -> bool:
        return any(
            call.tool_name == "get_pod_status" and 
            state.user_input.node_id in (call.parsed_data or {}).get("pods", [])
            for call in state.tool_calls
        )
    
    def _has_describe_pod(self, state: DiagnosticState) -> bool:
        return any(call.tool_name == "describe_pod" for call in state.tool_calls)
    
    def _has_pod_logs(self, state: DiagnosticState) -> bool:
        return any(call.tool_name == "get_pod_logs" for call in state.tool_calls)
    
    def _has_cluster_overview(self, state: DiagnosticState) -> bool:
        return any(call.tool_name == "get_cluster_overview" for call in state.tool_calls)
    
    def _handle_memory_issue(self, state: DiagnosticState) -> str:
        if state.user_input.pod_id and not self._has_pod_logs(state):
            return "get_pod_logs"
        elif state.user_input.node_id and not self._has_node_description(state):
            return "describe_node"
        return "get_pod_logs" if not self._has_pod_logs(state) else "analyze_and_conclude"
    
    def _handle_disk_issue(self, state: DiagnosticState) -> str:
        if state.user_input.node_id and not self._has_node_description(state):
            return "describe_node"
        return "describe_node" if not self._has_node_description(state) else "analyze_and_conclude"
    
    def _handle_restart_issue(self, state: DiagnosticState) -> str:
        if state.user_input.pod_id and not self._has_pod_logs(state):
            return "get_pod_logs"
        return "get_pod_logs" if not self._has_pod_logs(state) else "analyze_and_conclude"
    
    def _handle_not_ready_issue(self, state: DiagnosticState) -> str:
        if state.user_input.node_id and not self._has_node_description(state):
            return "describe_node"
        return "describe_node" if not self._has_node_description(state) else "analyze_and_conclude"