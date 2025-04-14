import React from 'react';
import { Routes, Route, Link, useLocation } from 'react-router-dom';
import { Layout, Menu, Typography, Button } from 'antd';
import {
  HomeOutlined,
  SoundOutlined,
  AudioOutlined,
  FileTextOutlined,
  BookOutlined,
  SwapOutlined,
  GithubOutlined
} from '@ant-design/icons';

// 页面导入
import Dashboard from './pages/dashboard/Dashboard';
import EnhancedVoiceLibrary from './pages/voice-library/EnhancedVoiceLibrary'; // 更新为增强版声音库
import UnifiedTTSPage from './pages/tts/UnifiedTTSPage'; // 新的统一TTS页面
import StandardSpeech from './pages/CosyVoicePage';
import CourseVoice from './pages/course-voice/CourseVoice';
import VoiceReplace from './pages/voice-replace/VoiceReplace';

// 布局组件
const { Header, Content, Footer, Sider } = Layout;
const { Title } = Typography;

function App() {
  const location = useLocation();
  const [collapsed, setCollapsed] = React.useState(false);

  // 菜单项定义
  const menuItems = [
    {
      key: '/',
      icon: <HomeOutlined />,
      label: <Link to="/">首页</Link>,
    },
    {
      key: '/voice-library',
      icon: <SoundOutlined />,
      label: <Link to="/voice-library">声音库</Link>, // 更新名称以反映增强功能
    },
    {
      key: '/text-to-speech',
      icon: <AudioOutlined />,
      label: <Link to="/text-to-speech">语音合成</Link>, // 更新为更简洁的名称
    },
    {
      key: '/standard-speech',
      icon: <FileTextOutlined />,
      label: <Link to="/standard-speech">标准语言输出</Link>,
    },
    {
      key: '/course-voice',
      icon: <BookOutlined />,
      label: <Link to="/course-voice">课件语音化</Link>,
    },
    {
      key: '/voice-replace',
      icon: <SwapOutlined />,
      label: <Link to="/voice-replace">声音置换与字幕</Link>,
    },
  ];

  return (
    <Layout className="full-height">
      <Header style={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between',
        padding: '0 24px',
        backgroundColor: '#fff',
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <SoundOutlined style={{ fontSize: '24px', marginRight: '12px', color: '#1890ff' }} />
          <Title level={3} style={{ margin: 0 }}>声教助手</Title>
        </div>
        <Button 
          type="link" 
          icon={<GithubOutlined />}
          href="https://github.com" 
          target="_blank"
        >
          GitHub
        </Button>
      </Header>
      <Layout>
        <Sider 
          width={200} 
          collapsible 
          collapsed={collapsed}
          onCollapse={(value) => setCollapsed(value)}
        >
          <Menu
            mode="inline"
            selectedKeys={[location.pathname]}
            style={{ height: '100%', borderRight: 0 }}
            items={menuItems}
          />
        </Sider>
        <Layout style={{ padding: '0 24px 24px' }}>
          <Content
            className="content-container"
            style={{
              padding: 24,
              margin: '16px 0',
              minHeight: 280,
            }}
          >
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/voice-library" element={<EnhancedVoiceLibrary />} />
              <Route path="/text-to-speech" element={<UnifiedTTSPage />} />
              <Route path="/standard-speech" element={<StandardSpeech />} />
              <Route path="/course-voice" element={<CourseVoice />} />
              <Route path="/voice-replace" element={<VoiceReplace />} />
            </Routes>
          </Content>
        </Layout>
      </Layout>
      <Footer style={{ textAlign: 'center', padding: '12px 50px' }}>
        声教助手 ©2023 - 基于AI语音合成的教学声音处理软件
      </Footer>
    </Layout>
  );
}

export default App;