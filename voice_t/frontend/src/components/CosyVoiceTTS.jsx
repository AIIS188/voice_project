import React, { useState, useEffect, useRef } from 'react';
import { 
  Button, 
  Space, 
  message, 
  Progress, 
  Card, 
  Tabs, 
  Select, 
  Input, 
  Upload, 
  Slider,
  Typography,
  Row,
  Col,
  Switch,
  Form
} from 'antd';
import { 
  PlayCircleOutlined, 
  PauseCircleOutlined, 
  UploadOutlined,
  DownloadOutlined,
  AudioOutlined,
  SoundOutlined,
  GlobalOutlined,
  ExperimentOutlined,
  StepBackwardOutlined,
  StepForwardOutlined
} from '@ant-design/icons';
import axios from 'axios';

const { TabPane } = Tabs;
const { Option } = Select;
const { TextArea } = Input;
const { Title, Text } = Typography;

// 定义不同模式的操作指南
const modeInstructions = {
  sft: '1. 选择预训练音色\n2. 点击生成音频按钮',
  zero_shot: '1. 上传参考音频文件 (不超过30秒)\n2. 输入参考文本\n3. 点击生成音频按钮',
  cross_lingual: '1. 上传参考音频文件 (不超过30秒)\n2. 点击生成音频按钮',
  instruct: '1. 选择预训练音色\n2. 输入指令文本\n3. 点击生成音频按钮'
};

// 定义不同模式的标题和图标
const modeIcons = {
  sft: <SoundOutlined />,
  zero_shot: <AudioOutlined />,
  cross_lingual: <GlobalOutlined />,
  instruct: <ExperimentOutlined />
};

const modeNames = {
  sft: '预训练音色',
  zero_shot: '3s极速复刻',
  cross_lingual: '跨语种复刻',
  instruct: '自然语言控制'
};

/**
 * CosyVoice TTS组件
 * 提供多种语音合成模式：预训练音色、3s极速复刻、跨语种复刻和自然语言控制
 */
const CosyVoiceTTS = ({ 
  text, 
  onComplete 
}) => {
  // 状态管理
  const [mode, setMode] = useState('sft'); // sft, zero_shot, cross_lingual, instruct
  const [voiceId, setVoiceId] = useState('');
  const [availableVoices, setAvailableVoices] = useState([]);
  const [loading, setLoading] = useState(false);
  const [promptText, setPromptText] = useState('');
  const [instructText, setInstructText] = useState('');
  const [promptAudio, setPromptAudio] = useState(null);
  const [speed, setSpeed] = useState(1.0);
  const [seed, setSeed] = useState(Math.floor(Math.random() * 1000000));
  const [isStreaming, setIsStreaming] = useState(false);
  const [audioUrl, setAudioUrl] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [taskId, setTaskId] = useState(null);
  const [taskStatus, setTaskStatus] = useState(null);
  
  // 新增状态
  const [audioData, setAudioData] = useState(null); // 存储音频数据，不立即保存到本地
  const [playbackProgress, setPlaybackProgress] = useState(0); // 播放进度
  const [audioDuration, setAudioDuration] = useState(0); // 音频总时长
  const [playbackSliderValue, setPlaybackSliderValue] = useState(0); // 播放进度滑块值
  const [sliderChanging, setSliderChanging] = useState(false); // 标记用户是否正在拖动滑块
  
  // 引用
  const audioRef = useRef(null);
  const websocketRef = useRef(null);
  const audioContextRef = useRef(null);
  const audioBuffersRef = useRef([]);
  const audioSourceRef = useRef(null);
  const statusIntervalRef = useRef(null);
  const audioBufferRef = useRef(null); // 存储完整的音频 buffer
  const playbackTimerRef = useRef(null); // 用于跟踪播放进度的定时器
  
  // 格式化时间
  const formatTime = (time) => {
    if (!time || isNaN(time)) return '0:00';
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };
  
  // 加载可用音色
  useEffect(() => {
    loadAvailableVoices();
  }, []);
  
  // 当组件卸载时清理资源
  useEffect(() => {
    return () => {
      cleanupWebSocket();
      cleanupAudio();
      
      if (statusIntervalRef.current) {
        clearInterval(statusIntervalRef.current);
      }
      
      if (playbackTimerRef.current) {
        clearInterval(playbackTimerRef.current);
      }
    };
  }, []);
  
  // 监听任务状态
  useEffect(() => {
    if (taskId && !isStreaming) {
      // 启动状态检查
      if (statusIntervalRef.current) {
        clearInterval(statusIntervalRef.current);
      }
      
      // 定时检查任务状态
      statusIntervalRef.current = setInterval(() => {
        checkTaskStatus(taskId);
      }, 1000);
      
      // 清理函数
      return () => {
        if (statusIntervalRef.current) {
          clearInterval(statusIntervalRef.current);
        }
      };
    }
  }, [taskId, isStreaming]);
  
  // 监听音频播放事件
  useEffect(() => {
    if (audioRef.current) {
      const audio = audioRef.current;
      
      // 设置事件监听器
      const handleTimeUpdate = () => {
        if (!sliderChanging) {
          setPlaybackProgress(audio.currentTime);
          setPlaybackSliderValue((audio.currentTime / audioDuration) * 100);
        }
      };
      
      const handleLoadedMetadata = () => {
        setAudioDuration(audio.duration);
      };
      
      // 添加事件监听器
      audio.addEventListener('timeupdate', handleTimeUpdate);
      audio.addEventListener('loadedmetadata', handleLoadedMetadata);
      
      // 清理函数
      return () => {
        audio.removeEventListener('timeupdate', handleTimeUpdate);
        audio.removeEventListener('loadedmetadata', handleLoadedMetadata);
      };
    }
  }, [audioRef.current, sliderChanging, audioDuration]);
  
  // 合并音频缓冲区 - 改进版
  const mergeAudioBuffers = (buffers) => {
    if (!buffers || buffers.length === 0) {
      console.log('No buffers to merge');
      return null;
    }
    
    try {
      const sampleRate = audioContextRef.current?.sampleRate || 44100;
      
      // 计算总长度（样本数）
      let totalLength = 0;
      for (let i = 0; i < buffers.length; i++) {
        totalLength += buffers[i].length; // AudioBuffer.length 是样本帧数
      }
      
      console.log(`合并 ${buffers.length} 个缓冲区，总长度 ${totalLength} 个样本`);
      
      // 创建合并数组
      const mergedArray = new Float32Array(totalLength);
      let offset = 0;
      
      // 复制每个缓冲区的数据
      for (let i = 0; i < buffers.length; i++) {
        const buffer = buffers[i];
        const channelData = buffer.getChannelData(0);
        mergedArray.set(channelData, offset);
        offset += buffer.length;
      }
      
      return {
        data: mergedArray,
        sampleRate: sampleRate
      };
    } catch (error) {
      console.error('合并音频缓冲区错误:', error);
      return null;
    }
  };
  
  // 加载可用音色列表
  const loadAvailableVoices = async () => {
    try {
      const response = await axios.get('/api/cosyvoice/voices');
      setAvailableVoices(response.data);
      
      // 默认选择第一个音色
      if (response.data && response.data.length > 0) {
        setVoiceId(response.data[0]);
      }
    } catch (error) {
      console.error('获取音色列表失败:', error);
      message.error('获取音色列表失败');
    }
  };
  
  // 初始化AudioContext
  const initAudioContext = () => {
    if (!audioContextRef.current || audioContextRef.current.state === 'closed') {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      audioContextRef.current = new AudioContext();
      console.log('创建了新的 AudioContext');
    }
    return audioContextRef.current;
  };
  
  // 生成随机种子
  const generateRandomSeed = () => {
    const newSeed = Math.floor(Math.random() * 1000000);
    setSeed(newSeed);
    return newSeed;
  };
  
  // 处理模式切换
  const handleModeChange = (newMode) => {
    setMode(newMode);
    // 清理上一个模式的状态
    setAudioUrl(null);
    setTaskId(null);
    setTaskStatus(null);
    setProgress(0);
    setAudioData(null);
    setPlaybackProgress(0);
    setPlaybackSliderValue(0);
    setAudioDuration(0);
    cleanupAudio();
  };
  
  // 标准合成（非流式）
  const handleStandardSynthesis = async () => {
    // 验证输入
    if (!validateInput()) {
      return;
    }
    
    setLoading(true);
    setTaskId(null);
    setTaskStatus(null);
    setAudioUrl(null);
    setAudioData(null);
    setProgress(0);
    setPlaybackProgress(0);
    setPlaybackSliderValue(0);
    setAudioDuration(0);
    
    // 清理任何现有的流式播放资源
    audioBuffersRef.current = [];
    audioBufferRef.current = null;
    
    if (audioSourceRef.current) {
      try {
        audioSourceRef.current.stop();
      } catch (e) {
        // 忽略已停止的错误
      }
      audioSourceRef.current = null;
    }
    
    if (playbackTimerRef.current) {
      clearInterval(playbackTimerRef.current);
      playbackTimerRef.current = null;
    }
    
    try {
      // 创建合成请求参数
      const params = {
        mode: mode,
        speed: speed,
        seed: seed
      };
      
      let response;
      
      // 判断是否需要上传文件
      if (mode === 'zero_shot' || mode === 'cross_lingual') {
        if (!promptAudio) {
          message.error('请上传参考音频文件');
          setLoading(false);
          return;
        }
        
        // 创建表单数据
        const formData = new FormData();
        formData.append('text', text);
        formData.append('mode', mode);
        formData.append('speed', speed);
        
        if (voiceId) {
          formData.append('voice_id', voiceId);
        }
        
        if (promptText) {
          formData.append('prompt_text', promptText);
        }
        
        if (instructText) {
          formData.append('instruct_text', instructText);
        }
        
        // 添加参考音频文件
        if (promptAudio) {
          formData.append('prompt_audio', promptAudio);
        }
        
        // 发送请求
        response = await axios.post('/api/cosyvoice/synthesize/upload', formData);
      } else {
        // JSON请求
        const requestData = {
          text: text,
          voice_id: voiceId,
          params: params
        };
        
        // 添加可选参数
        if (promptText) {
          requestData.prompt_text = promptText;
        }
        
        if (instructText) {
          requestData.instruct_text = instructText;
        }
        
        // 发送请求
        response = await axios.post('/api/cosyvoice/synthesize', requestData);
      }
      
      // 保存任务ID
      if (response && response.data && response.data.task_id) {
        setTaskId(response.data.task_id);
      } else {
        throw new Error('无效的任务ID');
      }
      
    } catch (error) {
      console.error('合成请求失败:', error);
      message.error('语音合成请求失败，请重试');
      setLoading(false);
    }
  };
  
  // 流式合成
  const handleStreamingSynthesis = async () => {
    // 验证输入
    if (!validateInput()) {
      return;
    }
    
    // 重置状态
    setLoading(true);
    setIsStreaming(true);
    setProgress(0);
    setPlaybackProgress(0);
    setPlaybackSliderValue(0);
    setAudioUrl(null); // 清除非流式音频URL
    setAudioData(null);
    setTaskId(null);
    setTaskStatus(null);
    audioBuffersRef.current = [];
    audioBufferRef.current = null;
    
    // 清理任何现有的音频源和定时器
    if (audioSourceRef.current) {
      try {
        audioSourceRef.current.stop();
      } catch (e) {
        // 忽略已停止的错误
      }
      audioSourceRef.current = null;
    }
    
    if (playbackTimerRef.current) {
      clearInterval(playbackTimerRef.current);
      playbackTimerRef.current = null;
    }
    
    // 初始化音频上下文
    initAudioContext();
    
    // 创建WebSocket连接
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    // 根据实际部署环境修改WebSocket地址
    const host = window.location.host; // 自动适配当前域名
    const wsUrl = `${protocol}://localhost:8000/api/cosyvoice/synthesize/stream`;
    
    console.log(`尝试连接WebSocket: ${wsUrl}`);
    try {
      // 关闭已有连接
      if (websocketRef.current) {
        websocketRef.current.close();
      }
      
      message.loading('正在连接到服务器...');
      
      websocketRef.current = new WebSocket(wsUrl);
      
      // 连接建立时发送参数
      websocketRef.current.onopen = () => {
        console.log('WebSocket连接已建立');
        message.success('WebSocket连接已建立');
        
        // 创建请求参数
        const requestData = {
          text: text,
          voice_id: voiceId,
          params: {
            mode: mode,
            speed: speed,
            seed: seed
          }
        };
        
        // 添加可选参数
        if (promptText) {
          requestData.prompt_text = promptText;
        }
        
        if (instructText) {
          requestData.instruct_text = instructText;
        }
        
        // 添加上传的参考音频
        if (promptAudio) {
          // 注意：WebSocket不能直接发送文件，要使用标准的API上传
          requestData.prompt_audio_id = promptAudio.name; // 用文件名或其他标识符
        }
        
        // 记录发送的数据
        console.log('发送WebSocket请求:', JSON.stringify(requestData));
        
        // 发送请求
        websocketRef.current.send(JSON.stringify(requestData));
        
        // 显示开始消息
        message.info('开始流式合成');
      };
      
      // 接收数据
      websocketRef.current.onmessage = (event) => {
        console.log('收到WebSocket消息类型:', typeof event.data, event.data instanceof Blob ? 'Blob(' + event.data.size + ' bytes)' : '');
        handleWebSocketMessage(event);
      };
      
      // 错误处理
      websocketRef.current.onerror = (error) => {
        console.error('WebSocket错误:', error);
        setLoading(false);
        setIsStreaming(false);
        message.error('连接失败，请重试');
      };
      
      // 连接关闭
      websocketRef.current.onclose = (event) => {
        console.log('WebSocket连接已关闭', event.code, event.reason);
        setLoading(false);
        // 重要：不要在这里设置 setIsStreaming(false)，因为我们需要保持控件的可见性
        
        if (event.code !== 1000) {
          // 非正常关闭
          message.error(`连接已关闭: ${event.reason || '未知原因'}`);
        }
      };
      
      // 设置超时处理
      setTimeout(() => {
        if (websocketRef.current && websocketRef.current.readyState !== WebSocket.OPEN) {
          console.error('WebSocket连接超时');
          message.error('连接超时，请重试');
          setLoading(false);
          setIsStreaming(false);
          
          if (websocketRef.current) {
            websocketRef.current.close();
          }
        }
      }, 5000); // 5秒超时
      
    } catch (error) {
      console.error('创建WebSocket连接失败:', error);
      setLoading(false);
      setIsStreaming(false);
      message.error('无法建立连接: ' + error.message);
    }
  };
  
  // 处理WebSocket消息 - 改进版
  const handleWebSocketMessage = async (event) => {
    try {
      // 检查是否为文本消息（JSON）
      if (typeof event.data === 'string') {
        const jsonData = JSON.parse(event.data);
        
        // 处理不同类型的消息
        if (jsonData.type === 'info') {
          // 接收信息
          console.log('信息:', jsonData);
          
          // 如果收到总块数信息，预先计算大致时长
          if (jsonData.total_chunks) {
            // 估算总时长 (每块约0.5秒)
            const estimatedDuration = jsonData.total_chunks * 0.5;
            setAudioDuration(estimatedDuration);
          }
        }
        else if (jsonData.type === 'progress') {
          // 更新进度
          setProgress(prev => Math.min(95, prev + 5));
          
          // 如果有块索引和持续时间信息，也更新音频总时长
          if (jsonData.chunk_index !== undefined && jsonData.duration) {
            // 更新该块的持续时间
            setAudioDuration(prev => Math.max(prev, (jsonData.chunk_index + 1) * jsonData.duration));
          }
        }
        else if (jsonData.type === 'complete') {
          // 合成完成
          setProgress(100);
          setLoading(false);
          
          // 重要：保持流式合成模式，不切换回非流式模式
          // setIsStreaming(false); - 删除这行以保持流式模式
          
          // 设置音频总时长
          if (jsonData.duration) {
            setAudioDuration(jsonData.duration);
          }
          
          // 触发完成回调
          if (onComplete) {
            onComplete(jsonData.duration);
          }
          
          message.success(`合成完成，时长: ${jsonData.duration?.toFixed(1) || 0} 秒`);
          
          // 如果有累积的音频缓冲区，创建完整的音频数据
          if (audioBuffersRef.current.length > 0) {
            // 使用改进的合并函数
            audioBufferRef.current = mergeAudioBuffers(audioBuffersRef.current);
            
            if (audioBufferRef.current) {
              console.log('成功合并音频数据，可用于播放和跳转');
              console.log(`最终缓冲区: ${audioBufferRef.current.data.length} 个样本，采样率 ${audioBufferRef.current.sampleRate}Hz`);
              message.success('音频数据已合并，可以下载完整音频');
            } else {
              console.error('合并音频缓冲区失败');
              message.error('合并音频数据失败');
            }
          } else {
            console.warn('没有可用于合并的音频缓冲区');
          }
        }
        else if (jsonData.type === 'error') {
          // 处理错误
          message.error(`合成错误: ${jsonData.message}`);
          setIsStreaming(false);
          setLoading(false);
        }
      }
      // 处理二进制音频数据
      else if (event.data instanceof Blob) {
        const arrayBuffer = await event.data.arrayBuffer();
        
        // 获取音频上下文
        const audioContext = initAudioContext();
        
        try {
          // 解码音频数据
          audioContext.decodeAudioData(arrayBuffer, (audioBuffer) => {
            // 存储解码后的音频
            audioBuffersRef.current.push(audioBuffer);
            
            // 更新进度条 - 根据已接收的音频块更新总长度估计
            if (audioBuffersRef.current.length > 0) {
              let totalDuration = 0;
              audioBuffersRef.current.forEach(buffer => {
                totalDuration += buffer.duration;
              });
              
              // 更新音频总时长（保守估计，可能比实际略长）
              setAudioDuration(prev => Math.max(prev, totalDuration * 1.1));
              
              // 创建并更新合并的缓冲区，供后续播放/跳转使用
              try {
                audioBufferRef.current = mergeAudioBuffers(audioBuffersRef.current);
                console.log('更新了合并的缓冲区，总长度:', 
                  audioBufferRef.current ? audioBufferRef.current.data.length : 'null');
              } catch (mergeError) {
                console.error('更新合并缓冲区时出错:', mergeError);
              }
              
              // 如果不是正在播放，但有新的音频块且自动播放启用，则开始播放
              if (!isPlaying && audioContextRef.current.state !== 'suspended' && audioBuffersRef.current.length === 1) {
                // 自动开始播放第一个块
                playNextBuffer();
              }
            }
          }, (error) => {
            console.error('音频解码失败:', error);
          });
        } catch (decodeError) {
          console.error('解码音频时出错:', decodeError);
        }
      }
    } catch (error) {
      console.error('处理WebSocket消息失败:', error);
    }
  };
  
  // 播放下一个音频缓冲区
  const playNextBuffer = () => {
    if (audioBuffersRef.current.length === 0) {
      return;
    }
    
    // 获取音频上下文
    const audioContext = audioContextRef.current;
    
    // 确保音频上下文不是暂停状态
    if (audioContext.state === 'suspended') {
      audioContext.resume();
    }
    
    // 创建音频源
    const source = audioContext.createBufferSource();
    source.buffer = audioBuffersRef.current[0];
    source.connect(audioContext.destination);
    
    // 保存音频源引用和开始时间
    audioSourceRef.current = source;
    audioSourceRef.current.startTime = audioContext.currentTime;
    audioSourceRef.current.bufferDuration = source.buffer.duration || 0;
    
    // 设置播放结束回调
    source.onended = () => {
      // 更新播放进度
      if (audioDuration > 0) {
        const currentProgress = (playbackProgress + audioSourceRef.current.bufferDuration) / audioDuration;
        setPlaybackSliderValue(currentProgress * 100);
        setPlaybackProgress(prev => prev + audioSourceRef.current.bufferDuration);
      }
      
      // 移除已播放的缓冲区
      audioBuffersRef.current.shift();
      
      // 如果还有下一个缓冲区，播放它
      if (audioBuffersRef.current.length > 0) {
        playNextBuffer();
      } else {
        // 如果没有更多缓冲区但流式传输仍在进行
        if (isStreaming) {
          // 等待更多数据
          setIsPlaying(false);
        } else {
          // 流式传输已结束
          setIsPlaying(false);
        }
      }
    };
    
    // 开始播放
    source.start(0);
    setIsPlaying(true);
    
    // 设置播放进度更新定时器
    if (playbackTimerRef.current) {
      clearInterval(playbackTimerRef.current);
    }
    
    playbackTimerRef.current = setInterval(() => {
      if (isPlaying && audioContextRef.current && audioSourceRef.current) {
        const elapsedTime = audioContextRef.current.currentTime - (audioSourceRef.current.startTime || 0);
        const currentTime = playbackProgress + elapsedTime;
        
        if (!sliderChanging && audioDuration > 0) {
          setPlaybackSliderValue((currentTime / audioDuration) * 100);
          setPlaybackProgress(currentTime); // 实时更新播放进度值
        }
      }
    }, 100);
  };
  
  // 检查任务状态
  const checkTaskStatus = async (id) => {
    if (!id) return;
    
    try {
      const response = await axios.get(`/api/cosyvoice/status/${id}`);
      const status = response.data;
      
      setTaskStatus(status);
      setProgress(status.progress * 100);
      
      // 如果已完成，设置音频URL
      if (status.status === 'completed') {
        // 不再保存到本地，而是准备好下载链接
        setAudioUrl(`/api/cosyvoice/download/${id}`);
        setLoading(false);
        
        // 设置音频时长
        if (status.duration) {
          setAudioDuration(status.duration);
        }
        
        // 清除定时器
        if (statusIntervalRef.current) {
          clearInterval(statusIntervalRef.current);
        }
        
        message.success('合成完成');
        
        // 触发完成回调
        if (onComplete) {
          onComplete(status.duration);
        }
      }
      // 如果失败，显示错误
      else if (status.status === 'failed') {
        setLoading(false);
        
        // 清除定时器
        if (statusIntervalRef.current) {
          clearInterval(statusIntervalRef.current);
        }
        
        message.error(`合成失败: ${status.error || '未知错误'}`);
      }
      
    } catch (error) {
      console.error('获取任务状态失败:', error);
    }
  };
  
  // 下载音频
  const handleDownload = () => {
    if (!audioUrl) return;
    
    // 使用服务器URL下载
    const a = document.createElement('a');
    a.href = audioUrl;
    a.download = `cosyvoice_tts_${new Date().getTime()}.wav`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };
  
  // 从缓冲区下载流式音频 - 改进版
  const handleDownloadStreaming = () => {
    // 检查是否有单个音频块或多个音频块
    if (!audioBufferRef.current && audioBuffersRef.current.length === 0) {
      message.warning('没有可下载的音频数据');
      return;
    }
    
    try {
      let data, sampleRate;
      
      // 如果有合并的音频数据，使用它
      if (audioBufferRef.current && audioBufferRef.current.data) {
        console.log('使用合并的音频缓冲区下载');
        data = audioBufferRef.current.data;
        sampleRate = audioBufferRef.current.sampleRate;
      } 
      // 否则如果有单个音频块，合并它们
      else if (audioBuffersRef.current.length > 0) {
        console.log('从音频块创建合并的缓冲区下载');
        const merged = mergeAudioBuffers(audioBuffersRef.current);
        
        if (!merged) {
          message.error('合并音频数据失败');
          return;
        }
        
        data = merged.data;
        sampleRate = merged.sampleRate;
        
        // 同时更新保存的音频数据供后续使用
        audioBufferRef.current = merged;
      } else {
        message.warning('没有可下载的音频数据');
        return;
      }
      
      // 将Float32Array转换为Int16Array (16-bit PCM)
      const pcmData = new Int16Array(data.length);
      for (let i = 0; i < data.length; i++) {
        const s = Math.max(-1, Math.min(1, data[i]));
        pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }
      
      // 创建WAV头
      const wavBuffer = createWavHeader(pcmData.length * 2, sampleRate);
      
      // 合并头和数据
      const wavBlob = new Blob([wavBuffer, pcmData], { type: 'audio/wav' });
      
      // 创建下载链接
      const url = URL.createObjectURL(wavBlob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `cosyvoice_tts_streaming_${new Date().getTime()}.wav`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      
      // 清理
      setTimeout(() => URL.revokeObjectURL(url), 100);
      
      message.success('音频文件已下载');
    } catch (error) {
      console.error('创建下载文件失败:', error);
      message.error('下载音频失败: ' + error.message);
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
    // fmt子块标识符
    writeString(view, 12, 'fmt ');
    // fmt子块长度
    view.setUint32(16, 16, true);
    // 音频格式 (1 = PCM)
    view.setUint16(20, 1, true);
    // 声道数 (1 = 单声道)
    view.setUint16(22, 1, true);
    // 采样率
    view.setUint32(24, sampleRate, true);
    // 字节率
    view.setUint32(28, sampleRate * 2, true);
    // 块对齐
    view.setUint16(32, 2, true);
    // 位深度
    view.setUint16(34, 16, true);
    // data子块标识符
    writeString(view, 36, 'data');
    // data子块长度
    view.setUint32(40, dataLength, true);
    
    return buffer;
  };
  
  // 写入字符串到DataView
  const writeString = (view, offset, string) => {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  };
  
  // 播放/暂停标准音频
  const toggleStandardPlayback = () => {
    if (!audioRef.current) return;
    
    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play();
    }
    
    setIsPlaying(!isPlaying);
  };
  
  // 暂停/恢复流式播放 - 改进版
  const toggleStreamingPlayback = () => {
    try {
      // 如果没有音频上下文或已关闭，初始化它
      if (!audioContextRef.current || audioContextRef.current.state === 'closed') {
        console.log('初始化新的 AudioContext');
        initAudioContext();
      }
      
      // 如果正在播放，暂停
      if (isPlaying) {
        if (audioContextRef.current && audioContextRef.current.state === 'running') {
          console.log('暂停 AudioContext');
          audioContextRef.current.suspend();
        }
        
        if (playbackTimerRef.current) {
          clearInterval(playbackTimerRef.current);
        }
        
        setIsPlaying(false);
        return;
      }
      
      // 如果暂停，恢复
      if (audioContextRef.current && audioContextRef.current.state === 'suspended') {
        console.log('恢复 AudioContext');
        audioContextRef.current.resume();
        
        // 如果有音频源，只恢复播放和定时器
        if (audioSourceRef.current) {
          console.log('恢复现有播放');
          
          // 重启进度定时器
          if (playbackTimerRef.current) {
            clearInterval(playbackTimerRef.current);
          }
          
          playbackTimerRef.current = setInterval(() => {
            if (audioContextRef.current && audioSourceRef.current) {
              const elapsedTime = audioContextRef.current.currentTime - (audioSourceRef.current.startTime || 0);
              const currentTime = playbackProgress + elapsedTime;
              
              if (!sliderChanging && audioDuration > 0) {
                setPlaybackSliderValue((currentTime / audioDuration) * 100);
                setPlaybackProgress(currentTime);
              }
            }
          }, 100);
          
          setIsPlaying(true);
          return;
        }
      }
      
      // 如果有完整的音频数据但没有活动源，从当前位置播放
      if (audioBufferRef.current && audioBufferRef.current.data) {
        console.log('从完整缓冲区开始播放，位置:', playbackProgress);
        
        // 使用类似于寻址的代码，从当前位置播放
        const audioContext = audioContextRef.current;
        const sampleRate = audioBufferRef.current.sampleRate;
        
        // 计算开始样本
        const startSample = Math.floor(playbackProgress * sampleRate);
        
        // 检查是否在范围内
        if (startSample < audioBufferRef.current.data.length) {
          // 从开始位置创建新缓冲区
          const remainingData = audioBufferRef.current.data.slice(startSample);
          
          // 创建 AudioBuffer
          const newBuffer = audioContext.createBuffer(1, remainingData.length, sampleRate);
          newBuffer.copyToChannel(remainingData, 0);
          
          // 创建新音频源
          const source = audioContext.createBufferSource();
          source.buffer = newBuffer;
          source.connect(audioContext.destination);
          
          // 保存引用和信息
          audioSourceRef.current = source;
          audioSourceRef.current.startTime = audioContext.currentTime;
          
          // 开始播放
          source.start(0);
          setIsPlaying(true);
          
          // 设置进度定时器
          if (playbackTimerRef.current) {
            clearInterval(playbackTimerRef.current);
          }
          
          playbackTimerRef.current = setInterval(() => {
            if (audioContextRef.current && audioSourceRef.current) {
              const elapsedTime = audioContextRef.current.currentTime - (audioSourceRef.current.startTime || 0);
              const currentTime = playbackProgress + elapsedTime;
              
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
          
          return;
        }
      }
      
      // 如果有单独的缓冲区但没有当前源，播放它们
      if (audioBuffersRef.current.length > 0) {
        console.log('从缓冲区队列开始播放');
        playNextBuffer();
        return;
      }
      
      // 如果到这里，我们没有可播放的音频
      message.info('没有可播放的音频数据');
    } catch (error) {
      console.error('切换播放出错:', error);
      message.error('播放控制失败: ' + error.message);
    }
  };
  
  // 停止流式合成
  const stopStreaming = () => {
    if (websocketRef.current && websocketRef.current.readyState === WebSocket.OPEN) {
      websocketRef.current.close();
    }
    setIsStreaming(false);
    setLoading(false);
    
    // 也停止播放
    if (audioSourceRef.current) {
      try {
        audioSourceRef.current.stop();
      } catch (e) {
        // 忽略已停止的错误
      }
      audioSourceRef.current = null;
    }
    
    setIsPlaying(false);
    
    // 停止进度更新定时器
    if (playbackTimerRef.current) {
      clearInterval(playbackTimerRef.current);
    }
  };
  
  // 测试WebSocket连接
  const testSimpleWebSocket = () => {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const wsUrl = `${protocol}://${window.location.host}/api/cosyvoice/simple-test`;
    
    console.log(`测试简单WebSocket: ${wsUrl}`);
    message.loading('正在测试简单WebSocket...');
    
    const ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
      console.log('简单WebSocket已连接');
      message.success('简单WebSocket连接成功');
    };
    
    ws.onmessage = (event) => {
      console.log('收到简单WebSocket消息:', event.data);
      message.info(`收到: ${event.data}`);
    };
    
    ws.onerror = (error) => {
      console.error('简单WebSocket错误:', error);
      message.error('简单WebSocket连接失败');
    };
    
    ws.onclose = () => {
      console.log('简单WebSocket已关闭');
      message.info('简单WebSocket已关闭');
    };
  };
  
  // 清理WebSocket
  const cleanupWebSocket = () => {
    if (websocketRef.current) {
      if (websocketRef.current.readyState === WebSocket.OPEN) {
        websocketRef.current.close();
      }
      websocketRef.current = null;
    }
  };
  
  // 清理音频
  const cleanupAudio = () => {
    if (audioSourceRef.current) {
      try {
        audioSourceRef.current.stop();
      } catch (e) {
        // 忽略已停止的错误
      }
      audioSourceRef.current = null;
    }
    
    if (audioContextRef.current) {
      try {
        audioContextRef.current.suspend();
      } catch (e) {
        // 忽略错误
      }
    }
    
    audioBuffersRef.current = [];
    
    // 停止播放进度更新定时器
    if (playbackTimerRef.current) {
      clearInterval(playbackTimerRef.current);
      playbackTimerRef.current = null;
    }
  };
  
  // 处理播放进度滑块改变
  const handlePlaybackSliderChange = (value) => {
    setPlaybackSliderValue(value);
    setSliderChanging(true);
  };
  
  // 处理播放进度滑块改变后 - 改进版
  const handlePlaybackSliderAfterChange = (value) => {
    setSliderChanging(false);
    
    // 计算新的播放位置
    const newTime = (value / 100) * audioDuration;
    
    if (isStreaming || audioBufferRef.current) {
      // 支持流式音频跳转
      try {
        // 停止当前播放
        if (audioSourceRef.current) {
          audioSourceRef.current.stop();
          audioSourceRef.current = null;
        }
        
        // 更新播放进度
        setPlaybackProgress(newTime);
        
        // 如果有完整的音频数据，从新位置开始播放
        if (audioBufferRef.current && audioBufferRef.current.data && audioBufferRef.current.data.length > 0) {
          console.log('在完整音频缓冲区中跳转');
          
          // 确保我们有一个音频上下文
          const audioContext = audioContextRef.current || initAudioContext();
          if (audioContext.state === 'suspended') {
            audioContext.resume();
          }
          
          const sampleRate = audioBufferRef.current.sampleRate;
          
          // 计算开始样本位置
          const startSample = Math.floor(newTime * sampleRate);
          console.log(`跳转到样本 ${startSample} (${newTime}s) / ${audioBufferRef.current.data.length} 个样本`);
          
          // 确保不超出缓冲区范围
          if (startSample < audioBufferRef.current.data.length) {
            // 从剩余数据创建新缓冲区
            const remainingData = audioBufferRef.current.data.slice(startSample);
            
            // 创建新的 AudioBuffer
            const newBuffer = audioContext.createBuffer(1, remainingData.length, sampleRate);
            newBuffer.copyToChannel(remainingData, 0);
            
            // 创建并连接新音频源
            const source = audioContext.createBufferSource();
            source.buffer = newBuffer;
            source.connect(audioContext.destination);
            
            // 保存引用和播放信息
            audioSourceRef.current = source;
            audioSourceRef.current.startTime = audioContext.currentTime;
            
            // 开始播放
            source.start(0);
            setIsPlaying(true);
            
            // 播放期间更新进度
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
          } else {
            // 超出缓冲区范围
            message.warning('尝试跳转到音频结尾之后的位置');
            setPlaybackProgress(audioDuration);
            setPlaybackSliderValue(100);
          }
        } else {
          // 没有可用的缓冲区
          console.warn('没有可用于跳转的完整音频数据');
          message.info('没有可跳转的完整音频数据');
        }
      } catch (error) {
        console.error('跳转过程中出错:', error);
        message.error('跳转播放失败: ' + error.message);
      }
    } else if (audioRef.current) {
      // 对于标准音频，设置播放位置
      audioRef.current.currentTime = newTime;
      setPlaybackProgress(newTime);
    }
  };
  
  // 快进5秒
  const handleFastForward = () => {
    if (audioRef.current) {
      const newTime = Math.min(audioRef.current.duration, audioRef.current.currentTime + 5);
      audioRef.current.currentTime = newTime;
      setPlaybackProgress(newTime);
      setPlaybackSliderValue((newTime / audioDuration) * 100);
    }
  };
  
  // 后退5秒
  const handleRewind = () => {
    if (audioRef.current) {
      const newTime = Math.max(0, audioRef.current.currentTime - 5);
      audioRef.current.currentTime = newTime;
      setPlaybackProgress(newTime);
      setPlaybackSliderValue((newTime / audioDuration) * 100);
    }
  };
  
  // 验证输入
  const validateInput = () => {
    if (!text) {
      message.warning('请输入文本内容');
      return false;
    }
    
    switch (mode) {
      case 'sft':
        if (!voiceId) {
          message.warning('请选择预训练音色');
          return false;
        }
        break;
        
      case 'zero_shot':
        if (!promptAudio) {
          message.warning('请上传参考音频文件');
          return false;
        }
        if (!promptText) {
          message.warning('请输入参考文本');
          return false;
        }
        break;
        
      case 'cross_lingual':
        if (!promptAudio) {
          message.warning('请上传参考音频文件');
          return false;
        }
        break;
        
      case 'instruct':
        if (!voiceId) {
          message.warning('请选择预训练音色');
          return false;
        }
        if (!instructText) {
          message.warning('请输入指令文本');
          return false;
        }
        break;
        
      default:
        break;
    }
    
    return true;
  };
  
  // 处理参考音频上传
  const handlePromptAudioUpload = (info) => {
    if (info.file.status === 'done') {
      setPromptAudio(info.file.originFileObj);
      message.success(`${info.file.name} 上传成功`);
    } else if (info.file.status === 'error') {
      message.error(`${info.file.name} 上传失败`);
    }
  };
  
  // 渲染模式特定的控制面板
  const renderModePanel = () => {
    switch (mode) {
      case 'sft':
        return (
          <div className="sft-panel">
            <Form.Item label="选择预训练音色" required={true}>
              <Select
                value={voiceId}
                onChange={setVoiceId}
                placeholder="请选择预训练音色"
                style={{ width: '100%' }}
                disabled={loading}
              >
                {availableVoices.map(voice => (
                  <Option key={voice} value={voice}>{voice}</Option>
                ))}
              </Select>
            </Form.Item>
          </div>
        );
        
      case 'zero_shot':
        return (
          <div className="zero-shot-panel">
            <Form.Item label="上传参考音频" required={true}>
              <Upload
                name="promptAudio"
                accept="audio/*"
                maxCount={1}
                showUploadList={true}
                beforeUpload={() => false}
                onChange={handlePromptAudioUpload}
                disabled={loading}
              >
                <Button icon={<UploadOutlined />} disabled={loading || isStreaming}>
                  选择音频文件
                </Button>
              </Upload>
              <div style={{ marginTop: 8, color: '#999' }}>
                提示：参考音频不超过30秒，语音清晰
              </div>
            </Form.Item>
            
            <Form.Item label="参考文本" required={true}>
              <TextArea
                value={promptText}
                onChange={(e) => setPromptText(e.target.value)}
                placeholder="请输入参考音频中说的文本内容"
                rows={3}
                disabled={loading || isStreaming}
              />
            </Form.Item>
          </div>
        );
        
      case 'cross_lingual':
        return (
          <div className="cross-lingual-panel">
            <Form.Item label="上传参考音频" required={true}>
              <Upload
                name="promptAudio"
                accept="audio/*"
                maxCount={1}
                showUploadList={true}
                beforeUpload={() => false}
                onChange={handlePromptAudioUpload}
                disabled={loading || isStreaming}
              >
                <Button icon={<UploadOutlined />} disabled={loading || isStreaming}>
                  选择音频文件
                </Button>
              </Upload>
              <div style={{ marginTop: 8, color: '#999' }}>
                提示：参考音频不超过30秒，语音清晰
              </div>
            </Form.Item>
            
            <div style={{ 
              marginBottom: 16, 
              background: '#e6f7ff', 
              padding: 12, 
              borderRadius: 4,
              border: '1px solid #91d5ff'
            }}>
              <div style={{ fontWeight: 'bold', marginBottom: 4 }}>跨语种复刻提示</div>
              <div>合成文本的语言应与参考音频的语言不同，例如：参考音频为中文，合成文本为英文。</div>
            </div>
          </div>
        );
        
      case 'instruct':
        return (
          <div className="instruct-panel">
            <Form.Item label="选择预训练音色" required={true}>
              <Select
                value={voiceId}
                onChange={setVoiceId}
                placeholder="请选择预训练音色"
                style={{ width: '100%' }}
                disabled={loading || isStreaming}
              >
                {availableVoices.map(voice => (
                  <Option key={voice} value={voice}>{voice}</Option>
                ))}
              </Select>
            </Form.Item>
            
            <Form.Item label="指令文本" required={true}>
              <TextArea
                value={instructText}
                onChange={(e) => setInstructText(e.target.value)}
                placeholder="请输入指令文本，例如：请用悲伤的语气朗读"
                rows={3}
                disabled={loading || isStreaming}
              />
            </Form.Item>
          </div>
        );
        
      default:
        return null;
    }
  };
  
  // 渲染音频播放控制
  const renderAudioControl = () => {
    // 流式合成模式下的播放控制 - 无论是否有数据，都显示控制面板
    if (isStreaming) {
      return (
        <div className="audio-control" style={{ marginTop: 16 }}>
          <div>
            <Row align="middle" gutter={8}>
              <Col>
                <Button
                  icon={isPlaying ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
                  onClick={toggleStreamingPlayback}
                  disabled={audioBuffersRef.current.length === 0 && !audioBufferRef.current} // 只在没有任何音频数据时禁用
                  type="primary"
                >
                  {isPlaying ? '暂停' : '播放'}
                </Button>
              </Col>
              
              <Col flex="auto">
                <Slider
                  value={playbackSliderValue}
                  onChange={handlePlaybackSliderChange}
                  onAfterChange={handlePlaybackSliderAfterChange}
                  disabled={audioDuration <= 0} // 只在没有时长信息时禁用
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
                  onClick={handleDownloadStreaming}
                  disabled={!audioBufferRef.current && audioBuffersRef.current.length === 0} // 只在没有任何音频数据时禁用
                >
                  下载
                </Button>
              </Col>
            </Row>
          </div>
        </div>
      );
    } else if (audioUrl) {
      // 标准合成播放控制
      return (
        <div className="audio-control" style={{ marginTop: 16 }}>
          <audio
            ref={audioRef}
            src={audioUrl}
            onPlay={() => setIsPlaying(true)}
            onPause={() => setIsPlaying(false)}
            onEnded={() => setIsPlaying(false)}
            style={{ display: 'none' }}
          />
          
          <div>
            <Row align="middle" gutter={8}>
              <Col>
                <Button
                  icon={<StepBackwardOutlined />}
                  onClick={handleRewind}
                  disabled={!audioRef.current}
                />
              </Col>
              
              <Col>
                <Button
                  icon={isPlaying ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
                  onClick={toggleStandardPlayback}
                  type="primary"
                >
                  {isPlaying ? '暂停' : '播放'}
                </Button>
              </Col>
              
              <Col>
                <Button
                  icon={<StepForwardOutlined />}
                  onClick={handleFastForward}
                  disabled={!audioRef.current}
                />
              </Col>
              
              <Col flex="auto">
                <Slider
                  value={playbackSliderValue}
                  onChange={handlePlaybackSliderChange}
                  onAfterChange={handlePlaybackSliderAfterChange}
                  disabled={!audioRef.current}
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
                >
                  下载
                </Button>
              </Col>
            </Row>
          </div>
        </div>
      );
    }
    
    // 没有音频时，仍然显示空的控制面板用于占位
    if (isStreaming) {
      return (
        <div className="audio-control" style={{ marginTop: 16 }}>
          <div>
            <Row align="middle" gutter={8}>
              <Col>
                <Button
                  icon={<PlayCircleOutlined />}
                  disabled={true}
                  type="primary"
                >
                  播放
                </Button>
              </Col>
              
              <Col flex="auto">
                <Slider
                  value={0}
                  disabled={true}
                />
              </Col>
              
              <Col>
                <Text>
                  0:00 / 0:00
                </Text>
              </Col>
              
              <Col>
                <Button
                  icon={<DownloadOutlined />}
                  disabled={true}
                >
                  下载
                </Button>
              </Col>
            </Row>
          </div>
        </div>
      );
    }
    
    return null;
  };
  
  return (
    <div className="cosyvoice-tts">
      <Card
        title={
          <div style={{ display: 'flex', alignItems: 'center' }}>
            {modeIcons[mode]} <span style={{ marginLeft: 8 }}>语音合成 - {modeNames[mode]}</span>
          </div>
        }
        bordered={false}
      >
        <Tabs activeKey={mode} onChange={handleModeChange}>
          <TabPane 
            tab={
              <span>
                <SoundOutlined /> 预训练音色
              </span>
            } 
            key="sft"
          />
          <TabPane 
            tab={
              <span>
                <AudioOutlined /> 3s极速复刻
              </span>
            } 
            key="zero_shot"
          />
          <TabPane 
            tab={
              <span>
                <GlobalOutlined /> 跨语种复刻
              </span>
            } 
            key="cross_lingual"
          />
          <TabPane 
            tab={
              <span>
                <ExperimentOutlined /> 自然语言控制
              </span>
            } 
            key="instruct"
          />
        </Tabs>
        
        <div className="instruction-panel" style={{ marginBottom: 16, background: '#f5f5f5', padding: 12, borderRadius: 4 }}>
          <Title level={5}>操作步骤</Title>
          <Text>
            {modeInstructions[mode].split('\n').map((line, i) => (
              <div key={i}>{line}</div>
            ))}
          </Text>
        </div>
        
        <Row gutter={[16, 16]}>
          <Col span={24}>
            <Form layout="vertical">
              {renderModePanel()}
              
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
                    // 只在非加载状态下允许切换
                    if (!loading) {
                      setIsStreaming(checked);
                      // 重置部分状态
                      if (checked) {
                        // 进入流式模式时重置所有与播放相关的状态
                        setAudioUrl(null);
                        setTaskId(null);
                        setTaskStatus(null);
                        setProgress(0);
                        setAudioData(null);
                        setPlaybackProgress(0);
                        setPlaybackSliderValue(0);
                        setAudioDuration(0);
                        cleanupAudio();
                        message.info('已切换到流式合成模式，合成时将自动播放');
                      } else {
                        // 退出流式模式
                        message.info('已切换到标准合成模式');
                        // 关闭任何可能的WebSocket连接
                        if (websocketRef.current) {
                          websocketRef.current.close();
                          websocketRef.current = null;
                        }
                        // 重置流式相关状态
                        audioBuffersRef.current = [];
                        audioBufferRef.current = null;
                        setPlaybackProgress(0);
                        setPlaybackSliderValue(0);
                        cleanupAudio();
                      }
                    }
                  }}
                  disabled={loading}
                />
                <span style={{ marginLeft: 8 }}>
                  {isStreaming ? '实时生成（自动播放）' : '标准生成（等待完成后播放）'}
                </span>
              </Form.Item>
              
              <Form.Item>
                <Space>
                  <Button
                    type="primary"
                    loading={loading}
                    onClick={isStreaming ? handleStreamingSynthesis : handleStandardSynthesis}
                    disabled={loading}
                  >
                    开始合成
                  </Button>
                  
                  {isStreaming && loading && (
                    <Button danger onClick={stopStreaming}>
                      停止合成
                    </Button>
                  )}
                </Space>
              </Form.Item>
            </Form>
          </Col>
        </Row>
        
        {/* 音频播放控件 */}
        {renderAudioControl()}
        
        {(loading || progress > 0) && (
          <div className="progress-bar" style={{ marginTop: 16 }}>
            <Progress percent={Math.round(progress)} status={loading ? "active" : "normal"} />
          </div>
        )}
        
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
        
        {process.env.NODE_ENV === 'development' && (
          <Card title="调试信息" style={{ marginTop: 16 }} size="small">
            <div>
              <div><b>WebSocket状态:</b> {
                websocketRef.current ? 
                ['正在连接', '已连接', '正在关闭', '已关闭'][websocketRef.current.readyState] : 
                '未初始化'
              }</div>
              <div><b>isStreaming:</b> {isStreaming ? '是' : '否'}</div>
              <div><b>isPlaying:</b> {isPlaying ? '是' : '否'}</div>
              <div><b>loading:</b> {loading ? '是' : '否'}</div>
              <div><b>audioBuffers:</b> {audioBuffersRef.current ? audioBuffersRef.current.length : 0} 个</div>
              <div>
                <Button 
                  size="small" 
                  onClick={() => {
                    console.log('WebSocket状态:', websocketRef.current);
                    console.log('音频缓冲区:', audioBuffersRef.current);
                    message.info('调试信息已打印到控制台');
                  }}
                >
                  打印调试信息
                </Button>
                <Button size="small" onClick={testSimpleWebSocket} style={{ marginLeft: 8 }}>
                  测试WebSocket
                </Button>
              </div>
            </div>
          </Card>
        )}
      </Card>
    </div>
  );
};

export default CosyVoiceTTS;