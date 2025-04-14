import os
import torch
import numpy as np
import json
import librosa
from pathlib import Path
from typing import Dict, Optional, Tuple, List
from app.core.config import settings

class VoiceEncoder:
    """声音编码器类，用于提取声音特征和声纹"""
    
    def __init__(self, model_path: Optional[str] = None):
        """
        初始化声音编码器
        
        Args:
            model_path: 预训练的声音编码器模型路径
        """
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # 使用预训练模型路径或使用默认位置
        if model_path is None:
            model_path = os.path.join(settings.MODELS_DIR, "voice_encoder", "encoder.pt")
        
        # 检查模型文件是否存在
        self.model = None
        if os.path.exists(model_path):
            try:
                self.model = torch.jit.load(model_path)
                self.model.to(self.device)
                self.model.eval()
                print(f"声音编码器模型加载成功: {model_path}")
            except Exception as e:
                print(f"加载声音编码器模型失败: {e}")
        else:
            print(f"声音编码器模型不存在: {model_path}")
            print("将使用替代方法提取声音特征")
    
    def extract_features(self, audio_path: str) -> Tuple[np.ndarray, Dict]:
        """
        从音频文件中提取声音特征
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            embedding: 声音嵌入向量
            features: 详细特征信息
        """
        # 确保文件存在
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")
        
        # 加载音频
        y, sr = librosa.load(audio_path, sr=None)
        
        # 如果有声音编码器模型，使用模型提取声纹
        if self.model is not None:
            try:
                return self._extract_with_model(y, sr)
            except Exception as e:
                print(f"使用模型提取特征失败: {e}")
                print("使用传统方法提取特征")
        
        # 使用传统方法提取特征
        return self._extract_traditional(y, sr)
    
    def _extract_with_model(self, y: np.ndarray, sr: int) -> Tuple[np.ndarray, Dict]:
        """使用神经网络模型提取声音嵌入向量"""
        # 重采样到模型需要的采样率（如16kHz）
        if sr != 16000:
            y = librosa.resample(y, orig_sr=sr, target_sr=16000)
            sr = 16000
        
        # 预处理：标准化音频
        y = librosa.util.normalize(y) * 0.95
        
        # 转换为张量
        audio_tensor = torch.FloatTensor(y).unsqueeze(0).to(self.device)
        
        # 使用模型提取特征
        with torch.no_grad():
            embedding = self.model(audio_tensor).cpu().numpy()[0]
        
        # 创建特征字典
        features = {
            "embedding_type": "neural",
            "embedding_dim": embedding.shape[0],
            "embedding": embedding.tolist()
        }
        
        return embedding, features
    
    def _extract_traditional(self, y: np.ndarray, sr: int) -> Tuple[np.ndarray, Dict]:
        """使用传统声学特征提取方法"""
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

class VoiceCloner:
    """声音克隆器，用于将源声音特征应用到TTS系统"""
    
    def __init__(self, encoder: Optional[VoiceEncoder] = None):
        """
        初始化声音克隆器
        
        Args:
            encoder: 声音编码器实例
        """
        self.encoder = encoder if encoder is not None else VoiceEncoder()
        
        # 声音样本库目录
        self.voice_samples_dir = os.path.join(settings.UPLOAD_DIR, "voice_embeddings")
        os.makedirs(self.voice_samples_dir, exist_ok=True)
    
    def process_voice_sample(self, audio_path: str, sample_id: str) -> Dict:
        """
        处理声音样本，提取声音特征并保存
        
        Args:
            audio_path: 音频文件路径
            sample_id: 样本ID
            
        Returns:
            features: 提取的特征信息
        """
        # 提取声音特征
        _, features = self.encoder.extract_features(audio_path)
        
        # 保存特征文件
        features_path = os.path.join(self.voice_samples_dir, f"{sample_id}_features.json")
        with open(features_path, 'w') as f:
            json.dump(features, f, indent=2)
        
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
            if features.get("embedding_type") == "neural" and "embedding" in features:
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
        
        # 如果是神经网络提取的嵌入向量，直接使用
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
            params["pitch"] = max(-1.0, min(1.0, params["pitch"]))
            params["energy"] = max(0.5, min(2.0, params["energy"]))
            
        except Exception as e:
            print(f"调整TTS参数失败: {e}")
            # 出错时使用原参数
        
        return params

# 创建单例
voice_encoder = VoiceEncoder()
voice_cloner = VoiceCloner(encoder=voice_encoder)