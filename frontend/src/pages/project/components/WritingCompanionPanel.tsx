// P5A: AI 写作伴侣侧面板
import { useState, useEffect } from 'react';
import { Card, Button, Spin, Tag, Typography, Empty, Divider } from 'antd';
import { BulbOutlined, ForwardOutlined, ExclamationCircleOutlined, ReloadOutlined, CloseOutlined, LightbulbOutlined } from '@ant-design/icons';
import { companionApi, type ContinueSuggestion, type InspirationIdea, type CharacterReminder } from '../../../services/api';

const { Text, Title } = Typography;

interface Props {
  projectId: string;
  projectName: string;
  chapterNumber: number;
  recentText: string;
  previousContext: string;
  worldview: string;
  characterList: string;
  onClose: () => void;
  onInsert: (text: string) => void;
}

const SEVERITY = (s: string) =>
  s === 'urgent' ? 'red' : s === 'warn' ? 'orange' : 'blue';

export default function WritingCompanionPanel({
  projectId, projectName, chapterNumber, recentText,
  previousContext, worldview, characterList,
  onClose, onInsert,
}: Props) {
  const [suggestions, setSuggestions] = useState<ContinueSuggestion[]>([]);
  const [inspirations, setInspirations] = useState<InspirationIdea[]>([]);
  const [reminders, setReminders] = useState<CharacterReminder[]>([]);
  const [sugLoading, setSugLoading] = useState(false);
  const [inspLoading, setInspLoading] = useState(false);
  const [remLoading, setRemLoading] = useState(false);

  const fetchReminders = async () => {
    setRemLoading(true);
    try {
      const { data } = await companionApi.reminders(projectId, chapterNumber);
      setReminders(data.reminders || []);
    } catch { /* noop */ }
    setRemLoading(false);
  };

  const fetchSuggestions = async () => {
    setSugLoading(true);
    try {
      const { data } = await companionApi.continueSuggestions({
        project_name: projectName,
        chapter_number: chapterNumber,
        recent_text: recentText,
        previous_context: previousContext,
        worldview,
        character_list: characterList,
      });
      setSuggestions(data.suggestions || []);
    } catch { /* noop */ }
    setSugLoading(false);
  };

  const fetchInspirations = async () => {
    setInspLoading(true);
    try {
      const { data } = await companionApi.inspirations({
        project_name: projectName,
        chapter_number: chapterNumber,
        current_scene: recentText.slice(-2000),
        worldview,
      });
      setInspirations(data.ideas || []);
    } catch { /* noop */ }
    setInspLoading(false);
  };

  useEffect(() => { fetchReminders(); }, [projectId, chapterNumber]);

  return (
    <div style={{
      width: 320,
      height: '100%',
      borderLeft: '1px solid #f0f0f0',
      background: '#fafafa',
      padding: '12px',
      overflow: 'auto',
      display: 'flex',
      flexDirection: 'column',
      gap: 12,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Title level={5} style={{ margin: 0 }}>🤝 AI 写作伴侣</Title>
        <Button type="text" icon={<CloseOutlined />} size="small" onClick={onClose} />
      </div>

      {/* 角色出场提醒 */}
      <Card size="small" title={<span><ExclamationCircleOutlined style={{ color: '#fa8c16' }} /> 角色提醒</span>}
        extra={<Button type="link" size="small" icon={<ReloadOutlined />} loading={remLoading} onClick={fetchReminders} />}>
        {reminders.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {reminders.map((r, i) => (
              <div key={i} style={{ padding: '4px 8px', background: 'white', borderRadius: 4, fontSize: 12 }}>
                <Tag color={SEVERITY(r.severity)}>{r.character_name}</Tag>
                {r.last_seen_chapter > 0 && <Text type="secondary">第{r.last_seen_chapter}章</Text>}
                <Text style={{ display: 'block', marginTop: 2 }}>{r.status_note}</Text>
              </div>
            ))}
          </div>
        ) : <Text type="secondary" style={{ fontSize: 12 }}>所有角色正常出场</Text>}
      </Card>

      {/* 续写建议 */}
      <Card size="small" title={<span><ForwardOutlined style={{ color: '#1890ff' }} /> 续写方向</span>}
        extra={<Button type="link" size="small" icon={<ReloadOutlined />} loading={sugLoading} onClick={fetchSuggestions} />}>
        {suggestions.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {suggestions.map((s, i) => (
              <div key={i} style={{ padding: '6px 8px', background: 'white', borderRadius: 4 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                  <Tag color="geekblue">{s.direction}</Tag>
                  <Button type="dashed" size="small" onClick={() => onInsert(s.text)}>插入</Button>
                </div>
                <Text style={{ fontSize: 12 }}>{s.text}</Text>
                <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 4 }}>
                  💡 {s.reasoning}
                </Text>
              </div>
            ))}
          </div>
        ) : sugLoading ? <Spin /> : <Text type="secondary" style={{ fontSize: 12 }}>点击刷新获取续写建议</Text>}
      </Card>

      {/* 灵感点子 */}
      <Card size="small" title={<span><LightbulbOutlined style={{ color: '#52c41a' }} /> 灵感推荐</span>}
        extra={<Button type="link" size="small" icon={<ReloadOutlined />} loading={inspLoading} onClick={fetchInspirations} />}>
        {inspirations.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {inspirations.map((idea, i) => (
              <div key={i} style={{ padding: '10px 8px', background: 'white', borderRadius: 4 }}>
                <Tag color="green">{idea.category}</Tag>
                <Text strong style={{ display: 'block', fontSize: 13, marginTop: 4 }}>{idea.concept}</Text>
                <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 4 }}>
                  ✍️ {idea.scene_suggestion}
                </Text>
              </div>
            ))}
          </div>
        ) : inspLoading ? <Spin /> : <Text type="secondary" style={{ fontSize: 12 }}>点击刷新获取灵感推荐</Text>}
      </Card>
    </div>
  );
}