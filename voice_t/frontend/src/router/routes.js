import { lazy } from 'react';
import { HomeOutlined, SoundOutlined, FileTextOutlined, SwapOutlined, BookOutlined, AudioOutlined } from '@ant-design/icons';

// 路由懒加载
const Home = lazy(() => import('../pages/Home'));
const TTSPage = lazy(() => import('../pages/TTSPage'));
const CoursePage = lazy(() => import('../pages/CoursePage'));
const ReplacePage = lazy(() => import('../pages/ReplacePage'));
const VoiceLibraryPage = lazy(() => import('../pages/VoiceLibraryPage'));
const CosyVoicePage = lazy(() => import('../pages/CosyVoicePage'));

// 路由配置
const routes = [
  {
    path: '/',
    component: Home,
    exact: true,
    name: '首页',
    icon: <HomeOutlined />,
    showInMenu: true
  },
  {
    path: '/tts',
    component: TTSPage,
    name: '语音合成',
    icon: <SoundOutlined />,
    showInMenu: true
  },
  {
    path: '/course',
    component: CoursePage,
    name: '课件语音化',
    icon: <BookOutlined />,
    showInMenu: true
  },
  {
    path: '/replace',
    component: ReplacePage,
    name: '声音置换',
    icon: <SwapOutlined />,
    showInMenu: true
  },
  {
    path: '/voice',
    component: VoiceLibraryPage,
    name: '声音库',
    icon: <FileTextOutlined />,
    showInMenu: true
  },
  {
    path: '/cosyvoice',
    component: CosyVoicePage,
    name: 'CosyVoice高级合成',
    icon: <AudioOutlined />,
    showInMenu: true
  }
];

export default routes;