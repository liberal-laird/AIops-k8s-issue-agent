from typing import Dict, Any, List, Optional
from .models import DiagnosticState, ToolCallResult
from src.utils.tools import K8sToolExecutor
from src.utils.llm_client import LLMClient
import logging

logger = logging.getLogger(__name__)

class AnalysisDecisionMaker:
    """分析决策器 - 生成诊断报告"""
    
    def __init__(self):
        self.llm_client = LLMClient()
    
    def analyze_findings(self, state: DiagnosticState) -> str:
        """分析发现并生成报告"""
        # 如果大模型可用，使用大模型生成智能报告
        if self.llm_client.enabled:
            return self._generate_llm_report(state)
        
        # 否则使用规则引擎
        return self._generate_rule_based_report(state)
    
    def _generate_llm_report(self, state: DiagnosticState) -> str:
        """使用大模型生成报告"""
        findings_data = {
            "user_input": state.user_input.dict(),
            "tool_calls": [],
            "pod_issues": [],
            "node_issues": [],
            "events": [],
            "logs": ""
        }
        
        # 收集所有相关信息
        for call in state.tool_calls:
            if call.success:
                findings_data["tool_calls"].append({
                    "tool_name": call.tool_name,
                    "parsed_data": call.parsed_data
                })
                
                if call.tool_name == "describe_pod" and call.parsed_data:
                    events = call.parsed_data.get("events", [])
                    findings_data["events"] = events
                    
                    # 使用大模型分析事件
                    if events:
                        pod_name = state.user_input.pod_id or "unknown"
                        event_analysis = self.llm_client.analyze_k8s_events(events, pod_name)
                        return f"## 智能诊断结果\n\n{event_analysis}"
                
                elif call.tool_name == "get_pod_logs" and call.output:
                    logs = call.output
                    pod_name = state.user_input.pod_id or "unknown"
                    log_analysis = self.llm_client.analyze_k8s_logs(logs, pod_name)
                    return f"## 智能诊断结果\n\n{log_analysis}"
        
        # 如果没有特定分析，生成综合报告
        return self.llm_client.generate_diagnostic_report(findings_data)
    
    def _generate_rule_based_report(self, state: DiagnosticState) -> str:
        """使用规则引擎生成报告"""
        findings = []
        recommendations = []
        
        user_input = state.user_input
        
        # 如果用户指定了具体的Pod，优先分析该Pod
        if user_input.pod_id:
            pod_specific_findings = self._analyze_specific_pod(state, user_input.pod_id)
            if pod_specific_findings:
                findings.extend(pod_specific_findings["findings"])
                recommendations.extend(pod_specific_findings["recommendations"])
            else:
                # Pod不存在的情况
                findings.append(f"未找到名为 '{user_input.pod_id}' 的Pod")
                recommendations.append(f"请确认Pod名称是否正确，或检查Pod是否在其他命名空间中")
                recommendations.append(f"使用 'kubectl get pods --all-namespaces | grep {user_input.pod_id}' 查找Pod")
        
        # 如果用户指定了具体的节点，优先分析该节点
        if user_input.node_id:
            node_specific_findings = self._analyze_specific_node(state, user_input.node_id)
            if node_specific_findings:
                findings.extend(node_specific_findings["findings"])
                recommendations.extend(node_specific_findings["recommendations"])
            else:
                findings.append(f"未找到名为 '{user_input.node_id}' 的节点")
                recommendations.append(f"请确认节点名称是否正确")
                recommendations.append(f"使用 'kubectl get nodes' 查看所有节点")
        
        # 如果没有指定具体资源，或者需要补充信息，分析整体集群状态
        if not user_input.pod_id and not user_input.node_id:
            # 分析节点问题
            node_issues = self._analyze_node_issues(state)
            if node_issues:
                findings.extend(node_issues["findings"])
                recommendations.extend(node_issues["recommendations"])
            
            # 分析Pod问题
            pod_issues = self._analyze_pod_issues(state)
            if pod_issues:
                findings.extend(pod_issues["findings"])
                recommendations.extend(pod_issues["recommendations"])
            
            # 分析日志问题
            log_issues = self._analyze_log_issues(state)
            if log_issues:
                findings.extend(log_issues["findings"])
                recommendations.extend(log_issues["recommendations"])
        
        if not findings:
            return "未发现明显问题。集群状态正常。"
        
        report = "## 诊断结果\n\n"
        if findings:
            report += "### 发现的问题\n"
            for finding in findings:
                report += f"- {finding}\n"
        
        if recommendations:
            report += "\n### 建议的解决方案\n"
            for rec in recommendations:
                report += f"- {rec}\n"
        
        return report
    
    def _analyze_specific_pod(self, state: DiagnosticState, pod_name: str) -> Optional[Dict[str, List[str]]]:
        """分析特定Pod的问题"""
        findings = []
        recommendations = []
        
        # 首先查找Pod状态
        target_pod = None
        for call in state.tool_calls:
            if call.tool_name == "get_pod_status" and call.success and call.parsed_data:
                pods = call.parsed_data.get("pods", [])
                for pod in pods:
                    # 检查Pod名称是否包含用户指定的名称
                    if pod_name in pod["name"] or pod["name"].endswith(f"/{pod_name}"):
                        target_pod = pod
                        break
                if target_pod:
                    break
        
        if not target_pod:
            return None
        
        # 分析Pod状态
        if target_pod["phase"] == "Pending":
            findings.append(f"Pod {target_pod['name']} 处于 Pending 状态")
            
            # 检查是否有describe_pod的详细信息
            pod_details = None
            for call in state.tool_calls:
                if call.tool_name == "describe_pod" and call.success and call.parsed_data:
                    pod_info = call.parsed_data.get("pod_info", {})
                    if pod_name in pod_info.get("name", "") or pod_info.get("name", "").endswith(f"/{pod_name}"):
                        pod_details = call.parsed_data
                        break
            
            if pod_details:
                # 分析容器状态和事件
                events = pod_details.get("events", [])
                containers = pod_details.get("spec", {}).get("containers", [])
                
                # 查找ImagePullBackOff错误
                image_pull_errors = [event for event in events if "ImagePullBackOff" in event.get("reason", "") or "Failed" in event.get("reason", "")]
                if image_pull_errors:
                    latest_error = image_pull_errors[-1]
                    container_image = containers[0]["image"] if containers else "unknown"
                    findings.append(f"Pod无法拉取镜像: {container_image}")
                    recommendations.append(f"检查镜像仓库 {container_image} 是否可访问")
                    recommendations.append(f"如果使用私有仓库，请确保已配置正确的imagePullSecrets")
                    recommendations.append(f"在节点上手动测试: docker pull {container_image}")
                else:
                    recommendations.append(f"检查Pod {target_pod['name']} 的事件: kubectl describe pod {target_pod['name'].split('/')[-1]} -n {target_pod['name'].split('/')[0]}")
                    recommendations.append("常见原因：节点资源不足、存储卷挂载失败、镜像拉取失败")
                    recommendations.append("检查节点是否有足够资源: kubectl describe nodes")
            
        elif target_pod["phase"] == "Error" or target_pod["phase"] == "Failed":
            findings.append(f"Pod {target_pod['name']} 启动失败")
            recommendations.append(f"查看Pod日志: kubectl logs {target_pod['name'].split('/')[-1]} -n {target_pod['name'].split('/')[0]}")
            recommendations.append(f"查看Pod事件: kubectl describe pod {target_pod['name'].split('/')[-1]} -n {target_pod['name'].split('/')[0]}")
            
        elif target_pod["restart_count"] > 0:
            findings.append(f"Pod {target_pod['name']} 已重启 {target_pod['restart_count']} 次")
            recommendations.append(f"查看Pod日志: kubectl logs {target_pod['name'].split('/')[-1]} -n {target_pod['name'].split('/')[0]} --previous")
            recommendations.append("检查应用是否配置了正确的健康检查探针")
            recommendations.append("检查资源限制是否过低导致OOMKilled")
        
        elif target_pod["phase"] not in ["Running", "Succeeded"]:
            findings.append(f"Pod {target_pod['name']} 状态异常: {target_pod['phase']}")
            recommendations.append(f"查看Pod详细信息: kubectl describe pod {target_pod['name'].split('/')[-1]} -n {target_pod['name'].split('/')[0]}")
            recommendations.append(f"查看Pod日志: kubectl logs {target_pod['name'].split('/')[-1]} -n {target_pod['name'].split('/')[0]}")
        
        return {"findings": findings, "recommendations": recommendations} if findings else None
    
    def _analyze_specific_node(self, state: DiagnosticState, node_name: str) -> Optional[Dict[str, List[str]]]:
        """分析特定节点的问题"""
        findings = []
        recommendations = []
        
        for call in state.tool_calls:
            if call.tool_name == "get_node_status" and call.success and call.parsed_data:
                nodes = call.parsed_data.get("nodes", [])
                for node in nodes:
                    if node["name"] == node_name:
                        if not node["status"]["ready"]:
                            findings.append(f"节点 {node_name} 未就绪")
                            recommendations.append(f"检查节点 {node_name} 的kubelet状态: systemctl status kubelet")
                            recommendations.append(f"查看节点事件: kubectl describe node {node_name}")
                        
                        if node["status"]["memory_pressure"]:
                            findings.append(f"节点 {node_name} 存在内存压力")
                            recommendations.append(f"检查节点 {node_name} 的内存使用: free -h")
                            recommendations.append(f"考虑迁移部分Pod或增加节点内存")
                        
                        if node["status"]["disk_pressure"]:
                            findings.append(f"节点 {node_name} 存在磁盘压力")
                            recommendations.append(f"清理节点 {node_name} 的磁盘空间: df -h")
                            recommendations.append(f"检查是否有大日志文件需要清理")
                        
                        break
        
        return {"findings": findings, "recommendations": recommendations} if findings else None
    
    def _analyze_node_issues(self, state: DiagnosticState) -> Optional[Dict[str, List[str]]]:
        """分析节点问题"""
        findings = []
        recommendations = []
        
        for call in state.tool_calls:
            if call.tool_name == "get_node_status" and call.success and call.parsed_data:
                nodes = call.parsed_data.get("nodes", [])
                for node in nodes:
                    if not node["status"]["ready"]:
                        findings.append(f"节点 {node['name']} 未就绪")
                        recommendations.append(f"检查节点 {node['name']} 的kubelet状态和系统资源")
                    
                    if node["status"]["memory_pressure"]:
                        findings.append(f"节点 {node['name']} 存在内存压力")
                        recommendations.append(f"检查节点 {node['name']} 的内存使用情况，考虑增加内存或迁移Pod")
                    
                    if node["status"]["disk_pressure"]:
                        findings.append(f"节点 {node['name']} 存在磁盘压力")
                        recommendations.append(f"清理节点 {node['name']} 的磁盘空间或扩展存储")
        
        return {"findings": findings, "recommendations": recommendations} if findings else None
    
    def _analyze_pod_issues(self, state: DiagnosticState) -> Optional[Dict[str, List[str]]]:
        """分析Pod问题"""
        findings = []
        recommendations = []
        
        for call in state.tool_calls:
            if call.tool_name == "get_pod_status" and call.success and call.parsed_data:
                pods = call.parsed_data.get("pods", [])
                for pod in pods:
                    if pod["phase"] not in ["Running", "Succeeded"]:
                        findings.append(f"Pod {pod['name']} 状态异常: {pod['phase']}")
                        recommendations.append(f"检查Pod {pod['name']} 的事件和配置")
                    
                    if pod["restart_count"] > 5:
                        findings.append(f"Pod {pod['name']} 频繁重启 ({pod['restart_count']} 次)")
                        recommendations.append(f"检查Pod {pod['name']} 的日志以确定重启原因")
        
        return {"findings": findings, "recommendations": recommendations} if findings else None
    
    def _analyze_log_issues(self, state: DiagnosticState) -> Optional[Dict[str, List[str]]]:
        """分析日志问题"""
        findings = []
        recommendations = []
        
        for call in state.tool_calls:
            if call.tool_name == "get_pod_logs" and call.success and call.output:
                logs = call.output.lower()
                pod_name = "unknown"
                
                # 提取Pod名称（简化处理）
                if state.user_input.pod_id:
                    pod_name = state.user_input.pod_id
                
                if "oom" in logs or "out of memory" in logs:
                    findings.append(f"Pod {pod_name} 日志中发现OOM错误")
                    recommendations.append(f"增加Pod {pod_name} 的内存限制或优化应用内存使用")
                
                if "connection refused" in logs or "connection timeout" in logs:
                    findings.append(f"Pod {pod_name} 日志中发现连接问题")
                    recommendations.append(f"检查Pod {pod_name} 的网络配置和依赖服务状态")
                
                if "disk" in logs or "storage" in logs or "no space" in logs:
                    findings.append(f"Pod {pod_name} 日志中发现磁盘空间问题")
                    recommendations.append(f"检查Pod {pod_name} 的存储卷和节点磁盘空间")
        
        return {"findings": findings, "recommendations": recommendations} if findings else None