import React, { useState, useEffect, useRef } from 'react';
import { 
  Typography, Card, Button, Upload, message, Steps, 
  Select, Form, Spin, Row, Col,
  Divider, Space, Progress
} from 'antd';
import { 
  UploadOutlined, AudioOutlined, 
  DownloadOutlined, PlayCircleOutlined, PauseCircleOutlined,
  CheckCircleOutlined, Loading3QuartersOutlined
} from '@ant-design/icons';
import axios from 'axios';

const { Title, Paragraph, Text } = Typography;
const { Step } = Steps;
const { Option } = Select;

const VoiceReplace = () => {
  // State management
  const [form] = Form.useForm();
  const [currentStep, setCurrentStep] = useState(0);
  const [fileId, setFileId] = useState(null);
  const [fileName, setFileName] = useState('');
  const [isVideo, setIsVideo] = useState(false);
  const [loading, setLoading] = useState(false);
  const [processingStatus, setProcessingStatus] = useState(null);
  const [processedVideoUrl, setProcessedVideoUrl] = useState('');
  const [voiceId, setVoiceId] = useState('');
  const [voices, setVoices] = useState([]);
  const [isPlaying, setIsPlaying] = useState(false);
  // 关键修复：添加更合理的最短显示时间和开始时间状态
  const [startTime, setStartTime] = useState(null);
  const [minDisplayTime, setMinDisplayTime] = useState(3000); // 降低为3秒，更合理
  
  // References
  const processingIntervalRef = useRef(null);
  const videoRef = useRef(null);
  
  // Fetch available voices on component mount
  useEffect(() => {
    fetchVoices();
    
    // Cleanup function
    return () => {
      if (processingIntervalRef.current) {
        clearInterval(processingIntervalRef.current);
      }
    };
  }, []);

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

  // Voice selection handler
  const handleVoiceChange = (selectedVoiceId) => {
    setVoiceId(selectedVoiceId);
    
    // Log selected voice details
    const selectedVoice = voices.find(v => v.id === selectedVoiceId);
    if (selectedVoice) {
      console.log(`已选择声音: ${selectedVoice.name}, 类型: ${selectedVoice.type}`);
    }
  };

  // File upload handler
  const handleFileUpload = async (info) => {
    if (info.file.status === 'uploading') {
      setLoading(true);
      return;
    }
    
    if (info.file.status === 'done') {
      setLoading(false);
      message.success(`${info.file.name} 上传成功`);
      
      // Save file ID and name
      setFileId(info.file.response.file_id);
      setFileName(info.file.name);
      
    } else if (info.file.status === 'error') {
      setLoading(false);
      const errorMsg = info.file.response?.detail?.error || 
                      info.file.response?.detail?.message || 
                      '服务器错误';
      message.error(`${info.file.name} 上传失败: ${errorMsg}`);
    }
  };

  // File upload validation
  const beforeUpload = (file) => {
    const isAudioVideo = file.type.startsWith('audio/') || file.type.startsWith('video/');
    if (!isAudioVideo) {
      message.error('只能上传音频或视频文件!');
      return false;
    }
  
    const isLt100M = file.size / 1024 / 1024 < 100;
    if (!isLt100M) {
      message.error('文件必须小于100MB!');
      return false;
    }
  
    // Show upload progress
    message.info(`${file.name} 开始上传...`);
  
    // Set whether it's a video
    setIsVideo(file.type.startsWith('video/'));
  
    return true;
  };

  // Start processing video with selected voice - 修复
  const startProcessing = async () => {
    if (!fileId) {
      message.error('请先上传文件');
      return;
    }
    
    if (!voiceId) {
      message.error('请选择声音');
      return;
    }
    
    setLoading(true);
    
    // 设置开始时间
    const processStartTime = Date.now();
    setStartTime(processStartTime);
    
    // 设置初始处理状态
    setProcessingStatus({
      status: 'processing',
      progress: 0
    });
    
    try {
      // 移动到下一步
      setCurrentStep(1);
      
      // 开始进度条动画
      startProcessingStatusCheck();
      
      // 准备表单数据
      const formData = new FormData();
      formData.append('voice_id', voiceId);
      
      // 提交处理请求
      const response = await axios.post('/api/replace/process', formData, {
        params: { file: fileId }
      });
      
      // 如果API立即返回处理后的视频URL
      if (response.data && response.data.processed_video_url) {
        // 保存视频URL
        setProcessedVideoUrl(response.data.processed_video_url);
        console.log('API立即返回了结果');
      }
    } catch (error) {
      console.error('处理视频失败:', error);
      message.error('处理视频失败，请重试');
      
      // 清除进度条
      clearProcessingInterval();
      
      setProcessingStatus({
        status: 'failed',
        progress: 0
      });
    } finally {
      setLoading(false);
    }
  };

  // 关键修复：添加清除处理间隔的辅助函数，确保一致性
  const clearProcessingInterval = () => {
    if (processingIntervalRef.current) {
      clearInterval(processingIntervalRef.current);
      processingIntervalRef.current = null;
    }
  };

  // 检查处理状态与假进度 - 修复版本
  const startProcessingStatusCheck = () => {
    // 清除之前的间隔
    clearProcessingInterval();
    
    // 获取当前时间以跟踪经过的时间
    const processStartTime = startTime || Date.now();
    
    // 目标持续时间 - 15秒（更现实的估计值）
    const targetDuration = 15000; // 15秒
    
    // 启动更新进度条
    processingIntervalRef.current = setInterval(() => {
      try {
        // 计算经过的时间
        const elapsedTime = Date.now() - processStartTime;
        
        // 计算基于经过时间的进度（0-99%）
        // 使用更平滑的曲线
        const progressPercent = Math.min(99, (elapsedTime / targetDuration) * 100);
        const smoothProgress = Math.min(99, Math.pow(progressPercent / 10, 1.05) * 10);
        
        // 更新状态
        setProcessingStatus(prevStatus => ({
          status: 'processing',
          progress: smoothProgress
        }));
        
        // 调试日志
        if (process.env.NODE_ENV === 'development') {
          console.log(`进度: ${smoothProgress.toFixed(1)}%, 已用时间: ${(elapsedTime/1000).toFixed(1)}s`);
        }
        
        // 如果已有处理后的视频URL
        if (processedVideoUrl) {
          // 如果最小显示时间已经过去
          if (elapsedTime >= minDisplayTime) {
            console.log('已有处理结果且已显示足够时间，完成处理');
            
            // 清除进度条定时器
            clearProcessingInterval();
            
            // 设置状态为已完成，进度为100%
            setProcessingStatus({
              status: 'completed',
              progress: 100
            });
            // 删除 message.success 调用
            // message.success('视频处理完成');
          }
          // 否则继续显示进度条直到最小时间过去
        }
        // 如果目标持续时间已过，切换到实时查询
        else if (elapsedTime >= targetDuration) {
          console.log('切换到实时查询模式');
          
          // 清除进度条定时器
          clearProcessingInterval();
          
          // 保持进度在99%
          setProcessingStatus(prevStatus => ({
            status: 'processing',
            progress: 99
          }));
          
          // 每秒开始查询状态
          processingIntervalRef.current = setInterval(() => {
            fetchProcessedVideo();
          }, 1000);
        }
      } catch (error) {
        // 捕获间隔中的任何错误以防止崩溃
        console.error('Progress update error:', error);
        clearProcessingInterval();
      }
    }, 200); // 每200毫秒更新一次，以获得平滑动画
  };

  // 获取处理后的视频URL - 修复
  const fetchProcessedVideo = async () => {
    try {
        // 如果我们已经有视频URL，检查是否过了最小显示时间
        if (processedVideoUrl) {
            const currentTime = Date.now();
            const processStartTime = startTime || currentTime;
            const elapsedTime = currentTime - processStartTime;
            
            // 如果最小显示时间已经过去，标记为已完成
            if (elapsedTime >= minDisplayTime) {
                // 设置状态为已完成，进度为100%
                setProcessingStatus({
                    status: 'completed',
                    progress: 100
                });
                
                message.success('视频处理完成');
                
                // 清除定时器
                clearProcessingInterval();
            }
            return;
        }
        
        // 否则从服务器获取状态
        const response = await axios.get(`/api/replace/status/${fileId}`);
        
        // 关键修复：更明确的条件检查
        if (response.data && response.data.processed_video_url) {
            // 保存视频URL
            setProcessedVideoUrl(response.data.processed_video_url);
            console.log('已获取到视频URL:', response.data.processed_video_url);
            
            // 检查是否过了最小显示时间
            const currentTime = Date.now();
            const processStartTime = startTime || currentTime;
            const elapsedTime = currentTime - processStartTime;
            
            // 只有在最小时间过去后才标记为完成
            if (elapsedTime >= minDisplayTime) {
                setProcessingStatus({
                    status: 'completed',
                    progress: 100
                });
                
                message.success('视频处理完成');
                
                // 清除定时器
                clearProcessingInterval();
            } else {
                // 如果没过最小时间，继续更新进度
                // 进度设为99%，等待最小显示时间
                setProcessingStatus({
                    status: 'processing',
                    progress: 99
                });
                
                // 设置一个新的定时器检查最小显示时间
                const remainingTime = minDisplayTime - elapsedTime;
                console.log(`等待最短显示时间，剩余${remainingTime}ms`);
                
                // 清除旧定时器，设置新的一次性定时器
                clearProcessingInterval();
                
                setTimeout(() => {
                    setProcessingStatus({
                        status: 'completed',
                        progress: 100
                    });
                    // 删除 message.success 调用
                    // message.success('视频处理完成');
                }, remainingTime);
            }
        } else if (response.data && response.data.status === 'processing') {
            // 继续等待，保持进度在99%
            setProcessingStatus(prevStatus => ({
                status: 'processing',
                progress: 99
            }));
        } else if (response.data && response.data.status === 'failed') {
            // 处理明确的失败状态
            throw new Error(response.data.message || '处理失败');
        } else {
            // 没有获取到预期的响应
            console.warn('获取状态响应不完整:', response.data);
        }
    } catch (error) {
        console.error('获取处理后视频失败:', error);
        message.error('获取处理后视频失败');
        
        // 清除定时器
        clearProcessingInterval();
        
        setProcessingStatus({
            status: 'failed',
            progress: 0
        });
    }
};

  // Download processed video
  const downloadProcessedVideo = () => {
    if (!processedVideoUrl) {
      message.error('没有可下载的视频');
      return;
    }
    
    const link = document.createElement('a');
    link.href = processedVideoUrl;
    link.setAttribute('download', `${fileName.split('.')[0]}_processed.mp4`);
    document.body.appendChild(link);
    link.click();
    link.parentNode.removeChild(link);
  };

  // Play/pause video preview
  const toggleVideoPlay = () => {
    if (!videoRef.current) return;
    
    if (isPlaying) {
      videoRef.current.pause();
    } else {
      videoRef.current.play();
    }
    
    setIsPlaying(!isPlaying);
  };

  // Reset to start over
  const handleReset = () => {
    setCurrentStep(0);
    setFileId(null);
    setFileName('');
    setIsVideo(false);
    setProcessingStatus(null);
    setProcessedVideoUrl('');
    setStartTime(null);
    
    clearProcessingInterval();
  };

  // Render step content - 修复后的安全条件检查
  const renderStepContent = () => {
    switch (currentStep) {
      case 0:
        return (
          <Card title="上传和设置" bordered={false}>
            <div style={{ padding: '20px 0' }}>
              <Row gutter={24}>
                <Col span={12}>
                  <Upload
                    name="file"
                    action="/api/replace/upload"
                    beforeUpload={beforeUpload}
                    onChange={handleFileUpload}
                    maxCount={1}
                    showUploadList={true}
                    data={{ name: 'media' }}
                  >
                    <Button icon={<UploadOutlined />} loading={loading}>
                      选择视频文件
                    </Button>
                    <div style={{ marginTop: 8 }}>
                      支持常见视频(MP4, AVI)格式，大小不超过100MB
                    </div>
                  </Upload>
                </Col>
                
                <Col span={12}>
                  <Form layout="vertical">
                    <Form.Item
                      label="选择声音"
                      required
                      tooltip="选择要替换的目标声音"
                    >
                      <Select
                        value={voiceId}
                        onChange={handleVoiceChange}
                        placeholder="请选择声音"
                        style={{ width: '100%' }}
                      >
                        {voices.map(voice => (
                          <Option key={voice.id} value={voice.id}>
                            {voice.name}
                          </Option>
                        ))}
                      </Select>
                    </Form.Item>
                  </Form>
                </Col>
              </Row>
              
              <Divider />
              
              <div style={{ textAlign: 'center', marginTop: 24 }}>
                <Button
                  type="primary"
                  size="large"
                  onClick={startProcessing}
                  loading={loading}
                  disabled={!fileId || !voiceId}
                >
                  开始处理
                </Button>
              </div>
            </div>
          </Card>
        );
      
      case 1:
        return (
          <Card title="处理结果" bordered={false}>
            <div style={{ textAlign: 'center', padding: '20px 0' }}>
              {/* 修复：更安全和明确的条件判断 */}
              {processingStatus && processingStatus.status === 'processing' ? (
                <div>
                  <Spin tip="正在处理中..." />
                  <div style={{ marginTop: 24 }}>
                    <Progress
                      key={`progress-${processingStatus.progress || 0}`}
                      percent={Math.round(processingStatus.progress || 0)}
                      status="active"
                      style={{ maxWidth: '80%', margin: '0 auto' }}
                    />
                    <div style={{ marginTop: 12, color: '#666' }}>
                      {/* 更新可能的处理时间 */}
                      预计处理时间：15-30秒
                    </div>
                  </div>
                </div>
              ) : processingStatus && processingStatus.status === 'completed' ? (
                <div>
                  <div style={{ marginBottom: 24 }}>
                    <CheckCircleOutlined style={{ fontSize: 48, color: '#52c41a' }} />
                    <Title level={4} style={{ marginTop: 16 }}>声音替换成功！</Title>
                  </div>
                  
                  <div style={{ marginBottom: 24 }}>
                    {processedVideoUrl && (
                      <div style={{ maxWidth: '640px', margin: '0 auto' }}>
                        <div style={{ marginBottom: 16 }}>
                          <Title level={5}>视频预览</Title>
                        </div>
                        <video
                          ref={videoRef}
                          src={processedVideoUrl}
                          controls
                          width="100%"
                          onPlay={() => setIsPlaying(true)}
                          onPause={() => setIsPlaying(false)}
                        />
                        <div style={{ marginTop: 16, marginBottom: 24 }}>
                          <Space>
                            <Button
                              type="primary"
                              icon={isPlaying ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
                              onClick={toggleVideoPlay}
                            >
                              {isPlaying ? '暂停' : '播放'}
                            </Button>
                          </Space>
                        </div>
                      </div>
                    )}
                  </div>
                  
                  <Space size="large">
                    <Button 
                      type="primary" 
                      icon={<DownloadOutlined />}
                      onClick={downloadProcessedVideo}
                    >
                      下载结果
                    </Button>
                    <Button onClick={handleReset}>重新开始</Button>
                  </Space>
                </div>
              ) : processingStatus && processingStatus.status === 'failed' ? (
                <div>
                  <div style={{ marginBottom: 24, color: '#f5222d' }}>
                    <Title level={4}>处理失败</Title>
                    <Text type="danger">请重试或联系管理员</Text>
                  </div>
                  <Button onClick={handleReset}>重新开始</Button>
                </div>
              ) : (
                <div>
                  <Loading3QuartersOutlined style={{ fontSize: 24, color: '#1890ff' }} spin />
                  <div style={{ marginTop: 8 }}>
                    <Text>准备中...</Text>
                  </div>
                  <div style={{ marginTop: 24 }}>
                    <Progress
                      percent={0}
                      status="active"
                      style={{ maxWidth: '80%', margin: '0 auto' }}
                    />
                  </div>
                </div>
              )}
            </div>
          </Card>
        );
      
      default:
        return (
          <Card>
            <div style={{ textAlign: 'center', padding: '20px 0' }}>
              <Button onClick={() => setCurrentStep(0)}>返回上传页面</Button>
            </div>
          </Card>
        );
    }
  };

  // 调试效果 - 保留用于故障排除
  useEffect(() => {
    // 在开发环境中记录状态更改
    if (process.env.NODE_ENV === 'development') {
      console.log('当前步骤:', currentStep);
      console.log('处理状态:', processingStatus);
      if (processedVideoUrl) {
        console.log('已获取视频URL:', processedVideoUrl.slice(0, 50) + '...');
      }
    }
  }, [currentStep, processingStatus, processedVideoUrl]);

  // 错误边界包装整个组件
  try {
    return (
      <div className="voice-replace">
        <div className="page-header">
          <Title level={2}>声音置换与字幕</Title>
          <Paragraph>
            替换音视频中的声音，生成同步字幕。
            上传音频或视频文件，选择新声音，系统将自动处理并生成结果。
          </Paragraph>
        </div>

        <Card bordered={false}>
          <Steps current={currentStep} className="replace-steps">
            <Step title="上传文件" description="选择文件与声音" />
            <Step title="处理结果" description="查看和下载" />
          </Steps>
          
          <div className="step-content" style={{ marginTop: 32 }}>
            {renderStepContent()}
          </div>
        </Card>
        
        {/* 应用场景 */}
        <Card title="应用场景" style={{ marginTop: 16 }} bordered={false}>
          <Row gutter={[16, 16]}>
            <Col xs={24} md={8}>
              <Card title="教学视频更新" size="small" bordered>
                <Paragraph>
                  更新已有教学视频的语音讲解，改进发音、语调或替换为新教师的声音，
                  无需重新拍摄视频，大大节省内容更新成本。
                </Paragraph>
              </Card>
            </Col>
            <Col xs={24} md={8}>
              <Card title="多语言教学" size="small" bordered>
                <Paragraph>
                  将教学内容转换为不同语言版本，保留原始视频的同时提供多语言讲解，
                  扩大教育资源的适用范围，促进教育国际化。
                </Paragraph>
              </Card>
            </Col>
            <Col xs={24} md={8}>
              <Card title="课程无障碍化" size="small" bordered>
                <Paragraph>
                  为教学视频添加清晰的字幕，帮助听障学生学习，
                  同时提供标准化的语音输出，确保教学内容的清晰传达。
                </Paragraph>
              </Card>
            </Col>
          </Row>
        </Card>
      </div>
    );
  } catch (error) {
    // 基本错误边界
    console.error("VoiceReplace rendering error:", error);
    return (
      <div className="error-fallback" style={{ padding: '20px', textAlign: 'center' }}>
        <Title level={3}>页面加载失败</Title>
        <Paragraph type="danger">发生了一个错误，请刷新页面重试</Paragraph>
        <Button type="primary" onClick={() => window.location.reload()}>
          刷新页面
        </Button>
      </div>
    );
  }
};

export default VoiceReplace;