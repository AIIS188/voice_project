import React, { useState } from 'react';
import { 
  Layout, 
  Typography, 
  Card, 
  Input, 
  Button, 
  Divider, 
  message, 
  Alert, 
  Collapse, 
  Space
} from 'antd';
import { SoundOutlined, QuestionCircleOutlined } from '@ant-design/icons';
import CosyVoiceTTS from '../components/CosyVoiceTTS';

const { Header, Content } = Layout;
const { Title, Paragraph, Text } = Typography;
const { TextArea } = Input;
const { Panel } = Collapse;

const CosyVoicePage = () => {
  // 状态管理
  const [text, setText] = useState('欢迎使用声教助手，这是语音合成系统，可以生成自然流畅的语音。');
  const [synthesisComplete, setSynthesisComplete] = useState(false);
  const [duration, setDuration] = useState(0);
  
  // 处理文本变化
  const handleTextChange = (e) => {
    setText(e.target.value);
    setSynthesisComplete(false);
  };
  
  // 处理合成完成
  const handleSynthesisComplete = (audioDuration) => {
    setSynthesisComplete(true);
    setDuration(audioDuration);
  };
  
  // 处理清空文本
  const handleClearText = () => {
    setText('');
    setSynthesisComplete(false);
  };
  
  // 处理使用示例文本
  const handleUseExample = () => {
    setText('通义灵码是阿里巴巴最新推出的智能编码助手，可以帮助程序员提高编码效率，减少重复工作，提升开发体验。它融合了通义大模型的强大能力，可以理解用户意图，生成高质量的代码。');
    setSynthesisComplete(false);
  };
  
  return (
    <Layout className="cosyvoice-page">
      <Header style={{ background: '#fff', padding: '0 20px', borderBottom: '1px solid #f0f0f0' }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <SoundOutlined style={{ fontSize: 24, marginRight: 8 }} />
          <Title level={3} style={{ margin: 0 }}>
            语音合成
          </Title>
        </div>
      </Header>
      
      <Content style={{ padding: '20px', backgroundColor: '#f0f2f5', minHeight: 'calc(100vh - 64px)' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto' }}>
          <Card style={{ marginBottom: 20 }}>
            <Paragraph>
              <Text strong></Text> 是高质量语音合成引擎，可以生成自然流畅的语音。
              本系统集成了，支持多种合成模式，让您的教学内容配上专业级的声音。
            </Paragraph>
            
            <Alert
              message="主要功能"
              description={
                <ul>
                  <li><Text strong>预训练音色</Text>：使用系统内置的优质音色直接合成语音</li>
                  <li><Text strong>3s极速复刻</Text>：只需3秒参考音频，就能复刻任何声音</li>
                  <li><Text strong>跨语种复刻</Text>：保持声音特征，输出不同语言的发音</li>
                  <li><Text strong>自然语言控制</Text>：通过文本指令控制语音的风格和情感</li>
                </ul>
              }
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
            />
          </Card>
          
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
            <CosyVoiceTTS 
              text={text}
              onComplete={handleSynthesisComplete}
            />
          </Card>
          
        </div>
      </Content>
    </Layout>
  );
};

export default CosyVoicePage;