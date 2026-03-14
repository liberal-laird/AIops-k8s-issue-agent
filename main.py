import os
import sys
import logging
from k8s_diagnostic_agent import run_diagnostic

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """主函数"""
    print("Kubernetes AI智能诊断Agent (LangGraph)")
    print("=" * 50)
    
    # 获取用户输入
    if len(sys.argv) > 1:
        user_input = " ".join(sys.argv[1:])
    else:
        user_input = input("请输入要诊断的问题描述: ").strip()
        if not user_input:
            print("需要提供具体的诊断问题描述")
            return
    
    print(f"\n开始诊断: {user_input}")
    print("-" * 50)
    
    try:
        result = run_diagnostic(user_input)
        print("\n诊断结果:")
        print("=" * 50)
        print(result)
    except Exception as e:
        print(f"\n诊断过程中发生错误: {str(e)}")
        print("请确保:")
        print("1. 已配置kubectl并能正常访问集群")
        print("2. 当前用户有足够权限访问集群资源")
        print("3. 集群API服务器可访问")

if __name__ == "__main__":
    main()