from typing import Dict, List, Optional, TypedDict, Any
from langgraph.graph import StateGraph, END
from kubernetes import client, config
from kubernetes.client.rest import ApiException
import logging
import os
from config.config import KUBECONFIG_PATH, DEBUG_MODE, TIMEOUT_SECONDS
from utils.llm_client import LLMClient

# 配置日志
logging.basicConfig(level=logging.DEBUG if DEBUG_MODE else logging.INFO)
logger = logging.getLogger(__name__)

class DiagnosticState(TypedDict):
    """诊断状态"""
    user_input: str
    cluster_status: Dict[str, Any]
    node_issues: List[Dict[str, Any]]
    pod_issues: List[Dict[str, Any]]
    service_issues: List[Dict[str, Any]]
    diagnostic_steps: List[str]
    final_diagnosis: str
    error: Optional[str]
    # 大模型相关
    llm_enabled: bool

def initialize_k8s_client():
    """初始化Kubernetes客户端"""
    try:
        # 尝试从集群内部加载配置
        config.load_incluster_config()
        logger.debug("使用集群内部配置")
    except config.ConfigException:
        try:
            # 尝试从本地kubeconfig加载配置
            if os.path.exists(os.path.expanduser(KUBECONFIG_PATH)):
                config.load_kube_config(config_file=os.path.expanduser(KUBECONFIG_PATH))
                logger.debug(f"使用本地kubeconfig: {KUBECONFIG_PATH}")
            else:
                config.load_kube_config()
                logger.debug("使用默认kubeconfig")
        except config.ConfigException:
            raise Exception("无法加载Kubernetes配置，请确保kubeconfig文件存在或在集群内部运行")

def check_cluster_overview(state: DiagnosticState) -> DiagnosticState:
    """检查集群概览"""
    logger.info("检查集群概览...")
    
    try:
        initialize_k8s_client()
        v1 = client.CoreV1Api()
        
        # 获取节点信息
        nodes = v1.list_node(_request_timeout=TIMEOUT_SECONDS)
        node_count = len(nodes.items)
        ready_nodes = sum(1 for node in nodes.items 
                         if any(cond.type == "Ready" and cond.status == "True" 
                               for cond in node.status.conditions))
        
        # 获取Pod信息
        pods = v1.list_pod_for_all_namespaces(_request_timeout=TIMEOUT_SECONDS)
        pod_count = len(pods.items)
        running_pods = sum(1 for pod in pods.items if pod.status.phase == "Running")
        
        # 获取命名空间信息
        namespaces = v1.list_namespace(_request_timeout=TIMEOUT_SECONDS)
        namespace_count = len(namespaces.items)
        
        state["cluster_status"] = {
            "nodes": {"total": node_count, "ready": ready_nodes},
            "pods": {"total": pod_count, "running": running_pods},
            "namespaces": namespace_count,
            "cluster_health": "healthy" if ready_nodes == node_count else "degraded"
        }
        state["diagnostic_steps"].append("集群概览检查完成")
        
    except ApiException as e:
        state["error"] = f"Kubernetes API错误 ({e.status}): {e.reason}"
        logger.error(state["error"])
    except Exception as e:
        state["error"] = f"集群概览检查失败: {str(e)}"
        logger.error(state["error"])
    
    return state

def check_node_status(state: DiagnosticState) -> DiagnosticState:
    """检查节点状态"""
    logger.info("检查节点状态...")
    
    if state.get("error"):
        return state
        
    try:
        initialize_k8s_client()
        v1 = client.CoreV1Api()
        nodes = v1.list_node(_request_timeout=TIMEOUT_SECONDS)
        
        node_issues = []
        for node in nodes.items:
            node_name = node.metadata.name
            conditions = {cond.type: cond for cond in node.status.conditions}
            
            # 检查节点是否就绪
            if not conditions.get("Ready") or conditions["Ready"].status != "True":
                node_issues.append({
                    "node": node_name,
                    "issue": "Node Not Ready",
                    "reason": conditions.get("Ready", {}).reason if conditions.get("Ready") else "Unknown",
                    "message": conditions.get("Ready", {}).message if conditions.get("Ready") else "Unknown"
                })
            
            # 检查内存压力
            if conditions.get("MemoryPressure") and conditions["MemoryPressure"].status == "True":
                node_issues.append({
                    "node": node_name,
                    "issue": "Memory Pressure",
                    "reason": conditions["MemoryPressure"].reason,
                    "message": conditions["MemoryPressure"].message
                })
            
            # 检查磁盘压力
            if conditions.get("DiskPressure") and conditions["DiskPressure"].status == "True":
                node_issues.append({
                    "node": node_name,
                    "issue": "Disk Pressure",
                    "reason": conditions["DiskPressure"].reason,
                    "message": conditions["DiskPressure"].message
                })
        
        state["node_issues"] = node_issues
        state["diagnostic_steps"].append("节点状态检查完成")
        
    except ApiException as e:
        state["error"] = f"Kubernetes API错误 ({e.status}): {e.reason}"
        logger.error(state["error"])
    except Exception as e:
        state["error"] = f"节点状态检查失败: {str(e)}"
        logger.error(state["error"])
    
    return state

def check_pod_status(state: DiagnosticState) -> DiagnosticState:
    """检查Pod状态"""
    logger.info("检查Pod状态...")
    
    if state.get("error"):
        return state
        
    try:
        initialize_k8s_client()
        v1 = client.CoreV1Api()
        pods = v1.list_pod_for_all_namespaces(_request_timeout=TIMEOUT_SECONDS)
        
        pod_issues = []
        for pod in pods.items:
            pod_name = f"{pod.metadata.namespace}/{pod.metadata.name}"
            phase = pod.status.phase
            
            if phase not in ["Running", "Succeeded"]:
                pod_issues.append({
                    "pod": pod_name,
                    "phase": phase,
                    "reason": pod.status.reason or "Unknown",
                    "message": pod.status.message or "Unknown"
                })
            elif phase == "Running":
                # 检查容器状态
                for container_status in (pod.status.container_statuses or []):
                    if not container_status.ready:
                        pod_issues.append({
                            "pod": pod_name,
                            "phase": "ContainerNotReady",
                            "reason": container_status.state.waiting.reason if container_status.state.waiting else "Unknown",
                            "message": container_status.state.waiting.message if container_status.state.waiting else "Container not ready"
                        })
                    elif container_status.restart_count > 5:
                        pod_issues.append({
                            "pod": pod_name,
                            "phase": "FrequentRestarts",
                            "reason": "High restart count",
                            "message": f"Container restarted {container_status.restart_count} times"
                        })
        
        state["pod_issues"] = pod_issues
        state["diagnostic_steps"].append("Pod状态检查完成")
        
    except ApiException as e:
        state["error"] = f"Kubernetes API错误 ({e.status}): {e.reason}"
        logger.error(state["error"])
    except Exception as e:
        state["error"] = f"Pod状态检查失败: {str(e)}"
        logger.error(state["error"])
    
    return state

def check_service_status(state: DiagnosticState) -> DiagnosticState:
    """检查Service状态"""
    logger.info("检查Service状态...")
    
    if state.get("error"):
        return state
        
    try:
        initialize_k8s_client()
        v1 = client.CoreV1Api()
        services = v1.list_service_for_all_namespaces(_request_timeout=TIMEOUT_SECONDS)
        
        service_issues = []
        for service in services.items:
            service_name = f"{service.metadata.namespace}/{service.metadata.name}"
            
            # 检查LoadBalancer服务是否有外部IP
            if service.spec.type == "LoadBalancer":
                if not service.status.load_balancer.ingress:
                    service_issues.append({
                        "service": service_name,
                        "issue": "LoadBalancer No External IP",
                        "message": "LoadBalancer service has no external IP assigned"
                    })
        
        state["service_issues"] = service_issues
        state["diagnostic_steps"].append("Service状态检查完成")
        
    except ApiException as e:
        state["error"] = f"Kubernetes API错误 ({e.status}): {e.reason}"
        logger.error(state["error"])
    except Exception as e:
        state["error"] = f"Service状态检查失败: {str(e)}"
        logger.error(state["error"])
    
    return state

def generate_diagnosis(state: DiagnosticState) -> DiagnosticState:
    """生成最终诊断报告"""
    logger.info("生成诊断报告...")
    
    if state.get("error"):
        state["final_diagnosis"] = f"诊断失败: {state['error']}"
        return state
    
    # 检查大模型是否可用
    try:
        llm_client = LLMClient()
        state["llm_enabled"] = llm_client.enabled
    except Exception as e:
        logger.warning(f"大模型初始化失败: {e}")
        state["llm_enabled"] = False
    
    # 如果大模型可用，使用大模型生成智能报告
    if state["llm_enabled"]:
        try:
            # 收集所有相关信息用于大模型分析
            findings_data = {
                "user_input": state["user_input"],
                "cluster_status": state["cluster_status"],
                "node_issues": state["node_issues"],
                "pod_issues": state["pod_issues"],
                "service_issues": state["service_issues"],
                "diagnostic_steps": state["diagnostic_steps"]
            }
            
            # 使用大模型生成综合诊断报告
            report = llm_client.generate_diagnostic_report(findings_data)
            state["final_diagnosis"] = report
            return state
        except Exception as e:
            logger.warning(f"大模型生成报告失败，回退到规则引擎: {e}")
    
    # 回退到规则引擎
    issues_found = []
    
    # 节点问题
    if state["node_issues"]:
        issues_found.append(f"发现 {len(state['node_issues'])} 个节点问题")
    
    # Pod问题
    if state["pod_issues"]:
        issues_found.append(f"发现 {len(state['pod_issues'])} 个Pod问题")
    
    # Service问题
    if state["service_issues"]:
        issues_found.append(f"发现 {len(state['service_issues'])} 个Service问题")
    
    if not issues_found:
        state["final_diagnosis"] = "集群状态正常，未发现明显问题。"
    else:
        diagnosis = "集群诊断发现问题：\n"
        diagnosis += "\n".join([f"- {issue}" for issue in issues_found])
        
        # 添加详细问题信息
        if state["node_issues"]:
            diagnosis += "\n\n节点问题详情："
            for issue in state["node_issues"][:3]:  # 只显示前3个
                diagnosis += f"\n  • 节点 {issue['node']}: {issue['issue']} - {issue['message']}"
            if len(state["node_issues"]) > 3:
                diagnosis += f"\n  • 还有 {len(state['node_issues']) - 3} 个节点问题..."
        
        if state["pod_issues"]:
            diagnosis += "\n\nPod问题详情："
            for issue in state["pod_issues"][:3]:  # 只显示前3个
                diagnosis += f"\n  • Pod {issue['pod']}: {issue['phase']} - {issue['message']}"
            if len(state["pod_issues"]) > 3:
                diagnosis += f"\n  • 还有 {len(state['pod_issues']) - 3} 个Pod问题..."
        
        if state["service_issues"]:
            diagnosis += "\n\nService问题详情："
            for issue in state["service_issues"][:3]:  # 只显示前3个
                diagnosis += f"\n  • Service {issue['service']}: {issue['issue']} - {issue['message']}"
            if len(state["service_issues"]) > 3:
                diagnosis += f"\n  • 还有 {len(state['service_issues']) - 3} 个Service问题..."
        
        state["final_diagnosis"] = diagnosis
    
    return state

def create_diagnostic_graph() -> StateGraph:
    """创建诊断图"""
    graph = StateGraph(DiagnosticState)
    
    # 添加节点
    graph.add_node("check_cluster_overview", check_cluster_overview)
    graph.add_node("check_node_status", check_node_status)
    graph.add_node("check_pod_status", check_pod_status)
    graph.add_node("check_service_status", check_service_status)
    graph.add_node("generate_diagnosis", generate_diagnosis)
    
    # 设置起始点
    graph.set_entry_point("check_cluster_overview")
    
    # 添加边
    graph.add_edge("check_cluster_overview", "check_node_status")
    graph.add_edge("check_node_status", "check_pod_status")
    graph.add_edge("check_pod_status", "check_service_status")
    graph.add_edge("check_service_status", "generate_diagnosis")
    graph.add_edge("generate_diagnosis", END)
    
    return graph.compile()

def run_diagnostic(user_input: str) -> str:
    """运行诊断"""
    initial_state = DiagnosticState(
        user_input=user_input,
        cluster_status={},
        node_issues=[],
        pod_issues=[],
        service_issues=[],
        diagnostic_steps=[],
        final_diagnosis="",
        error=None,
        llm_enabled=False
    )
    
    graph = create_diagnostic_graph()
    result = graph.invoke(initial_state)
    
    return result["final_diagnosis"]