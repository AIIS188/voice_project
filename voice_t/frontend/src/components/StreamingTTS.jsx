import React, { useState, useEffect, useRef } from 'react';
import { Button, Space, message, Progress } from 'antd';
import { 
  PlayCircleOutlined, 
  PauseCircleOutlined, 
  LoadingOutlined 
} from '@ant-design/icons';

/**
 * 流式TTS组件
 * 支持通过WebSocket进行实时语音合成和播放
 */
const StreamingTTS = ({ 
  text, 
  voiceId, 
  params = {},
  onStart,
  onComplete,
  onError,
  autoPlay = false
}) => {
  // 状态管理
  const [isConnecting, setIsConnecting] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [totalChunks, setTotalChunks] = useState(0);
  const [receivedChunks, setReceivedChunks] = useState(0);
  
  // 引用
  const websocketRef = useRef(null);
  const audioContextRef = useRef(null);
  const audioBuffersRef = useRef([]);
  const audioSourceRef = useRef(null);
  const audioQueueRef = useRef([]);
  const isProcessingRef = useRef(false);
  
  // 当组件卸载时清理资源
  useEffect(() => {
    return () => {
      cleanupWebSocket();
      cleanupAudio();
    };
  }, []);
  
  // 当autoPlay为true且文本、voiceId有效时自动开始
  useEffect(() => {
    if (autoPlay && text && voiceId && !isStreaming && !isConnecting) {
      handleStartStreaming();
    }
  }, [autoPlay, text, voiceId]);
  
  // 初始化AudioContext
  const initAudioContext = () => {
    if (!audioContextRef.current) {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      audioContextRef.current = new AudioContext();
    }
    return audioContextRef.current;
  };
  
  // 启动流式合成
  const handleStartStreaming = () => {
    if (!text || !voiceId) {
      message.warning('请提供文本和声音ID');
      return;
    }
    
    if (isStreaming || isConnecting) {
      return;
    }
    
    // 初始化音频上下文
    initAudioContext();
    
    // 重置状态
    setIsConnecting(true);
    setProgress(0);
    setTotalChunks(0);
    setReceivedChunks(0);
    audioBuffersRef.current = [];
    audioQueueRef.current = [];
    
    // 创建WebSocket连接
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const wsUrl = `${protocol}://${window.location.host}/api/tts/synthesize/stream`;
    
    try {
      websocketRef.current = new WebSocket(wsUrl);
      
      // 连接建立时发送参数
      websocketRef.current.onopen = () => {
        console.log('WebSocket连接已建立');
        setIsConnecting(false);
        setIsStreaming(true);
        
        // 发送请求参数
        websocketRef.current.send(JSON.stringify({
          text,
          voice_id: voiceId,
          params
        }));
        
        // 触发开始回调
        if (onStart) onStart();
      };
      
      // 接收数据
      websocketRef.current.onmessage = (event) => {
        handleWebSocketMessage(event);
      };
      
      // 错误处理
      websocketRef.current.onerror = (error) => {
        console.error('WebSocket错误:', error);
        setIsConnecting(false);
        setIsStreaming(false);
        message.error('连接失败，请重试');
        
        // 触发错误回调
        if (onError) onError(error);
      };
      
      // 连接关闭
      websocketRef.current.onclose = () => {
        console.log('WebSocket连接已关闭');
        setIsConnecting(false);
        setIsStreaming(false);
      };
      
    } catch (error) {
      console.error('创建WebSocket连接失败:', error);
      setIsConnecting(false);
      message.error('无法建立连接');
      
      // 触发错误回调
      if (onError) onError(error);
    }
  };
  
  // 处理WebSocket消息
  const handleWebSocketMessage = async (event) => {
    try {
      // 检查是否为文本消息（JSON）
      if (typeof event.data === 'string') {
        const jsonData = JSON.parse(event.data);
        
        // 处理不同类型的消息
        if (jsonData.type === 'info') {
          // 接收总块数信息
          if (jsonData.total_chunks) {
            setTotalChunks(jsonData.total_chunks);
          }
          
          // 接收总句子数信息
          if (jsonData.total_sentences) {
            setTotalChunks(jsonData.total_sentences);
          }
        }
        else if (jsonData.type === 'sentence_complete') {
          // 更新进度
          if (jsonData.total > 0) {
            const newProgress = Math.round((jsonData.index + 1) / jsonData.total * 100);
            setProgress(newProgress);
            setReceivedChunks(jsonData.index + 1);
          }
        }
        else if (jsonData.type === 'complete') {
          // 合成完成
          setProgress(100);
          setIsStreaming(false);
          
          // 触发完成回调
          if (onComplete) onComplete(jsonData.duration);
        }
        else if (jsonData.type === 'error') {
          // 处理错误
          message.error(`合成错误: ${jsonData.message}`);
          setIsStreaming(false);
          
          // 触发错误回调
          if (onError) onError(new Error(jsonData.message));
        }
      }
      // 处理二进制音频数据
      else if (event.data instanceof Blob) {
        const arrayBuffer = await event.data.arrayBuffer();
        
        // 将接收到的音频数据添加到队列
        audioQueueRef.current.push(arrayBuffer);
        
        // 更新接收计数
        setReceivedChunks(prev => prev + 1);
        if (totalChunks > 0) {
          setProgress(Math.round((receivedChunks + 1) / totalChunks * 100));
        }
        
        // 如果未在播放，则开始处理音频队列
        if (!isProcessingRef.current) {
          processAudioQueue();
        }
      }
    } catch (error) {
      console.error('处理WebSocket消息失败:', error);
    }
  };
  
  // 处理音频队列
  const processAudioQueue = async () => {
    if (audioQueueRef.current.length === 0 || isProcessingRef.current) {
      return;
    }
    
    isProcessingRef.current = true;
    
    try {
      // 获取音频上下文
      const audioContext = initAudioContext();
      
      // 从队列中取出一个音频缓冲区
      const arrayBuffer = audioQueueRef.current.shift();
      
      // 解码音频数据
      const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
      
      // 存储解码后的音频
      audioBuffersRef.current.push(audioBuffer);
      
      // 如果当前未播放，开始播放
      if (!isPlaying && audioContextRef.current.state !== 'suspended') {
        playNextBuffer();
        setIsPlaying(true);
      }
    } catch (error) {
      console.error('处理音频数据失败:', error);
    } finally {
      isProcessingRef.current = false;
      
      // 如果队列中还有数据，继续处理
      if (audioQueueRef.current.length > 0) {
        processAudioQueue();
      }
    }
  };
  
  // 播放下一个音频缓冲区
  const playNextBuffer = () => {
    if (audioBuffersRef.current.length === 0) {
      return;
    }
    
    // 获取音频上下文
    const audioContext = audioContextRef.current;
    
    // 创建音频源
    const source = audioContext.createBufferSource();
    source.buffer = audioBuffersRef.current[0];
    source.connect(audioContext.destination);
    
    // 保存音频源引用
    audioSourceRef.current = source;
    
    // 设置播放结束回调
    source.onended = () => {
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
  };
  
  // 暂停/恢复播放
  const togglePlayback = () => {
    if (!audioContextRef.current) return;
    
    if (isPlaying) {
      // 暂停播放
      audioContextRef.current.suspend();
      setIsPlaying(false);
    } else {
      // 恢复播放
      audioContextRef.current.resume();
      
      // 如果没有正在播放的音频源但有缓冲区，开始播放
      if (!audioSourceRef.current && audioBuffersRef.current.length > 0) {
        playNextBuffer();
      }
      
      setIsPlaying(true);
    }
  };
  
  // 停止流式合成
  const stopStreaming = () => {
    if (websocketRef.current && websocketRef.current.readyState === WebSocket.OPEN) {
      websocketRef.current.close();
    }
    setIsStreaming(false);
    
    // 也停止播放
    if (audioSourceRef.current) {
      audioSourceRef.current.stop();
      audioSourceRef.current = null;
    }
    
    setIsPlaying(false);
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
        audioContextRef.current.close();
      } catch (e) {
        // 忽略错误
      }
      audioContextRef.current = null;
    }
  };
  
  return (
    <div className="streaming-tts">
      <div className="controls">
        <Space>
          {!isStreaming && !isConnecting ? (
            <Button 
              type="primary" 
              icon={<PlayCircleOutlined />} 
              onClick={handleStartStreaming}
            >
              开始合成
            </Button>
          ) : (
            <Button 
              danger
              onClick={stopStreaming}
            >
              停止合成
            </Button>
          )}
          
          {audioBuffersRef.current.length > 0 && (
            <Button
              icon={isPlaying ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
              onClick={togglePlayback}
            >
              {isPlaying ? '暂停' : '播放'}
            </Button>
          )}
        </Space>
      </div>
      
      {(isStreaming || isConnecting || progress > 0) && (
        <div className="progress-container" style={{ marginTop: 16 }}>
          <Progress 
            percent={progress} 
            status={isStreaming || isConnecting ? "active" : "normal"} 
          />
          <div className="status-text">
            {isConnecting && <><LoadingOutlined /> 正在连接...</>}
            {isStreaming && <><LoadingOutlined /> 正在合成...</>}
            {!isStreaming && !isConnecting && progress >= 100 && '合成完成'}
          </div>
        </div>
      )}
    </div>
  );
};

export default StreamingTTS;