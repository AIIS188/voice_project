import React, { useState, useEffect, useRef } from 'react';
import { 
  Typography, Card, Button, Table, Tag, Space, 
  Upload, Modal, Form, Input, message, Progress, 
  Tabs, Tooltip
} from 'antd';
import { 
  UploadOutlined, AudioOutlined, PlusOutlined, 
  DeleteOutlined, PlayCircleOutlined, PauseCircleOutlined,
  InfoCircleOutlined
} from '@ant-design/icons';
import axios from 'axios';

const { Title, Paragraph, Text } = Typography;
const { TabPane } = Tabs;

const EnhancedVoiceLibrary = () => {
  // State management
  const [voices, setVoices] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploadModalVisible, setUploadModalVisible] = useState(false);
  const [recordModalVisible, setRecordModalVisible] = useState(false);
  const [playingId, setPlayingId] = useState(null);
  const [recordingStatus, setRecordingStatus] = useState('inactive'); // inactive, recording, paused
  const [recordingTime, setRecordingTime] = useState(0);
  const [recordedAudio, setRecordedAudio] = useState(null);
  const [uploadedFile, setUploadedFile] = useState(null);
  
  // Recording references
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const timerRef = useRef(null);
  
  // Form reference
  const [form] = Form.useForm();
  
  // Load voice data
  const fetchVoices = async () => {
    setLoading(true);
    try {
      const response = await axios.get('/api/voice/list');
      setVoices(response.data.items);
    } catch (error) {
      console.error('获取声音库失败:', error);
      message.error('获取声音库失败，请稍后重试');
      setVoices([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchVoices();
  }, []);

  // 从预览URL中提取文件名
  const getPreviewFilename = (previewUrl) => {
    if (!previewUrl) return null;
    // 从URL路径中提取最后一部分作为文件名
    const parts = previewUrl.split('/');
    return parts[parts.length - 1];
  };
  
  // 构建直接预览URL
  const getDirectPreviewUrl = (previewUrl) => {
    if (!previewUrl) return null;
    
    const filename = getPreviewFilename(previewUrl);
    if (!filename) return previewUrl;
    
    // 使用直接预览端点
    return `/api/voice/direct-preview/${encodeURIComponent(filename)}`;
  };
  
  // 从预览URL中提取语音ID
  const getVoiceIdFromPreviewUrl = (previewUrl) => {
    if (!previewUrl) return null;
    
    // 从URL路径中提取最后一部分
    const parts = previewUrl.split('/');
    const lastPart = parts[parts.length - 1];
    
    // 如果是标准格式 "voice_id_preview.wav"，去掉 "_preview.wav" 后缀
    if (lastPart.endsWith('_preview.wav')) {
      return lastPart.substring(0, lastPart.length - 12); // 移除 "_preview.wav"
    }
    
    // 如果格式不是标准格式，则返回整个最后部分
    return lastPart;
  };

  // 修改播放音频函数
  const playVoicePreview = (id, previewUrl) => {
    console.log(`尝试播放音频: ${id}, 原始URL: ${previewUrl}`);
    
    // 获取直接预览URL
    const directUrl = getDirectPreviewUrl(previewUrl);
    console.log(`直接预览URL: ${directUrl}`);
    
    if (playingId === id) {
      // 如果点击的是当前正在播放的音频，则暂停
      setPlayingId(null);
      const audio = document.getElementById(`audio-${id}`);
      if (audio) {
        audio.pause();
        console.log(`已暂停音频: ${id}`);
      }
    } else {
      // 确保有可用的预览URL
      if (!directUrl) {
        message.error('预览音频不可用');
        console.error('没有可用的预览URL');
        return;
      }
      
      // 首先停止任何当前正在播放的音频
      if (playingId) {
        const currentlyPlaying = document.getElementById(`audio-${playingId}`);
        if (currentlyPlaying) {
          currentlyPlaying.pause();
          console.log(`停止之前播放的音频: ${playingId}`);
        }
      }
      
      // 设置播放状态
      setPlayingId(id);
      console.log(`设置当前播放ID为: ${id}`);
      
      // 尝试使用更可靠的方式直接播放音频
      try {
        // 创建新的音频元素
        const audio = new Audio();
        audio.id = `audio-${id}`;
        
        // 添加调试信息事件监听
        audio.addEventListener('loadstart', () => console.log(`音频开始加载: ${id}`));
        audio.addEventListener('canplay', () => console.log(`音频可以播放: ${id}`));
        audio.addEventListener('playing', () => console.log(`音频正在播放: ${id}`));
        
        // 错误处理
        audio.addEventListener('error', (e) => {
          console.error(`音频错误 (${id}):`, e);
          console.error(`错误代码: ${audio.error ? audio.error.code : '未知'}`);
          message.error(`音频播放失败 (错误码: ${audio.error ? audio.error.code : '未知'})`);
          setPlayingId(null);
        });
        
        // 播放结束处理
        audio.addEventListener('ended', () => {
          console.log(`音频播放结束: ${id}`);
          setPlayingId(null);
        });
        
        // 添加防缓存参数以避免缓存问题
        const cacheBuster = new Date().getTime();
        audio.src = `${directUrl}?v=${cacheBuster}`;
        
        console.log(`开始播放: ${id}, 源: ${audio.src}`);
        
        // 开始播放
        const playPromise = audio.play();
        
        if (playPromise !== undefined) {
          playPromise.catch(error => {
            console.error(`播放承诺错误 (${id}):`, error);
            message.error(`音频播放失败: ${error.message}`);
            setPlayingId(null);
          });
        }
        
        // 将音频元素存储在文档中，以便稍后可能需要暂停
        document.body.appendChild(audio);
        
      } catch (error) {
        console.error(`播放音频时发生一般错误 (${id}):`, error);
        message.error(`音频播放失败: ${error.message}`);
        setPlayingId(null);
      }
    }
  };
  
  // Updated render code for the action column in the table
  const renderActionColumn = (_, record) => (
    <Space size="middle">
      <Button 
        type="text" 
        icon={playingId === record.id ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
        onClick={() => playVoicePreview(record.id, record.preview_url)}
        disabled={!record.preview_url}
      >
        {playingId === record.id ? '暂停' : '播放'}
      </Button>
      
      {record.type === 'user-uploaded' && (
        <Button 
          type="text" 
          danger
          icon={<DeleteOutlined />}
          onClick={() => deleteVoice(record.id)}
        >
          删除
        </Button>
      )}
    </Space>
  );
  
  // Delete voice
  const deleteVoice = async (id) => {
    // Confirm deletion
    Modal.confirm({
      title: '确认删除',
      content: '删除后无法恢复，确认要删除这个声音吗？',
      okText: '确认',
      cancelText: '取消',
      onOk: async () => {
        try {
          await axios.delete(`/api/voice/${id}`);
          message.success('删除成功');
          fetchVoices();
        } catch (error) {
          console.error('删除失败:', error);
          message.error('删除失败，请稍后重试');
        }
      }
    });
  };

  // 处理文件上传变更 - 增强版本以适应不同的文件结构
  const handleFileChange = (info) => {
    console.log('文件上传状态变更:', info);
    
    // 处理文件移除情况
    if (info.file && info.file.status === 'removed') {
      setUploadedFile(null);
      return;
    }
    
    // 处理各种可能的文件对象结构
    let fileObj = null;
    
    // 情况1: 标准的 Ant Design 结构
    if (info.file && info.file.originFileObj) {
      fileObj = info.file.originFileObj;
      console.log('找到标准文件对象:', info.file.originFileObj);
    } 
    // 情况2: 已经有文件名的完整信息但不在标准位置
    else if (info.file && info.file.name && (info.file instanceof File || info.file.type)) {
      fileObj = info.file;
      console.log('找到非标准文件对象:', info.file);
    }
    // 情况3: 文件列表中的第一个文件
    else if (info.fileList && info.fileList.length > 0) {
      const firstFile = info.fileList[0];
      if (firstFile.originFileObj) {
        fileObj = firstFile.originFileObj;
        console.log('从文件列表找到文件对象:', firstFile.originFileObj);
      } else if (firstFile instanceof File || (firstFile.name && firstFile.type)) {
        fileObj = firstFile;
        console.log('从文件列表找到非标准文件对象:', firstFile);
      }
    }
    
    // 特殊情况: 从截图看到文件已经被选中但不在标准结构中
    if (!fileObj && info.file && info.file.name) {
      console.log('检测到仅有文件名的情况:', info.file.name);
      
      // 创建一个自定义文件对象来处理这种情况
      // 这里我们使用文件名并假设内容稍后会从DOM获取
      const fileName = info.file.name;
      
      // 尝试从页面上获取实际的上传控件
      const uploadInputs = document.querySelectorAll('input[type="file"]');
      for (let input of uploadInputs) {
        if (input.files && input.files.length > 0) {
          console.log('找到包含文件的input元素:', input.files[0].name);
          if (input.files[0].name === fileName) {
            fileObj = input.files[0];
            console.log('从DOM中找到匹配的文件:', fileObj);
            break;
          }
        }
      }
      
      // 如果还是找不到，创建一个标记对象
      if (!fileObj) {
        console.log('无法找到实际文件对象，但文件名已知:', fileName);
        // 使用文件名作为标识符
        setUploadedFile({ 
          isCustom: true, 
          name: fileName,
          type: fileName.endsWith('.wav') ? 'audio/wav' : 
                fileName.endsWith('.mp3') ? 'audio/mp3' : 'audio/mpeg',
          _domSelector: true  // 标记稍后从DOM获取
        });
        return;
      }
    }
    
    if (fileObj) {
      console.log('已设置上传文件:', fileObj.name, fileObj.size, fileObj.type);
      setUploadedFile(fileObj);
    } else {
      console.warn('无法从上传事件中提取文件对象:', info);
    }
  };

  // 修改上传声音函数
  const uploadVoice = async (values) => {
    try {
      console.log('上传表单数据:', values);
      
      // 检查文件是否已上传 - 更宽松的检查
      let actualFile = uploadedFile;
      
      // 如果没有文件对象但UI中显示有文件
      if (!actualFile || actualFile._domSelector) {
        console.log('尝试从DOM获取文件...');
        // 尝试再次从页面获取
        const uploadInputs = document.querySelectorAll('input[type="file"]');
        for (let input of uploadInputs) {
          if (input.files && input.files.length > 0) {
            console.log('找到包含文件的input元素:', input.files[0].name);
            actualFile = input.files[0];
            console.log('从DOM中找到文件:', actualFile.name, actualFile.size);
            break;
          }
        }
      }
      
      // 最终检查是否有文件
      if (!actualFile || (actualFile._domSelector && !actualFile.size)) {
        // 特殊情况：如果UI显示有文件，但我们无法获取它
        // 我们可以尝试强制提交表单而不使用JS获取文件
        console.log('检测到特殊情况：UI有文件但JS无法获取');
        
        // 查找表单并尝试原生提交
        const uploadForm = document.querySelector('form');
        if (uploadForm) {
          console.log('找到表单，尝试原生提交');
          // 创建隐藏的字段来传递其他数据
          const nameInput = document.createElement('input');
          nameInput.type = 'hidden';
          nameInput.name = 'name';
          nameInput.value = values.name;
          uploadForm.appendChild(nameInput);
          
          const descInput = document.createElement('input');
          descInput.type = 'hidden';
          descInput.name = 'description';
          descInput.value = values.description || '';
          uploadForm.appendChild(descInput);
          
          const tagsInput = document.createElement('input');
          tagsInput.type = 'hidden';
          tagsInput.name = 'tags';
          tagsInput.value = values.tags || '';
          uploadForm.appendChild(tagsInput);
          
          const refTextInput = document.createElement('input');
          refTextInput.type = 'hidden';
          refTextInput.name = 'reference_text';
          refTextInput.value = values.reference_text || '';
          uploadForm.appendChild(refTextInput);
          
          // 设置表单属性
          uploadForm.method = 'post';
          uploadForm.action = '/api/voice/upload';
          uploadForm.enctype = 'multipart/form-data';
          
          // 提交表单
          const uploadingMsg = message.loading('正在上传声音文件...', 0);
          
          try {
            uploadForm.submit();
            // 注意：表单提交会导航离开页面，所以以下代码可能不会执行
            setTimeout(() => {
              uploadingMsg();
              message.success('提交成功');
              setUploadModalVisible(false);
              form.resetFields();
              setUploadedFile(null);
            }, 2000);
          } catch (e) {
            uploadingMsg();
            console.error('表单提交失败:', e);
            message.error('表单提交失败');
          }
          return;
        }
        
        message.warning('无法获取音频文件，请重新选择');
        return;
      }
      
      console.log('准备上传文件:', actualFile.name, actualFile.size, actualFile.type);

      // 准备FormData
      const formData = new FormData();
      formData.append('file', actualFile);
      formData.append('name', values.name);
      formData.append('description', values.description || '');
      formData.append('tags', values.tags || '');
      formData.append('reference_text', values.reference_text || '');

      // 显示上传中状态
      const uploadingMsg = message.loading('正在上传声音文件...', 0);

      // 发送请求
      console.log('发送上传请求...');
      const response = await axios.post('/api/voice/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 90000, // 延长超时时间到90秒
      });

      // 关闭上传中消息
      uploadingMsg();

      console.log('上传响应:', response.data);
      
      if (response && response.data && response.data.success) {
        message.success('上传成功');
        setUploadModalVisible(false);
        form.resetFields();
        setUploadedFile(null);
        fetchVoices();
      } else {
        throw new Error(response.data?.message || '上传失败，服务器返回未知错误');
      }
    } catch (error) {
      console.error('上传失败:', error);
      message.error(`上传失败: ${error.message || '未知错误'}`);
    }
  };

  // Start recording
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      audioChunksRef.current = [];
      
      mediaRecorderRef.current.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };
      
      mediaRecorderRef.current.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
        const audioUrl = URL.createObjectURL(audioBlob);
        setRecordedAudio({ blob: audioBlob, url: audioUrl });
      };
      
      mediaRecorderRef.current.start();
      setRecordingStatus('recording');
      
      // Start timer
      timerRef.current = setInterval(() => {
        setRecordingTime(prev => prev + 1);
      }, 1000);
    } catch (error) {
      console.error('录音失败:', error);
      message.error('无法访问麦克风，请检查设备权限');
    }
  };

  // Pause recording
  const pauseRecording = () => {
    if (mediaRecorderRef.current && recordingStatus === 'recording') {
      mediaRecorderRef.current.pause();
      setRecordingStatus('paused');
      clearInterval(timerRef.current);
    }
  };

  // Resume recording
  const resumeRecording = () => {
    if (mediaRecorderRef.current && recordingStatus === 'paused') {
      mediaRecorderRef.current.resume();
      setRecordingStatus('recording');
      
      // Resume timer
      timerRef.current = setInterval(() => {
        setRecordingTime(prev => prev + 1);
      }, 1000);
    }
  };

  // Stop recording
  const stopRecording = () => {
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream.getTracks().forEach(track => track.stop());
      setRecordingStatus('inactive');
      clearInterval(timerRef.current);
    }
  };

  // Save recording
  const saveRecording = async (values) => {
    if (!recordedAudio) {
      message.error('请先录制声音');
      return;
    }
    
    const { name, description, tags, reference_text } = values;
    
    const formData = new FormData();
    formData.append('file', new File([recordedAudio.blob], `${name}.wav`, { type: 'audio/wav' }));
    formData.append('name', name);
    formData.append('description', description || '');
    formData.append('tags', tags || '');
    formData.append('reference_text', reference_text || '');
    
    try {
      await axios.post('/api/voice/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      
      message.success('保存成功');
      setRecordModalVisible(false);
      resetRecording();
      form.resetFields();
      fetchVoices();
    } catch (error) {
      console.error('保存失败:', error);
      message.error('保存失败，请稍后重试');
    }
  };

  // Reset recording
  const resetRecording = () => {
    setRecordingStatus('inactive');
    setRecordingTime(0);
    setRecordedAudio(null);
    clearInterval(timerRef.current);
    if (mediaRecorderRef.current && mediaRecorderRef.current.stream) {
      mediaRecorderRef.current.stream.getTracks().forEach(track => track.stop());
    }
  };

  // Close recording modal
  const handleRecordModalCancel = () => {
    resetRecording();
    setRecordModalVisible(false);
  };

  // Format recording time
  const formatRecordTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // Check if recording length is valid
  const isValidRecordingLength = () => {
    return recordingTime >= 5 && recordingTime <= 30;
  };



  // Table columns
  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      render: (type) => {
        let color = 'green';
        let text = '预训练';
        
        if (type === 'user-uploaded') {
          color = 'blue';
          text = '用户上传';
        }
        
        return <Tag color={color}>{text}</Tag>;
      },
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '标签',
      dataIndex: 'tags',
      key: 'tags',
      render: (tags) => (
        <>
          {tags && tags.map((tag) => (
            <Tag key={tag}>{tag}</Tag>
          ))}
        </>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status) => {
        let color = 'default';
        let text = '未知';
        
        if (status === 'ready') {
          color = 'success';
          text = '可用';
        } else if (status === 'processing') {
          color = 'processing';
          text = '处理中';
        } else if (status === 'failed') {
          color = 'error';
          text = '失败';
        }
        
        return <Tag color={color}>{text}</Tag>;
      },
    },
    {
      title: '操作',
      key: 'action',
      render: renderActionColumn,
    },
  ];

  return (
    <div className="voice-library">
      <div className="page-header">
        <Title level={2}>声音库</Title>
        <Paragraph>
          管理声音，可以使用预训练声音，或者上传、录制自己的声音。
          每个声音需要5-30秒长度，系统会自动提取声音特征用于合成。
        </Paragraph>
      </div>

      {/* Action buttons */}
      <div style={{ marginBottom: 16 }}>
        <Space>
          <Button 
            type="primary" 
            icon={<UploadOutlined />}
            onClick={() => {
              setUploadModalVisible(true);
              // 重置上传状态
              setUploadedFile(null);
              form.resetFields();
            }}
          >
            上传声音
          </Button>
          <Button 
            icon={<AudioOutlined />}
            onClick={() => setRecordModalVisible(true)}
          >
            录制声音
          </Button>

        </Space>
      </div>

      {/* Voice list */}
      <Tabs defaultActiveKey="1">
        <TabPane tab="预训练声音" key="1">
          <Table 
            columns={columns} 
            dataSource={voices.filter(v => v.type === 'pretrained')}
            rowKey="id"
            loading={loading}
          />
        </TabPane>
        <TabPane tab="我的声音" key="2">
          <Table 
            columns={columns} 
            dataSource={voices.filter(v => v.type === 'user-uploaded')}
            rowKey="id"
            loading={loading}
          />
        </TabPane>
      </Tabs>

      {/* 上传声音模态框 */}
      <Modal
        title="上传声音"
        open={uploadModalVisible}
        onCancel={() => {
          setUploadModalVisible(false);
          form.resetFields();
          setUploadedFile(null);
        }}
        footer={null}
        destroyOnClose={true}
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{ description: '', tags: '' }}
          onFinish={(values) => {
            console.log("表单提交值:", values);
            uploadVoice(values);
          }}
        >
          <Form.Item
            name="name"
            label="名称"
            rules={[{ required: true, message: '请输入声音名称' }]}
          >
            <Input placeholder="例如：教师男声1" />
          </Form.Item>
          
          <Form.Item
            name="description"
            label="描述"
          >
            <Input.TextArea placeholder="对声音的描述" />
          </Form.Item>
          
          <Form.Item
            name="tags"
            label="标签"
          >
            <Input placeholder="用逗号分隔，例如：男声,清晰,教学" />
          </Form.Item>
          
          <Form.Item
            name="reference_text"
            label={
              <span>
                参考文本
                <Tooltip title="请输入上传音频中说的文字内容，用于声音复制">
                  <InfoCircleOutlined style={{ marginLeft: 8 }} />
                </Tooltip>
              </span>
            }
            rules={[{ required: true, message: '请输入参考文本' }]}
          >
            <Input.TextArea 
              placeholder="请输入该音频中说的文字内容" 
              rows={3}
            />
          </Form.Item>
          
          {/* 简化的文件上传组件 */}
          <Form.Item
            label="音频文件"
            required
            tooltip="支持WAV、MP3格式，5-30秒，小于10MB"
          >
            <Upload
              accept="audio/*"
              maxCount={1}
              listType="text"
              beforeUpload={(file) => {
                // 检查文件类型
                const isAudio = file.type.startsWith('audio/');
                if (!isAudio) {
                  message.error('请上传音频文件!');
                  return Upload.LIST_IGNORE;
                }
                
                // 检查文件大小
                const isLt10M = file.size / 1024 / 1024 < 10;
                if (!isLt10M) {
                  message.error('文件必须小于10MB!');
                  return Upload.LIST_IGNORE;
                }
                
                // 返回 false 阻止自动上传
                return false;
              }}
              onChange={handleFileChange}
              onRemove={() => {
                setUploadedFile(null);
                return true;
              }}
            >
              <Button icon={<UploadOutlined />}>选择文件</Button>
            </Upload>
            <div style={{ marginTop: 8, color: '#888', fontSize: '12px' }}>
              支持WAV、MP3格式，5-30秒，小于10MB
            </div>
            {uploadedFile && (
              <div style={{ marginTop: 8, color: 'green' }}>
                已选择文件: {uploadedFile.name} ({Math.round(uploadedFile.size/1024)} KB)
              </div>
            )}
          </Form.Item>
          
          <Form.Item style={{ marginTop: 24 }}>
            <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
              <Button onClick={() => {
                setUploadModalVisible(false);
                form.resetFields();
                setUploadedFile(null);
              }}>
                取消
              </Button>
              <Button 
                type="primary" 
                htmlType="submit"
                // 只要表单已填写就允许上传按钮启用
                // 移除了对uploadedFile的依赖，改为仅检查必填字段
              >
                上传
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* Record voice modal */}
      <Modal
        title="录制声音"
        open={recordModalVisible}
        onCancel={handleRecordModalCancel}
        footer={null}
        width={600}
      >
        <div style={{ marginBottom: 20 }}>
          <div style={{ textAlign: 'center', marginBottom: 16 }}>
            <div style={{ fontSize: 24, fontWeight: 'bold' }}>
              {formatRecordTime(recordingTime)}
            </div>
            <div>
              {recordingStatus === 'inactive' && !recordedAudio && '准备录制'}
              {recordingStatus === 'recording' && '正在录制...'}
              {recordingStatus === 'paused' && '已暂停'}
              {recordingStatus === 'inactive' && recordedAudio && '录制完成'}
            </div>
          </div>
          
          {/* Recording progress */}
          <Progress 
            percent={Math.min(100, (recordingTime / 30) * 100)} 
            status={
              recordingTime > 30 ? 'exception' : 
              recordingTime < 5 ? 'active' : 'success'
            }
            strokeColor={{
              '0%': '#108ee9',
              '100%': '#87d068',
            }}
          />
          
          <div style={{ textAlign: 'center', marginTop: 8 }}>
            {recordingTime < 5 && '至少需要5秒'}
            {recordingTime >= 5 && recordingTime <= 30 && '长度合适'}
            {recordingTime > 30 && '已超过最大长度30秒'}
          </div>
        </div>
        
        {/* Recording controls */}
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 20 }}>
          {recordingStatus === 'inactive' && !recordedAudio && (
            <Button type="primary" onClick={startRecording} icon={<AudioOutlined />}>
              开始录制
            </Button>
          )}
          
          {recordingStatus === 'recording' && (
            <>
              <Button onClick={pauseRecording} style={{ marginRight: 8 }}>
                暂停
              </Button>
              <Button type="primary" onClick={stopRecording}>
                停止录制
              </Button>
            </>
          )}
          
          {recordingStatus === 'paused' && (
            <>
              <Button type="primary" onClick={resumeRecording} style={{ marginRight: 8 }}>
                继续
              </Button>
              <Button onClick={stopRecording}>
                停止录制
              </Button>
            </>
          )}
          
          {recordingStatus === 'inactive' && recordedAudio && (
            <>
              <Button onClick={() => {
                const audio = new Audio(recordedAudio.url);
                audio.play();
              }} style={{ marginRight: 8 }}>
                播放
              </Button>
              <Button type="primary" onClick={startRecording} style={{ marginRight: 8 }}>
                重新录制
              </Button>
            </>
          )}
        </div>
        
        {/* Save recording form */}
        {recordingStatus === 'inactive' && recordedAudio && (
          <Form
            form={form}
            layout="vertical"
            onFinish={saveRecording}
          >
            <Form.Item
              name="name"
              label="名称"
              rules={[{ required: true, message: '请输入声音名称' }]}
            >
              <Input placeholder="例如：我的声音1" />
            </Form.Item>
            
            <Form.Item
              name="description"
              label="描述"
            >
              <Input.TextArea placeholder="对声音的描述" />
            </Form.Item>
            
            <Form.Item
              name="tags"
              label="标签"
            >
              <Input placeholder="用逗号分隔，例如：男声,清晰,教学" />
            </Form.Item>
            
            <Form.Item
              name="reference_text"
              label={
                <span>
                  参考文本
                  <Tooltip title="请输入录制音频中说的文字内容，用于声音复制">
                    <InfoCircleOutlined style={{ marginLeft: 8 }} />
                  </Tooltip>
                </span>
              }
              rules={[{ required: true, message: '请输入参考文本' }]}
            >
              <Input.TextArea 
                placeholder="请输入录音中说的文字内容" 
                rows={3}
              />
            </Form.Item>
            
            <Form.Item>
              <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
                <Button onClick={handleRecordModalCancel}>取消</Button>
                <Button 
                  type="primary" 
                  htmlType="submit"
                  disabled={!isValidRecordingLength()}
                >
                  保存
                </Button>
              </Space>
            </Form.Item>
          </Form>
        )}
      </Modal>
    </div>
  );
};

export default EnhancedVoiceLibrary;