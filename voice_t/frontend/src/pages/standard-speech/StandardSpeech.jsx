import React, { useState, useRef } from 'react';
import { 
  Typography, Card, Form, Input, Button, Select, 
  Slider, Radio, Space, Tabs, Row, Col, Spin, message 
} from 'antd';
import { 
  AudioOutlined, DownloadOutlined,
  PlayCircleOutlined, PauseCircleOutlined, 
  SoundOutlined, GlobalOutlined
} from '@ant-design/icons';
import axios from 'axios';

const { Title, Paragraph, Text } = Typography;
const { TextArea } = Input;
const { Option } = Select;
const { TabPane } = Tabs;

const StandardSpeech = () => {
  // 状态管理
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [audioUrl, setAudioUrl] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  
  // 引用
  const audioRef = useRef(null);
  
  // 模拟生成标准语言示例
  const generateStandardSpeech = async (values) => {
    // 在实际项目中，这里会调用API
    // 这里使用模拟数据作为示例
    try {
      setLoading(true);
      
      // 模拟API请求延迟
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      // 模拟生成音频（这里使用示例音频URL）
      // 在实际实现中，这会是从后端获取的音频URL
      const mockAudioUrl = 'https://example.com/api/standard-speech/sample.mp3';
      
      // 由于无法真正获取音频，这里直接使用文字转语音API来演示
      // 这是一个简单的语音演示
      const text = values.text || "这是标准语言输出的示例，请想象这是符合您设置的标准发音。";
      const speech = new SpeechSynthesisUtterance(text);
      speech.lang = values.language === 'en-US' ? 'en-US' : 'zh-CN';
      speech.rate = values.speed;
      speech.pitch = values.pitch + 1; // 调整到适合的范围
      speech.volume = values.volume;
      
      // 停止之前的语音
      window.speechSynthesis.cancel();
      
      // 播放新语音
      window.speechSynthesis.speak(speech);
      setIsPlaying(true);
      
      // 监听结束事件
      speech.onend = () => {
        setIsPlaying(false);
      };
      
      // 设置模拟音频URL
      setAudioUrl(mockAudioUrl);
      
      message.success('标准语言生成成功');
    } catch (error) {
      console.error('生成失败:', error);
      message.error('生成失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };
  
  // 处理表单提交
  const handleSubmit = (values) => {
    if (!values.text || values.text.trim().length < 5) {
      message.error('请输入至少5个字符的文本内容');
      return;
    }
    
    generateStandardSpeech(values);
  };
  
  // 播放/暂停演示音频
  const togglePlay = () => {
    if (window.speechSynthesis.speaking) {
      if (window.speechSynthesis.paused) {
        window.speechSynthesis.resume();
        setIsPlaying(true);
      } else {
        window.speechSynthesis.pause();
        setIsPlaying(false);
      }
    } else {
      const values = form.getFieldsValue();
      generateStandardSpeech(values);
    }
  };
  
  // 停止演示音频
  const stopPlay = () => {
    window.speechSynthesis.cancel();
    setIsPlaying(false);
  };
  
  // 渲染语音参数控制器
  const renderControlsTab = () => (
    <div className="speech-controls">
      <Row gutter={[16, 16]}>
        <Col span={12}>
          <Form.Item
            name="speed"
            label="语速"
            initialValue={1.0}
          >
            <Slider
              min={0.5}
              max={2.0}
              step={0.1}
              marks={{
                0.5: '慢',
                1.0: '正常',
                2.0: '快'
              }}
            />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item
            name="pitch"
            label="音调"
            initialValue={0}
          >
            <Slider
              min={-1.0}
              max={1.0}
              step={0.1}
              marks={{
                '-1.0': '低',
                '0': '正常',
                '1.0': '高'
              }}
            />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item
            name="volume"
            label="音量"
            initialValue={1.0}
          >
            <Slider
              min={0.1}
              max={1.0}
              step={0.1}
              marks={{
                0.1: '低',
                0.5: '中',
                1.0: '高'
              }}
            />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item
            name="emphasis"
            label="重音强度"
            initialValue={1.0}
          >
            <Slider
              min={0.0}
              max={2.0}
              step={0.2}
              marks={{
                0.0: '无',
                1.0: '中',
                2.0: '强'
              }}
            />
          </Form.Item>
        </Col>
      </Row>
    </div>
  );
  
  // 渲染标准语言选项
  const renderLanguageTab = () => (
    <div className="language-options">
      <Form.Item
        name="language"
        label="语言"
        initialValue="zh-CN"
      >
        <Radio.Group>
          <Radio.Button value="zh-CN">普通话</Radio.Button>
          <Radio.Button value="en-US">英语</Radio.Button>
        </Radio.Group>
      </Form.Item>
      
      <Form.Item
        name="accent"
        label="口音"
        initialValue="standard"
      >
        <Select style={{ width: '100%' }}>
          <Option value="standard">标准</Option>
          <Option value="beijing">北京</Option>
          <Option value="canton">粤语</Option>
          <Option value="us">美式</Option>
          <Option value="uk">英式</Option>
          <Option value="australia">澳式</Option>
        </Select>
      </Form.Item>
      
      <Form.Item
        name="gender"
        label="声音性别"
        initialValue="female"
      >
        <Radio.Group>
          <Radio.Button value="female">女声</Radio.Button>
          <Radio.Button value="male">男声</Radio.Button>
        </Radio.Group>
      </Form.Item>
      
      <Form.Item
        name="age"
        label="声音年龄"
        initialValue="adult"
      >
        <Radio.Group>
          <Radio.Button value="adult">成年</Radio.Button>
          <Radio.Button value="elder">老年</Radio.Button>
          <Radio.Button value="child">儿童</Radio.Button>
        </Radio.Group>
      </Form.Item>
    </div>
  );
  
  // 渲染高级选项
  const renderAdvancedTab = () => (
    <div className="advanced-options">
      <Form.Item
        name="clarity"
        label="清晰度增强"
        initialValue="medium"
      >
        <Radio.Group>
          <Radio.Button value="low">关闭</Radio.Button>
          <Radio.Button value="medium">中等</Radio.Button>
          <Radio.Button value="high">高</Radio.Button>
        </Radio.Group>
      </Form.Item>
      
      <Form.Item
        name="syllable"
        label="音节分解"
        initialValue={false}
        valuePropName="checked"
      >
        <Radio.Group>
          <Radio.Button value={false}>关闭</Radio.Button>
          <Radio.Button value={true}>开启</Radio.Button>
        </Radio.Group>
      </Form.Item>
      
      <Form.Item
        name="pause_duration"
        label="停顿时长"
        initialValue="normal"
      >
        <Radio.Group>
          <Radio.Button value="short">短</Radio.Button>
          <Radio.Button value="normal">正常</Radio.Button>
          <Radio.Button value="long">长</Radio.Button>
        </Radio.Group>
      </Form.Item>
      
      <Form.Item
        name="highlight_key"
        label="重点词强调"
        initialValue={false}
        valuePropName="checked"
      >
        <Radio.Group>
          <Radio.Button value={false}>关闭</Radio.Button>
          <Radio.Button value={true}>开启</Radio.Button>
        </Radio.Group>
      </Form.Item>
    </div>
  );

  return (
    <div className="standard-speech">
      <div className="page-header">
        <Title level={2}>标准语言输出</Title>
        <Paragraph>
          生成标准语言发音，适用于语言学习和标准发音示范。
          支持多种语言和口音，可以调整语速、音调等参数。
        </Paragraph>
      </div>

      <Form form={form} layout="vertical" onFinish={handleSubmit}>
        <Row gutter={[16, 16]}>
          <Col xs={24} lg={16}>
            <Card title="文本内容" bordered={false}>
              <Form.Item
                name="text"
                rules={[{ required: true, message: '请输入文本内容' }]}
              >
                <TextArea
                  rows={6}
                  placeholder="请输入要转换为标准语音的文本内容"
                  maxLength={2000}
                  showCount
                />
              </Form.Item>
              
              <div style={{ display: 'flex', justifyContent: 'center', marginTop: 16 }}>
                <Space>
                  <Button
                    type="primary"
                    icon={<AudioOutlined />}
                    onClick={() => form.submit()}
                    loading={loading}
                  >
                    生成标准语音
                  </Button>
                  {audioUrl && (
                    <Button
                      icon={isPlaying ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
                      onClick={togglePlay}
                    >
                      {isPlaying ? '暂停' : '播放'}
                    </Button>
                  )}
                  {isPlaying && (
                    <Button
                      danger
                      onClick={stopPlay}
                    >
                      停止
                    </Button>
                  )}
                </Space>
              </div>
            </Card>
          </Col>
          
          <Col xs={24} lg={8}>
            <Card title="语言设置" bordered={false}>
              <Tabs defaultActiveKey="language">
                <TabPane 
                  tab={
                    <span>
                      <GlobalOutlined />
                      语言选项
                    </span>
                  }
                  key="language"
                >
                  {renderLanguageTab()}
                </TabPane>
                <TabPane 
                  tab={
                    <span>
                      <SoundOutlined />
                      语音控制
                    </span>
                  }
                  key="controls"
                >
                  {renderControlsTab()}
                </TabPane>
                <TabPane 
                  tab={
                    <span>
                      <span>高级设置</span>
                    </span>
                  }
                  key="advanced"
                >
                  {renderAdvancedTab()}
                </TabPane>
              </Tabs>
            </Card>
            
            {/* 音频预览卡片 */}
            <Card 
              title="音频输出" 
              bordered={false}
              style={{ marginTop: 16 }}
            >
              {loading ? (
                <div style={{ textAlign: 'center', padding: '20px 0' }}>
                  <Spin tip="生成中..." />
                </div>
              ) : (
                <div>
                  {audioUrl ? (
                    <div>
                      <div style={{ marginBottom: 16 }}>
                        <Text>标准语音已生成，可以播放或下载。</Text>
                      </div>
                      
                      {/* 在实际项目中，这里会是真实的音频播放器 */}
                      <div style={{ marginBottom: 16 }}>
                        <Text type="secondary">
                          (注：当前为演示模式，使用浏览器语音合成API)
                        </Text>
                      </div>
                      
                      <div className="audio-actions" style={{ textAlign: 'center' }}>
                        <Space>
                          <Button 
                            type="primary"
                            icon={<DownloadOutlined />}
                            disabled={!audioUrl}
                          >
                            下载音频
                          </Button>
                        </Space>
                      </div>
                    </div>
                  ) : (
                    <div style={{ textAlign: 'center', padding: '30px 0', color: '#aaa' }}>
                      <div>点击"生成标准语音"按钮生成音频</div>
                    </div>
                  )}
                </div>
              )}
            </Card>
          </Col>
        </Row>
      </Form>
      
      {/* 比较功能 */}
      <Card title="标准发音比较" style={{ marginTop: 16 }} bordered={false}>
        <Paragraph>
          比较不同口音之间的发音差异，帮助理解标准与非标准发音的区别。
        </Paragraph>
        
        <div className="comparison-panel">
          <Row gutter={[16, 16]}>
            <Col xs={24} md={8}>
              <Card title="标准普通话" size="small">
                <div style={{ textAlign: 'center', padding: '10px 0' }}>
                  <Button icon={<PlayCircleOutlined />}>播放示例</Button>
                </div>
                <div>
                  <Text type="secondary">
                    标准普通话特点：清晰的声调变化，准确的辅音发音，元音饱满。
                  </Text>
                </div>
              </Card>
            </Col>
            <Col xs={24} md={8}>
              <Card title="北京口音" size="small">
                <div style={{ textAlign: 'center', padding: '10px 0' }}>
                  <Button icon={<PlayCircleOutlined />}>播放示例</Button>
                </div>
                <div>
                  <Text type="secondary">
                    北京口音特点：儿化音多，部分音节变形，声调略有不同。
                  </Text>
                </div>
              </Card>
            </Col>
            <Col xs={24} md={8}>
              <Card title="粤语口音" size="small">
                <div style={{ textAlign: 'center', padding: '10px 0' }}>
                  <Button icon={<PlayCircleOutlined />}>播放示例</Button>
                </div>
                <div>
                  <Text type="secondary">
                    粤语口音特点：声调丰富，部分辅音发音位置不同，句尾音调特殊。
                  </Text>
                </div>
              </Card>
            </Col>
          </Row>
        </div>
      </Card>
      
      {/* 教学提示 */}
      <Card title="语音学习提示" style={{ marginTop: 16 }} bordered={false}>
        <Row gutter={[16, 16]}>
          <Col xs={24} md={8}>
            <Title level={4}>普通话学习要点</Title>
            <ul>
              <li>注意四声的准确发音</li>
              <li>区分zh/ch/sh与z/c/s</li>
              <li>掌握前后鼻音的区别</li>
              <li>避免方言音的影响</li>
            </ul>
          </Col>
          <Col xs={24} md={8}>
            <Title level={4}>英语发音要点</Title>
            <ul>
              <li>注意长短元音的区分</li>
              <li>掌握辅音连缀规则</li>
              <li>重音和弱读的正确使用</li>
              <li>句子语调的自然表达</li>
            </ul>
          </Col>
          <Col xs={24} md={8}>
            <Title level={4}>有效学习方法</Title>
            <ul>
              <li>反复模仿标准发音</li>
              <li>录音与标准进行对比</li>
              <li>关注口型和气息控制</li>
              <li>培养语感，注重整体节奏</li>
            </ul>
          </Col>
        </Row>
      </Card>
    </div>
  );
};

export default StandardSpeech;