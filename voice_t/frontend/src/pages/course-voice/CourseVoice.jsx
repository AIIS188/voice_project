import React, { useState, useEffect, useRef } from 'react';
import {
  Layout,
  Typography,
  Card,
  Button,
  message,
  Alert,
  Space,
  Upload,
  Table,
  Form,
  Select,
  Slider,
  Progress,
  Modal,
  Descriptions,
  Row,
  Col,
  Input,
  Switch,
  Divider
} from 'antd';
import {
  SoundOutlined,
  UploadOutlined,
  FileTextOutlined,
  DownloadOutlined,
  ReloadOutlined,
  SettingOutlined,
  PlayCircleOutlined,
  PauseCircleOutlined,
  StepBackwardOutlined,
  StepForwardOutlined,
  StopOutlined
} from '@ant-design/icons';

import axios from 'axios';

const { Header, Content } = Layout;
const { Title, Paragraph, Text } = Typography;
const { Option, OptGroup } = Select;
const { TextArea } = Input;

// API base URL
const API_BASE_URL = '/api/course_service';

const EnhancedCosyVoicePage = () => {


  // Courseware states
  const [coursewareList, setCoursewareList] = useState([]);
  const [tasksList, setTasksList] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [currentTask, setCurrentTask] = useState(null);
  const [statusPolling, setStatusPolling] = useState(null);
  const [statusProgress, setStatusProgress] = useState(0);
  const [taskDetailsVisible, setTaskDetailsVisible] = useState(false);
  const [selectedTaskDetails, setSelectedTaskDetails] = useState(null);
  const [extractedTextVisible, setExtractedTextVisible] = useState(false);
  const [extractedTextDetails, setExtractedTextDetails] = useState(null);

  // Voice parameters
  const [voiceParams, setVoiceParams] = useState({
    voice_id: '',
    speed: 1.0,
    emotion: 'neutral',
    pitch: 0.0,
    energy: 1.0,
    pause_factor: 1.0
  });

  // Voice synthesis states
  const [text, setText] = useState('欢迎使用声教助手，这是语音合成系统，可以生成自然流畅的语音。');
  const [voices, setVoices] = useState([]);
  const [seed, setSeed] = useState(Math.floor(Math.random() * 1000000));
  const [audioUrl, setAudioUrl] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [taskId, setTaskId] = useState(null);
  const [taskStatus, setTaskStatus] = useState(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [statusFailCount, setStatusFailCount] = useState(0);
  const [playbackProgress, setPlaybackProgress] = useState(0);
  const [audioDuration, setAudioDuration] = useState(0);
  const [playbackSliderValue, setPlaybackSliderValue] = useState(0);
  const [sliderChanging, setSliderChanging] = useState(false);
  // References for audio handling
  const audioRef = useRef(null);
  const statusIntervalRef = useRef(null);
  const websocketRef = useRef(null);
  const audioContextRef = useRef(null);
  const audioBuffersRef = useRef([]);
  const audioSourceRef = useRef(null);
  const audioBufferRef = useRef(null);
  const playbackTimerRef = useRef(null);
  const taskCompletedRef = useRef(false);
  const successMessageShownRef = useRef(false);
  const streamCompletedRef = useRef(false);

  // Available emotions
  const availableEmotions = [
    { id: 'neutral', name: '平静' },
    { id: 'happy', name: '愉快' },
    { id: 'sad', name: '悲伤' },
    { id: 'angry', name: '愤怒' },
    { id: 'fearful', name: '恐惧' }
  ];

  // Debug mode
  const [debugMode, setDebugMode] = useState(false);
  const [apiResponse, setApiResponse] = useState(null);

  // 切换调试模式
  const toggleDebugMode = () => {
    setDebugMode(!debugMode);
    message.info(`调试模式已${!debugMode ? '开启' : '关闭'}`);
  };

  // Format time helper
  const formatTime = (time) => {
    if (!time || isNaN(time)) return '0:00';
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  // Fetch courseware, tasks, and voices on component mount
  useEffect(() => {
    fetchCoursewareList();
    fetchTasksList();
    fetchVoices();

    // Initialize AudioContext
    if (typeof window !== 'undefined') {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (AudioContext && !audioContextRef.current) {
        audioContextRef.current = new AudioContext();
      }
    }

    // Clean up resources when component unmounts
    return () => {
      stopStatusPolling();
      cleanupResources();

      // Clean up temporary Blob URL
      if (audioUrl && audioUrl.startsWith('blob:')) {
        URL.revokeObjectURL(audioUrl);
      }
    };
  }, []);

  // Clean up resources function
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

  // Fetch available voices
  const fetchVoices = async () => {
    try {
      console.log('开始获取声音列表');
      const response = await axios.get('/api/voice/list');
      console.log('获取声音列表响应:', response.data);

      if (response.data && response.data.items) {
        console.log('设置声音列表:', response.data.items);
        setVoices(response.data.items);

        // Select first voice by default
        if (response.data.items.length > 0) {
          console.log('选择默认声音:', response.data.items[0].id);
          setVoiceParams(prev => ({
            ...prev,
            voice_id: response.data.items[0].id
          }));
        }
      } else if (response.data && Array.isArray(response.data)) {
        // 处理直接返回数组的情况
        console.log('设置声音列表(数组格式):', response.data);
        setVoices(response.data);

        // Select first voice by default
        if (response.data.length > 0) {
          console.log('选择默认声音(数组格式):', response.data[0].id);
          setVoiceParams(prev => ({
            ...prev,
            voice_id: response.data[0].id
          }));
        }
      } else {
        console.warn('获取声音列表返回不完整数据:', response.data);
        message.warning('获取声音列表返回不完整数据');

        // 如果没有返回数据，使用预设的声音列表
        const presetVoices = [
          { id: '中文女', name: '中文女声', type: 'pretrained', gender: 'female' },
          { id: '中文男', name: '中文男声', type: 'pretrained', gender: 'male' },
          { id: '英文女', name: '英文女声', type: 'pretrained', gender: 'female' },
          { id: '英文男', name: '英文男声', type: 'pretrained', gender: 'male' },
          { id: '日语男', name: '日语男声', type: 'pretrained', gender: 'male' },
          { id: '韩语女', name: '韩语女声', type: 'pretrained', gender: 'female' },
          { id: '粤语女', name: '粤语女声', type: 'pretrained', gender: 'female' }
        ];
        console.log('使用预设声音列表:', presetVoices);
        setVoices(presetVoices);

        if (presetVoices.length > 0) {
          setVoiceParams(prev => ({
            ...prev,
            voice_id: presetVoices[0].id
          }));
        }
      }
    } catch (error) {
      console.error('获取声音列表失败:', error);
      message.error('获取声音列表失败，请稍后重试');

      // 使用模拟数据作为备选
      const mockVoices = [
        { id: '中文女', name: '中文女声', type: 'pretrained', gender: 'female' },
        { id: '中文男', name: '中文男声', type: 'pretrained', gender: 'male' },
        { id: '英文女', name: '英文女声', type: 'pretrained', gender: 'female' },
        { id: '英文男', name: '英文男声', type: 'pretrained', gender: 'male' },
        { id: '日语男', name: '日语男声', type: 'pretrained', gender: 'male' },
        { id: '韩语女', name: '韩语女声', type: 'pretrained', gender: 'female' },
        { id: '粤语女', name: '粤语女声', type: 'pretrained', gender: 'female' }
      ];
      console.log('使用模拟声音数据:', mockVoices);
      setVoices(mockVoices);

      if (mockVoices.length > 0) {
        setVoiceParams(prev => ({
          ...prev,
          voice_id: mockVoices[0].id
        }));
      }
    }
  };

  // Generate random seed
  const generateRandomSeed = () => {
    const newSeed = Math.floor(Math.random() * 1000000);
    setSeed(newSeed);
  };

  // Reset audio state
  const resetAudioState = () => {
    setAudioUrl(null);
    setTaskId(null);
    setTaskStatus(null);
    setProgress(0);
    setPlaybackProgress(0);
    setPlaybackSliderValue(0);
    setAudioDuration(0);
    taskCompletedRef.current = false;
    successMessageShownRef.current = false;
    streamCompletedRef.current = false;

    // Stop current playback
    if (audioRef.current) {
      try {
        audioRef.current.pause();
      } catch (e) {
        console.error('Error stopping audio playback:', e);
      }
    }

    if (audioSourceRef.current) {
      try {
        audioSourceRef.current.stop();
      } catch (e) {
        // Ignore already stopped errors
      }
      audioSourceRef.current = null;
    }
  };

  // Show success message once
  const showSuccessMessageOnce = (messageText) => {
    if (!successMessageShownRef.current) {
      message.success(messageText);
      successMessageShownRef.current = true;
    }
  };

  // Standard synthesis function
  const handleStandardSynthesis = async () => {
    console.log('开始语音合成请求');
    console.log('当前文本:', text);
    console.log('当前声音ID:', voiceParams.voice_id);
    console.log('当前声音参数:', voiceParams);

    // Validate input
    if (!text) {
      message.warning('请输入要合成的文本');
      return;
    }

    if (!voiceParams.voice_id) {
      message.warning('请选择声音');
      return;
    }

    // Reset state
    resetAudioState();
    console.log('重置音频状态完成');

    // Clean up audioUrl (if it's a blob URL)
    if (audioUrl && audioUrl.startsWith('blob:')) {
      URL.revokeObjectURL(audioUrl);
      setAudioUrl(null);
      console.log('清理旧的Blob URL');
    }

    setLoading(true);
    setStatusFailCount(0);

    try {
      // Prepare request
      const params = {
        speed: voiceParams.speed,
        seed: seed,
        pitch: voiceParams.pitch,
        energy: voiceParams.energy,
        pause_factor: voiceParams.pause_factor,
        emotion: voiceParams.emotion
      };
      console.log('准备请求参数:', params);

      // Show loading message
      message.loading('正在提交合成请求...', 1);

      // Send synthesis request
      console.log('发送合成请求到:', '/api/tts/synthesize');
      const response = await axios.post('/api/tts/synthesize', {
        text: text,
        voice_id: voiceParams.voice_id,
        params: params
      });

      console.log('合成请求响应:', response.data);

      // Handle response
      if (response?.data?.task_id) {
        const newTaskId = response.data.task_id;
        console.log('设置任务ID:', newTaskId);
        setTaskId(newTaskId);
        message.success('合成任务已提交，请稍候');

        // taskId has been updated, useEffect will handle status checking interval
      } else {
        throw new Error('无效的任务ID');
      }

    } catch (error) {
      console.error('合成请求失败:', error);
      message.error('语音合成请求失败: ' + (error.response?.data?.detail || error.message));
      setLoading(false);

      // 模拟成功响应用于测试
      if (process.env.NODE_ENV === 'development') {
        console.log('开发模式: 模拟成功响应');
        const mockAudioUrl = 'https://example.com/mock-audio.wav';
        setAudioUrl(mockAudioUrl);
        setLoading(false);
        message.success('开发模式: 模拟合成完成');
      }
    }
  };

  // Check TTS task status
  const checkTTSTaskStatus = async (id) => {
    if (!id || taskCompletedRef.current) return;

    try {
      console.log(`检查任务状态: ${id}`);
      const response = await axios.get(`/api/tts/status/${id}`);
      const status = response.data;

      console.log(`任务状态: ${status.status}, 进度: ${status.progress}`);
      setTaskStatus(status);
      setProgress(status.progress * 100 || 0);

      // If completed, set audio URL and update flags
      if (status.status === 'completed') {
        const audioUrl = `/api/tts/preview_audio/${id}`;
        console.log(`任务完成，设置音频URL: ${audioUrl}`);
        setAudioUrl(audioUrl);
        setLoading(false);

        // Set streaming synthesis completion flag
        streamCompletedRef.current = true;

        // Set audio duration
        if (status.duration) {
          setAudioDuration(status.duration);
        }

        // Mark task as completed to prevent further checking
        taskCompletedRef.current = true;

        // Clear checking interval
        if (statusIntervalRef.current) {
          clearInterval(statusIntervalRef.current);
          statusIntervalRef.current = null;
          console.log('已清除状态检查间隔');
        }

        // Show success message once
        showSuccessMessageOnce('合成完成');

        // Preload audio
        if (audioRef.current) {
          audioRef.current.load();
        }
      }
      // If failed, show error
      else if (status.status === 'failed') {
        setLoading(false);
        taskCompletedRef.current = true;

        // Clear checking interval
        if (statusIntervalRef.current) {
          clearInterval(statusIntervalRef.current);
          statusIntervalRef.current = null;
        }

        console.error(`合成失败: ${status.error || '未知错误'}`);
        message.error(`合成失败: ${status.error || '未知错误'}`);
      }

      // Reset failure count
      setStatusFailCount(0);

      return status;
    } catch (error) {
      console.error('获取任务状态失败:', error);

      setStatusFailCount(prevCount => {
        const newCount = prevCount + 1;

        // If failed 3 times in a row, stop checking
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

      return null;
    }
  };

  // Monitor task status
  useEffect(() => {
    // Reset completion state
    taskCompletedRef.current = false;
    successMessageShownRef.current = false;
    streamCompletedRef.current = false;

    if (taskId) {
      if (statusIntervalRef.current) {
        clearInterval(statusIntervalRef.current);
      }

      statusIntervalRef.current = setInterval(() => {
        // Only check status if task is not completed
        if (!taskCompletedRef.current) {
          checkTTSTaskStatus(taskId);
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

  // Toggle standard playback
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
        // Ensure audio element is loaded
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

  // Download function
  const handleDownload = () => {
    if (taskStatus && taskStatus.download_url) {
      // Use server-provided download URL with save flag
      const downloadUrl = `${taskStatus.download_url}?save_local=true`;
      console.log(`使用下载URL: ${downloadUrl}`);

      // Create download link
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = `voice_synthesis_${taskStatus.task_id || taskId}.wav`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);

      message.success('开始下载音频文件');
    } else if (taskId) {
      // Compatibility with older versions, build download URL
      const downloadUrl = `/api/tts/download/${taskId}?save_local=true`;
      console.log(`构建下载URL: ${downloadUrl}`);

      // Create download link
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = `voice_synthesis_${taskId}.wav`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);

      message.success('开始下载音频文件');
    } else if (audioUrl) {
      // Use audio URL for download
      console.log(`使用音频URL下载: ${audioUrl}`);
      const a = document.createElement('a');
      a.href = audioUrl;
      a.download = `voice_synthesis_${new Date().getTime()}.wav`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);

      message.success('开始下载音频文件');
    } else {
      message.warning('没有可下载的音频');
    }
  };

  // Playback slider change
  const handlePlaybackSliderChange = (value) => {
    setPlaybackSliderValue(value);
    setSliderChanging(true);
  };

  // Playback slider after change
  const handlePlaybackSliderAfterChange = (value) => {
    setSliderChanging(false);

    // Calculate new position
    const newTime = (value / 100) * audioDuration;

    if (audioRef.current) {
      // Standard audio seeking
      try {
        audioRef.current.currentTime = newTime;
        setPlaybackProgress(newTime);
      } catch (e) {
        console.error('设置音频位置失败:', e);
        message.error('设置播放位置失败: ' + e.message);
      }
    }
  };

  // Fast forward 5 seconds
  const handleFastForward = () => {
    if (audioRef.current) {
      const newTime = Math.min(audioRef.current.duration, audioRef.current.currentTime + 5);
      audioRef.current.currentTime = newTime;
      setPlaybackProgress(newTime);
      setPlaybackSliderValue((newTime / audioDuration) * 100);
    }
  };

  // Rewind 5 seconds
  const handleRewind = () => {
    if (audioRef.current) {
      const newTime = Math.max(0, audioRef.current.currentTime - 5);
      audioRef.current.currentTime = newTime;
      setPlaybackProgress(newTime);
      setPlaybackSliderValue((newTime / audioDuration) * 100);
    }
  };

  // Handle text change
  const handleTextChange = (e) => {
    setText(e.target.value);
  };





  // Courseware API functions
  const fetchCoursewareList = async () => {
    try {
      setLoading(true);
      console.log('获取课件列表...');
      // 使用正确的API端点
      const response = await axios.get(`/api/course_service/list`);
      console.log('获取课件列表响应:', response.data);

      if (debugMode) {
        setApiResponse(response.data);
      }
      setCoursewareList(response.data);
    } catch (error) {
      console.error('获取课件列表失败:', error);
      message.error('获取课件列表失败: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  const fetchTasksList = async () => {
    try {
      setLoading(true);
      console.log('获取任务列表...');
      // 使用正确的API端点
      const response = await axios.get(`/api/course_service/tasks`);
      console.log('获取任务列表响应:', response.data);

      if (debugMode) {
        setApiResponse(response.data);
      }
      setTasksList(response.data);
    } catch (error) {
      console.error('获取任务列表失败:', error);
      message.error('获取任务列表失败: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (file, name) => {
    setUploading(true);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('name', name || file.name);

    try {
      console.log('上传课件文件:', file.name);
      // 使用API_BASE_URL
      const response = await axios.post(`${API_BASE_URL}/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });

      console.log('课件上传响应:', response.data);

      if (debugMode) {
        setApiResponse(response.data);
      }

      message.success('课件上传成功');
      fetchCoursewareList();
    } catch (error) {
      console.error('课件上传失败:', error);
      message.error('课件上传失败: ' + (error.response?.data?.detail || error.message));
    } finally {
      setUploading(false);
    }
  };

  const extractText = async (fileId) => {
    try {
      setLoading(true);
      // 使用API_BASE_URL
      const response = await axios.get(`${API_BASE_URL}/extract/${fileId}`);

      if (debugMode) {
        setApiResponse(response.data);
      }

      // 将提取的文本设置到输入框中
      if (response.data.text) {
        setText(response.data.text);
      }

      // 将提取的详细文本保存下来，供开发者查看
      setExtractedTextDetails(response.data);
      // 直接调用显示函数
      setTimeout(() => showExtractedTextDetails(), 500);

      message.success('文本提取成功');
    } catch (error) {
      console.error('文本提取失败:', error);
      message.error('文本提取失败: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  const generateVoicedCourseware = async (fileId) => {
    try {
      setLoading(true);
      // 生成语音课件

      // 检查声音ID是否有效
      if (!voiceParams.voice_id) {
        message.error('请选择一个声音');
        return;
      }

      // 检查文件ID是否有效
      if (!fileId) {
        message.error('请选择一个课件文件');
        return;
      }

      // 使用API_BASE_URL
      const response = await axios.post(`${API_BASE_URL}/generate`, {
        file_id: fileId,
        ...voiceParams
      });

      if (debugMode) {
        setApiResponse(response.data);
      }

      if (!response.data.task_id) {
        message.error('服务器响应中缺少任务ID');
        return;
      }

      message.success('语音课件生成任务已提交');
      setCurrentTask(response.data.task_id);

      // Start polling for task status
      startStatusPolling(response.data.task_id);

      fetchTasksList();
    } catch (error) {
      console.error('生成语音课件失败:', error);

      // 显示更详细的错误信息
      let errorMessage = '生成语音课件失败';

      if (error.response) {
        console.error('错误响应数据:', error.response.data);
        errorMessage += ': ' + (error.response.data.detail || error.response.statusText || error.message);
      } else if (error.request) {
        console.error('未收到响应:', error.request);
        errorMessage += ': 服务器未响应，请检查网络连接';
      } else {
        console.error('请求配置错误:', error.message);
        errorMessage += ': ' + error.message;
      }

      message.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const optimizeVoiceParams = async () => {
    try {
      setLoading(true);
      const voiceId = voiceParams.voice_id;
      const textSample = "欢迎使用声教助手，这是语音合成系统，可以生成自然流畅的语音。"; // Default sample text

      console.log('优化语音参数，声音ID:', voiceId);
      // 使用API_BASE_URL
      const response = await axios.get(
        `${API_BASE_URL}/optimize-params/${voiceId}?text_sample=${encodeURIComponent(textSample)}`
      );

      console.log('优化语音参数响应:', response.data);

      if (debugMode) {
        setApiResponse(response.data);
      }

      // Update voice parameters with optimized values
      setVoiceParams(prev => ({
        ...prev,
        speed: response.data.speed || prev.speed,
        pitch: response.data.pitch || prev.pitch,
        energy: response.data.energy || prev.energy,
        pause_factor: response.data.pause_factor || prev.pause_factor
      }));

      message.success('语音参数已优化');
    } catch (error) {
      console.error('优化语音参数失败:', error);
      message.error('优化语音参数失败: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  const checkCoursewareTaskStatus = async (taskId) => {
    try {
      // 如果任务已经完成，不再检查状态
      if (taskCompletedRef.current) {
        console.log('任务已经完成，不再检查状态');
        stopStatusPolling();
        return null;
      }

      console.log('检查任务状态，任务ID:', taskId);

      // 检查任务ID是否有效
      if (!taskId) {
        console.error('任务ID无效');
        stopStatusPolling();
        return null;
      }

      // 使用API_BASE_URL
      const response = await axios.get(`${API_BASE_URL}/status/${taskId}`);

      if (debugMode) {
        setApiResponse(response.data);
      }

      // 检查响应是否有效
      if (!response.data || typeof response.data !== 'object') {
        console.error('无效的任务状态响应:', response.data);
        return null;
      }

      // 检查状态是否存在
      if (!response.data.status) {
        console.error('响应中缺少状态字段:', response.data);
        return null;
      }

      // 检查是否有停止轮询标志
      if (response.data.stop_polling) {
        console.log('收到停止轮询标志，停止轮询');
        stopStatusPolling();
        return response.data;
      }

      // Update progress based on status
      switch (response.data.status) {
        case 'pending':
          setStatusProgress(10);
          break;
        case 'processing':
          // Calculate progress based on any progress info in the response
          const progressInfo = response.data.progress || 0;
          const calculatedProgress = progressInfo ? 10 + (progressInfo * 80) : 50;
          setStatusProgress(calculatedProgress);
          break;
        case 'completed':
          setStatusProgress(100);

          // 立即标记任务完成
          taskCompletedRef.current = true;

          // 立即停止轮询
          stopStatusPolling();

          // 只显示一次成功消息
          if (!successMessageShownRef.current) {
            message.success('语音课件生成完成');
            successMessageShownRef.current = true;
          }

          // 刷新任务列表
          fetchTasksList();

          // 返回状态对象后立即结束函数
          return response.data;
        case 'failed':
          console.error('任务状态: 失败, 错误信息:', response.data.error);
          setStatusProgress(0);
          stopStatusPolling();

          // 显示更详细的错误信息
          let errorMessage = '语音课件生成失败';
          if (response.data.error) {
            if (response.data.error.includes('TTS engine not available')) {
              errorMessage += ': 语音合成引擎不可用，请联系管理员';
            } else if (response.data.error.includes('No text extracted')) {
              errorMessage += ': 课件没有提取文本，请先提取文本';
            } else {
              errorMessage += ': ' + response.data.error;
            }
          } else {
            errorMessage += ': 未知错误';
          }

          message.error(errorMessage);
          break;
        default:
          console.warn('未知任务状态:', response.data.status);
          setStatusProgress(0);
      }

      return response.data;
    } catch (error) {
      console.error('检查任务状态失败:', error);

      // 显示更详细的错误信息
      let errorMessage = '检查任务状态失败';

      if (error.response) {
        console.error('错误响应数据:', error.response.data);
        errorMessage += ': ' + (error.response.data.detail || error.response.statusText || error.message);
      } else if (error.request) {
        console.error('未收到响应:', error.request);
        errorMessage += ': 服务器未响应，请检查网络连接';
      } else {
        console.error('请求配置错误:', error.message);
        errorMessage += ': ' + error.message;
      }

      message.error(errorMessage);
      stopStatusPolling();
      return null;
    }
  };

  const startStatusPolling = (taskId) => {
    // Stop any existing polling
    stopStatusPolling();

    // 重置标志
    successMessageShownRef.current = false;
    taskCompletedRef.current = false;

    // Start new polling
    const intervalId = setInterval(() => {
      // 如果任务已经完成，停止轮询
      if (taskCompletedRef.current) {
        stopStatusPolling();
        return;
      }
      checkCoursewareTaskStatus(taskId);
    }, 2000); // Poll every 2 seconds

    setStatusPolling(intervalId);
  };

  const stopStatusPolling = () => {
    if (statusPolling) {
      clearInterval(statusPolling);
      setStatusPolling(null);
    }
  };

  // Modified download function in CourseVoicePage.jsx
// Modified download function in CourseVoicePage.jsx
const downloadTaskResult = async (taskId) => {
  try {
    // Show a loading message
    message.loading('正在准备下载...', 0.5);
    
    // First get the task status to check if it's completed and get file paths
    const statusResponse = await axios.get(`${API_BASE_URL}/status/${taskId}`);
    const statusData = statusResponse.data;

    // Check task status
    if (statusData.status !== 'completed' && statusData.status !== 'failed') {
      message.error(`课件还未生成完成，当前状态: ${statusData.status}`);
      return;
    }

    // If task failed, show warning
    if (statusData.status === 'failed') {
      message.warning(`此任务已失败，但仍然可以尝试下载文件。错误信息: ${statusData.error || '未知错误'}`);
    }

    // Use direct download URL with appropriate parameters
    const downloadUrl = `${API_BASE_URL}/download/${taskId}?timestamp=${new Date().getTime()}`;
    console.log(`下载URL: ${downloadUrl}`);

    // Create a temporary hidden link and trigger download
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.target = '_blank';
    link.download = `voiced_courseware_${taskId}.pptx`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    message.success('开始下载语音课件');
  } catch (error) {
    console.error('下载语音课件失败:', error);
    let errorMessage = '下载语音课件失败';
    
    if (error.response) {
      console.error('错误响应数据:', error.response.data);
      errorMessage += ': ' + (error.response.data.detail || error.response.statusText || error.message);
    } else {
      errorMessage += ': ' + error.message;
    }
    
    message.error(errorMessage);
  }
};

// Modified manifest download function
const downloadManifest = async (taskId) => {
  try {
    // Show a loading message
    message.loading('正在准备下载清单文件...', 0.5);
    
    // Use direct download URL with cache-busting parameter
    const downloadUrl = `${API_BASE_URL}/manifest/${taskId}?timestamp=${new Date().getTime()}`;
    console.log(`清单下载URL: ${downloadUrl}`);

    // Create a temporary hidden link and trigger download
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.target = '_blank';
    link.download = `manifest_${taskId}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    message.success('开始下载清单文件');
  } catch (error) {
    console.error('下载清单文件失败:', error);
    message.error('下载清单文件失败: ' + error.message);
  }
};

  const showTaskDetails = async (taskId) => {
    try {
      // 使用 fetch 而不是 checkTTSTaskStatus，因为我们需要获取课件任务的状态
      const response = await fetch(`${API_BASE_URL}/status/${taskId}`);
      const status = await response.json();

      console.log('任务详情:', status);

      // 如果任务失败并且有详细错误信息，显示在控制台中
      if (status.status === 'failed' && status.error_details) {
        console.log('详细错误信息:', status.error_details);
      }

      setSelectedTaskDetails(status);
      setTaskDetailsVisible(true);
    } catch (error) {
      console.error('获取任务详情失败:', error);
      message.error('获取任务详情失败: ' + error.message);
    }
  };

  // Upload props configuration
  const uploadProps = {
    name: 'file',
    accept: '.ppt,.pptx,.pdf',
    beforeUpload: (file) => {
      // Show confirm modal to get courseware name
      Modal.confirm({
        title: '上传课件',
        content: (
          <div>
            <p>文件名: {file.name}</p>
            <Input
              placeholder="请输入课件名称"
              defaultValue={file.name.split('.')[0]}
              id="courseware-name-input"
            />
          </div>
        ),
        onOk: () => {
          const nameInput = document.getElementById('courseware-name-input');
          const name = nameInput ? nameInput.value : file.name.split('.')[0];
          handleUpload(file, name);
        }
      });
      return false; // Prevent default upload behavior
    },
    showUploadList: false,
  };

  // Courseware list columns
  const coursewareColumns = [
    {
      title: '课件名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '文件ID',
      dataIndex: 'file_id',
      key: 'file_id',
      ellipsis: true,
      width: 250,
    },
    {
      title: '上传时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (text) => text || '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 300,
      render: (_, record) => (
        <Space size="small">
          <Button
            icon={<FileTextOutlined />}
            onClick={() => extractText(record.file_id)}
            size="small"
          >
            提取文本
          </Button>
          <Button
            type="primary"
            icon={<SoundOutlined />}
            onClick={() => generateVoicedCourseware(record.file_id)}
            size="small"
          >
            生成语音课件
          </Button>
        </Space>
      ),
    },
  ];

  // Tasks list columns
  const tasksColumns = [
    {
      title: '课件名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status) => {
        switch (status) {
          case 'pending':
            return <Text type="warning">等待中</Text>;
          case 'processing':
            return <Text type="warning">处理中</Text>;
          case 'completed':
            return <Text type="success">已完成</Text>;
          case 'failed':
            return <Text type="danger">失败</Text>;
          default:
            return status;
        }
      }
    },
    {
      title: '操作',
      key: 'action',
      width: 350,
      render: (_, record) => (
        <Space size="small">
          <Button
            icon={<ReloadOutlined />}
            onClick={() => checkTTSTaskStatus(record.task_id)}
            size="small"
          >
            刷新状态
          </Button>
          <Button
            type="primary"
            icon={<DownloadOutlined />}
            onClick={() => downloadTaskResult(record.task_id)}
            size="small"
            disabled={record.status !== 'completed' && record.status !== 'failed'}
          >
            下载
          </Button>
          <Button
            icon={<FileTextOutlined />}
            onClick={() => downloadManifest(record.task_id)}
            size="small"
            disabled={record.status !== 'completed' && record.status !== 'failed'}
          >
            下载清单
          </Button>
          <Button
            type="link"
            onClick={() => showTaskDetails(record.task_id)}
            size="small"
          >
            详情
          </Button>
        </Space>
      ),
    },
  ];

  // 这里不需要重复声明 toggleDebugMode 函数

  // 显示提取的文本详情
  const showExtractedTextDetails = () => {
    if (!extractedTextDetails) return null;

    // 将提取的文本显示在控制台中，方便开发者调试
    console.log('提取的文本详情:', extractedTextDetails);

    // 如果有幻灯片数据，显示每张幻灯片的文本
    if (Array.isArray(extractedTextDetails)) {
      extractedTextDetails.forEach((slide, index) => {
        console.log(`幻灯片 ${index + 1}:`);
        console.log(`标题: ${slide.title || '无标题'}`);
        console.log(`内容: ${slide.content || '无内容'}`);
        console.log(`备注: ${slide.notes || '无备注'}`);
        console.log('-------------------');
      });
    } else if (typeof extractedTextDetails === 'object') {
      // 如果是对象，显示对象的属性
      Object.keys(extractedTextDetails).forEach(key => {
        console.log(`${key}: ${JSON.stringify(extractedTextDetails[key])}`);
      });
    } else {
      // 如果是字符串，直接显示
      console.log(extractedTextDetails);
    }

    // 显示提示消息
    message.info('提取的文本详情已在控制台中显示，请按 F12 查看');
  };

  return (
    <Layout className="cosyvoice-page">
      <Header style={{ background: '#fff', padding: '0 20px', borderBottom: '1px solid #f0f0f0' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <SoundOutlined style={{ fontSize: 24, marginRight: 8 }} />
            <Title level={3} style={{ margin: 0 }}>
              语音课件生成系统
            </Title>
          </div>
          <Button
            icon={<SettingOutlined />}
            type={debugMode ? "primary" : "default"}
            onClick={toggleDebugMode}
          >
            调试模式
          </Button>
        </div>
      </Header>

      <Content style={{ padding: '20px', backgroundColor: '#f0f2f5', minHeight: 'calc(100vh - 64px)' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto' }}>
          <Card style={{ marginBottom: 20 }}>
            <Paragraph>
              <Text strong>声教助手</Text> 是高质量语音合成与课件配音系统，可以生成自然流畅的教学语音。
              本系统支持PPT/PPTX课件上传与自动配音，让您的教学内容配上专业级的声音。
            </Paragraph>

            <Alert
              message="主要功能"
              description={
                <ul>
                  <li><Text strong>课件上传</Text>：支持PPT/PPTX/PDF课件上传和管理</li>
                  <li><Text strong>文本提取</Text>：自动提取课件中的文本内容</li>
                  <li><Text strong>语音合成</Text>：将文本转换为自然流畅的语音</li>
                  <li><Text strong>语音课件</Text>：生成带有语音讲解的课件文件</li>
                </ul>
              }
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
            />
          </Card>

          <div>

              <Card title="语音参数设置" style={{ marginBottom: 20 }}>
                <Form layout="vertical">
                  <Form.Item label="输入文本">
                    <TextArea
                      value={text}
                      onChange={handleTextChange}
                      placeholder="请输入要合成的文本内容..."
                      rows={6}
                      allowClear
                      maxLength={2000}
                      showCount
                    />

                    <div style={{ marginTop: 16, display: 'flex', justifyContent: 'space-between' }}>
                      <div>
                        <Space>
                          <Button onClick={() => setText('')}>清空文本</Button>
                          <Button type="primary" onClick={() => setText('欢迎使用声教助手，这是语音合成系统，可以生成自然流畅的语音。')}>使用示例文本</Button>
                        </Space>
                      </div>

                      <div>
                        <Text type="secondary">
                          建议文本长度: 800~2000字
                        </Text>
                      </div>
                    </div>
                  </Form.Item>

                  <Divider />

                  <Form.Item label="选择声音">
                    <Row gutter={8}>
                      <Col span={20}>
                        <Select
                          value={voiceParams.voice_id}
                          onChange={val => setVoiceParams({...voiceParams, voice_id: val})}
                          style={{ width: '100%' }}
                          showSearch
                          optionFilterProp="label"
                          optionLabelProp="label"
                        >
                          <OptGroup label="预训练声音">
                            {voices
                              .filter(voice => voice.type === 'pretrained' || voice.type === 'recommended' || !voice.type)
                              .map(voice => (
                                <Option
                                  key={voice.id}
                                  value={voice.id}
                                  label={voice.name}
                                >
                                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                    <span>{voice.name}</span>
                                    <Text type="secondary">{voice.gender === 'female' ? '女声' : '男声'}</Text>
                                  </div>
                                </Option>
                              ))
                            }
                          </OptGroup>

                          <OptGroup label="标准声音">
                            {voices
                              .filter(voice => voice.type === 'standard')
                              .map(voice => (
                                <Option
                                  key={voice.id}
                                  value={voice.id}
                                  label={voice.name}
                                >
                                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                    <span>{voice.name}</span>
                                    <Text type="secondary">{voice.gender === 'female' ? '女声' : '男声'}</Text>
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
                                    <Text type="secondary">自定义声音</Text>
                                  </div>
                                </Option>
                              ))
                            }
                          </OptGroup>
                        </Select>
                      </Col>
                      <Col span={4}>
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
                            value={voiceParams.speed}
                            onChange={val => setVoiceParams({...voiceParams, speed: val})}
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

                    <Row gutter={16}>
                      <Col span={12}>
                        <Form.Item label="情感" required={false}>
                          <Select
                            value={voiceParams.emotion}
                            onChange={val => setVoiceParams({...voiceParams, emotion: val})}
                            style={{ width: '100%' }}
                            disabled={loading}
                          >
                            {availableEmotions.map(emotion => (
                              <Option key={emotion.id} value={emotion.id}>{emotion.name}</Option>
                            ))}
                          </Select>
                        </Form.Item>
                      </Col>
                      <Col span={12}>
                        <Form.Item label="音调" required={false}>
                          <Slider
                            min={-10.0}
                            max={10.0}
                            step={1.0}
                            value={voiceParams.pitch}
                            onChange={val => setVoiceParams({...voiceParams, pitch: val})}
                            disabled={loading}
                            marks={{
                              '-10': '低',
                              '0': '标准',
                              '10': '高'
                            }}
                          />
                        </Form.Item>
                      </Col>
                    </Row>

                    <Row gutter={16}>
                      <Col span={12}>
                        <Form.Item label="能量" required={false}>
                          <Slider
                            min={0.5}
                            max={2.0}
                            step={0.1}
                            value={voiceParams.energy}
                            onChange={val => setVoiceParams({...voiceParams, energy: val})}
                            disabled={loading}
                            marks={{
                              '0.5': '低',
                              '1.0': '标准',
                              '2.0': '高'
                            }}
                          />
                        </Form.Item>
                      </Col>
                      <Col span={12}>
                        <Form.Item label="停顿因子" required={false}>
                          <Slider
                            min={0.5}
                            max={2.0}
                            step={0.1}
                            value={voiceParams.pause_factor}
                            onChange={val => setVoiceParams({...voiceParams, pause_factor: val})}
                            disabled={loading}
                            marks={{
                              '0.5': '短',
                              '1.0': '标准',
                              '2.0': '长'
                            }}
                          />
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
                        onClick={handleStandardSynthesis}
                        disabled={loading || !text || !voiceParams.voice_id}
                        icon={<SoundOutlined />}
                      >
                        开始合成
                      </Button>

                      <Button
                        type="primary"
                        onClick={optimizeVoiceParams}
                        icon={<SettingOutlined />}
                        disabled={loading}
                      >
                        优化参数
                      </Button>
                    </Space>
                  </Form.Item>
                </Form>

                {/* 音频播放器 */}
                {audioUrl && (
                  <div style={{ marginTop: 16 }}>
                    <Card>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                        <div style={{ width: '100%', marginBottom: 16 }}>
                          <Slider
                            value={playbackSliderValue}
                            onChange={handlePlaybackSliderChange}
                            onAfterChange={handlePlaybackSliderAfterChange}
                            disabled={!audioUrl}
                          />
                          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <Text>{formatTime(playbackProgress)}</Text>
                            <Text>{formatTime(audioDuration)}</Text>
                          </div>
                        </div>

                        <div>
                          <Space>
                            <Button
                              icon={<StepBackwardOutlined />}
                              onClick={handleRewind}
                              disabled={!audioUrl}
                            />
                            <Button
                              type="primary"
                              shape="circle"
                              icon={isPlaying ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
                              onClick={toggleStandardPlayback}
                              disabled={!audioUrl}
                              size="large"
                            />
                            <Button
                              icon={<StepForwardOutlined />}
                              onClick={handleFastForward}
                              disabled={!audioUrl}
                            />
                            <Button
                              icon={<DownloadOutlined />}
                              onClick={handleDownload}
                              disabled={!audioUrl}
                            >
                              下载
                            </Button>
                          </Space>
                        </div>
                      </div>

                      <audio
                        ref={audioRef}
                        src={audioUrl}
                        preload="auto"
                        onEnded={() => setIsPlaying(false)}
                        style={{ display: 'none' }}
                      />
                    </Card>
                  </div>
                )}

                {/* 进度条 */}
                {(loading || progress > 0) && (
                  <div style={{ marginTop: 16 }}>
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
              </Card>

              <Card title="课件上传" style={{ marginBottom: 20 }}>
                <Upload {...uploadProps}>
                  <Button icon={<UploadOutlined />} loading={uploading}>
                    上传课件文件
                  </Button>
                </Upload>
                <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
                  支持的文件格式: PPT, PPTX, PDF
                </Text>
              </Card>

              <Card title="课件列表" style={{ marginBottom: 20 }}>
                <div style={{ marginBottom: 16 }}>
                  <Button
                    onClick={fetchCoursewareList}
                    icon={<ReloadOutlined />}
                    loading={loading}
                  >
                    刷新列表
                  </Button>
                </div>

                <Table
                  dataSource={coursewareList}
                  columns={coursewareColumns}
                  rowKey="file_id"
                  loading={loading}
                  pagination={{ pageSize: 5 }}
                />
              </Card>

              <Card title="任务列表">
                <div style={{ marginBottom: 16 }}>
                  <Button
                    onClick={fetchTasksList}
                    icon={<ReloadOutlined />}
                    loading={loading}
                  >
                    刷新列表
                  </Button>
                </div>

                {currentTask && statusPolling && (
                  <div style={{ marginBottom: 16 }}>
                    <Alert
                      message="当前任务正在处理中"
                      description={
                        <div>
                          <Text>任务ID: {currentTask}</Text>
                          <Progress percent={statusProgress} status="active" />
                        </div>
                      }
                      type="info"
                      showIcon
                    />
                  </div>
                )}

                <Table
                  dataSource={tasksList}
                  columns={tasksColumns}
                  rowKey="task_id"
                  loading={loading}
                  pagination={{ pageSize: 5 }}
                />
              </Card>
          </div>

          {debugMode && apiResponse && (
            <Card title="API响应" style={{ marginTop: 20 }}>
              <pre style={{ maxHeight: 300, overflow: 'auto' }}>
                {JSON.stringify(apiResponse, null, 2)}
              </pre>
            </Card>
          )}
        </div>
      </Content>

      <Modal
        title="任务详情"
        open={taskDetailsVisible}
        onCancel={() => setTaskDetailsVisible(false)}
        footer={[
          <Button key="close" onClick={() => setTaskDetailsVisible(false)}>
            关闭
          </Button>
        ]}
        width={700}
      >
        {selectedTaskDetails && (
          <div>
            <Descriptions bordered column={1}>
              <Descriptions.Item label="任务ID">{selectedTaskDetails.task_id}</Descriptions.Item>
              <Descriptions.Item label="课件名称">{selectedTaskDetails.name}</Descriptions.Item>
              <Descriptions.Item label="状态">
                {selectedTaskDetails.status === 'completed' ? (
                  <Tag color="success">已完成</Tag>
                ) : selectedTaskDetails.status === 'processing' ? (
                  <Tag color="processing">处理中</Tag>
                ) : selectedTaskDetails.status === 'failed' ? (
                  <Tag color="error">失败</Tag>
                ) : (
                  <Tag>{selectedTaskDetails.status}</Tag>
                )}
              </Descriptions.Item>
              <Descriptions.Item label="创建时间">{selectedTaskDetails.created_at}</Descriptions.Item>
              <Descriptions.Item label="更新时间">{selectedTaskDetails.updated_at || '-'}</Descriptions.Item>
              {selectedTaskDetails.error && (
                <Descriptions.Item label="错误信息" style={{ color: 'red' }}>
                  {selectedTaskDetails.error}
                </Descriptions.Item>
              )}
              {selectedTaskDetails.file_path && (
                <Descriptions.Item label="文件路径">{selectedTaskDetails.file_path}</Descriptions.Item>
              )}
              {selectedTaskDetails.manifest_path && (
                <Descriptions.Item label="清单文件路径">{selectedTaskDetails.manifest_path}</Descriptions.Item>
              )}
            </Descriptions>

            {/* 显示操作按钮 */}
            {(selectedTaskDetails.status === 'completed' || selectedTaskDetails.status === 'failed') && (
              <div style={{ marginTop: 16 }}>
                <Space>
                  <Button
                    type="primary"
                    icon={<DownloadOutlined />}
                    onClick={() => downloadTaskResult(selectedTaskDetails.task_id)}
                  >
                    下载语音课件
                  </Button>
                  <Button
                    icon={<FileTextOutlined />}
                    onClick={() => downloadManifest(selectedTaskDetails.task_id)}
                  >
                    下载清单文件
                  </Button>
                </Space>
              </div>
            )}

            {/* 显示详细错误信息 */}
            {selectedTaskDetails.error_details && (
              <div style={{ marginTop: 16 }}>
                <Collapse>
                  <Collapse.Panel header="详细错误信息" key="1">
                    <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                      {JSON.stringify(selectedTaskDetails.error_details, null, 2)}
                    </pre>
                  </Collapse.Panel>
                </Collapse>
              </div>
            )}
          </div>
        )}
      </Modal>
    </Layout>
  );
}

export default EnhancedCosyVoicePage;