import os
import torch
import numpy as np
import json
import librosa
import soundfile as sf
from pathlib import Path
from typing import Dict, Optional, Tuple, List

import os
import sys
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(ROOT_DIR)
from app.core.config import settings

# Try to import PaddleSpeech components
try:
    import paddle
    from paddlespeech.cli.tts import TTSExecutor
    from paddlespeech.cli.vector import VectorExecutor
    PADDLESPEECH_AVAILABLE = True
except ImportError:
    PADDLESPEECH_AVAILABLE = False
    print("警告: PaddleSpeech 不可用，声音克隆功能将受限。")

class VoiceCloner:
    """基于PaddleSpeech的声音克隆器"""
    
    def __init__(self):
        """初始化声音克隆器"""
        self.device = "gpu" if paddle.device.is_compiled_with_cuda() else "cpu"
        
        # 声音样本库目录
        self.voice_samples_dir = os.path.join(settings.UPLOAD_DIR, "voice_embeddings")
        os.makedirs(self.voice_samples_dir, exist_ok=True)
        
        # 声音模型目录
        self.voice_models_dir = os.path.join(settings.UPLOAD_DIR, "voice_models")
        os.makedirs(self.voice_models_dir, exist_ok=True)
        
        if not PADDLESPEECH_AVAILABLE:
            print("PaddleSpeech 不可用，将使用替代实现")
            return
        
        try:
            # 初始化声纹提取器
            self.vector_executor = VectorExecutor()
            print("声纹提取器初始化成功")
            
            # 初始化TTS执行器（可用于测试克隆效果）
            self.tts_executor = TTSExecutor()
            print("TTS执行器初始化成功")
        except Exception as e:
            print(f"初始化声音克隆器失败: {e}")
            self.vector_executor = None
            self.tts_executor = None
    
    def extract_voice_features(self, audio_path: str) -> Tuple[Optional[np.ndarray], Dict]:
        """
        提取声音特征
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            embedding: 声音嵌入向量
            features: 详细特征信息
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")
            
        # 使用PaddleSpeech提取声纹
        if PADDLESPEECH_AVAILABLE and self.vector_executor:
            try:
                # 提取声纹
                spk_embedding = self.vector_executor(
                    audio_file=audio_path,
                    model='ecapa_tdnn',  # 声纹提取模型
                    device=self.device,
                )
                
                # 创建特征字典
                features = {
                    "embedding_type": "paddlespeech_vector",
                    "embedding_dim": spk_embedding.shape[0] if isinstance(spk_embedding, np.ndarray) else 0,
                    "embedding": spk_embedding.tolist() if isinstance(spk_embedding, np.ndarray) else None,
                    "model": "ecapa_tdnn"
                }
                
                return spk_embedding, features
                
            except Exception as e:
                print(f"PaddleSpeech声纹提取失败: {e}")
                
        # 使用备选方法提取声音特征
        return self._extract_traditional_features(audio_path)
    
    def _extract_traditional_features(self, audio_path: str) -> Tuple[np.ndarray, Dict]:
        """使用传统方法提取声音特征"""
        try:
            # 加载音频
            y, sr = librosa.load(audio_path, sr=16000)
            
            # 基本特征
            duration = librosa.get_duration(y=y, sr=sr)
            
            # 音高分析
            pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
            pitch_values = pitches[magnitudes > 0.1]
            pitch_mean = np.mean(pitch_values) if len(pitch_values) > 0 else 0
            pitch_std = np.std(pitch_values) if len(pitch_values) > 0 else 0
            
            # 能量特征
            rms = librosa.feature.rms(y=y)[0]
            energy_mean = np.mean(rms)
            energy_std = np.std(rms)
            
            # 频谱特征
            mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)
            mfcc_means = np.mean(mfccs, axis=1)
            mfcc_stds = np.std(mfccs, axis=1)
            
            # 声音特征
            spectral_centroid = np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)[0])
            spectral_bandwidth = np.mean(librosa.feature.spectral_bandwidth(y=y, sr=sr)[0])
            spectral_contrast = np.mean(librosa.feature.spectral_contrast(y=y, sr=sr)[0])
            
            # 创建特征字典
            features = {
                "embedding_type": "traditional",
                "duration": float(duration),
                "pitch_mean": float(pitch_mean),
                "pitch_std": float(pitch_std),
                "energy_mean": float(energy_mean),
                "energy_std": float(energy_std),
                "spectral_centroid": float(spectral_centroid),
                "spectral_bandwidth": float(spectral_bandwidth),
                "spectral_contrast": float(spectral_contrast),
                "mfcc_means": mfcc_means.tolist(),
                "mfcc_stds": mfcc_stds.tolist()
            }
            
            # 合并特征为嵌入向量
            embedding = np.concatenate([
                [pitch_mean, pitch_std, energy_mean, energy_std, 
                 spectral_centroid, spectral_bandwidth, spectral_contrast], 
                mfcc_means
            ])
            
            return embedding, features
            
        except Exception as e:
            print(f"传统特征提取失败: {e}")
            # 返回空特征
            return np.array([]), {"embedding_type": "empty", "error": str(e)}
    
    def process_voice_sample(self, audio_path: str, sample_id: str) -> Dict:
        """
        处理声音样本，提取特征并创建声音模型
        
        Args:
            audio_path: 音频文件路径
            sample_id: 样本ID
            
        Returns:
            features: 提取的特征信息
        """
        # 提取声音特征
        embedding, features = self.extract_voice_features(audio_path)
        
        # 保存特征文件
        features_path = os.path.join(self.voice_samples_dir, f"{sample_id}_features.json")
        with open(features_path, 'w') as f:
            json.dump(features, f, indent=2)
        
        # 为声音克隆创建优化的音频模型
        model_path = os.path.join(self.voice_models_dir, f"{sample_id}.wav")
        
        try:
            # 加载和处理音频
            y, sr = librosa.load(audio_path, sr=None)
            
            # 归一化
            y = librosa.util.normalize(y)
            
            # 裁剪静音部分
            y, _ = librosa.effects.trim(y, top_db=20)
            
            # 保存处理后的音频作为声音模型
            sf.write(model_path, y, sr)
            
        except Exception as e:
            print(f"创建声音模型失败: {e}")
        
        # 更新特征信息
        features["model_path"] = model_path
        
        return features
    
    def load_voice_embedding(self, sample_id: str) -> Optional[np.ndarray]:
        """
        加载声音嵌入向量
        
        Args:
            sample_id: 样本ID
            
        Returns:
            embedding: 声音嵌入向量，如果不存在则返回None
        """
        features_path = os.path.join(self.voice_samples_dir, f"{sample_id}_features.json")
        
        if not os.path.exists(features_path):
            print(f"声音特征文件不存在: {features_path}")
            return None
        
        try:
            with open(features_path, 'r') as f:
                features = json.load(f)
            
            # 根据特征类型加载嵌入向量
            if features.get("embedding_type") == "paddlespeech_vector" and "embedding" in features:
                return np.array(features["embedding"])
            
            elif features.get("embedding_type") == "traditional":
                # 重建传统特征嵌入向量
                pitch_mean = features.get("pitch_mean", 0.0)
                pitch_std = features.get("pitch_std", 0.0)
                energy_mean = features.get("energy_mean", 0.0)
                energy_std = features.get("energy_std", 0.0)
                spectral_centroid = features.get("spectral_centroid", 0.0)
                spectral_bandwidth = features.get("spectral_bandwidth", 0.0)
                spectral_contrast = features.get("spectral_contrast", 0.0)
                mfcc_means = np.array(features.get("mfcc_means", [0] * 20))
                
                embedding = np.concatenate([
                    [pitch_mean, pitch_std, energy_mean, energy_std, 
                     spectral_centroid, spectral_bandwidth, spectral_contrast], 
                    mfcc_means
                ])
                
                return embedding
            
            # 尝试加载mfcc_fingerprint（兼容现有格式）
            elif "mfcc_fingerprint" in features:
                return np.array(features["mfcc_fingerprint"])
                
            else:
                print(f"不支持的特征格式: {features_path}")
                return None
            
        except Exception as e:
            print(f"加载声音特征失败: {e}")
            return None
    
    def get_voice_model_path(self, sample_id: str) -> Optional[str]:
        """
        获取声音模型路径
        
        Args:
            sample_id: 样本ID
            
        Returns:
            model_path: 声音模型路径，如果不存在则返回None
        """
        # 首先尝试从特征文件获取
        features_path = os.path.join(self.voice_samples_dir, f"{sample_id}_features.json")
        if os.path.exists(features_path):
            try:
                with open(features_path, 'r') as f:
                    features = json.load(f)
                
                if "model_path" in features and os.path.exists(features["model_path"]):
                    return features["model_path"]
            except Exception:
                pass
        
        # 然后尝试标准位置
        model_path = os.path.join(self.voice_models_dir, f"{sample_id}.wav")
        if os.path.exists(model_path):
            return model_path
        
        return None
    
    def find_similar_voices(self, embedding: np.ndarray, top_n: int = 3) -> List[Dict]:
        """
        查找与给定嵌入向量最相似的声音样本
        
        Args:
            embedding: 声音嵌入向量
            top_n: 返回的最相似样本数量
            
        Returns:
            similar_voices: 相似声音列表，包含样本ID和相似度
        """
        similarities = []
        
        # 遍历所有声音样本
        for file_path in Path(self.voice_samples_dir).glob("*_features.json"):
            sample_id = file_path.stem.split('_')[0]
            
            # 加载样本嵌入向量
            sample_embedding = self.load_voice_embedding(sample_id)
            
            if sample_embedding is not None:
                # 确保维度匹配
                min_dim = min(len(embedding), len(sample_embedding))
                emb1 = embedding[:min_dim]
                emb2 = sample_embedding[:min_dim]
                
                # 计算余弦相似度
                dot_product = np.dot(emb1, emb2)
                norm1 = np.linalg.norm(emb1)
                norm2 = np.linalg.norm(emb2)
                
                if norm1 > 0 and norm2 > 0:
                    similarity = dot_product / (norm1 * norm2)
                    # 转换到0-1范围
                    similarity = (similarity + 1) / 2
                    
                    similarities.append({
                        "sample_id": sample_id,
                        "similarity": float(similarity)
                    })
        
        # 按相似度排序并返回top_n个
        similarities.sort(key=lambda x: x["similarity"], reverse=True)
        return similarities[:top_n]
    
    def adapt_tts_params(self, embedding: np.ndarray, base_params: Dict) -> Dict:
        """
        基于声音嵌入向量调整TTS参数
        
        Args:
            embedding: 声音嵌入向量
            base_params: 基础TTS参数
            
        Returns:
            adapted_params: 调整后的TTS参数
        """
        # 复制基础参数
        params = base_params.copy()
        
        # 如果是PaddleSpeech声纹特征，添加声纹嵌入
        if len(embedding) > 50:  # 简单判断是否为神经特征
            params["speaker_embedding"] = embedding.tolist()
            return params
        
        # 对于传统特征，提取有用信息调整参数
        try:
            # 假设前7个元素包含基本声学特征
            pitch_mean = embedding[0]
            pitch_std = embedding[1]
            energy_mean = embedding[2]
            energy_std = embedding[3]
            
            # 根据音高特征调整pitch
            # 将平均音高映射到-1到1的范围
            base_pitch = params.get("pitch", 0.0)
            if 100 < pitch_mean < 300:  # 正常人声范围
                # 女声通常高于220Hz，男声通常在100-170Hz
                gender_pitch_adj = (pitch_mean - 170) / 100  # 映射到大约-0.7到1.3
                params["pitch"] = base_pitch + gender_pitch_adj * 0.3  # 适度调整
            
            # 根据能量特征调整energy
            base_energy = params.get("energy", 1.0)
            if energy_mean > 0:
                energy_adj = (energy_mean - 0.1) / 0.2  # 假设正常范围为0.1-0.3
                params["energy"] = base_energy * max(0.8, min(1.2, 1 + energy_adj * 0.2))
            
            # 限制在合理范围内
            params["pitch"] = max(-1.0, min(1.0, params.get("pitch", 0.0)))
            params["energy"] = max(0.5, min(2.0, params.get("energy", 1.0)))
            
        except Exception as e:
            print(f"调整TTS参数失败: {e}")
            # 出错时使用原参数
        
        return params
    
    def test_voice_clone(self, sample_id: str, text: str = "这是一段测试声音克隆效果的示例文本。") -> Optional[str]:
        """
        测试声音克隆效果
        
        Args:
            sample_id: 样本ID
            text: 测试文本
            
        Returns:
            output_path: 输出文件路径，如果失败则为None
        """
        if not PADDLESPEECH_AVAILABLE or self.tts_executor is None:
            print("PaddleSpeech不可用，无法测试声音克隆")
            return None
        
        try:
            # 获取声音模型
            model_path = self.get_voice_model_path(sample_id)
            if not model_path:
                print(f"声音模型不存在: {sample_id}")
                return None
            
            # 加载声音嵌入向量
            embedding = self.load_voice_embedding(sample_id)
            
            # 创建输出目录
            output_dir = os.path.join(settings.UPLOAD_DIR, "voice_clone_tests")
            os.makedirs(output_dir, exist_ok=True)
            
            # 输出文件路径
            output_path = os.path.join(output_dir, f"clone_test_{sample_id}.wav")
            
            # 执行TTS测试
            # 注意：根据PaddleSpeech版本不同，可能需要调整以下代码
            result = self.tts_executor(
                text=text,
                output=output_path,
                am="fastspeech2_mix",  # 混合模型更适合声音克隆
                voc="pwgan_csmsc",     # 声码器
                lang="zh",
                spk_id=0
            )
            
            return output_path
            
        except Exception as e:
            print(f"测试声音克隆失败: {e}")
            return None

# 创建单例
voice_cloner = VoiceCloner()