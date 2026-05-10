"""
自定义可观测性指标扩展 - 质量评估增强模块
================================================

本模块扩展了原有的质量评估系统，新增以下指标：
1. 回答简洁性评分 (Conciseness): 评估回答是否简洁、无冗余
2. 语言流畅度评分 (Fluency): 评估回答的语言表达是否流畅自然
3. 逻辑性评分 (Logic): 评估回答的结构逻辑是否清晰

作者: [你的姓名]
日期: 2025-05-10
"""

from openai import OpenAI
import json
import time
import re
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from observability_quality import QualityMetrics, QualityJudge


@dataclass
class ExtendedQualityMetrics:
    """扩展质量评估指标"""
    # 基础指标（继承原有）
    accuracy: float
    relevance: float
    helpfulness: float
    safety: float
    hallucination_score: float
    overall_score: float
    feedback: str
    
    # 新增扩展指标
    conciseness: float  # 简洁性: 1-10分，评估回答是否简洁无冗余
    fluency: float      # 流畅度: 1-10分，评估语言表达是否流畅
    logic: float        # 逻辑性: 1-10分，评估结构逻辑是否清晰
    extended_overall: float  # 扩展总分: 综合所有维度的平均分
    extended_feedback: str   # 扩展反馈: 针对新增维度的详细反馈


class ConcisenessEvaluator:
    """
    回答简洁性评估器
    
    评估维度：
    - 信息密度: 单位字数内的有效信息量
    - 冗余度: 是否存在重复、啰嗦的表达
    - 简洁度: 是否用最少字数表达完整意思
    """
    
    def __init__(self, client: OpenAI):
        self.client = client
    
    def calculate_conciseness_score(self, question: str, answer: str) -> Dict:
        """
        计算简洁性评分
        
        Args:
            question: 用户问题
            answer: 模型回答
            
        Returns:
            包含评分和反馈的字典
        """
        # 基础统计
        word_count = len(answer)
        sentence_count = len(re.findall(r'[。！？.!?]+', answer))
        sentence_count = max(sentence_count, 1)
        
        # 检测重复内容
        repeated_phrases = self._detect_repetition(answer)
        
        # 检测填充词
        filler_words = ['嗯', '啊', '呢', '吧', '那个', '这个', '就是', '其实', ' basically', ' actually']
        filler_count = sum(answer.count(fw) for fw in filler_words)
        
        evaluation_prompt = f"""请评估以下回答的简洁性（Conciseness），评分标准1-10分：

**问题**: {question}

**回答**: {answer}

**统计数据**: 
- 总字数: {word_count}
- 句子数: {sentence_count}
- 平均句长: {word_count/sentence_count:.1f}字
- 检测到的重复短语: {repeated_phrases if repeated_phrases else '无'}
- 填充词数量: {filler_count}

**评分维度**:
1. 信息密度 (4分): 每句话是否都包含有效信息，无废话
2. 表达精炼 (3分): 是否用最简练的方式表达，无冗余修饰
3. 结构紧凑 (3分): 是否存在重复内容或可以合并的句子

**输出要求**: 只返回JSON格式
{{"conciseness": 8, "feedback": "回答较为简洁，但在XX部分可以更精炼..."}}
"""
        
        try:
            response = self.client.chat.completions.create(
                model="qwen3.5:9b",
                messages=[{"role": "user", "content": evaluation_prompt}],
                temperature=0.1
            )
            
            content = response.choices[0].message.content
            result = self._extract_json(content)
            
            if result:
                return {
                    "score": float(result.get("conciseness", 5)),
                    "feedback": result.get("feedback", "评估完成"),
                    "statistics": {
                        "word_count": word_count,
                        "sentence_count": sentence_count,
                        "avg_sentence_length": word_count / sentence_count,
                        "repeated_phrases": repeated_phrases,
                        "filler_count": filler_count
                    }
                }
        except Exception as e:
            print(f"简洁性评估出错: {e}")
        
        # 出错时返回基于统计的默认评分
        return self._fallback_conciseness_score(answer, word_count, sentence_count)
    
    def _detect_repetition(self, text: str) -> List[str]:
        """检测文本中的重复短语"""
        # 检测连续重复的2-4字短语
        repeated = []
        for length in [4, 3, 2]:
            seen = set()
            for i in range(len(text) - length + 1):
                phrase = text[i:i+length]
                if phrase in seen:
                    repeated.append(phrase)
                else:
                    seen.add(phrase)
            if repeated:
                break
        return list(set(repeated))[:3]  # 最多返回3个
    
    def _fallback_conciseness_score(self, answer: str, word_count: int, sentence_count: int) -> Dict:
        """基于统计的备用评分"""
        avg_sentence_length = word_count / max(sentence_count, 1)
        
        # 中文回答理想句长: 20-40字
        if 20 <= avg_sentence_length <= 40:
            score = 8
        elif avg_sentence_length < 20:
            score = 7  # 可能过于简短
        else:
            score = 6  # 句子过长
        
        return {
            "score": score,
            "feedback": f"基于统计的评分。平均句长{avg_sentence_length:.1f}字，总字数{word_count}。",
            "statistics": {
                "word_count": word_count,
                "sentence_count": sentence_count,
                "avg_sentence_length": avg_sentence_length
            }
        }
    
    def _extract_json(self, content: str) -> Optional[Dict]:
        """从文本中提取JSON"""
        import re
        try:
            return json.loads(content.strip())
        except:
            pass
        
        # 尝试从代码块提取
        pattern = r'```(?:json)?\s*([\s\S]*?)```'
        matches = re.findall(pattern, content)
        for match in matches:
            try:
                return json.loads(match.strip())
            except:
                continue
        
        # 尝试匹配JSON对象
        pattern = r'\{[\s\S]*?\}'
        matches = re.findall(pattern, content)
        for match in matches:
            try:
                return json.loads(match.strip())
            except:
                continue
        
        return None


class FluencyEvaluator:
    """
    语言流畅度评估器
    
    评估维度：
    - 语法正确性: 是否存在语法错误
    - 表达自然度: 是否符合自然语言习惯
    - 连贯性: 句子之间衔接是否流畅
    """
    
    def __init__(self, client: OpenAI):
        self.client = client
    
    def calculate_fluency_score(self, question: str, answer: str) -> Dict:
        """
        计算流畅度评分
        
        Args:
            question: 用户问题
            answer: 模型回答
            
        Returns:
            包含评分和反馈的字典
        """
        # 基础统计
        sentence_count = len(re.findall(r'[。！？.!?]+', answer))
        sentence_count = max(sentence_count, 1)
        
        # 检测语法问题标记
        grammar_issues = self._detect_grammar_issues(answer)
        
        evaluation_prompt = f"""请评估以下回答的语言流畅度（Fluency），评分标准1-10分：

**问题**: {question}

**回答**: {answer}

**检测到的潜在问题**:
{grammar_issues if grammar_issues else '未发现明显的语法问题'}

**评分维度**:
1. 语法正确性 (4分): 是否存在语法错误、错别字、用词不当
2. 表达自然度 (3分): 是否符合中文表达习惯，不生硬、不机器化
3. 连贯性与衔接 (3分): 句子之间过渡是否自然，逻辑连接词使用是否恰当

**输出要求**: 只返回JSON格式
{{"fluency": 8, "feedback": "语言流畅自然，但在XX处衔接可以更顺畅..."}}
"""
        
        try:
            response = self.client.chat.completions.create(
                model="qwen3.5:9b",
                messages=[{"role": "user", "content": evaluation_prompt}],
                temperature=0.1
            )
            
            content = response.choices[0].message.content
            result = self._extract_json(content)
            
            if result:
                return {
                    "score": float(result.get("fluency", 5)),
                    "feedback": result.get("feedback", "评估完成"),
                    "issues": grammar_issues
                }
        except Exception as e:
            print(f"流畅度评估出错: {e}")
        
        return {
            "score": 7,
            "feedback": "基于规则的默认评分，模型评估失败。",
            "issues": grammar_issues
        }
    
    def _detect_grammar_issues(self, text: str) -> List[str]:
        """检测潜在的语法问题"""
        issues = []
        
        # 检测重复标点
        if re.search(r'[，,]{2,}', text):
            issues.append("重复标点符号")
        
        # 检测中英文标点混用
        if re.search(r'[，。！？][,.!?]', text) or re.search(r'[,.!?][，。！？]', text):
            issues.append("中英文标点混用")
        
        # 检测过长的句子（超过100字无标点）
        long_sentences = re.findall(r'[^，。！？,\.!?]{100,}', text)
        if long_sentences:
            issues.append(f"存在{len(long_sentences)}个超长句子")
        
        # 检测重复词语
        repeats = re.findall(r'(\w{2,})\1', text)
        if repeats:
            issues.append(f"存在重复词语: {set(repeats)}")
        
        return issues
    
    def _extract_json(self, content: str) -> Optional[Dict]:
        """从文本中提取JSON"""
        import re
        try:
            return json.loads(content.strip())
        except:
            pass
        
        pattern = r'```(?:json)?\s*([\s\S]*?)```'
        matches = re.findall(pattern, content)
        for match in matches:
            try:
                return json.loads(match.strip())
            except:
                continue
        
        pattern = r'\{[\s\S]*?\}'
        matches = re.findall(pattern, content)
        for match in matches:
            try:
                return json.loads(match.strip())
            except:
                continue
        
        return None


class LogicEvaluator:
    """
    逻辑性评估器
    
    评估回答的结构逻辑是否清晰合理
    """
    
    def __init__(self, client: OpenAI):
        self.client = client
    
    def calculate_logic_score(self, question: str, answer: str) -> Dict:
        """计算逻辑性评分"""
        
        # 分析回答结构
        structure = self._analyze_structure(answer)
        
        evaluation_prompt = f"""请评估以下回答的逻辑性（Logic），评分标准1-10分：

**问题**: {question}

**回答**: {answer}

**结构分析**:
- 段落数: {structure['paragraph_count']}
- 句子数: {structure['sentence_count']}
- 是否使用分点: {'是' if structure['has_list'] else '否'}
- 是否有过渡词: {'是' if structure['has_transitions'] else '否'}

**评分维度**:
1. 结构清晰 (4分): 是否有明确的开头、主体、结尾，层次分明
2. 论证合理 (3分): 论据是否支持论点，推理是否合理
3. 逻辑连贯 (3分): 各部分之间逻辑关系是否清晰，无跳跃

**输出要求**: 只返回JSON格式
{{"logic": 8, "feedback": "逻辑结构清晰，论证充分，但XX部分过渡可以更自然..."}}
"""
        
        try:
            response = self.client.chat.completions.create(
                model="qwen3.5:9b",
                messages=[{"role": "user", "content": evaluation_prompt}],
                temperature=0.1
            )
            
            content = response.choices[0].message.content
            result = self._extract_json(content)
            
            if result:
                return {
                    "score": float(result.get("logic", 5)),
                    "feedback": result.get("feedback", "评估完成"),
                    "structure": structure
                }
        except Exception as e:
            print(f"逻辑性评估出错: {e}")
        
        return {
            "score": 7,
            "feedback": "基于规则的默认评分。",
            "structure": structure
        }
    
    def _analyze_structure(self, text: str) -> Dict:
        """分析文本结构特征"""
        paragraphs = [p for p in text.split('\n') if p.strip()]
        sentences = re.findall(r'[^。！？.!?]+[。！？.!?]', text)
        
        # 检测分点
        has_list = bool(re.search(r'[\d一二三四五六七八九十]\s*[.、\.]', text))
        
        # 检测过渡词
        transition_words = ['首先', '其次', '然后', '接着', '最后', '总之', '因此', '但是', '然而', '另外']
        has_transitions = any(word in text for word in transition_words)
        
        return {
            "paragraph_count": len(paragraphs),
            "sentence_count": len(sentences),
            "has_list": has_list,
            "has_transitions": has_transitions
        }
    
    def _extract_json(self, content: str) -> Optional[Dict]:
        """从文本中提取JSON"""
        import re
        try:
            return json.loads(content.strip())
        except:
            pass
        
        pattern = r'```(?:json)?\s*([\s\S]*?)```'
        matches = re.findall(pattern, content)
        for match in matches:
            try:
                return json.loads(match.strip())
            except:
                continue
        
        pattern = r'\{[\s\S]*?\}'
        matches = re.findall(pattern, content)
        for match in matches:
            try:
                return json.loads(match.strip())
            except:
                continue
        
        return None


class ExtendedQualityJudge(QualityJudge):
    """
    扩展质量评估器
    
    在原有质量评估基础上，新增简洁性、流畅度、逻辑性三个维度
    """
    
    def __init__(self, 
                 judge_model: str = "qwen3.5:9b",
                 target_model: str = "qwen3.5:9b",
                 base_url: str = "http://localhost:11434/v1"):
        super().__init__(judge_model, target_model, base_url)
        
        # 初始化新增评估器
        self.conciseness_evaluator = ConcisenessEvaluator(self.client)
        self.fluency_evaluator = FluencyEvaluator(self.client)
        self.logic_evaluator = LogicEvaluator(self.client)
    
    def evaluate_answer_extended(self, 
                                question: str, 
                                answer: str,
                                reference_answer: Optional[str] = None) -> ExtendedQualityMetrics:
        """
        执行扩展质量评估
        
        Args:
            question: 问题
            answer: 模型回答
            reference_answer: 参考答案（可选）
            
        Returns:
            ExtendedQualityMetrics 扩展质量指标
        """
        print("\n🔍 执行基础质量评估...")
        # 先执行基础评估
        base_metrics = self.evaluate_answer(question, answer, reference_answer)
        
        print("📝 评估回答简洁性...")
        # 评估简洁性
        conciseness_result = self.conciseness_evaluator.calculate_conciseness_score(question, answer)
        print(f"   简洁性评分: {conciseness_result['score']}/10")
        
        print("💬 评估语言流畅度...")
        # 评估流畅度
        fluency_result = self.fluency_evaluator.calculate_fluency_score(question, answer)
        print(f"   流畅度评分: {fluency_result['score']}/10")
        
        print("🧠 评估逻辑性...")
        # 评估逻辑性
        logic_result = self.logic_evaluator.calculate_logic_score(question, answer)
        print(f"   逻辑性评分: {logic_result['score']}/10")
        
        # 计算扩展总分
        extended_overall = (
            base_metrics.overall_score * 0.4 +  # 基础指标占40%
            conciseness_result['score'] * 0.2 +  # 简洁性占20%
            fluency_result['score'] * 0.2 +      # 流畅度占20%
            logic_result['score'] * 0.2          # 逻辑性占20%
        )
        
        # 生成扩展反馈
        extended_feedback = f"""
【简洁性评估】{conciseness_result['feedback']}
统计信息: 字数{conciseness_result['statistics']['word_count']}, 
句数{conciseness_result['statistics']['sentence_count']}, 
平均句长{conciseness_result['statistics']['avg_sentence_length']:.1f}字

【流畅度评估】{fluency_result['feedback']}
潜在问题: {', '.join(fluency_result['issues']) if fluency_result['issues'] else '无'}

【逻辑性评估】{logic_result['feedback']}
结构分析: {logic_result['structure']['paragraph_count']}段落, 
{logic_result['structure']['sentence_count']}句子, 
{'使用' if logic_result['structure']['has_list'] else '未使用'}分点, 
{'使用' if logic_result['structure']['has_transitions'] else '未使用'}过渡词
        """.strip()
        
        # 构建扩展指标
        extended_metrics = ExtendedQualityMetrics(
            # 基础指标
            accuracy=base_metrics.accuracy,
            relevance=base_metrics.relevance,
            helpfulness=base_metrics.helpfulness,
            safety=base_metrics.safety,
            hallucination_score=base_metrics.hallucination_score,
            overall_score=base_metrics.overall_score,
            feedback=base_metrics.feedback,
            # 新增指标
            conciseness=conciseness_result['score'],
            fluency=fluency_result['score'],
            logic=logic_result['score'],
            extended_overall=round(extended_overall, 2),
            extended_feedback=extended_feedback
        )
        
        # 记录扩展评估历史
        self.evaluation_history.append({
            "timestamp": time.time(),
            "question": question,
            "answer": answer,
            "reference_answer": reference_answer,
            "metrics": asdict(extended_metrics)
        })
        
        return extended_metrics
    
    def print_extended_evaluation_report(self):
        """打印扩展评估报告"""
        if not self.evaluation_history:
            print("暂无评估记录")
            return
        
        # 计算平均值
        metrics_list = [h["metrics"] for h in self.evaluation_history]
        
        print("\n" + "="*80)
        print("📊 扩展质量评估汇总报告")
        print("="*80)
        print(f"总评估次数: {len(metrics_list)}")
        
        print(f"\n🎯 基础指标平均分:")
        print(f"  准确度: {sum(m['accuracy'] for m in metrics_list)/len(metrics_list):.2f}")
        print(f"  相关性: {sum(m['relevance'] for m in metrics_list)/len(metrics_list):.2f}")
        print(f"  有用性: {sum(m['helpfulness'] for m in metrics_list)/len(metrics_list):.2f}")
        print(f"  安全性: {sum(m['safety'] for m in metrics_list)/len(metrics_list):.2f}")
        print(f"  幻觉评分: {sum(m['hallucination_score'] for m in metrics_list)/len(metrics_list):.2f}")
        print(f"  基础总分: {sum(m['overall_score'] for m in metrics_list)/len(metrics_list):.2f}")
        
        print(f"\n✨ 新增指标平均分:")
        print(f"  简洁性: {sum(m['conciseness'] for m in metrics_list)/len(metrics_list):.2f}")
        print(f"  流畅度: {sum(m['fluency'] for m in metrics_list)/len(metrics_list):.2f}")
        print(f"  逻辑性: {sum(m['logic'] for m in metrics_list)/len(metrics_list):.2f}")
        print(f"  扩展总分: {sum(m['extended_overall'] for m in metrics_list)/len(metrics_list):.2f}")
        
        print("="*80 + "\n")


def test_extended_quality_evaluation():
    """测试扩展质量评估系统"""
    
    print("="*80)
    print("🎯 扩展质量可观测性实战 - 新增简洁性、流畅度、逻辑性评估")
    print("="*80)
    
    judge = ExtendedQualityJudge(
        judge_model="qwen3.5:9b",
        target_model="qwen3.5:9b"
    )
    
    test_cases = [
        {
            "question": "请解释什么是机器学习？",
            "reference_answer": "机器学习是人工智能的一个分支，通过算法让计算机从数据中学习规律，无需显式编程。"
        },
        {
            "question": "如何学习Python编程？",
            "reference_answer": None
        },
        {
            "question": "请描述一下北京的气候特点。",
            "reference_answer": None
        }
    ]
    
    print(f"\n📝 开始评估 {len(test_cases)} 个测试用例（含扩展指标）...\n")
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"[{i}/{len(test_cases)}] 问题: {test_case['question']}")
        print(f"{'='*80}")
        
        answer = judge.generate_answer(test_case["question"])
        print(f"\n💬 模型回答:\n{answer}\n")
        
        metrics = judge.evaluate_answer_extended(
            question=test_case["question"],
            answer=answer,
            reference_answer=test_case.get("reference_answer")
        )
        
        print(f"\n📊 评估结果:")
        print(f"  基础总分: {metrics.overall_score:.2f}/10")
        print(f"  扩展总分: {metrics.extended_overall:.2f}/10")
        print(f"\n  基础指标:")
        print(f"    准确度: {metrics.accuracy}/10")
        print(f"    相关性: {metrics.relevance}/10")
        print(f"    有用性: {metrics.helpfulness}/10")
        print(f"    安全性: {metrics.safety}/10")
        print(f"    幻觉评分: {metrics.hallucination_score}/10")
        print(f"\n  扩展指标:")
        print(f"    简洁性: {metrics.conciseness}/10 ⭐新增")
        print(f"    流畅度: {metrics.fluency}/10 ⭐新增")
        print(f"    逻辑性: {metrics.logic}/10 ⭐新增")
        print(f"\n📝 详细反馈:\n{metrics.extended_feedback}")
        
        time.sleep(2)
    
    judge.print_extended_evaluation_report()
    
    print("\n💡 思考问题:")
    print("   1. 新增的简洁性、流畅度、逻辑性指标如何帮助改进模型回答质量？")
    print("   2. 扩展指标与基础指标的关系是什么？如何设置合理的权重？")
    print("   3. 在工业场景中，如何将这些指标应用于模型选型和优化？")
    print("   4. 还有哪些维度可以进一步扩展（如创造性、专业性、可读性等）？")


if __name__ == "__main__":
    test_extended_quality_evaluation()
