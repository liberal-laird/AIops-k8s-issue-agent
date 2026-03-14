import re
from typing import Optional
from .models import UserInput

class UserInputParser:
    """用户输入解析器"""
    
    def __init__(self):
        # 定义常见模式
        self.node_patterns = [
            r'节点\s*(\w+)',
            r'node\s*(\w+)',
            r'(\w+)\s*节点',
            r'(\w+)\s*node'
        ]
        
        self.pod_patterns = [
            r'pod\s*([a-zA-Z0-9\-_]+)',
            r'容器\s*([a-zA-Z0-9\-_]+)',
            r'([a-zA-Z0-9\-_]+)\s*pod'
        ]
        
        self.namespace_patterns = [
            r'命名空间\s*(\w+)',
            r'namespace\s*(\w+)',
            r'在\s*(\w+)\s*中'
        ]
        
        self.issue_patterns = {
            'memory': [r'内存', r'memory', r'oom'],
            'disk': [r'磁盘', r'disk', r'storage'],
            'network': [r'网络', r'network', r'connection'],
            'cpu': [r'cpu', r'处理器', r'计算资源'],
            'restart': [r'重启', r'restart', r'crash'],
            'not_ready': [r'not ready', r'未就绪', r'notready']
        }
    
    def parse(self, user_input: str) -> UserInput:
        """解析用户输入"""
        parsed = UserInput(raw_input=user_input)
        
        # 提取节点ID
        for pattern in self.node_patterns:
            match = re.search(pattern, user_input, re.IGNORECASE)
            if match:
                parsed.node_id = match.group(1)
                break
        
        # 提取Pod ID
        for pattern in self.pod_patterns:
            match = re.search(pattern, user_input, re.IGNORECASE)
            if match:
                parsed.pod_id = match.group(1)
                break
        
        # 提取命名空间
        for pattern in self.namespace_patterns:
            match = re.search(pattern, user_input, re.IGNORECASE)
            if match:
                parsed.namespace = match.group(1)
                break
        
        # 提取问题类型
        for issue_type, patterns in self.issue_patterns.items():
            for pattern in patterns:
                if re.search(pattern, user_input, re.IGNORECASE):
                    parsed.issue_type = issue_type
                    break
            if parsed.issue_type:
                break
        
        # 提取报警信息
        if '报警' in user_input or 'alert' in user_input.lower():
            parsed.alert_message = user_input
        
        return parsed