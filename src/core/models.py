from typing import Dict, List, Optional, Literal, Any
from pydantic import BaseModel, Field
from datetime import datetime

class UserInput(BaseModel):
    """用户输入解析结果"""
    raw_input: str
    node_id: Optional[str] = None
    pod_id: Optional[str] = None
    namespace: Optional[str] = None
    issue_type: Optional[str] = None
    alert_message: Optional[str] = None

class ToolCallResult(BaseModel):
    """工具调用结果"""
    tool_name: str
    timestamp: datetime = Field(default_factory=datetime.now)
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    parsed_data: Optional[Dict[str, Any]] = None

class DiagnosticState(BaseModel):
    """诊断状态管理"""
    user_input: UserInput
    current_step: int = 0
    max_steps: int = 10
    completed: bool = False
    tool_calls: List[ToolCallResult] = Field(default_factory=list)
    findings: Dict[str, Any] = Field(default_factory=dict)
    analysis_result: Optional[str] = None
    final_recommendation: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True