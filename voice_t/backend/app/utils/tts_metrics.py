import os
import numpy as np
import torch
import librosa
import soundfile as sf
from typing import Dict, Optional, Tuple, List
from scipy.spatial.distance import cosine
from scipy.stats import pearsonr

class TTSMetrics:
    """TTS质量评估类，用于评估合成语音的质量"""
    
    def __init__(self, model_path: Optional[str] = None):
        """
        初始化TTS质量评估器
        
        Args:
            model_path: MOSNet质量评估模型的路径（可选）
        """
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # 尝试加载MOSNet评估模型
        self.mos_model = None
        if model_path and os.path.exists(model_path):
            try:
                self.mos_model = torch.jit.load(model_path)
                self.mos_model.to(self.device)
                self.mos_model.eval()
                print(f"MOSNet模型加载成功: {model_path}")
            except Exception as e:
                print(f"加载MOSNet模型失败: {e}")
        
    def evaluate_naturalness(self, audio_path: str) -> float:
        """
        评估语音的自然度（MOSNet或替代方法）
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            mos_score: 平均意见分数(Mean Opinion Score)，范围1-5
        """
        # 确保文件存在
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")
        
        # 加载音频
        y, sr = librosa.load(audio_path, sr=16000)  # MOSNet通常需要16kHz采样率
        
        # 使用MOSNet模型评估（如果可用）
        if self.mos_model is not None:
            try:
                return self._evaluate_with_mosnet(y, sr)
            except Exception as e:
                print(f"使用MOSNet评估失败: {e}")
                print("使用替代方法评估自然度")
        
        # 使用传统特征计算替代评分
        return self._evaluate_traditional(y, sr)
    
    def _evaluate_with_mosnet(self, y: np.ndarray, sr: int) -> float:
        """使用MOSNet模型评估MOS分数"""
        # 确保采样率为16kHz
        if sr != 16000:
            y = librosa.resample(y, orig_sr=sr, target_sr=16000)
        
        # 预处理音频
        y = librosa.util.normalize(y) * 0.95
        
        # 转换为张量
        audio_tensor = torch.FloatTensor(y).unsqueeze(0).to(self.device)
        
        # 使用MOSNet模型预测分数
        with torch.no_grad():
            mos_prediction = self.mos_model(audio_tensor).cpu().numpy()[0][0]
        
        # MOSNet通常输出范围在1-5之间
        return float(mos_prediction)
    
    def _evaluate_traditional(self, y: np.ndarray, sr: int) -> float:
        """使用传统声学特征估计语音质量"""
        # 检查音频长度
        duration = librosa.get_duration(y=y, sr=sr)
        if duration < 1.0:
            print("警告: 音频过短，评估可能不准确")
            return 3.0  # 默认中等分数
        
        # 提取各种与质量相关的特征
        
        # 1. 信噪比（SNR）估计
        # 使用信号的上下文最小值作为噪声估计
        frame_length = int(0.025 * sr)
        hop_length = int(0.010 * sr)
        
        # 计算RMS能量
        rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
        noise_floor = np.percentile(rms, 10)  # 使用10th百分位作为噪声地板
        if noise_floor > 0:
            snr = 10 * np.log10(np.mean(rms) / noise_floor)
        else:
            snr = 30  # 高信噪比
        
        # 2. 谐波噪声比（HNR）估计
        # 使用频谱对比度作为谐波结构指标
        spectral_contrast = np.mean(librosa.feature.spectral_contrast(y=y, sr=sr)[0])
        
        # 3. 音频动态范围
        dynamic_range = np.percentile(rms, 95) / np.percentile(rms, 5) if np.percentile(rms, 5) > 0 else 10
        
        # 4. 清晰度估计（频谱质心变化）
        spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        centroid_std = np.std(spectral_centroid) / np.mean(spectral_centroid) if np.mean(spectral_centroid) > 0 else 0
        
        # 5. 能量平滑度（表示语音平稳性）
        energy_smoothness = 1.0 - np.std(rms) / np.mean(rms) if np.mean(rms) > 0 else 0
        
        # 组合特征计算MOS估计
        # 参数权重是基于经验调整的
        mos_estimate = (
            3.0  # 基础分
            + min(1.0, snr / 30) * 0.7  # SNR贡献（最高0.7分）
            + min(1.0, spectral_contrast / 30) * 0.7  # 谐波结构贡献
            + max(-0.5, min(0.5, np.log10(dynamic_range) / 2))  # 动态范围贡献
            - max(0, min(0.5, centroid_std - 0.3)) * 0.5  # 频谱变化惩罚（如果过大）
            + min(0.6, energy_smoothness * 0.6)  # 能量平滑度贡献
        )
        
        # 限制在1-5范围内
        mos_estimate = max(1.0, min(5.0, mos_estimate))
        
        return float(mos_estimate)
    
    def evaluate_similarity(self, reference_path: str, synthesized_path: str) -> float:
        """
        评估合成语音与参考音频的相似度
        
        Args:
            reference_path: 参考语音文件路径
            synthesized_path: 合成语音文件路径
            
        Returns:
            similarity_score: 相似度分数，范围0-1
        """
        try:
            # 加载音频
            ref_y, ref_sr = librosa.load(reference_path, sr=None)
            syn_y, syn_sr = librosa.load(synthesized_path, sr=None)
            
            # 确保相同的采样率
            if ref_sr != syn_sr:
                syn_y = librosa.resample(syn_y, orig_sr=syn_sr, target_sr=ref_sr)
                syn_sr = ref_sr
            
            # 提取MFCC特征
            ref_mfcc = librosa.feature.mfcc(y=ref_y, sr=ref_sr, n_mfcc=13)
            syn_mfcc = librosa.feature.mfcc(y=syn_y, sr=syn_sr, n_mfcc=13)
            
            # 如果长度不同，截断到较短的长度
            min_len = min(ref_mfcc.shape[1], syn_mfcc.shape[1])
            ref_mfcc = ref_mfcc[:, :min_len]
            syn_mfcc = syn_mfcc[:, :min_len]
            
            # 计算每帧MFCC的相似度
            frame_similarities = []
            for i in range(min_len):
                cos_sim = 1 - cosine(ref_mfcc[:, i], syn_mfcc[:, i])
                frame_similarities.append(cos_sim)
            
            # 取平均值作为整体相似度
            similarity = np.mean(frame_similarities)
            
            # 归一化到0-1范围
            similarity = (similarity + 1) / 2
            
            return float(similarity)
            
        except Exception as e:
            print(f"计算语音相似度失败: {e}")
            return 0.5  # 出错时返回中等相似度
    
    def evaluate_clarity(self, audio_path: str) -> float:
        """
        评估语音的清晰度
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            clarity_score: 清晰度分数，范围0-1
        """
        try:
            # 加载音频
            y, sr = librosa.load(audio_path, sr=None)
            
            # 1. 高频能量比例（清晰语音有更多高频内容）
            spec = np.abs(librosa.stft(y))
            freq_bins = spec.shape[0]
            
            # 将频谱分为低频和高频部分
            low_freq = np.sum(spec[:int(freq_bins/3), :])
            high_freq = np.sum(spec[int(freq_bins/3):, :])
            
            # 高频能量比
            high_ratio = high_freq / (low_freq + high_freq) if (low_freq + high_freq) > 0 else 0.5
            
            # 2. 零交叉率（与辅音清晰度相关）
            zero_crossings = librosa.feature.zero_crossing_rate(y)[0]
            zcr_mean = np.mean(zero_crossings)
            
            # 3. 频谱对比度（清晰语音有更高的对比度）
            contrast = np.mean(librosa.feature.spectral_contrast(y=y, sr=sr)[0])
            
            # 4. 音高变化度（自然语音有合理的音高变化）
            pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
            pitch_values = pitches[magnitudes > np.max(magnitudes)*0.1]
            pitch_std = np.std(pitch_values) / np.mean(pitch_values) if len(pitch_values) > 0 and np.mean(pitch_values) > 0 else 0
            
            # 组合特征计算清晰度
            clarity = (
                0.3 * min(1.0, high_ratio * 2)  # 高频比例贡献
                + 0.3 * min(1.0, zcr_mean * 10)  # 零交叉率贡献
                + 0.3 * min(1.0, contrast / 20)  # 频谱对比度贡献
                + 0.1 * min(1.0, pitch_std)  # 音高变化贡献
            )
            
            # 限制在0-1范围
            clarity = max(0.0, min(1.0, clarity))
            
            return float(clarity)
            
        except Exception as e:
            print(f"计算语音清晰度失败: {e}")
            return 0.5  # 出错时返回中等清晰度
    
    def evaluate_overall(self, audio_path: str, reference_path: Optional[str] = None) -> Dict:
        """
        综合评估语音质量
        
        Args:
            audio_path: 音频文件路径
            reference_path: 参考音频路径（可选）
            
        Returns:
            metrics: 包含多个指标的评估结果
        """
        # 计算各项指标
        naturalness = self.evaluate_naturalness(audio_path)
        clarity = self.evaluate_clarity(audio_path)
        
        # 如果有参考音频，计算相似度
        similarity = None
        if reference_path and os.path.exists(reference_path):
            similarity = self.evaluate_similarity(reference_path, audio_path)
        
        # 计算响应时间（假设已经记录）
        # 在实际应用中，这应该是从请求开始到生成完成的时间
        response_time = None  # 这里需要外部提供
        
        # 计算综合得分
        overall_score = (
            naturalness / 5.0 * 0.4  # 自然度贡献40%
            + clarity * 0.4          # 清晰度贡献40%
        )
        
        # 如果有相似度，加入评分
        if similarity is not None:
            overall_score = overall_score * 0.8 + similarity * 0.2  # 相似度贡献20%
        
        # 构建结果字典
        results = {
            "naturalness": float(naturalness),     # 自然度(1-5)
            "naturalness_norm": float(naturalness) / 5.0,  # 归一化自然度(0-1)
            "clarity": float(clarity),             # 清晰度(0-1)
            "overall_score": float(overall_score)  # 综合得分(0-1)
        }
        
        # 添加可选指标
        if similarity is not None:
            results["similarity"] = float(similarity)
        
        if response_time is not None:
            results["response_time"] = float(response_time)
        
        return results

# 创建评估器实例
def create_evaluator(model_path: Optional[str] = None) -> TTSMetrics:
    """
    创建TTS质量评估器实例
    
    Args:
        model_path: MOSNet模型路径（可选）
        
    Returns:
        evaluator: TTS质量评估器实例
    """
    return TTSMetrics(model_path)