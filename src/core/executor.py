from typing import Dict, Any, Optional
from .models import DiagnosticState, UserInput, ToolCallResult
from .user_input_parser import UserInputParser
from src.utils.tools import K8sToolExecutor
from .analysis import AnalysisDecisionMaker
from .condition_router import ConditionRouter
from src.config.config import MAX_DIAGNOSTIC_STEPS
import logging

logger = logging.getLogger(__name__)

class DiagnosticExecutor:
    """诊断执行器 - 管理整个排查流程"""
    
    def __init__(self):
        self.parser = UserInputParser()
        self.tool_executor = K8sToolExecutor()
        self.router = ConditionRouter(self.tool_executor)
        self.analyzer = AnalysisDecisionMaker()
    
    def execute_diagnostic(self, user_input_str: str) -> str:
        """执行完整的诊断流程"""
        # 1. 解析用户输入
        parsed_input = self.parser.parse(user_input_str)
        logger.info(f"解析用户输入: {parsed_input}")
        
        # 2. 初始化状态
        state = DiagnosticState(user_input=parsed_input, max_steps=MAX_DIAGNOSTIC_STEPS)
        
        # 3. 执行诊断循环
        while not state.completed and state.current_step < state.max_steps:
            logger.info(f"执行步骤 {state.current_step + 1}")
            
            # 确定下一步行动
            next_action = self.router.determine_next_action(state)
            logger.info(f"下一步行动: {next_action}")
            
            if next_action == "analyze_and_conclude":
                # 生成最终分析报告
                analysis_result = self.analyzer.analyze_findings(state)
                state.analysis_result = analysis_result
                state.completed = True
                break
            elif next_action == "complete_diagnostic":
                state.completed = True
                break
            else:
                # 执行工具调用
                tool_result = self._execute_tool_call(next_action, state)
                state.tool_calls.append(tool_result)
                state.current_step += 1
        
        # 4. 返回结果
        if state.analysis_result:
            return state.analysis_result
        else:
            return "诊断完成，但未发现明显问题。"
    
    def _execute_tool_call(self, action: str, state: DiagnosticState) -> ToolCallResult:
        """执行工具调用"""
        try:
            user_input = state.user_input
            result = None
            
            if action == "get_node_status":
                if user_input.node_id:
                    raw_result = self.tool_executor.get_node_status(user_input.node_id)
                    result = ToolCallResult(
                        tool_name="get_node_status",
                        success=True,
                        parsed_data=raw_result
                    )
                else:
                    raw_result = self.tool_executor.get_node_status()
                    result = ToolCallResult(
                        tool_name="get_node_status",
                        success=True,
                        parsed_data=raw_result
                    )
            
            elif action == "describe_node":
                if user_input.node_id:
                    raw_result = self.tool_executor.describe_node(user_input.node_id)
                    result = ToolCallResult(
                        tool_name="describe_node",
                        success=True,
                        parsed_data=raw_result
                    )
            
            elif action == "get_pod_status":
                if user_input.namespace and user_input.node_id:
                    raw_result = self.tool_executor.get_pod_status(
                        namespace=user_input.namespace, 
                        node_name=user_input.node_id
                    )
                elif user_input.namespace:
                    raw_result = self.tool_executor.get_pod_status(namespace=user_input.namespace)
                elif user_input.node_id:
                    raw_result = self.tool_executor.get_pod_status(node_name=user_input.node_id)
                else:
                    raw_result = self.tool_executor.get_pod_status()
                
                result = ToolCallResult(
                    tool_name="get_pod_status",
                    success=True,
                    parsed_data=raw_result
                )
            
            elif action == "get_pod_logs":
                if user_input.pod_id:
                    namespace = user_input.namespace or "default"
                    raw_result = self.tool_executor.get_pod_logs(
                        pod_name=user_input.pod_id,
                        namespace=namespace
                    )
                    result = ToolCallResult(
                        tool_name="get_pod_logs",
                        success=True,
                        output=raw_result
                    )
            
            elif action == "describe_pod":
                if user_input.pod_id:
                    # 从之前的get_pod_status结果中找到完整的Pod名称
                    full_pod_name = user_input.pod_id
                    namespace = user_input.namespace or "default"
                    
                    # 查找完整的Pod名称
                    for call in state.tool_calls:
                        if call.tool_name == "get_pod_status" and call.success and call.parsed_data:
                            pods = call.parsed_data.get("pods", [])
                            for pod in pods:
                                if user_input.pod_id in pod["name"]:
                                    full_pod_name = pod["name"].split("/")[-1]  # 提取实际的Pod名称
                                    namespace = pod["name"].split("/")[0]  # 提取命名空间
                                    break
                    
                    raw_result = self.tool_executor.describe_pod(
                        pod_name=full_pod_name,
                        namespace=namespace
                    )
                    result = ToolCallResult(
                        tool_name="describe_pod",
                        success=True,
                        parsed_data=raw_result
                    )
            
            elif action == "get_cluster_overview":
                # 组合调用
                try:
                    nodes_result = self.tool_executor.get_node_status()
                    pods_result = self.tool_executor.get_pod_status()
                    result = ToolCallResult(
                        tool_name="get_cluster_overview",
                        success=True,
                        parsed_data={"nodes": nodes_result, "pods": pods_result}
                    )
                except Exception as e:
                    raise Exception(f"获取集群概览失败: {e}")
            
            if result is None:
                raise Exception(f"未知的工具调用: {action}")
            
            logger.info(f"工具调用成功: {action}")
            return result
            
        except Exception as e:
            logger.error(f"工具调用失败 {action}: {e}")
            return ToolCallResult(
                tool_name=action,
                success=False,
                error=str(e)
            )