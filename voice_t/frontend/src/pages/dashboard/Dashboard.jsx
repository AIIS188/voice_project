import React, { useState, useEffect } from 'react';

const EnhancedDashboard = () => {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Styles
  const styles = {
    container: {
      padding: '20px',
      fontFamily: 'Arial, sans-serif'
    },
    header: {
      marginBottom: '20px'
    },
    headerTitle: {
      fontSize: '24px',
      fontWeight: 'bold',
      marginBottom: '8px'
    },
    paragraph: {
      fontSize: '14px',
      color: '#666',
      marginBottom: '16px'
    },
    errorText: {
      color: '#ff4d4f'
    },
    row: {
      display: 'flex',
      flexWrap: 'wrap',
      margin: '0 -8px',
      marginBottom: '16px'
    },
    col: {
      padding: '0 8px',
      boxSizing: 'border-box',
      marginBottom: '16px'
    },
    col6: {
      width: '50%'
    },
    col12: {
      width: '100%'
    },
    colSm6: {
      width: '25%'
    },
    colMd8: {
      width: '66.66%'
    },
    colMd16: {
      width: '33.33%'
    },
    card: {
      border: '1px solid #f0f0f0',
      borderRadius: '4px',
      padding: '16px',
      backgroundColor: '#fff',
      boxShadow: '0 1px 2px rgba(0, 0, 0, 0.05)'
    },
    cardTitle: {
      fontSize: '16px',
      fontWeight: 'bold',
      marginBottom: '12px',
      display: 'flex',
      alignItems: 'center'
    },
    cardSmall: {
      padding: '12px'
    },
    statistic: {
      textAlign: 'center'
    },
    statisticTitle: {
      fontSize: '14px',
      color: '#666',
      marginBottom: '4px'
    },
    statisticValue: {
      fontSize: '24px',
      fontWeight: 'bold',
      color: '#1890ff',
      margin: 0
    },
    statisticBlue: {
      color: '#1890ff'
    },
    statisticGreen: {
      color: '#52c41a'
    },
    statisticPurple: {
      color: '#722ed1'
    },
    statisticOrange: {
      color: '#fa8c16'
    },
    smallStat: {
      fontSize: '16px',
      fontWeight: 'bold'
    },
    divider: {
      margin: '16px 0',
      height: '1px',
      backgroundColor: '#f0f0f0'
    },
    progressContainer: {
      marginBottom: '8px'
    },
    progressLabel: {
      display: 'flex',
      justifyContent: 'space-between',
      marginBottom: '4px'
    },
    progressBar: {
      height: '8px',
      backgroundColor: '#f0f0f0',
      borderRadius: '4px',
      overflow: 'hidden'
    },
    progressFill: {
      height: '100%',
      borderRadius: '4px',
      transition: 'width 0.3s ease'
    },
    badgeContainer: {
      display: 'inline-flex',
      alignItems: 'center'
    },
    badge: {
      display: 'inline-block',
      width: '8px',
      height: '8px',
      borderRadius: '50%',
      marginRight: '4px'
    },
    taskDistribution: {
      display: 'flex',
      height: '20px',
      borderRadius: '4px',
      overflow: 'hidden',
      marginBottom: '8px'
    },
    taskDistributionItem: {
      height: '100%'
    },
    taskLabels: {
      display: 'flex',
      textAlign: 'center'
    },
    timelineContainer: {
      padding: '16px 0'
    },
    timelineItem: {
      position: 'relative',
      paddingBottom: '20px',
      paddingLeft: '20px'
    },
    timelineDot: {
      position: 'absolute',
      left: 0,
      top: '4px',
      width: '10px',
      height: '10px',
      borderRadius: '50%'
    },
    timelineContent: {
      marginBottom: '4px'
    },
    timelineTime: {
      fontSize: '12px',
      color: '#999'
    },
    flex: {
      display: 'flex'
    },
    loadingContainer: {
      textAlign: 'center',
      padding: '50px'
    },
    icon: {
      marginRight: '8px',
      fontSize: '16px'
    },
    alertError: {
      padding: '16px',
      backgroundColor: '#fff2f0',
      border: '1px solid #ffccc7',
      borderRadius: '4px',
      marginBottom: '16px'
    },
    alertTitle: {
      fontWeight: 'bold',
      marginBottom: '8px',
      display: 'flex',
      alignItems: 'center'
    }
  };

  // 加载指标数据
  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        setLoading(true);
        const response = await fetch('/api/metrics');
        if (!response.ok) {
          throw new Error(`API error: ${response.status}`);
        }
        const data = await response.json();
        setMetrics(data);
        setError(null);
      } catch (err) {
        console.error('Failed to fetch metrics:', err);
        setError('获取指标数据失败，请稍后重试');
        
        // 使用模拟数据作为后备
        setMetrics({
          voice_samples_count: 5,
          tts_tasks_count: 12,
          courseware_tasks_count: 3,
          replace_tasks_count: 2,
          total_processed_audio: "324.50 seconds",
          average_processing_time: "2.35 seconds",
          average_quality_score: "0.85",
          recent_activity: [
            {
              type: "voice_sample",
              timestamp: "2023-03-01T14:30:25",
              quality_score: 0.92
            },
            {
              type: "tts",
              timestamp: "2023-03-01T14:45:10",
              duration: 42.3,
              processing_time: 3.2
            }
          ]
        });
      } finally {
        setLoading(false);
      }
    };

    fetchMetrics();
    
    // 每30秒刷新一次
    const interval = setInterval(fetchMetrics, 30000);
    
    return () => clearInterval(interval);
  }, []);

  // 格式化活动类型
  const formatActivityType = (type) => {
    switch (type) {
      case 'voice_sample':
        return '声音样本';
      case 'tts':
        return '语音合成';
      case 'courseware':
        return '课件处理';
      case 'replace':
        return '声音替换';
      default:
        return type;
    }
  };
  
  // 格式化日期时间
  const formatDateTime = (dateTimeStr) => {
    try {
      const date = new Date(dateTimeStr);
      return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      });
    } catch (e) {
      return dateTimeStr;
    }
  };
  
  // 渲染活动时间轴
  const renderTimeline = (activities) => {
    if (!activities || activities.length === 0) {
      return (
        <div style={{ textAlign: 'center', padding: '20px 0', color: '#999' }}>
          暂无活动记录
        </div>
      );
    }

    return (
      <div style={styles.timelineContainer}>
        {activities.slice().reverse().map((activity, index) => {
          const type = formatActivityType(activity.type);
          const time = formatDateTime(activity.timestamp);
          
          let dotColor;
          let content;
          
          switch (activity.type) {
            case 'voice_sample':
              dotColor = '#1890ff';
              content = (
                <div>
                  <div style={{ fontWeight: 'bold' }}>处理了声音样本</div>
                  <div>质量评分: {activity.quality_score?.toFixed(2) || '未知'}</div>
                </div>
              );
              break;
            case 'tts':
              dotColor = '#52c41a';
              content = (
                <div>
                  <div style={{ fontWeight: 'bold' }}>生成了语音合成</div>
                  <div>时长: {activity.duration?.toFixed(1) || '0'} 秒</div>
                  <div>处理时间: {activity.processing_time?.toFixed(1) || '0'} 秒</div>
                </div>
              );
              break;
            case 'courseware':
              dotColor = '#722ed1';
              content = (
                <div>
                  <div style={{ fontWeight: 'bold' }}>处理了课件</div>
                  <div>幻灯片数: {activity.slides_count || '未知'}</div>
                  <div>处理时间: {activity.processing_time?.toFixed(1) || '0'} 秒</div>
                </div>
              );
              break;
            case 'replace':
              dotColor = '#fa8c16';
              content = (
                <div>
                  <div style={{ fontWeight: 'bold' }}>替换了声音</div>
                  <div>时长: {activity.duration?.toFixed(1) || '0'} 秒</div>
                  <div>处理时间: {activity.processing_time?.toFixed(1) || '0'} 秒</div>
                </div>
              );
              break;
            default:
              dotColor = '#999';
              content = <div style={{ fontWeight: 'bold' }}>{type}</div>;
          }
          
          return (
            <div key={index} style={styles.timelineItem}>
              <div 
                style={{
                  ...styles.timelineDot,
                  backgroundColor: dotColor
                }}
              />
              <div style={styles.timelineContent}>
                {content}
              </div>
              <div style={styles.timelineTime}>{time}</div>
            </div>
          );
        })}
      </div>
    );
  };

  // 如果正在加载，显示加载中状态
  if (loading && !metrics) {
    return (
      <div style={styles.loadingContainer}>
        <div>加载中...</div>
      </div>
    );
  }

  // 如果发生错误且没有指标数据
  if (error && !metrics) {
    return (
      <div style={styles.alertError}>
        <div style={styles.alertTitle}>
          ⚠️ 加载失败
        </div>
        <div>{error}</div>
      </div>
    );
  }
  
  // 解析质量评分
  const qualityScore = parseFloat(metrics?.average_quality_score || '0');
  const qualityLevel = qualityScore >= 0.85 ? '优' : 
                       qualityScore >= 0.7 ? '良' : 
                       qualityScore >= 0.5 ? '中' : '差';
  
  // 计算总任务数
  const totalTasks = (metrics?.tts_tasks_count || 0) + 
                   (metrics?.courseware_tasks_count || 0) + 
                   (metrics?.replace_tasks_count || 0);

  // 计算任务分布百分比
  const ttsPercent = ((metrics?.tts_tasks_count || 0) / (totalTasks || 1) * 100).toFixed(1);
  const coursewarePercent = ((metrics?.courseware_tasks_count || 0) / (totalTasks || 1) * 100).toFixed(1);
  const replacePercent = ((metrics?.replace_tasks_count || 0) / (totalTasks || 1) * 100).toFixed(1);

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <div style={styles.headerTitle}>系统概览</div>
        <div style={styles.paragraph}>
          声教助手系统运行指标与数据统计分析。
          {error && <span style={styles.errorText}> (部分数据加载失败，显示缓存数据)</span>}
        </div>
      </div>

      {/* 主要指标统计 */}
      <div style={styles.row}>
        <div style={{...styles.col, ...styles.col6, ...styles.colSm6}}>
          <div style={styles.card}>
            <div style={styles.statistic}>
              <div style={styles.statisticTitle}>声音样本</div>
              <div style={{...styles.statisticValue, ...styles.statisticBlue}}>
                🎤 {metrics?.voice_samples_count || 0}
              </div>
            </div>
          </div>
        </div>
        <div style={{...styles.col, ...styles.col6, ...styles.colSm6}}>
          <div style={styles.card}>
            <div style={styles.statistic}>
              <div style={styles.statisticTitle}>语音合成</div>
              <div style={{...styles.statisticValue, ...styles.statisticGreen}}>
                🔊 {metrics?.tts_tasks_count || 0}
              </div>
            </div>
          </div>
        </div>
        <div style={{...styles.col, ...styles.col6, ...styles.colSm6}}>
          <div style={styles.card}>
            <div style={styles.statistic}>
              <div style={styles.statisticTitle}>课件处理</div>
              <div style={{...styles.statisticValue, ...styles.statisticPurple}}>
                📚 {metrics?.courseware_tasks_count || 0}
              </div>
            </div>
          </div>
        </div>
        <div style={{...styles.col, ...styles.col6, ...styles.colSm6}}>
          <div style={styles.card}>
            <div style={styles.statistic}>
              <div style={styles.statisticTitle}>声音替换</div>
              <div style={{...styles.statisticValue, ...styles.statisticOrange}}>
                🔄 {metrics?.replace_tasks_count || 0}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 详细指标分析 */}
      <div style={styles.row}>
        <div style={{...styles.col, ...styles.colMd8}}>
          <div style={styles.card}>
            <div style={styles.cardTitle}>
              📊 性能指标
            </div>
            
            <div style={styles.row}>
              <div style={{...styles.col, ...styles.col6}}>
                <div style={styles.statistic}>
                  <div style={styles.statisticTitle}>总处理音频时长</div>
                  <div style={{...styles.statisticValue, ...styles.smallStat}}>
                    {metrics?.total_processed_audio || '0 seconds'}
                  </div>
                </div>
              </div>
              <div style={{...styles.col, ...styles.col6}}>
                <div style={styles.statistic}>
                  <div style={styles.statisticTitle}>平均处理时间</div>
                  <div style={{...styles.statisticValue, ...styles.smallStat}}>
                    {metrics?.average_processing_time || '0 seconds'}
                  </div>
                </div>
              </div>
            </div>
            
            <div style={styles.divider} />
            
            <div style={styles.progressContainer}>
              <div style={styles.progressLabel}>
                <span>
                  声音质量评分: <strong>{metrics?.average_quality_score || '0'}</strong>
                </span>
                <span style={styles.badgeContainer}>
                  <span 
                    style={{ 
                      ...styles.badge, 
                      backgroundColor: qualityLevel === '优' ? '#52c41a' :
                                       qualityLevel === '良' ? '#1890ff' :
                                       qualityLevel === '中' ? '#faad14' : '#f5222d'
                    }} 
                  />
                  {qualityLevel}
                </span>
              </div>
              <div style={styles.progressBar}>
                <div 
                  style={{
                    ...styles.progressFill,
                    width: `${qualityScore * 100}%`,
                    backgroundColor: qualityLevel === '优' ? '#52c41a' :
                                    qualityLevel === '良' ? '#1890ff' :
                                    qualityLevel === '中' ? '#faad14' : '#f5222d'
                  }}
                />
              </div>
            </div>
            
            <div style={styles.divider} />
            
            <div>
              <div style={{...styles.headerTitle, fontSize: '16px'}}>任务分布</div>
              <div style={styles.taskDistribution}>
                <div style={{
                  ...styles.taskDistributionItem, 
                  flex: metrics?.tts_tasks_count || 1,
                  backgroundColor: '#52c41a',
                  borderRadius: '4px 0 0 4px'
                }} />
                <div style={{
                  ...styles.taskDistributionItem, 
                  flex: metrics?.courseware_tasks_count || 1,
                  backgroundColor: '#722ed1'
                }} />
                <div style={{
                  ...styles.taskDistributionItem, 
                  flex: metrics?.replace_tasks_count || 1,
                  backgroundColor: '#fa8c16',
                  borderRadius: '0 4px 4px 0'
                }} />
              </div>
              <div style={styles.taskLabels}>
                <div style={{ flex: metrics?.tts_tasks_count || 1 }}>
                  <div style={styles.badgeContainer}>
                    <span style={{ ...styles.badge, backgroundColor: '#52c41a' }} />
                    语音合成
                  </div>
                  <div>{ttsPercent}%</div>
                </div>
                <div style={{ flex: metrics?.courseware_tasks_count || 1 }}>
                  <div style={styles.badgeContainer}>
                    <span style={{ ...styles.badge, backgroundColor: '#722ed1' }} />
                    课件处理
                  </div>
                  <div>{coursewarePercent}%</div>
                </div>
                <div style={{ flex: metrics?.replace_tasks_count || 1 }}>
                  <div style={styles.badgeContainer}>
                    <span style={{ ...styles.badge, backgroundColor: '#fa8c16' }} />
                    声音替换
                  </div>
                  <div>{replacePercent}%</div>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <div style={{...styles.col, ...styles.colMd16}}>
          <div style={styles.card}>
            <div style={styles.cardTitle}>
              🕒 最近活动
            </div>
            {renderTimeline(metrics?.recent_activity)}
          </div>
        </div>
      </div>
      
      {/* 信息卡片 */}
      <div style={styles.row}>
        <div style={{...styles.col, ...styles.col12}}>
          <div style={styles.card}>
            <div style={styles.cardTitle}>
              🔬 系统分析
            </div>
            <div style={styles.row}>
              <div style={{...styles.col, ...styles.col6, ...styles.colMd8}}>
                <div style={{...styles.card, ...styles.cardSmall}}>
                  <div style={{...styles.cardTitle, fontSize: '14px'}}>性能状况</div>
                  <div style={styles.flex}>
                    <div style={{...styles.icon, color: '#52c41a'}}>✅</div>
                    <div>
                      <div style={{ fontWeight: 'bold' }}>系统运行良好</div>
                      <div>平均响应时间: {metrics?.average_processing_time || '未知'}</div>
                    </div>
                  </div>
                </div>
              </div>
              <div style={{...styles.col, ...styles.col6, ...styles.colMd8}}>
                <div style={{...styles.card, ...styles.cardSmall}}>
                  <div style={{...styles.cardTitle, fontSize: '14px'}}>语音质量</div>
                  <div style={styles.flex}>
                    <div style={{...styles.icon, color: '#1890ff'}}>📈</div>
                    <div>
                      <div style={{ fontWeight: 'bold' }}>平均质量评分: {metrics?.average_quality_score || '未知'}</div>
                      <div>质量等级: {qualityLevel}</div>
                    </div>
                  </div>
                </div>
              </div>
              <div style={{...styles.col, ...styles.col6, ...styles.colMd8}}>
                <div style={{...styles.card, ...styles.cardSmall}}>
                  <div style={{...styles.cardTitle, fontSize: '14px'}}>使用情况</div>
                  <div style={styles.flex}>
                    <div style={{...styles.icon, color: '#722ed1'}}>⬆️</div>
                    <div>
                      <div style={{ fontWeight: 'bold' }}>总任务数: {totalTasks}</div>
                      <div>总处理音频: {metrics?.total_processed_audio || '未知'}</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default EnhancedDashboard;