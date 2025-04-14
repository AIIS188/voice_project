import React, { useState } from 'react';
import { 
  Layout, 
  Typography, 
  Card, 
  Input, 
  Button, 
  Alert, 
  Space,
  Tabs,
  Divider
} from 'antd';
import { SoundOutlined, DatabaseOutlined } from '@ant-design/icons';
import SimplifiedTTS from '../../components/SimplifiedTTS.jsx';
import EnhancedVoiceLibrary from '../../components/EnhancedVoiceLibrary';

const { Header, Content } = Layout;
const { Title, Paragraph, Text } = Typography;
const { TextArea } = Input;
const { TabPane } = Tabs;

const UnifiedTTSPage = () => {
  // State
  const [text,  setText] = useState('欢迎使用声教助手，这是语音合成系统，可以生成自然流畅的语音。');
  const [synthesisComplete, setSynthesisComplete] = useState(false);
  const [duration, setDuration] = useState(0);
  const [activeTab, setActiveTab] = useState('1');
  
  // Handle text change
  const handleTextChange = (e) => {
    setText(e.target.value);
    setSynthesisComplete(false);
  };
  
  // Handle synthesis complete
  const handleSynthesisComplete = (audioDuration) => {
    setSynthesisComplete(true);
    setDuration(audioDuration);
  };
  
  // Handle clear text
  const handleClearText = () => {
    setText('');
    setSynthesisComplete(false);
  };
  
  // Handle use example text
  const handleUseExample = () => {
    setText('通义灵码是阿里巴巴最新推出的智能编码助手，可以帮助程序员提高编码效率，减少重复工作，提升开发体验。它融合了通义大模型的强大能力，可以理解用户意图，生成高质量的代码。');
    setSynthesisComplete(false);
  };
  
  return (
    <Layout className="unified-tts-page">
      <Header style={{ background: '#fff', padding: '0 20px', borderBottom: '1px solid #f0f0f0' }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <SoundOutlined style={{ fontSize: 24, marginRight: 8 }} />
          <Title level={3} style={{ margin: 0 }}>
            语音合成系统
          </Title>
        </div>
      </Header>
      
      <Content style={{ padding: '20px', backgroundColor: '#f0f2f5', minHeight: 'calc(100vh - 64px)' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto' }}>
          <Card style={{ marginBottom: 20 }}>
            <Paragraph>
              <Text strong>语音合成系统</Text> 支持预训练音色合成和声音复刻，轻松为您的教学内容配上专业级的声音。
            </Paragraph>
            
            <Alert
              message="主要功能"
              description={
                <ul>
                  <li><Text strong>预训练音色</Text>：使用系统内置的优质音色直接合成语音</li>
                  <li><Text strong>声音复刻</Text>：使用您上传的声音样本，复刻您的声音</li>
                  <li><Text strong>统一界面</Text>：简化的界面，无需切换模式，系统会根据选择的声音自动采用最佳合成方式</li>
                  <li><Text strong>声音管理</Text>：管理声音库，包括预训练声音和您上传的声音</li>
                </ul>
              }
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
            />
          </Card>
          
          <Tabs 
            activeKey={activeTab} 
            onChange={setActiveTab}
            type="card"
          >
            <TabPane 
              tab={
                <span>
                  <SoundOutlined /> 语音合成
                </span>
              } 
              key="1"
            >
              <Card title="输入合成文本" style={{ marginBottom: 20 }}>
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
                      <Button onClick={handleClearText}>清空文本</Button>
                      <Button type="primary" onClick={handleUseExample}>使用示例文本</Button>
                    </Space>
                  </div>
                  
                  <div>
                    <Text type="secondary">
                      建议文本长度: 800~2000字
                    </Text>
                  </div>
                </div>
                
                {synthesisComplete && duration > 0 && (
                  <div style={{ marginTop: 16 }}>
                    <Alert
                      message="合成信息"
                      description={`最近一次合成时长: ${duration.toFixed(1)}秒`}
                      type="success"
                      showIcon
                    />
                  </div>
                )}
              </Card>
              
              <Card>
                <SimplifiedTTS 
                  text={text}
                  onComplete={handleSynthesisComplete}
                />
              </Card>
            </TabPane>
            
            <TabPane 
              tab={
                <span>
                  <DatabaseOutlined /> 声音库
                </span>
              } 
              key="2"
            >
              <EnhancedVoiceLibrary />
            </TabPane>
          </Tabs>
        </div>
      </Content>
    </Layout>
  );
};

export default UnifiedTTSPage;