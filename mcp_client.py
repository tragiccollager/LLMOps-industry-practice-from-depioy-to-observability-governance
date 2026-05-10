from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import OpenAI
import json
import asyncio
import os


# ============================================================
# 第三方 MCP Server 配置示例
# ============================================================

def get_local_server_params():
    """本地 MCP Server 配置"""
    return StdioServerParameters(
        command="python",
        args=["mcp_server.py"]
    )


def get_github_server_params():
    """
    GitHub MCP Server 配置（第三方）
    需要先安装: npm install -g @modelcontextprotocol/server-github
    或运行: npx -y @modelcontextprotocol/server-github
    """
    return StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-github"],
        env={
            **os.environ,  # 继承当前环境变量
            "GITHUB_PERSONAL_ACCESS_TOKEN": os.getenv("GITHUB_TOKEN", "your_github_token_here")
        }
    )


def get_filesystem_server_params():
    """
    文件系统 MCP Server 配置（第三方）
    允许 LLM 读写本地文件
    """
    return StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/directory"]
    )


def get_postgres_server_params():
    """
    PostgreSQL MCP Server 配置（第三方）
    允许 LLM 查询数据库
    """
    return StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-postgres", 
                os.getenv("DATABASE_URL", "postgresql://localhost/mydb")]
    )


# ============================================================
# MCP 客户端核心逻辑
# ============================================================

async def call_mcp_server(server_params: StdioServerParameters, query: str, 
                          server_name: str = "MCP Server"):
    """
    调用 MCP Server 的通用函数
    
    Args:
        server_params: MCP Server 配置参数
        query: 用户查询
        server_name: 服务器名称（用于显示）
    """
    print(f"\n{'=' * 70}")
    print(f"🌐 连接到 {server_name}")
    print(f"{'=' * 70}")
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            tools_response = await session.list_tools()
            
            print(f"\n📡 {server_name} 提供的工具：")
            for tool in tools_response.tools:
                print(f"  - {tool.name}: {tool.description[:50]}...")
            
            llm_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema
                    }
                }
                for tool in tools_response.tools
            ]
            
            client = OpenAI(base_url='http://localhost:11434/v1', api_key='local')
            
            print(f"\n📝 用户查询: {query}")
            
            response = client.chat.completions.create(
                model="qwen3.5:9b",
                messages=[{"role": "user", "content": query}],
                tools=llm_tools,
                tool_choice="auto"
            )
            
            message = response.choices[0].message
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    func_name = tool_call.function.name
                    func_args = json.loads(tool_call.function.arguments)
                    print(f"\n🔧 调用工具: {func_name}")
                    print(f"📊 参数: {func_args}")
                    
                    result = await session.call_tool(
                        func_name,
                        arguments=func_args
                    )
                    
                    result_text = result.content[0].text
                    print(f"✅ 执行结果: {result_text[:200]}...")
                    return result_text
            else:
                print(f"💬 直接回复: {message.content}")
                return message.content


async def main():
    """
    主函数：演示如何调用不同的 MCP Server
    """
    print("=" * 70)
    print("MCP 架构工具调用 - 支持本地和第三方 Server")
    print("=" * 70)
    
    # --------------------------------------------------------
    # 示例 1: 调用本地 MCP Server（计算、获取时间）
    # --------------------------------------------------------
    await call_mcp_server(
        server_params=get_local_server_params(),
        query="现在几点了？计算 256 * 1024，顺便统计一下这句话有多少个字",
        server_name="本地工具 Server"
    )
    
    # --------------------------------------------------------
    # 示例 2: 调用第三方 GitHub MCP Server（需要配置 GITHUB_TOKEN）
    # --------------------------------------------------------
    print("\n⏳ 正在连接第三方 GitHub MCP Server...")
    try:
        await call_mcp_server(
            server_params=get_github_server_params(),
            query="搜索关于 'machine learning' 的仓库，找出星标最多的前5个",
            server_name="GitHub MCP Server"
        )
    except Exception as e:
        print(f"❌ GitHub Server 调用失败: {e}")
        print("💡 提示：请确保已安装 Node.js，并且 GITHUB_TOKEN 有效")
    
    # --------------------------------------------------------
    # 示例 3: 调用第三方文件系统 MCP Server（需要配置路径）
    # --------------------------------------------------------
    # await call_mcp_server(
    #     server_params=get_filesystem_server_params(),
    #     query="列出允许目录下的所有文件",
    #     server_name="文件系统 MCP Server"
    # )
    
    # --------------------------------------------------------
    # 示例 4: 调用第三方 PostgreSQL MCP Server（需要配置数据库连接）
    # --------------------------------------------------------
    # await call_mcp_server(
    #     server_params=get_postgres_server_params(),
    #     query="查询用户表中前10条记录",
    #     server_name="PostgreSQL MCP Server"
    # )
    
    print("\n" + "=" * 70)
    print("✅ 所有 MCP Server 调用完成")
    print("=" * 70)
    print("\n💡 提示：要测试第三方 Server，请：")
    print("   1. 确保已安装 Node.js 和 npx")
    print("   2. 设置必要的环境变量（如 GITHUB_TOKEN）")
    print("   3. 取消对应示例代码的注释")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
