// 修复完成后的SimplifiedTTS.jsx
import React, { useState, useEffect, useRef } from 'react';
import { 
  Button, 
  Space, 
  message, 
  Progress, 
  Card, 
  Select, 
  Slider,
  Typography,
  Row,
  Col,
  Input,
  Form,
  Switch
} from 'antd';
import { 
  PlayCircleOutlined, 
  PauseCircleOutlined, 
  DownloadOutlined,
  SoundOutlined,
  StepBackwardOutlined,
  StepForwardOutlined,
  ReloadOutlined,
  StopOutlined
} from '@ant-design/icons';
import axios from 'axios';

const { Option, OptGroup } = Select;
const { Title, Text } = Typography;

/**
 * Simplified TTS Component
 * 
 * A unified interface for text-to-speech synthesis that automatically
 * selects the appropriate synthesis method based on the voice type.
 */
const SimplifiedTTS = ({ 
  text, 
  onComplete 
}) => {
  // State
  const [voiceId, setVoiceId] = useState('');
  const [voices, setVoices] = useState([]);
  const [loading, setLoading] = useState(false);
  const [speed, setSpeed] = useState(1.0);
  const [seed, setSeed] = useState(Math.floor(Math.random() * 1000000));
  const [audioUrl, setAudioUrl] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [taskId, setTaskId] = useState(null);
  const [taskStatus, setTaskStatus] = useState(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [statusFailCount, setStatusFailCount] = useState(0);
  // Playback state
  const [playbackProgress, setPlaybackProgress] = useState(0);
  const [audioDuration, setAudioDuration] = useState(0);
  const [playbackSliderValue, setPlaybackSliderValue] = useState(0);
  const [sliderChanging, setSliderChanging] = useState(false);
  
  // References
  const audioRef = useRef(null);
  const statusIntervalRef = useRef(null);
  const websocketRef = useRef(null);
  const audioContextRef = useRef(null);
  const audioBuffersRef = useRef([]);
  const audioSourceRef = useRef(null);
  const audioBufferRef = useRef(null);
  const playbackTimerRef = useRef(null);
  const taskCompletedRef = useRef(false);
  const successMessageShownRef = useRef(false); // 跟踪成功消息是否已显示
  const streamCompletedRef = useRef(false); // 新增：跟踪流式合成是否已完成
  
  // Format time helper
  const formatTime = (time) => {
    if (!time || isNaN(time)) return '0:00';
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };
  
  // Load voices on mount
  useEffect(() => {
    fetchVoices();
    
    // 初始化 AudioContext
    if (typeof window !== 'undefined') {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (AudioContext && !audioContextRef.current) {
        audioContextRef.current = new AudioContext();
      }
    }

    // 清理函数
    return () => {
      cleanupResources();
      
      // 清理临时Blob URL
      if (audioUrl && audioUrl.startsWith('blob:')) {
        URL.revokeObjectURL(audioUrl);
      }
    };
  }, []);
  
  // 清理资源函数
  const cleanupResources = () => {
    if (statusIntervalRef.current) {
      clearInterval(statusIntervalRef.current);
      statusIntervalRef.current = null;
    }
    
    if (websocketRef.current) {
      websocketRef.current.close();
      websocketRef.current = null;
    }
    
    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
    
    if (playbackTimerRef.current) {
      clearInterval(playbackTimerRef.current);
      playbackTimerRef.current = null;
    }
  };
  
  // Monitor task status
  useEffect(() => {
    // 重置完成状态
    taskCompletedRef.current = false;
    successMessageShownRef.current = false; // 重置成功消息标志
    streamCompletedRef.current = false; // 重置流式合成完成标志
    
    if (taskId) {
      if (statusIntervalRef.current) {
        clearInterval(statusIntervalRef.current);
      }
      
      statusIntervalRef.current = setInterval(() => {
        // 只在任务未完成时检查状态
        if (!taskCompletedRef.current) {
          checkTaskStatus(taskId);
        }
      }, 1000);
      
      return () => {
        if (statusIntervalRef.current) {
          clearInterval(statusIntervalRef.current);
          statusIntervalRef.current = null;
        }
      };
    }
  }, [taskId]);
  
  // Monitor audio playback
  useEffect(() => {
    if (audioRef.current) {
      const audio = audioRef.current;
      
      const handleTimeUpdate = () => {
        if (!sliderChanging) {
          setPlaybackProgress(audio.currentTime);
          if (audioDuration > 0) {
            setPlaybackSliderValue((audio.currentTime / audioDuration) * 100);
          }
        }
      };
      
      const handleLoadedMetadata = () => {
        if (audio.duration && !isNaN(audio.duration)) {
          setAudioDuration(audio.duration);
        }
      };
      
      audio.addEventListener('timeupdate', handleTimeUpdate);
      audio.addEventListener('loadedmetadata', handleLoadedMetadata);
      
      return () => {
        audio.removeEventListener('timeupdate', handleTimeUpdate);
        audio.removeEventListener('loadedmetadata', handleLoadedMetadata);
      };
    }
  }, [audioRef.current, sliderChanging, audioDuration]);
  
  // 监听 audioUrl 变化，当 URL 变化且流式合成完成时强制切换到标准播放
  useEffect(() => {
    if (audioUrl && streamCompletedRef.current) {
      console.log('检测到完整音频 URL 已设置且流式合成已完成，切换到标准播放');
      
      // 停止流式播放，如果正在进行
      if (audioSourceRef.current) {
        try {
          audioSourceRef.current.stop();
          audioSourceRef.current = null;
        } catch (e) {
          // 忽略已停止的错误
        }
      }
      
      // 确保音频元素预加载
      if (audioRef.current) {
        audioRef.current.load();
      }
    }
  }, [audioUrl]);
  
  // Fetch available voices
  const fetchVoices = async () => {
    try {
      const response = await axios.get('/api/voice/list');
      if (response.data && response.data.items) {
        setVoices(response.data.items);
        
        // Select first voice by default
        if (response.data.items.length > 0) {
          setVoiceId(response.data.items[0].id);
        }
      } else {
        console.warn('获取声音列表返回不完整数据:', response.data);
        message.warning('获取声音列表返回不完整数据');
      }
    } catch (error) {
      console.error('获取声音列表失败:', error);
      message.error('获取声音列表失败，请稍后重试');
    }
  };
  
  // Generate random seed
  const generateRandomSeed = () => {
    const newSeed = Math.floor(Math.random() * 1000000);
    setSeed(newSeed);
  };
  
  // 声音选择处理函数
  const handleVoiceChange = (selectedVoiceId) => {
    // 设置所选声音
    setVoiceId(selectedVoiceId);
    
    // 根据声音类型自动设置合成模式
    const selectedVoice = voices.find(v => v.id === selectedVoiceId);
    if (selectedVoice) {
      console.log(`已选择声音: ${selectedVoice.name}, 类型: ${selectedVoice.type}`);
      
      // 清除之前的音频状态
      resetAudioState();
    }
  };

  // 重置音频状态
  const resetAudioState = () => {
    setAudioUrl(null);
    setTaskId(null);
    setTaskStatus(null);
    setProgress(0);
    setPlaybackProgress(0);
    setPlaybackSliderValue(0);
    setAudioDuration(0);
    taskCompletedRef.current = false;
    successMessageShownRef.current = false; // 重置成功消息标志
    streamCompletedRef.current = false; // 重置流式合成完成标志
    
    // 停止当前播放
    if (audioRef.current) {
      try {
        audioRef.current.pause();
      } catch (e) {
        console.error('停止音频播放时出错:', e);
      }
    }
    
    if (audioSourceRef.current) {
      try {
        audioSourceRef.current.stop();
      } catch (e) {
        // 忽略已停止的错误
      }
      audioSourceRef.current = null;
    }
  };

  // Show success message once
  const showSuccessMessageOnce = (message) => {
    if (!successMessageShownRef.current) {
      window.message.success(message);
      successMessageShownRef.current = true;
    }
  };

  // 标准合成函数 - 简化版本
  const handleStandardSynthesis = async () => {
    // 验证输入
    if (!text) {
      message.warning('请输入要合成的文本');
      return;
    }
    
    if (!voiceId) {
      message.warning('请选择声音');
      return;
    }
    
    // 重置状态
    resetAudioState();

    // 清理audioUrl（如果是blob URL）
    if (audioUrl && audioUrl.startsWith('blob:')) {
      URL.revokeObjectURL(audioUrl);
      setAudioUrl(null);
    }

    setLoading(true);
    setStatusFailCount(0);
    
    try {
      // 准备请求
      const params = {
        speed: speed,
        seed: seed
      };
      // 显示加载消息
      message.loading('正在提交合成请求...', 1);
      
      // 发送合成请求
      const response = await axios.post('/api/tts/synthesize', {
        text: text,
        voice_id: voiceId,
        params: params
      });
      
      // 处理响应
      if (response?.data?.task_id) {
        const newTaskId = response.data.task_id;
        setTaskId(newTaskId);
        message.success('合成任务已提交，请稍候');
        
        // taskId已更新，useEffect会处理状态检查的间隔设置
      } else {
        throw new Error('无效的任务ID');
      }
      
    } catch (error) {
      console.error('合成请求失败:', error);
      message.error('语音合成请求失败: ' + (error.response?.data?.detail || error.message));
      setLoading(false);
    }
  };

  // 流式合成WebSocket处理
  const handleStreamingSynthesis = async () => {
    // 验证输入
    if (!text) {
      message.warning('请输入要合成的文本');
      return;
    }
    
    if (!voiceId) {
      message.warning('请选择声音');
      return;
    }
    
    // 重置状态
    resetAudioState();
  
    // 清理audioUrl（如果是blob URL）
    if (audioUrl && audioUrl.startsWith('blob:')) {
      URL.revokeObjectURL(audioUrl);
      setAudioUrl(null);
    }
  
    setLoading(true);
    setStatusFailCount(0);
    setProgress(0);
    
    // 清除之前的音频缓冲
    audioBuffersRef.current = [];
    audioBufferRef.current = null;
    audioSourceRef.current = null;
    
    // 设置WebSocket连接
    try {
      // 关闭现有连接
      if (websocketRef.current) {
        websocketRef.current.close();
        websocketRef.current = null;
      }
      
      // 使用正确的WebSocket URL
      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const baseUrl = window.location.host;
      
      // 根据当前环境构建WebSocket URL
      const wsUrl = `${protocol}://localhost:8000/api/tts/synthesize/stream`;
      console.log(`尝试连接WebSocket: ${wsUrl}`);
      
      message.loading('正在连接到服务器...', 1);
      
      // 创建WebSocket连接
      websocketRef.current = new WebSocket(wsUrl);
      
      // 当连接打开时，发送参数
      websocketRef.current.onopen = () => {
        console.log('WebSocket连接已建立');
        
        const requestData = {
          text: text,
          voice_id: voiceId,
          params: {
            speed: speed,
            seed: seed
          }
        };
        
        console.log('发送合成请求:', requestData);
        if (websocketRef.current && websocketRef.current.readyState === WebSocket.OPEN) {
          websocketRef.current.send(JSON.stringify(requestData));
          message.info('开始流式合成');
        } else {
          message.error('WebSocket连接已关闭，无法发送请求');
          setLoading(false);
        }
      };
      
      // 处理收到的消息
      websocketRef.current.onmessage = async (event) => {
        await handleWebSocketMessage(event);
      };
      
      // 处理错误
      websocketRef.current.onerror = (error) => {
        console.error('WebSocket错误:', error);
        setLoading(false);
        message.error('WebSocket连接失败，请重试');
      };
      
      // 处理连接关闭
      websocketRef.current.onclose = (event) => {
        console.log('WebSocket连接已关闭', event.code, event.reason);
        setLoading(false);
        
        if (event.code !== 1000 && event.code !== 1005) {
          message.error(`连接已关闭: ${event.reason || '未知原因'} (错误码: ${event.code})`);
        } else if (audioBuffersRef.current && audioBuffersRef.current.length === 0) {
          // 如果连接正常关闭但没有收到任何音频数据
          message.warning('未收到任何音频数据，请尝试再次合成');
        }
      };
      
      // 设置连接超时
      setTimeout(() => {
        if (websocketRef.current && websocketRef.current.readyState === WebSocket.CONNECTING) {
          message.error('连接超时，请重试');
          setLoading(false);
          
          if (websocketRef.current) {
            websocketRef.current.close();
            websocketRef.current = null;
          }
        }
      }, 5000);
      
    } catch (error) {
      console.error('创建WebSocket连接失败:', error);
      setLoading(false);
      message.error('无法建立连接: ' + error.message);
    }
  };
  
  // 处理WebSocket消息
// 处理WebSocket消息
const handleWebSocketMessage = async (event) => {
  try {
    // 检查是否是文本消息(JSON)
    if (typeof event.data === 'string') {
      const jsonData = JSON.parse(event.data);
      
      // 处理不同消息类型
      if (jsonData.type === 'info') {
        console.log('信息:', jsonData);
        
        if (jsonData.message) {
          message.info(jsonData.message);
        }
      }
      else if (jsonData.type === 'progress') {
        // 更新进度
        setProgress(prev => Math.min(95, prev + 5));
        
        // 保存任务ID（如果有）
        if (jsonData.task_id && !taskId) {
          console.log(`设置流式任务ID: ${jsonData.task_id}`);
          setTaskId(jsonData.task_id);
        }
        
        // 如果有时长信息，更新时长
        if (jsonData.chunk_index !== undefined && jsonData.duration) {
          setAudioDuration(prev => Math.max(prev, (jsonData.chunk_index + 1) * jsonData.duration));
        }
      }
      else if (jsonData.type === 'complete') {
        // 合成完成
        console.log('收到流式合成完成消息:', jsonData);
        setProgress(100);
        setLoading(false);
        
        // 设置流式合成完成标志
        streamCompletedRef.current = true;
        
        // 保存任务ID
        if (jsonData.task_id) {
          console.log(`设置完成的任务ID: ${jsonData.task_id}`);
          setTaskId(jsonData.task_id);
          
          // 设置完整音频URL
          const completeAudioUrl = `/api/tts/preview_audio/${jsonData.task_id}`;
          console.log(`设置完整音频URL: ${completeAudioUrl}`);
          setAudioUrl(completeAudioUrl);
          
          // 预加载音频
          if (audioRef.current) {
            audioRef.current.load();
          }
        }
        
        // 设置音频时长
        if (jsonData.duration !== undefined && jsonData.duration !== null) {
          try {
            const duration = parseFloat(jsonData.duration);
            if (!isNaN(duration)) {
              setAudioDuration(duration);
              console.log(`设置音频时长: ${duration}秒`);
            }
          } catch (error) {
            console.error(`解析音频时长时出错: ${error}`);
          }
        }
        
        // 触发完成回调
        if (onComplete) {
          onComplete(jsonData.duration);
        }
        
        // 显示成功消息
        showSuccessMessageOnce(`合成完成，时长: ${jsonData.duration?.toFixed(1) || 0} 秒`);
      }
      // 其他消息类型处理...
    } 
    // 处理二进制音频数据...
  } catch (error) {
    console.error('处理WebSocket消息失败:', error);
  }
};
  
  // 新增：创建最终的完整音频文件
  const createFinalAudioFile = () => {
    console.log('创建最终完整音频文件...');
    
    // 如果有音频缓冲，合并它们
    if (audioBuffersRef.current && audioBuffersRef.current.length > 0) {
      try {
        console.log('开始合并流式音频数据...');
        const mergedBuffer = mergeAudioBuffers(audioBuffersRef.current);
        
        if (mergedBuffer) {
          console.log('音频数据已成功合并:', mergedBuffer);
          audioBufferRef.current = mergedBuffer;
          
          // 创建临时音频文件并设置URL
          console.log('尝试创建临时音频文件...');
          createTemporaryAudioFile();
          
          // 添加额外检查，确保URL已设置
          setTimeout(() => {
            if (!audioUrl && audioBufferRef.current && audioBufferRef.current.data) {
              console.log('检测到audioUrl未设置，尝试再次创建...');
              createTemporaryAudioFile();
            }
          }, 200);
        } else {
          console.error('合并后的缓冲区无效');
        }
      } catch (error) {
        console.error('处理流式音频数据时出错:', error);
        message.error('处理音频数据失败: ' + error.message);
      }
    } else {
      console.warn('没有音频缓冲区可合并');
    }
  };

  // 创建临时音频文件
  const createTemporaryAudioFile = () => {
    console.log('尝试创建临时音频文件...');
    
    // 增加详细的数据检查和日志
    if (!audioBufferRef.current) {
      console.warn('没有音频缓冲区引用');
      return;
    }
    
    if (!audioBufferRef.current.data) {
      console.warn('音频缓冲区没有数据属性:', audioBufferRef.current);
      return;
    }
    
    console.log('音频数据可用，长度:', audioBufferRef.current.data.length);
    console.log('采样率:', audioBufferRef.current.sampleRate);
    
    try {
      // 将流式合成的数据转换为临时音频文件
      const floatData = audioBufferRef.current.data;
      const sampleRate = audioBufferRef.current.sampleRate || 44100;
      
      // 转换为16位PCM
      const pcmData = new Int16Array(floatData.length);
      for (let i = 0; i < floatData.length; i++) {
        const s = Math.max(-1, Math.min(1, floatData[i]));
        pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }
      
      // 创建WAV头
      const wavHeader = createWavHeader(pcmData.byteLength, sampleRate);
      
      // 合并数据并创建Blob URL
      const wavBlob = new Blob([wavHeader, pcmData.buffer], { type: 'audio/wav' });
      
      // 清理之前的URL
      if (audioUrl && audioUrl.startsWith('blob:')) {
        URL.revokeObjectURL(audioUrl);
      }
      
      const tempUrl = URL.createObjectURL(wavBlob);
      
      console.log('成功创建临时音频URL:', tempUrl);
      
      // 设置为当前音频URL
      setAudioUrl(tempUrl);
      
      // 如果有audio元素，预加载音频
      if (audioRef.current) {
        console.log('加载音频到audio元素');
        audioRef.current.load();
      }
      
      // 如果流式合成已完成且正在播放，停止流式播放并切换到标准播放
      if (streamCompletedRef.current && isPlaying) {
        console.log('流式合成已完成且正在播放，切换到标准播放');
        
        // 停止当前流式播放
        if (audioSourceRef.current) {
          try {
            audioSourceRef.current.stop();
            audioSourceRef.current = null;
          } catch (e) {
            // 忽略已停止的错误
          }
        }
        
        // 短暂延迟后开始标准播放
        setTimeout(() => {
          if (audioRef.current) {
            audioRef.current.play()
              .then(() => {
                console.log('已切换到标准播放');
                setIsPlaying(true);
              })
              .catch(err => {
                console.error('切换到标准播放失败:', err);
              });
          }
        }, 100);
      }
      
      // 返回清理函数
      return () => {
        console.log('释放临时URL:', tempUrl);
        URL.revokeObjectURL(tempUrl);
      };
    } catch (error) {
      console.error('创建临时音频文件失败:', error);
      message.error('处理音频失败: ' + error.message);
      return null;
    }
  };
  
  // 播放下一个音频缓冲
  const playNextBuffer = () => {
    if (!audioBuffersRef.current || audioBuffersRef.current.length === 0) {
      console.log('没有可播放的音频缓冲区');
      return;
    }
    
    // 如果流式合成已完成且我们有完整的音频URL，使用标准播放器
    if (streamCompletedRef.current && audioUrl) {
      console.log('流式合成已完成且有完整音频URL，使用标准播放器');
      toggleStandardPlayback();
      return;
    }
    
    console.log(`开始播放音频块，剩余块数: ${audioBuffersRef.current.length}`);
    
    // 获取音频上下文
    if (!audioContextRef.current) {
      try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        audioContextRef.current = new AudioContext();
        console.log('创建了新的AudioContext');
      } catch (error) {
        console.error('创建AudioContext失败:', error);
        message.error('创建音频上下文失败，请刷新页面');
        return;
      }
    }
    
    // 确保音频上下文正在运行
    if (audioContextRef.current.state === 'suspended') {
      audioContextRef.current.resume().then(() => {
        console.log('AudioContext恢复成功');
      }).catch(err => {
        console.error('恢复AudioContext失败:', err);
      });
    }
    
    try {
      // 创建音频源
      const source = audioContextRef.current.createBufferSource();
      source.buffer = audioBuffersRef.current[0];
      source.connect(audioContextRef.current.destination);
      
      // 存储源引用和开始时间
      audioSourceRef.current = source;
      audioSourceRef.current.startTime = audioContextRef.current.currentTime;
      audioSourceRef.current.bufferDuration = source.buffer.duration || 0;
      
      console.log(`开始播放音频块，时长: ${source.buffer.duration}秒`);
      
      // 设置结束回调
      source.onended = () => {
        console.log('当前音频块播放完毕');
        
        // 标记当前源为null，表示已经播放完毕
        audioSourceRef.current = null;
        
        // 更新播放进度
        if (audioDuration > 0) {
          const buffer = audioBuffersRef.current[0];
          const bufferDuration = buffer ? (buffer.duration || 0) : 0;
          const newProgress = playbackProgress + bufferDuration;
          
          setPlaybackProgress(newProgress);
          setPlaybackSliderValue((newProgress / audioDuration) * 100);
          console.log(`已播放时长更新为: ${newProgress}秒`);
        }
        
        // 移除已播放的缓冲
        if (audioBuffersRef.current && audioBuffersRef.current.length > 0) {
          audioBuffersRef.current.shift();
          console.log(`移除已播放的缓冲区，剩余: ${audioBuffersRef.current.length}个`);
        }
        
        // 如果流式合成已完成且我们有完整的音频URL，切换到标准播放
        if (streamCompletedRef.current && audioUrl) {
          console.log('检测到流式合成已完成且有完整音频URL，切换到标准播放');
          
          if (isPlaying) {
            setTimeout(() => {
              toggleStandardPlayback();
            }, 100);
          }
          
          return;
        }
        
        // 如果有更多缓冲，播放下一个
        if (audioBuffersRef.current && audioBuffersRef.current.length > 0) {
          console.log('有更多音频块，继续播放');
          playNextBuffer();
        } else if (websocketRef.current && websocketRef.current.readyState === WebSocket.OPEN) {
          // WebSocket仍然打开，可能还会有更多数据
          console.log('已播放所有可用音频块，等待更多数据...');
        } else {
          // 没有更多缓冲，并且WebSocket已关闭
          console.log('播放完毕，没有更多音频数据');
          setIsPlaying(false);
          
          if (playbackTimerRef.current) {
            clearInterval(playbackTimerRef.current);
            playbackTimerRef.current = null;
          }
        }
      };
      
      // 开始播放
      source.start(0);
      setIsPlaying(true);
      
      // 更新播放进度
      if (playbackTimerRef.current) {
        clearInterval(playbackTimerRef.current);
        playbackTimerRef.current = null;
      }
      
      playbackTimerRef.current = setInterval(() => {
        if (isPlaying && audioContextRef.current && audioSourceRef.current) {
          const elapsedTime = audioContextRef.current.currentTime - (audioSourceRef.current.startTime || 0);
          const currentTime = playbackProgress + elapsedTime;
          
          if (!sliderChanging && audioDuration > 0) {
            setPlaybackSliderValue((currentTime / audioDuration) * 100);
            setPlaybackProgress(currentTime);
          }
        }
      }, 100);
    } catch (error) {
      console.error('播放音频缓冲失败:', error);
      message.error('播放失败，请重试');
      setIsPlaying(false);
    }
  };
  
  // 切换流式播放
  const toggleStreamingPlayback = () => {
    try {
      // 如果流式合成已完成且我们有完整的音频URL，使用标准播放器
      if (streamCompletedRef.current && audioUrl) {
        console.log('流式合成已完成且有完整音频URL，切换到标准播放');
        toggleStandardPlayback();
        return;
      }
      
      // 初始化音频上下文（如果需要）
      if (!audioContextRef.current) {
        try {
          const AudioContext = window.AudioContext || window.webkitAudioContext;
          audioContextRef.current = new AudioContext();
        } catch (error) {
          console.error('创建AudioContext失败:', error);
          message.error('创建音频上下文失败，请刷新页面');
          return;
        }
      }
      
      // 如果正在播放，暂停
      if (isPlaying) {
        console.log('尝试暂停播放');
        
        if (audioContextRef.current.state === 'running') {
          audioContextRef.current.suspend().then(() => {
            console.log('AudioContext已暂停');
          }).catch(err => {
            console.error('暂停AudioContext失败:', err);
          });
        }
        
        if (audioSourceRef.current) {
          try {
            // 某些浏览器可能不支持暂停，尝试保存当前播放位置
            console.log('记录当前播放位置');
            // 保存当前播放位置
            const currentElapsedTime = audioContextRef.current.currentTime - (audioSourceRef.current.startTime || 0);
            const currentBufferPosition = currentElapsedTime;
            audioSourceRef.current.pausePosition = currentBufferPosition;
            
            // 停止当前源
            audioSourceRef.current.stop();
            audioSourceRef.current = null;
          } catch (e) {
            console.error('停止音频源失败:', e);
          }
        }
        
        if (playbackTimerRef.current) {
          clearInterval(playbackTimerRef.current);
          playbackTimerRef.current = null;
        }
        
        setIsPlaying(false);
        return;
      }
      
      // 如果已暂停，恢复
      console.log('尝试恢复播放');
      
      if (audioContextRef.current.state === 'suspended') {
        audioContextRef.current.resume().then(() => {
          console.log('AudioContext已恢复');
        }).catch(err => {
          console.error('恢复AudioContext失败:', err);
        });
      }
      
      // 如果我们有音频缓冲区，从当前位置播放
      if (audioBufferRef.current && audioBufferRef.current.data) {
        console.log('使用合并的缓冲区从当前位置恢复播放');
        
        try {
          const sampleRate = audioBufferRef.current.sampleRate || 44100;
          const startSample = Math.floor(playbackProgress * sampleRate);
          
          if (startSample < audioBufferRef.current.data.length) {
            // 从当前位置创建缓冲区
            const remainingData = audioBufferRef.current.data.slice(startSample);
            
            // 创建AudioBuffer
            const newBuffer = audioContextRef.current.createBuffer(1, remainingData.length, sampleRate);
            newBuffer.copyToChannel(remainingData, 0);
            
            // 创建源
            const source = audioContextRef.current.createBufferSource();
            source.buffer = newBuffer;
            source.connect(audioContextRef.current.destination);
            
            // 存储引用
            audioSourceRef.current = source;
            audioSourceRef.current.startTime = audioContextRef.current.currentTime;
            
            // 设置结束回调
            source.onended = () => {
              console.log('恢复的音频播放完毕');
              audioSourceRef.current = null;
              setIsPlaying(false);
              
              if (playbackTimerRef.current) {
                clearInterval(playbackTimerRef.current);
                playbackTimerRef.current = null;
              }
            };
            
            // 开始播放
            source.start(0);
            setIsPlaying(true);
            
            // 更新进度
            if (playbackTimerRef.current) {
              clearInterval(playbackTimerRef.current);
              playbackTimerRef.current = null;
            }
            
            playbackTimerRef.current = setInterval(() => {
              if (isPlaying && audioContextRef.current && audioSourceRef.current) {
                const elapsedTime = audioContextRef.current.currentTime - (audioSourceRef.current.startTime || 0);
                const currentTime = playbackProgress + elapsedTime;
                
                if (!sliderChanging && audioDuration > 0) {
                  setPlaybackSliderValue((currentTime / audioDuration) * 100);
                  setPlaybackProgress(currentTime);
                }
              }
            }, 100);
            
            return;
          }
        } catch (error) {
          console.error('从当前位置恢复播放失败:', error);
        }
      }
      
      // 如果有缓冲但没有当前源，开始播放它们
      if (audioBuffersRef.current && audioBuffersRef.current.length > 0) {
        console.log('使用现有缓冲区开始播放');
        playNextBuffer();
        return;
      }
      
      // 没有音频可播放
      console.log('没有可播放的音频');
      message.info('没有可播放的音频');
      
    } catch (error) {
      console.error('播放控制失败:', error);
      message.error('播放控制失败: ' + error.message);
    }
  };
  
  // 切换标准播放
  const toggleStandardPlayback = () => {
    if (!audioRef.current || !audioUrl) {
      message.info('无可播放的音频');
      return;
    }
    
    try {
      if (isPlaying) {
        audioRef.current.pause();
        setIsPlaying(false);
      } else {
        // 确保音频元素已加载
        if (audioRef.current.readyState === 0) {
          audioRef.current.load();
          audioRef.current.oncanplaythrough = () => {
            audioRef.current.play()
              .then(() => setIsPlaying(true))
              .catch(error => {
                console.error('播放音频失败:', error);
                message.error('音频播放失败: ' + error.message);
              });
          };
        } else {
          audioRef.current.play()
            .then(() => setIsPlaying(true))
            .catch(error => {
              console.error('播放音频失败:', error);
              message.error('音频播放失败: ' + error.message);
            });
        }
      }
    } catch (error) {
      console.error('切换播放失败:', error);
      message.error('播放控制失败: ' + error.message);
    }
  };
  
  // 改进后的 togglePlayback 函数
  const togglePlayback = () => {
    console.log('togglePlayback 被调用, audioUrl =', audioUrl);
    console.log('流式合成完成状态:', streamCompletedRef.current);
    
    // 如果流式合成已完成且有音频URL可用，总是使用标准播放器
    if (streamCompletedRef.current && audioUrl) {
      console.log('流式合成已完成且有音频URL，使用标准播放器');
      toggleStandardPlayback();
      return;
    }
    
    // 否则根据当前可用资源决定播放方式
    if (audioUrl) {
      console.log('使用标准播放器播放URL:', audioUrl);
      toggleStandardPlayback();
    } else if (audioBufferRef.current && audioBufferRef.current.data) {
      console.log('使用流式播放器播放缓冲数据');
      // 尝试为缓冲数据创建URL
      createTemporaryAudioFile();
      
      // 如果创建URL成功，使用标准播放，否则使用流式播放
      if (audioUrl) {
        toggleStandardPlayback();
      } else {
        toggleStreamingPlayback();
      }
    } else {
      console.log('没有可播放的音频数据');
      message.info('没有可播放的音频');
    }
  };
  
  // 停止流式合成
  const stopStreaming = () => {
    // 关闭WebSocket
    if (websocketRef.current) {
      console.log('关闭WebSocket连接');
      websocketRef.current.close();
      websocketRef.current = null;
    }
    
    // 停止音频播放
    if (audioSourceRef.current) {
      try {
        console.log('停止当前音频播放');
        audioSourceRef.current.stop();
      } catch (e) {
        // 忽略错误
      }
      audioSourceRef.current = null;
    }
    
    setIsPlaying(false);
    setLoading(false);
    
    // 停止进度定时器
    if (playbackTimerRef.current) {
      clearInterval(playbackTimerRef.current);
      playbackTimerRef.current = null;
    }
    
    // 如果我们已经接收到一些音频数据，创建一个音频文件
    if (audioBuffersRef.current && audioBuffersRef.current.length > 0) {
      // 标记流式合成为完成状态
      streamCompletedRef.current = true;
      
      try {
        console.log('尝试合并已接收的音频数据');
        const mergedBuffer = mergeAudioBuffers(audioBuffersRef.current);
        
        if (mergedBuffer) {
          console.log('已接收的音频数据已合并');
          audioBufferRef.current = mergedBuffer;
          
          // 创建临时音频文件
          createTemporaryAudioFile();
        }
      } catch (error) {
        console.error('合并已接收音频数据失败:', error);
      }
    }
    
    message.info('已停止合成');
  };
  
  // 合并音频缓冲区
  const mergeAudioBuffers = (buffers) => {
    if (!buffers || buffers.length === 0) {
      console.warn('没有可合并的缓冲区');
      return null;
    }
    
    console.log(`开始合并 ${buffers.length} 个音频缓冲区`);
    
    try {
      const sampleRate = audioContextRef.current?.sampleRate || 44100;
      console.log('使用采样率:', sampleRate);
      
      // 计算总长度和记录每个缓冲区的信息
      let totalLength = 0;
      const bufferInfo = [];
      
      for (let i = 0; i < buffers.length; i++) {
        const buffer = buffers[i];
        if (buffer) {
          const length = buffer.length || (buffer.duration ? Math.floor(buffer.duration * sampleRate) : 0);
          totalLength += length;
          bufferInfo.push({
            index: i,
            length: length,
            hasGetChannelData: typeof buffer.getChannelData === 'function'
          });
        }
      }
      
      console.log('缓冲区信息:', bufferInfo);
      console.log('计算出的总长度:', totalLength);
      
      if (totalLength <= 0) {
        console.warn('计算的总长度无效');
        return null;
      }
      
      // 创建合并数组
      const mergedArray = new Float32Array(totalLength);
      let offset = 0;
      
      // 从每个缓冲区复制数据
      for (let i = 0; i < buffers.length; i++) {
        const buffer = buffers[i];
        if (buffer && typeof buffer.getChannelData === 'function') {
          try {
            const channelData = buffer.getChannelData(0);
            mergedArray.set(channelData, offset);
            offset += channelData.length;
            console.log(`缓冲区 ${i}: 成功合并 ${channelData.length} 个样本`);
          } catch (e) {
            console.error(`无法获取缓冲区 ${i} 的通道数据:`, e);
          }
        } else {
          console.warn(`缓冲区 ${i} 无法获取通道数据`);
        }
      }
      
      console.log('成功合并音频数据，总长度:', mergedArray.length);
      
      // 返回带有data和sampleRate属性的对象
      return {
        data: mergedArray,
        sampleRate: sampleRate,
        length: mergedArray.length,
        duration: mergedArray.length / sampleRate
      };
    } catch (error) {
      console.error('合并音频缓冲区失败:', error);
      return null;
    }
  };
  
  // 检查任务状态 - 经过修复的版本
  const checkTaskStatus = async (id) => {
    if (!id || taskCompletedRef.current) return;
    
    try {
      console.log(`检查任务状态: ${id}`);
      const response = await axios.get(`/api/tts/status/${id}`);
      const status = response.data;
      
      console.log(`任务状态: ${status.status}, 进度: ${status.progress}`);
      setTaskStatus(status);
      setProgress(status.progress * 100 || 0);
      
      // 如果完成，设置音频URL并更新标记
      if (status.status === 'completed') {
        const audioUrl = `/api/tts/preview_audio/${id}`;
        console.log(`任务完成，设置音频URL: ${audioUrl}`);
        setAudioUrl(audioUrl);
        setLoading(false);
        
        // 设置流式合成完成标志
        streamCompletedRef.current = true;
        
        // 设置音频时长
        if (status.duration) {
          setAudioDuration(status.duration);
        }
        
        // 标记任务已完成，防止继续检查
        taskCompletedRef.current = true;
        
        // 清除检查间隔
        if (statusIntervalRef.current) {
          clearInterval(statusIntervalRef.current);
          statusIntervalRef.current = null;
          console.log('已清除状态检查间隔');
        }
        
        // 使用去重函数显示成功消息
        showSuccessMessageOnce('合成完成');

        // 预加载音频
        if (audioRef.current) {
          audioRef.current.load();
        }
        
        // 触发回调
        if (onComplete) {
          onComplete(status.duration);
        }
      }
      // 如果失败，显示错误
      else if (status.status === 'failed') {
        setLoading(false);
        taskCompletedRef.current = true;
        
        // 清除检查间隔
        if (statusIntervalRef.current) {
          clearInterval(statusIntervalRef.current);
          statusIntervalRef.current = null;
        }
        
        console.error(`合成失败: ${status.error || '未知错误'}`);
        message.error(`合成失败: ${status.error || '未知错误'}`);
      }

      // 重置失败计数
      setStatusFailCount(0);
      
    } catch (error) {
      console.error('获取任务状态失败:', error);
      
      setStatusFailCount(prevCount => {
        const newCount = prevCount + 1;
        
        // 如果连续失败3次，停止检查
        if (newCount > 3) {
          if (statusIntervalRef.current) {
            clearInterval(statusIntervalRef.current);
            statusIntervalRef.current = null;
            setLoading(false);
            message.error('获取状态失败，请重试');
          }
        }
        
        return newCount;
      });
    }
  };
  
  // 下载函数
  const handleDownload = () => {
    if (taskStatus && taskStatus.download_url) {
      // 使用服务器提供的下载URL，添加保存标记
      const downloadUrl = `${taskStatus.download_url}?save_local=true`;
      console.log(`使用下载URL: ${downloadUrl}`);
      
      // 创建下载链接
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = `voice_synthesis_${taskStatus.task_id || taskId}.wav`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      
      message.success('开始下载音频文件');
    } else if (taskId) {
      // 兼容旧版本，构建下载URL
      const downloadUrl = `/api/tts/download/${taskId}?save_local=true`;
      console.log(`构建下载URL: ${downloadUrl}`);
      
      // 创建下载链接
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = `voice_synthesis_${taskId}.wav`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      
      message.success('开始下载音频文件');
    } else if (audioUrl) {
      // 使用音频URL下载
      console.log(`使用音频URL下载: ${audioUrl}`);
      const a = document.createElement('a');
      a.href = audioUrl;
      a.download = `voice_synthesis_${new Date().getTime()}.wav`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      
      message.success('开始下载音频文件');
    } else if (audioBufferRef.current && audioBufferRef.current.data) {
      // 处理流式合成的音频数据
      try {
        // 将音频数据转换为 16 位 PCM WAV
        const floatData = audioBufferRef.current.data;
        const sampleRate = audioBufferRef.current.sampleRate || 44100;
        
        // 转换为16位PCM
        const pcmData = new Int16Array(floatData.length);
        for (let i = 0; i < floatData.length; i++) {
          const s = Math.max(-1, Math.min(1, floatData[i]));
          pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        
        // 创建WAV头
        const wavHeader = createWavHeader(pcmData.byteLength, sampleRate);
        
        // 合并数据
        const wavBlob = new Blob([wavHeader, pcmData.buffer], { type: 'audio/wav' });
        
        // 创建下载链接
        const url = URL.createObjectURL(wavBlob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `voice_synthesis_stream_${new Date().getTime()}.wav`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        
        // 释放URL
        setTimeout(() => URL.revokeObjectURL(url), 100);
        
        message.success('开始下载流式合成音频文件');
      } catch (error) {
        console.error('创建流式音频下载失败:', error);
        message.error('下载音频失败: ' + error.message);
      }
    } else {
      message.warning('没有可下载的音频');
    }
  };
    
  // 创建WAV头
  const createWavHeader = (dataLength, sampleRate) => {
    const buffer = new ArrayBuffer(44);
    const view = new DataView(buffer);
    
    // RIFF标识符
    writeString(view, 0, 'RIFF');
    // 文件长度
    view.setUint32(4, 36 + dataLength, true);
    // WAVE标识符
    writeString(view, 8, 'WAVE');
    // fmt 块标识符
    writeString(view, 12, 'fmt ');
    // fmt 块长度
    view.setUint32(16, 16, true);
    // 样本格式 (1 = PCM)
    view.setUint16(20, 1, true);
    // 通道数 (1 = 单声道)
    view.setUint16(22, 1, true);
    // 采样率
    view.setUint32(24, sampleRate, true);
    // 字节率
    view.setUint32(28, sampleRate * 2, true);
    // 块对齐
    view.setUint16(32, 2, true);
    // 每个样本的位数
    view.setUint16(34, 16, true);
    // data 块标识符
    writeString(view, 36, 'data');
    // data 块长度
    view.setUint32(40, dataLength, true);
    
    return buffer;
  };
  
  // 写入字符串到DataView
  const writeString = (view, offset, string) => {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  };
  
  // 播放滑块变化
  const handlePlaybackSliderChange = (value) => {
    setPlaybackSliderValue(value);
    setSliderChanging(true);
  };
  
  // 播放滑块变化后
  const handlePlaybackSliderAfterChange = (value) => {
    setSliderChanging(false);
    
    // 计算新位置
    const newTime = (value / 100) * audioDuration;
    
    // 如果流式合成已完成且有完整音频URL，总是使用标准播放器
    if (streamCompletedRef.current && audioUrl && audioRef.current) {
      console.log('使用标准播放器设置播放位置:', newTime);
      try {
        audioRef.current.currentTime = newTime;
        setPlaybackProgress(newTime);
      } catch (e) {
        console.error('设置音频位置失败:', e);
        message.error('设置播放位置失败: ' + e.message);
      }
      return;
    }
    
    // 为流式播放处理寻址
    if (isStreaming) {
      try {
        // 停止当前播放
        if (audioSourceRef.current) {
          audioSourceRef.current.stop();
          audioSourceRef.current = null;
        }
        
        // 更新播放位置
        setPlaybackProgress(newTime);
        
        // 如果我们有完整的音频数据，寻找并播放
        if (audioBufferRef.current && audioBufferRef.current.data) {
          const audioContext = audioContextRef.current || initAudioContext();
          if (audioContext.state === 'suspended') {
            audioContext.resume();
          }
          
          const sampleRate = audioBufferRef.current.sampleRate;
          
          // 计算样本位置
          const startSample = Math.floor(newTime * sampleRate);
          
          // 检查是否在范围内
          if (startSample < audioBufferRef.current.data.length) {
            // 从寻址位置创建缓冲区
            const remainingData = audioBufferRef.current.data.slice(startSample);
            
            // 创建AudioBuffer
            const newBuffer = audioContext.createBuffer(1, remainingData.length, sampleRate);
            newBuffer.copyToChannel(remainingData, 0);
            
            // 创建源
            const source = audioContext.createBufferSource();
            source.buffer = newBuffer;
            source.connect(audioContext.destination);
            
            // 存储引用
            audioSourceRef.current = source;
            audioSourceRef.current.startTime = audioContext.currentTime;
            
            // 开始播放
            source.start(0);
            setIsPlaying(true);
            
            // 更新进度
            if (playbackTimerRef.current) {
              clearInterval(playbackTimerRef.current);
            }
            
            playbackTimerRef.current = setInterval(() => {
              if (isPlaying && audioContextRef.current && audioSourceRef.current) {
                const elapsedTime = audioContextRef.current.currentTime - (audioSourceRef.current.startTime || 0);
                const currentTime = newTime + elapsedTime;
                
                if (!sliderChanging && audioDuration > 0) {
                  setPlaybackSliderValue((currentTime / audioDuration) * 100);
                  setPlaybackProgress(currentTime);
                }
              }
            }, 100);
            
            // 处理播放结束
            source.onended = () => {
              setIsPlaying(false);
              if (playbackTimerRef.current) {
                clearInterval(playbackTimerRef.current);
              }
            };
          }
        }
      } catch (error) {
        console.error('音频跳转失败:', error);
        message.error('跳转失败: ' + error.message);
      }
    } else if (audioRef.current) {
      // 标准音频寻址
      try {
        audioRef.current.currentTime = newTime;
        setPlaybackProgress(newTime);
      } catch (e) {
        console.error('设置音频位置失败:', e);
        message.error('设置播放位置失败: ' + e.message);
      }
    }
  };
  
  // 快进5秒
  const handleFastForward = () => {
    // 如果流式合成已完成且有完整音频URL，使用标准播放器快进
    if (streamCompletedRef.current && audioUrl && audioRef.current) {
      const newTime = Math.min(audioRef.current.duration, audioRef.current.currentTime + 5);
      audioRef.current.currentTime = newTime;
      setPlaybackProgress(newTime);
      setPlaybackSliderValue((newTime / audioDuration) * 100);
      return;
    }
    
    // 如果正在使用流式播放
    if (audioBufferRef.current && audioBufferRef.current.data) {
      const newTime = Math.min(audioDuration, playbackProgress + 5);
      handlePlaybackSliderAfterChange((newTime / audioDuration) * 100);
    }
  };
  
  // 倒退5秒
  const handleRewind = () => {
    // 如果流式合成已完成且有完整音频URL，使用标准播放器倒退
    if (streamCompletedRef.current && audioUrl && audioRef.current) {
      const newTime = Math.max(0, audioRef.current.currentTime - 5);
      audioRef.current.currentTime = newTime;
      setPlaybackProgress(newTime);
      setPlaybackSliderValue((newTime / audioDuration) * 100);
      return;
    }
    
    // 如果正在使用流式播放
    if (audioBufferRef.current && audioBufferRef.current.data) {
      const newTime = Math.max(0, playbackProgress - 5);
      handlePlaybackSliderAfterChange((newTime / audioDuration) * 100);
    }
  };
  
  // 初始化AudioContext
  const initAudioContext = () => {
    if (!audioContextRef.current || audioContextRef.current.state === 'closed') {
      try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        audioContextRef.current = new AudioContext();
      } catch (error) {
        console.error('创建AudioContext失败:', error);
        message.error('创建音频上下文失败，请刷新页面');
      }
    }
    return audioContextRef.current;
  };
  
  // 声音类型标签
  const getVoiceTypeLabel = (type) => {
    if (type === 'pretrained') return '预训练';
    if (type === 'user-uploaded') return '我的声音';
    return '未知类型';
  };
  
  // 音频播放器渲染
  const renderAudioPlayer = () => {
    if (!audioUrl && !audioBufferRef.current && !isPlaying && loading) {
      // 没有音频，显示加载状态
      return (
        <div className="audio-player-loading" style={{ marginTop: 16, textAlign: 'center' }}>
          <div>准备音频播放器...</div>
        </div>
      );
    }
    
    if (audioUrl || audioBufferRef.current || isPlaying) {
      // 有音频，显示播放器
      return (
        <div className="audio-player" style={{ marginTop: 16 }}>
          {/* 隐藏的音频元素用于播放 */}
          {audioUrl && (
            <audio
              ref={audioRef}
              src={audioUrl}
              onPlay={() => setIsPlaying(true)}
              onPause={() => setIsPlaying(false)}
              onEnded={() => setIsPlaying(false)}
              onTimeUpdate={() => {
                if (audioRef.current && !sliderChanging) {
                  setPlaybackProgress(audioRef.current.currentTime);
                  if (audioDuration > 0) {
                    setPlaybackSliderValue((audioRef.current.currentTime / audioDuration) * 100);
                  }
                }
              }}
              onLoadedMetadata={() => {
                if (audioRef.current && audioRef.current.duration) {
                  setAudioDuration(audioRef.current.duration);
                }
              }}
              onError={(e) => {
                console.error('音频播放错误:', e);
                message.error('音频加载失败，请尝试刷新页面');
              }}
              style={{ display: 'none' }}
            />
          )}
          
          <Row align="middle" gutter={8}>
            <Col>
              <Button
                icon={<StepBackwardOutlined />}
                onClick={handleRewind}
                disabled={!audioUrl && !audioBufferRef.current}
              />
            </Col>
            
            <Col>
              <Button
                icon={isPlaying ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
                onClick={togglePlayback}
                type="primary"
                disabled={!audioUrl && (!audioBufferRef.current || !audioBufferRef.current.data)}
              >
                {isPlaying ? '暂停' : '播放'}
              </Button>
            </Col>
            
            <Col>
              <Button
                icon={<StepForwardOutlined />}
                onClick={handleFastForward}
                disabled={!audioUrl && !audioBufferRef.current}
              />
            </Col>
            
            <Col flex="auto">
              <Slider
                value={playbackSliderValue}
                onChange={handlePlaybackSliderChange}
                onAfterChange={handlePlaybackSliderAfterChange}
                disabled={!audioUrl && !audioBufferRef.current}
                tooltip={{
                  formatter: value => formatTime((value / 100) * audioDuration)
                }}
              />
            </Col>
            
            <Col>
              <Text>
                {formatTime(playbackProgress)} / {formatTime(audioDuration)}
              </Text>
            </Col>
            
            <Col>
              <Button
                icon={<DownloadOutlined />}
                onClick={handleDownload}
                disabled={!audioUrl && !audioBufferRef.current && !taskId}
              >
                下载
              </Button>
            </Col>
          </Row>
        </div>
      );
    }
    
    // 没有音频，不显示播放器
    return null;
  };
  
  return (
    <div className="simplified-tts">
      <Card
        title={
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <SoundOutlined /> <span style={{ marginLeft: 8 }}>语音合成</span>
          </div>
        }
        bordered={false}
      >
        <Form layout="vertical">
          <Form.Item 
            label="选择声音" 
            required={true}
            extra="选择预训练音色或您上传的声音，系统将自动使用合适的合成方式"
          >
            <Row gutter={8}>
              <Col flex="auto">
                <Select
                  value={voiceId}
                  onChange={handleVoiceChange}
                  placeholder="请选择声音"
                  style={{ width: '100%' }}
                  disabled={loading}
                  optionLabelProp="label"
                >
                  <OptGroup label="预训练声音">
                    {voices
                      .filter(voice => voice.type === 'pretrained')
                      .map(voice => (
                        <Option 
                          key={voice.id} 
                          value={voice.id}
                          label={voice.name}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <span>{voice.name}</span>
                            <Text type="secondary">{getVoiceTypeLabel(voice.type)}</Text>
                          </div>
                        </Option>
                      ))
                    }
                  </OptGroup>
                  
                  <OptGroup label="我的声音">
                    {voices
                      .filter(voice => voice.type === 'user-uploaded')
                      .map(voice => (
                        <Option 
                          key={voice.id} 
                          value={voice.id}
                          label={voice.name}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <span>{voice.name}</span>
                            <Text type="secondary">{getVoiceTypeLabel(voice.type)}</Text>
                          </div>
                        </Option>
                      ))
                    }
                  </OptGroup>
                </Select>
              </Col>
              <Col>
                <Button 
                  icon={<ReloadOutlined />} 
                  onClick={fetchVoices}
                  disabled={loading}
                >
                  刷新
                </Button>
              </Col>
            </Row>
          </Form.Item>
          
          <Form.Item label="合成参数">
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item label="语速" required={false}>
                  <Slider
                    min={0.5}
                    max={2.0}
                    step={0.1}
                    value={speed}
                    onChange={setSpeed}
                    disabled={loading}
                    marks={{
                      0.5: '慢',
                      1.0: '标准',
                      2.0: '快'
                    }}
                  />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item label="随机种子">
                  <Row>
                    <Col span={18}>
                      <Input
                        value={seed}
                        onChange={(e) => setSeed(parseInt(e.target.value) || 0)}
                        disabled={loading}
                      />
                    </Col>
                    <Col span={6}>
                      <Button 
                        onClick={generateRandomSeed}
                        disabled={loading}
                      >
                        随机
                      </Button>
                    </Col>
                  </Row>
                </Form.Item>
              </Col>
            </Row>
          </Form.Item>
          
          <Form.Item label="流式合成">
            <Switch
              checked={isStreaming}
              onChange={(checked) => {
                if (!loading) {
                  setIsStreaming(checked);
                  // 切换模式时重置状态
                  resetAudioState();
                  
                  message.info(checked ? '已切换到流式合成模式' : '已切换到标准合成模式');
                }
              }}
              disabled={loading}
            />
            <span style={{ marginLeft: 8 }}>
              {isStreaming ? '实时生成（边合成边播放）' : '标准生成（完成后播放）'}
            </span>
          </Form.Item>
          
          <Form.Item>
            <Space>
              <Button
                type="primary"
                loading={loading}
                onClick={isStreaming ? handleStreamingSynthesis : handleStandardSynthesis}
                disabled={loading || !text || !voiceId}
                icon={<SoundOutlined />}
              >
                开始合成
              </Button>
              
              {isStreaming && loading && (
                <Button 
                  danger 
                  icon={<StopOutlined />}
                  onClick={stopStreaming}
                >
                  停止合成
                </Button>
              )}
            </Space>
          </Form.Item>
        </Form>
        
        {/* 音频播放器 */}
        {renderAudioPlayer()}
        
        {/* 进度条 */}
        {(loading || progress > 0) && (
          <div className="progress-bar" style={{ marginTop: 16 }}>
            <Progress 
              percent={Math.round(progress)} 
              status={loading ? "active" : "normal"} 
              strokeColor={{
                from: '#108ee9',
                to: '#87d068',
              }}
            />
          </div>
        )}
        
        {/* 合成结果 */}
        {taskStatus && taskStatus.status === 'completed' && (
          <div className="result-info" style={{ marginTop: 16 }}>
            <div
              style={{
                padding: 10,
                borderRadius: 4,
                backgroundColor: '#f6ffed',
                border: '1px solid #b7eb8f'
              }}
            >
              <div style={{ fontWeight: 'bold', marginBottom: 4 }}>合成成功</div>
              <div>{`合成时长: ${taskStatus.duration?.toFixed(1) || 0} 秒`}</div>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
};

export default SimplifiedTTS;