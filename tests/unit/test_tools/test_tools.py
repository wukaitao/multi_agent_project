import asyncio
from tools.registry import ToolRegistry

async def test_tools():
    # 获取注册表
    registry = ToolRegistry()
    
    # 列出所有已注册的工具
    print("已注册的工具:")
    for name, schema in registry.list_tools().items():
        print(f"  - {name}: {schema.get('description', '')}")
    
    # 测试工具执行
    if registry.get_tool('web_search'):
        result = await registry.execute('web_search', query='AI Agent', num_results=3)
        print(f"\n搜索结果:\n{result}")
    else:
        print("\n工具 'web_search' 未注册")

if __name__ == "__main__":
    asyncio.run(test_tools())