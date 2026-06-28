"""
评估指标计算器
计算各种评估指标
"""

from typing import List, Dict, Any, Optional
import math
import statistics
from collections import Counter
import numpy as np

class MetricsCalculator:
    """指标计算器"""

    def __init__(self):
        self.metrics = {}

    def calculate_accuracy(self, predictions: List[Any], references: List[Any]) -> float:
        """计算准确率"""
        if not predictions or len(predictions) != len(references):
            return 0.0
        
        correct = sum(1 for p, r in zip(predictions, references) if p == r)
        return correct / len(predictions)
    
    def calculate_precision_recall_f1(
        self,
        predictions: List[Any],
        references: List[Any],
        positive_label: Any = 1
    ) -> Dict[str, float]:
        """计算精确率、召回率和 F1 分数"""
        # 转换为二分类
        tp = sum(1 for p, r in zip(predictions, references) if p == positive_label and r == positive_label)
        fp = sum(1 for p, r in zip(predictions, references) if p == positive_label and r != positive_label)
        fn = sum(1 for p, r in zip(predictions, references) if p != positive_label and r == positive_label)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1  = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        return {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "tp": tp,
            "fp": fp,
            "fn": fn
        }
    
    def calculate_rouge(
        self,
        predications: List[str],
        references: List[str]
    ) -> Dict[str, float]:
        """
        计算 ROUGE 分数(简化版)
        使用 n-gram 重叠
        """
        if not predications or len(predications) != len(references):
            return {"rouge-1": 0.0, "rouge-2": 0.0, "rouge-l": 0.0}
        
        rouge_scores = {"rouge-1": [], "rouge-2": [], "rouge-l": []}

        for pred, ref in zip(predications, references):
            # 分词
            pred_tokens = self._tokenize(pred)
            ref_tokens = self._tokenize(ref)

            # ROUGE-1(unigram)
            rouge_1 = self._calculate_ngram_overlap(pred_tokens, ref_tokens, 1)
            rouge_scores["rouge-1"].append(rouge_1)

            # ROUGE-2(bigram)
            rouge_2 = self._calculate_ngram_overlap(pred_tokens, ref_tokens, 2)
            rouge_scores["rouge-2"].append(rouge_2)

            # ROUGE_L(LCS)
            rouge_l = self._calculate_lcs(pred_tokens, ref_tokens)
            rouge_scores["rouge-l"].append(rouge_l)
        
        return {
            "rouge-1": statistics.mean(rouge_scores["rouge-1"]) if rouge_scores["rouge-1"] else 0,
            "rouge-2": statistics.mean(rouge_scores["rouge-2"]) if rouge_scores["rouge-2"] else 0,
            "rouge-l": statistics.mean(rouge_scores["rouge-l"]) if rouge_scores["rouge-l"] else 0
        }
    
    def _tokenize(self, text: str) -> List[str]:
        """简单分词"""
        import re
        # 中英文分词
        tokens = re.findall(r"[\u4e00-\u9fff]|[a-zA-Z]+|[0-9]+", text)
        return tokens
    
    def _calculate_ngram_overlap(
        self,
        pred_tokens: List[str],
        ref_tokens: List[str],
        n: int
    ) -> float:
        """计算 n-gram 重叠"""
        if len(pred_tokens) < n or len(ref_tokens) < n:
            return 0.0
        
        pred_ngrams = set(zip(*[pred_tokens[i:] for i in range(n)]))
        ref_ngrams = set(zip(*[ref_tokens[i:] for i in range(n)]))

        if not pred_ngrams or not ref_ngrams:
            return 0.0
        
        overlap = len(pred_ngrams & ref_ngrams)

        return overlap / max(len(pred_ngrams), len(ref_ngrams))
    
    def _calculate_lcs(self, pred_tokens: List[str], ref_tokens: List[str]) -> float:
        """计算最长公共子序列"""
        if not pred_tokens or not ref_tokens:
            return 0.0
        
        # DP 计算 LCS 长度
        m, n = len(pred_tokens), len(ref_tokens)
        dp = [[0] * (n + 1) for _ in range(m + 1)]

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if pred_tokens[i - 1] == ref_tokens[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1] + 1
                else:
                    dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
        
        lcs_len = dp[m][n]
        return lcs_len / max(m, n)
    
    def calculate_bleu(
        self,
        predictions: List[str],
        references: List[str]
    ) -> float:
        """
        计算 BLEU 分数(简化版)
        """
        if not predictions or len(predictions) != len(references):
            return 0.0
        
        bleu_scores = []

        for pred, ref in zip(predictions, references):
            pred_tokens = self._tokenize(pred)
            ref_tokens = self._tokenize(ref)

            # 计算 1-4 gram precision
            precisions = []
            for n in range(1, 5):
                prec = self._calculate_ngram_precision(pred_tokens, ref_tokens, n)
                precisions.append(prec)

            # 简化的 BLEU
            if min(precisions) == 0:
                bleu = 0.0
            else:
                # 几何平均
                log_prec = sum(math.log(p) for p in precisions) / len(precisions)
                bleu = max.exp(log_prec)

            bleu_scores.append(bleu)

        return statistics.mean(bleu_scores) if bleu_scores else 0.0
    
    def _calculate_ngram_precision(
        self,
        pred_tokens: List[str],
        ref_tokens: List[str],
        n: int
    ) -> float:
        """计算 n-gram 精确率"""
        if len(pred_tokens) < n:
            return 0.0
        
        pred_ngrams = list(zip(*[pred_tokens[i:] for i in range(n)]))
        ref_ngrams = set(zip(*[ref_tokens[i:] for i in range(n)]))

        if not pred_ngrams:
            return 0.0
        
        matched = sum(1 for ngram in pred_ngrams if ngram in ref_ngrams)
        return matched / len(pred_ngrams)
    
    def calculate_error_rate(
        self,
        predictions: List[str],
        references: List[str]
    ) -> Dict[str, Dict]:
        """计算错误率"""
        if not predictions or len(predictions) != len(references):
            return {"wer": 1.0, "cer": 1.0}
        
        wer_scores = []
        cer_scores = []

        for pred, ref in zip(predictions, references):
            pred_tokens = self._tokenize(pred)
            ref_tokens = self._tokenize(ref)

            # 词错误率
            if ref_tokens:
                wer = self._levenshtein_distance(pred_tokens, ref_tokens) / len(ref_tokens)
                wer_scores.append(min(1.0, wer))

            # 字符错误率
            pred_chars = list(pred.replace(" ", ""))
            ref_chars = list(ref.replace(" ", ""))
            if ref_chars:
                cer = self._levenshtein_distance(pred_chars, ref_chars) / len(ref_chars)
                cer_scores.append(min(1.0, cer))

            return {
                "wer": statistics.mean(wer_scores) if wer_scores else 1.0,
                "cer": statistics.mean(cer_scores) if cer_scores else 1.0
            }
        
    def _levenshtein_distance(self, seq1: List, seq2: List) -> int:
        """计算 Levenshtein 距离"""
        m, n = len(seq1), len(seq2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]

        for i in range(m + 1):
            dp[i][0] = i
        for j in range(n + 1):
            dp[0][j] = j

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if seq1[i - 1] == seq2[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1]
                else:
                    dp[i][j] = min(dp[i -1][j], dp[i][j - 1], dp[i -1][j - 1]) + 1
        return dp[m][n]
    
    def calculate_response_time_stats(self, times: List[float]) -> Dict[str, float]:
        """计算响应时间统计"""
        if not times:
            return {"mean": 0, "median": 0, "p95": 0, "p99": 0}
        
        sorted_times = sorted(times)

        return {
            "mean": statistics.mean(times),
            "median": statistics.median(times),
            "min": min(times),
            "max": max(times),
            "p95": sorted_times[int(len(sorted_times) * 0.95)] if len(sorted_times) > 0 else 0,
            "p99": sorted_times[int(len(sorted_times) * 0.99)] if len(sorted_times) > 0 else 0,
            "std": statistics.stdev(times) if len(times) > 1 else 0
        }
    
    def calculate_confidence_interval(
        self,
        scores: List[float],
        confidence: float = 0.95
    ) -> Dict[str, float]:
        """计算置信区间"""
        if not scores:
            return {"mean": 0, "lower": 0, "upper": 0}
        
        mean = statistics.mean(scores)
        std = statistics.stdev(scores) if len(scores) > 1 else 0

        # 使用 z-score
        import scipy.stats as stats
        z_score = stats.norm.ppf((1 + confidence) / 2)

        margin = z_score * (std / math.sqrt(len(scores))) if std > 0 else 0

        return {
            "mean": mean,
            "lover": max(0, mean - margin),
            "upper": min(1, mean + margin)
        }