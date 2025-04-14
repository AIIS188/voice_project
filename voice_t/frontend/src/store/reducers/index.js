import { combineReducers } from 'redux';
import ttsReducer from './ttsReducer';

export default combineReducers({
  tts: ttsReducer,
  // Add other reducers here as needed
});