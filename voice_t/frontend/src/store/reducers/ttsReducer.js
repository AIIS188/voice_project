import { 
  FETCH_VOICES_REQUEST,
  FETCH_VOICES_SUCCESS,
  FETCH_VOICES_FAILURE,
  TTS_SYNTHESIZE_REQUEST,
  TTS_SYNTHESIZE_SUCCESS,
  TTS_SYNTHESIZE_FAILURE,
  TTS_STATUS_UPDATE,
  TTS_CLEAR_RESULT
} from '../actions/types';

const initialState = {
  voiceSamples: [],
  loading: false,
  error: null,
  synthesizing: false,
  taskId: null,
  taskStatus: null,
  audioUrl: null
};

export default function ttsReducer(state = initialState, action) {
  switch (action.type) {
    case FETCH_VOICES_REQUEST:
      return {
        ...state,
        loading: true
      };
      
    case FETCH_VOICES_SUCCESS:
      return {
        ...state,
        loading: false,
        voiceSamples: action.payload,
        error: null
      };
      
    case FETCH_VOICES_FAILURE:
      return {
        ...state,
        loading: false,
        error: action.payload,
        voiceSamples: action.fallbackData || [] // 使用后备数据
      };
      
    case TTS_SYNTHESIZE_REQUEST:
      return {
        ...state,
        synthesizing: true,
        taskId: null,
        taskStatus: null,
        audioUrl: null
      };
      
    case TTS_SYNTHESIZE_SUCCESS:
      return {
        ...state,
        taskId: action.payload.taskId
      };
      
    case TTS_SYNTHESIZE_FAILURE:
      return {
        ...state,
        synthesizing: false,
        error: action.payload
      };
      
    case TTS_STATUS_UPDATE:
      const { status } = action.payload;
      
      // 如果合成完成，获取音频URL
      if (status.status === 'completed') {
        return {
          ...state,
          synthesizing: false,
          taskStatus: status,
          audioUrl: `/api/tts/download/${state.taskId}`
        };
      }
      
      // 如果失败，停止合成
      if (status.status === 'failed') {
        return {
          ...state,
          synthesizing: false,
          taskStatus: status
        };
      }
      
      // 否则只更新状态
      return {
        ...state,
        taskStatus: status
      };
      
    case TTS_CLEAR_RESULT:
      return {
        ...state,
        taskId: null,
        taskStatus: null,
        audioUrl: null
      };
      
    default:
      return state;
  }
}