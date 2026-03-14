import subprocess
import json
import logging
from typing import Dict, Any, Optional, List
from kubernetes import client, config
from kubernetes.client.rest import ApiException
import os
from src.config.config import TIMEOUT_SECONDS, KUBECONFIG_PATH

logger = logging.getLogger(__name__)

class K8sToolExecutor:
    """Kubernetes工具执行器"""
    
    def __init__(self):
        self._initialize_k8s_client()
    
    def _initialize_k8s_client(self):
        """初始化Kubernetes客户端"""
        try:
            config.load_incluster_config()
            logger.debug("使用集群内部配置")
        except config.ConfigException:
            try:
                if os.path.exists(os.path.expanduser(KUBECONFIG_PATH)):
                    config.load_kube_config(config_file=os.path.expanduser(KUBECONFIG_PATH))
                else:
                    config.load_kube_config()
                logger.debug("使用本地kubeconfig")
            except config.ConfigException:
                raise Exception("无法加载Kubernetes配置")
    
    def get_node_status(self, node_name: str = None) -> Dict[str, Any]:
        """获取节点状态"""
        try:
            v1 = client.CoreV1Api()
            if node_name:
                node = v1.read_node(name=node_name, _request_timeout=TIMEOUT_SECONDS)
                return self._parse_node_status(node)
            else:
                nodes = v1.list_node(_request_timeout=TIMEOUT_SECONDS)
                return {"nodes": [self._parse_node_status(node) for node in nodes.items]}
        except ApiException as e:
            logger.error(f"获取节点状态失败: {e}")
            raise
    
    def describe_node(self, node_name: str) -> Dict[str, Any]:
        """获取节点详细信息"""
        try:
            v1 = client.CoreV1Api()
            node = v1.read_node(name=node_name, _request_timeout=TIMEOUT_SECONDS)
            # 获取节点事件
            events = v1.list_event_for_all_namespaces(field_selector=f"involvedObject.name={node_name}", _request_timeout=TIMEOUT_SECONDS)
            
            return {
                "node_info": self._parse_node_status(node),
                "events": [self._parse_event(event) for event in events.items],
                "allocatable": node.status.allocatable,
                "capacity": node.status.capacity
            }
        except ApiException as e:
            logger.error(f"描述节点失败: {e}")
            raise
    
    def get_pod_status(self, namespace: str = None, node_name: str = None) -> Dict[str, Any]:
        """获取Pod状态"""
        try:
            v1 = client.CoreV1Api()
            if namespace and node_name:
                field_selector = f"spec.nodeName={node_name}"
                pods = v1.list_namespaced_pod(namespace=namespace, field_selector=field_selector, _request_timeout=TIMEOUT_SECONDS)
            elif namespace:
                pods = v1.list_namespaced_pod(namespace=namespace, _request_timeout=TIMEOUT_SECONDS)
            elif node_name:
                field_selector = f"spec.nodeName={node_name}"
                pods = v1.list_pod_for_all_namespaces(field_selector=field_selector, _request_timeout=TIMEOUT_SECONDS)
            else:
                pods = v1.list_pod_for_all_namespaces(_request_timeout=TIMEOUT_SECONDS)
            
            return {"pods": [self._parse_pod_status(pod) for pod in pods.items]}
        except ApiException as e:
            logger.error(f"获取Pod状态失败: {e}")
            raise
    
    def get_pod_logs(self, pod_name: str, namespace: str = "default", container_name: str = None) -> str:
        """获取Pod日志"""
        try:
            v1 = client.CoreV1Api()
            if container_name:
                logs = v1.read_namespaced_pod_log(
                    name=pod_name, 
                    namespace=namespace, 
                    container=container_name,
                    tail_lines=100,
                    _request_timeout=TIMEOUT_SECONDS
                )
            else:
                logs = v1.read_namespaced_pod_log(
                    name=pod_name, 
                    namespace=namespace,
                    tail_lines=100,
                    _request_timeout=TIMEOUT_SECONDS
                )
            return logs
        except ApiException as e:
            logger.error(f"获取Pod日志失败: {e}")
            raise
    
    def describe_pod(self, pod_name: str, namespace: str = "default") -> Dict[str, Any]:
        """获取Pod详细信息"""
        try:
            v1 = client.CoreV1Api()
            pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace, _request_timeout=TIMEOUT_SECONDS)
            # 获取Pod事件
            field_selector = f"involvedObject.name={pod_name},involvedObject.namespace={namespace}"
            events = v1.list_namespaced_event(namespace=namespace, field_selector=field_selector, _request_timeout=TIMEOUT_SECONDS)
            
            return {
                "pod_info": self._parse_pod_status(pod),
                "events": [self._parse_event(event) for event in events.items],
                "spec": {
                    "containers": [{
                        "name": container.name,
                        "image": container.image,
                        "resources": container.resources.to_dict() if container.resources else {},
                        "ports": [port.to_dict() for port in container.ports] if container.ports else []
                    } for container in pod.spec.containers]
                }
            }
        except ApiException as e:
            logger.error(f"描述Pod失败: {e}")
            raise
    
    def top_nodes(self) -> Dict[str, Any]:
        """获取节点资源使用情况"""
        try:
            # 这里简化实现，实际可能需要metrics-server
            v1 = client.CoreV1Api()
            nodes = v1.list_node(_request_timeout=TIMEOUT_SECONDS)
            return {"resource_usage": "需要metrics-server支持"}
        except ApiException as e:
            logger.error(f"获取节点资源使用失败: {e}")
            return {"error": str(e)}
    
    def top_pods(self, namespace: str = None) -> Dict[str, Any]:
        """获取Pod资源使用情况"""
        try:
            # 简化实现
            if namespace:
                v1 = client.CoreV1Api()
                pods = v1.list_namespaced_pod(namespace=namespace, _request_timeout=TIMEOUT_SECONDS)
            else:
                v1 = client.CoreV1Api()
                pods = v1.list_pod_for_all_namespaces(_request_timeout=TIMEOUT_SECONDS)
            return {"resource_usage": "需要metrics-server支持"}
        except ApiException as e:
            logger.error(f"获取Pod资源使用失败: {e}")
            return {"error": str(e)}
    
    def _parse_node_status(self, node) -> Dict[str, Any]:
        """解析节点状态"""
        conditions = {}
        if hasattr(node.status, 'conditions') and node.status.conditions:
            conditions = {cond.type: cond for cond in node.status.conditions}
        return {
            "name": node.metadata.name,
            "status": {
                "ready": conditions.get("Ready", {}).status == "True" if conditions.get("Ready") else False,
                "memory_pressure": conditions.get("MemoryPressure", {}).status == "True" if conditions.get("MemoryPressure") else False,
                "disk_pressure": conditions.get("DiskPressure", {}).status == "True" if conditions.get("DiskPressure") else False,
                "pid_pressure": conditions.get("PIDPressure", {}).status == "True" if conditions.get("PIDPressure") else False,
                "network_unavailable": conditions.get("NetworkUnavailable", {}).status == "True" if conditions.get("NetworkUnavailable") else False
            },
            "addresses": [addr.address for addr in node.status.addresses] if node.status.addresses else [],
            "version": node.status.node_info.kubelet_version if node.status.node_info else "",
            "os": node.status.node_info.os_image if node.status.node_info else "",
            "architecture": node.status.node_info.architecture if node.status.node_info else ""
        }
    
    def _parse_pod_status(self, pod) -> Dict[str, Any]:
        """解析Pod状态"""
        return {
            "name": f"{pod.metadata.namespace}/{pod.metadata.name}",
            "phase": pod.status.phase,
            "reason": pod.status.reason,
            "message": pod.status.message,
            "node": pod.spec.node_name,
            "containers": len(pod.spec.containers),
            "restart_count": sum(cs.restart_count for cs in (pod.status.container_statuses or [])),
            "conditions": {cond.type: cond.status for cond in (pod.status.conditions or [])}
        }
    
    def _parse_event(self, event) -> Dict[str, Any]:
        """解析事件"""
        return {
            "type": event.type,
            "reason": event.reason,
            "message": event.message,
            "count": event.count,
            "first_timestamp": event.first_timestamp,
            "last_timestamp": event.last_timestamp
        }