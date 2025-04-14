import axios from 'axios';
import {
  FETCH_VOICES_REQUEST,
  FETCH_VOICES_SUCCESS,
  FETCH_VOICES_FAILURE,
  TTS_SYNTHESIZE_REQUEST,
  TTS_SYNTHESIZE_SUCCESS,
  TTS_SYNTHESIZE_FAILURE,
  TTS_STATUS_UPDATE,
  TTS_CLEAR_RESULT
} from './types';

// 获取声音样本列表
export const fetchVoiceSamples = () => async (dispatch) => {
  dispatch({ type: FETCH_VOICES_REQUEST });
  
  try {
    const response = await axios.get('/api/voice/list');
    
    // 过滤出状态为"ready"的样本
    const readyVoices = response.data.items.filter(item => item.status === 'ready');
    
    // 添加预设声音
    const presetVoices = [
      {
        id: 'preset_1',
        name: '男声教师1',
        description: '标准男声，适合讲解',
        tags: ['male', 'teacher', 'standard'],
        status: 'ready',
        quality_score: 0.95,
      },
      {
        id: 'preset_2',
        name: '女声教师1',
        description: '标准女声，适合讲解',
        tags: ['female', 'teacher', 'standard'],
        status: 'ready',
        quality_score: 0.96,
      },
      {
        id: 'preset_3',
        name: '男声活力',
        description: '活力男声，适合活跃气氛',
        tags: ['male', 'energetic'],
        status: 'ready',
        quality_score: 0.92,
      },
      {
        id: 'preset_4',
        name: '女声温柔',
        description: '温柔女声，适合抒情内容',
        tags: ['female', 'gentle'],
        status: 'ready',
        quality_score: 0.94,
      },
    ];
    
    // 合并预设声音和用户声音
    const combinedVoices = [...presetVoices, ...readyVoices];
    
    dispatch({
      type: FETCH_VOICES_SUCCESS,
      payload: combinedVoices
    });
  } catch (error) {
    console.error('获取声音样本失败:', error);
    
    // 如果API调用失败，也使用预设声音
    const fallbackVoices = [
      {
        id: 'preset_1',
        name: '男声教师1',
        description: '标准男声，适合讲解',
        tags: ['male', 'teacher', 'standard'],
        status: 'ready',
        quality_score: 0.95,
      },
      {
        id: 'preset_2',
        name: '女声教师1',
        description: '标准女声，适合讲解',
        tags: ['female', 'teacher', 'standard'],
        status: 'ready',
        quality_score: 0.96,
      },
      {
        id: 'preset_3',
        name: '男声活力',
        description: '活力男声，适合活跃气氛',
        tags: ['male', 'energetic'],
        status: 'ready',
        quality_score: 0.92,
      },
      {
        id: 'preset_4',
        name: '女声温柔',
        description: '温柔女声，适合抒情内容',
        tags: ['female', 'gentle'],
        status: 'ready',
        quality_score: 0.94,
      },
    ];
    
    dispatch({
      type: FETCH_VOICES_FAILURE,
      payload: error.message,
      fallbackData: fallbackVoices
    });
  }
};

// 合成语音
export const synthesizeSpeech = (text, voiceId, params) => async (dispatch) => {
  dispatch({ type: TTS_SYNTHESIZE_REQUEST });
  
  try {
    const response = await axios.post('/api/tts/synthesize', {
      text,
      voice_id: voiceId,
      params
    });
    
    dispatch({
      type: TTS_SYNTHESIZE_SUCCESS,
      payload: { taskId: response.data.task_id }
    });
  } catch (error) {
    console.error('语音合成请求失败:', error);
    dispatch({
      type: TTS_SYNTHESIZE_FAILURE,
      payload: error.message
    });
  }
};

// 获取合成状态
export const getSynthesisStatus = (taskId) => async (dispatch) => {
  try {
    const response = await axios.get(`/api/tts/status/${taskId}`);
    
    dispatch({
      type: TTS_STATUS_UPDATE,
      payload: { status: response.data }
    });
  } catch (error) {
    console.error('获取合成状态失败:', error);
  }
};

// 清除合成结果
export const clearSynthesisResult = () => ({
  type: TTS_CLEAR_RESULT
});