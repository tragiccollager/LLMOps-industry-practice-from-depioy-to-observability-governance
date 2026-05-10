from mcp.server.fastmcp import FastMCP
from datetime import datetime
import ast
import operator
import re
import json
import random
import base64
import hashlib

mcp = FastMCP("ToolServer")

@mcp.tool()
def get_current_time() -> str:
    """
    获取当前时间
    
    返回格式化的当前时间字符串
    """
    now = datetime.now()
    return f"当前时间是 {now.strftime('%Y年%m月%d日 %H:%M:%S')}"

class SafeCalculator:
    """安全的数学表达式计算器"""
    
    # 支持的操作符映射
    operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    
    @staticmethod
    def validate_expression(expression: str) -> bool:
        """
        验证表达式是否只包含允许的字符
        
        Args:
            expression: 数学表达式
            
        Returns:
            bool: 是否有效
        """
        # 只允许数字、运算符、括号和空格
        pattern = r'^[\d\s+\-*/().]+$'
        if not re.match(pattern, expression):
            return False
        
        # 检查是否包含危险模式
        dangerous_patterns = [
            '__',      # dunder 方法
            'import',  # import 语句
            'exec',    # exec 函数
            'eval',    # eval 函数
            'open',    # 文件操作
            'os.',     # os 模块
            'sys.',    # sys 模块
        ]
        
        expression_lower = expression.lower()
        for pattern in dangerous_patterns:
            if pattern in expression_lower:
                return False
        
        return True
    
    @staticmethod
    def safe_eval(node):
        """
        安全地递归计算 AST 节点
        
        Args:
            node: AST 节点
            
        Returns:
            计算结果
            
        Raises:
            ValueError: 无效的表达式
        """
        if isinstance(node, ast.Constant):  # Python 3.8+
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("只支持数字常量")
        
        elif isinstance(node, ast.BinOp):
            left = SafeCalculator.safe_eval(node.left)
            right = SafeCalculator.safe_eval(node.right)
            op_type = type(node.op)
            if op_type in SafeCalculator.operators:
                return SafeCalculator.operators[op_type](left, right)
            raise ValueError(f"不支持的操作符: {op_type.__name__}")
        
        elif isinstance(node, ast.UnaryOp):
            operand = SafeCalculator.safe_eval(node.operand)
            op_type = type(node.op)
            if op_type in SafeCalculator.operators:
                return SafeCalculator.operators[op_type](operand)
            raise ValueError(f"不支持的一元操作符: {op_type.__name__}")
        
        elif isinstance(node, ast.Expression):
            return SafeCalculator.safe_eval(node.body)
        
        elif isinstance(node, ast.Call):
            raise ValueError("不允许调用函数")
        
        elif isinstance(node, ast.Name):
            raise ValueError("不允许使用变量")
        
        elif isinstance(node, ast.Attribute):
            raise ValueError("不允许访问属性")
        
        else:
            raise ValueError(f"不支持的表达式类型: {type(node).__name__}")
    
    @classmethod
    def calculate(cls, expression: str) -> float:
        """
        计算数学表达式的值
        
        Args:
            expression: 数学表达式，例如 "2+3*4" 或 "(10+5)/3"
            
        Returns:
            计算结果
            
        Raises:
            ValueError: 表达式无效或包含不支持的操作
        """
        # 去除空白字符
        expression = expression.strip()
        
        # 验证字符安全性
        if not cls.validate_expression(expression):
            raise ValueError("表达式包含非法字符")
        
        # 检查表达式长度（防止过大的表达式）
        if len(expression) > 200:
            raise ValueError("表达式过长")
        
        # 使用 AST 安全解析
        try:
            tree = ast.parse(expression, mode='eval')
            result = cls.safe_eval(tree)
            return result
        except SyntaxError as e:
            raise ValueError(f"语法错误: {str(e)}")
        except ValueError as e:
            raise ValueError(f"计算错误: {str(e)}")

@mcp.tool()
def calculate(expression: str) -> str:
    """
    执行数学计算（安全版本）
    
    Args:
        expression: 数学表达式，例如 "2+3*4" 或 "(10+5)/3"
    
    Returns:
        计算结果的字符串形式
    """
    try:
        result = SafeCalculator.calculate(expression)
        return f"{expression} = {result}"
    except ValueError as e:
        return f"错误：{str(e)}"
    except Exception as e:
        return f"计算错误：{str(e)}"


# ============================================================
# 新增本地 MCP 工具
# ============================================================

@mcp.tool()
def count_words(text: str) -> str:
    """
    统计文本的字数和字符数
    
    Args:
        text: 要统计的文本内容
    
    Returns:
        字数统计结果
    """
    char_count = len(text)
    # 中文字符和英文单词统计
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    english_words = len(re.findall(r'[a-zA-Z]+', text))
    
    return f"字符总数: {char_count}, 中文字符: {chinese_chars}, 英文单词: {english_words}"


@mcp.tool()
def generate_random_number(min_value: int = 1, max_value: int = 100) -> str:
    """
    生成指定范围内的随机整数
    
    Args:
        min_value: 最小值（包含）
        max_value: 最大值（包含）
    
    Returns:
        随机数结果
    """
    try:
        result = random.randint(min_value, max_value)
        return f"随机数 ({min_value}-{max_value}): {result}"
    except Exception as e:
        return f"生成随机数失败: {str(e)}"


@mcp.tool()
def base64_encode(text: str) -> str:
    """
    将文本进行 Base64 编码
    
    Args:
        text: 要编码的文本
    
    Returns:
        Base64 编码结果
    """
    try:
        encoded = base64.b64encode(text.encode('utf-8')).decode('utf-8')
        return f"Base64 编码结果: {encoded}"
    except Exception as e:
        return f"编码失败: {str(e)}"


@mcp.tool()
def base64_decode(encoded_text: str) -> str:
    """
    将 Base64 编码的文本解码
    
    Args:
        encoded_text: Base64 编码的文本
    
    Returns:
        解码后的原文
    """
    try:
        decoded = base64.b64decode(encoded_text.encode('utf-8')).decode('utf-8')
        return f"Base64 解码结果: {decoded}"
    except Exception as e:
        return f"解码失败: {str(e)}"


@mcp.tool()
def generate_md5(text: str) -> str:
    """
    生成文本的 MD5 哈希值
    
    Args:
        text: 要生成哈希的文本
    
    Returns:
        MD5 哈希值
    """
    try:
        md5_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
        return f"MD5 哈希值: {md5_hash}"
    except Exception as e:
        return f"生成哈希失败: {str(e)}"


@mcp.tool()
def format_json(json_string: str) -> str:
    """
    格式化 JSON 字符串
    
    Args:
        json_string: 要格式化的 JSON 字符串
    
    Returns:
        格式化后的 JSON
    """
    try:
        data = json.loads(json_string)
        formatted = json.dumps(data, indent=2, ensure_ascii=False)
        return f"格式化后的 JSON:\n{formatted}"
    except json.JSONDecodeError as e:
        return f"JSON 解析错误: {str(e)}"
    except Exception as e:
        return f"格式化失败: {str(e)}"


@mcp.tool()
def text_to_uppercase(text: str) -> str:
    """
    将文本转换为大写
    
    Args:
        text: 要转换的文本
    
    Returns:
        大写文本
    """
    return text.upper()


@mcp.tool()
def text_to_lowercase(text: str) -> str:
    """
    将文本转换为小写
    
    Args:
        text: 要转换的文本
    
    Returns:
        小写文本
    """
    return text.lower()


@mcp.tool()
def get_day_of_week(date_string: str = "") -> str:
    """
    获取指定日期是星期几
    
    Args:
        date_string: 日期字符串，格式为 YYYY-MM-DD，空字符串表示今天
    
    Returns:
        星期几
    """
    try:
        if date_string:
            date_obj = datetime.strptime(date_string, "%Y-%m-%d")
        else:
            date_obj = datetime.now()
        
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        weekday = weekdays[date_obj.weekday()]
        
        if date_string:
            return f"{date_string} 是 {weekday}"
        else:
            return f"今天是 {weekday}"
    except ValueError:
        return "日期格式错误，请使用 YYYY-MM-DD 格式"
    except Exception as e:
        return f"查询失败: {str(e)}"


@mcp.tool()
def generate_password(length: int = 12) -> str:
    """
    生成随机密码
    
    Args:
        length: 密码长度（默认 12，建议 8-32）
    
    Returns:
        生成的随机密码
    """
    try:
        if length < 4:
            return "密码长度至少为 4"
        if length > 128:
            return "密码长度不能超过 128"
        
        # 包含大小写字母、数字和特殊字符
        characters = (
            "abcdefghijklmnopqrstuvwxyz"
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "0123456789"
            "!@#$%^&*"
        )
        
        # 确保包含各类字符
        password = [
            random.choice("abcdefghijklmnopqrstuvwxyz"),
            random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
            random.choice("0123456789"),
            random.choice("!@#$%^&*")
        ]
        
        # 填充剩余长度
        password += random.choices(characters, k=length - 4)
        random.shuffle(password)
        
        result = ''.join(password)
        return f"生成的密码 ({length}位): {result}"
    except Exception as e:
        return f"生成密码失败: {str(e)}"


if __name__ == "__main__":
    mcp.run(transport='stdio')
